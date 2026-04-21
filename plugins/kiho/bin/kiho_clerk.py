#!/usr/bin/env python3
"""
kiho_clerk.py — committee transcript deterministic parser (v5.19 Tier-B).

Reads a `transcript.md` written per the format in
`references/committee-rules.md` §"Transcript format" and emits a
JSONL stream at `rounds.jsonl` next to the transcript (or to the
path given by `--out`). One JSONL row per message event plus one
closing row per transcript. Pure stdlib; no LLM calls; parse-only —
never mutates the transcript.

Usage (CLI):
    kiho_clerk.py extract-rounds --transcript <path> [--out <path>]
                                 [--plugin-root <path>]
    kiho_clerk.py extract-rounds --self-test [--plugin-root <path>]

Exit codes (v5.15.2 convention):
    0 — transcript parsed cleanly; JSONL written (or --self-test passed)
    1 — transcript malformed (missing frontmatter, bad round/phase
        nesting, malformed message bullet, unclosed transcript)
    2 — usage error (bad flags, missing --transcript, path not a file)
    3 — internal error (unexpected exception)

JSONL schema (one object per line):

    {
      "committee_id": "<from frontmatter>",
      "chartered_at": "<ISO-8601 with tz>",
      "round": <int>,                     # 0 for the Close row
      "phase": "research" | "suggest" | "challenge" | "choose" | "close",
      "author": "@agent-name",            # null on Close rows
      "confidence": 0.XX,                 # null on Close rows / placeholders
      "position": "<summary text>",
      "rationale": "<optional blockquote text>",   # absent when no quote
      "outcome": "<unanimous|consensus|split|deferred>",   # only on Close rows
      "final_confidence": 0.XX,           # only on Close rows
      "rounds_used": <int>,               # only on Close rows
      "decision": "<quoted sentence>"     # only on Close rows
    }

Grounding:
    * references/committee-rules.md § "Transcript format"
    * references/data-storage-matrix.md § 5 (committee-records-jsonl row)
    * bin/kb_lint_skill_solutions.py — structural template

Non-goals (explicit):
    * Does NOT auto-discover transcripts. Caller passes `--transcript`.
    * Does NOT write to sqlite. That is the Wave 2 committee-index-sqlite
      row — ships only when the first cross-committee query fires.
    * Does NOT lint content (wording, confidence accuracy). Only
      validates structure per the format spec.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --- patterns ---------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_ROUND_HEADER_RE = re.compile(r"^##\s+Round\s+(\d+)\s*$", re.MULTILINE)
_CLOSE_HEADER_RE = re.compile(r"^##\s+Close\s*$", re.MULTILINE)
_PHASE_HEADER_RE = re.compile(
    r"^###\s+(research|suggest|challenge|choose)\s*$",
    re.MULTILINE,
)
_MESSAGE_RE = re.compile(
    r"^-\s+\*\*(@[A-Za-z0-9_\-]+)\*\*\s+\(confidence:\s*(\d\.\d{2})\)\s+"
    r"—\s+(.+?)\s*$",
    re.MULTILINE,
)
_PLACEHOLDER_RE = re.compile(
    r"^-\s+\(no entries this round\)\s*$",
    re.MULTILINE,
)
_CLOSE_FIELD_RE = re.compile(
    r"^-\s+([a-z_]+):\s*(.+?)\s*$",
    re.MULTILINE,
)

# Minimalist YAML frontmatter reader for the narrow schema used here:
# committee_id, topic, chartered_at, members (list), quorum.
_FM_SCALAR_RE = re.compile(r"^([a-z_]+)\s*:\s*(.+?)\s*$", re.MULTILINE)
_FM_LIST_START_RE = re.compile(r"^([a-z_]+)\s*:\s*$", re.MULTILINE)
_FM_LIST_ITEM_RE = re.compile(r"^[ \t]+-[ \t]+(.+?)[ \t]*$", re.MULTILINE)

_PHASES = ("research", "suggest", "challenge", "choose")
_CLOSE_OUTCOMES = {"unanimous", "consensus", "split", "deferred"}


# --- errors -----------------------------------------------------------------

class TranscriptError(ValueError):
    """Raised when a transcript violates the format spec."""


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


# --- frontmatter ------------------------------------------------------------

def parse_frontmatter(text: str) -> dict:
    """Parse the transcript's YAML frontmatter (narrow schema)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise TranscriptError("missing or malformed YAML frontmatter")
    block = m.group(1)

    data: dict = {}
    # list-valued keys first (greedy); remove matched spans to avoid
    # re-matching them as scalars.
    consumed_spans: list[tuple[int, int]] = []
    for lm in _FM_LIST_START_RE.finditer(block):
        key = lm.group(1)
        start = lm.end()
        # Walk forward line-by-line collecting indented list items.
        lines = block[start:].splitlines(keepends=True)
        items: list[str] = []
        length = 0
        for line in lines:
            item_match = _FM_LIST_ITEM_RE.match(line)
            if item_match:
                items.append(_strip_quotes(item_match.group(1)))
                length += len(line)
            elif line.strip() == "":
                length += len(line)
                continue
            else:
                break
        if not items:
            continue
        data[key] = items
        consumed_spans.append((lm.start(), start + length))

    # Scalar keys — skip any that fall inside a consumed list span.
    def _in_consumed(pos: int) -> bool:
        return any(s <= pos < e for s, e in consumed_spans)

    for sm in _FM_SCALAR_RE.finditer(block):
        if _in_consumed(sm.start()):
            continue
        key = sm.group(1)
        val = _strip_quotes(sm.group(2))
        data.setdefault(key, val)

    for required in ("committee_id", "chartered_at", "members"):
        if required not in data:
            raise TranscriptError(
                f"frontmatter missing required key: {required}"
            )
    return data


