#!/usr/bin/env python3
"""
critic_score.py — skill-critic deterministic rubric (v5.19.4, Phase 2 step 5).

Scores a SKILL.md draft on 8 axes with documented weights. Emits a JSON report
with per-axis score, rationale, and overall weighted score. Never mutates the
target file — critic is read-only.

Intended caller: `bin/skill_factory.py` Step 5 during Phase 2 wiring. Callable
standalone for ad-hoc quality checks.

Grounding:
    * skills/_meta/skill-critic/SKILL.md (contract)
    * skills/_meta/skill-critic/references/rubric.md (axis definitions)
    * references/skill-authoring-standards.md (normative rules this rubric enforces)
    * references/capability-taxonomy.md (closed 8-verb set for axis 7)
    * references/topic-vocabulary.md (closed 18-tag set for axis 8)

Usage:
    critic_score.py --skill-path <path-to-SKILL.md>
        [--plugin-root <path>]         # for vocab/tax lookups; default cwd
        [--threshold 0.80]             # pass threshold; default 0.80

Exit codes (v5.15.2 convention):
    0 — scored successfully (pass OR fail, both exit 0; reader checks `pass`)
    1 — scored with hard failure (malformed SKILL.md: no frontmatter / no H1)
    2 — usage error (missing args, unreadable paths)
    3 — internal error (unexpected exception)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

# Plugin root inferred from script location (skills/_meta/skill-critic/scripts/critic_score.py).
# This is purely a default; --plugin-root flag overrides for the rubric vocab,
# and --critic-jsonl-path flag overrides the JSONL append target.
_DEFAULT_PLUGIN_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_CRITIC_JSONL = _DEFAULT_PLUGIN_ROOT / "_meta-runtime" / "critic-verdicts.jsonl"


# --- vocabulary loaders -----------------------------------------------------

_CAPABILITY_RE = re.compile(r"^###\s+`([a-z-]+)`\s*$", re.MULTILINE)
_TAG_RE = re.compile(r"^###\s+`([a-z-]+)`\s*$", re.MULTILINE)


def load_capability_verbs(plugin_root: Path) -> set[str]:
    """Parse the closed 8-verb set from capability-taxonomy.md. Returns {} on
    failure so the axis degrades to "skipped" instead of crashing the critic."""
    path = plugin_root / "references" / "capability-taxonomy.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(_CAPABILITY_RE.findall(text))


def load_topic_tags(plugin_root: Path) -> set[str]:
    """Parse the controlled tag set from topic-vocabulary.md. Same graceful
    degradation as load_capability_verbs."""
    path = plugin_root / "references" / "topic-vocabulary.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(_TAG_RE.findall(text))


# --- frontmatter extraction -------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_NAME_RE = re.compile(r"^name\s*:\s*(.+?)\s*$", re.MULTILINE)
_DESC_RE = re.compile(r"^description\s*:\s*(.+?)\s*$", re.MULTILINE)
_KIHO_BLOCK_RE = re.compile(
    r"^\s*kiho\s*:\s*\n((?:[ \t]+.+\n)+)", re.MULTILINE
)
_KIHO_FIELD_RE = re.compile(r"^\s*([a-z_]+)\s*:\s*(.+?)\s*$", re.MULTILINE)
_INLINE_LIST_RE = re.compile(r"\[(.*?)\]")
_VERSION_RE = re.compile(r"^version\s*:\s*(.+?)\s*$", re.MULTILINE)


def extract_frontmatter(text: str) -> dict:
    """Return a best-effort parse of the YAML frontmatter. Keys: name,
    description, version, kiho (dict with capability, topic_tags, data_classes).
    Missing keys are absent from the dict."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    fm: dict = {}

    name_m = _NAME_RE.search(block)
    if name_m:
        fm["name"] = name_m.group(1).strip().strip('"\'')

    desc_m = _DESC_RE.search(block)
    if desc_m:
        fm["description"] = desc_m.group(1).strip().strip('"\'')

    ver_m = _VERSION_RE.search(block)
    if ver_m:
        fm["version"] = ver_m.group(1).strip().strip('"\'')

    kiho_m = _KIHO_BLOCK_RE.search(block + "\n")
    if kiho_m:
        kiho_body = kiho_m.group(1)
        kiho_dict: dict = {}
        for field_m in _KIHO_FIELD_RE.finditer(kiho_body):
            key, raw_val = field_m.group(1), field_m.group(2)
            list_m = _INLINE_LIST_RE.match(raw_val)
            if list_m:
                items = [
                    s.strip().strip('"\'')
                    for s in list_m.group(1).split(",")
                    if s.strip()
                ]
                kiho_dict[key] = items
            else:
                kiho_dict[key] = raw_val.strip().strip('"\'')
        fm["kiho"] = kiho_dict

    fm["_frontmatter_end"] = m.end()
    return fm


