---
name: memory-write
description: Writes a new entry to an agent's memory store (observations, reflections, lessons, or todos). Appends a frontmatter-delimited entry to the appropriate memory file with confidence, tags, and source provenance. For high-value lessons with confidence >= 0.95, suggests graduation to the KB via kb-add. Use when an agent learns something during a task, records a pattern, captures a lesson from a committee, or adds a todo for future work. Triggers on "remember this", "note that", "lesson learned", "add todo", or after committee/task completion.
metadata:
  trust-tier: T2
  kiho:
    capability: create
    topic_tags: [ingestion]
    data_classes: ["observations"]
---
# memory-write

Appends a structured entry to an agent's memory. Memory is the agent's private, durable context that persists across sessions. Unlike the KB (shared, vetted, structured), memory is personal and low-ceremony.

## Contents
- [Inputs](#inputs)
- [Write procedure](#write-procedure)
- [Memory types](#memory-types)
- [KB graduation](#kb-graduation)
- [Response shape](#response-shape)
- [Anti-patterns](#anti-patterns)

## Inputs

```
agent_id: <agent-name or agent-name-instance-id>
memory_type: observation | reflection | lesson | todo
                | soul-override | onboarding-note
                | rejection-feedback | shift-handoff
content: <markdown body of the entry>
confidence: <0.0-1.0>
tags: [<kebab-case strings>]
source: <where this memory came from — committee ID, task path, session, etc.>
tier: project | company  (default: project)
written_by: <writing-agent-id>  (default: caller; required for cross-agent writes)
```

**Cross-agent writes (v5.20 Wave 2.1+).** Some ceremonies write to *other* agents' memories (retrospective → participants' lessons; postmortem → affected_agents' lessons; committee clerk → members' reflections; recruit/onboard → IC's onboarding-note). When `written_by != agent_id`, the writer MUST be a CEO/clerk/HR-lead role; non-CEO peer writes are still rejected by the anti-pattern below. The skill records `written_by` in the entry frontmatter so the audit trail is preserved.

All fields except `agent_id`, `memory_type`, and `content` have defaults:
- `confidence`: 0.70
- `tags`: [] (auto-extracted from content keywords if empty)
- `source`: "session" (current session)
- `tier`: "project"

## Write procedure

1. Resolve the memory file path:
   - Project: `<project>/.kiho/agents/<agent-name>/memory/<type>s.md`
   - Company: `$COMPANY_ROOT/agents/<agent-name>/memory/<type>s.md`
2. If the file or directory does not exist, create it with `mkdir -p` and an empty file.
3. Generate an `entry_id`: `mem-<agent-short>-<sequential-number>` (read the file to find the highest existing sequence number, increment by 1).
4. Append the new entry:

```markdown

---
entry_id: mem-eng-01-043
type: observation
created_at: 2026-04-11T15:30:00Z
confidence: 0.85
tags: [caching, redis, performance]
source: committee/2026-04-11-caching-strategy
---
Redis cluster mode requires at least 6 nodes for production HA. Single-node Redis is acceptable for dev/staging.
```

5. If `memory_type` is `lesson` and `confidence >= 0.95`, trigger KB graduation check (see below).
6. Return the entry_id and file path.

## Memory types

| Type | When to use | Typical confidence range | File | Retention |
|---|---|---|---|---|
| **observation** | Raw fact learned during a task. No interpretation. | 0.60-0.90 | `memory/observations.md` | importance-decay; pruned by `memory-prune` when >100 entries |
| **reflection** | Pattern noticed across multiple observations. Requires at least 2 supporting observations. | 0.70-0.90 | `memory/reflections.md` | retained until consolidated into a lesson |
| **lesson** | Actionable guideline derived from reflections. Changes future behavior. | 0.80-0.98 | `memory/lessons.md` | retained indefinitely (committee-blessed) |
| **todo** | Action the agent plans to take in a future session. Include a clear completion criterion. | N/A (confidence = 1.0) | `memory/todos.md` | archived on completion; pruned 90d after archive |
| **soul-override** | CEO/HR-lead authorized soul trait change. | N/A (governance) | `memory/soul-overrides.md` | retained indefinitely (committee artifact) |
| **onboarding-note** | First-week ramp-up notes from `onboard` skill (Wave 3.1). | 0.70-0.90 | `memory/onboarding.md` | retained 180 days, then archived |
| **rejection-feedback** | Structured rejection memo for losing recruit candidates. | 0.70-0.90 | `memory/rejection-feedback.md` | retained 365 days for re-interview reference |
| **shift-handoff** | End-of-shift structured handoff (Wave 3.4). | N/A | `memory/shift-handoffs.md` | retained 30 days; rolled into AGENT.md weekly |

### Promotion ladder

Observations can be promoted to reflections, and reflections to lessons, via `skills/memory-consolidate/`. memory-write only writes at the specified type; it does not auto-promote.

## KB graduation

When a lesson has `confidence >= 0.95`:

1. Check if the lesson duplicates an existing KB entry via `kb-search` (query the lesson content)
2. If no match: suggest graduation by returning `kb_graduation_candidate: true` in the response
3. The calling agent (or CEO) decides whether to call `kb-add` with the lesson as a `principle` or `convention` page
4. If the lesson graduates to KB, add a tag `graduated: <kb-page-id>` to the memory entry

Do not auto-graduate. The decision to add to KB requires a human or CEO judgment call.

## Response shape

```json
{
  "status": "ok",
  "entry_id": "mem-eng-01-043",
  "file_path": ".kiho/agents/kiho-eng-lead/memory/observations.md",
  "kb_graduation_candidate": false
}
```

## Anti-patterns

- Never write to another agent's memory **as a peer**. Cross-agent writes are only allowed when invoked from a CEO / clerk / HR-lead role context (retrospective, postmortem, committee, recruit/onboard); the writer-of-record is captured in `written_by`. Pure peer-to-peer writes remain forbidden — use `memo-send` or `memory-cross-agent-learn` instead.
- Never store secrets, credentials, or PII in memory. Memory files are plaintext on disk.
- Never write duplicate entries. Before appending, do a quick content similarity check against the last 10 entries in the file.
- Never write observations with confidence > 0.95. If confidence is that high, it should be a reflection or lesson.
- Never skip the `source` field. Provenance matters for later consolidation.
