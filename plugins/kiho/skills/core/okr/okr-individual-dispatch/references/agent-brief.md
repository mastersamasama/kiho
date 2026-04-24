# agent-brief.md — the experience-using individual-O drafting brief

This is the canonical brief HR-lead sends to a candidate agent when dispatching them to draft their own individual Objective. The skill `okr-individual-dispatch` parameterizes this template at stage 2 and passes it as the sub-agent prompt.

The brief's load-bearing property: the agent **reads its own memory before drafting**. A draft whose rationale does not cite at least one memory/lesson ref is rejected structurally at stage 3 — not by the committee, by HR-lead's validator. This prevents drafts that could have been written by any agent and forces the individual O to reflect the actual individual.

## Template

Substitute `{…}` placeholders at dispatch time.

```
# Draft your individual OKR for {period}

You have been selected by HR-lead to draft an individual Objective for
{period}, aligned to the department Objective {dept_o.id} — "{dept_o.title}".

## Before drafting — read your own experience

Do these four reads in order. Do NOT skip. The draft's rationale section MUST
cite at least one ref from these reads.

1. **Your last 5 lessons.** Invoke:

   ```
   memory-query agent={self.id} kind=lesson limit=5 order=desc
   ```

   Each lesson is a generalized takeaway from past work — something you've
   concluded that future drafts should incorporate.

2. **Your pending todos.** Invoke:

   ```
   memory-query agent={self.id} kind=todo status=open
   ```

   If there are todos you've been meaning to address, an Objective that makes
   those todos concrete deadlines is often high-value.

3. **Your recent high-importance observations.** Invoke:

   ```
   memory-query agent={self.id} kind=observation importance>=7 limit=10
   ```

   Observations with importance ≥ 7 are the signals you flagged as
   structurally meaningful, not routine.

4. **Your role context.** Read `agents/{self.id}/agent.md` §Soul (your current
   identity) + §Skills (your portfolio) + the department O you're aligning to
   ({dept_o.path}).

## Draft shape

Propose exactly one Objective and 3-5 Key Results.

- **Objective (O)**: one sentence describing an outcome state to be true by
  the end of {period}. Must be owned-by-you achievable with your current
  skills portfolio + the skills you plan to learn. Must serve the dept-O.

- **Key Results (KRs)**: 3-5 items, each:
  - **id**: kebab-case, unique within this O
  - **description**: one sentence, measurable
  - **weight**: integer in [0, 100], all weights sum to ≤ 100
  - **direction**: `up` (higher = better) | `down` (lower = better) | `binary`
  - **stretch**: boolean; stretch KRs cap at 0.7 for aggregate purposes
  - **derivable_from_cycle_events**: boolean; AT LEAST ONE KR must be true

The `derivable_from_cycle_events: true` constraint means the KR's progress
can be computed from `cycle-events.jsonl` + `handoffs.jsonl` without you
needing to manually checkin — PR 3 of v6.2 (`bin/okr_derive_score.py`) will
auto-update it when cycles close. Examples: "5 cycles I own close on-budget",
"committee win rate ≥ 80% across committees I'm a member of", "zero cycles
aborted under my ownership this period".

## Return format

Return as structured JSON inside a single code block:

```json
{
  "period": "{period}",
  "owner": "{self.id}",
  "aligns_to": "{dept_o.id}",
  "objective": "...",
  "kr": [
    {
      "id": "...",
      "description": "...",
      "weight": 40,
      "direction": "up",
      "stretch": false,
      "derivable_from_cycle_events": true
    },
    ...
  ],
  "rationale_from_lessons": [
    "memory/lessons.md#<ref> — <one-line connection to this O>",
    "memory/observations.md#<ref> — <one-line connection>",
    ...
  ],
  "estimated_effort_fraction_of_period": 0.25,
  "risks_acknowledged": [
    "<one-line risk>",
    ...
  ]
}
```

## Do NOT

- DO NOT write the file yourself. The HR-lead + dept-lead + OKR-master will
  review your draft and, if approved, the dept-lead emits the
  DEPT_LEAD_OKR_CERTIFICATE and HR-lead invokes `okr-set level=individual`.
  Any direct Write to the OKR path is blocked by the PreToolUse hook.
- DO NOT propose an Objective that replicates what the dept-O already covers
  verbatim. Your individual O is your personal wedge INTO the dept-O, not a
  smaller copy of it.
- DO NOT cite a memory/lesson you haven't actually read — the validator
  cross-checks. Fabricated refs fail stage-3 validation.
- DO NOT propose > 5 KRs or weights summing > 100. The validator rejects both.
- DO NOT omit `rationale_from_lessons`. A draft without experience citation
  fails validation — it could have been written by any agent.

## Context bundle

For your reference while drafting:

- **Your self.id**: `{self.id}`
- **Your department**: `{self.dept}`
- **Period**: `{period}` (bounds: `{period.start}` to `{period.end}` exclusive)
- **Parent dept-O path**: `{dept_o.path}`
- **Parent dept-O KRs**: `{dept_o.kr_summary}`
- **agent-score for you** (if available): `{self.score}` (null = no prior period scored)
- **Your onboarded iterations**: `{self.onboard_iters}`
- **Prior individual O closed?**: `{self.has_prior_closed_okr}` (these four
  fields determine whether a user seat attends your review committee)

If any of the four "high-risk" flags are true (onboard_iters < 30, no prior
OKR, score < 0.70, or you propose 5 KRs), the review committee will include
a user seat. Be extra explicit about your experience citations — a user is
more likely to catch thin rationale.

## Stage flow reminder

1. **This brief** (you are here) — you draft.
2. HR-lead validates structural correctness.
3. Lightweight committee reviews (dept-lead + HR-lead + OKR-master + optional user).
4. On approve: dept-lead emits certificate; HR-lead invokes `okr-set`; file lands.
5. Throughout the period: cycles you own close → auto-checkin via cycle-runner hook → your KR scores update.
6. Period end: `okr-close` aggregates your KRs.
```

## Notes for the authoring skill (okr-individual-dispatch)

- The `{…}` placeholders are substituted from the HR-lead's context: `self.*` from agent.md + capability-matrix + agent-score; `dept_o.*` from the parent OKR file; `period.*` from period math.
- The brief is passed as the sub-agent's initial prompt. The sub-agent has full Agent-tool context (can Read, Grep, invoke `memory-query`); it does NOT have Write (prevented by not listing Write in the spawn's allowed tools) — it MUST return the draft via structured output, not by writing files.
- Structural validation at stage 3 is a JSON-shape check + memory-ref regex + weight-sum arithmetic. If the agent returns free-form prose instead of JSON, validation fails on first iteration and the agent gets the memo "structured JSON required, see brief".

## Why this works

- **Enforces introspection**. Without the memory-query step, drafts would be generic. With it, each agent's O reflects their actual trajectory in the org.
- **Auditable provenance**. The `rationale_from_lessons` array is a self-declared evidence trail. The committee can click through each ref.
- **Structural honesty**. The `derivable_from_cycle_events: true` requirement prevents "vibes-based KRs" — at least one metric must be machine-verifiable.
- **High-risk escalation**. The four flags (new agent, no prior O, low score, max KRs) trigger user review without requiring the user to proactively watch every draft.