# --- axis scorers -----------------------------------------------------------

_TRIGGER_PHRASE_HINTS = (
    "use this skill",
    "triggers on",
    "invoke",
    "when the user",
    "when to use",
    "when a",
    "when ",
    "for ",
)
_H1_RE = re.compile(r"^#\s+.+$", re.MULTILINE)
_H2_RE = re.compile(r"^##\s+.+$", re.MULTILINE)
_ANTIPATTERN_RE = re.compile(
    r"^##+\s+(anti[- ]?patterns?|do not|avoid|never)\b",
    re.MULTILINE | re.IGNORECASE,
)
_CODE_FENCE_RE = re.compile(r"^```", re.MULTILINE)
_EXAMPLE_HEADING_RE = re.compile(r"^##+\s+.*example", re.MULTILINE | re.IGNORECASE)


def score_description_quality(fm: dict) -> dict:
    """Axis 1 — description length, third-person tone, trigger phrase count.
    Weight 0.20."""
    desc = fm.get("description", "")
    length = len(desc)
    length_ok = 50 <= length <= 1024
    starts_useful = desc.lower().startswith("use this skill") or (
        not desc.startswith(("I ", "You ", "We "))
    )
    # Count distinct trigger hints present
    hint_hits = sum(1 for h in _TRIGGER_PHRASE_HINTS if h in desc.lower())
    # Sub-scores
    length_score = 1.0 if length_ok else (0.5 if length else 0.0)
    tone_score = 1.0 if starts_useful else 0.3
    trigger_score = min(1.0, hint_hits / 3.0)  # 3 hints → full credit
    score = (length_score + tone_score + trigger_score) / 3.0
    return {
        "score": round(score, 2),
        "weight": 0.20,
        "detail": (
            f"length={length} (ok={length_ok}); tone_ok={starts_useful}; "
            f"trigger_hints={hint_hits}/3"
        ),
    }


def score_body_length(body: str) -> dict:
    """Axis 2 — body under 500 lines per standards. Weight 0.05."""
    lines = body.count("\n") + 1
    if lines < 400:
        s = 1.0
    elif lines < 500:
        s = 0.8  # yellow
    else:
        s = 0.0  # red
    return {
        "score": round(s, 2),
        "weight": 0.05,
        "detail": f"lines={lines} (threshold 500)",
    }


def score_structure(body: str) -> dict:
    """Axis 3 — frontmatter parsed + H1 + ≥1 H2. Weight 0.15."""
    has_h1 = bool(_H1_RE.search(body))
    h2_count = len(_H2_RE.findall(body))
    s = 0.0
    if has_h1:
        s += 0.5
    if h2_count >= 1:
        s += 0.3
    if h2_count >= 3:
        s += 0.2
    return {
        "score": round(min(s, 1.0), 2),
        "weight": 0.15,
        "detail": f"h1={has_h1}; h2_count={h2_count}",
    }


