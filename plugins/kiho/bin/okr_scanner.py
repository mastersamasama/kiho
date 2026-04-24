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
                           (v6.2.1+: checks BOTH project-tier AND $COMPANY_ROOT/company/state/
                           before emitting — company-O set in any project suppresses re-nudge)
  - cascade-dept         : active company O has no aligned dept O for some dept
  - cascade-individual   : active dept O has qualifying agents without individual Os
  - stale-memo           : active O with no checkin > stale_days
  - period-close         : today > period.end for period with any active O
  - cascade-close        : parent O closed; aligned children still active
  - onboard-dispatch     : (v6.2.1+) ledger entry `okr_individual_schedule_onboard` reached
                           `fires_at_ts` — time to dispatch HR individual-O for that agent

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


def _resolve_company_root() -> Path | None:
    """Resolve $COMPANY_ROOT from env, plugin config.toml, or skill config.toml.

    Precedence (v6.2.1):
      1. Env var COMPANY_ROOT (explicit override)
      2. ${CLAUDE_PLUGIN_ROOT}/skills/core/harness/kiho/config.toml [company] root
      3. plugin-default templates/config.default.toml [company] root
      4. None (company-tier reads silently skipped)
    """
    import os

    env = os.environ.get("COMPANY_ROOT")
    if env:
        p = Path(env)
        if p.exists():
            return p

    if _toml is None:
        return None

    here = Path(__file__).resolve().parents[1]
    for candidate in (
        here / "skills" / "core" / "harness" / "kiho" / "config.toml",
        here / "templates" / "config.default.toml",
    ):
        if not candidate.exists():
            continue
        try:
            with candidate.open("rb") as fh:
                raw = _toml.load(fh)
        except Exception:
            continue
        company = raw.get("company") or {}
        root = company.get("root")
        if root:
            p = Path(str(root))
            if p.exists():
                return p
    return None


def _load_cfg(project_root: Path) -> dict:
    """Merge DEFAULT_CFG with plugin-default, $COMPANY_ROOT/settings.md, project config.toml.

    Layered precedence (later wins):
      1. DEFAULT_CFG hardcoded
      2. ${CLAUDE_PLUGIN_ROOT}/templates/config.default.toml [okr]
      3. $COMPANY_ROOT/settings.md [okr] (v6.2.1+ — gap G)
      4. <project>/.kiho/config.toml [okr]

    Settings.md uses TOML-in-markdown heuristic: we look for an `[okr]` header
    line followed by key=value lines terminated by blank line or next `[` block.
    Lightweight parser — company-wide OKR settings don't need full TOML escape
    handling.
    """
    cfg = dict(DEFAULT_CFG)
    if _toml is None:
        return cfg

    # Layer 2: plugin default
    here = Path(__file__).resolve().parents[1]
    plugin_default = here / "templates" / "config.default.toml"
    if plugin_default.exists():
        try:
            with plugin_default.open("rb") as fh:
                raw = _toml.load(fh)
            _merge_okr_block(cfg, raw.get("okr") or {})
        except Exception:
            pass

    # Layer 3: $COMPANY_ROOT/settings.md (TOML-in-markdown)
    company_root = _resolve_company_root()
    if company_root:
        settings_md = company_root / "settings.md"
        if settings_md.exists():
            _merge_okr_from_settings_md(cfg, settings_md)

    # Layer 4: project .kiho/config.toml
    project_toml = project_root / ".kiho" / "config.toml"
    if project_toml.exists():
        try:
            with project_toml.open("rb") as fh:
                raw = _toml.load(fh)
            _merge_okr_block(cfg, raw.get("okr") or {})
        except Exception:
            pass

    return cfg


def _merge_okr_block(cfg: dict, block: dict) -> None:
    """Merge an [okr] TOML block into cfg — later callers win via overwrite."""
    for k, v in block.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                cfg[kk] = vv  # later layer wins (overwrite)
        else:
            cfg[k] = v


