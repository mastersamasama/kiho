# 00 — Reversal of committee-01 OKR decision (user direct override)

## Status

**Committee-01 of v5.23 OA-integration** closed `okr-framework-2026-04-23` unanimously at confidence 0.91 on 2026-04-23. The decision produced the v6.1.0 explicit-only OKR skill portfolio (okr-set / okr-checkin / okr-close).

**User direct override on 2026-04-24** reverses the committee's "no auto-cadence" stance (section: "Cadence: No automatic cadence. `okr-checkin` is invoked explicitly by the responsible agent (R per RACI) on an irregular basis. No Ralph-loop-turn trigger. The auditor vetoed 'checkin every turn' as ceremony noise.").

The reversal is **partial**: time-based cadence is still rejected (valid concern — "ceremony noise" is a real failure mode); event-driven auto-flow is now adopted. These are distinct categories.

## Why the reversal was valid

Per CLAUDE.md invariant: **"User confirmation is non-bypassable"** extends to user-directed reversal of committee decisions. A closed committee decision is binding on agents; it is not binding on the user. The precedent was set when CLAUDE.md explicitly enumerated user-accept as the final gate for every soul-mutating change; by extension, the user can reverse an already-accepted committee decision when their understanding of the system shifts.

The user's stated reason on 2026-04-24:

> "This not match the philosophy of full auto company, ceo or other agent should setup okr when need automatically and follow the flow of okr set up, track, scoring and implementation, or else it is no need."

Translation: kiho is a full-auto organization; OKRs that require the user to initiate every cadence step add friction without adding value over `plan.md`. Either the flow completes autonomously or it shouldn't exist.

Committee-01 reasoned under an OA analogy (humans set OKRs by hand because humans have agency). The user clarified that in kiho, **agents are the agency substrate**, and OKRs must flow through agents the way every other kiho ceremony does.

## What changed (v6.2 vs v6.1)

| Aspect | v6.1 (committee-01 accepted) | v6.2 (user override adopted) |
|---|---|---|
| Cadence for `okr-set` | Explicit only | Event-driven (period boundary + onboard threshold + committee close) |
| Cadence for `okr-checkin` | Explicit only | Event-driven (cycle close success) |
| Cadence for `okr-close` | Explicit only | Event-driven (period end) |
| User on path | All three levels (user drafts O in conversation) | Company-level only (`USER_OKR_CERTIFICATE` invariant preserved) |
| Dept-level O emission | User invokes after committee close | Committee close auto-invokes `okr-set level=department` |
| Individual-level O emission | User invokes or manual dept-lead approval | HR-dispatched agent-drafts-from-experience → lightweight committee review → auto-emit on approve |

## What did NOT change

Committee-01's load-bearing invariants remain intact:

- Three-level structure (company / department / individual) — unchanged
- Per-level approval chain + certificate markers (`USER_OKR_CERTIFICATE`, `DEPT_COMMITTEE_OKR_CERTIFICATE`, `DEPT_LEAD_OKR_CERTIFICATE`) — unchanged
- Stretch KR cap at 0.7 for aggregate — unchanged
- One-concept-per-file Tier-1 storage at `.kiho/state/okrs/<period>/` — unchanged
- `okr-set`/`okr-checkin`/`okr-close` atomic primitives — unchanged (auto-orchestrators call them)
- No time-based cadence (hourly / daily / weekly triggers) — unchanged; v6.2 adds EVENT-based triggers, not TIME-based

The user's concern ("ceremony noise" from time-based cadence) is preserved. Committee-01 was right about that; it just conflated time-based with event-based.

## Precedent for future similar reversals

1. **User reversal of committee decisions is valid** when the user cites a philosophical principle already present in CLAUDE.md (e.g., "full-auto", "CEO-only user interaction"). Reversal is recorded in `_proposals/<version>-<name>/00-reversal.md` citing the original decision path.

2. **Partial reversals are valid**. Not every claim in a committee's decision is equally load-bearing. Reversing the cadence posture without reversing the three-level structure or the certificate invariants is coherent.

3. **The committee's work is not wasted**. The v6.1.0 OKR skill portfolio (okr-set/okr-checkin/okr-close) shipped under committee-01's design and remains the atomic-primitive layer under v6.2's auto-orchestrators. Reversal of cadence decision ≠ scrapping the committee's output.

4. **The reversal record goes in `_proposals/`, not in CHANGELOG alone**. Future auditors (including the kb-manager at INITIALIZE) need the full lineage: committee decision → user reversal reasoning → new architecture. One-line CHANGELOG mention is insufficient.

## v6.2 implementation lineage

See `_proposals/v6.2-okr-auto-flow/01-architecture.md` (sibling file) for the full auto-flow architecture — the 6-phase `okr-period.toml` cycle template, the new `kiho-okr-master` agent role, the HR-dispatched individual-O drafting protocol, the cycle-close auto-checkin hook, and the period-end cascade close.

Shipped files (v6.2 PR 1 + PR 2 + PR 3):

- `agents/kiho-okr-master.md` (new agent, parallel to kb-manager)
- `bin/okr_scanner.py` + `bin/okr_derive_score.py` (deterministic helpers)
- `references/cycle-templates/okr-period.toml` (the lifecycle template)
- `skills/core/okr/okr-auto-sweep/` (sk-083) + `okr-dept-cascade/` (sk-084) + `okr-individual-dispatch/` (sk-085) + `okr-close-period/` (sk-086)
- `skills/core/okr/okr-individual-dispatch/references/agent-brief.md` + `review-committee.md`
- Ledger actions: `okr_sweep_complete`, `okr_auto_proposed`, `okr_cascade_dept_memo`, `okr_dispatch_spawn`, `okr_individual_emitted`, `okr_period_auto_close_complete`, `okr_cascade_close`, + approval_stage_* for the okr-individual chain

Total scope: +4 new skills (sk-083–086), +1 new agent, +2 new Python helpers + 2 new test files, +1 new cycle template, +5 new ledger action types, +2 new drift classes in `ceo_behavior_audit.py`. Zero changes to the v6.1 atomic primitives.

## Committee-01 decision document (unchanged)

The original decision remains at `_proposals/v5.23-oa-integration/01-committee-okr/decision.md`. This reversal record supersedes section "Cadence: No automatic cadence..." of that decision. All other sections stand.
