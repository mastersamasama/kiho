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
  to_agent:         <agent slug of the recipient — required; OR wildcard per "Wildcard recipients" below>
  subject:          <one-line summary, <= 80 chars>
  body_md:          <markdown body; findings, context, links>
  severity:         info | action | blocker (default: info)
  task_ref:         <optional; plan.md task id or ceo-ledger entry id>
  ttl_iterations:   <optional int; default 10; broker evicts after N CEO loops>
  pinned_until:     <optional ISO-8601; REQUIRED for wildcard recipients — broadcast auto-emits to announcements/>
  ack_required:     <optional bool; default false; wildcard-broadcast-only; tracked via announcement.ack_by>
  basis:            <optional path; REQUIRED for wildcard emission when emitter is NOT CEO and NOT a dept-lead; must cite a closed committee decision>
```

## Wildcard recipients (v5.23+)

`to_agent` accepts three wildcard forms in addition to a single agent slug. Wildcards cause `memo-send` to emit an **announcement** (Tier-1 markdown at `.kiho/state/announcements/<yyyy-mm-dd>-<slug>.md`) instead of a per-recipient inbox entry; each matching agent's `memo-inbox-read` and the `shift-handoff` ceremony pick it up from there.

| Wildcard | Expansion | Source of truth |
|---|---|---|
| `@all` | every agent listed in `state/org-registry.md` | `org-sync` output |
| `@dept:<department>` | every agent whose `agent.md` frontmatter declares `department: <value>` | agent.md frontmatter |
| `@capability:<verb>` | every agent whose row in `state/capability-matrix.md` shows ≥3 proficiency on the named verb | capability-matrix |

Wildcard emission requires:

- `pinned_until` set (bulletin-board entries MUST have an expiry — no unbounded pins)
- If emitter is NOT the CEO (main conversation) AND NOT a dept-lead, a `basis` field pointing at a closed committee decision is REQUIRED. `memo-send` aborts with `status: broadcast_basis_required` if missing. This is the v5.22-style pre-emit gate applied to emission — not a PreToolUse hook (which would be redundant since the skill is the single writer for this surface).
- `severity: blocker` combined with a wildcard is REJECTED. A company-wide blocker is a contradiction; if the situation really demands that, use `severity: action` on the announcement and escalate to `incident-open` separately.

Fan-out of the wildcard expansion is bounded by the capability-matrix size (typically ≤ 20 agents). The depth/fanout caps that apply to sub-agent spawning do NOT apply here; wildcard expansion is a file-read followed by one file-write, not a spawn.

## Procedure

1. Validate inputs. Reject if `from_agent == to_agent` (no self-memos — use scratch notes instead). Reject if `severity` is not in the three-value enum. If `to_agent` starts with `@` (wildcard), validate per "Wildcard recipients" (require `pinned_until`; require `basis` unless emitter is CEO / dept-lead; reject `severity: blocker`) and branch to step 2b.
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

### Step 2b — Wildcard broadcast branch

When `to_agent` is a wildcard (`@all`, `@dept:*`, `@capability:*`), replace steps 2 and 3 with a single announcement write:

```
OP: put
namespace:       state/announcements
kind:            announcement
payload:
  id:            <yyyy-mm-dd>-<slug-derived-from-subject>
  emitter:       <from_agent>
  audience:      <to_agent wildcard string, verbatim>
  pinned_until:  <pinned_until>
  ack_required:  <ack_required, default false>
  ack_by:        []
  basis:         <basis or null>
  subject:       <subject>
  severity:      <severity>
  created_at:    <iso>
body:            <body_md>
human_legible:   true
access_pattern:  read-heavy
durability:      project
scope:           project
owner:           <from_agent>
```

Broker resolves to markdown at `<project>/.kiho/state/announcements/<id>.md` per the v5.23 data-storage-matrix `announcements` row. Emit `action: announcement_published, payload: {announcement_id, emitter, audience, ack_required}` to the CEO ledger.

Subsequent `memo-inbox-read` sweeps and the `shift-handoff` ceremony re-surface the announcement to matching agents; acknowledgement is non-blocking (agents acknowledge via `memo-inbox-read` which appends their id to `announcement.ack_by` and emits `action: announcement_acknowledged` to the ledger). No agent is forced to respond; the `ack_by` list is a visibility mechanism.

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

- **Not a replacement for dedicated channels.** Targeted peer-to-peer is the primary mode. Wildcard recipients (v5.23+) emit announcements — a distinct bulletin-board surface — not a push bus.
- **Not a live chat.** No streaming, no push. If the sender needs a same-turn reply, they must finish returning to the CEO and let the CEO route a new delegation.
- **Not a replacement for delegation briefs.** The CEO still owns task routing. A memo is "for your awareness when you next run"; a delegation is "do this work now."
- **Not a cross-project channel.** Inboxes are project-scoped. Cross-project coordination goes through the KB or the org-registry, not memos.

## Grounding

- `skills/core/storage/storage-broker/SKILL.md` — the broker this skill calls for both primary and mirror writes
- `references/react-storage-doctrine.md` — signal-to-tier resolution (why `append-only` + non-reviewable `kind=memo` lands in jsonl)
- `references/storage-architecture.md` — Tier-1 md mirror rationale for committee-visible blockers
- `skills/core/communication/memo-inbox-read/SKILL.md` — the paired read skill CEO runs at loop start
