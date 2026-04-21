---
name: values-flag
description: Use this skill as the only path for soul or red-line conflicts. Fires when an agent's brief would require action that clashes with its soul red_lines or values, when committee deliberation stalemates on a values axis, or when two agents with incompatible red_lines are assigned to the same task. Produces a Tier-1 markdown ruling signed by the CEO after committee advisory input. May trigger soul-apply-override if the resolution involves mutating a soul clause; in that case the user-accept gate is non-bypassable. Substance committees resolve business decisions, not value conflicts — route value clashes here instead to preserve soul auditability.
argument-hint: "agent_id=<id> conflict_summary=<text>"
metadata:
  trust-tier: T2
  kiho:
    capability: decide
    topic_tags: [governance, reflection]
    data_classes: ["values-flags"]
---
# values-flag

The **only** path for soul and red-line conflicts in kiho. Substance committees decide what to build; values-flag decides what an agent is permitted to be asked to build.

## Contents
- [Why values ≠ substance](#why-values--substance)
- [Inputs](#inputs)
- [Procedure](#procedure)
- [Ruling structure](#ruling-structure)
- [Response shapes](#response-shapes)
- [Invariants](#invariants)
- [Non-Goals](#non-goals)
- [Grounding](#grounding)

## Why values ≠ substance

A substance committee weighs trade-offs against a goal — cost vs. latency, scope vs. deadline. A values conflict is different: the agent's soul says "never", the brief says "now". There is no optimization to compute; there is only a ruling to make and a soul to either uphold or mutate. Routing this through a substance committee is category-confused: the committee resolves, the ruling evaporates, and next week the same clash re-appears with no paper trail on the soul itself.

Every values-flag call produces a **named Tier-1 ruling** the soul document can point back to. When `soul-apply-override` is later asked to mutate a clause, it cites the ruling ID. This is how kiho preserves soul auditability across reflections.

## Inputs

```
PAYLOAD:
  agent_id: <id of the agent whose soul is in tension>
  conflict_summary: <1-2 sentence plain-language description>
  soul_clause_ref: <path + section heading into the agent's soul document>
  brief_ref: <path to the delegation brief, or plan.md task row>
  proposed_resolutions: [<text>, ...]  # optional caller-drafted candidates
  severity: block | warn  # default block; warn only if agent can proceed with a note
```

`soul_clause_ref` is mandatory — a values-flag without a specific clause anchor is a complaint, not a conflict.

## Procedure

1. **Load** — fetch the named soul clause and the brief. Verify the clause text matches what the caller summarized; if the caller misread their own soul, return `status: ambiguous_clause` and ask them to re-quote.
2. **Convene advisory committee** — call the `committee` skill in **advisory mode** (`role: advisory`, not `role: decision`). The committee reviews the clause, the brief, and the proposed resolutions, then returns a non-binding recommendation with dissent notes. Advisory committees do not vote to close; they produce input for the CEO.
3. **CEO reads and rules** — the CEO is the sole signer. Ruling body is drafted in markdown and persisted via the broker:
   ```
   storage-broker.put(
     namespace="state/values-conflicts",
     kind="values-flag",
     human_legible=True,
     body=<ruling markdown>
   )
   ```
   The reviewable-kind guardrail forces Tier-1 md — the broker refuses any other tier for `values-flag`.
4. **Soul mutation gate** — if `soul_mutation_required: true`, queue a `soul-apply-override` call with the ruling ID as evidence. The user-accept gate is **non-bypassable**; the CEO surfaces the proposed clause change to the user and waits for explicit accept before `soul-apply-override` fires.
5. **Memo** — emit a memo via `comms-memo-send` to the affected agent(s) with `severity=action` and the ruling ID. The agent's next delegation brief carries the ruling as prior context.

## Ruling structure

Every ruling is a single markdown file with this shape:

```markdown
---
ruling_id: vf-2026-04-19-0001
agent_id: eng-lead-01
soul_clause_ref: agents/eng-lead-01.md#red_lines.no-midnight-deploys
brief_ref: .kiho/state/plans/2026-04-19.md#task-7
ceo_signed: ceo-01
ceo_signed_at: 2026-04-19T23:14:00Z
soul_mutation_required: false
---
# Values ruling vf-2026-04-19-0001

## Conflict
<one paragraph: what the brief asked, what the soul says>

## Advisory summary
<2-4 bullets from the committee; dissents named>

## CEO decision
<the ruling in the CEO's voice — "uphold", "narrow", "mutate", or "recuse">

## Consequences
- Brief change: <what changes in the brief, if anything>
- Soul change: <clause mutation or "none">
- Precedent: <whether this ruling sets precedent for future clashes>
```

Four ruling modes:

- **uphold** — soul wins, brief is narrowed or rejected. No soul mutation.
- **narrow** — soul clause is clarified (not weakened) to resolve the ambiguity. Counts as a soul mutation; gate applies.
- **mutate** — soul clause is rewritten. Gate applies; user-accept required.
- **recuse** — the agent is re-assigned. Soul unchanged. Second agent picked by capability-matrix.

## Response shapes

```markdown
## Receipt <REQUEST_ID>
OPERATION: values-flag
STATUS: ruled | ambiguous_clause | awaiting_user_accept | error
RULING_ID: vf-2026-04-19-0001
RULING_MODE: uphold | narrow | mutate | recuse
SOUL_MUTATION_REQUIRED: <bool>
RULING_PATH: .kiho/state/values-conflicts/vf-2026-04-19-0001.md
MEMO_IDS:
  - <id emitted to affected agent(s)>
NOTES: <e.g. "user-accept queued; soul-apply-override will fire on accept">
```

Awaiting-user-accept shape:

```markdown
## Receipt <REQUEST_ID>
OPERATION: values-flag
STATUS: awaiting_user_accept
RULING_ID: vf-2026-04-19-0001
PROPOSED_CLAUSE_DIFF: |
  <unified diff the user will be shown>
USER_QUESTION: |
  <exact text the CEO will pass to AskUserQuestion>
```

## Invariants

- **Tier-1 md forced.** `values-flag` is on the reviewable-kind list; broker refuses jsonl/sqlite/mem.
- **User-accept for soul mutations.** No CEO ruling can mutate a soul clause without explicit user accept at the `/kiho` loop boundary.
- **Advisory committee cannot be skipped.** Even a confidence-1.0 CEO intuition must collect advisory input; the minutes become part of the ruling's provenance.
- **One ruling per conflict.** Idempotent on `(agent_id, soul_clause_ref, brief_ref)` — re-calls update the existing ruling, never duplicate.
- **CEO-only signer.** Department leaders may draft; only `ceo-01` signs.

## Non-Goals

- **Not a substance decision tool.** "Should we deploy at noon or 6pm" is substance — route to the substance committee, not here.
- **Not a performance review.** An agent repeatedly hitting values-flag is a soul-design concern, not a discipline matter. Escalate to soul-reflect, not to HR-style review.
- **Not a user veto channel.** The user is consulted only when soul mutation is proposed; users cannot force a values-flag ruling from outside the loop.

## Grounding

- `references/soul-architecture.md` — soul clause anatomy, red-line semantics
- `references/committee-rules.md` — advisory vs. decision modes
- `references/react-storage-doctrine.md` — reviewable-kind guardrail forcing Tier-1 md
- `references/storage-architecture.md` — Tier-1 canonical state
- `skills/memory/memory-reflect/SKILL.md` — the upstream surface that often detects a latent values clash
- `skills/core/harness/soul-apply-override/SKILL.md` — the downstream mutator this skill queues
