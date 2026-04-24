#!/usr/bin/env python3
"""Compute deterministic per-agent cycle-outcome scores (v5.23+).

Decision: perf-review-360-2026-04-23. Replaces a naive 360 peer-review
extension with a telemetry-derived quantitative score. Reads existing JSONL
streams; writes `agent-score-<period>.jsonl` (T2 regenerable).

Formula:
    score = 0.40 × invocation_outcome_rate
          + 0.30 × cycle_phase_owner_success_rate
          + 0.20 × committee_winning_position_rate
          + 0.10 × kb_contribution_weight

Component bounds are [0.0, 1.0]; aggregate is in [0.0, 1.0]. Any agent
scoring < 0.70 is flagged in the JSONL as `below_promotion_threshold: true`
so `agent-promote` committees can filter quickly.

Inputs (all optional; missing sources contribute 0.0 to the dependent
component):
  - <project>/.kiho/state/skill-invocations.jsonl
      shape: {ts, agent, skill, outcome: "success" | "error" | "abort"}
  - <project>/.kiho/state/cycles/<id>/handoffs.jsonl
      shape: {ts, from_phase, to_phase, owner_agent, contributors, status}
  - <project>/.kiho/committees/<id>/transcript.md (full sweep)
      parsed for winning position per member in close block
  - <project>/.kiho/state/ceo-ledger.jsonl (kb_add entries)

Invocation:
    python bin/agent_cycle_score.py --project <path> --period 2026-Q2
        (default path: cwd; default period: current-quarter)

Emits: <project>/.kiho/state/agent-score-<period>.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

WEIGHT_INVOCATION = 0.40
WEIGHT_PHASE_OWNER = 0.30
WEIGHT_COMMITTEE_WIN = 0.20
WEIGHT_KB = 0.10
PROMOTION_THRESHOLD = 0.70

# Auditor personas are EXCLUDED from committee_winning_position_rate —
# challenging well-supported positions is their job and MUST NOT lower their
# score. Flagged in decision.md as implementation concern.
AUDITOR_AGENT_PATTERNS = (
    re.compile(r"auditor", re.IGNORECASE),
    re.compile(r"skeptic", re.IGNORECASE),
)


@dataclass
class Breakdown:
    invocation_rate: float
    phase_owner_rate: float
    committee_win_rate: float
    kb_weight: float

    def aggregate(self) -> float:
        return (
            WEIGHT_INVOCATION * self.invocation_rate
            + WEIGHT_PHASE_OWNER * self.phase_owner_rate
            + WEIGHT_COMMITTEE_WIN * self.committee_win_rate
            + WEIGHT_KB * self.kb_weight
        )


def _parse_iso(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _iter_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _quarter_bounds(q: str) -> tuple[datetime, datetime]:
    m = re.match(r"^(\d{4})-Q([1-4])$", q)
    if not m:
        raise ValueError(f"bad period: {q!r} (expected YYYY-Q[1-4])")
    year, qi = int(m.group(1)), int(m.group(2))
    start_month = (qi - 1) * 3 + 1
    start = datetime(year, start_month, 1, tzinfo=timezone.utc)
    if qi == 4:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, start_month + 3, 1, tzinfo=timezone.utc)
    return start, end


def _in_window(dt: datetime | None, start: datetime, end: datetime) -> bool:
    return dt is not None and start <= dt < end


def _is_auditor(agent: str) -> bool:
    return any(p.search(agent) for p in AUDITOR_AGENT_PATTERNS)


def compute_invocation_rate(
    project_root: Path, start: datetime, end: datetime
) -> dict[str, float]:
    entries = _iter_jsonl(project_root / ".kiho" / "state" / "skill-invocations.jsonl")
    totals: dict[str, int] = {}
    successes: dict[str, int] = {}
    for e in entries:
        ts = _parse_iso(e.get("ts", ""))
        if not _in_window(ts, start, end):
            continue
        agent = str(e.get("agent", "")) or "unknown"
        outcome = str(e.get("outcome", "")).lower()
        totals[agent] = totals.get(agent, 0) + 1
        if outcome in {"success", "ok", "passed", "granted"}:
            successes[agent] = successes.get(agent, 0) + 1
    return {a: (successes.get(a, 0) / totals[a]) for a in totals}


def compute_phase_owner_rate(
    project_root: Path, start: datetime, end: datetime
) -> dict[str, float]:
    """Owner weight 1.0; contributor weight 0.5. Success = handoff status 'success' or closed cycle."""
    cycles_dir = project_root / ".kiho" / "state" / "cycles"
    per_agent_weight: dict[str, float] = {}
    per_agent_success: dict[str, float] = {}
    if not cycles_dir.exists():
        return {}
    for cycle_dir in sorted(cycles_dir.iterdir()):
        if not cycle_dir.is_dir():
            continue
        handoffs = _iter_jsonl(cycle_dir / "handoffs.jsonl")
        for h in handoffs:
            ts = _parse_iso(h.get("ts", ""))
            if not _in_window(ts, start, end):
                continue
            status = str(h.get("status", "")).lower()
            is_success = status in {"success", "closed", "granted", "ok"}
            owner = str(h.get("owner_agent", h.get("owner", "")))
            if owner:
                per_agent_weight[owner] = per_agent_weight.get(owner, 0.0) + 1.0
                if is_success:
                    per_agent_success[owner] = per_agent_success.get(owner, 0.0) + 1.0
            contributors = h.get("contributors") or []
            if isinstance(contributors, str):
                contributors = [contributors]
            for c in contributors:
                if not c or c == owner:
                    continue
                per_agent_weight[c] = per_agent_weight.get(c, 0.0) + 0.5
                if is_success:
                    per_agent_success[c] = per_agent_success.get(c, 0.0) + 0.5
    return {
        a: (per_agent_success.get(a, 0.0) / per_agent_weight[a])
        for a in per_agent_weight
    }


def compute_committee_win_rate(
    project_root: Path, start: datetime, end: datetime
) -> dict[str, float]:
    committees_dir = project_root / ".kiho" / "committees"
    if not committees_dir.exists():
        return {}
    per_agent_total: dict[str, int] = {}
    per_agent_wins: dict[str, int] = {}
    for transcript in sorted(committees_dir.glob("*/transcript.md")):
        try:
            text = transcript.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Best-effort period gate: look for chartered_at in YAML frontmatter
        m_chartered = re.search(
            r"chartered_at:\s*(\S+)", text[: min(len(text), 500)]
        )
        if m_chartered:
            dt = _parse_iso(m_chartered.group(1).strip('"\''))
            if dt and not _in_window(dt, start, end):
                continue
        # Parse members list
        m_members = re.search(
            r"members:\s*\n((?:\s+-\s+.+\n)+)",
            text[: min(len(text), 1000)],
        )
        members: list[str] = []
        if m_members:
            for line in m_members.group(1).splitlines():
                m = re.match(r"\s+-\s+\"?@?([^\"\s]+)\"?", line)
                if m:
                    members.append(m.group(1))
        # Parse Close outcome
        close = re.search(r"##\s+Close\s*\n(.+?)(?:\n##|\Z)", text, re.DOTALL)
        if not close:
            continue
        block = close.group(1)
        m_outcome = re.search(r"^-\s*outcome:\s*(\S+)", block, re.MULTILINE)
        if not m_outcome:
            continue
        outcome = m_outcome.group(1).lower()
        # "unanimous" means every non-auditor member won; "consensus" means most;
        # "split" means hard to attribute — skip. "deferred" means escalated.
        for agent in members:
            if _is_auditor(agent):
                continue  # auditors are excluded from this metric
            per_agent_total[agent] = per_agent_total.get(agent, 0) + 1
            if outcome == "unanimous":
                per_agent_wins[agent] = per_agent_wins.get(agent, 0) + 1
    return {
        a: (per_agent_wins.get(a, 0) / per_agent_total[a])
        for a in per_agent_total
    }


def compute_kb_weight(
    project_root: Path, start: datetime, end: datetime
) -> dict[str, float]:
    """Per-agent KB contribution normalized to [0, 1] by the max contributor."""
    ledger = _iter_jsonl(project_root / ".kiho" / "state" / "ceo-ledger.jsonl")
    per_agent: dict[str, int] = {}
    for e in ledger:
        ts = _parse_iso(e.get("ts", ""))
        if not _in_window(ts, start, end):
            continue
        if e.get("action") not in {"kb_add", "kb_update"}:
            continue
        payload = e.get("payload") or {}
        emitter = str(payload.get("caused_by") or payload.get("emitter") or "")
        if not emitter:
            continue
        entries = payload.get("entries") or payload.get("slugs") or [payload.get("slug")]
        if isinstance(entries, str):
            entries = [entries]
        per_agent[emitter] = per_agent.get(emitter, 0) + len([s for s in entries if s])
    if not per_agent:
        return {}
    top = max(per_agent.values())
    return {a: (v / top) for a, v in per_agent.items()}


def compute_all(project_root: Path, period: str) -> dict[str, Breakdown]:
    start, end = _quarter_bounds(period)
    inv = compute_invocation_rate(project_root, start, end)
    phase = compute_phase_owner_rate(project_root, start, end)
    comm = compute_committee_win_rate(project_root, start, end)
    kb = compute_kb_weight(project_root, start, end)
    agents = sorted(set(inv) | set(phase) | set(comm) | set(kb))
    return {
        a: Breakdown(
            invocation_rate=inv.get(a, 0.0),
            phase_owner_rate=phase.get(a, 0.0),
            committee_win_rate=comm.get(a, 0.0),
            kb_weight=kb.get(a, 0.0),
        )
        for a in agents
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="kiho v5.23 per-agent cycle-outcome score")
    p.add_argument("--project", type=Path, default=Path.cwd(), help="project root")
    p.add_argument(
        "--period",
        required=True,
        help="YYYY-Q[1-4] — e.g., 2026-Q2",
    )
    p.add_argument("--out", type=Path, default=None, help="output path")
    p.add_argument("--json", action="store_true", help="emit JSON rollup on stdout too")
    args = p.parse_args(argv)

    scores = compute_all(args.project, args.period)
    generated_at = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()

    out_path = args.out
    if out_path is None:
        out_path = (
            args.project / ".kiho" / "state" / f"agent-score-{args.period}.jsonl"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    stdout_rows: list[dict] = []
    for agent in sorted(scores):
        b = scores[agent]
        score = b.aggregate()
        row = {
            "period": args.period,
            "agent": agent,
            "score": round(score, 4),
            "breakdown": {
                "invocation_rate": round(b.invocation_rate, 4),
                "phase_owner_rate": round(b.phase_owner_rate, 4),
                "committee_win_rate": round(b.committee_win_rate, 4),
                "kb_weight": round(b.kb_weight, 4),
            },
            "below_promotion_threshold": score < PROMOTION_THRESHOLD,
            "generated_at": generated_at,
        }
        lines.append(json.dumps(row, sort_keys=True))
        stdout_rows.append(row)
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    if args.json:
        print(json.dumps(stdout_rows, indent=2))
    else:
        print(f"wrote {out_path} ({len(scores)} agent(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
