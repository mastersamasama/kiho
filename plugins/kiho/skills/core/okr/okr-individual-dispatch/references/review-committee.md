# review-committee.md — lightweight review committee for individual-O drafts

Declarative spec for the per-draft review committee that `okr-individual-dispatch` convenes at stage 4. Follows the `references/committee-rules.md` **§Lightweight committee** variant shipped in v6.1 (from v5.23 decision 04-committee-pulse).

## Committee identity

- **Convener**: HR-lead (`kiho-hr-lead`)
- **Quorum**: 3 (+ optional 4th for user escalation)
- **Max rounds**: 1 (one-round cap per lightweight variant)
- **Phases**: `research` + `choose` REQUIRED; `suggest` + `challenge` emit `(no entries this round)` placeholder
- **Close threshold**: standard unanimous + aggregate confidence ≥ 0.90 + no unresolved challenges (no relaxation)
- **Transcript**: `<project>/.kiho/committees/okr-indiv-<agent>-<period>/transcript.md`
- **Escalation**: non-unanimous within the single round → HR-lead routes to revise-or-reject per outcome

## Members

| Member | Role | Why they're here | Who they are NOT |
|---|---|---|---|
| `kiho-hr-lead` | convener + workforce fit | HR owns the dispatch + agent-lifecycle view; verifies the draft aligns with the agent's capability + capacity | NOT the domain judge |
| `<dept-lead>` (of the agent's dept) | domain fit + certificate emitter | Only person qualified to say "this KR is measurable and valuable in our domain"; emits `DEPT_LEAD_OKR_CERTIFICATE` on approve | NOT the cross-cutting auditor |
| `kiho-okr-master` | alignment integrity + cross-cutting audit | Verifies `aligns_to` actually matches parent dept-O's intent; cascade/cascade-close implications | NOT the convener; abstains from certificate emission |
| `user` (optional 4th) | final say on high-risk drafts | Invoked via CEO `AskUserQuestion` when one of four flags is true (see below) | NOT the workforce or domain expert |

## Optional user-seat triggers (any one of these)

The review committee includes a user seat iff any of:

1. Agent has < 30 onboarded iterations.
2. Agent has no prior closed individual OKR.
3. Agent's cycle-outcome score is below 0.70.
4. Draft has 5 Key Results (maximum — ambition flag).

When triggered: OKR-master prepares a user-seat preview (the draft + the agent's memory-ref citations + the committee's other-member positions), and CEO calls `AskUserQuestion` with the preview as context. User's answer counts as the 4th confidence value in the aggregate.

## Phase flow (lightweight — 1 round only)

### research phase

Each member produces a bulleted assessment:

- `@kiho-hr-lead` — assessment from workforce perspective: does the agent have capacity? does the capability-matrix support the KR skill requirements?
- `@<dept-lead>` — assessment from domain perspective: are the KRs measurable in this dept's normal operations? do they align to the parent O's intent?
- `@kiho-okr-master` — assessment from alignment perspective: does `aligns_to` match the O's actual path? are there cascade risks (e.g., a stretch KR that if missed would trigger false parent-close cascade)?
- `@user` (if seat triggered) — assessment from intent perspective: does this draft feel like the right commitment for this agent this period?

Each member's research entry cites ≥ 1 specific line from the draft's `rationale_from_lessons` list.

### suggest phase

`- (no entries this round)` — lightweight variant skips suggest.

### challenge phase

`- (no entries this round)` — lightweight variant skips challenge.

### choose phase

Each member produces a one-line vote in one of three forms:

- `- **@member** (confidence: 0.XX) — APPROVE: <one-line reason>`
- `- **@member** (confidence: 0.XX) — REVISE: <one-line specific feedback>`
- `- **@member** (confidence: 0.XX) — REJECT: <one-line reason>`

## Close decision

Close rule applied after choose phase (per `references/committee-rules.md` §Close rule):

1. All members say APPROVE + aggregate confidence ≥ 0.90 + no unresolved challenges → **Approve**.
2. Otherwise, if any member says REVISE (even with some APPROVE) → **Revise** (agent gets memo with combined feedback).
3. Otherwise, if all non-APPROVE members say REJECT → **Reject**.
4. Split between APPROVE and REJECT (no REVISE) → **Revise** as fallback (give agent one more chance before outright reject).

## Approve path

1. Dept-lead writes the `DEPT_LEAD_OKR_CERTIFICATE` block:

   ```
   DEPT_LEAD_OKR_CERTIFICATE:
     chain_id: okr-individual
     stages_complete: proposal-draft, dept-lead-review
     agent: <agent-id>
     dept_o_aligns_to: <parent-o-id>
     committee_id: okr-indiv-<agent>-<period>
     emitted_at: <iso>
     dept_lead: <dept-lead-agent-id>
   ```

2. HR-lead invokes `okr-set level=individual` with the approved draft's payload + certificate body.

3. Ledger gains `okr_individual_emitted` + `approval_stage_granted` entries (the stage_granted entries feed the v5.23 `ceo_behavior_audit.py approval_chain_skipped` drift check).

## Revise path

1. HR-lead aggregates feedback across all REVISE votes into a single memo to the agent.
2. Agent gets 2 more draft iterations (total of 3). On 3rd failure, force to Reject.
3. Memo cites specific `rationale_from_lessons` entries that didn't satisfy a reviewer.
4. No certificate emitted; the revise is NOT a chain-stage-granted event — only the final approved committee emits `approval_stage_granted`.

## Reject path

1. HR-lead invokes `skills/core/hr/rejection-feedback` to compose a structured rejection.
2. `memo-send` to agent (severity: info) with the structured feedback.
3. Ledger gains `okr_individual_rejected` entry citing the rejection reason.
4. No individual O for this agent this period; their performance is still measured by the dept-O rollup + cycle-outcome score.

## Ledger action types (consumed by v5.23 audit)

- `okr_dispatch_filter_complete` — stage 1
- `okr_dispatch_spawn` — stage 2 (one per agent spawn)
- `okr_dispatch_draft_received` — stage 3 (one per draft return)
- `okr_dispatch_draft_invalid` — stage 3 (per validation failure, includes iteration)
- `okr_review_committee_convened` — stage 4 open
- `approval_stage_entered` / `approval_stage_granted` — stage 4 close, chain_id=okr-individual
- `approval_chain_closed` — stage 4 close, outcome=granted|denied
- `okr_individual_emitted` — stage 5 approve
- `okr_individual_revise_requested` — stage 5 revise
- `okr_individual_rejected` — stage 5 reject

The `bin/ceo_behavior_audit.py` `approval_chain_skipped` drift class (v5.23) automatically catches any committee-approved OKR whose ledger trail is missing `approval_stage_granted` entries for both stages of the `okr-individual` chain.

## Why this shape

- **3 is the minimum for triangulation.** Fewer than 3 = single-point-of-failure on one reviewer; more than 4 = outside committee-rules ceiling + attention cost.
- **Lightweight > standard.** Individual O drafting is high-volume (N agents × M dept-Os), so 3-round committees would crush the turn budget. Single round forces reviewers to state their final position directly instead of deliberating.
- **Optional user seat > always user seat.** User fatigue is real; auto-reviewing every individual O would burn trust. The four flags are conservative — they trigger for genuinely novel or high-ambition drafts only.
- **Certificate emission stays at dept-lead.** Breaks the "who approves whom" ambiguity: HR orchestrates, OKR-master audits, dept-lead signs. Domain expertise is the gate.