# --- body -------------------------------------------------------------------

def _split_sections(body: str) -> list[tuple[str, str, int]]:
    """Split body into (section_type, content, round_num) tuples.

    Iterates over H2 headings (`## Round N` and `## Close`), returning each
    section's content (everything up to the next H2).
    """
    markers: list[tuple[str, int, int]] = []  # (kind, start_line_idx, round_num)
    for m in _ROUND_HEADER_RE.finditer(body):
        markers.append(("round", m.start(), int(m.group(1))))
    for m in _CLOSE_HEADER_RE.finditer(body):
        markers.append(("close", m.start(), 0))
    markers.sort(key=lambda t: t[1])

    sections: list[tuple[str, str, int]] = []
    for i, (kind, pos, rn) in enumerate(markers):
        end = markers[i + 1][1] if i + 1 < len(markers) else len(body)
        # Drop the heading line from content.
        nl = body.find("\n", pos)
        content = body[nl + 1:end] if nl != -1 else ""
        sections.append((kind, content, rn))
    return sections


def _split_phases(round_content: str) -> dict[str, str]:
    """Split a round section by H3 phase headings. Raises on missing phases."""
    found: dict[str, str] = {}
    markers = list(_PHASE_HEADER_RE.finditer(round_content))
    seen_names: list[str] = []
    for i, m in enumerate(markers):
        name = m.group(1)
        if name in found:
            raise TranscriptError(
                f"duplicate phase heading '{name}' in round section"
            )
        end = markers[i + 1].start() if i + 1 < len(markers) else len(round_content)
        nl = round_content.find("\n", m.start())
        content = round_content[nl + 1:end] if nl != -1 else ""
        found[name] = content
        seen_names.append(name)

    if seen_names != list(_PHASES):
        raise TranscriptError(
            f"phase ordering wrong; expected {list(_PHASES)}, got {seen_names}"
        )
    return found


