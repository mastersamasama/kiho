# Charter — pulse survey committee

## Committee identity

- **committee_id:** `pulse-surveys-2026-04-23`
- **topic:** "Should kiho have lightweight pulse polls distinct from committees?"
- **chartered_at:** 2026-04-23T15:30:00Z
- **reversibility:** reversible
- **knowledge_update:** true

## Members (quorum 3 of 4)

- **@kiho-hr-lead** — OA pulse surveys originate in HR; HR-lead owns the domain
- **@kiho-perf-reviewer** — pulse signal is adjacent to performance signal
- **@kiho-auditor-pragmatist** — the most likely challenger (is this just a committee with fewer members?)
- **@kiho-researcher** — brings the lightweight-poll design pattern from existing OA products into the room

Clerk: auto-assigned. Not a member.

## Input context

- User gap: Lark/DingTalk/Feishu support 1-question "how are you feeling this week?" / "did this process work?" polls with aggregate sentiment, distinct from formal deliberation.
- Gap score from `00-gap-analysis.md` §matrix row 4: **MEDIUM** — may be overlap with committee once scoped; committee may close with "not needed".
- kiho has `values-flag` (single-agent raising) and `committee` (heavyweight deliberation) but no non-blocking aggregate signal mechanism.

## Questions the committee MUST answer

| # | Question | Why it matters |
|---|---|---|
| Q1 | **Is there a meaningful gap?** Does `committee` with a reduced member set + single choose-phase already cover pulse? | Pragmatist's primary concern |
| Q2 | **Design shape if needed** — 1-question only or multi-question? Anonymous or attributed? Aggregate emitted when quorum responds or after deadline? | Design detail |
| Q3 | **Storage** — new `pulses/` directory? Extension of values-flag pattern? In-memory only (ephemeral)? | Must respect storage-architecture.md tier rules |
| Q4 | **Aggregation → action pipeline** — how does a pulse result feed into soul-override, values-flag escalation, or skill-deprecate? | Without this, pulse becomes decorative telemetry |
| Q5 | **Cadence** — every turn? Weekly cycle boundary? Triggered by specific events (post-incident, post-cycle)? | Cadence choice is the difference between "useful signal" and "noise" |
| Q6 | **How is it distinct from `values-flag`?** values-flag is a single agent raising; pulse is many agents answering | If indistinguishable in practice → close with "not needed" |

## Success criteria

Unanimous position that is one of:

- **Endorse introduction** — with concrete design: skill ID (e.g., `pulse-poll`), storage, aggregation trigger, cadence, and a clear delta from committee AND values-flag.
- **Reject with justification** — argue that existing primitives cover the workload; recommend any missing composition (e.g., "a 2-member committee with quorum 2 serves as a lightweight pulse; document that pattern in committee-rules as a named variant").
- **Partial endorse** — e.g., endorse a lightweight aggregation helper (`pulse-aggregate` reading existing values-flag jsonl) without a full new poll emission skill.

## Constraints + references

- `plugins/kiho/references/committee-rules.md` — the committee primitive this proposal must be distinct from OR gracefully compose with.
- `plugins/kiho/skills/core/values/values-flag/SKILL.md` — closest existing "agent raises a lightweight signal" primitive.
- `plugins/kiho/skills/core/values/values-alignment-audit/SKILL.md` — the aggregation step if pulse data feeds alignment.
- `plugins/kiho/references/soul-architecture.md` — if pulse results trigger soul-overrides, must fit the existing pipeline.
- `plugins/kiho/references/data-storage-matrix.md` — any new row requires Storage-fit follow-up.

## Out of scope (explicit)

- **No employee engagement surveys in the HR-product sense.** LLM agents don't have engagement to measure. The reframed question is: can aggregate agent signal on a process be useful (e.g., "after 10 recruit cycles under the v5.22 pre-emit gate, do agents find it blocking their work?")?
- **No anonymous pulse without a values-flag analog.** Anonymity + no escalation path = noise pool.
- **No production implementation.** Proposal only.

## Escalation triggers

- Round 1 reveals full overlap with existing primitives → close unanimously with "not needed" + document pattern in committee-rules.
- Round 3 still splits on Q4 (aggregation → action) → ASK_USER with the two competing positions.
