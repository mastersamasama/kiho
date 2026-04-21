---
name: memory-read
description: Reads per-agent memory files (observations, reflections, lessons, todos) and returns matching entries. Accepts an agent-id and optional query string or tags for filtering. Scoped by tier — global agents read from $COMPANY_ROOT/agents/<name>/memory/, project agents from .kiho/agents/<name>/memory/. Use when any agent needs to recall prior experiences, check existing lessons, review outstanding todos, or search their own memory before making decisions. Triggers on "what do I know about", "recall", "check memory", "my notes on".
metadata:
  trust-tier: T2
  kiho:
    capability: read
    topic_tags: [retrieval]
    data_classes: ["observations", "reflections", "lessons", "todos"]
---
# memory-read

Retrieves entries from an agent's memory store. Four memory types exist: observations (raw facts), reflections (interpreted patterns), lessons (actionable guidelines), and todos (pending actions). Each entry is a frontmatter-delimited block in a markdown file.

## Contents
- [Inputs](#inputs)
- [Memory locations](#memory-locations)
- [Entry format](#entry-format)
- [Query and filtering](#query-and-filtering)
- [Response shape](#response-shape)
- [Anti-patterns](#anti-patterns)

## Inputs

```
agent_id: <agent-name or agent-name-instance-id>
memory_type: observation | reflection | lesson | todo | all  (default: all)
query: <optional search string>
tags: [<optional tag filters>]
limit: <max entries to return, default 20>
tier: project | company  (default: project)
```

## Memory locations

**Project-scoped agents:**
```
<project>/.kiho/agents/<agent-name>/memory/
  observations.md
  reflections.md
  lessons.md
  todos.md
```

**Company-scoped agents (global):**
```
$COMPANY_ROOT/agents/<agent-name>/memory/
  observations.md
  reflections.md
  lessons.md
  todos.md
```

If the memory directory or files do not exist, return an empty result (not an error). The agent has no memories yet.

## Entry format

Each memory file contains zero or more entries, separated by `---`:

```markdown
---
entry_id: mem-<agent>-<seq>
type: observation
created_at: 2026-04-11T14:00:00Z
confidence: 0.85
tags: [auth, firebase, performance]
source: committee/2026-04-11-auth-provider
---
Firebase Auth's free tier has a 10k MAU limit. Beyond that, Identity Platform pricing applies at $0.0055/MAU.

---
entry_id: mem-<agent>-<seq+1>
type: observation
...
```

## Query and filtering

When `query` is provided:
1. Read all entries from the specified memory type(s)
2. Score each entry by word overlap between the query and the entry body + tags
3. Return the top `limit` entries sorted by score descending

When `tags` are provided:
1. Filter entries to only those whose `tags` array intersects with the requested tags
2. If both `query` and `tags` are provided, apply tags filter first, then score by query

When neither is provided:
1. Return the most recent `limit` entries sorted by `created_at` descending

## Response shape

```markdown
## Memory results for <agent_id>

**Query:** <query or "none">
**Tags:** <tags or "none">
**Results:** <count> entries

### [mem-eng-01-042] observation — 2026-04-11T14:00:00Z
**confidence:** 0.85
**tags:** auth, firebase, performance
Firebase Auth's free tier has a 10k MAU limit...

### [mem-eng-01-039] lesson — 2026-04-10T09:30:00Z
**confidence:** 0.92
**tags:** auth, vendor-selection
Always check vendor pricing tiers before recommending...
```

## Anti-patterns

- Never read another agent's memory without explicit authorization from the CEO or a department leader. Memory is private by default.
- Never modify memory files via memory-read. Use `skills/memory-write/` for writes.
- Never return the entire memory store when a query would suffice. Memory files can grow large; always filter.
- Never synthesize or interpret memory entries — return them as-is. Interpretation is the reading agent's job.
