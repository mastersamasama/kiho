---
name: state-read
description: Use this skill when any agent needs to inspect kiho's durable state — the CEO ledger, the current plan, recent delegations, committee statuses, or the session's AGENT.md learnings. Reads .kiho/state/ files directly via Read and Grep. No writes. Trigger when the CEO is initializing a Ralph loop, when a subagent needs to know what was delegated before it, when debugging "what just happened", or when reviewing a prior session's closing state.
argument-hint: "<what-to-read>"
metadata:
  trust-tier: T2
  kiho:
    capability: read
    topic_tags: [observability, state-management]
    data_classes: ["ceo-ledger", "plan", "completion"]
---
# state-read

Read-only inspection of kiho's project state tree. Use `Read` and `Grep` directly; no Python helper needed.

## Files you can read

All under `<project>/.kiho/state/`:

| File | Contents | Common queries |
|---|---|---|
| `ceo-ledger.jsonl` | Append-only CEO action log | last 20 entries, entries of type X, entries touching agent Y |
| `plan.md` | Ralph-style @fix_plan.md | What's Pending, what's In progress, what's Blocked |
| `AGENT.md` | Durable runtime learnings | Build commands, known quirks, last-session summary |
| `completion.md` | This turn's completion criteria | What does "done" look like for this turn |
| `org.json` | Current organization chart | Which departments/teams exist, who reports to whom |
| `briefs/<iso>.md` | CEO delegation briefs | The full context a subagent was given |
| `research/<iso>.md` | Research cascade cache | Prior research results for reuse |

Also: `<project>/.kiho/CONTINUITY.md` (last-session handoff) and `<project>/.kiho/committee/<date>-<slug>/` (committee transcripts and decisions).

## Common operations

### Last N ledger entries

```bash
tail -n 20 <project>/.kiho/state/ceo-ledger.jsonl
```

Or using Read with offset if tail isn't available.

### Find all entries of a type

```bash
grep '"action":"delegate"' <project>/.kiho/state/ceo-ledger.jsonl | tail -10
```

### What's currently pending

Read `<project>/.kiho/state/plan.md`, look at the `## Pending` section.

### What did the last session end with

Read `<project>/.kiho/CONTINUITY.md`.

### What's the org chart

Read `<project>/.kiho/state/org.json` with `Read`.

### What was the brief for a specific delegation

Find the `brief_id` in the ledger entry, then read `<project>/.kiho/state/briefs/<brief_id>.md`.

## Output shape

Return whatever the caller asked for. Typical patterns:

**Summarized recent activity** (for CEO initializing a Ralph loop):
```markdown
## Recent activity (last 20 ledger entries)
- 2026-04-12T14:20Z · delegate · eng-lead-01 · brief-...
- 2026-04-12T14:21Z · committee_open · C-17
- 2026-04-12T14:25Z · committee_close · C-17 · confidence 0.92
...
```

**Plan status** (for "what's left"):
```markdown
## Plan status
- In progress: 1 item (spec-02-billing)
- Pending: 3 items
- Blocked: 0 items
- Completed this session: 2 items
```

**Structured JSON** (for subagent consumption): just emit the raw file contents as JSON if the caller needs it structured.

## Invariants

- Read-only. Never modify state files via this skill.
- Never read `.kiho/kb/` through state-read — that's kb-manager's turf.
- Never read other projects' state trees — scope to `<project>/.kiho/` only.
