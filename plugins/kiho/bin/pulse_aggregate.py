#!/usr/bin/env python3
"""Aggregate recent values-flag entries into a friction rollup.

Reader aid for comms + hr-lead at CEO INITIALIZE. Groups entries by topic,
counts frequency, flags topics with N >= threshold for values-alignment-audit
attention. Stdlib-only. Regenerable Tier-2 output — does not mutate sources.

Invocation:
    python bin/pulse_aggregate.py --project <path> [--days 30] [--threshold 3]
    python bin/pulse_aggregate.py --project <path> --json

Introduced by committee `pulse-surveys-2026-04-23` (v5.23 planning) as a
helper to complement the retrospective ceremony's process_friction section.
The script is READ-ONLY over `values-flag.jsonl`; it never writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class FlagEntry:
    timestamp: datetime
    agent: str
    topic: str
    severity: str
    summary: str


@dataclass
class TopicRollup:
    topic: str
    count: int
    agents: set[str] = field(default_factory=set)
    latest: datetime | None = None
    threshold_exceeded: bool = False


def parse_timestamp(raw: str) -> datetime:
    """Accept ISO-8601 with or without timezone."""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_values_flag_jsonl(path: Path) -> list[FlagEntry]:
    """Return parsed entries; missing file or unparseable lines are skipped."""
    entries: list[FlagEntry] = []
    if not path.exists():
        return entries
    with path.open("r", encoding="utf-8") as fh:
        for line_num, raw in enumerate(fh, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                print(
                    f"warning: {path}:{line_num} skipped (invalid JSON)",
                    file=sys.stderr,
                )
                continue
            ts = parse_timestamp(row.get("timestamp", row.get("created_at", "")))
            entries.append(
                FlagEntry(
                    timestamp=ts,
                    agent=str(row.get("agent", row.get("from_agent", "unknown"))),
                    topic=str(row.get("topic", row.get("subject", "untagged"))),
                    severity=str(row.get("severity", "info")),
                    summary=str(row.get("summary", row.get("body", "")))[:120],
                )
            )
    return entries


def rollup(
    entries: list[FlagEntry], since: datetime, threshold: int
) -> list[TopicRollup]:
    """Group within-window entries by topic. Flag topics at/over threshold."""
    filtered = [e for e in entries if e.timestamp >= since]
    counter: Counter[str] = Counter()
    agents_by_topic: dict[str, set[str]] = defaultdict(set)
    latest_by_topic: dict[str, datetime] = {}
    for entry in filtered:
        counter[entry.topic] += 1
        agents_by_topic[entry.topic].add(entry.agent)
        prior = latest_by_topic.get(entry.topic)
        if prior is None or entry.timestamp > prior:
            latest_by_topic[entry.topic] = entry.timestamp
    rollups = [
        TopicRollup(
            topic=topic,
            count=count,
            agents=agents_by_topic[topic],
            latest=latest_by_topic.get(topic),
            threshold_exceeded=count >= threshold,
        )
        for topic, count in counter.most_common()
    ]
    return rollups


def format_text(
    rollups: list[TopicRollup], days: int, threshold: int
) -> str:
    lines = [f"Friction rollup — last {days} days (threshold: {threshold} flags)"]
    if not rollups:
        lines.append("  (no flags in window)")
        return "\n".join(lines)
    width = max(len(r.topic) for r in rollups)
    for r in rollups:
        marker = "  (threshold exceeded)" if r.threshold_exceeded else ""
        flag_word = "flags" if r.count != 1 else "flag"
        lines.append(
            f"  {r.topic.ljust(width)} : {r.count} {flag_word}"
            f"  ({len(r.agents)} unique agent{'s' if len(r.agents) != 1 else ''}){marker}"
        )
    return "\n".join(lines)


def format_json(rollups: list[TopicRollup], days: int, threshold: int) -> str:
    return json.dumps(
        {
            "window_days": days,
            "threshold": threshold,
            "topics": [
                {
                    "topic": r.topic,
                    "count": r.count,
                    "unique_agents": sorted(r.agents),
                    "latest": r.latest.isoformat() if r.latest else None,
                    "threshold_exceeded": r.threshold_exceeded,
                }
                for r in rollups
            ],
        },
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate values-flag entries by topic.")
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: cwd). Reads <project>/.kiho/state/values-flag.jsonl.",
    )
    parser.add_argument(
        "--days", type=int, default=30, help="Window size in days (default: 30)."
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Count at/over which a topic is marked threshold-exceeded (default: 3).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args(argv)

    jsonl = args.project / ".kiho" / "state" / "values-flag.jsonl"
    entries = load_values_flag_jsonl(jsonl)
    since = datetime.now(tz=timezone.utc) - timedelta(days=args.days)
    rollups = rollup(entries, since, args.threshold)

    if args.json:
        print(format_json(rollups, args.days, args.threshold))
    else:
        print(format_text(rollups, args.days, args.threshold))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
