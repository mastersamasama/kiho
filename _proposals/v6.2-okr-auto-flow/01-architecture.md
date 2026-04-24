# 01 — v6.2 OKR auto-flow architecture

Formalized version of the user-approved plan (`C:\Users\wky\.claude\plans\drifting-wondering-treasure.md`). This is the architectural reference for the v6.2 OKR auto-flow; it cites the exact files shipped and the invariants that hold.

## The three user-required properties

The user's direct instruction on 2026-04-24:

> "OKR may let HR called the agent work and agent base on its experience to work on and check by lead and HR and OKR master or even user."

This decomposes into three load-bearing properties, each implemented structurally (not aspirationally):

1. **HR dispatches the agent to OKR work.** Implemented: `skills/core/okr/okr-individual-dispatch/SKILL.md` stage 2. HR-lead (not CEO, not OKR-master) spawns the candidate agent as sub-agent with the brief.

2. **Agent uses its own experience.** Implemented: `skills/core/okr/okr-individual-dispatch/references/agent-brief.md` — the brief REQUIRES four `memory-query` invocations (last 5 lessons, pending todos, recent importance-7+ observations, own agent.md soul) BEFORE drafting, and the returned JSON's `rationale_from_lessons` array MUST cite memory refs by regex-checkable path. Structural validation at stage 3 of the dispatch skill rejects drafts missing these refs.

3. **Multi-party review by dept-lead + HR + OKR-master + optional user.** Implemented: `skills/core/okr/okr-individual-dispatch/references/review-committee.md` — lightweight 1-round committee (v6.1 shipped variant from committee-04) with quorum 3, fourth user seat when any of four high-risk flags is true.

## The five trigger surfaces

Auto-flow is event-driven. Five events trigger OKR actions; no time-based cadence.

| Event | Emits trigger where | Action taken | File reference |
|---|---|---|---|
| CEO INITIALIZE (every /kiho turn) | `bin/okr_scanner.py` detects state | Emit prioritized action list (6 kinds); CEO routes per dispatch table | `agents/kiho-ceo.md` INITIALIZE step 17.5 |
| Period boundary (first 30 days of period with no company O) | Scanner `propose-company` action | OKR-master drafts; CEO bubbles via AskUserQuestion; on accept `okr-set level=company` | `bin/okr_scanner.py` + `skills/core/okr/okr-auto-sweep/SKILL.md` |
| Company O set, no dept O | Scanner `cascade-dept` action | OKR-master memos each dept-lead; dept-leads run OKR committees on their turn | `skills/core/okr/okr-dept-cascade/SKILL.md` |
| Dept O set, no individual Os | Scanner `cascade-individual` action | OKR-master memos HR-lead; HR-lead filters, dispatches, reviews, emits | `skills/core/okr/okr-individual-dispatch/SKILL.md` |
| Cycle close success with aligns_to_okr | cycle-runner `on_close_success` hook | `okr-checkin` auto with derived score delta | `skills/_meta/cycle-runner/references/orchestrator-protocol.md` §Hook verbs |
| Period end (today > period.end) | Scanner `period-close` action | `okr-close-period` batch + cascade close | `skills/core/okr/okr-close-period/SKILL.md` |
| Parent O closed | Scanner `cascade-close` action | Cascade rule applied; children → deferred or archive | `skills/core/okr/okr-close-period/SKILL.md` stage 4 |
| Onboard agent reaches threshold_iter | `skills/core/hr/onboard/SKILL.md` step 8 | HR-lead memoed to dispatch single-agent individual O | `skills/core/hr/onboard/SKILL.md` |

## Invariants

### User-gate invariants (unchanged from v6.1 committee-01)

- Company-level O REQUIRES `USER_OKR_CERTIFICATE` (user-accept via `AskUserQuestion`).
- Department-level O REQUIRES `DEPT_COMMITTEE_OKR_CERTIFICATE` (closed committee decision).
- Individual-level O REQUIRES `DEPT_LEAD_OKR_CERTIFICATE` (dept-lead emits at committee close).
- PreToolUse hook `bin/hooks/pre_write_chain_gate.py` enforces all three via `references/approval-chains.toml`.

