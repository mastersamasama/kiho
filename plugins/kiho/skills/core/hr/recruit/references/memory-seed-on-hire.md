# Phase 6 detail — memory seed at hire

This reference documents how recruit populates the hired agent's
`$COMPANY_ROOT/agents/<id>/memory/` directory with non-empty
`lessons.md`, `todos.md`, and `observations.md` at hire time.

## Why this exists

v5 careful-hire produced agents with empty `memory/` directories. The
first `memory-reflect` invocation on a new agent had nothing to read and
typically generated generic reflections. Per v6 plan §2 Cluster A2,
4 of 7 33Ledger agents shipped empty. v6 enforces non-empty seeds at
hire time — lint R5 rejects empty files in enforce mode (PR #3).

## Files seeded

```
$COMPANY_ROOT/agents/<id>/memory/
├── lessons.md       — semantic reflections, retention 180d
├── todos.md         — pending work items, no retention limit
├── observations.md  — episodic observations, retention 14d
└── .last-reflect    — ISO timestamp, epoch 0 at hire
```

## lessons.md seed

Semantic reflections the agent should remember across projects. Sourced
from the Phase 4 interview and the Phase 5 selection rationale.

Template:

```markdown
# Lessons — <agent_id>

> Seeded at hire on <iso_date>. Format: memory-reflect output shape.

## L-000 hire rationale

- **trigger:** hire_commit
- **confidence:** <rubric_avg_normalized_to_0_1>
- **observation:** You were hired for <role_generic>. Your rubric_avg was
  <rubric_avg>; you beat <top2_count> other candidates on <winning_dimensions>.
- **lesson:** Your distinguishing strength in the interview was
  <strongest_rubric_dimension> (score <score>). Double down on this when
  delegating decisions are close.
- **evidence:** [interview-transcript-<round>-<ts>]
- **tags:** [self-identity, hire-rationale]

## L-001 improvement target — <weakest_dimension>

- **trigger:** hire_commit
- **confidence:** <1.0 - weakest_dim_gap>
- **observation:** In Round <N> you scored <weakest_score> on
  <weakest_dimension>. Specifically, <specific_weakness_text>.
- **lesson:** When facing <pattern_that_triggered_weakness>, pause and
  <recommended_correction>. This is your first growth target.
- **evidence:** [interview-transcript-r<N>]
- **tags:** [growth, <weakest_dimension>]

## L-002 auditor dissent — <auditor_persona>

(one per auditor who dissented; skip if all 4 auditors agreed)

- **trigger:** hire_commit
- **confidence:** 0.75
- **observation:** The <persona> auditor dissented on your hire, citing
  <dissent_rationale>.
- **lesson:** Be aware that <persona>-style reviewers see <blind_spot> in
  your profile. When you work with <persona_aligned_colleague>, proactively
  address <blind_spot>.
- **tags:** [auditor-dissent, blindspot]

## L-003 work-sample reflection

- **trigger:** hire_commit
- **confidence:** <work_sample_score_normalized>
- **observation:** Your work-sample task was <work_sample_summary>. You
  approached it by <candidate_approach>. The auditors noted <auditor_feedback>.
- **lesson:** <generalized_takeaway>.
- **evidence:** [work-sample-transcript]
- **tags:** [work-sample, role-grounding]
```

**Minimum: 3 lessons (hire rationale + improvement target + work-sample).**
Empty lessons.md is a lint error.

## todos.md seed

Pending work items. Sourced from the role spec + work-sample residuals +
orientation needs.

Template:

```markdown
# Todos — <agent_id>

> Seeded at hire on <iso_date>. Format: memory-write todo schema.

## TODO-001 first-assignment orientation

- **priority:** high
- **due:** first assignment
- **status:** pending
- **description:** Read `$COMPANY_ROOT/company/wiki/index.md` and the
  entries tagged <capability_keywords_from_role_spec>. Then read the v5
  soul-architecture reference to internalize your own soul structure.
- **acceptance:** Be able to cite 3 company-wiki entries relevant to your
  role in your first reflection.

## TODO-002 first memory-reflect

- **priority:** medium
- **due:** after first 5 completed tasks
- **status:** pending
- **description:** Run memory-reflect to consolidate observations into
  lessons. Expected output: 2-3 new lessons, 0-1 reflections promoted.
- **acceptance:** lessons.md grows by at least 1 entry.

## TODO-003 work-sample residual — <subtask>

(one per unresolved sub-task from work-sample)

- **priority:** medium
- **due:** first wave on <active_project>
- **status:** pending
- **description:** The work-sample surfaced <specific_residual>.
- **acceptance:** <concrete_deliverable>.

## TODO-004 team-fit check

- **priority:** low
- **due:** after first collaborative task
- **status:** pending
- **description:** Review <teammate_agent_id>'s red lines (soul §4) and
  confirm no collaboration conflict. If any ambiguity, raise in a
  committee.
- **acceptance:** Either (a) confirm in journal "no conflict observed" or
  (b) file a committee agenda item.
```

**Minimum: 3 todos.** Empty todos.md is a lint error.

## observations.md seed

Episodic observations — what the agent noticed in its own interview.
Sourced verbatim (or near-verbatim) from the candidate's responses to
better preserve its own voice.

Template:

```markdown
# Observations — <agent_id>

> Seeded at hire on <iso_date>. Format: memory-write observation schema.

## O-000 (Round 1 — domain)

- **ts:** <iso_of_interview>
- **importance:** <round_1_rubric_normalized>
- **observation:** <paraphrased_first_person: the candidate's own take on
  the domain challenge it faced, from its transcript response>
- **tags:** [interview, domain, <domain_area>]

## O-001 (Round 2 — tools)

- **ts:** <iso>
- **importance:** <round_2_rubric_normalized>
- **observation:** <paraphrased_first_person: candidate's own reflection on
  which tool it chose and why>
- **tags:** [interview, tools]

## O-002 (Round 3 — edge case)

- **ts:** <iso>
- **importance:** <round_3_rubric_normalized>
- **observation:** <paraphrased_first_person: candidate's own reflection on
  how it handled ambiguity>
- **tags:** [interview, edge-case, uncertainty]

## O-003 (Round 4 — value hierarchy)

- **ts:** <iso>
- **importance:** <round_4_rubric_normalized>
- **observation:** <paraphrased_first_person: candidate's own articulation
  of its value hierarchy under pressure>
- **tags:** [interview, values, self-identity]

## O-004 (Round 5 — team-fit)

- **ts:** <iso>
- **importance:** <round_5_rubric_normalized>
- **observation:** <paraphrased_first_person: candidate's own reflection on
  collaborating around another agent's red line>
- **tags:** [interview, collaboration, red-lines]

## O-005 (Round 6 — self-reflection)

- **ts:** <iso>
- **importance:** <round_6_rubric_normalized>
- **observation:** <paraphrased_first_person: candidate's own naming of its
  blindspots>
- **tags:** [interview, self-awareness, blindspots]

## O-006 (work-sample)

- **ts:** <iso>
- **importance:** <work_sample_rubric_normalized>
- **observation:** <paraphrased_first_person: candidate's own reflection on
  the held-out real-job task>
- **tags:** [work-sample, role-grounding]
```

**Minimum: 5 observations** (5 of 7 interview rounds — even when some score
below 3.0, the observation is still seeded so the agent remembers the low
point). Empty observations.md is a lint error.

## .last-reflect

Plain-text ISO timestamp file:

```
1970-01-01T00:00:00Z
```

Epoch 0 seeds the memory-reflect cadence. On the agent's first CEO
INITIALIZE after hire, `memory-reflect` will fire (age_at_trigger >
`reflection_task_interval * 60` seconds since epoch 0).

## Authoring responsibility

Who writes these files?

- `design-agent` Step 7 creates the memory directory (`mkdir -p`).
- `recruit` Phase 6 composes the seed content from interview transcripts
  AND writes the files.
- This split exists because the seeding logic is recruit-owned (it needs
  the interview output) but the directory creation is design-agent-owned
  (as part of agent provisioning).

## Interaction with lint

`bin/agent_md_lint.py` R5 checks:

1. `memory_path` directory exists
2. `lessons.md` present, size > 0
3. `todos.md` present, size > 0
4. `observations.md` present, size > 0

Empty files fail R5. In PR #2 lint runs warn-only; in PR #3 enforce mode,
hire rolls back.

## Interaction with `settings.recruit.memory_seed_on_hire`

If `memory_seed_on_hire == false` (user override), Phase 6 is SKIPPED. The
agent.md is written with `memory_path` pointing to an empty directory. Lint
R5 will warn/error on the next audit. This is an intentional footgun —
teams that disable seeding are signalling they'll backfill via
memory-reflect on first turn.

## Anti-patterns

- **MUST NOT** write placeholder stubs like "TODO: seed later". The point
  of seeding is that the files are useful on turn 1.
- **MUST NOT** generate synthetic observations that weren't in the
  interview. Use the candidate's actual responses.
- **MUST NOT** copy-paste lessons across all hires. Each hire's lessons
  are specific to its own interview performance.
- Do not mix formats — `lessons.md` uses the memory-reflect schema,
  `observations.md` uses memory-write observation schema. Future
  memory-reflect runs will break if formats drift.
- Do not skip the .last-reflect file. Without it the first memory-reflect
  will compute age from a missing file and may fail silently.
