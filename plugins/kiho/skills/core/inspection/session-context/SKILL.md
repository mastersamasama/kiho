---
name: session-context
description: Use this skill when any agent needs to see recent activity from prior Claude Code sessions — what tool was called, what the user said, what happened in the last N minutes, how a skill was used, what the previous session's final state was. Parses ~/.claude/projects/<slug>/*.jsonl session logs on demand via a bundled Python script. No hooks, no state propagation; the agent pulls exactly what it needs, exactly when it needs it. Trigger when the CEO is initializing a Ralph loop, when skill-improve needs last-use telemetry, when evolution-scan is mining session traces, or when kb-manager needs to cite a raw session source.
argument-hint: "<query-or-flags>"
metadata:
  trust-tier: T2
  kiho:
    capability: read
    topic_tags: [observability]
    data_classes: ["scratch-per-script"]
---
# session-context

Read-only access to Claude Code session logs. Wraps `bin/session_context.py`, a narrow Python parser.

## When to use

- CEO initializing a Ralph loop: "what happened in the last 60 minutes on this project?"
- `skill-improve`: "last 10 invocations of skill X and their outcomes"
- `evolution-scan`: "mine recent successful executions for capture candidates"
- kb-manager: "find the raw session entry that produced this page"
- Debugging: "what did the user just type that broke us?"

## Usage

Run the script via `Bash`:

```bash
python ${CLAUDE_PLUGIN_ROOT}/bin/session_context.py \
  --query "<text>" \
  --scope project \
  --limit 20 \
  --format markdown
```

All flags are optional. Common combinations:

| Need | Flags |
|---|---|
| Last 20 entries on this project | `--last 20 --format markdown` |
| Entries mentioning a skill | `--query "skill-improve" --limit 10` |
| Tool invocations of Bash | `--tool Bash --limit 15` |
| Activity by a specific agent | `--agent kiho-ceo --last 30` |
| Entries since a timestamp | `--since 2026-04-12T14:00:00Z` |
| Global (all projects) | `--scope global` |

## Output format

- `--format markdown` for human-readable output (default if you want to paste into a transcript or KB)
- `--format json` for structured parsing (default if another agent will consume it)

Markdown shape:
```
# session-context — N match(es)
**Query:** `<query>`

- _<timestamp> · <tool> · <agent> · <file>_
  > <snippet>
```

JSON shape:
```json
{
  "status": "ok",
  "scope": "project",
  "files_scanned": 3,
  "match_count": 12,
  "matches": [
    {"timestamp": "...", "tool": "...", "agent": "...", "snippet": "...", "file": "..."},
    ...
  ]
}
```

## Scopes

- `current` — only the most recent session file (usually "this session")
- `project` (default) — all session files under the project's slugified dir
- `global` — every project under `~/.claude/projects/`

## Limits

Hard-capped at 200 results per call. Line scan cap is 50,000 lines per file. These caps exist to prevent runaway reads on huge session histories.

## Anti-patterns

- Do not use this skill to search the current conversation — use Read/Grep on files directly.
- Do not load the full JSON output if you only need a count or a single snippet; use `--format markdown` and `--limit` to constrain.
- Do not call this skill in a tight loop. If you need many queries, batch them into one call with a broader query and post-filter.
- Do not parse session logs without this script. The JSONL schema is nontrivial and this script handles the edge cases.
