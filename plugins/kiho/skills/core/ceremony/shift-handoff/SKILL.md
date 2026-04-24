---
name: shift-handoff
description: Use this skill at CEO DONE to produce a structured handoff for the next session. Upgrades the existing CONTINUITY.md (which has been a free-text dump) into a four-section ceremony output — completed, blocked, on-fire, next-priorities — so the next /kiho turn can resume in seconds rather than re-deriving state from ledger scans. Triggers from CEO DONE step (replaces the ad-hoc CONTINUITY.md write); also manually invocable as "shift handoff" or "end of session brief". Writes the structured handoff to CONTINUITY.md AND a memory shift-handoff entry to ceo-01 so the rolling 30d window is queryable.
metadata:
  trust-tier: T2
  kiho:
    capability: communicate
    topic_tags: [coordination, lifecycle]
    data_classes: [continuity]
---
# shift-handoff

The end-of-session ceremony. CONTINUITY.md was free-text and read by SessionStart hook; this skill makes it structured so the next CEO turn can rely on a known shape.

## When to use

- CEO DONE step (replaces the ad-hoc CONTINUITY.md write at step 7)
- Manually after a long session to produce an interim handoff
- Pre-shift-change in multi-agent setups (currently degenerate to single-CEO; future-compat)

Do **NOT** invoke when:

- The turn produced no completions and no blockers — empty handoff is noise; just write `"no state changes; refer to prior CONTINUITY.md"` inline
- The user has already asked a question and is waiting — answer first, handoff after

## Inputs

```
turn_id: <id>                     # default current turn
include_memory_write: <bool>      # default true
target: continuity-md | both      # default both (writes CONTINUITY.md AND memory entry)
```

## Procedure

1. **Aggregate the four sections from this turn's ledger and plan.md.**

   **completed** — read `plan.md`'s Completed section (items moved during this turn). For each: `{item_id, title, owner_agent, completion_iteration, key_artifact_ref}`.

   **blocked** — read `plan.md`'s Blocked section. For each: `{item_id, title, blocker_summary, owner_agent, unblock_dependency, opened_iteration}`.

   **on-fire** — read `state/incidents/index` for incidents with `status: open` AND `severity ∈ {sev1, sev2}`. For each: `{incident_id, severity, opened_at, owner_agent, current_state}`.

   **next-priorities** — read `plan.md`'s Pending section, filter to items where `priority` is high OR the item has dependencies satisfied this turn. For each: `{item_id, title, recommended_starter_agent, blocking_factors_resolved}`.

   **unread-announcements** (v5.23+) — scan `state/announcements/*.md` for entries where `pinned_until > now()` AND the frontmatter `ack_by` list does NOT contain every agent matched by `audience`. Per matching agent, collect `{announcement_id, subject, pinned_until, ack_required}`. These surface in the continuity output as a fifth section; agents pick them up on their next `memo-inbox-read` sweep.

2. **Compute one-line digest.** "Turn <id>: <N> completed, <N> blocked, <N> on-fire, <N> next, <N> pinned announcements." This is the SessionStart hook's load-bearing pre-read. The announcement count is appended at the end (v5.23+ — hook readers that pre-date v5.23 gracefully ignore trailing fields).

3. **Write the structured CONTINUITY.md.** Format:
   ```markdown
   # Continuity — <ts>

   <one-line digest>

   ## Completed this turn
   - **<title>** (<item_id>) — <owner> @ iter <N> — <key_artifact_ref>
   ...

   ## Blocked
   - **<title>** (<item_id>) — blocker: <summary>; unblock requires: <dep>; opened iter <N>
   ...

   ## On fire (open sev1/sev2)
   - **<incident_id>** (<sev>) — <current_state>; owner: <agent>
   ...

   ## Next priorities (recommended starters)
   - **<title>** (<item_id>) — start with: <agent>; ready because: <blocking_factors_resolved>
   ...

   ## Unread pinned announcements (v5.23+)
   - **<announcement_id>** — <subject>; pinned until <pinned_until>; ack required: <yes|no>
   ...

   ## Cross-references
   - This turn's ledger: state/ceo-ledger.jsonl rows <start>-<end>
   - Telemetry rollup: _meta-runtime/skill-health.jsonl
   - Last evolve audit: _meta-runtime/storage-audit.jsonl <last row>
   ```

4. **Write a memory entry to ceo-01.** If `include_memory_write: true`, call `memory-write`:
   ```
   agent_id: ceo-01
   memory_type: shift-handoff
   confidence: 0.90
   tags: [continuity, turn-<id>]
   source: "shift-handoff@<turn_id>"
   content: |
     <one-line digest>
     Detail: <continuity_ref>
     Critical attention next turn: <on-fire and next-priorities highlights, max 3 bullets>
   ```
   Per `references/memory-pruning-policy.md`, shift-handoff entries are retained 30 days then synthesized into AGENT.md.

5. **Return refs.** Response shape below.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: shift-handoff
STATUS: ok | error
TURN_ID: <id>
COMPLETED_COUNT: <int>
BLOCKED_COUNT: <int>
ON_FIRE_COUNT: <int>
NEXT_PRIORITIES_COUNT: <int>
CONTINUITY_REF: md://CONTINUITY.md
MEMORY_REF: mem://ceo-01/shift-handoffs#L<n>
```

## Invariants

- **Five sections, fixed order.** completed / blocked / on-fire / next-priorities / unread-announcements. Other sections degrade SessionStart hook's parsability. The announcements section MAY be empty (no pinned entries in window); it MUST appear in the fixed order when present.
- **One-line digest at the top.** SessionStart only loads the first ~265 chars; that line carries the load.
- **No prose preamble.** No "Hello from the previous CEO turn"; the next CEO knows.
- **Atomic write.** CONTINUITY.md is replaced wholesale, not appended. The previous turn's continuity is git history.

## Non-Goals

- Not a session summary for the user. The user-facing summary at DONE step 9 is separate.
- Not a retrospective. Patterns across turns belong in retrospective.
- Not a status page. Single-reader (next CEO turn); not for human dashboard consumption.
- Not a backup. CONTINUITY.md is operational, not archival; rely on git for full history.

## Anti-patterns

- Never include closed/resolved items in "on-fire". Closed incidents go to retrospective triggers, not the next turn's attention.
- Never list >5 items per section. If you have more, the section is "everything"; pick the top 5 or escalate the volume issue.
- Never skip the cross-references section. The next CEO needs to know where to dig deeper.
- Never write CONTINUITY.md without also writing the memory entry. The memory entry is what makes shift-handoff queryable across turns.

## Grounding

- `agents/kiho-ceo.md` DONE step 7 — the canonical invocation point.
- SessionStart hook (loads CONTINUITY.md prefix) — the load-bearing reader of this output.
- `references/memory-pruning-policy.md` — shift-handoff retention rule.
- `skills/core/ceremony/retrospective/SKILL.md` — the heavier ceremony for cross-turn pattern mining.
