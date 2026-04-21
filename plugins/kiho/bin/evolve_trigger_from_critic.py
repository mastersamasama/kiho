#!/usr/bin/env python3
"""
evolve_trigger_from_critic.py — derive an evolve agenda from critic telemetry.

Reads `_meta-runtime/critic-verdicts.jsonl` (data-storage-matrix row
`skill-critic-verdicts`), groups by `skill_id`, and emits an evolve agenda for
skills whose recent average critic score falls below the threshold OR whose
score has trended downward over the last N runs.

This script is the kiho-blessed alternative to building skill-optimize/skill-verify
(Phase 2 wave 2 was deliberately not built — see skills/_meta/skill-factory/SKILL.md).
The CEO can take the agenda and trigger `skill-improve` per row, preserving the
existing FIX semantics rather than introducing a new step in the SOP.

Usage:
    evolve_trigger_from_critic.py
        [--jsonl _meta-runtime/critic-verdicts.jsonl]
        [--threshold 0.80]      # below this average → agenda candidate
        [--window 5]            # last N runs per skill considered
        [--min-runs 2]          # skill must have this many runs to be evaluated
        [--lens score-floor|trend|both]  # default: both
        [--out -]               # output path; '-' for stdout (default)

Exit codes (v5.15.2 convention):
    0 — agenda produced (may be empty list)
    1 — agenda contains entries (CEO action recommended)
    2 — usage error
    3 — internal error
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSONL = PLUGIN_ROOT / "_meta-runtime" / "critic-verdicts.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def group_recent_by_skill(rows: list[dict], window: int) -> dict[str, list[dict]]:
    """Return {skill_id: [last N rows in chronological order]}."""
    by_skill: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        sid = r.get("skill_id")
        if not sid:
            continue
        by_skill[sid].append(r)
    # Keep last N per skill (rows are already in append order)
    return {sid: lst[-window:] for sid, lst in by_skill.items()}


def _numeric_scores(runs: list[dict]) -> list[float]:
    """Extract overall_score values that are present and numeric."""
    out: list[float] = []
    for r in runs:
        s = r.get("overall_score")
        if isinstance(s, (int, float)):
            out.append(float(s))
    return out


def detect_score_floor(runs: list[dict], threshold: float) -> tuple[bool, float]:
    """Return (below_floor, avg_score)."""
    scores = _numeric_scores(runs)
    if not scores:
        return False, 0.0
    avg = sum(scores) / len(scores)
    return avg < threshold, avg


def detect_downward_trend(runs: list[dict]) -> tuple[bool, float]:
    """Heuristic: trending if last score is at least 0.05 lower than first AND
    not flat. Returns (is_trending_down, slope_proxy)."""
    scores = _numeric_scores(runs)
    if len(scores) < 3:
        return False, 0.0
    delta = scores[-1] - scores[0]
    return delta <= -0.05, delta


def find_axis_blindspots(runs: list[dict]) -> list[str]:
    """Return axis names that scored < 0.7 in ≥ half of the recent runs.

    These are critic-axis blindspots: persistent low scores on the same dimension
    suggest the skill needs work in that direction.
    """
    if not runs:
        return []
    axis_low_count: dict[str, int] = defaultdict(int)
    for r in runs:
        for name, axis in (r.get("axes") or {}).items():
            if (axis.get("score") or 0) < 0.7:
                axis_low_count[name] += 1
    threshold = max(1, len(runs) // 2)
    return sorted([n for n, c in axis_low_count.items() if c >= threshold])


def build_agenda(
    rows: list[dict], window: int, threshold: float, min_runs: int, lens: str
) -> list[dict]:
    grouped = group_recent_by_skill(rows, window)
    agenda: list[dict] = []
    for sid, runs in sorted(grouped.items()):
        if len(runs) < min_runs:
            continue
        below_floor, avg_score = detect_score_floor(runs, threshold)
        trending, delta = detect_downward_trend(runs)

        triggered_by: list[str] = []
        if lens in ("score-floor", "both") and below_floor:
            triggered_by.append("score-floor")
        if lens in ("trend", "both") and trending:
            triggered_by.append("downward-trend")

        if not triggered_by:
            continue

        agenda.append({
            "skill_id": sid,
            "skill_path": runs[-1].get("skill_path"),
            "trigger_lens": triggered_by,
            "recent_runs": len(runs),
            "avg_score": round(avg_score, 3),
            "score_delta": round(delta, 3),
            "axis_blindspots": find_axis_blindspots(runs),
            "last_run_ts": runs[-1].get("ts"),
            "recommended_op": "skill-improve",
            "next_action": (
                f"Invoke skill-improve with failure_evidence='avg critic score "
                f"{avg_score:.2f} over last {len(runs)} runs (threshold {threshold:.2f}); "
                f"axis blindspots: {find_axis_blindspots(runs) or 'none'}'"
            ),
        })
    return agenda


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Derive evolve agenda from critic-verdicts.jsonl telemetry.",
    )
    p.add_argument("--jsonl", default=str(DEFAULT_JSONL),
                   help="Path to critic-verdicts.jsonl")
    p.add_argument("--threshold", type=float, default=0.80,
                   help="Average score below which a skill enters the agenda")
    p.add_argument("--window", type=int, default=5,
                   help="Number of most-recent runs per skill considered")
    p.add_argument("--min-runs", type=int, default=2,
                   help="Minimum runs per skill to include in evaluation")
    p.add_argument("--lens", default="both",
                   choices=["score-floor", "trend", "both"],
                   help="Which trigger lens to apply")
    p.add_argument("--out", default="-",
                   help="Output path; '-' for stdout (default)")

    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    try:
        rows = read_jsonl(Path(args.jsonl))
        agenda = build_agenda(
            rows,
            window=args.window,
            threshold=args.threshold,
            min_runs=args.min_runs,
            lens=args.lens,
        )
        payload = {
            "status": "ok",
            "jsonl_source": args.jsonl,
            "params": {
                "threshold": args.threshold,
                "window": args.window,
                "min_runs": args.min_runs,
                "lens": args.lens,
            },
            "skills_evaluated": len(set(r.get("skill_id") for r in rows if r.get("skill_id"))),
            "agenda_size": len(agenda),
            "agenda": agenda,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out == "-":
            sys.stdout.write(text + "\n")
        else:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
        return 1 if agenda else 0
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
