---
name: memo-inbox-read
description: Use this skill when the CEO (or any lead) needs to check its inbox for memos dropped by peers or sub-agents. Two modes — full reads all memos chronologically, digest returns a triaged summary grouped by severity and source. Runs at CEO loop-start as part of the Ralph initialization so blockers surface before the next delegation. Also callable ad-hoc by sub-agents that want to pull prior FYI threads before starting a task. Reads only; never deletes memos (use storage-broker evict for cleanup). Respects the CEO-only user funnel — digest output is CEO-consumable, never rendered to the user directly without CEO discretion.
argument-hint: "agent_id=<id> mode=<full|digest> since=<iso>"
metadata:
  trust-tier: T2
  kiho:
    capability: read
    topic_tags: [coordination, retrieval]
    data_classes: ["memo-inbox"]
---
# memo-inbox-read

The paired reader for `memo-send`. Every agent with a jsonl inbox under `<project>/.kiho/state/inbox/<agent_id>.jsonl` uses this skill to pull incoming memos. The CEO runs it at loop start to triage overnight memos before re-reading plan.md; sub-agents may call it ad-hoc when they want to pick up prior FYI threads before starting a task.

## Why a two-mode read

The inbox has two natural consumption patterns. The CEO cares about "what needs my attention this loop" — a bounded, severity-sorted digest with the full body inlined only for blockers. A sub-agent opening its own inbox cares about "show me everything I have not seen before" — a chronological full list. One mode per intent, no compromise surface that fits neither.

## Inputs

```
PAYLOAD:
  agent_id:         <agent slug whose inbox to read — required>
  mode:             full | digest (default: digest)
  since:            <optional ISO timestamp; only return memos created at or after>
  severity_filter:  <optional list; subset of [info, action, blocker]>
  limit:            <optional int; default 50 for full, 15 for digest (5 per group)>
```

## Procedure

1. Validate that `<project>/.kiho/state/inbox/<agent_id>.jsonl` is within the project's inbox namespace. Reject paths containing `..` or absolute overrides.
2. Call `storage-broker` op=`query`:

   ```
   OP: query
   namespace:   state/inbox/<agent_id>
   where:       { severity: <severity_filter if set> }
   order_by:    created_at desc
   limit:       <limit>
   ```

   If `since` is supplied, the caller filters the returned rows by `created_at >= since` (broker does not yet support range filters natively; this is a client-side trim).

3. Shape the response by mode:

   - **full**: return the row list as `rows`, preserving broker order (newest first). Each row carries its full `payload`, `body`, and a `Ref` the caller can cite later.
   - **digest**: group rows by severity in the order `blocker → action → info`. Within each group, keep at most 5 rows (the most recent). For each kept row, emit a one-line summary: `[<severity>] <from_agent> → <to_agent>: <subject> (<iso-date>)`. For blockers, inline the `body` excerpt (first 240 chars) and include the `mirror_ref` if present. Record a `truncated` count per group when rows were dropped by the 5-per-group cap.

4. If `mode=digest` AND any blocker rows were returned AND the caller is `ceo-01`, emit a `ceo_ledger_hint` entry in the response pointing at the blocker `mirror_ref` paths — the CEO persona converts this into `ceo-ledger` escalations during its INITIALIZE phase.

5. Return. Do not mark rows as "read"; there is no read-state on an inbox memo. De-duplication across loops is the caller's job (the CEO compares `since` against the prior loop's `loop_started_at`).

## CEO loop-start usage

The `kiho-ceo` agent's Ralph INITIALIZE phase is canonically:

1. `session-context` — rehydrate conversation context.
2. `memo-inbox-read agent_id=ceo-01 mode=digest since=<last_loop_started_at>` — triage overnight memos.
3. Re-read `plan.md`, ledger, and any pending `escalate_to_user` frames.

Blockers in the digest force an escalation path: the CEO writes a `ceo-ledger` entry citing the blocker memo's Ref, adds a RACI'd task to plan.md if needed, and may bundle the blocker into the next `AskUserQuestion` if the blocker is user-answerable. Action memos are surfaced in the CEO's turn summary and routed into the next delegation batch. Info memos are logged but do not gate the loop.

