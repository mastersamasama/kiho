---
name: memory-cross-agent-learn
description: Broadcasts a lesson learned by one agent to a selected set of target agents, filtering for soul compatibility (dropping red-line conflicts, flagging value tensions) and writing the notification into a cross-agent learning queue that the CEO consumes at the next INITIALIZE step. Use when an agent discovers a lesson that other agents on the team could benefit from — a fix for a common mistake, a new convention, a correction to a shared assumption. Triggers on "share this learning", "broadcast lesson", "cross-agent propagate", "tell the other agents", or when soul-apply-override or memory-reflect surfaces a shareable lesson.
metadata:
  trust-tier: T2
  kiho:
    capability: communicate
    topic_tags: [learning]
    data_classes: ["cross-agent-learnings", "lessons"]
---
# memory-cross-agent-learn

Soul-aware lesson propagation. One agent's reflections become another agent's prior knowledge. The skill does not spawn or wake target agents; it enqueues a notification that the CEO injects into each target's next delegation brief.

## Contents
- [Inputs](#inputs)
- [Procedure](#procedure)
- [Target agent selection](#target-agent-selection)
- [Notification format](#notification-format)
- [Queue storage](#queue-storage)
- [Response shape](#response-shape)
- [Anti-patterns](#anti-patterns)

## Inputs

```
source_agent: <agent that learned the lesson>
lesson_id: <memory entry ID, e.g., lesson-2026-04-13-003>
lesson_tags: [<tag1>, <tag2>]
confidence: <0.0-1.0>
override_targets: <optional — explicit list of agent_ids to skip auto-selection>
```

The caller must pre-load the lesson body (or a 1-2 sentence summary) so this skill can embed it in the notification.

## Procedure

1. **Validate** — confirm `source_agent` exists, `lesson_id` resolves to a memory entry, `confidence >= 0.60`. Reject low-confidence lessons with `status: skip_low_confidence`.
2. **Select target agents** — either use `override_targets` directly or run [automatic selection](#target-agent-selection).
3. **Filter by soul** — for each candidate target, compare `lesson_tags` against the target's `red_lines` and `values`:
   - Any tag conflicting with a red line → drop target with reason `red_line_conflict`.
   - Any tag clashing with a value but not a red line → keep target, set `tension: true` in the notification so the target can weigh it.
4. **Write to queue** — append one JSONL entry per surviving target to `.kiho/state/cross-agent-learnings.jsonl`.
5. **Return** — report all targets considered, dropped, queued, and any tensions flagged.

## Target agent selection

**Automatic mode** (no `override_targets`):
1. Read `.kiho/state/capability-matrix.md`. Compute tag overlap between the lesson tags and each agent's skill-tag list.
2. Rank agents by overlap score (descending).
3. Exclude the `source_agent`.
4. For `local:*`-tagged lessons (e.g., `local:frontend`), exclude peers on a different team.
5. Cap the selection at 5 targets — if more than 5 qualify, take the top 5 by score and note the rest in `overflow`.

**Override mode** (`override_targets` provided):
1. Trust the caller. Still run soul filtering.
2. Still cap at 5. If more than 5 provided, reject with `status: error — target_list_too_large`.

## Notification format

Each queue entry follows this JSONL schema:

```json
{
  "queue_id": "xal-2026-04-14-0001",
  "ts": "2026-04-14T08:30:00Z",
  "source_agent": "eng-lead-01",
  "lesson_id": "lesson-2026-04-13-003",
  "lesson_summary": "Always run kb-lint after a bulk wiki rename to catch broken wikilinks.",
  "lesson_tags": ["kb", "wiki", "post-bulk-edit"],
  "confidence": 0.82,
  "target_agent": "kb-manager-01",
  "tension": false,
  "consumed": false,
  "consumed_at": null
}
```

`tension: true` adds a marker the target agent sees during delegation ("this lesson may clash with your value of X — weigh it before applying").

## Queue storage

- **Path:** `.kiho/state/cross-agent-learnings.jsonl`
- **Consumer:** the CEO at INITIALIZE step 15 scans this file for `consumed: false` entries matching the agents being delegated to this turn, injects the `lesson_summary` (plus tension note if any) into the target's delegation brief, and marks the entry `consumed: true` with `consumed_at` set.
- **Retention:** consumed entries survive 7 days for traceability, then archive into `.kiho/state/archive/cross-agent-learnings/<YYYY-MM>.jsonl`.
- **Dedup:** before appending, check the last 50 entries for a matching `(source_agent, lesson_id, target_agent)` tuple; if present, skip with reason `already_queued`.

## Response shape

```json
{
  "status": "ok | skip_low_confidence | error",
  "source_agent": "eng-lead-01",
  "lesson_id": "lesson-2026-04-13-003",
  "targets_considered": 7,
  "targets_queued": ["kb-manager-01", "design-lead-02"],
  "targets_dropped": [
    {"agent": "security-lead-01", "reason": "red_line_conflict"}
  ],
  "tensions_flagged": ["design-lead-02"],
  "queue_entry_ids": ["xal-2026-04-14-0001", "xal-2026-04-14-0002"],
  "overflow": []
}
```

## Anti-patterns

- **Immediate spawning.** Never call `Task` to wake a target agent mid-turn. Always enqueue and let CEO route it.
- **Ignoring red lines.** A lesson that violates a target's red line must be dropped, not marked as tension.
- **Propagating low-confidence lessons.** Below 0.60 is noise; broadcasting it erodes the signal-to-noise ratio of the queue.
- **Dedup-blind propagation.** Re-queueing the same lesson for the same target pollutes the brief and trains the target to ignore shared learnings.
- **Cross-tier leakage.** A `local:*`-tagged lesson must not escape its team; a `company:*`-tagged lesson may cross teams but never crosses into a different company scope.
