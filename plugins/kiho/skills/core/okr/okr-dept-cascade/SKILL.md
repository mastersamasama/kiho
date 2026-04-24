---
name: okr-dept-cascade
description: Orchestrate the cascade from an active company Objective to department-level Objectives (v6.2+). Invoked by `kiho-okr-master` when the scanner emits `cascade-dept` action (active company O has no aligned dept O for one or more departments). For each such department, sends a memo (via `memo-send` severity=action) to the dept-lead with a brief to convene an OKR committee in their next /kiho turn. Does NOT wait for committee close — committees run asynchronously across /kiho turns; the scanner re-detects at the next sweep whether a dept O has emerged. Use when OKR-master receives `OPERATION: dispatch-dept` from CEO's INITIALIZE step 17.5, or from the `okr-period.toml` cycle template's `dept-cascade` phase.
argument-hint: "company_o_id=<id> period=<YYYY-QN>"
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: active
  kiho:
    capability: communicate
    topic_tags: [governance, coordination]
    data_classes: ["memo-inbox"]
    storage_fit:
      reads:
        - "<project>/.kiho/state/okrs/**"
        - "<project>/.kiho/state/org-registry.md"
      writes:
        - "<project>/.kiho/state/inbox/<dept-lead>.jsonl"
---
# okr-dept-cascade

OKR-master → dept-lead memo dispatcher. Fan-out from one company O to N department memos. Async by design — dept-leads act in their own /kiho turn.

## When to use

- `kiho-okr-master` receives `OPERATION: dispatch-dept` from CEO or cycle-runner.
- `okr-period.toml` phase `dept-cascade` invokes this as its entry skill.
- Post-company-O-accept: the CEO knows a company O just landed and no dept Os exist yet.

Do NOT invoke:

- To re-cascade a company O that already has aligned dept Os for every active dept (waste of memos). The scanner won't emit `cascade-dept` in that case.
- To dispatch individual Os — that's `okr-individual-dispatch` (separate skill).
- Across periods — one dept-cascade invocation serves one period.

## Inputs

```
PAYLOAD:
  company_o_id:       <O id>                                   # required
  period:             <YYYY-QN or YYYY-HN or custom slug>      # required
  include_depts:      [<dept-name>, ...]                       # optional; default: all active depts from org-registry
  exclude_depts:      [<dept-name>, ...]                       # optional
```

## Procedure

### 1. Read state

- Load the company O file at `<project>/.kiho/state/okrs/<period>/<company_o_id>.md` to pull its title + KRs (memo body cites them).
- Read `<project>/.kiho/state/org-registry.md` for the active dept list + dept-lead assignments.
- Read existing dept Os for this period to skip depts that already have aligned Os.

Refuse with `status: company_o_not_found` if the company O file is missing, or `status: company_o_not_active` if its `status != active`.

### 2. Resolve dispatch targets

```
targets = active_depts
        - excluded_depts
        - depts_with_existing_aligned_dept_o
```

If `include_depts` is given, intersect with that list.

If targets is empty, return `status: noop, reason: all_depts_aligned`.

### 3. Memo each dept-lead

For each dept in targets, emit one `memo-send`:

```
memo-send
  from_agent: kiho-okr-master
  to_agent:   <dept-lead-agent-id>
  subject:    "[OKR] Convene department OKR committee for <period> under <company_o_id>"
  severity:   action
  task_ref:   "okr-cascade-<period>-<dept>-<timestamp>"
  body_md: |
    Per the v6.2 OKR auto-flow, this department has no active Objective for
    <period> aligned to the company Objective just set:

    **Company O**: <company_o_id> — <title>
    **Key Results** (abbreviated):
    <first line of each KR>

    Please convene an OKR committee for <period> under this company O.
    Standard committee (3 rounds, 4 members: you + OKR-master + domain IC +
    auditor-skeptic). On close, the committee clerk signs
    `DEPT_COMMITTEE_OKR_CERTIFICATE` and auto-invokes okr-set level=department
    with aligns_to=<company_o_id>.

    Scope for your dept's O: one measurable outcome per period that, if
    achieved, materially advances the company O's KRs. 3-5 weighted KRs.

    Reply via memo or proceed directly in your next /kiho turn.

    Mechanism: references/approval-chains.toml chain `okr-department`.
    Guide: references/okr-guide.md (§How OKRs help).
```

### 4. Ledger trail

One entry per memo sent + one summary entry:

```
{"ts": "<iso>", "action": "okr_cascade_dept_memo",
 "payload": {"from": "kiho-okr-master", "to": "<dept-lead>",
             "company_o_id": "<id>", "period": "<period>", "dept": "<name>"}}

{"ts": "<iso>", "action": "okr_cascade_dept_complete",
 "payload": {"company_o_id": "<id>", "period": "<period>",
             "depts_memoed": [<list>], "depts_skipped_already_aligned": [<list>]}}
```

## Response shape

```
## Receipt <REQUEST_ID>
OPERATION: okr-dept-cascade
STATUS: ok | noop | company_o_not_found | company_o_not_active
COMPANY_O_ID: <id>
PERIOD: <period>
DEPTS_MEMOED: [<list>]
DEPTS_SKIPPED: [<list with reason>]
LEDGER_REF: jsonl://state/ceo-ledger.jsonl#seq=<n>
```

## Invariants

- **Async dispatch.** Do NOT wait for committee close in this /kiho turn. Committees run in their own subsequent turn.
- **One memo per dept per period.** Idempotence check: skip depts whose inbox already has an active `okr-cascade-<period>-<dept>-*` memo (from a prior sweep). The dept-lead's `memo-inbox-read` at their next turn surfaces it once; repeated memos are noise.
- **Memo via memo-send.** Do NOT direct-Write dept-lead inbox files — go through the memo-send skill so the blockers-mirror + inbox JSONL invariants hold.
- **Certificate neutrality.** This skill does NOT emit DEPT_COMMITTEE_OKR_CERTIFICATE. That's the committee clerk's job on close.

## Non-Goals

- **Not a committee runner.** This skill dispatches the ASK to run a committee; the committee skill runs in the dept-lead's turn.
- **Not a retry.** If a dept-lead ignores the memo across multiple periods, that's an escalation for the dept-lead's performance-review, not a dept-cascade retry loop.
- **Not a per-agent dispatcher.** Individual-O dispatch is `okr-individual-dispatch` — a different skill with a different review committee shape.

## Grounding

- `agents/kiho-okr-master.md` — the primary invoker.
- `skills/core/communication/memo-send/SKILL.md` — the dispatch primitive.
- `skills/core/planning/committee/SKILL.md` — what the dept-lead runs on receipt.
- `references/approval-chains.toml` — `okr-department` chain defines the certificate + stages the committee must execute.
- `references/okr-guide.md` — context the memo body cites for the dept-lead.
- `skills/core/okr/okr-individual-dispatch/SKILL.md` — sibling skill for the leaf layer of the cascade.
