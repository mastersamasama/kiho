# Decision — pulse surveys (committee pulse-surveys-2026-04-23)

## Status

Accepted by unanimous close at aggregate confidence 0.91, 1 round. Outcome: **reject new surface**, land three small reinforcements.

## Context

OA suites (Lark, Culture Amp, Leapsome) ship lightweight 1–3-question pulse surveys. Primary OA use cases: employee engagement signal + process-friction signal. kiho has `values-flag` (agent raises), `values-alignment-audit` (aggregate), and `retrospective` (narrative). Committee examined whether process-friction signal collection has a genuine gap.

## Decision

**No new skill.** Three small reinforcements instead:

### 1. Document "lightweight-committee" variant in `committee-rules.md`

Under `§Special committee types`, add:

```markdown
### Lightweight committee (v5.23+)

- Members: minimum 2, maximum 3 (plus clerk)
- Topic: a single closed question, binary or <5-option multiple-choice
- Max rounds: 1 (one round cap, not 3)
- Phases: research + choose ONLY; suggest and challenge are OPTIONAL and typically skipped
- Close threshold: standard unanimous + ≥0.90 (no relaxation)
- Use case: fast signal capture on a narrow question where 3-round deliberation is overkill
```

This preserves committee as the convergence primitive; the "lightweight" variant is notation, not new infrastructure.

### 2. Add process-friction question to retrospective ceremony

Under `skills/core/ceremony/retrospective/SKILL.md` §Procedure, insert mandatory step:

> Each participating agent MUST provide a single-sentence answer to: "What in this period's process blocked or slowed you? Answer 'nothing' if nothing did." Aggregate responses into the retrospective's friction section. Any `nothing`-to-`specific` ratio < 50% triggers a values-alignment-audit.

This captures the pulse use case inline — agents are already present at retro, answering a single question costs nothing.

### 3. Ship `bin/pulse_aggregate.py` helper

Stdlib-only script that reads `.kiho/state/values-flag.jsonl` (if it exists), groups entries by topic tag, and prints a friction rollup:

```
Friction rollup — last 30 days
  v5.22-hooks           : 3 flags  (threshold exceeded)
  cycle-runner-budgets  : 1 flag
  committee-round-cap   : 0 flags
```

Intended as a reader aid for comms + hr-lead at INITIALIZE. Also feeds committee 06 (dashboard) as a candidate metric.

## Consequences

### Positive

- No new skill means no new capability-taxonomy row, topic-vocabulary addition, or CATALOG entry.
- Lightweight-committee variant formalizes existing practice without changing semantics.
- Retrospective process-friction question captures signal agents were already empowered to raise via values-flag, but may not have prompted themselves to raise.
- Aggregation helper is a 50-line Python script, no state mutation, no tier concerns.

### Negative

- The retrospective ceremony grows by one required answer per participant — ~N words per agent per retro, small attention-budget cost.
- `pulse_aggregate.py` becomes yet-another stdlib script to maintain — total count of kiho Python helpers grows by 1.

## Alternatives considered and rejected

- **New `pulse-poll` skill + emission + aggregation + storage** — rejected as unjustified given existing primitives cover the workload.
- **Anonymous pulse track** — rejected; anonymity without escalation path is a noise pool. Attribution via values-flag is already the preferred kiho pattern.
- **Automatic pulse every N turns** — rejected as ceremony noise; the retrospective question lands pulse-signal at a natural boundary already.

## Scope estimate

- 1 small section add to `references/committee-rules.md` (~15 lines)
- 1 small procedure edit to `skills/core/ceremony/retrospective/SKILL.md` (~10 lines)
- 1 new Python helper `bin/pulse_aggregate.py` (~50 lines)
- 0 new skills, 0 data-storage-matrix rows, 0 hook changes
- Estimated implementation: ~1 hour

## Dependencies

- No blocking dependencies. `values-flag` and `retrospective` are shipped.

## Next concrete step

Implementation plan includes the three small edits. No follow-up committee. The process-friction question outcome should be checked at next retro-cycle to validate; if ratio consistently stays at 100% `nothing`, the committee's bet was wrong and the question gets rethought.
