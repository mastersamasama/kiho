# Charter — 360 performance review committee

## Committee identity

- **committee_id:** `perf-review-360-2026-04-23`
- **topic:** "Should kiho extend performance-review to multi-peer 360, or is agent peer signal insufficient?"
- **chartered_at:** 2026-04-23T16:00:00Z
- **reversibility:** reversible
- **knowledge_update:** true

## Members (quorum 4 of 5)

- **@kiho-hr-lead** — owner of the performance-review flow
- **@kiho-perf-reviewer** — current single-reviewer agent; most affected by any change
- **@kiho-kb-manager** — review outputs become KB decisions; gateway concern
- **@kiho-pm-lead** — promotion criteria interaction
- **@kiho-auditor-skeptic** — challenges the assumption that more reviewers = better signal

Clerk: auto-assigned. Not a member.

## Input context

- User gap: 360 review aggregates peer + self + manager feedback. Current kiho `performance-review` is single-reviewer.
- Gap score from `00-gap-analysis.md` §matrix row 5: **MEDIUM** — LLM-agent peer signal quality is an open empirical question.
- Unique constraint: LLM agents share base models + training; peer signal may echo rather than triangulate. This committee must decide whether 360 produces information or noise.

## Questions the committee MUST answer

| # | Question | Why it matters |
|---|---|---|
| Q1 | **Does multi-peer LLM feedback produce more signal than single-reviewer?** Or does it produce correlated echo? | Central empirical question; may kill the proposal outright |
| Q2 | **Which peer pairs carry meaningful signal?** Cross-department (eng-lead reviewing HR-lead) vs same-department (HR-lead reviewing perf-reviewer)? | Determines who gets put into the review panel |
| Q3 | **Collusion / echo prevention** — if two peers share context (just worked the same cycle together), how is their independence preserved? | LLM peers don't collude but DO echo common priors |
| Q4 | **Storage** — extension of `memory/reflections.md` per-agent, new `reviews/<period>/<subject>/` directory, or overlay on existing `agent-performance.jsonl`? | Must be T1 for committee-reviewable (promotion-impacting) |
| Q5 | **Integration with `agent-promote` criteria** — does 360 feed in, replace, or supplement existing capability-matrix + telemetry? | If not wired to promotion, it's decorative |
| Q6 | **Is the alternative "cycle-outcome-based scoring" stronger?** — rating = f(cycles shipped, incidents triggered, committees won/lost) — and does this make 360 unnecessary? | The skeptic's likely counter-proposal |

## Success criteria

Unanimous position that is one of:

- **Endorse 360 extension** — concrete design: reviewer selection protocol, echo-prevention mechanism, storage tier, integration with promotion. Must cite at least one hypothesis for why multi-peer produces signal not present in single-reviewer.
- **Reject 360, endorse cycle-outcome scoring** — concrete design: which telemetry feeds the score, weighting, storage, promotion integration. The skeptic's likely winning position if Q1 gets a negative answer.
- **Hybrid** — single-reviewer stays for narrative assessment; cycle-outcome scoring added as quantitative supplement. 360-from-peers rejected.

## Constraints + references

- `plugins/kiho/skills/core/hr/performance-review/SKILL.md` — the current single-reviewer flow.
- `plugins/kiho/skills/core/hr/agent-promote/SKILL.md` — promotion criteria consumer.
- `plugins/kiho/references/soul-architecture.md` — reviews feed `soul-overrides` pipeline.
- `plugins/kiho/references/data-storage-matrix.md` — `agent-performance-jsonl` row already exists; new review rows may be needed.
- `plugins/kiho/agents/kiho-perf-reviewer.md` — affected agent's soul; any change must be reconcilable with existing role.

## Out of scope (explicit)

- **No self-review as primary signal.** LLM self-assessment is a known unreliable signal (sycophancy, overconfidence).
- **No calibration meetings.** Calibration is a human-manager ceremony; agents don't gather at a round table.
- **No 360 of the CEO.** CEO is reviewed by user, not by subordinate agents. Out of scope to re-litigate.

## Escalation triggers

- Round 1 research phase produces strong evidence (or lack of evidence) that multi-peer LLM feedback is redundant — skeptic's position becomes default; committee may close unanimously in round 1 with "reject 360, endorse cycle-outcome scoring".
- If round 3 splits on hybrid vs pure-reject, PROCEED with winner if confidence ≥ 0.80 (reversible — can always add 360 later).
