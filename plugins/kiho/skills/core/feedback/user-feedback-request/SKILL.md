---
name: user-feedback-request
description: Use this skill to propose a user-facing feedback prompt that the CEO will embed in its next response. Only the CEO may author user prompts; sub-agents write to the feedback request queue and CEO consumes at loop start, deciding whether and how to surface each request. Prompts are rate-limited to avoid survey fatigue — at most one per N accepted turns, or after a sev1 incident closure, or at CEO discretion. Records user responses to the feedback response JSONL for later analysis by memory-reflect. Does not itself call AskUserQuestion — CEO's Ralph loop does, using this skill's output as the draft.
argument-hint: "turn_id=<id> question_set=<nps|helpful|specific>"
metadata:
  trust-tier: T2
  kiho:
    capability: communicate
    topic_tags: [coordination, reflection]
    data_classes: ["feedback-queue"]
---
# user-feedback-request

A queue for feedback prompts. Sub-agents write proposed user questions into a JSONL; the CEO drains the queue at loop start, applies the rate-limiter, and embeds at most one prompt into the current response. The skill exists to preserve the CEO-only user-funnel invariant while still letting sub-agents (who actually know when a prompt would be useful) originate the content.

## Why not just call `AskUserQuestion`

Because sub-agents aren't allowed to. Full stop. The CEO-only funnel is load-bearing for four reasons: (1) the user trusts one voice, not twelve; (2) rate-limiting is trivial with one caller and impossible with many; (3) survey fatigue kills every multi-agent system that lets each agent ping the user; (4) the CEO's context is the only place that knows what question is most valuable to ask right now. This skill gives sub-agents a write-only mailbox into the CEO's decision-making without violating the invariant.

## Inputs

```
PAYLOAD:
  turn_id: <id>                     # required — ralph turn the request belongs to
  question_set: nps | helpful | specific   # required
  context_ref: <ref>                # required — what prompted the request
  requester_agent: <agent_id>       # required — who is asking
  proposed_question: <string>       # required for question_set=specific
  priority: routine | post_incident # optional — post_incident bypasses rate limit
  incident_ref: <ref>               # required if priority=post_incident
```

Question sets:
- `nps`: "On a 0–10 scale, how likely are you to recommend kiho to a colleague?" + one free-text follow-up.
- `helpful`: "Was the last response helpful? If not, what should it have done differently?"
- `specific`: uses `proposed_question` verbatim (CEO may still edit).

## Procedure

### Sub-agent write path

1. **Validate inputs.** `context_ref` must resolve. For `question_set=specific`, `proposed_question` must be non-empty and ≤ 240 chars (longer = the sub-agent is sneaking work into a feedback prompt; reject).

2. **Enqueue.** Call `storage-broker` op=`put`:
   ```
   namespace: state/feedback/requests
   kind: feedback-request
   access_pattern: append-only
   durability: project
   human_legible: false
   body:
     request_id: <uuid>
     turn_id: <turn_id>
     question_set: <nps|helpful|specific>
     proposed_question: <string-or-null>
     context_ref: <ref>
     requester_agent: <agent_id>
     priority: <routine|post_incident>
     incident_ref: <ref-or-null>
     ts: <iso>
     status: pending
   ```

3. **Return the ref.** Sub-agent gets a queue position, not a user answer. Response shape below.

### CEO drain path

At the start of each Ralph iteration, the CEO:

1. **Query the queue.** `storage-broker` op=`query` on `state/feedback/requests` where `status=pending`.

2. **Apply the rate limit.** Read `state/feedback/rate-limiter.yaml`. The default policy is "at most 1 feedback prompt per N accepted turns where N=5" plus "at most 1 per 24h" plus "always allow priority=post_incident once per incident_ref." If the limiter forbids surfacing now, leave all `pending` rows and skip step 3.

