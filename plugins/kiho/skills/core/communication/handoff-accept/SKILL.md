---
name: handoff-accept
description: Use this skill whenever a sub-agent receives a delegation brief from the CEO or a dept lead and MUST emit an acknowledgement receipt before starting work. Records understood summary, ETA in iterations, confidence, accept/conditional/reject decision, and any open questions into the turn's receipts JSONL via storage-broker. The receipt is what the CEO reads at loop boundaries to confirm a delegated task is actually picked up; without a receipt the CEO does not count the task as in-flight. Never use this skill without a brief ID — it is the only input that threads a receipt back to its brief.
argument-hint: "brief_id=<id> accept=<true|conditional|reject> eta_iterations=<n>"
metadata:
  trust-tier: T2
  kiho:
    capability: communicate
    topic_tags: [coordination]
    data_classes: ["handoff-receipts"]
---
# handoff-accept

The one-shot acknowledgement ceremony that a sub-agent MUST perform before starting delegated work. Prevents silent drop of delegated work: the CEO's loop-boundary scan counts a task as in-flight only when a matching receipt exists on disk, so an agent that skips this skill is — from the CEO's point of view — not working on anything at all. A receipt is intentionally a single file-write, not an agent spawn and not a status channel; it names what the agent thinks the brief says, when the agent expects to be done, how confident the agent is, and whether the agent accepts the task.

## Why a receipt at all

A delegated brief is a contract between two agents who cannot see each other's working memory. Without an explicit receipt, the CEO cannot tell apart three indistinguishable failure modes: the sub-agent never received the brief, the sub-agent received it but misread the scope, or the sub-agent is quietly working with a different mental model than the CEO wrote. The receipt collapses all three into a single signal — either the brief was understood and accepted on the record, or it wasn't — and makes silent drift impossible to hide behind "I was going to".

## Inputs

```
PAYLOAD:
  brief_id: <id — matches a ledger row or state/briefs/<id>.md>
  agent_id: <soul id of the receiving agent, e.g. dept-eng-01>
  understood_summary: <2-4 sentences; the agent's own words>
  eta_iterations: <integer; how many Ralph iterations until done>
  confidence: <0..1; agent's self-rating on completing as scoped>
  open_questions: [<free-text questions, empty list if none>]
  accept: true | conditional | reject
  conditions: <free-text; required when accept=conditional, else empty>
  reject_reason: <free-text; required when accept=reject, else empty>
```

`brief_id` is mandatory — it is the only field that threads a receipt back to the originating brief. A receipt without a resolvable `brief_id` is an ERR (see response shapes).

## Procedure

### Step 1 — Resolve the brief

Locate the brief the CEO (or dept lead) handed you. Briefs live in one of two places:

- `.kiho/state/ceo-ledger.md` — the CEO's active ledger; each row has a `brief_id` column.
- `.kiho/state/briefs/<brief_id>.md` — standalone brief file when the ledger row pointed out-of-band.

Read the brief. If neither source contains `<brief_id>`, return `status: err, reason: brief_not_found`. Do **not** fabricate a summary — a receipt against an unknown brief is worse than no receipt at all.

### Step 2 — Construct the receipt dict

Build the dict verbatim from inputs; do not paraphrase the summary after the agent wrote it:

```
receipt = {
  "brief_id": <brief_id>,
  "agent_id": <agent_id>,
  "turn_id": <from session-context>,
  "received_at": <iso-8601 utc>,
  "understood_summary": <verbatim from input>,
  "eta_iterations": <int>,
  "confidence": <float>,
  "open_questions": [<strings>],
  "accept": "true" | "conditional" | "reject",
  "conditions": <str or null>,
  "reject_reason": <str or null>,
}
```

Validation before write:
- `0 <= confidence <= 1`
- `eta_iterations >= 1`
- `accept=conditional` requires non-empty `conditions`
- `accept=reject` requires non-empty `reject_reason`
- `understood_summary` is non-empty

### Step 3 — Put via storage-broker

Call `storage-broker` once:

