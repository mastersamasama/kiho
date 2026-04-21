---
name: one-on-one
description: Use this skill when a department lead wants to hold a structured check-in with an IC they own. Produces a paired artifact with a shared_summary (CEO-visible) and private_notes_ref (lead-visible; CEO can still request on audit). Pulls the last N standup-log entries as pre-read to avoid re-litigating status. Action items surfaced during the check-in mirror into the actions JSONL and emit memos. Not a forced ceremony — leads invoke it before performance review or when an IC shows sustained perf drift. Not a surveillance mechanism; the private_notes field exists so leads can coach without the IC editing itself for committee readability.
argument-hint: "lead_id=<id> ic_id=<id>"
metadata:
  trust-tier: T2
  kiho:
    capability: communicate
    topic_tags: [coordination, reflection]
    data_classes: [observations]
---
# one-on-one

Runs a structured lead↔IC check-in and writes a paired artifact: a `shared_summary` the CEO can always read, and `private_notes` the lead uses to coach. "Private" here means visibility-defaulted, not encrypted — kiho keeps no true secrets from the CEO, and an audit request resolves the private notes on demand. The split exists so the IC isn't writing for a committee and the lead isn't writing for a filesystem grep.

## Why private ≠ hidden from CEO

If every coaching note were committee-grade, leads would either stop taking notes or launder them into uselessness. The private_notes half of the artifact is a soft partition: normal CEO digests filter it out, memory-reflect skips it, retrospective never promotes it. But `storage-broker` op=`read` with `audit_reason=<text>` will return it, and the audit is logged. That's enough surveillance for governance without turning every 1:1 into a deposition.

Check-ins are Tier-2 artifacts — the raw material, like standups. If the shard is lost, the reflection pass won't rebuild it (there's no other source); that's acceptable because 1:1s are ephemeral by design. The durable outputs are the action items, which mirror into `state/actions` and survive independently.

## Inputs

```
PAYLOAD:
  lead_id: <id>                # required — e.g., "eng-lead-01"
  ic_id: <id>                  # required — the IC being checked-in with
  topics: [<bullet>, ...]      # optional — agenda; if empty, pre-read drives it
  prev_checkin_ref: <ref>      # optional — previous 1:1 to resume threads from
  pre_read_weeks: <int>        # optional — default 2, standup weeks to pull
  ts: <iso>                    # optional — defaults to now
```

## Procedure

1. **Ownership check.** Resolve `.kiho/state/org-registry.md` — `lead_id` must actually own `ic_id`. If not, return `status: error reason=not_owner`. The CEO can always run 1:1s with any agent (ceo-01 shortcuts the ownership check).

2. **Pull pre-read.** Call `memory-query` (or `storage-broker` op=`query` on `state/standups/*`) for the last `pre_read_weeks` of standup rows where `agent_id == ic_id`. Extract a condensed bullet list: recent `did`, outstanding `blocked`, unanswered `asks`. This is the pre-read — leads should walk in knowing status, not rehash it. If `prev_checkin_ref` is set, pull that too and extract open action items.