def parse_messages(
    phase_content: str,
    *,
    members: list[str],
) -> list[dict]:
    """Parse message bullets in one phase block."""
    messages: list[dict] = []

    # Placeholder case: allowed only if no real message bullets exist.
    placeholder = _PLACEHOLDER_RE.search(phase_content)
    real_bullets = list(_MESSAGE_RE.finditer(phase_content))

    if placeholder and real_bullets:
        raise TranscriptError(
            "phase contains both '(no entries this round)' placeholder "
            "and real messages"
        )
    if placeholder:
        return []  # explicitly empty phase
    if not real_bullets:
        raise TranscriptError(
            "phase has neither message bullets nor '(no entries this round)' "
            "placeholder"
        )

    # Find rationale blockquotes by scanning lines between bullets.
    lines = phase_content.splitlines()
    # Build an offset index to the start character of each line.
    line_starts: list[int] = []
    off = 0
    for ln in lines:
        line_starts.append(off)
        off += len(ln) + 1  # plus \n

    def _line_index_of(char_pos: int) -> int:
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= char_pos:
                lo = mid
            else:
                hi = mid - 1
        return lo

    for idx, m in enumerate(real_bullets):
        author = m.group(1)
        confidence = float(m.group(2))
        position = m.group(3).rstrip(".")
        if author not in members:
            raise TranscriptError(
                f"message author {author} not listed in frontmatter members"
            )

        # Look at lines after this bullet, before the next bullet, for
        # contiguous blockquote lines (`> ...`) — they form the rationale.
        cur_line = _line_index_of(m.end())
        if idx + 1 < len(real_bullets):
            next_line = _line_index_of(real_bullets[idx + 1].start())
        else:
            next_line = len(lines)

        rationale_lines: list[str] = []
        started = False
        for j in range(cur_line + 1, next_line):
            s = lines[j].strip()
            if s.startswith(">"):
                started = True
                rationale_lines.append(s.lstrip(">").strip())
            elif started and s == "":
                break
            elif started and not s.startswith(">"):
                break
            else:
                # still a non-quote line before any quote — skip
                continue

        msg: dict = {
            "author": author,
            "confidence": confidence,
            "position": position,
        }
        if rationale_lines:
            msg["rationale"] = "\n".join(rationale_lines)
        messages.append(msg)

    return messages


def parse_close(close_content: str) -> dict:
    """Parse the `## Close` section — required key/value list."""
    fields: dict[str, str] = {}
    for m in _CLOSE_FIELD_RE.finditer(close_content):
        key = m.group(1)
        val = _strip_quotes(m.group(2))
        fields[key] = val

    for required in ("outcome", "final_confidence", "rounds_used", "decision"):
        if required not in fields:
            raise TranscriptError(
                f"Close section missing required field: {required}"
            )

    outcome = fields["outcome"].lower()
    if outcome not in _CLOSE_OUTCOMES:
        raise TranscriptError(
            f"outcome '{outcome}' not in {_CLOSE_OUTCOMES}"
        )

    try:
        final_conf = float(fields["final_confidence"])
    except ValueError as exc:
        raise TranscriptError(
            f"final_confidence not a float: {fields['final_confidence']}"
        ) from exc

    try:
        rounds_used = int(fields["rounds_used"])
    except ValueError as exc:
        raise TranscriptError(
            f"rounds_used not an int: {fields['rounds_used']}"
        ) from exc

    return {
        "outcome": outcome,
        "final_confidence": final_conf,
        "rounds_used": rounds_used,
        "decision": fields["decision"],
    }


# --- top-level parse --------------------------------------------------------