3. **Pick one.** Order: all `post_incident` first (FIFO by incident_ref), then `specific` (FIFO), then `helpful` (FIFO), then `nps` (FIFO). CEO selects the first eligible one and may edit the wording — the proposed_question is a draft, not a contract.

4. **Embed in the response.** CEO calls `AskUserQuestion` as part of its own turn. This skill does not call it; the CEO does. The question text and its source `request_id` are both included so the user sees a coherent ask.

5. **Record the response.** After the user replies, the CEO writes:
   ```
   storage-broker put
     namespace: state/feedback/responses
     kind: feedback-response
     body:
       request_id: <matching>
       turn_id: <turn_id>
       question_asked: <final-wording>
       user_response: <verbatim>
       ts: <iso>
   ```
   Then update the original request row's status to `answered` via a matching append (never edit the prior row — JSONL is append-only; `storage-broker` models updates as replacement rows with the same `request_id`).

6. **Notify the requester.** `memo-send` severity=`fyi` to the sub-agent that originated the request, linking the response. Closes the loop without forcing the sub-agent to poll.

## Rate limit

- Default `N=5` accepted turns between prompts.
- Default `cooldown_h=24` hours between prompts regardless of turn count.
- `post_incident` priority bypasses both, but is itself capped at one prompt per `incident_ref`.
- All three numbers live in `state/feedback/rate-limiter.yaml` so the CEO can tune them without code changes.
- The rate limit is enforced by the CEO drain path only — the write path will always accept the enqueue. This keeps sub-agents simple.

## Response shape

### Sub-agent enqueue response

```markdown
## Receipt <REQUEST_ID>
OPERATION: user-feedback-request
STATUS: ok | error
REQUEST_REF: jsonl://state/feedback/requests#L<n>
QUEUE_POSITION: <int>
NOTES: <optional — e.g., "rate-limiter currently blocking; CEO will drain when window opens">
```

### CEO drain response (internal)

```markdown
## Receipt <REQUEST_ID>
OPERATION: user-feedback-request.drain
STATUS: ok | deferred
SELECTED_REQUEST_REF: <ref-or-null>
RATE_LIMIT_DECISION: allow | defer_n_turns | defer_cooldown
```

## Invariants

- **Sub-agents NEVER call `AskUserQuestion`.** Not via this skill, not via any other. This is the CEO-only user funnel invariant and it is non-bypassable.
- **Rate limit is enforced at drain, not at enqueue.** A backed-up queue is fine; a spammed user is not.
- **User response is recorded before the memo-notify.** If the response write fails, don't notify — the sub-agent would otherwise chase a ghost.
- **No silent editing.** If the CEO edits the `proposed_question`, the response row records both the proposed and the final wording. Sub-agents reading their own feedback results need to see what the user actually heard.
- **Post-incident bypass is per-incident, not blanket.** A sev1 doesn't unlock every queued nps prompt.

## Non-Goals

- Not a polling service. This skill does not schedule recurring prompts; it responds to events.
- Not a notification mechanism. If the CEO wants to tell the user something (not ask), that's just the CEO's normal output — no queue needed.
- Not a ticketing system. Sub-agents don't track feedback themselves; memory-reflect reads the response JSONL on its own cadence.
- Not a per-user routing system. kiho is single-user by charter; the queue has one audience.
- Not a replacement for memos. Agent-to-agent questions go through `memo-send`, not through the user.

## Grounding

- `references/storage-architecture.md` — Tier-2 append-only discipline for the request/response streams.
- `references/react-storage-doctrine.md` — storage-broker mediation for both streams.
- `skills/core/storage/storage-broker/SKILL.md` — put/query contracts used in enqueue and drain.
- `skills/core/communication/memo-send/SKILL.md` — requester notification in drain step 6.
- `agents/kiho-ceo.md` — the CEO persona that owns the drain path and the `AskUserQuestion` call.
- `references/ralph-loop-philosophy.md` — "loop start" semantics for the drain pass.