3. **Conduct the check-in.** This skill does not script the conversation. The lead runs it, notes what was discussed, and returns two blocks to the skill call:
   - `shared_summary`: 3-8 bullets, written for CEO readability (what was discussed, what was decided, what's changing).
   - `private_notes`: free-form coaching text (tone, doubts, hypotheses about root causes, things the IC said the lead wants to remember). No format required.

4. **Write the paired artifact.** Call `storage-broker` op=`put`:
   ```
   namespace: state/oneonone/<lead_id>__<ic_id>
   kind: one-on-one
   access_pattern: append-only
   durability: project
   human_legible: true
   body:
     lead_id: <lead_id>
     ic_id: <ic_id>
     ts: <iso>
     pre_read_digest: [...]
     topics: [...]
     shared_summary: [...]
     private_notes_ref: <broker-written child ref, access-gated>
     action_items: [...]
   ```
   The broker writes `private_notes` to a sibling entry whose ACL defaults to lead_id + ceo-01-on-audit, and stores only the ref in the main artifact.

5. **Surface action items.** For each bullet in `action_items`, call `storage-broker` op=`put` to `state/actions` (kind=`action`) with owner, due iteration, source=`one-on-one`. Then `memo-send` severity=`fyi` to the action owner summarizing the item and linking the 1:1 ref. If the IC agreed to the action, the owner is the IC; if the lead committed to unblocking something, the owner is the lead.

6. **Write a coaching observation to the lead's own memory (v5.20 Wave 2.1).** Call `memory-write`:
   ```
   agent_id: <lead_id>
   type: observation
   importance: 5                  # bump to 8 if private_notes flagged a growth area
   subject: "1:1 with <ic_id> @ <ts>"
   body: |
     Topics: <comma-joined topic headlines>
     Action items: <count>
     Coaching note: <one-line distilled from private_notes; no quotes>
   refs: [<one_on_one_ref>]
   ```
   This grows the lead's own observation stream so quarterly retrospectives or performance-reviews (Wave 3.3) can spot patterns like "lead has logged 4 observations this quarter where ic-eng-02 struggled with async PR turnaround". The IC's memory is NOT written here — 1:1s are the lead's coaching journal, not the IC's record. Failure is best-effort; log `memory_write_skipped` and continue.

7. **Return the refs.** Response shape below.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: one-on-one
STATUS: ok | error
LEAD_ID: <id>
IC_ID: <id>
CHECKIN_REF: md://state/oneonone/<lead>__<ic>/<iso>.md
PRIVATE_NOTES_REF: <access-gated ref>
PRE_READ_BULLETS: <int count>
ACTION_ITEMS_RECORDED:
  - action_ref: jsonl://state/actions#L<n>
    owner: <agent_id>
    due_iteration: <id>
    line: <text>
MEMOS_SENT:
  - memo_ref: memo://inbox/<owner>/<id>
NOTES: <optional>
```

## Audit path

If the CEO needs the private notes (performance review, conflict escalation, policy question), they call `storage-broker` op=`read` with:
```
ref: <private_notes_ref>
audit_reason: <one-line why>
```
The broker logs the audit access to `state/audit/oneonone-reads.jsonl` (Tier-2, CEO-readable) and returns the content. The lead is notified via `memo-send` severity=`fyi` that an audit read happened and why. This keeps the private tier honest without making it a true secret.

## Invariants

- **Not user-facing.** ICs are agents, not users. Do not call `AskUserQuestion`. If the 1:1 surfaces something that needs the real user's input, the lead escalates via CEO in the normal way.
- **Private notes are CEO-visible on audit.** Never promise the IC or the lead that private notes are encrypted, sealed, or irrecoverable — they aren't. The skill's description says so; the artifact's `private_notes_ref` header repeats it.
- **Action items leave the ceremony.** If an action item stays only in the 1:1 and never hits `state/actions`, it effectively didn't happen. Step 5 is non-skippable.
- **Not used for performance review scoring.** agent-performance.jsonl is the input to capability-matrix. 1:1s are coaching, not measurement. Conflating the two incentivizes dishonest notes.
- **Ownership gate.** Only the IC's direct lead (or ceo-01) may run this skill. Cross-department fishing trips go through agent-promote cross_train or a committee, not a 1:1.

## Non-Goals

- Not a surveillance tool. The private_notes field exists so leads can be candid, not so CEOs can scrape sentiment.
- Not a performance review. perf review is a separate ceremony with different artifacts.
- Not a chat log. If the content is long-form dialog, the lead summarizes it; the skill stores the summary, not the transcript.
- Not a planning tool. plan.md owns forward work; 1:1s surface actions that flow into plan.md, they don't replace it.
- Not user-initiated. Only leads (and ceo-01) trigger this; ICs cannot demand a 1:1 via this skill — that's a memo to the lead.

## Grounding

- `references/storage-architecture.md` — Tier-2 discipline and the regenerability exception for 1:1 artifacts.
- `references/react-storage-doctrine.md` — why this skill goes through storage-broker instead of writing raw.
- `skills/core/storage/storage-broker/SKILL.md` — the put/read op contracts used in steps 4 and audit.
- `skills/core/ceremony/standup-log/SKILL.md` — the pre-read source in step 2.
- `skills/core/communication/memo-send/SKILL.md` — action-item notification in step 5.
- `references/org-tracking-protocol.md` — ownership lookup in step 1.
