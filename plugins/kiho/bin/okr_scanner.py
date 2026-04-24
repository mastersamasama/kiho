#!/usr/bin/env python3
"""OKR auto-sweep scanner (v6.2+).

Read-only inspector that produces a deterministic action list for the CEO's
INITIALIZE step 17.5 (`okr-auto-sweep`). Does NOT mutate state — just reports
what the auto-flow should do next.

Invoked from the `okr-auto-sweep` skill (Bash call) with a project root. Emits
one JSON object on stdout with `actions: list`, each action a record with
enough payload for the CEO / OKR-master to dispatch.

Action kinds emitted:
  - propose-company      : no active company O for current period + nudge window open
  - cascade-dept         : active company O has no aligned dept O for some dept
  - cascade-individual   : active dept O has qualifying agents without individual Os
  - stale-memo           : active O with no checkin > stale_days
  - period-close         : today > period.end for period with any active O
  - cascade-close        : parent O closed; aligned children still active

Decision: v6.2 OKR auto-flow (reverses committee-01 no-auto-cadence rule
per user direct override 2026-04-24). See
`_proposals/v6.2-okr-auto-flow/` (authored at v6.2.0 release).

Stdlib-only. Python 3.10+ (falls back to `tomli` on 3.10 per kiho convention).

Usage:
    python bin/okr_scanner.py --project <path> [--today YYYY-MM-DD] [--json]

Exit codes:
  0 — scan complete (even with zero actions)
  2 — usage error
  3 — project root invalid / inaccessible
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import tomllib as _toml  # type: ignore
except ModuleNotFoundError:
    try:
        import tomli as _toml  # type: ignore
    except ModuleNotFoundError:
        _toml = None  # type: ignore


# Config defaults (mirror plugins/kiho/templates/config.default.toml [okr] section)
DEFAULT_CFG = {
    "auto_trigger_enabled": True,
    "nudge_days_before_start": 7,
    "stale_days": 30,
    "cascade_rule": "deferred",  # "deferred" | "archive"
    "auto_checkin_from_cycle": True,
    "onboard_threshold_iter": 30,
    "individual_max_per_dept": 5,
    "nudge_cooldown_days_after_dismiss": 7,
}


@dataclass
class Action:
    kind: str
    payload: dict
    reason: str = ""


@dataclass
class OKR:
    path: Path
    frontmatter: dict
    body: str

    @property
    def o_id(self) -> str:
        return str(self.frontmatter.get("o_id", self.path.stem))

    @property
    def level(self) -> str:
        return str(self.frontmatter.get("okr_level", "unknown"))

    @property
    def status(self) -> str:
        return str(self.frontmatter.get("status", "unknown"))

    @property
    def period(self) -> str:
        return str(self.frontmatter.get("period", ""))

    @property
    def owner(self) -> str:
        return str(self.frontmatter.get("owner", ""))

    @property
    def aligns_to(self) -> str | None:
        val = self.frontmatter.get("aligns_to")
        if val in (None, "null", ""):
            return None
        return str(val)

    def last_checkin(self) -> datetime | None:
        # Search KR history for the latest ts. Best-effort markdown scan.
        candidates: list[datetime] = []
        for line in self.body.splitlines():
            m = re.search(r"-\s+ts:\s*([^\s]+)", line)
            if m:
                raw = m.group(1).strip("\"'")
                try:
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    candidates.append(dt)
                except ValueError:
                    continue
        return max(candidates) if candidates else None


def _load_cfg(project_root: Path) -> dict:
    """Merge DEFAULT_CFG with project-level and plugin-default config.toml [okr]."""
    cfg = dict(DEFAULT_CFG)
    if _toml is None:
        return cfg
    candidates = [
        project_root / ".kiho" / "config.toml",
        Path(__file__).resolve().parents[1] / "templates" / "config.default.toml",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("rb") as fh:
                raw = _toml.load(fh)
        except Exception:
            continue
        block = raw.get("okr") or {}
        # flatten one level: [okr.period], [okr.auto_set] etc. merge keys
        for k, v in block.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    cfg.setdefault(kk, vv)
            else:
                cfg.setdefault(k, v)
    return cfg


def _parse_period(period: str, today: date) -> tuple[date, date] | None:
    """Return (start, end_exclusive) for YYYY-QN / YYYY-HN / custom slug.

    Custom slugs (non-matching) return None — not auto-closeable.
    """
    m = re.match(r"^(\d{4})-Q([1-4])$", period)
    if m:
        year, qi = int(m.group(1)), int(m.group(2))
        start_month = (qi - 1) * 3 + 1
        start = date(year, start_month, 1)
        if qi == 4:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, start_month + 3, 1)
        return start, end
    m = re.match(r"^(\d{4})-H([1-2])$", period)
    if m:
        year, hi = int(m.group(1)), int(m.group(2))
        if hi == 1:
            return date(year, 1, 1), date(year, 7, 1)
        return date(year, 7, 1), date(year + 1, 1, 1)
    return None


def _current_period_label(today: date) -> str:
    quarter = (today.month - 1) // 3 + 1
    return f"{today.year}-Q{quarter}"


def _load_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Best-effort YAML parsing via lines."""
    if not text.startswith("---"):
        return {}, text
    end_match = re.search(r"\n---\s*\n", text[3:])
    if not end_match:
        return {}, text
    fm_raw = text[3 : 3 + end_match.start()]
    body = text[3 + end_match.end() :]
    fm: dict = {}
    for line in fm_raw.splitlines():
        m = re.match(r"^([a-z_][a-z0-9_]*)\s*:\s*(.*)$", line, re.IGNORECASE)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            fm[key] = val
    return fm, body


