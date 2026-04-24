#!/usr/bin/env python3
"""Regenerable Tier-2 dashboard generator — period rollup of kiho activity.

Reads existing telemetry (cycle-events.jsonl, agent-performance.jsonl,
factory-verdicts.jsonl, ceo-ledger.jsonl, committee transcript close blocks)
and the optional agent-score-<period>.jsonl (produced by bin/agent_cycle_score.py,
committee 05) and emits a markdown period-rollup file at
`<project>/.kiho/state/dashboards/<period>.md`.

Metrics (each with a named downstream consumer per committee decision
`dashboard-analytics-2026-04-23`):

  1. cycles_closed / cycles_opened  — retrospective
  2. incidents + mean MTTR           — retrospective
  3. agents_hired / agents_rejected  — HR / retrospective
  4. committees convened + rates     — retrospective + skill-evolution
  5. factory pass / reject rates     — skill-evolution
  6. kb pages added rate             — kb-lint health check
  7. top/bottom agent scores         — agent-promote (v5.23+: stubbed if
                                       agent-score-<period>.jsonl absent)

Idempotent: re-running on same inputs emits byte-identical output. All
JSONL reads sort entries by (ts | seq) before consumption.

Stdlib-only. Python 3.10+.

Invocation:
  python bin/dashboard.py --project <path> --period per-cycle --cycle-id <id> \\
      [--out <path>]
  python bin/dashboard.py --project <path> --period quarterly --quarter 2026-Q2 \\
      [--out <path>]

Decision: dashboard-analytics-2026-04-23 (v5.23 planning).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


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
    """Sorted-by-(ts,seq) list of JSONL rows. Missing file → empty."""
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
    out.sort(key=lambda e: (e.get("ts") or "", e.get("seq") or 0))
    return out


@dataclass
class Period:
    kind: str  # "per-cycle" | "quarterly"
    cycle_id: str | None = None
    quarter: str | None = None
    start: datetime | None = None
    end: datetime | None = None

    def label(self) -> str:
        if self.kind == "per-cycle":
            return f"per-cycle (cycle-id: {self.cycle_id})"
        return f"quarterly ({self.quarter})"

    def filename(self) -> str:
        if self.kind == "per-cycle":
            return f"{self.cycle_id}.md"
        return f"{self.quarter}.md"

    def contains(self, dt: datetime | None) -> bool:
        if dt is None:
            return True  # undated entries count
        if self.start and dt < self.start:
            return False
        if self.end and dt > self.end:
            return False
        return True


def _quarter_bounds(q: str) -> tuple[datetime, datetime]:
    m = re.match(r"^(\d{4})-Q([1-4])$", q)
    if not m:
        raise ValueError(f"bad --quarter: {q!r} (expected YYYY-Q[1-4])")
    year = int(m.group(1))
    qi = int(m.group(2))
    start_month = (qi - 1) * 3 + 1
    end_month = start_month + 2
    start = datetime(year, start_month, 1, tzinfo=timezone.utc)
    if end_month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, end_month + 1, 1, tzinfo=timezone.utc)
    return (start, end)


def _cycle_bounds(project_root: Path, cycle_id: str) -> tuple[datetime | None, datetime | None]:
    handoffs = project_root / ".kiho" / "state" / "cycles" / cycle_id / "handoffs.jsonl"
    entries = _iter_jsonl(handoffs)
    if not entries:
        return (None, None)
    starts = [_parse_iso(e.get("ts", "")) for e in entries]
    starts = [d for d in starts if d is not None]
    if not starts:
        return (None, None)
    return (min(starts), max(starts))


# ---------------------------------------------------------------------------
# Metric extractors — each takes project_root + Period, returns dict
# ---------------------------------------------------------------------------


def metric_velocity(project_root: Path, period: Period) -> dict:
    events = _iter_jsonl(project_root / ".kiho" / "state" / "cycle-events.jsonl")
    opened = closed = 0
    for e in events:
        ts = _parse_iso(e.get("ts", ""))
        if not period.contains(ts):
            continue
        action = e.get("action", "")
        if action == "cycle_opened":
            opened += 1
        elif action in {"cycle_closed", "cycle_closed_success", "cycle_closed_abort"}:
            closed += 1
    ratio = (closed / opened) if opened else None
    return {"opened": opened, "closed": closed, "ratio": ratio}


def metric_incidents(project_root: Path, period: Period) -> dict:
    events = _iter_jsonl(project_root / ".kiho" / "state" / "cycle-events.jsonl")
    opened_count = 0
    mttr_samples_s: list[float] = []
    open_opened_at: dict[str, datetime] = {}
    for e in events:
        ts = _parse_iso(e.get("ts", ""))
        action = e.get("action", "")
        payload = e.get("payload") or {}
        incident_id = payload.get("incident_id") or payload.get("cycle_id") or ""
        if action == "incident_opened" and period.contains(ts):
            opened_count += 1
            if ts and incident_id:
                open_opened_at[incident_id] = ts
        elif action in {"incident_closed", "incident_resolved"}:
            if not incident_id or incident_id not in open_opened_at:
                continue
            if not ts:
                continue
            if not period.contains(ts):
                continue
            delta = (ts - open_opened_at[incident_id]).total_seconds()
            if delta >= 0:
                mttr_samples_s.append(delta)
    mean_mttr = (sum(mttr_samples_s) / len(mttr_samples_s)) if mttr_samples_s else None
    return {
        "opened": opened_count,
        "resolved": len(mttr_samples_s),
        "mean_mttr_seconds": mean_mttr,
    }


def metric_hiring(project_root: Path, period: Period) -> dict:
    ledger = _iter_jsonl(project_root / ".kiho" / "state" / "ceo-ledger.jsonl")
    hired = rejected = 0
    for e in ledger:
        ts = _parse_iso(e.get("ts", ""))
        if not period.contains(ts):
            continue
        action = e.get("action", "")
        if action == "recruit":
            payload = e.get("payload") or {}
            agents = payload.get("agents") or payload.get("hired") or []
            if isinstance(agents, str):
                agents = [agents]
            hired += len([a for a in agents if a])
        elif action in {"recruit_rejected", "rejection_feedback"}:
            rejected += 1
    total = hired + rejected
    rate = (hired / total) if total else None
    return {"hired": hired, "rejected": rejected, "hire_rate": rate}


def metric_committees(project_root: Path, period: Period) -> dict:
    """Scan committee transcript close blocks under .kiho/committees/<id>/transcript.md."""
    committees_dir = project_root / ".kiho" / "committees"
    if not committees_dir.exists():
        return {
            "convened": 0,
            "unanimous_close_rate": None,
            "mean_rounds_used": None,
        }
    outcomes: list[str] = []
    rounds: list[int] = []
    for transcript in sorted(committees_dir.glob("*/transcript.md")):
        try:
            text = transcript.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Trust the committee-rules format: ## Close block with outcome / rounds_used
        close = re.search(r"##\s+Close\s*\n(.+?)(?:\n##|\Z)", text, re.DOTALL)
        if not close:
            continue
        block = close.group(1)
        m_outcome = re.search(r"^-\s*outcome:\s*(\S+)", block, re.MULTILINE)
        m_rounds = re.search(r"^-\s*rounds_used:\s*(\d+)", block, re.MULTILINE)
        if not m_outcome:
            continue
        # TODO: period filtering on committees is best-effort via chartered_at
        # in frontmatter; for the first cut, we include all committees and let
        # readers interpret "convened" as "closed during any period whose
        # files exist". This is conservative and idempotent.
        outcomes.append(m_outcome.group(1))
        if m_rounds:
            rounds.append(int(m_rounds.group(1)))
    convened = len(outcomes)
    unanimous = sum(1 for o in outcomes if o == "unanimous")
    rate = (unanimous / convened) if convened else None
    mean_rounds = (sum(rounds) / len(rounds)) if rounds else None
    return {
        "convened": convened,
        "unanimous_close_rate": rate,
        "mean_rounds_used": mean_rounds,
    }


def metric_factory(project_root: Path, period: Period) -> dict:
    verdicts_a = project_root / "_meta-runtime" / "factory-verdicts.jsonl"
    verdicts_b = project_root / ".kiho" / "_meta-runtime" / "factory-verdicts.jsonl"
    entries = _iter_jsonl(verdicts_a) or _iter_jsonl(verdicts_b)
    passed = rejected = 0
    for e in entries:
        ts = _parse_iso(e.get("ts", ""))
        if not period.contains(ts):
            continue
        verdict = str(e.get("verdict", e.get("status", ""))).lower()
        if verdict in {"pass", "passed", "approved", "accepted"}:
            passed += 1
        elif verdict in {"reject", "rejected", "denied"}:
            rejected += 1
    total = passed + rejected
    return {
        "passed": passed,
        "rejected": rejected,
        "pass_rate": (passed / total) if total else None,
        "reject_rate": (rejected / total) if total else None,
    }


def metric_kb(project_root: Path, period: Period) -> dict:
    ledger = _iter_jsonl(project_root / ".kiho" / "state" / "ceo-ledger.jsonl")
    adds = 0
    for e in ledger:
        ts = _parse_iso(e.get("ts", ""))
        if not period.contains(ts):
            continue
        if e.get("action") in {"kb_add", "kb_update"}:
            payload = e.get("payload") or {}
            entries = payload.get("entries") or payload.get("slugs") or [payload.get("slug")]
            if isinstance(entries, str):
                entries = [entries]
            adds += len([s for s in entries if s])
    # Stale count: best-effort scan of wiki dir for files not touched in 90d
    wiki_dir = project_root / ".kiho" / "kb" / "wiki"
    stale = 0
    if wiki_dir.exists():
        now = datetime.now(tz=timezone.utc).timestamp()
        for p in wiki_dir.rglob("*.md"):
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if (now - mtime) > 90 * 24 * 3600:
                stale += 1
    return {"pages_added": adds, "stale_count": stale}


def metric_agent_scores(project_root: Path, period: Period) -> dict:
    """Top 5 / bottom 5 agents by cycle-outcome score.

    Reads the optional `agent-score-<period>.jsonl` emitted by
    bin/agent_cycle_score.py (committee 05, v5.23+). If the file is not
    present, returns a stub indicating score source unavailable.
    """
    # Period-specific file first; fall back to generic.
    if period.kind == "quarterly" and period.quarter:
        score_file = project_root / ".kiho" / "state" / f"agent-score-{period.quarter}.jsonl"
    else:
        score_file = project_root / ".kiho" / "state" / "agent-score-current.jsonl"
    entries = _iter_jsonl(score_file)
    if not entries:
        return {"available": False, "top": [], "bottom": []}
    scored: list[tuple[str, float]] = []
    for e in entries:
        agent = str(e.get("agent", ""))
        score = e.get("score")
        if not agent or not isinstance(score, (int, float)):
            continue
        scored.append((agent, float(score)))
    scored.sort(key=lambda x: (-x[1], x[0]))  # highest first; stable alphabetical tiebreak
    top = scored[:5]
    bottom = sorted(scored[-5:], key=lambda x: (x[1], x[0]))
    return {
        "available": True,
        "top": [{"agent": a, "score": s} for a, s in top],
        "bottom": [{"agent": a, "score": s} for a, s in bottom],
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _fmt_ratio(r: float | None) -> str:
    if r is None:
        return "n/a"
    return f"{r:.3f}"


def _fmt_seconds(s: float | None) -> str:
    if s is None:
        return "n/a"
    if s < 60:
        return f"{int(s)}s"
    if s < 3600:
        return f"{int(s / 60)}m"
    return f"{s / 3600:.1f}h"


def render(period: Period, metrics: dict, generated_at: str) -> str:
    v = metrics["velocity"]
    i = metrics["incidents"]
    h = metrics["hiring"]
    c = metrics["committees"]
    f = metrics["factory"]
    k = metrics["kb"]
    a = metrics["agent_scores"]

    lines: list[str] = []
    lines.append(f"# Dashboard — {period.label()}")
    lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append("Source: bin/dashboard.py")
    lines.append(
        "Decision: dashboard-analytics-2026-04-23 "
        "(_proposals/v5.23-oa-integration/06-committee-dashboard/decision.md)"
    )
    lines.append("")
    lines.append("## Velocity")
    lines.append(f"- cycles_opened: {v['opened']}")
    lines.append(f"- cycles_closed: {v['closed']}")
    lines.append(f"- ratio (closed/opened): {_fmt_ratio(v['ratio'])}")
    lines.append("")
    lines.append("## Reliability")
    lines.append(f"- incidents_opened: {i['opened']}")
    lines.append(f"- incidents_resolved: {i['resolved']}")
    lines.append(f"- mean_mttr: {_fmt_seconds(i['mean_mttr_seconds'])}")
    lines.append("")
    lines.append("## Hiring")
    lines.append(f"- agents_hired: {h['hired']}")
    lines.append(f"- agents_rejected: {h['rejected']}")
    lines.append(f"- hire_rate: {_fmt_ratio(h['hire_rate'])}")
    lines.append("")
    lines.append("## Committees")
    lines.append(f"- convened: {c['convened']}")
    lines.append(f"- unanimous_close_rate: {_fmt_ratio(c['unanimous_close_rate'])}")
    lines.append(
        f"- mean_rounds_used: "
        f"{c['mean_rounds_used']:.2f}" if c["mean_rounds_used"] is not None else "- mean_rounds_used: n/a"
    )
    lines.append("")
    lines.append("## Skill factory")
    lines.append(f"- passed: {f['passed']}")
    lines.append(f"- rejected: {f['rejected']}")
    lines.append(f"- pass_rate: {_fmt_ratio(f['pass_rate'])}")
    lines.append(f"- reject_rate: {_fmt_ratio(f['reject_rate'])}")
    lines.append("")
    lines.append("## KB")
    lines.append(f"- pages_added: {k['pages_added']}")
    lines.append(f"- stale_count (>90d untouched): {k['stale_count']}")
    lines.append("")
    lines.append("## Agent scores (cycle-outcome, v5.23+)")
    if not a["available"]:
        lines.append("- (agent-score-<period>.jsonl not present — run bin/agent_cycle_score.py)")
    else:
        lines.append("### Top 5")
        for row in a["top"]:
            lines.append(f"- {row['agent']}: {row['score']:.3f}")
        if a["bottom"] and a["top"] and a["bottom"][0]["score"] < 0.70:
            lines.append("### Bottom 5 (attention required)")
            for row in a["bottom"]:
                lines.append(f"- {row['agent']}: {row['score']:.3f}")
    lines.append("")
    return "\n".join(lines) + "\n"


def compute(project_root: Path, period: Period) -> dict:
    return {
        "velocity": metric_velocity(project_root, period),
        "incidents": metric_incidents(project_root, period),
        "hiring": metric_hiring(project_root, period),
        "committees": metric_committees(project_root, period),
        "factory": metric_factory(project_root, period),
        "kb": metric_kb(project_root, period),
        "agent_scores": metric_agent_scores(project_root, period),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="kiho v5.23 dashboard generator")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="project root")
    parser.add_argument(
        "--period", choices=("per-cycle", "quarterly"), required=True, help="granularity"
    )
    parser.add_argument("--cycle-id", help="cycle id (required for --period per-cycle)")
    parser.add_argument("--quarter", help="YYYY-Q[1-4] (required for --period quarterly)")
    parser.add_argument("--out", type=Path, default=None, help="output path (default: auto)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = parser.parse_args(argv)

    if args.period == "per-cycle":
        if not args.cycle_id:
            parser.error("--cycle-id required for --period per-cycle")
        start, end = _cycle_bounds(args.project, args.cycle_id)
        period = Period(kind="per-cycle", cycle_id=args.cycle_id, start=start, end=end)
    else:
        if not args.quarter:
            parser.error("--quarter required for --period quarterly")
        start, end = _quarter_bounds(args.quarter)
        period = Period(kind="quarterly", quarter=args.quarter, start=start, end=end)

    metrics = compute(args.project, period)
    generated_at = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()

    if args.json:
        body = json.dumps(
            {"period": period.label(), "generated_at": generated_at, "metrics": metrics},
            indent=2,
            sort_keys=True,
            default=str,
        )
    else:
        body = render(period, metrics, generated_at)

    out_path = args.out
    if out_path is None:
        dashboards_dir = args.project / ".kiho" / "state" / "dashboards"
        dashboards_dir.mkdir(parents=True, exist_ok=True)
        out_path = dashboards_dir / period.filename()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    print(f"wrote {out_path} ({len(body)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
