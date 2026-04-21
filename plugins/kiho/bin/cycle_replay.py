#!/usr/bin/env python3
"""
cycle_replay.py — reconstruct a cycle's timeline from handoffs.jsonl + index.toml.

Used for debugging stuck cycles or auditing past lifecycles.

Usage:
    cycle_replay.py --cycle-id <id> [--project-root <path>] [--detail brief|full]

Exit codes: 0 ok, 1 cycle not found, 2 usage, 3 internal.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

try:
    import tomllib as _toml
except ImportError:
    try:
        import tomli as _toml  # type: ignore
    except ImportError:
        print("FATAL: requires Python 3.11+ tomllib or tomli on 3.10", file=sys.stderr)
        sys.exit(3)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def _iso_to_dt(s: str) -> _dt.datetime:
    return _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)


def render(cycle_id: str, index: dict, handoffs: list[dict], detail: str) -> str:
    meta = index.get("meta", {})
    budget = index.get("budget", {})
    opened_at = meta.get("opened_at", "")
    template = f"{meta.get('template_id', '?')} v{meta.get('template_version', '?')}"
    status = meta.get("status", "?")
    phase = meta.get("phase", "?")
    requestor = meta.get("requestor", "?")

    lines = [
        f"Cycle: {cycle_id}",
        f"Template: {template}",
        f"Opened: {opened_at} by {requestor}",
        f"Status: {status} @ phase {phase}",
        f"Budget: {budget.get('iters_used', 0)}/{budget.get('iters_max', '?')} iters, "
        f"{budget.get('pages_used', 0)}/{budget.get('pages_max', '?')} pages, "
        f"{budget.get('wall_clock_min_used', 0)}/{budget.get('wall_clock_min_max', '?')} min",
        "",
        "Timeline:",
    ]

    if not handoffs:
        lines.append("  (no handoffs recorded)")
    else:
        try:
            opened_dt = _iso_to_dt(opened_at) if opened_at else _iso_to_dt(handoffs[0].get("ts", ""))
        except ValueError:
            opened_dt = None

        for h in handoffs:
            ts = h.get("ts", "")
            try:
                cur_dt = _iso_to_dt(ts)
                if opened_dt:
                    elapsed = cur_dt - opened_dt
                    mins = int(elapsed.total_seconds() // 60)
                    secs = int(elapsed.total_seconds() % 60)
                    rel = f"[{mins:02d}:{secs:02d}]"
                else:
                    rel = "[--:--]"
            except ValueError:
                rel = "[--:--]"

            action = h.get("action") or ""
            if not action and "from" in h and "to" in h:
                action = f"{h['from']} → {h['to']}"
                if h.get("reason"):
                    action += f" ({h['reason']})"
            elif action == "delegate_skill":
                action = f"delegate {h.get('entry_skill', '?')}"
            elif action == "escalate_to_user":
                action = "escalate_to_user"
            elif h.get("from_status") and h.get("from_status") != action:
                action = f"{action} (was {h['from_status']})"

            lines.append(f"  {rel} {action}")
            if detail == "full":
                lines.append(f"          raw: {json.dumps(h, ensure_ascii=False)}")

    blockers = index.get("blockers", {})
    if blockers:
        lines.append("")
        lines.append("Blockers:")
        for k, v in blockers.items():
            lines.append(f"  {k}: {v}")

    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Replay a cycle's timeline.")
    p.add_argument("--cycle-id", required=True)
    p.add_argument("--project-root", default=".")
    p.add_argument("--detail", choices=["brief", "full"], default="brief")
    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    try:
        project_root = Path(args.project_root).resolve()
        cdir = project_root / ".kiho" / "state" / "cycles" / args.cycle_id
        ip = cdir / "index.toml"
        hp = cdir / "handoffs.jsonl"
        if not ip.is_file():
            print(f"Cycle not found: {args.cycle_id}", file=sys.stderr)
            return 1
        with ip.open("rb") as fp:
            index = _toml.load(fp)
        handoffs = _read_jsonl(hp)
        sys.stdout.write(render(args.cycle_id, index, handoffs, args.detail))
        return 0
    except Exception as exc:
        print(f"error: {exc!r}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
