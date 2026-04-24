---
committee_id: perf-review-360-2026-04-23
topic: "Should kiho extend performance-review to multi-peer 360, or is agent peer signal insufficient?"
chartered_at: 2026-04-23T16:00:00Z
members:
  - "@kiho-hr-lead"
  - "@kiho-perf-reviewer"
  - "@kiho-kb-manager"
  - "@kiho-pm-lead"
  - "@kiho-auditor-skeptic"
quorum: 4
---

## Round 1

### research

- **@kiho-auditor-skeptic** (confidence: 0.85) — Central question: does multi-peer LLM feedback produce INFORMATION relative to single-reviewer, or does it produce CORRELATED ECHO? LLM agents share base model + training corpus; on judgment tasks their outputs exhibit high pairwise correlation. In human 360 the signal comes from perspective diversity — each human has different private context. In agent 360 the "private context" is mostly session memory, which is narrow and often overlapping.
- **@kiho-perf-reviewer** (confidence: 0.82) — Current performance-review is single-reviewer (usually me). Reviewer draws from `agent-performance.jsonl` (telemetry) + `memory/reflections.md` (self-observation) + capability-matrix (proficiency). The telemetry IS already quantitative and multi-source (every cycle / committee / skill-invocation contributes). Arguably the "360" is already built-in — just with the telemetry playing the role of "peers."
- **@kiho-hr-lead** (confidence: 0.75) — Fair counter to the OA framing: OA 360 is peer-provided observation BECAUSE human work is often invisible to telemetry. Agent work is visible in JSONL streams. The gap OA fills (human ambiguity) may not exist for agents.
- **@kiho-pm-lead** (confidence: 0.78) — Promotion criteria today: capability-matrix ≥ 3.5 in the target role's skills + `performance-review` narrative + CEO accept. Adding 360 peers would insert a third axis that's weakly independent of the first two. Low signal gain, high coordination cost.
- **@kiho-kb-manager** (confidence: 0.80) — Storage concern: if 360 peer feedback lands, where does it live? Extension of `memory/reflections.md` bloats each agent's tier-3 archive with "others' observations of me". Separate `reviews/<period>/<subject>/<reviewer>.md` is cleaner but adds N×M files per period.

### suggest

- **@kiho-auditor-skeptic** (confidence: 0.90) — **Reject pure 360.** Adopt a HYBRID: (a) keep single-reviewer narrative performance-review as-is, (b) add `performance-score-cycle-outcome.py` deterministic quantitative score from existing telemetry (`agent-performance.jsonl` + `cycle-events.jsonl` + `committee-close`-outcomes + `skill-invocations.jsonl`), (c) reject multi-peer-observation entry. Single-reviewer narrative + deterministic quantitative score = functional 360 equivalent without LLM peer-echo noise.
- **@kiho-hr-lead** (confidence: 0.85) — Second the hybrid. The deterministic score is where the real gain is: promotion committees can cite concrete numbers, not just narrative.

### challenge

- **@kiho-pm-lead** (confidence: 0.82) — Weak challenge on the hybrid: does cycle-outcome scoring correctly attribute credit in multi-agent cycles? A cycle with 4 contributors shouldn't give equal credit.
  > Resolved: use per-agent `skill-invocations.jsonl` restricted to the cycle's handoffs.jsonl window, weighted by skill's role in the cycle phase. Phase owner gets 1.0 weight; phase contributor gets 0.5. Full formula specified in decision.md.
- **@kiho-perf-reviewer** (confidence: 0.88) — Challenge on feasibility: does adding a quantitative score collide with my current role?
  > Resolved: no. I continue to author the narrative; the script emits the quantitative score as a supplement. My review cites the score but doesn't generate it.

### choose

- **@kiho-hr-lead** (confidence: 0.92) — Hybrid: keep single-reviewer narrative, add deterministic cycle-outcome score via new `bin/agent_cycle_score.py` helper. Reject multi-peer-observation entry.
- **@kiho-perf-reviewer** (confidence: 0.90) — Same.
- **@kiho-kb-manager** (confidence: 0.90) — Same. Storage: score output is T2 regenerable (`agent-score-<period>.jsonl`), not a new markdown directory.
- **@kiho-pm-lead** (confidence: 0.90) — Same. Promotion criteria get the score as a third signal.
- **@kiho-auditor-skeptic** (confidence: 0.93) — Same.

Aggregate = mean(0.92, 0.90, 0.90, 0.90, 0.93) = **0.910** ≥ 0.90. Unanimous. No unresolved challenges. **CLOSE.**

## Close

- outcome: unanimous
- final_confidence: 0.91
- rounds_used: 1
- decision: "Reject pure multi-peer 360 as redundant with existing telemetry + high-risk for LLM peer echo. Adopt HYBRID: keep single-reviewer narrative performance-review unchanged; add deterministic quantitative cycle-outcome score via new `bin/agent_cycle_score.py` helper reading existing JSONL streams, output to Tier-2 `agent-score-<period>.jsonl`; update promotion criteria to cite the score alongside narrative + capability-matrix. ZERO new review skills; ZERO new agent roles; one Python helper + one T2 output."
