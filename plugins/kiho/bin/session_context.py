#!/usr/bin/env python3
"""
session_context.py — read-only session log parser for kiho.

Scans ~/.claude/projects/<slug>/*.jsonl session logs and returns structured
slices on demand. Used by the session-context skill when CEO, kb-manager, or
any agent needs to see recent activity without loading entire log files into
context.

Usage:
    python session_context.py --query <free-text>
                               [--project <slug>]
                               [--scope current|project|global]
                               [--last <N>]
                               [--since <iso-timestamp>]
                               [--tool <tool-name>]
                               [--agent <agent-name>]
                               [--limit <K>]
                               [--format json|markdown]

Returns a structured summary on stdout. No file writes. No network.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Tunables — justified values, no voodoo constants
DEFAULT_LIMIT = 20           # default max results (keeps output readable)
MAX_LIMIT = 200              # hard upper bound (prevents runaway scans)
SNIPPET_CHARS = 240          # bytes of content shown per match (tight but useful)
LINE_SCAN_CAP = 50_000       # lines to scan per session file (safety cap)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only session log parser for kiho"
    )
    parser.add_argument("--query", default="",
                        help="Free-text query to match against message content")
    parser.add_argument("--project", default=None,
                        help="Project slug (default: inferred from cwd)")
    parser.add_argument("--scope", choices=["current", "project", "global"],
                        default="project",
                        help="Scope: current (this session), project (this project), global (all projects)")
    parser.add_argument("--last", type=int, default=None,
                        help="Return the last N entries (ignores query)")
    parser.add_argument("--since", default=None,
                        help="Only include entries after this ISO-8601 timestamp")
    parser.add_argument("--tool", default=None,
                        help="Filter by tool name (e.g., Bash, Write)")
    parser.add_argument("--agent", default=None,
                        help="Filter by agent name")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"Max results (1..{MAX_LIMIT})")
    parser.add_argument("--format", choices=["json", "markdown"],
                        default="json",
                        help="Output format")
    return parser.parse_args()


def slugify_path(path: Path) -> str:
    """Convert a filesystem path to the Claude Code project-slug form."""
    # Claude Code slugifies cwd by replacing separators with dashes.
    # Example: C:\Users\wky\.claude -> C--Users-wky--claude
    p = str(path.resolve())
    # Drop drive colon on Windows ("C:" -> "C")
    p = re.sub(r"^([A-Za-z]):", r"\1", p)
    # Replace both slashes with dashes
    p = p.replace("\\", "-").replace("/", "-")
    return p


def find_project_dirs(scope: str, project_hint: str | None) -> list[Path]:
    """Return the list of project directories to scan based on scope."""
    projects_root = Path.home() / ".claude" / "projects"
    if not projects_root.exists():
        return []

    if scope == "global":
        return [d for d in projects_root.iterdir() if d.is_dir()]

    if project_hint:
        target = projects_root / project_hint
        return [target] if target.exists() else []

    # Infer from cwd
    cwd_slug = slugify_path(Path.cwd())
    target = projects_root / cwd_slug
    if target.exists():
        return [target]

    # Fallback — best-effort prefix match
    matches = [
        d for d in projects_root.iterdir()
        if d.is_dir() and d.name.startswith(cwd_slug[:8])
    ]
    return matches


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        # Accept Z suffix
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def iter_session_files(project_dirs: list[Path], scope: str) -> list[Path]:
    """Return session JSONL files, newest first. 'current' takes the most recent only."""
    files: list[Path] = []
    for d in project_dirs:
        try:
            files.extend(d.glob("*.jsonl"))
        except OSError:
            continue
    # Sort newest first by mtime
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if scope == "current" and files:
        return [files[0]]
    return files


def extract_snippet(obj: dict[str, Any]) -> str:
    """Pull a short representative snippet from a session log entry."""
    # Session log entries have varied shapes — try common fields in order
    for key in ("content", "text", "message", "summary", "result", "output"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val[:SNIPPET_CHARS]
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, dict):
                inner = first.get("text") or first.get("content")
                if isinstance(inner, str):
                    return inner[:SNIPPET_CHARS]
            elif isinstance(first, str):
                return first[:SNIPPET_CHARS]
    return json.dumps(obj, ensure_ascii=False)[:SNIPPET_CHARS]


def match_entry(
    entry: dict[str, Any],
    query_pattern: re.Pattern[str] | None,
    tool_filter: str | None,
    agent_filter: str | None,
    since: datetime | None,
) -> bool:
    """Return True if the entry passes all filters."""
    if since:
        ts = parse_iso(entry.get("timestamp"))
        if not ts or ts < since:
            return False
    if tool_filter:
        tool = entry.get("tool") or entry.get("tool_name") or ""
        if tool_filter.lower() not in str(tool).lower():
            return False
    if agent_filter:
        agent = entry.get("agent") or entry.get("actor") or ""
        if agent_filter.lower() not in str(agent).lower():
            return False
    if query_pattern:
        blob = json.dumps(entry, ensure_ascii=False)
        if not query_pattern.search(blob):
            return False
    return True


def scan_file(
    path: Path,
    query_pattern: re.Pattern[str] | None,
    tool_filter: str | None,
    agent_filter: str | None,
    since: datetime | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Scan one jsonl file and return matching entries (newest first within file)."""
    matches: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i > LINE_SCAN_CAP:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue
                if match_entry(entry, query_pattern, tool_filter, agent_filter, since):
                    matches.append({
                        "file": path.name,
                        "timestamp": entry.get("timestamp", ""),
                        "type": entry.get("type") or entry.get("event") or "entry",
                        "tool": entry.get("tool") or entry.get("tool_name"),
                        "agent": entry.get("agent") or entry.get("actor"),
                        "snippet": extract_snippet(entry),
                    })
                    if len(matches) >= limit:
                        return matches
    except OSError as exc:
        return [{"file": path.name, "error": f"read failed: {exc}"}]
    return matches


