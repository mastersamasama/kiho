---
name: standup-log
description: Use this skill when any agent finishes an iteration and should record a standup entry describing what they did, what they are doing next, and any blockers. CEO invokes it once per turn per working agent as part of the Ralph loop; individual contributors also fire it at task completion. Writes a Tier-2 JSONL row to the weekly shard via storage-broker. Blockers additionally mirror into the owner lead's inbox via memo-send so the lead can unblock without waiting for the CEO digest. Standups feed memory-reflect (drift detection) and retrospective (systemic patterns). Standups are not committee-reviewable by default; they only surface to committee when retrospective promotes them.
argument-hint: "agent_id=<id> did=<list> blocked=<list>"
metadata:
  trust-tier: T2
  kiho:
    capability: create
    topic_tags: [coordination, reflection]
    data_classes: [observations]
---
# standup-log

Appends a structured standup row for a single agent-iteration pair. Standups are the finest-grained ceremony kiho runs: one line per agent per iteration, written via `storage-broker` to a weekly JSONL shard. They are the raw material that retrospective, memory-reflect, and the CEO digest all consume.

## Why a skill and not a free-text note

A standup is a **contract**: three fields (did / doing / blocked) every agent must fill in the same shape so downstream readers don't have to parse prose. Free-text reflections are what soul reflection writes; standups are what coordination reads. Keeping them separate means the CEO can scan a week of standups in seconds without an LLM pass.

Standups are Tier-2 processing artifacts — regenerable from agent memory and plan.md, never the source of truth for what happened. If the JSONL shard is lost, the next reflection pass rebuilds it from memory-query.

## Inputs

```
PAYLOAD:
  agent_id: <id>             # required — e.g., "eng-lead-01"
  iteration_id: <id>         # required — Ralph loop iteration, e.g., "turn-142.iter-03"
  did: [<bullet>, ...]       # required — what the agent completed this iteration
  doing: [<bullet>, ...]     # required — what the agent is doing next
  blocked: [<bullet>, ...]   # optional — blockers (empty list if none)
  asks: [<bullet>, ...]      # optional — questions for the lead or CEO
  ts: <iso>                  # optional — defaults to now
```

Each bullet is a one-line string, max ~160 chars. Longer content belongs in a memo or a reflection, not a standup.

## Procedure

1. **Shape validation.** Reject calls where `did` or `doing` is empty or where any bullet exceeds the length cap. Standups with no did-items are almost always a misfire (agent called before producing output); return `status: error reason=empty_did`.

2. **Resolve the weekly shard.** Compute ISO week as `<YYYY-WW>` from `ts`. Namespace is `state/standups/<YYYY-WW>`. This keeps shards bounded in line-count and cheap to scan.

3. **Write the standup row.** Call `storage-broker` op=`put`:
   ```
   OPERATION: put
   PAYLOAD:
     namespace: state/standups/<YYYY-WW>
     kind: standup
     access_pattern: append-only
     durability: project
     human_legible: false
     body:
       agent_id: <agent_id>
       iteration_id: <iteration_id>
       ts: <iso>
       did: [...]
       doing: [...]
       blocked: [...]
       asks: [...]
   ```
   Storage-broker selects JSONL for this shape (append-only, machine-consumed) and returns a ref of the form `jsonl://state/standups/2026-W16#L37`.

4. **Mirror blockers to the lead.** If `blocked` is non-empty, call `memo-send` once per blocker line:
   ```
   memo-send to=<dept-lead-for(agent_id)> severity=action
     subject: "Blocker from <agent_id> @ <iteration_id>"
     body: <blocker line, plus link to the standup ref>
   ```
   Dept-lead lookup uses `.kiho/state/org-registry.md`. If the agent is a dept lead, mirror to `ceo-01`. If no lead can be resolved, fall back to `ceo-01` and note `routed_to_ceo_fallback: true` in the response.

5. **Mirror asks to the lead at severity=fyi.** Same routing as blockers, but severity `fyi` — asks are softer than blockers and shouldn't page the lead.

6. **Write an observation to the agent's own memory (v5.20 Wave 2.1).** Call `memory-write` once with:
   ```
   agent_id: <agent_id>
   type: observation
   importance: 3            # baseline; bump to 7 if blocked is non-empty
   subject: "Standup @ <iteration_id>"
   body: "did=<n_did>; doing=<n_doing>; blocked=<n_blocked>"
   refs: [<STANDUP_REF>]
   ```
   This makes the standup discoverable from the agent's own memory tree (the JSONL shard alone is fine for coordination, but memory-reflect needs the per-agent observation stream to detect drift). On `memory-write` failure, log `memory_write_skipped: <reason>` in the response and continue — standup write is the contract; observation write is best-effort.