def score_examples(body: str) -> dict:
    """Axis 4 — at least one code fence OR 'Example' heading. Weight 0.15."""
    fence_count = len(_CODE_FENCE_RE.findall(body)) // 2  # pairs
    example_heading = bool(_EXAMPLE_HEADING_RE.search(body))
    if fence_count >= 1 and example_heading:
        s = 1.0
    elif fence_count >= 1 or example_heading:
        s = 0.7
    else:
        s = 0.0
    return {
        "score": round(s, 2),
        "weight": 0.15,
        "detail": f"code_fence_pairs={fence_count}; example_heading={example_heading}",
    }


def score_anti_patterns(body: str) -> dict:
    """Axis 5 — body has explicit Anti-patterns / Do-not section. Weight 0.15."""
    m = _ANTIPATTERN_RE.search(body)
    return {
        "score": 1.0 if m else 0.0,
        "weight": 0.15,
        "detail": f"anti_patterns_heading={'present' if m else 'missing'}",
    }


def score_frontmatter_completeness(fm: dict) -> dict:
    """Axis 6 — required name+description + recommended kiho block. Weight 0.15."""
    has_name = bool(fm.get("name"))
    has_desc = bool(fm.get("description"))
    kiho = fm.get("kiho", {}) or {}
    has_capability = bool(kiho.get("capability"))
    has_tags = bool(kiho.get("topic_tags"))
    has_data_classes = "data_classes" in kiho  # empty list acceptable here; axis just checks declaration
    s = 0.0
    if has_name:
        s += 0.3
    if has_desc:
        s += 0.3
    if has_capability:
        s += 0.15
    if has_tags:
        s += 0.15
    if has_data_classes:
        s += 0.1
    return {
        "score": round(min(s, 1.0), 2),
        "weight": 0.15,
        "detail": (
            f"name={has_name}; description={has_desc}; "
            f"capability={has_capability}; topic_tags={has_tags}; "
            f"data_classes={has_data_classes}"
        ),
    }


def score_capability_valid(fm: dict, verbs: set[str]) -> dict:
    """Axis 7 — declared capability must be in closed 8-verb set. Weight 0.05."""
    kiho = fm.get("kiho", {}) or {}
    cap = kiho.get("capability")
    if not verbs:  # vocab file unreadable; skip gracefully
        return {
            "score": 1.0,
            "weight": 0.05,
            "detail": "capability-taxonomy.md unreadable; axis skipped",
        }
    if not cap:
        return {
            "score": 0.0,
            "weight": 0.05,
            "detail": "no capability declared",
        }
    ok = cap in verbs
    return {
        "score": 1.0 if ok else 0.0,
        "weight": 0.05,
        "detail": f"capability={cap!r}; valid={ok}",
    }


def score_topic_tags_valid(fm: dict, tags: set[str]) -> dict:
    """Axis 8 — all declared topic_tags in controlled vocabulary. Weight 0.10."""
    kiho = fm.get("kiho", {}) or {}
    declared = kiho.get("topic_tags") or []
    if not tags:
        return {
            "score": 1.0,
            "weight": 0.10,
            "detail": "topic-vocabulary.md unreadable; axis skipped",
        }
    if not declared:
        return {
            "score": 0.0,
            "weight": 0.10,
            "detail": "no topic_tags declared",
        }
    invalid = [t for t in declared if t not in tags]
    ratio = (len(declared) - len(invalid)) / len(declared)
    return {
        "score": round(ratio, 2),
        "weight": 0.10,
        "detail": f"declared={declared}; invalid={invalid}",
    }


# --- orchestration ----------------------------------------------------------