def _merge_okr_from_settings_md(cfg: dict, settings_md: Path) -> None:
    """Extract [okr] block from TOML-in-markdown settings.md and merge into cfg.

    Finds `[okr]` or `[okr.*]` headers inside markdown and parses key = value
    lines until blank / next header. Quotes are stripped; booleans lower-case;
    integers parsed. Anything unparseable is left as string.
    """
    try:
        text = settings_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    in_okr = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            in_okr = False
            continue
        if line.startswith("["):
            in_okr = line == "[okr]" or line.startswith("[okr.")
            continue
        if not in_okr:
            continue
        m = re.match(r"^([a-z_][a-z0-9_]*)\s*=\s*(.+?)(?:\s*#.*)?$", line, re.IGNORECASE)
        if not m:
            continue
        key, raw_val = m.group(1), m.group(2).strip()
        if raw_val.startswith('"') and raw_val.endswith('"'):
            cfg[key] = raw_val[1:-1]
        elif raw_val.startswith("'") and raw_val.endswith("'"):
            cfg[key] = raw_val[1:-1]
        elif raw_val.lower() == "true":
            cfg[key] = True
        elif raw_val.lower() == "false":
            cfg[key] = False
        else:
            try:
                cfg[key] = int(raw_val)
            except ValueError:
                try:
                    cfg[key] = float(raw_val)
                except ValueError:
                    cfg[key] = raw_val


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
    """Scan both project-tier and company-tier OKR directories.

    v6.2.1+ (gap E): reads:
      - <project>/.kiho/state/okrs/<period>/*.md
      - $COMPANY_ROOT/company/state/okrs/<period>/*.md  (if company root resolved)

    Excludes _closed/ subdirs in either tier. Company-tier Os are tagged with
    `scope=company-tier` in their .path for downstream filtering; project-tier
    files stay as project_root-relative.
    """
    dirs_to_scan: list[tuple[str, Path]] = [
        ("project", project_root / ".kiho" / "state" / "okrs"),
    ]
    company_root = _resolve_company_root()
    if company_root:
        dirs_to_scan.append(("company", company_root / "company" / "state" / "okrs"))

    out: list[OKR] = []
    for _scope, okrs_dir in dirs_to_scan:
        if not okrs_dir.exists():
            continue
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


def parse_timestamp(raw: str) -> datetime | None:
    """Parse ISO-8601 timestamp, coercing naive datetimes to UTC.

    Returns None on unparseable input (not exception — scanner is best-effort).
    """
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _load_ledger(project_root: Path) -> list[dict]:
    """Load ceo-ledger.jsonl for scanner checks that need action history."""
    ledger = project_root / ".kiho" / "state" / "ceo-ledger.jsonl"
    if not ledger.exists():
        return []
    out: list[dict] = []
    for line in ledger.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
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

    # 7. onboard-dispatch (v6.2.1+, gap C) — ledger `okr_individual_schedule_onboard`
    #    entries whose fires_at_ts has passed AND no matching dispatch/individual-O
    #    emission since. Gated on [okr.auto_set] individual_on_onboard.
    if cfg.get("individual_on_onboard", True):
        ledger = _load_ledger(project_root)
        pending = _collect_pending_onboard_dispatches(ledger, today_dt)
        for sched in pending:
            actions.append(Action(
                kind="onboard-dispatch",
                payload={
                    "agent": sched["agent"],
                    "scheduled_at": sched["scheduled_at"],
                    "fires_at": sched["fires_at"],
                    "days_since_scheduled": sched["days_since_scheduled"],
                },
                reason=(
                    f"agent {sched['agent']} passed onboard threshold "
                    f"({sched['days_since_scheduled']} days); dispatch HR individual-O"
                ),
            ))

    return actions


def _collect_pending_onboard_dispatches(ledger: list[dict], today_dt: datetime) -> list[dict]:
    """Return onboard schedules whose fires_at has passed + no matching dispatch yet.

    Ledger shape (v6.2.1 onboard step 8):
      {"action": "okr_individual_schedule_onboard",
       "payload": {"agent": "<id>", "scheduled_at": "<iso>", "fires_at": "<iso>"}}

    A schedule is considered "dispatched" when a subsequent entry has action
    in {"okr_dispatch_spawn", "okr_individual_emitted",
        "okr_individual_rejected", "okr_individual_schedule_cancelled"} with the
    same agent id. A schedule is also cleared if a newer `okr_individual_schedule_onboard`
    for the same agent supersedes it.
    """
    pending_by_agent: dict[str, dict] = {}
    for entry in ledger:
        action = entry.get("action", "")
        payload = entry.get("payload") or {}
        agent = str(payload.get("agent", ""))
        if not agent:
            continue
        if action == "okr_individual_schedule_onboard":
            fires_raw = payload.get("fires_at", "")
            fires_at = parse_timestamp(fires_raw) if fires_raw else None
            if fires_at is None:
                continue
            pending_by_agent[agent] = {
                "agent": agent,
                "scheduled_at": payload.get("scheduled_at", ""),
                "fires_at": fires_raw,
                "fires_dt": fires_at,
            }
        elif action in {
            "okr_dispatch_spawn",
            "okr_individual_emitted",
            "okr_individual_rejected",
            "okr_individual_schedule_cancelled",
        }:
            pending_by_agent.pop(agent, None)

    out: list[dict] = []
    for rec in pending_by_agent.values():
        if rec["fires_dt"] <= today_dt:
            days_since = (today_dt - rec["fires_dt"]).days
            out.append({
                "agent": rec["agent"],
                "scheduled_at": rec["scheduled_at"],
                "fires_at": rec["fires_at"],
                "days_since_scheduled": days_since,
            })
    return out


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
