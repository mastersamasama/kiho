# Decision — 360 performance review (committee perf-review-360-2026-04-23)

## Status

Accepted by unanimous close at aggregate confidence 0.91, 1 round. Outcome: **reject pure peer-360**, adopt cycle-outcome-scoring hybrid.

## Context

OA 360 review aggregates peer + self + manager observations to produce a calibrated rating, compensating for the limited single-manager viewpoint on human work. Applying the pattern to LLM agents has a core concern: agents sharing a base model produce correlated judgments. Multi-peer "perspectives" may amount to repeated draws from the same distribution rather than independent signals.

Simultaneously, agent work is visible in telemetry in a way human work is not: `agent-performance.jsonl`, `cycle-events.jsonl`, `committee-close` outcomes, and `skill-invocations.jsonl` already capture the observable contribution surface. The committee's question collapsed to: is the gap that 360 fills in OA even present in an agent harness?

## Decision

**Reject multi-peer peer-observation entry.** Keep the current single-reviewer narrative review. Add a deterministic quantitative cycle-outcome score as a supplement.

### 1. No change to `performance-review` skill

`performance-review` continues as single-reviewer (usually `kiho-perf-reviewer`), producing narrative prose. Format, cadence, and integration with soul-overrides unchanged.

### 2. New helper `bin/agent_cycle_score.py`

Stdlib-only Python reading existing telemetry:

```
score(agent, period) =
    0.4  × skill_invocation_outcome_rate(agent, period)      # succeeded / invoked
  + 0.3  × cycle_phase_owner_success_rate(agent, period)     # cycles they owned that closed on-budget
  + 0.2  × committee_winning_position_rate(agent, period)    # committees they joined where their position won
  + 0.1  × kb_contribution_weight(agent, period)             # kb-manager-routed pages they caused (via committee decisions or direct research)
```

Per-cycle contributor credit uses the cycle's `handoffs.jsonl` window: phase owner gets 1.0 weight on `cycle_phase_owner_success_rate`; named contributors get 0.5.

Output: `agent-score-<period>.jsonl` (Tier-2, regenerable, append-only):

```jsonl
{"period": "2026-Q2", "agent": "kiho-eng-lead", "score": 0.847, "breakdown": {"invocation_rate": 0.92, "phase_owner_rate": 0.85, "committee_win_rate": 0.78, "kb_weight": 0.72}, "generated_at": "2026-04-23T17:00:00Z"}
```

### 3. Update promotion criteria

`skills/core/hr/agent-promote/SKILL.md` §Procedure: promotion committee MUST cite three signals (up from two):

- Capability-matrix proficiency (existing)
- `performance-review` narrative (existing)
- Cycle-outcome score (NEW) — raw number cited verbatim; any score < 0.70 blocks promotion unless the committee provides explicit counter-argument.

### 4. Data-storage-matrix row

New row (flagged as Storage-fit follow-up):

| Slug | Tier | Format | Path | Gatekeeper | Regenerable |
|---|---|---|---|---|---|
| agent-cycle-score-jsonl | T2 | JSONL | `.kiho/state/agent-score-<period>.jsonl` | bin/agent_cycle_score.py | yes (from existing T2 sources) |

## Consequences

### Positive

- Adds quantitative rigor to promotion without introducing correlated LLM peer feedback.
- Reuses existing telemetry — no new observation-collection surface.
- Regenerable T2 — the score is always recomputable from source JSONL streams.
- `perf-reviewer` role unchanged — no agent soul edit required.
- Preserves the single-reviewer narrative for context that telemetry can't capture (e.g., "this agent defused an escalation that didn't leave a ledger trace").

### Negative

- Cycle-outcome scoring introduces Goodhart risk: agents may learn to prefer committees they'll win, cycles they'll finish, skills with high hit rates. Values-alignment-audit becomes a necessary counterweight.
- The weighting (0.4/0.3/0.2/0.1) is a design choice without empirical calibration; may need tuning after first period. The 0.70 promotion threshold is similarly speculative.
- The `committee_winning_position_rate` metric could suppress legitimate dissent (the auditor-skeptic role would score poorly if they challenge well-supported positions even when they're right to challenge). Mitigation: auditor personas are excluded from this component or weighted differently — flagged as implementation concern, not committee decision.

## Alternatives considered and rejected

- **Pure peer-360** (each agent reviews N peers, aggregate rating) — rejected because LLM peer feedback is likely correlated echo, not independent signal.
- **Self-review component** — rejected; LLM self-assessment is a known unreliable signal (sycophancy, overconfidence).
- **Calibration meeting** — rejected as a human-manager ceremony without an agent analog.
- **360 of the CEO** — explicitly out-of-scope per charter; user reviews CEO, not subordinate agents.
- **No change** (status quo) — rejected because the current promotion criteria (capability-matrix + narrative) lack a quantitative signal; promotion committees have asked for one.

## Scope estimate

- 1 new Python helper (~150 lines with unit tests)
- 1 data-storage-matrix row (Storage-fit follow-up)
- 1 SKILL.md edit (`agent-promote` — promotion-criteria addendum)
- 0 new skills, 0 agent.md changes, 0 hook changes
- Estimated implementation: ~4 hours

## Dependencies

- Existing telemetry streams (`agent-performance.jsonl`, `cycle-events.jsonl`, `skill-invocations.jsonl`, committee close records) — all shipped.
- Storage-fit follow-up for new T2 row.

## Next concrete step

Implementation plan authorizes: `bin/agent_cycle_score.py` scaffolding + unit tests + synthetic fixtures covering the four breakdown components, then the `agent-promote` SKILL.md edit citing the score, then the Storage-fit row addition. First real period score emission would be retro at end of 2026-Q2.

## Explicit open question flagged for user (post-close)

Weighting calibration (0.4/0.3/0.2/0.1) and the 0.70 promotion threshold are design picks without empirical basis. Recommendation: ship as specified; record the first two periods' scores; hold a recalibration committee at end of v5.23 period to adjust based on observed distribution. This is an intentional "try it, measure it, tune it" loop rather than a blocker on v5.23.
