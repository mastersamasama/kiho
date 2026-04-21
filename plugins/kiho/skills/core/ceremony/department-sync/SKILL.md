---
name: department-sync
description: Use this skill when a department lead needs a structured pulse from their ICs without the CEO pulling each agent individually. The lead spawns the IC list with a uniform "did/doing/blocked" prompt (lighter than standup-log, faster than 1:1), aggregates into a dept-digest, and returns one summary to the CEO. Replaces the anti-pattern where CEO INITIALIZE step 9 reads every agent's lessons individually — the dept lead is the right aggregation point. Triggers on "dept sync", "department standup", "team pulse", "rollup status from <dept>", or auto-fires when CEO INITIALIZE detects > 5 agents in the planned RACI fanout (would breach fanout cap if CEO pulled directly).
metadata:
  trust-tier: T2
  kiho:
    capability: orchestrate
    topic_tags: [coordination, lifecycle]
    data_classes: [observations]
---
# department-sync

The "lead aggregates, CEO consumes one digest" pattern. Solves the depth/fanout cap pressure when a department has 4+ ICs and CEO would otherwise spawn each individually.

## When to use

- CEO INITIALIZE detected > 5 unique agents in this turn's planned RACI assignments
- A dept lead is about to delegate ≥ 3 parallel sub-tasks and wants a status snapshot first
- Pre-retrospective pulse: lead wants to know what changed before triggering the (heavier) retrospective ceremony

Do **NOT** invoke when:

- The dept has ≤ 2 active ICs (lead can just read their standup-log directly)
- The CEO needs a full retrospective — that's a different ceremony with deeper output
- A blocker needs immediate attention — `memo-send severity=blocker` direct, don't delay for sync

## Inputs

```
dept_id: <dept-name>                         # required (e.g., "engineering")
lead_id: <agent-id>                          # required (must be the dept's lead per org-registry)
ic_ids: [<id>, ...]                          # optional; defaults to all ICs under lead
include_pre_read: <bool>                     # default true; lead reads standup-log shards first
return_to: ceo-01 | <other-lead>             # default ceo-01
```

## Procedure

1. **Ownership check.** Resolve `.kiho/state/org-registry.md`. If `lead_id` is not the dept lead of `dept_id`, return `status: error reason=not_dept_lead`. Multi-dept agents who lead one dept may sync that one only.

2. **Pre-read (lead-side, optional).** If `include_pre_read=true`, the lead reads:
   - The latest standup-log shard for the current week, filtered to `agent_id ∈ ic_ids`
   - Any open blockers in the lead's own inbox originating from these ICs
   This populates the lead's context so the sync prompt can ask about *changes since*, not full status.

3. **Spawn ICs in parallel for one structured pulse.** For each IC in `ic_ids`, the lead sends one short prompt via `Agent` tool:
   ```
   subject: "Department sync pulse — 60-second response please"
   prompt: |
     Did since last sync (1 line each, max 3): ...
     Doing this iteration (1 line, max 1): ...
     Blocked-on (1 line each, may be empty): ...
     One ask for the lead, if any (1 line, may be empty): ...

     Reply with the four sections in the order shown. No prose preamble. Be terse.
   ```
   ICs respond within their own iteration budget (the lead is essentially issuing a 1-iteration internal sub-delegation). Fanout is bounded by depth-cap 3 (CEO → lead → IC).

4. **Aggregate into dept-digest.** The lead collates the IC responses into a dept-digest with:
   - **Per-IC summary** (4 lines each)
   - **Cross-IC themes** (any topic mentioned by ≥ 2 ICs surfaces here)
   - **Open blockers** (deduplicated; lead's own assessment of severity)
   - **Asks for the lead** (lead can choose to handle inline or queue for later)
   - **Recommended CEO actions** (≤ 3 bullets; this is the value-add the dept lead provides over raw IC responses)

5. **Write the dept-digest.** Call `storage-broker` op=`put`:
   ```
   namespace: state/dept-digests/<dept_id>
   kind: dept-digest
   access_pattern: read-mostly
   durability: project
   human_legible: true
   body: { dept_id, lead_id, ts, ic_ids, per_ic_summaries, themes, blockers, asks, recommended_ceo_actions }
   ```
   Broker selects T1 markdown because `human_legible: true` (CEO will scan it).

6. **Lead writes one observation to their own memory.** Call `memory-write`:
   ```
   agent_id: <lead_id>
   memory_type: observation
   confidence: 0.80
   tags: [dept-sync, <dept_id>]
   source: "department-sync@<iso-ts>"
   content: |
     Synced <N> ICs in <dept_id>; <count> blockers, <count> asks.
     Top theme: <first cross-IC theme or "none observed">
     CEO actions recommended: <count>
   refs: [<dept_digest_ref>]
   ```

7. **Return one digest to `return_to`.** Single `memo-send severity=fyi` with the dept-digest ref. CEO consumes one memo per dept instead of spawning each IC individually.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: department-sync
STATUS: ok | partial | error
DEPT_ID: <id>
LEAD_ID: <id>
ICS_PULSED: <count>
ICS_RESPONDED: <count>
DEPT_DIGEST_REF: md://state/dept-digests/<dept_id>/<ts>.md
THEMES_SURFACED: <count>
BLOCKERS_OPEN: <count>
RECOMMENDED_CEO_ACTIONS: <count>
```

## Invariants

- **Lead is the aggregator, not a transcriber.** The dept-digest must add value beyond just concatenating IC responses — themes + recommended actions are the lead's contribution.
- **Pulse, not interrogation.** Each IC sees one prompt; if any IC needs deeper conversation, that's a 1:1, not part of dept-sync.
- **Single memo to CEO.** Multiple memos defeats the aggregation purpose; if the lead wants to escalate two distinct things, send one digest + one separate blocker memo.
- **Fanout cap honored.** Lead spawns ICs sequentially-but-fast, not all 5+ in a single message. Adheres to depth-3/fanout-5.

## Non-Goals

- Not a substitute for standup-log. Standups are continuous, fine-grained; dept-sync is a periodic snapshot.
- Not a 1:1. The four-section prompt is closed-form; coaching conversation is out of scope.
- Not a retrospective. Dept-sync is a pulse, not a pattern-mining session.
- Not for cross-dept syncs (yet). Multi-dept coordination is a committee, not a department-sync.

## Anti-patterns

- Never use department-sync to bypass standup-log. Standups feed memory-reflect; sync is for human (CEO) consumption.
- Never have the lead skip the aggregation step. Sending raw IC responses defeats the purpose.
- Never run department-sync from inside a committee. Committees have their own context-setting.
- Never fire dept-sync more than once per turn per dept. Pulse means snapshot; multiple snapshots is interrogation.

## Grounding

- `references/raci-assignment-protocol.md` — dept-lead role and the Accountable position they own.
- `skills/core/ceremony/standup-log/SKILL.md` — the continuous fine-grained source the dept-sync pre-read consumes.
- `skills/core/ceremony/one-on-one/SKILL.md` — the deeper coaching ceremony when an IC needs more than a pulse.
- `agents/kiho-ceo.md` LOOP step b (RACI assignment) — the depth/fanout pressure that motivates dept-sync.
