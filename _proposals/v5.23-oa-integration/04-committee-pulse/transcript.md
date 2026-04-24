---
committee_id: pulse-surveys-2026-04-23
topic: "Should kiho have lightweight pulse polls distinct from committees?"
chartered_at: 2026-04-23T15:30:00Z
members:
  - "@kiho-hr-lead"
  - "@kiho-perf-reviewer"
  - "@kiho-auditor-pragmatist"
  - "@kiho-researcher"
quorum: 3
---

## Round 1

### research

- **@kiho-researcher** (confidence: 0.80) — OA pulse surveys (Lark, Culture Amp, Leapsome) are 1-3 questions, weekly-to-monthly cadence, anonymous aggregate. Primary use: engagement + process-friction signal. Central design tension: anonymous (honest but uncitable) vs attributed (actionable but chills honesty).
- **@kiho-hr-lead** (confidence: 0.75) — kiho has no engagement signal to measure — LLM agents don't "disengage". But the PROCESS-FRICTION use case is real and unaddressed: after a process change (v5.22 hooks, new cycle template), there's no fast aggregate-signal mechanism to hear "this is blocking work" without convening a full retrospective.
- **@kiho-auditor-pragmatist** (confidence: 0.85) — Scrutinizing the gap: (a) `values-flag` lets any agent raise a signal; (b) `values-alignment-audit` aggregates flags at cadence; (c) retrospective ceremony provides narrative friction feedback; (d) 2-member committee with single choose-phase is ~15 minutes of work. Can ANY proposed pulse use-case not be served by these?
- **@kiho-perf-reviewer** (confidence: 0.78) — Process-friction signal IS covered by values-flag already. Agents flag process friction via values-flag; values-alignment-audit catches it. The only delta a pulse adds is "prompt agents to flag" rather than "agents raise spontaneously." That's negligible delta in an agent harness — agents act on skill invocation, not mood.

### suggest

- **@kiho-auditor-pragmatist** (confidence: 0.88) — **Reject new pulse skill.** Existing primitives (values-flag + values-alignment-audit + retrospective + small committee) cover the workload. Recommend: document a "lightweight-committee" pattern in `committee-rules.md` §Special committee types as a named variant (min 2 members, 1 round cap, single choose phase); also recommend an optional helper `bin/pulse_aggregate.py` that groups recent values-flag entries by topic for at-a-glance friction view.
- **@kiho-researcher** (confidence: 0.80) — Support pragmatist's reject, with one addition: add a single-question survey template to the retrospective ceremony — "Anything in this period's process that blocked you?" — which every agent answers as part of retro. Zero new skill; one added retrospective template field.

### challenge

- **@kiho-hr-lead** (confidence: 0.80) — Weak challenge: will agents remember to values-flag process friction proactively, or will friction get suppressed?
  > Resolved: the auditor's framing is correct — agents don't "remember" in the human sense; they flag on observation, which is their design. If values-flag is not being invoked by agents on real friction, that's a soul-drift problem (agent doesn't consider process-friction in-scope for values-flag), to be fixed in soul-overrides, not by adding a new surface.

### choose

- **@kiho-hr-lead** (confidence: 0.90) — Reject new pulse skill. Document lightweight-committee variant + add the retrospective "process-friction" question + ship `bin/pulse_aggregate.py` helper.
- **@kiho-perf-reviewer** (confidence: 0.90) — Same.
- **@kiho-auditor-pragmatist** (confidence: 0.92) — Same.
- **@kiho-researcher** (confidence: 0.90) — Same.

Aggregate = mean(0.90, 0.90, 0.92, 0.90) = **0.905** ≥ 0.90. Unanimous. No unresolved challenges. **CLOSE.**

## Close

- outcome: unanimous
- final_confidence: 0.91
- rounds_used: 1
- decision: "Reject new pulse skill as unjustified overlap with existing primitives. Land three small changes: (1) document 'lightweight-committee' variant in committee-rules.md §Special committee types (min 2 members, 1 round cap, single choose phase); (2) add a mandatory 'process-friction question' to the retrospective ceremony template; (3) ship `bin/pulse_aggregate.py` helper that groups recent values-flag entries by topic for at-a-glance view. ZERO new skills."
