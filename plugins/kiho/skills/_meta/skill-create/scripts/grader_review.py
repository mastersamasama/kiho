#!/usr/bin/env python3
"""
grader_review.py — Gate 13 grader review sampler (v5.14).

Given a draft skill's benchmark.json (with per-assertion pass records) and
the transcripts that produced them, this script picks a deterministic 10%
sample of graded transcripts per assertion and emits a review worksheet
for kiho-kb-manager (or a designated human auditor) to confirm the grader
verdicts are themselves correct.

The premise (from Anthropic's Jan 2026 "Demystifying Evals for AI Agents"):
"you won't know if your graders are working well unless you read the
transcripts and grades from many trials." This script makes that review
tractable by surfacing only the 10% that will actually be spot-checked.

Grounding: Anthropic Jan 9 2026 Demystifying Evals post; v5.14 H1.

Usage:
    grader_review.py --benchmark <path> --transcripts-dir <path>
                    [--sample-rate 0.10] [--out worksheet.md]

Exit codes:
    0 — worksheet written
    2 — usage or input error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_SAMPLE_RATE = 0.10      # 10% per-assertion sample
MIN_SAMPLE_SIZE = 1             # at least 1 row per assertion even at 10%
MAX_SAMPLE_SIZE = 5             # cap per-assertion sample at 5 rows


def deterministic_sample(items: list[Any], rate: float, seed: str) -> list[Any]:
    """Pick a deterministic sample using a seeded hash.

    Same (items, rate, seed) always produces the same sample. This is important
    for reviewers — they need to see the same rows twice if they re-run the tool.
    """
    n = len(items)
    target = max(MIN_SAMPLE_SIZE, min(MAX_SAMPLE_SIZE, int(round(n * rate))))
    if n <= target:
        return list(items)
    ranked = sorted(
        enumerate(items),
        key=lambda pair: hashlib.sha256(
            f"{seed}:{pair[0]}".encode()
        ).hexdigest(),
    )
    return [pair[1] for pair in ranked[:target]]


def load_benchmark(path: Path) -> dict[str, Any]:
    if not path.exists():
        sys.stderr.write(f"benchmark not found: {path}\n")
        sys.exit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def group_by_assertion(benchmark: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Walk the benchmark and produce {assertion_id: [grading-row, ...]}."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for scen in benchmark.get("scenarios") or []:
        scen_id = scen.get("id") or scen.get("scenario_id") or "?"
        for a in scen.get("assertions") or []:
            aid = str(a.get("id") or a.get("assertion_id") or "?")
            groups.setdefault(aid, []).append({
                "scenario_id": scen_id,
                "passed": bool(a.get("passed")),
                "verdict": a.get("verdict") or ("pass" if a.get("passed") else "fail"),
                "grader_reasoning": a.get("grader_reasoning") or a.get("reasoning") or "",
                "transcript_ref": a.get("transcript_ref") or f"{scen_id}.transcript",
            })
    return groups


def find_transcript(
    transcripts_dir: Path,
    scen_id: str,
    assertion_id: str,
) -> Path | None:
    """Heuristic locator for a transcript file tied to a (scenario, assertion) pair."""
    candidates = [
        transcripts_dir / f"{scen_id}.md",
        transcripts_dir / f"{scen_id}.transcript.md",
        transcripts_dir / f"{scen_id}.json",
        transcripts_dir / scen_id / f"{assertion_id}.md",
        transcripts_dir / scen_id / "transcript.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Last resort: glob
    for p in transcripts_dir.rglob(f"*{scen_id}*"):
        if p.is_file():
            return p
    return None


def snippet(path: Path, max_chars: int = 400) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"(read failed: {exc})"
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def build_worksheet(
    benchmark: dict[str, Any],
    transcripts_dir: Path,
    rate: float,
    seed: str,
) -> str:
    groups = group_by_assertion(benchmark)
    total_assertions = len(groups)
    total_rows = sum(len(v) for v in groups.values())

    lines: list[str] = []
    lines.append("# Grader review worksheet")
    lines.append("")
    lines.append(f"- Benchmark assertions: **{total_assertions}**")
    lines.append(f"- Total grading rows: **{total_rows}**")
    lines.append(f"- Sample rate: **{rate:.0%}**")
    lines.append(f"- Min rows per assertion: {MIN_SAMPLE_SIZE}")
    lines.append(f"- Max rows per assertion: {MAX_SAMPLE_SIZE}")
    lines.append("")
    lines.append(
        "For each assertion below, read the sampled rows and answer: **"
        "does the grader verdict match what the transcript shows?** If you "
        "disagree, flag it in the `reviewer_verdict` column. Any disagreement "
        "on >10% of reviewed rows routes the skill back to Step 9 eval "
        "generation with the disagreeing assertions attached."
    )
    lines.append("")

    for aid, rows in sorted(groups.items()):
        sample = deterministic_sample(rows, rate, f"{seed}:{aid}")
        lines.append(f"## Assertion `{aid}` ({len(sample)}/{len(rows)} sampled)")
        lines.append("")
        for i, row in enumerate(sample, 1):
            lines.append(f"### Row {i}")
            lines.append(f"- Scenario: `{row['scenario_id']}`")
            lines.append(f"- Grader verdict: `{row['verdict']}`")
            reasoning = row.get("grader_reasoning", "").strip() or "(none given)"
            lines.append(f"- Grader reasoning: {reasoning}")
            t_path = find_transcript(
                transcripts_dir, row["scenario_id"], aid,
            )
            if t_path:
                lines.append(f"- Transcript: `{t_path}`")
                lines.append("")
                lines.append("```")
                lines.append(snippet(t_path))
                lines.append("```")
            else:
                lines.append("- Transcript: **NOT FOUND**")
            lines.append("")
            lines.append("- Reviewer verdict: [ ] agree  [ ] disagree  [ ] abstain")
            lines.append("- Reviewer notes: _________________")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "After completing this worksheet, count the disagreements. If >10% of "
        "reviewed rows show `disagree`, the grader is unreliable for that "
        "assertion and the skill must route back to Step 9 with the disagreeing "
        "assertions. Record the disagreement rate in the skill audit block as "
        "`grader_review_disagreement_rate`."
    )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--benchmark", required=True, help="benchmark.json path")
    p.add_argument("--transcripts-dir", required=True,
                   help="directory holding per-scenario transcripts")
    p.add_argument("--sample-rate", type=float, default=DEFAULT_SAMPLE_RATE)
    p.add_argument("--seed", default="kiho-grader-review",
                   help="deterministic seed for sampling")
    p.add_argument("--out", default="-", help="output path or '-' for stdout")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    benchmark = load_benchmark(Path(args.benchmark))
    transcripts_dir = Path(args.transcripts_dir).resolve()
    if not transcripts_dir.exists():
        sys.stderr.write(f"transcripts dir not found: {transcripts_dir}\n")
        return 2
    worksheet = build_worksheet(
        benchmark, transcripts_dir, args.sample_rate, args.seed,
    )
    if args.out == "-":
        sys.stdout.write(worksheet)
    else:
        Path(args.out).write_text(worksheet, encoding="utf-8")
        sys.stderr.write(f"wrote {args.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
