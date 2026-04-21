---
name: memo-send
description: Use this skill when any sub-agent finishes work and wants to drop a note in another agent's inbox without requiring the CEO to spawn a new delegation. Covers "FYI I discovered X", "heads-up the API changed", or "I'm blocked on your decision" style communications. Writes a JSONL row to the recipient's inbox via storage-broker. Severity=blocker memos are also mirrored into the committee-visible blockers markdown. CEO reads all inboxes at loop start through memo-inbox-read — memo-send is file-write only, never an agent spawn, so depth and fanout caps do not apply. Use when you need async peer-to-peer notification that outlives the current task but does not require immediate CEO attention.
argument-hint: "to_agent=<id> subject=<text> severity=<info|action|blocker>"
metadata:
  trust-tier: T2
  kiho:
    capability: communicate
    topic_tags: [coordination]
    data_classes: ["memo-inbox"]
---
# memo-send

The async peer-to-peer channel for kiho sub-agents. kiho forbids sub-agents from spawning other agents or talking to the user, but real work constantly surfaces findings relevant to a peer the CEO did not explicitly route. Previously that signal was either silently dropped or shoe-horned into a return payload the CEO had to manually re-dispatch. `memo-send` gives every agent a write-only file channel into any other agent's inbox, read lazily at loop boundaries by `memo-inbox-read`.

## Why a file-backed inbox

A message bus would require a daemon kiho does not run. A return-payload convention would force the CEO to triage every stray observation. A markdown pile would make digesting N memos per loop O(n) token cost. File-per-recipient JSONL via `storage-broker` gets the three properties that matter: durable across turns, cheap to append, cheap to scan and group. Blocker memos pay a small extra cost — an additional md mirror — so the committee sees them without scraping inbox jsonl.

## Inputs

```
PAYLOAD:
  from_agent:       <agent slug of the sender — required>
  to_agent:         <agent slug of the recipient — required>
  subject:          <one-line summary, <= 80 chars>
  body_md:          <markdown body; findings, context, links>
  severity:         info | action | blocker (default: info)
  task_ref:         <optional; plan.md task id or ceo-ledger entry id>
  ttl_iterations:   <optional int; default 10; broker evicts after N CEO loops>
```

## Procedure

1. Validate inputs. Reject if `from_agent == to_agent` (no self-memos — use scratch notes instead). Reject if `severity` is not in the three-value enum.
2. Call `storage-broker` op=`put`:

   ```
   OP: put
   namespace:       state/inbox/<to_agent>
   kind:            memo
   payload:
     from_agent:    <from_agent>
     to_agent:      <to_agent>
     subject:       <subject>
     severity:      <severity>
     task_ref:      <task_ref or null>
     ttl_iterations: <ttl_iterations>
     created_at:    <iso>
   body:            <body_md>
   access_pattern:  append-only
   durability:      project
   scope:           project
   owner:           <from_agent>
   ```

   The broker resolves tier to **jsonl** (append-only, non-reviewable kind) and returns a `Ref` pointing at `<project>/.kiho/state/inbox/<to_agent>.jsonl`.

3. If `severity == blocker`, additionally call `storage-broker` op=`put` a second time for the committee-visible mirror:

   ```
   OP: put
   namespace:       state/inbox/blockers
   kind:            announcement
   payload:
     from_agent:    <from_agent>
     to_agent:      <to_agent>
     subject:       <subject>
     task_ref:      <task_ref or null>
     created_at:    <iso>
     primary_ref:   <Ref dict from step 2>
   body:            <body_md>
   human_legible:   true
   access_pattern:  read-heavy
   durability:      project
   scope:           project
   owner:           <from_agent>
   ```

   Because `kind=announcement` is a reviewable kind, the broker forces **md** placement at `<project>/.kiho/state/inbox/blockers/<key>.md`. Committees scanning blockers see these without parsing jsonl.

4. Return the primary Ref (from step 2). If a blocker mirror was written, include its Ref as `mirror_ref` in the response.

## Severity semantics

- **info** — Sender thinks the recipient might find this useful. Surfaces in `memo-inbox-read mode=digest` as a terse bullet. No CEO action implied. Example: "FYI the scraper cache has an extra 30k rows after yesterday's backfill."
- **action** — Sender is asking the recipient to do something or make a decision. Digest surfaces with a call-to-action marker. CEO routes this into the next plan.md delegation if the recipient has not acted within 3 loops. Example: "Please double-check the capability-matrix row for kb-update before I ship the T2 promotion."
- **blocker** — Sender cannot progress without the recipient. Mirrored to `state/inbox/blockers/` md so committees see it immediately. CEO escalates into `ceo-ledger` on the next loop and treats it as a pending question until resolved. Example: "I need a decision on whether the evolution row should carry the trust-tier auto-downgrade — blocking skill-factory step 7."

## Response shapes

```
OK (info / action):
{
  "status": "ok",
  "ref": {"tier": "jsonl", "namespace": "state/inbox/<to_agent>",
          "key": "<uuid>", "path": "<project>/.kiho/state/inbox/<to_agent>.jsonl",
          "row_id": "<id>", "etag": "<hash>"},
  "severity": "info | action",
  "mirror_ref": null
}

OK (blocker):
{
  "status": "ok",
  "ref": {"tier": "jsonl", ...},
  "severity": "blocker",
  "mirror_ref": {"tier": "md", "namespace": "state/inbox/blockers",
                 "key": "<uuid>", "path": "...blockers/<key>.md", ...}
}

ERR (policy violation):
{"status": "error", "code": "self_memo | bad_severity | missing_field",
 "detail": "<what failed>"}
```

## Invariants

- **File-write, never spawn.** `memo-send` is pure file I/O via `storage-broker`. It does not invoke the recipient, wake any daemon, or count toward the depth-3 / fanout-5 caps.
- **Lazy-read delivery.** Recipients receive nothing in real time. Memos surface when the recipient (or CEO on their behalf) next calls `memo-inbox-read`. Senders MUST NOT assume the recipient has seen a memo within the current turn.
- **CEO-only user funnel preserved.** Memos are agent-to-agent only. A memo is never rendered to the user. If a sub-agent believes the user must see something, it emits an `escalate_to_user` structured return — not a memo.
- **Blocker mirror is additive.** The primary Ref is always the jsonl row. The md mirror is a convenience for committees; losing it would not lose the memo.
- **No deletes.** `memo-send` never overwrites or deletes a prior memo. Retraction is done by sending a follow-up memo that references the original's key.

## Non-Goals

- **Not a broadcast bus.** Each call targets exactly one recipient. Fan-out to multiple agents means multiple `memo-send` calls; there is no wildcard recipient.
- **Not a live chat.** No streaming, no push. If the sender needs a same-turn reply, they must finish returning to the CEO and let the CEO route a new delegation.
- **Not a replacement for delegation briefs.** The CEO still owns task routing. A memo is "for your awareness when you next run"; a delegation is "do this work now."
- **Not a cross-project channel.** Inboxes are project-scoped. Cross-project coordination goes through the KB or the org-registry, not memos.

## Grounding

- `skills/core/storage/storage-broker/SKILL.md` — the broker this skill calls for both primary and mirror writes
- `references/react-storage-doctrine.md` — signal-to-tier resolution (why `append-only` + non-reviewable `kind=memo` lands in jsonl)
- `references/storage-architecture.md` — Tier-1 md mirror rationale for committee-visible blockers
- `skills/core/communication/memo-inbox-read/SKILL.md` — the paired read skill CEO runs at loop start