def parse_transcript(text: str) -> tuple[dict, list[dict]]:
    """Return (frontmatter, jsonl_rows)."""
    fm = parse_frontmatter(text)
    # body = everything after the closing `---` of frontmatter
    fm_match = _FRONTMATTER_RE.match(text)
    body = text[fm_match.end():] if fm_match else text

    sections = _split_sections(body)
    if not sections:
        raise TranscriptError("no `## Round` or `## Close` sections found")

    round_sections = [s for s in sections if s[0] == "round"]
    close_sections = [s for s in sections if s[0] == "close"]

    if not close_sections:
        raise TranscriptError("transcript lacks `## Close` section")
    if len(close_sections) > 1:
        raise TranscriptError(
            f"transcript has {len(close_sections)} `## Close` sections; "
            "exactly one required"
        )
    if not round_sections:
        raise TranscriptError("transcript has no `## Round N` sections")

    # Round numbers must start at 1 and increment by 1.
    expected = 1
    for _, _, rn in round_sections:
        if rn != expected:
            raise TranscriptError(
                f"round numbering broken; expected {expected}, got {rn}"
            )
        expected += 1

    rows: list[dict] = []
    members = fm["members"]
    committee_id = fm["committee_id"]
    chartered_at = fm["chartered_at"]

    for _, content, rn in round_sections:
        phases = _split_phases(content)
        for phase in _PHASES:
            for msg in parse_messages(phases[phase], members=members):
                row = {
                    "committee_id": committee_id,
                    "chartered_at": chartered_at,
                    "round": rn,
                    "phase": phase,
                    "author": msg["author"],
                    "confidence": msg["confidence"],
                    "position": msg["position"],
                }
                if "rationale" in msg:
                    row["rationale"] = msg["rationale"]
                rows.append(row)

    close_data = parse_close(close_sections[0][1])
    # Sanity: rounds_used must match actual round count.
    if close_data["rounds_used"] != len(round_sections):
        raise TranscriptError(
            f"rounds_used={close_data['rounds_used']} does not match "
            f"actual rounds={len(round_sections)}"
        )
    rows.append({
        "committee_id": committee_id,
        "chartered_at": chartered_at,
        "round": 0,
        "phase": "close",
        "author": None,
        "confidence": None,
        "position": close_data["decision"],
        "outcome": close_data["outcome"],
        "final_confidence": close_data["final_confidence"],
        "rounds_used": close_data["rounds_used"],
        "decision": close_data["decision"],
    })

    return fm, rows


def emit_jsonl(rows: list[dict]) -> str:
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"


# --- self-test fixtures -----------------------------------------------------

_FIXTURE_A = """---
committee_id: color-pick-2026-05-01
topic: "Pick a color token for the warning banner"
chartered_at: 2026-05-01T10:00:00Z
members:
  - "@frontend-lead"
  - "@design-ic"
  - "@a11y-reviewer"
quorum: 3
---

## Round 1

### research

- **@design-ic** (confidence: 0.92) — Amber #F59E0B meets AA contrast on both light/dark surfaces.
- **@a11y-reviewer** (confidence: 0.90) — Confirmed WCAG 2.1 AA at 4.7:1 ratio.

### suggest

- **@design-ic** (confidence: 0.92) — Adopt amber #F59E0B as tokens.warning.

### challenge

- (no entries this round)

### choose

- **@frontend-lead** (confidence: 0.91) — Adopt amber #F59E0B.
- **@design-ic** (confidence: 0.92) — Adopt amber #F59E0B.
- **@a11y-reviewer** (confidence: 0.90) — Adopt amber #F59E0B.

## Close

- outcome: unanimous
- final_confidence: 0.91
- rounds_used: 1
- decision: "Adopt amber #F59E0B as tokens.warning."
"""

_FIXTURE_B_MALFORMED = """---
committee_id: malformed-example
topic: "Missing close section"
chartered_at: 2026-05-01T10:00:00Z
members:
  - "@a"
  - "@b"
quorum: 2
---

## Round 1

### research
- **@a** (confidence: 0.80) — foo
### suggest
- **@a** (confidence: 0.80) — foo
### challenge
- (no entries this round)
### choose
- **@a** (confidence: 0.80) — foo
- **@b** (confidence: 0.80) — foo
"""