### Role invariants (new in v6.2)

- **HR-lead dispatches.** Not CEO. Not OKR-master. HR-lead owns the workforce orchestration.
- **OKR-master audits but never emits certificates.** Parallel to kb-manager's never-write-raw invariant. OKR-master is committee MEMBER, never convener.
- **Dept-lead emits individual-O certificates.** Not HR-lead. Domain judgment is the gate.
- **Only CEO calls AskUserQuestion.** OKR-master prepares the preview; CEO bubbles. The CLAUDE.md invariant "CEO-only AskUserQuestion" holds.

### Structural invariants (new in v6.2)

- **Agent draft must cite memory.** `rationale_from_lessons` array in the draft JSON MUST have ≥ 1 ref. Missing → validation fail at stage 3 of dispatch skill.
- **At least one KR must be derivable from cycle events.** `derivable_from_cycle_events: true` flag required on ≥ 1 KR. Enables the auto-checkin hook to update the KR without explicit agent action.
- **Max 3 draft iterations.** Agent gets 3 tries before forced reject. Prevents infinite revision loops.
- **Fanout ≤ 5 per dispatch batch.** `individual_max_per_dept` config default; aligns with depth-cap discipline.
- **Leaf-first close.** Individual Os close before dept Os before company Os. Guarantees scoring order.
- **Cascade-rule config-gated.** `[okr] cascade_rule` = `deferred` (default) or `archive`; undefined → fallback to `deferred`.

### Audit invariants (new in v6.2)

- `okr_stale_o` drift (MINOR) fires when an active O has no checkin within `[okr] stale_days`.
- `okr_period_overrun` drift (MAJOR) fires when a period has ended but no `okr_period_auto_close_complete` ledger entry exists in the current turn.
- Scanner MUST emit a ledger entry even when zero actions — `okr_sweep_clean` prevents silent-skip drift (the same v5.22 discipline applied to step 7 and step 14).

## Sequence: one full period end-to-end

