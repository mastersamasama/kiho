#!/usr/bin/env python3
"""
kiho_telemetry_rollup.py — roll up skill + cycle telemetry into health stats.

Reads two telemetry streams:
  1. Per-invocation skill telemetry (project-tier skill-invocations.jsonl)
  2. Per-advance cycle telemetry (plugin-tier _meta-runtime/cycle-events.jsonl)

Writes two rolling-stats JSONLs the CEO consumes at INITIALIZE:
  - skill-health.jsonl  (one row per skill_id; needs_evolve flagging)
  - cycle-health.jsonl  (one row per cycle_id + one per template_id;
                         needs_attention flagging)

Skill-health row schema:

    {
      "ts": "<iso>", "skill_id": "<sk-XXX>",
      "total_invocations": <int>, "recent_window": <int>,
      "recent_invocations": <int>, "recent_success_rate": <float 0..1>,
      "recent_failure_count": <int>, "needs_evolve": <bool>,
      "last_invocation_ts": "<iso>"
    }

Cycle-health row schema (kind=cycle):

    {
      "ts": "<iso>", "kind": "cycle", "cycle_id": "...",
      "template_id": "...", "template_version": "...",
      "opens_count": <int>, "advances_count": <int>,
      "current_phase": "...", "current_status": "in_progress|blocked|closed-success|closed-failure|cancelled|paused",
      "iters_used": <int>, "iters_max": <int>,
      "blocker_reason": <str|null>,
      "first_seen_ts": "<iso>", "last_seen_ts": "<iso>",
      "total_duration_ms": <int>
    }

Cycle-health row schema (kind=template):

    {
      "ts": "<iso>", "kind": "template", "template_id": "...",
      "cycles_total": <int>, "cycles_in_progress": <int>,
      "cycles_blocked": <int>, "cycles_closed_success": <int>,
      "cycles_closed_failure": <int>, "cycles_cancelled": <int>,
      "avg_iters_per_cycle": <float>,
      "avg_duration_ms_per_advance": <float>,
      "needs_attention": <bool>
    }

The CEO uses `needs_evolve` (skills) and `needs_attention` (templates) to
populate the next turn's agenda automatically — no manual prompt needed.

Usage:
    kiho_telemetry_rollup.py
        [--invocations-jsonl <project>/.kiho/state/skill-invocations.jsonl]
        [--cycles-jsonl _meta-runtime/cycle-events.jsonl]
        [--out _meta-runtime/skill-health.jsonl]
        [--cycles-out _meta-runtime/cycle-health.jsonl]
        [--threshold 0.70] [--window 20] [--min-invocations 5]

Either --invocations-jsonl or --cycles-jsonl (or both) MUST be supplied.
A missing file is treated as empty (rollup writes zero rows for that stream).

Exit codes (v5.15.2 convention):
    0 — wrote rollups (always 0 unless internal error)
    2 — usage error (no input source)
    3 — internal error
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from collections import defaultdict
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PLUGIN_ROOT / "_meta-runtime" / "skill-health.jsonl"
DEFAULT_CYCLES_JSONL = PLUGIN_ROOT / "_meta-runtime" / "cycle-events.jsonl"
DEFAULT_CYCLES_OUT = PLUGIN_ROOT / "_meta-runtime" / "cycle-health.jsonl"

TERMINAL_STATUSES = frozenset({
    "closed-success", "closed-failure", "blocked", "cancelled", "paused",
})


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


def rollup(rows: list[dict], window: int, threshold: float, min_invocations: int) -> list[dict]:
    """Group by skill_id, compute recent success rate, flag needs_evolve.

    `success` field in each row is treated as truthy boolean. `ts` is preserved
    as-is (rows assumed to be in append/chronological order).
    """
    by_skill: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        sid = r.get("skill_id")
        if not sid:
            continue
        by_skill[sid].append(r)

    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: list[dict] = []
    for sid, items in sorted(by_skill.items()):
        recent = items[-window:]
        successes = sum(1 for r in recent if r.get("success") is True)
        rate = successes / len(recent) if recent else 0.0
        failure_count = len(recent) - successes
        needs_evolve = (
            len(recent) >= min_invocations
            and rate < threshold
        )
        out.append({
            "ts": now,
            "skill_id": sid,
            "total_invocations": len(items),
            "recent_window": window,
            "recent_invocations": len(recent),
            "recent_success_rate": round(rate, 3),
            "recent_failure_count": failure_count,
            "needs_evolve": needs_evolve,
            "last_invocation_ts": (recent[-1].get("ts") if recent else None),
        })
    return out


def cycle_rollup(
    rows: list[dict],
    blocked_threshold: float = 0.10,
    success_threshold: float = 0.50,
    min_cycles_for_template_flag: int = 3,
) -> tuple[list[dict], list[dict]]:
    """Roll up cycle-events.jsonl into per-cycle and per-template stats.

    Returns (cycle_rows, template_rows). Each cycle_id collapses to one row;
    each template_id collapses to one row. Templates are flagged
    `needs_attention=true` when blocked-rate exceeds blocked_threshold OR
    when success-rate (over closed cycles) falls below success_threshold,
    provided the template has ≥min_cycles_for_template_flag cycles to score.
    """
    by_cycle: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        cid = r.get("cycle_id")
        if not cid:
            continue
        by_cycle[cid].append(r)

    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cycle_rows: list[dict] = []
    by_template: dict[str, list[dict]] = defaultdict(list)

    for cid, items in sorted(by_cycle.items()):
        items_sorted = sorted(items, key=lambda r: r.get("ts", ""))
        first = items_sorted[0]
        last = items_sorted[-1]
        opens_count = sum(1 for r in items_sorted if r.get("op") == "open")
        advances_count = sum(1 for r in items_sorted if r.get("op") == "advance")
        current_phase = last.get("phase_after") or last.get("phase_before") or "unknown"
        if current_phase in TERMINAL_STATUSES:
            current_status = current_phase
        elif last.get("blocker_reason"):
            current_status = "blocked"
        else:
            current_status = "in_progress"
        budget = last.get("budget") or {}
        total_duration_ms = sum(int(r.get("duration_ms") or 0) for r in items_sorted)
        cycle_row = {
            "ts": now,
            "kind": "cycle",
            "cycle_id": cid,
            "template_id": first.get("template_id"),
            "template_version": first.get("template_version"),
            "opens_count": opens_count,
            "advances_count": advances_count,
            "current_phase": current_phase,
            "current_status": current_status,
            "iters_used": int(budget.get("iters_used") or 0),
            "iters_max": int(budget.get("iters_max") or 0),
            "blocker_reason": last.get("blocker_reason"),
            "first_seen_ts": first.get("ts"),
            "last_seen_ts": last.get("ts"),
            "total_duration_ms": total_duration_ms,
        }
        cycle_rows.append(cycle_row)
        tid = first.get("template_id")
        if tid:
            by_template[tid].append(cycle_row)

    template_rows: list[dict] = []
    for tid, cycles in sorted(by_template.items()):
        total = len(cycles)
        in_progress = sum(1 for c in cycles if c["current_status"] == "in_progress")
        blocked = sum(1 for c in cycles if c["current_status"] == "blocked")
        closed_success = sum(1 for c in cycles if c["current_status"] == "closed-success")
        closed_failure = sum(1 for c in cycles if c["current_status"] == "closed-failure")
        cancelled = sum(1 for c in cycles if c["current_status"] == "cancelled")
        closed = closed_success + closed_failure
        avg_iters = (
            sum(c["iters_used"] for c in cycles) / total if total else 0.0
        )
        total_advances = sum(c["advances_count"] for c in cycles)
        total_dur = sum(c["total_duration_ms"] for c in cycles)
        avg_dur = (total_dur / total_advances) if total_advances else 0.0
        blocked_rate = blocked / total if total else 0.0
        success_rate = (closed_success / closed) if closed else None
        needs_attention = False
        if total >= min_cycles_for_template_flag:
            if blocked_rate > blocked_threshold:
                needs_attention = True
            if success_rate is not None and success_rate < success_threshold:
                needs_attention = True
        template_rows.append({
            "ts": now,
            "kind": "template",
            "template_id": tid,
            "cycles_total": total,
            "cycles_in_progress": in_progress,
            "cycles_blocked": blocked,
            "cycles_closed_success": closed_success,
            "cycles_closed_failure": closed_failure,
            "cycles_cancelled": cancelled,
            "avg_iters_per_cycle": round(avg_iters, 2),
            "avg_duration_ms_per_advance": round(avg_dur, 2),
            "needs_attention": needs_attention,
        })
    return cycle_rows, template_rows


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Roll up skill + cycle telemetry into health stats.",
    )
    p.add_argument(
        "--invocations-jsonl",
        default=None,
        help="Path to skill-invocations.jsonl (project-tier). Optional in v5.21.",
    )
    p.add_argument(
        "--cycles-jsonl",
        default=None,
        help=(
            f"Path to cycle-events.jsonl (default: {DEFAULT_CYCLES_JSONL} "
            "if file exists). v5.21+."
        ),
    )
    p.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help=f"Skill-health output path (default: {DEFAULT_OUT}).",
    )
    p.add_argument(
        "--cycles-out",
        default=str(DEFAULT_CYCLES_OUT),
        help=f"Cycle-health output path (default: {DEFAULT_CYCLES_OUT}).",
    )
    p.add_argument("--threshold", type=float, default=0.70,
                   help="Skill success rate below which a skill is flagged for evolve.")
    p.add_argument("--window", type=int, default=20,
                   help="Most-recent invocations per skill considered.")
    p.add_argument("--min-invocations", type=int, default=5,
                   help="Min invocations before a skill can be flagged.")

    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    cycles_path = Path(args.cycles_jsonl) if args.cycles_jsonl else DEFAULT_CYCLES_JSONL
    invocations_path = Path(args.invocations_jsonl) if args.invocations_jsonl else None

    if invocations_path is None and not cycles_path.is_file():
        print(json.dumps({
            "status": "error",
            "error": (
                "no input source: pass --invocations-jsonl and/or "
                "--cycles-jsonl, or place cycle-events.jsonl at "
                f"{DEFAULT_CYCLES_JSONL}"
            ),
        }), file=sys.stderr)
        return 2

    try:
        report: dict = {"status": "ok", "params": {
            "threshold": args.threshold,
            "window": args.window,
            "min_invocations": args.min_invocations,
        }}

        if invocations_path is not None:
            rows = read_jsonl(invocations_path)
            rollup_rows = rollup(
                rows, args.window, args.threshold, args.min_invocations,
            )
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("w", encoding="utf-8") as fp:
                for r in rollup_rows:
                    fp.write(json.dumps(r, ensure_ascii=False) + "\n")
            flagged = [r for r in rollup_rows if r["needs_evolve"]]
            report["skills"] = {
                "source": str(invocations_path),
                "out": str(out_path),
                "skills_total": len(rollup_rows),
                "skills_flagged_for_evolve": len(flagged),
                "flagged_skill_ids": [r["skill_id"] for r in flagged],
            }

        if cycles_path.is_file():
            cycle_events = read_jsonl(cycles_path)
            cycle_rows, template_rows = cycle_rollup(cycle_events)
            cycles_out_path = Path(args.cycles_out)
            cycles_out_path.parent.mkdir(parents=True, exist_ok=True)
            with cycles_out_path.open("w", encoding="utf-8") as fp:
                for r in cycle_rows + template_rows:
                    fp.write(json.dumps(r, ensure_ascii=False) + "\n")
            flagged_t = [r for r in template_rows if r["needs_attention"]]
            blocked_c = [r for r in cycle_rows if r["current_status"] == "blocked"]
            report["cycles"] = {
                "source": str(cycles_path),
                "out": str(cycles_out_path),
                "cycles_total": len(cycle_rows),
                "templates_total": len(template_rows),
                "templates_flagged_attention": len(flagged_t),
                "flagged_template_ids": [r["template_id"] for r in flagged_t],
                "blocked_cycle_ids": [r["cycle_id"] for r in blocked_c],
            }

        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