def score_skill(skill_path: Path, plugin_root: Path, threshold: float) -> dict:
    text = skill_path.read_text(encoding="utf-8")
    fm = extract_frontmatter(text)
    if not fm:
        return {
            "status": "malformed",
            "skill_path": str(skill_path),
            "error": "no frontmatter detected",
        }

    body = text[fm.get("_frontmatter_end", 0):]
    verbs = load_capability_verbs(plugin_root)
    tags = load_topic_tags(plugin_root)

    axes = {
        "description_quality": score_description_quality(fm),
        "body_length": score_body_length(body),
        "structure": score_structure(body),
        "examples": score_examples(body),
        "anti_patterns": score_anti_patterns(body),
        "frontmatter_completeness": score_frontmatter_completeness(fm),
        "capability_valid": score_capability_valid(fm, verbs),
        "topic_tags_valid": score_topic_tags_valid(fm, tags),
    }

    total_weight = sum(a["weight"] for a in axes.values())
    weighted = sum(a["score"] * a["weight"] for a in axes.values())
    overall = round(weighted / total_weight, 3) if total_weight else 0.0

    # Structural hard-fail flags: no H1 OR body under 20 lines
    has_h1 = axes["structure"]["score"] >= 0.5
    body_nonempty = body.count("\n") >= 20
    hard_fail = not (has_h1 and body_nonempty)

    return {
        "status": "hard_fail" if hard_fail else "ok",
        "skill_path": str(skill_path),
        "overall_score": overall,
        "threshold": threshold,
        "pass": overall >= threshold and not hard_fail,
        "axes": axes,
        "warnings": [
            f"{name}: {axis['detail']}"
            for name, axis in axes.items()
            if axis["score"] < 0.7
        ],
    }


def append_critic_verdict_jsonl(
    report: dict,
    skill_path: Path,
    jsonl_path: Path,
    invocation_source: str,
) -> None:
    """Append one row to _meta-runtime/critic-verdicts.jsonl (per data-storage-matrix
    row `skill-critic-verdicts`). Suppresses any IO error to keep the score path
    side-effect-free for the caller — the JSONL stream is best-effort telemetry."""
    try:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skill_id": skill_path.parent.name,
            "skill_path": str(skill_path).replace("\\", "/"),
            "overall_score": report.get("overall_score"),
            "threshold": report.get("threshold"),
            "pass": report.get("pass"),
            "hard_fail": report.get("status") == "hard_fail",
            "axes": {
                name: {
                    "score": axis.get("score"),
                    "weight": axis.get("weight"),
                    "detail": axis.get("detail"),
                }
                for name, axis in (report.get("axes") or {}).items()
            },
            "warnings": report.get("warnings") or [],
            "invocation_source": invocation_source,
        }
        with jsonl_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Deterministic rubric scorer for SKILL.md drafts.",
        epilog=(
            "Exit codes: 0 scored (check `pass` in JSON), 1 malformed input, "
            "2 usage, 3 internal."
        ),
    )
    p.add_argument(
        "--skill-path",
        required=True,
        help="Path to a SKILL.md file (not a directory).",
    )
    p.add_argument(
        "--plugin-root",
        default=".",
        help="Plugin root for vocabulary lookups. Default: cwd.",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.80,
        help="Overall-score threshold for pass=true. Default: 0.80.",
    )
    p.add_argument(
        "--critic-jsonl-path",
        default=str(_DEFAULT_CRITIC_JSONL),
        help=(
            "Path to append the critic-verdict row (data-storage-matrix row "
            "`skill-critic-verdicts`). Default: <plugin-root>/_meta-runtime/critic-verdicts.jsonl. "
            "Set to empty string to disable JSONL append (for ad-hoc dry runs)."
        ),
    )
    p.add_argument(
        "--invocation-source",
        default="manual",
        help=(
            "Tag for the invocation source recorded in the JSONL row "
            "(factory-step5 | manual | evolve-trigger). Default: manual."
        ),
    )

    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    skill_path = Path(args.skill_path)
    if not skill_path.is_file():
        print(
            json.dumps(
                {"status": "error", "error": f"{args.skill_path!r} not a file"}
            ),
            file=sys.stderr,
        )
        return 2

    try:
        report = score_skill(
            skill_path, Path(args.plugin_root).resolve(), args.threshold
        )
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr)
        return 3

    if args.critic_jsonl_path:
        append_critic_verdict_jsonl(
            report, skill_path, Path(args.critic_jsonl_path),
            invocation_source=args.invocation_source,
        )

    print(json.dumps(report, indent=2))
    if report.get("status") == "hard_fail":
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
