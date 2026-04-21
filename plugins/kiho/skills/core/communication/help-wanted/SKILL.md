---
name: help-wanted
description: Use this skill when an agent is stuck on a sub-problem and wants peer help without escalating to CEO. Broadcasts a structured help request to peers whose capability-matrix proficiency in the relevant skill is >= 3. Peers can claim the request (taking on a 1-iteration assist) or signal interest (defer to CEO if no claim within N iterations). Avoids the failure mode where every blocker walks the CEO escalation path. Triggers on "help wanted", "ask the team", "is anyone good at X", or when an agent's working memory shows it has retried the same sub-step twice without progress. Reads capability-matrix to filter recipients; writes to peer inboxes via memo-send severity=action with claim/decline metadata.
metadata:
  trust-tier: T2
  kiho:
    capability: communicate
    topic_tags: [coordination, ingestion]
    data_classes: [capability-matrix]
---
# help-wanted

The soft-escalation channel. Memo-send goes to one recipient with severity; help-wanted broadcasts to a filtered peer set so the *first available* expert claims the work. No CEO involved unless nobody claims within the timeout.

## When to use

- Agent has retried the same sub-step twice with no progress AND a different agent has higher capability-matrix proficiency for that skill
- Cross-cutting question that would page the CEO unnecessarily ("does anyone know the OAuth provider's deprecation policy?")
- Pair-up request that doesn't need full pair-request scaffolding ("anyone want to spot-check this regex?")

Do **NOT** invoke when:

- It's a real blocker — use `memo-send severity=blocker` direct to dept lead
- The user is waiting — escalate to CEO via standard return path
- You haven't tried capability-matrix lookup first — pinging the *right* one peer is cheaper than broadcasting

## Inputs

```
topic: <one-line subject>                    # required
context: <2-5 sentences>                      # required
required_skill: <sk-XXX or skill-name>        # required for capability filter
required_proficiency: <1-5>                   # default 3
urgency: now | this-turn | this-session       # default this-turn
claim_deadline_iterations: <int>              # default 3
exclude_agents: [<id>, ...]                   # optional; the requester is auto-excluded
```

## Procedure

1. **Filter recipients via capability-matrix.** Read `.kiho/state/capability-matrix.md`. Build the recipient list from agents whose proficiency in `required_skill` is >= `required_proficiency`. Subtract `exclude_agents` and the requester. If the resulting list is empty, fall back to the dept lead of `required_skill`'s primary owner-dept; if that also yields nothing, escalate to CEO with `escalate_to_user: false, reason: no_qualified_peer`.

2. **Compose the help-wanted memo body** (one memo, sent to all recipients):
   ```
   subject: "Help wanted: <topic>"
   body: |
     Requester: <agent_id>
     Required skill: <required_skill> (min proficiency <N>)
     Urgency: <urgency>
     Claim deadline: iteration <current+claim_deadline_iterations>

     Context:
     <context>

     To claim: reply with "help-wanted-claim cycle=<cycle_id>" via memo-send.
     To decline: ignore (silent decline is fine).
   ```

3. **Send via memo-send, severity=action.** One memo per recipient (so each inbox shows it independently). Use `severity=action` because peers should look at it within the urgency window.

4. **Open a help-wanted cycle** at `state/help-wanted/<cycle_id>.json` (T2 JSONL via storage-broker):
   ```json
   {
     "cycle_id": "hw-<short-uuid>",
     "ts": "<iso>",
     "requester": "<agent_id>",
     "topic": "<topic>",
     "required_skill": "<sk-XXX>",
     "required_proficiency": <N>,
     "recipients": ["<id>", ...],
     "urgency": "<urgency>",
     "claim_deadline_iteration": <int>,
     "claimed_by": null,
     "claimed_at": null,
     "outcome": "open"
   }
   ```

5. **Wait for claim OR deadline.** The CEO loop, on each iteration, polls `state/help-wanted/<cycle_id>.json`:
   - If a peer replied with `help-wanted-claim`, mark `claimed_by` and `claimed_at`, mark `outcome: claimed`, and pair the requester with the claimer for the next iteration
   - If the deadline passes with no claim, mark `outcome: timed_out`, escalate to CEO with `escalate_to_user: true, reason: no_claim_in_window` so the CEO can decide between (a) reframe the problem, (b) direct memo-send blocker to a specific lead, (c) ASK_USER

6. **Return cycle ref.** Response shape below.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: help-wanted
STATUS: ok | escalated | error
CYCLE_ID: hw-<id>
RECIPIENTS_COUNT: <N>
RECIPIENTS: [<id>, ...]   # truncated to 5 in human view
DEADLINE_ITERATION: <int>
CYCLE_REF: jsonl://state/help-wanted/<cycle_id>
NEXT_ACTION: "Wait for claim or deadline; CEO polls each iteration"
```

## Invariants

- **Peer broadcast, not CEO escalation.** If you find yourself wanting to add the CEO to the recipient list, you don't have a help-wanted, you have a blocker — use `memo-send severity=blocker`.
- **Claim is binding for one iteration.** A peer who claims commits to one iteration of help. Beyond that, a `pair-request` is the right tool.
- **Deadline timeout is informational, not punitive.** No-claim is signal that the org doesn't have the capability — a recruit gap. CEO logs this to feed `recruit` agenda.
- **No anonymous broadcasts.** Requester is always named so peers can decide based on relationship + context.

## Non-Goals

- Not a chat room. One topic, one memo, one cycle. If a thread of conversation is needed, hand off to `pair-request`.
- Not a status board. The cycle JSONL is operational state, not a public dashboard.
- Not a survey. Yes/no/maybe is not the protocol — claim or decline.
- Not a substitute for `research`. Knowledge questions go through the research cascade (KB → web → ...).

## Anti-patterns

- Never broadcast with `required_proficiency: 1`. That defeats the filter — half the org will get the memo. Pick a meaningful threshold.
- Never re-broadcast the same cycle. A timed-out cycle should escalate or close, not loop.
- Never claim and then silently abandon. Honored claims feed capability-matrix updates; abandoned ones poison the org's trust in help-wanted.
- Never open a cycle from inside a committee. Committees have their own escalation; help-wanted is for IC-level peer support.

## Grounding

- `references/raci-assignment-protocol.md` — peer-as-Consulted role pattern, complement to formal RACI.
- `skills/core/communication/memo-send/SKILL.md` — the underlying delivery mechanism.
- `references/data-storage-matrix.md` row `capability-matrix` — the filter source.
- `skills/core/communication/pair-request/SKILL.md` — the heavier-weight follow-up when help-wanted reveals a multi-iteration collab.