7. **Return the ref.** Response shape below. Do not emit telemetry beyond storage-broker's own; standups are already the telemetry.

## Shard rotation

- **Weekly rotation.** A new shard opens every Monday 00:00 in project timezone. The skill itself never closes shards — it just writes into whichever one the current ISO week resolves to. This keeps any single shard bounded at roughly `active_agents × 7 × iterations_per_day` rows, a size that `storage-broker` op=`query` can scan without pagination.
- **Eviction at 90 days.** A nightly ralph housekeeping pass (owned by retrospective, not this skill) deletes `state/standups/<YYYY-WW>` files older than 90 days after confirming they have been summarized into at least one retrospective artifact. Standups are raw material; the distilled version lives in Tier-1 retrospectives.
- **Do not compress mid-week.** Readers expect the current-week shard to be live-appendable. Compression happens only on rotation. If a reader needs aggregated historical standups, they query the retrospective namespace, not the archived JSONL.
- **Week boundary correctness.** An iteration that straddles midnight Sunday→Monday writes to the shard named after the `ts` field, not the one named after the iteration's start. Readers sort by `iteration_id` within the shard to recover order.

## Example row

A typical standup row looks like this (one JSONL line, pretty-printed for readability):

```json
{
  "agent_id": "eng-lead-01",
  "iteration_id": "turn-142.iter-03",
  "ts": "2026-04-18T14:22:07Z",
  "did": ["Wired storage-broker op=put into committee-agenda step 6"],
  "doing": ["Drafting eviction policy for state/actions shard"],
  "blocked": ["Need CEO ruling on whether 90d eviction applies to sev1 actions"],
  "asks": []
}
```

Downstream readers grep by `agent_id` for per-agent timelines, by `iteration_id` for cross-agent slices of a single Ralph iteration, or by non-empty `blocked` for the weekly blocker digest.

Empty-list fields are still emitted (`blocked: []`, `asks: []`) so readers never have to distinguish "missing" from "none".

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: standup-log
STATUS: ok | error
AGENT_ID: <id>
ITERATION_ID: <id>
STANDUP_REF: jsonl://state/standups/<YYYY-WW>#L<n>
BLOCKERS_MIRRORED:
  - memo_ref: memo://inbox/<lead>/<id>
    blocker: <line>
ASKS_MIRRORED:
  - memo_ref: memo://inbox/<lead>/<id>
    ask: <line>
NOTES: <optional, e.g., routed_to_ceo_fallback>
```

## Invariants

- **Not a status page.** Standups are not rendered for user eyes. The CEO digest is the user-facing summary; standups are its input.
- **Not user-facing.** Do not prompt the user, do not call `AskUserQuestion`, do not escalate. If an agent has a user-facing question it goes through the CEO escalation path, not a standup.
- **Append-only.** Never edit a prior standup row. Corrections go in the next iteration's `did` as "correction: ...".
- **One row per agent-iteration.** If called twice for the same `(agent_id, iteration_id)` pair, reject the second call with `status: error reason=duplicate`.
- **Blameless.** Blockers describe the situation, not the person who caused it. The retrospective linter re-checks this on promotion.

## Non-Goals

- Not a planning tool. `doing` is a one-line intent, not a plan; plan.md owns forward work.
- Not a performance review. agent-performance.jsonl is a separate stream with different fields and a different reader (capability matrix), not this one.
- Not a chat log. If two agents need to converse, that's memos or a committee session, not a standup.
- Not a metric. Standup counts are not KPIs; rewarding volume would destroy signal.

## Grounding

- `references/storage-architecture.md` — Tier-2 JSONL discipline and regenerability rules.
- `references/react-storage-doctrine.md` — why this skill picks storage-broker instead of writing directly.
- `skills/core/storage/storage-broker/SKILL.md` — the put op contract used in step 3.
- `skills/core/communication/memo-send/SKILL.md` — blocker and ask mirroring in steps 4 and 5.
- `references/org-tracking-protocol.md` — dept-lead resolution used for routing.
- `skills/core/ceremony/retrospective/SKILL.md` — the downstream consumer that promotes systemic patterns out of standups.