def load_okrs(project_root: Path) -> list[OKR]:
    """Scan <project>/.kiho/state/okrs/<period>/*.md (excluding _closed/)."""
    okrs_dir = project_root / ".kiho" / "state" / "okrs"
    if not okrs_dir.exists():
        return []
    out: list[OKR] = []
    for period_dir in sorted(okrs_dir.iterdir()):
        if not period_dir.is_dir():
            continue
        for o_file in sorted(period_dir.glob("O-*.md")):
            if "_closed" in o_file.parts:
                continue
            try:
                text = o_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            fm, body = _load_frontmatter(text)
            out.append(OKR(path=o_file, frontmatter=fm, body=body))
    return out


def scan(project_root: Path, today: date | None = None) -> list[Action]:
    today = today or date.today()
    cfg = _load_cfg(project_root)
    actions: list[Action] = []

    if not cfg.get("auto_trigger_enabled", True):
        return actions  # master switch off

    current_period = _current_period_label(today)
    period_bounds = _parse_period(current_period, today)

    okrs = load_okrs(project_root)
    by_id = {o.o_id: o for o in okrs}
    active = [o for o in okrs if o.status == "active"]
    closed = [o for o in okrs if o.status == "closed"]

    # 1. propose-company — no active company O for current period
    active_company_cur = [o for o in active if o.level == "company" and o.period == current_period]
    if not active_company_cur and period_bounds:
        _, period_end = period_bounds
        days_to_end = (period_end - today).days
        # Nudge if period is "starting" (recently began) OR hasn't started yet within window
        nudge_window = int(cfg.get("nudge_days_before_start", 7))
        # Fire if (today is within first 30 days of period) OR (today + nudge_window >= period start)
        period_start, _ = period_bounds
        in_first_month = (today >= period_start) and (today - period_start).days <= 30
        pre_start = (today < period_start) and (period_start - today).days <= nudge_window
        if in_first_month or pre_start:
            actions.append(Action(
                kind="propose-company",
                payload={"period": current_period, "days_to_period_end": days_to_end},
                reason=(
                    "period active with no company O"
                    if in_first_month
                    else "period starts soon with no company O"
                ),
            ))

    # 2. cascade-dept — active company O without aligned dept O
    for co in [o for o in active if o.level == "company"]:
        has_dept_child = any(
            o.level == "department" and o.aligns_to == co.o_id
            for o in active
        )
        if not has_dept_child:
            actions.append(Action(
                kind="cascade-dept",
                payload={"company_o_id": co.o_id, "period": co.period, "owner": co.owner},
                reason=f"company O {co.o_id} has no aligned department O",
            ))

    # 3. cascade-individual — active dept O without aligned individual O(s)
    #    (CEO / OKR-master decides WHICH agents get individual Os based on capability-matrix
    #     + agent-score; this scanner only flags that dispatch is needed, not who)
    for do in [o for o in active if o.level == "department"]:
        has_indiv_child = any(
            o.level == "individual" and o.aligns_to == do.o_id
            for o in active
        )
        if not has_indiv_child:
            actions.append(Action(
                kind="cascade-individual",
                payload={"dept_o_id": do.o_id, "period": do.period, "dept_owner": do.owner},
                reason=f"dept O {do.o_id} has no aligned individual O",
            ))

    # 4. stale-memo — active O with no checkin in > stale_days
    stale_days = int(cfg.get("stale_days", 30))
    today_dt = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    for o in active:
        lc = o.last_checkin()
        if lc is None:
            # never checked in; treat creation as the clock-start via file mtime
            try:
                mtime = o.path.stat().st_mtime
            except OSError:
                continue
            created = datetime.fromtimestamp(mtime, tz=timezone.utc)
            age_days = (today_dt - created).days
        else:
            age_days = (today_dt - lc).days
        if age_days > stale_days:
            actions.append(Action(
                kind="stale-memo",
                payload={
                    "o_id": o.o_id,
                    "level": o.level,
                    "owner": o.owner,
                    "days_since_checkin": age_days,
                    "last_checkin": lc.isoformat() if lc else None,
                },
                reason=f"{age_days} days since last checkin",
            ))

    # 5. period-close — today past period.end for any active O
    for o in active:
        pb = _parse_period(o.period, today)
        if pb is None:
            continue
        _, period_end = pb
        if today >= period_end:
            actions.append(Action(
                kind="period-close",
                payload={"o_id": o.o_id, "level": o.level, "period": o.period,
                         "period_end": period_end.isoformat()},
                reason=f"period {o.period} ended {(today - period_end).days + 1} days ago",
            ))

    # 6. cascade-close — parent O closed, aligned child O(s) still active
    closed_ids = {o.o_id for o in closed}
    for o in active:
        parent = o.aligns_to
        if parent and parent in closed_ids:
            actions.append(Action(
                kind="cascade-close",
                payload={"o_id": o.o_id, "level": o.level, "parent_o_id": parent,
                         "cascade_rule": cfg.get("cascade_rule", "deferred")},
                reason=f"parent {parent} is closed",
            ))

    return actions


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="kiho v6.2 OKR auto-sweep scanner")
    ap.add_argument("--project", type=Path, default=Path.cwd(), help="project root")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD (override for tests)")
    ap.add_argument("--json", action="store_true", help="emit JSON (default)")
    ap.add_argument("--text", action="store_true", help="emit human-readable summary")
    args = ap.parse_args(argv)

    project_root = args.project.resolve()
    if not project_root.exists():
        print(f"project root does not exist: {project_root}", file=sys.stderr)
        return 3

    today = date.today()
    if args.today:
        try:
            today = date.fromisoformat(args.today)
        except ValueError:
            print(f"bad --today: {args.today}", file=sys.stderr)
            return 2

    actions = scan(project_root, today)

    if args.text:
        print(f"OKR auto-sweep — {project_root} — {today.isoformat()}")
        if not actions:
            print("  (no actions)")
        else:
            for a in actions:
                print(f"  [{a.kind}] {a.reason}")
                for k, v in a.payload.items():
                    print(f"    {k}: {v}")
    else:
        print(json.dumps(
            {"today": today.isoformat(), "actions": [asdict(a) for a in actions]},
            indent=2,
            default=str,
        ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