```
OPERATION: put
PAYLOAD:
  namespace: state/receipts/<turn_id>
  kind: receipt
  access_pattern: append-only
  durability: session    # turn-scope; broker evicts at turn end
  key: <brief_id>        # idempotency key
  row: <receipt dict as JSON>
```

The broker handles JSONL append to `<project>/.kiho/state/receipts/<turn_id>.jsonl` and returns a `Ref`. Do not write the file directly — the broker owns the path and eviction policy.

### Step 4 — Return the Ref

Return the `Ref` in the response shape below. The Ref is what downstream skills (e.g. the CEO's loop-boundary scan) dereference to confirm this task is in-flight.

### Step 5 — Proceed only if accepted

- `accept: true` — proceed with the delegated work immediately.
- `accept: conditional` — stop. The CEO must read the conditions at the next loop boundary and either relax them, adjust scope, or cancel. Do not begin work that depends on conditions the CEO hasn't seen.
- `accept: reject` — stop. The receipt is on file; the CEO will redelegate. Do not attempt a partial version.

## Response shapes

**OK:**

```markdown
## Receipt <REQUEST_ID>
OPERATION: handoff-accept
STATUS: ok
BRIEF_ID: <brief_id>
AGENT_ID: <agent_id>
ACCEPT: true | conditional | reject
ETA_ITERATIONS: <n>
CONFIDENCE: <0..1>
RECEIPT_REF: <broker Ref string>
NOTES: <optional>
```

**ERR — brief not resolvable:**

```markdown
## Receipt <REQUEST_ID>
OPERATION: handoff-accept
STATUS: err
REASON: brief_not_found
BRIEF_ID: <brief_id>
CHECKED: [state/ceo-ledger.md, state/briefs/<brief_id>.md]
```

**ERR — receipt already exists (idempotency):**

Re-emitting a receipt for the same `brief_id` in the same `turn_id` is a **no-op**, not an overwrite. The broker returns the existing Ref and this skill surfaces it:

```markdown
## Receipt <REQUEST_ID>
OPERATION: handoff-accept
STATUS: ok
BRIEF_ID: <brief_id>
ACCEPT: <from stored receipt>
RECEIPT_REF: <existing broker Ref>
NOTES: idempotent — receipt already on file for this brief_id
```

## Invariants

- A receipt is a **file-write, not an agent spawn**. Depth-3 and fanout-5 caps do not apply; a sub-agent emitting a receipt is not "going deeper".
- Receipts are **Tier-2 processing artifacts**, append-only JSONL, one row per receipt, one file per `turn_id`.
- Receipts **auto-expire at turn end**. The storage-broker's `durability: session` policy evicts `state/receipts/<turn_id>.jsonl` when the turn closes — do not read stale files across turns.
- Receipts are **not committee-reviewable**. They are ephemeral coordination metadata, not blessed canonical state.
- Idempotency is by `(brief_id, turn_id)`. Re-calling this skill with the same pair returns the existing Ref unchanged.
- `accept: reject` **forces the CEO to redelegate** — there is no retry-in-place. The rejecting agent does not own the task anymore.
- The `understood_summary` is the agent's own words. Do not copy the brief's prose verbatim — the whole point is to surface misreadings early.

## Non-Goals

- **Not a status update channel.** Mid-task progress, "I'm 60% done", "ran into issue X" — use `memo-send` for that. A receipt is one-shot at the start of work, never amended.
- **Not a progress report.** `eta_iterations` is a commitment at receipt time, not a running estimate. If the estimate changes materially, send a `memo-send` with the new number; do not re-emit a receipt.
- **Not a blocker escalation.** If you hit a blocker mid-task, escalate via the normal CEO-bound path (structured `escalate_to_user` output). A rejected receipt at accept time is not the same as a blocker discovered during execution.
- **Not a task-state database.** Receipts are append-only and turn-scoped. They answer "was this brief picked up in this turn?", not "what is the task doing right now?".

## Grounding

- `skills/core/storage/storage-broker/SKILL.md` — the `put` operation, `append-only` access pattern, and `session` durability tier used here.
- `references/react-storage-doctrine.md` — why receipts are Tier-2 JSONL with per-turn eviction rather than Tier-1 markdown or Tier-3 sqlite.