def _run_self_test() -> int:
    """Parse fixture A; expect 6 message rows + 1 close row = 7 JSONL rows.

    Also parse fixture B (missing Close); expect TranscriptError.
    """
    fm, rows = parse_transcript(_FIXTURE_A)
    if fm["committee_id"] != "color-pick-2026-05-01":
        print(
            f"[self-test] committee_id mismatch: {fm['committee_id']!r}",
            file=sys.stderr,
        )
        return 1
    # Fixture A: research(2) + suggest(1) + challenge(0-placeholder) +
    # choose(3) = 6 message rows, plus 1 close row.
    if len(rows) != 7:
        print(
            f"[self-test] expected 7 JSONL rows, got {len(rows)}",
            file=sys.stderr,
        )
        return 1
    if rows[-1]["phase"] != "close" or rows[-1]["outcome"] != "unanimous":
        print("[self-test] close row malformed", file=sys.stderr)
        return 1
    # Phase-coverage sanity: we should see research and choose entries.
    seen_phases = {r["phase"] for r in rows}
    for required in ("research", "suggest", "choose", "close"):
        if required not in seen_phases:
            print(
                f"[self-test] expected {required} phase in output",
                file=sys.stderr,
            )
            return 1

    try:
        parse_transcript(_FIXTURE_B_MALFORMED)
    except TranscriptError:
        pass
    else:
        print(
            "[self-test] malformed fixture parsed without error",
            file=sys.stderr,
        )
        return 1

    print(json.dumps({"status": "ok", "rows_emitted": 7, "fixtures": 2}))
    return 0


# --- CLI --------------------------------------------------------------------

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Parse committee transcript.md into rounds.jsonl (v5.19 Tier-B). "
            "See references/committee-rules.md § Transcript format."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    er = sub.add_parser(
        "extract-rounds",
        help="Parse a transcript into JSONL",
    )
    er.add_argument("--transcript", default=None)
    er.add_argument("--out", default=None)
    er.add_argument("--plugin-root", default=None)
    er.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in fixtures and exit (no --transcript needed)",
    )

    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    if args.cmd != "extract-rounds":
        print(
            json.dumps({"status": "error", "error": "unknown subcommand"}),
            file=sys.stderr,
        )
        return 2

    if args.self_test:
        try:
            return _run_self_test()
        except Exception as exc:  # pragma: no cover — defensive
            print(
                json.dumps({"status": "error", "error": repr(exc)}),
                file=sys.stderr,
            )
            return 3

    if not args.transcript:
        print(
            json.dumps({
                "status": "error",
                "error": "--transcript is required (or pass --self-test)",
            }),
            file=sys.stderr,
        )
        return 2

    transcript_path = Path(args.transcript).resolve()
    if not transcript_path.is_file():
        print(
            json.dumps({
                "status": "error",
                "error": f"transcript not found or not a file: {transcript_path}",
            }),
            file=sys.stderr,
        )
        return 2

    try:
        text = transcript_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            json.dumps({"status": "error", "error": repr(exc)}),
            file=sys.stderr,
        )
        return 2

    try:
        fm, rows = parse_transcript(text)
    except TranscriptError as exc:
        print(
            json.dumps({
                "status": "malformed",
                "error": str(exc),
                "transcript": str(transcript_path),
            }),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # pragma: no cover — defensive
        print(
            json.dumps({"status": "error", "error": repr(exc)}),
            file=sys.stderr,
        )
        return 3

    out_path = (
        Path(args.out).resolve()
        if args.out
        else transcript_path.parent / "rounds.jsonl"
    )
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(emit_jsonl(rows), encoding="utf-8")
    except OSError as exc:
        print(
            json.dumps({"status": "error", "error": repr(exc)}),
            file=sys.stderr,
        )
        return 3

    print(json.dumps({
        "status": "ok",
        "committee_id": fm["committee_id"],
        "rows": len(rows),
        "out": str(out_path),
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
