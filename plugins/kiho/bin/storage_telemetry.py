#!/usr/bin/env python3
"""
storage_telemetry.py — minimal Tier-2 JSONL emitter for storage events (v5.19).

Append-only JSONL stream at `<project>/.kiho/state/storage-events.jsonl`
recording kiho storage operations: index build, cache hits, query latency,
eviction, parity checks. Consumers (post-week checkpoint, performance
analytics) aggregate via `org_sync`-style Python loops or an optional
DuckDB overlay per `references/storage-tech-stack.md` §2.

Usage as module:
    from storage_telemetry import record
    record(op="index.build", key="skill-catalog", duration_ms=93, skills_indexed=45)

Usage as CLI:
    storage_telemetry.py record --op <op> [--key K] [--duration-ms N]
                                [--plugin-root .] [--extra '<json>']

Exit codes:
    0 — event written
    2 — usage error
    3 — internal error

Schema (one object per line):
    {
      "ts": "<iso-8601 with timezone>",
      "op": "<operation-id>",       # e.g., "index.build", "index.reuse", "query.fts", ...
      "key": "<optional resource key>",  # e.g., "skill-catalog"
      "duration_ms": <int>,         # optional
      "<extra keys>": ...           # any additional numeric/string fields
    }

Grounding:
    * references/storage-architecture.md T2-MUST-1 / T2-MUST-2 (JSONL regenerable,
      regeneration recipe documented)
    * references/data-storage-matrix.md (new storage-events row to be added
      in v5.19.1 once the stream has lived for one week; for now it is a
      lazy-augmented telemetry stream)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


_DEFAULT_RELPATH = Path(".kiho") / "state" / "storage-events.jsonl"


def _stream_path(plugin_root: Path | None) -> Path:
    root = plugin_root if plugin_root is not None else Path.cwd()
    return Path(root) / _DEFAULT_RELPATH


def record(
    op: str,
    *,
    key: str | None = None,
    duration_ms: int | None = None,
    plugin_root: Path | str | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Append one JSONL event. Returns the stream path.

    Errors writing the file are swallowed — telemetry is best-effort and
    MUST NOT break calling scripts. On failure the function returns the
    attempted path without raising.
    """
    event: dict[str, Any] = {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "op": op,
    }
    if key is not None:
        event["key"] = key
    if duration_ms is not None:
        event["duration_ms"] = int(duration_ms)
    if extra:
        for k, v in extra.items():
            if k in ("ts", "op"):
                continue
            event[k] = v

    pr = Path(plugin_root) if plugin_root else None
    path = _stream_path(pr)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False))
            f.write("\n")
    except OSError:
        pass  # telemetry is best-effort
    return path


# --- CLI --------------------------------------------------------------------

def _plugin_root_default() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__ or "")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("record", help="Append one event")
    pr.add_argument("--op", required=True, help="Operation id (e.g., index.build)")
    pr.add_argument("--key", default=None, help="Optional resource key")
    pr.add_argument("--duration-ms", type=int, default=None)
    pr.add_argument("--plugin-root", default=str(_plugin_root_default()))
    pr.add_argument("--extra", default=None, help='JSON object of extra fields')

    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    try:
        extra = json.loads(args.extra) if args.extra else None
        path = record(
            op=args.op,
            key=args.key,
            duration_ms=args.duration_ms,
            plugin_root=args.plugin_root,
            extra=extra,
        )
        print(json.dumps({"status": "ok", "stream": str(path)}))
        return 0
    except json.JSONDecodeError as exc:
        print(
            json.dumps({"status": "error", "error": f"--extra not valid JSON: {exc}"}),
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # pragma: no cover — defensive
        print(json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