Sub-agent leads (department heads, team leads) running sub-loops may call `memo-inbox-read mode=digest` with their own `agent_id` at the start of their task, subject to the depth-3 / fanout-5 caps — which this skill does not itself contribute to, since it is a read call.

## Response shapes

```
OK (digest):
{
  "status": "ok",
  "mode": "digest",
  "agent_id": "<id>",
  "since": "<iso or null>",
  "groups": {
    "blocker": {
      "count": <int>,
      "truncated": <int>,
      "rows": [
        {
          "summary":    "[blocker] kb-manager → ceo-01: <subject> (2026-04-18T22:10Z)",
          "body_excerpt": "<first 240 chars>",
          "ref":        {"tier": "jsonl", "namespace": "...", "key": "..."},
          "mirror_ref": {"tier": "md", "namespace": "state/inbox/blockers", ...}
        }
      ]
    },
    "action": { "count": <int>, "truncated": <int>, "rows": [...] },
    "info":   { "count": <int>, "truncated": <int>, "rows": [...] }
  },
  "ceo_ledger_hint": [ "<mirror_ref.path>", ... ]   # present only when caller=ceo-01 and blockers > 0
}

OK (full):
{
  "status": "ok",
  "mode": "full",
  "agent_id": "<id>",
  "since": "<iso or null>",
  "rows": [
    {
      "meta":    {...},
      "payload": {"from_agent": "...", "to_agent": "...", "subject": "...",
                  "severity": "...", "task_ref": "...", "created_at": "..."},
      "body":    "<full markdown body>",
      "ref":     {"tier": "jsonl", ...}
    }
  ]
}

OK (empty inbox):
{"status": "ok", "mode": "<mode>", "agent_id": "<id>", "rows": []}

ERR:
{"status": "error", "code": "bad_namespace | bad_mode", "detail": "<what failed>"}
```

## Invariants

- **Read-only.** This skill never calls `storage-broker` with op=`put` or op=`evict`. It cannot delete, edit, or mark memos. Cleanup is a separate `storage-broker evict` call that the caller (CEO or a committee-approved housekeeping skill) makes explicitly.
- **CEO-only user funnel.** Digest output is CEO-consumable. A sub-agent calling this skill receives structured data it may act on internally, but it MUST NOT surface memo content to the user — only the CEO chooses whether to raise a memo into an `AskUserQuestion` prompt.
- **O(n) scan is fine until ~1000 rows.** The jsonl spool reads linearly; below ~1000 rows per inbox this is negligible. Above that threshold, `storage-broker` auto-promotes the namespace to a lazily built sqlite FTS index on the next query — no caller change required.
- **No read-state tracking.** The skill never writes back "seen" markers. Callers that need idempotency track `last_loop_started_at` themselves and pass it as `since`.
- **Scope-safe.** Inbox namespaces are project-scoped. This skill refuses absolute paths or traversal patterns.

## Non-Goals

- **Not a notification daemon.** There is no push, no watcher, no callback. The CEO's Ralph loop is the schedule.
- **Not a search tool.** Cross-inbox search and semantic retrieval are the job of `learning-query` (over the experience pool). `memo-inbox-read` reads exactly one recipient's inbox.
- **Not an evictor.** Housekeeping (older-than-N-days, keep-last-N) is done by `storage-broker evict` under committee policy, not here.
- **Not a diff tool.** The skill does not compute what-changed-since-last-read. Callers compare `since` timestamps themselves.

## Grounding

- `skills/core/storage/storage-broker/SKILL.md` — the query backend; digest groupings are built on top of its ordered scan
- `references/react-storage-doctrine.md` — why inbox reads stay jsonl until the auto-promote threshold
- `skills/core/communication/memo-send/SKILL.md` — the paired writer; every row read here was produced by a `memo-send` call
- `agents/kiho-ceo.md` — INITIALIZE phase that wires this skill into the Ralph loop