```
T-7 days before 2026-Q2 starts
  └─ CEO INITIALIZE step 17.5 runs scanner
     └─ Scanner: propose-company action (pre-start window)
        └─ OKR-master drafts 2 candidate Os from plan.md + retro + dashboard
           └─ CEO AskUserQuestion: "propose 2026-Q2 company O — accept / edit / dismiss?"
              └─ User: accept (edits weights on KR-2)
                 └─ okr-set level=company → file emitted with USER_OKR_CERTIFICATE
                    → Ledger: okr_auto_proposed, okr_set (company)

2026-04-02 (first /kiho turn after Q2 starts)
  └─ CEO INITIALIZE step 17.5 runs scanner
     └─ Scanner: cascade-dept action (company O has no dept children)
        └─ OKR-master memos each of {eng-lead, pm-lead, hr-lead, comms, kb-manager, perf-reviewer}
           → Ledger: 6× okr_cascade_dept_memo

2026-04-08 (eng-lead runs /kiho)
  └─ eng-lead reads inbox, sees OKR memo
     └─ Convenes standard committee (3-round, 4 members: self + OKR-master + eng-ic + auditor-skeptic)
        └─ Committee closes unanimous conf 0.91
           └─ committee clerk emits DEPT_COMMITTEE_OKR_CERTIFICATE
              └─ Auto-invokes okr-set level=department aligns_to=<company-O-id>
                 → Ledger: committee_closed, okr_set (dept-engineering)

2026-04-10 (next /kiho turn)
  └─ CEO INITIALIZE step 17.5 runs scanner
     └─ Scanner: cascade-individual action (new eng dept O, no aligned individual Os)
        └─ OKR-master memos HR-lead
           └─ HR-lead filters eng agents: keep 3 with capability ≥3 + score ≥0.70
              └─ For each of 3 agents, spawn with experience-using brief
                 ├─ Agent-A: drafts, cites 3 lessons, returns structured JSON
                 ├─ Agent-B: drafts, cites 1 lesson, returns structured JSON
                 └─ Agent-C: misses rationale → HR-lead memo iteration 1
                    └─ Agent-C iteration 2: drafts properly, cites 2 lessons
              └─ HR-lead validates all 3 drafts
                 └─ Convenes 3× lightweight 1-round review committee (one per draft)
                    ├─ Agent-A: 3 members (dept-lead + HR + OKR-master) unanimous APPROVE conf 0.92
                    ├─ Agent-B: 4 members (added user seat, agent has <30 iters) unanimous APPROVE conf 0.91
                    └─ Agent-C: dept-lead APPROVE, HR REVISE on weights, OKR-master APPROVE
                       → Revise outcome; memo Agent-C; iteration 3
                       └─ Agent-C iteration 3: revised weights → lightweight committee re-convenes → unanimous APPROVE
              └─ dept-lead emits 3× DEPT_LEAD_OKR_CERTIFICATE
                 └─ HR-lead invokes 3× okr-set level=individual
                    → Ledger: 3× okr_individual_emitted, 3× approval_chain_closed (okr-individual)

2026-04-10 through 2026-06-30 (many /kiho turns, many cycles run)
  └─ cycles with aligns_to_okr close success
     └─ cycle-runner on_close_success hook: okr-checkin
        └─ bin/okr_derive_score.py: delta = 0.05 × (KR weight / 100) × success_weight
           └─ Ledger: okr_auto_checkin_from_cycle
              └─ Individual O file history gains entry per cycle close

2026-07-01 (Q2 over; first /kiho turn of Q3)
  └─ CEO INITIALIZE step 17.5 runs scanner
     └─ Scanner: period-close action (today > 2026-07-01 for active 2026-Q2 Os)
        └─ OKR-master invokes okr-close-period period=2026-Q2
           └─ Walk tree leaf-first:
              ├─ 3× okr-close for individual Os (aggregates 0.82, 0.71, 0.45)
              ├─ 1× okr-close for dept O (aggregate 0.76)
              └─ 1× okr-close for company O (aggregate 0.78)
           └─ 5× memo-send to owners (fyi, aggregate cited)
           → Ledger: okr_period_auto_close_complete, closed: 5
  └─ Scanner also emits propose-company for Q3
     └─ Cycle begins anew
```

The user is on path exactly twice: accepting the Q2 company O draft on 2026-03-25, and being seated on Agent-B's review committee due to the <30-iter flag. Every other step is agent-autonomous.

## Composition with v5.23 infrastructure

The v6.2 auto-flow reuses — without modifying — five v5.23 systems:

1. **Approval chains** (`references/approval-chains.toml`) — the three OKR chains (okr-company, okr-department, okr-individual) stay unchanged. v6.2 auto-orchestrators emit the same certificates the v6.1 explicit flow does.
2. **Chain-aware PreToolUse hook** (`bin/hooks/pre_write_chain_gate.py`) — no change. Blocks any OKR-path write missing the correct certificate marker.
3. **Lightweight committee variant** (`references/committee-rules.md` §Lightweight) — v6.2 review committee is one instance of this variant.
4. **Agent cycle-outcome score** (`bin/agent_cycle_score.py`) — HR-lead reads this at dispatch stage 1 for filter criteria (≥ 0.70).
5. **Dashboard metric 7** (`bin/dashboard.py`) — surfaces closed individual Os automatically on next period rollup; no change needed.

## References

- Reversal: `00-reversal.md` (sibling file).
- User plan: `C:\Users\wky\.claude\plans\drifting-wondering-treasure.md`.
- Shipped commits: v6.2 PR 1 `c3ed4eb`, PR 2 `3b1c085`, PR 3 `f58c1de`.
- Release: v6.2.0 tag (next commit after this authoring).