def format_markdown(results: list[dict[str, Any]], query: str) -> str:
    """Render matches as compact markdown."""
    if not results:
        return f"# session-context\n\nNo matches for query: `{query or '(all)'}`\n"
    lines = [f"# session-context — {len(results)} match(es)"]
    if query:
        lines.append(f"**Query:** `{query}`")
    lines.append("")
    for r in results:
        if "error" in r:
            lines.append(f"- **error** in `{r['file']}`: {r['error']}")
            continue
        ts = r.get("timestamp", "")
        tool = r.get("tool") or ""
        agent = r.get("agent") or ""
        meta_bits = [x for x in (ts, tool, agent, r["file"]) if x]
        lines.append(f"- _{' · '.join(meta_bits)}_")
        snippet = r.get("snippet", "").replace("\n", " ")
        lines.append(f"  > {snippet}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()

    # Bound the limit
    limit = max(1, min(args.limit, MAX_LIMIT))

    # Compile query regex (literal case-insensitive fallback)
    query_pattern: re.Pattern[str] | None = None
    if args.query:
        try:
            query_pattern = re.compile(args.query, re.IGNORECASE)
        except re.error:
            # Fall back to literal match
            query_pattern = re.compile(re.escape(args.query), re.IGNORECASE)

    since = parse_iso(args.since) if args.since else None

    project_dirs = find_project_dirs(args.scope, args.project)
    if not project_dirs:
        out = {"status": "no_project_logs_found",
               "cwd": str(Path.cwd()),
               "scope": args.scope,
               "matches": []}
        print(json.dumps(out, indent=2) if args.format == "json" else
              "# session-context\n\nNo project logs found.\n")
        return 0

    files = iter_session_files(project_dirs, args.scope)

    # Handle --last (bypass query filters for a simple recent slice)
    if args.last is not None:
        results: list[dict[str, Any]] = []
        target = max(1, min(args.last, MAX_LIMIT))
        for f in files:
            results.extend(
                scan_file(f, None, None, None, None, target - len(results))
            )
            if len(results) >= target:
                break
        results = results[:target]
    else:
        results = []
        for f in files:
            results.extend(
                scan_file(f, query_pattern, args.tool, args.agent,
                          since, limit - len(results))
            )
            if len(results) >= limit:
                break

    if args.format == "markdown":
        sys.stdout.write(format_markdown(results, args.query))
    else:
        payload = {
            "status": "ok",
            "scope": args.scope,
            "project_dirs": [str(d) for d in project_dirs],
            "files_scanned": len(files),
            "match_count": len(results),
            "matches": results,
        }
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
