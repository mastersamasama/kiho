---
name: recruit
description: Unified v6 recruitment protocol — one flow, 4 candidates always. Produces a role-spec stub, runs a design-validate-fill-validate loop that authors any missing skills BEFORE agents are drafted, emits 4 diverse candidates, reconciles their proposed skill lists across the company library (dedupe, deprecate, improve, author), interviews all 4 via interview-simulate, selects a winner with optional synthesis when top-2 are complementary, and seeds the hired agent's memory with interview-derived lessons/todos/observations. Replaces v5 quick-hire / careful-hire split. Use when a capability gap is detected (RACI fail on a plan item OR mid-wave CEO capability gap), when HR-lead is invoked with `op=auto-recruit`, or when a department needs new capacity. Governed by `settings.recruit.*` — when `auto_trigger_on_gap` is false falls back to v5 ASK_USER on gap.
metadata:
  trust-tier: T2
  version: 3.0.0
  lifecycle: active
  kiho:
    capability: create
    topic_tags: [hiring, gap-healing, skill-authoring]
    data_classes: ["recruit-role-specs", "agent-md", "agent-souls", "skill-definitions"]
    storage_fit:
      reads: ["$COMPANY_ROOT/settings.md", "$COMPANY_ROOT/skills/**", "$COMPANY_ROOT/skills/INDEX.md", "$COMPANY_ROOT/project-registry.md", "<project>/.kiho/state/capability-matrix.md"]
      writes: ["$COMPANY_ROOT/agents/<id>/agent.md", "$COMPANY_ROOT/agents/<id>/memory/{lessons,todos,observations}.md", "$COMPANY_ROOT/skills/<id>/SKILL.md (via skill-derive)", ".kiho/state/recruit/<slug>/role-spec.md"]
---
# recruit (v6)

The **universal gap-healing reflex**. When the CEO encounters a capability no
current agent can cover, this skill produces a role-specification, iteratively
designs an ideal agent persona while authoring any missing skills, drafts four
diverse candidates, reconciles their skill proposals against the company
library, interviews all four, and hires one (or a synthesis of the top two)
with seeded memory.

v6 collapses the v5 `quick-hire` / `careful-hire` split. There is one flow.
The hard minimum is **four candidates, always**. Governed by
`$COMPANY_ROOT/settings.md` `[recruit]` and plugin `config.toml` `[recruit]`
fallback.

## When to use

Invoke this skill when:

- `kiho-ceo` INITIALIZE step 11 detects a RACI gap AND
  `settings.recruit.auto_trigger_on_gap == true`
- `kiho-ceo` LOOP step b/c enumerates `required_skills` and at least one is
  absent from `$COMPANY_ROOT/skills/`
- `kiho-hr-lead` is invoked with `op=auto-recruit` and a capability brief
- A department leader files a documented headcount request

Do NOT invoke this skill when:

- A **skill** (not an agent) is the sole deliverable — call `skill-derive`
  directly; the gap-healing path in Phase 2 already wraps it
- An existing agent needs behavioral changes — use `skill-improve` or
  `soul-apply-override` on the agent's soul
- `settings.recruit.auto_trigger_on_gap == false` AND the gap is ambiguous —
  fall back to the v5 behaviour (ASK_USER with the role spec draft)

## Non-Goals

- **Not a skill author in isolation.** Recruit owns the wrapper flow; skill
  authoring is delegated to `skill-derive` inside Phase 2.
- **Not a registry.** `org-sync` + `$COMPANY_ROOT/agents/INDEX.md` own runtime
  lookup; recruit writes agent.md and hands off.
- **Not a drift monitor.** Post-deploy persona drift is `memory-reflect`.
- **Not a pool of 1, 2, or 3.** Four is the hard minimum per user direction
  and `settings.recruit.min_candidates_always`.
- **Not an emitter of empty memory.** Phase 6 seeds `lessons.md`, `todos.md`,
  and `observations.md` with non-empty content; lint R5 rejects otherwise.

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** are
to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and
only when, they appear in all capitals.

## Inputs

```
op:            auto-recruit | reassess
role_brief:    <free text — what capability is missing / what the agent must do>
requestor:     <agent-id> (usually ceo-01 or a dept lead)
trigger:       raci_gap | midwave_skill_gap | dept_headcount | user_request
capability_gap: [<skill_description_1>, ...]   # from CEO if available
conditions:    <optional constraints — tool floor, model cap, budget>
settings:      <inline `recruit.*` overrides; else read from $COMPANY_ROOT/settings.md>
```

## Phase 0 — Load settings

1. Read `$COMPANY_ROOT/settings.md` frontmatter. Merge `[recruit]` section over
   plugin `config.toml` `[recruit]` fallback. Required keys resolved:
   - `auto_trigger_on_gap` (default `true`)
   - `min_candidates_always` (default `4`, cannot be lowered)
   - `committee_gate_threshold` (default `4.0`)
   - `synthesis_when_complementary` (default `true`)
   - `synthesis_rubric_delta_max` (default `0.20`)
   - `memory_seed_on_hire` (default `true`)
   - `max_auto_recruits_per_turn` (default `2`)
   - `skill_research_before_design` (default `true`)
   - `max_skills_authored_per_recruit` (default `3`)
   - `max_design_iterations` (default `3`)
2. If `settings.recruit.auto_trigger_on_gap == false` AND `op == auto-recruit`
   coming from a RACI / mid-wave trigger → emit `status: v5_fallback_required`
   with the draft `role-spec.md` attached and return. CEO then runs its legacy
   v5 ASK_USER path.
3. Check the turn's `.kiho/state/ceo-ledger.jsonl` for prior
   `action: auto_recruit_started` entries in this turn. If count ≥
   `max_auto_recruits_per_turn` → emit `status: runaway_guard_hit` and
   ASK_USER via the CEO before proceeding.

## Phase 1 — Role spec STUB

**MUST** run before any candidate is drafted. v5 produced a full four-field
contract; v6 produces a **stub** — no skill enumeration, because Phase 2's
design-validate-fill-validate loop is where skills emerge.

Write `.kiho/state/recruit/<slug>/role-spec.md` with:

```yaml
role_spec:
  objective:       <one sentence — what the hired agent must accomplish>
  output_format:   <artifact shape — code | report | decision | routing | review>
  tool_boundaries: <must-have / must-not-have tools; model floor or cap>
  termination:     <completion criteria — how the leader knows a turn ended>
  scaling_rule:    <expected invocation depth + fanout>
  work_sample:     <one held-out real-job task — used in Phase 4 Round 7>
  # v6 additions:
  capability_keywords: [<free-text descriptors — NOT skill IDs yet>]
  diversity_axes_required: 3   # candidates must differ on all three
```

No `required_skills:` yet. Design-agent proposes skills in Phase 2. This
prevents anchoring and lets the agent designer think freshly about what the
ideal professional needs.

## Phase 2 — Design-validate-fill-validate loop (CORE REFLEX)

Iterate at most `settings.recruit.max_design_iterations` times (default 3).
Output is a **validated recipe**: a persona + skill list where every skill ID
resolves to `$COMPANY_ROOT/skills/<id>/SKILL.md`.

```
for iteration in 1..max_design_iterations:

  2.1 THINK — invoke design-agent op=propose_recipe with the role-spec stub.
      Returns:
        - persona_draft { role_generic, role_specialties, soul_traits_hint }
        - wanted_skills [ { id_hint, description, feature_list, rationale } ]
        - skill_id_hints must be kebab-case `sk-*` but need not exist yet

  2.2 DESIGN — design-agent emits a draft agent.md with skills set to the
      `id_hint` values. IDs are UNRESOLVED at this stage.

  2.3 VALIDATE skills — for each wanted_skill:
        resolved = Path($COMPANY_ROOT / "skills" / id_hint / "SKILL.md").exists()
        if resolved:
          read SKILL.md; compute feature_coverage(wanted.feature_list, skill.features)
          if feature_coverage >= 0.80: mark "resolved_reuse"
          elif feature_coverage < 0.40: mark "conflict_narrow"  # existing too narrow
          else:                        mark "partial_reuse"     # candidate may want IMPROVE
        else:
          # v6.0.1 Fix P1 — semantic pre-check BEFORE marking "to_author".
          # Avoids authoring a new skill when an existing library entry with a
          # different ID already covers the same semantic territory.
          if Path($COMPANY_ROOT / "skills" / "unified-search" / "SKILL.md").exists():
            neighbor = unified-search(
              query: wanted.description,
              scope: ["skills"],
              limit: 3,
              min_score: 0.70
            )
            if neighbor and neighbor[0].score >= 0.75:
              mark "resolved_reuse" with suggested_skill_id = neighbor[0].skill_id
              rewrite wanted.id_hint := neighbor[0].skill_id  # rename candidate ref
              Log: action: skill_semantic_match_in_validate, original: <id_hint>,
                   matched: <neighbor[0].skill_id>, score: <neighbor[0].score>.
              continue
          mark "to_author"   # no Path match AND no semantic neighbor → Phase 2.4

  2.4 FILL BACK — for each mark in {to_author, conflict_narrow, partial_reuse}:

    authored_count = count(mark == to_author OR creates new ID via conflict)
    if authored_count > settings.recruit.max_skills_authored_per_recruit:
      emit status: too_many_skills_needed
      ASK_USER via CEO to (a) split role, (b) raise cap, (c) narrow wanted list

    for each wanted_skill where mark in {to_author, conflict_narrow}:
      2.4a-EXTERNAL  (v6.0.1 — Fix P2)
            If settings.external_skills.allow_references == true AND
               $COMPANY_ROOT/external-skills-catalog.json exists:
              catalog = load($COMPANY_ROOT/external-skills-catalog.json)
              for candidate in catalog.discovered_skills:
                similarity = embedding_util.text_similarity(
                                 wanted.description, candidate.description)
                if similarity >= 0.75:
                  record external_reference_candidate = {
                    type: plugin_skill,
                    plugin: candidate.plugin,
                    skill_id: candidate.skill_id,
                    similarity_score: similarity,
                    purpose: wanted.rationale
                  }
                  Log: action: external_reference_candidate_matched,
                       wanted_id: <id_hint>, matched: <plugin:skill_id>,
                       similarity_score: <similarity>.
                  SKIP kiho-researcher + skill-derive for this wanted_skill;
                  in Phase 2.5 substitute by authoring a thin wrapper skill
                  whose frontmatter carries
                  `references: [{type: plugin_skill, plugin, skill_id}]`
                  (per references/skill-frontmatter-schema.md §references:).
                  break
            Else (no external match OR catalog missing OR setting off):
              proceed to 2.4a (kiho-researcher → skill-derive legacy path).

            Mirrors design-agent Step 2.3 (lines 123-150) — the two paths now
            have equivalent external-catalog behavior.

      2.4a  Invoke kiho-researcher with query built from wanted.description +
            wanted.feature_list (uses KB → trusted sources → web → deepwiki →
            clone → ask_user cascade). Budget: respect
            settings.external_skills.allow_references and settings.performance.*.

      2.4b  Researcher returns { findings, citations, synthesis_draft }.

      2.4c  Invoke skill-derive with
              { parents: [], use_case: wanted.description,
                seed_findings: findings, proposed_name: wanted.id_hint,
                rationale: wanted.rationale }
            Skill-derive emits $COMPANY_ROOT/skills/<id>/SKILL.md and may add
            references/ + scripts/ + spec shots. Frontmatter lifecycle=draft.

      2.4d  Invoke kiho-kb-manager op=kb-add page_type=entity to register the
            new skill; it updates $COMPANY_ROOT/skills/INDEX.md.

    for each wanted_skill where mark == partial_reuse:
      2.4e  Invoke skill-improve with
              { skill_id: id_hint,
                proposed_delta: wanted.rationale + wanted.feature_list,
                committee_mode: light }
            skill-improve handles the self-improvement committee gate; if
            approved, bumps semver on the SKILL.md.

  2.5 VALIDATE AGAIN — re-read every wanted_skill.id_hint file. Zero
      unresolved permitted. If any still missing after fill-back (researcher
      cost cap hit / user rejected during ASK_USER path / researcher could not
      find seed material):
        option (a) REVISE persona — design-agent drops the unresolvable skill
                   or substitutes an adjacent available skill; go to 2.1 with
                   the updated wanted list
        option (b) ESCALATE — return status: skill_fill_blocked with the
                   specific missing skill IDs; CEO decides whether to ASK_USER

  2.6 LOOP CONTROL — if design-agent made any REVISE in 2.5, restart at 2.1.
      Exit loop when:
        (a) all wanted_skills resolve AND design-agent reports
            persona_satisfied: true
        (b) iteration == max_design_iterations → ESCALATE with the last draft
```

Detailed heuristics, feature-coverage scoring, and edge cases:
`references/skill-gap-resolution.md`.

After Phase 2 exits cleanly: we hold one validated **recipe** (persona +
resolved skill list). Phase 3 uses it as the brief for multi-candidate
generation.

## Phase 3 — Produce 4 candidates (ALWAYS 4)

Four is the hard minimum per `settings.recruit.min_candidates_always`. If the
setting is raised (e.g., 6), produce that many; never fewer than 4.

```
3.1  Using the Phase 2 recipe as the brief, spawn design-agent × 4 IN PARALLEL.
     Each spawn receives the same role-spec + recipe but a distinct
     diversity prompt targeting a different axis emphasis:

       Candidate 1 — seniority-emphasis: experienced, conservative soul
       Candidate 2 — seniority-emphasis: mid-level, autonomous soul
       Candidate 3 — philosophy-emphasis: safety-first, refusal-heavy Big Five
       Candidate 4 — specialty-emphasis: breadth over depth, high Openness

3.2  Each candidate proposes its OWN final persona + skill list. It MAY
     extend the Phase 2 skill recipe with additional skills it wants, or
     narrow (drop skills it does not need for its philosophy). Candidates
     do NOT author skills themselves — they declare `skills_wanted` with
     features; Phase 3.5 reconciles.

3.3  Each candidate runs its own inline design-agent Steps 1-7 (persona,
     soul, coherence check, tool allowlist, team-fit). Candidates that fail
     their own pass gates (coherence < 0.70, tool-alignment < 0.70, etc.)
     are REGENERATED up to 2 times; final failure → ESCALATE with the
     candidate's failure report.

3.4  Diversity enforcement: after all 4 land, recruit MUST verify they
     differ on all 3 axes (seniority OR philosophy OR specialty — Big Five
     spread ≥ 3 on at least one dimension for each candidate pair). If two
     candidates are too similar, regenerate the younger.
```

Output of Phase 3: 4 candidate drafts under
`.kiho/state/recruit/<slug>/candidates/{1,2,3,4}/agent.md.draft` — each a
fully-formed v2 agent.md except for the `skills[]` list, which may still
contain unresolved `id_hint` entries from Step 3.2 extensions.

## Phase 3.5 — Cross-candidate skill reconciliation

**New in v6.** Before interviews, converge the 4 candidates' skill proposals
into a clean, conflict-free set in `$COMPANY_ROOT/skills/`. Without this step,
candidate A authors `sk-visual-qa-playwright` and candidate B authors
`sk-visual-regression-testing` in parallel, polluting the library with
near-duplicates.

```
3.5.1  UNION
  proposed_skills = ⋃ for c in candidates { c.skills_wanted }

3.5.2  For each unique skill_id_hint in proposed_skills:
  existing = load($COMPANY_ROOT/skills/<id>/SKILL.md) or None
  if existing and feature_coverage(wanted.features, existing.features) >= 0.80:
    action = RESOLVED_REUSE
  elif existing and feature_coverage < 0.40:
    action = CONFLICT_NARROW     # existing skill too narrow → propose IMPROVE or AUTHOR_NEW
  elif existing is None:
    # v6.0.1 Fix P3 — real unified-search call, no pseudocode.
    # Uses `semantic_neighbor_exists(wanted.description)` helper whose concrete
    # python-style implementation lives in references/skill-reconciliation.md
    # §3.5.2 (calls unified_search scope=[skills], min_score=0.70).
    neighbor = semantic_neighbor_exists(wanted.description)   # (skill_id, score) | None
    if neighbor is not None:
      action = NAMING_CONFLICT   # similar-domain skill has different ID → dedupe names
    else:
      action = AUTHOR_NEW
  else:
    action = AUTHOR_NEW

3.5.3  DEDUPE proposals among candidates themselves:
  # v6.0.1 Fix P3 — `feature_overlap(A, B)` is the concrete helper from
  # references/skill-reconciliation.md §3.5.3 that calls
  # embedding_util.text_similarity over joined feature-list strings.
  for (wanted_A, wanted_B) where feature_overlap(A.features, B.features) >= 0.70
                               AND A.candidate != B.candidate:
    merge into a single skill with features = A.features ∪ B.features
    both candidates' skills_wanted lists now reference the merged ID
    record in .kiho/state/recruit/<slug>/reconciliation-ledger.jsonl

3.5.4  DEPRECATE existing:
  for each existing skill id where:
    combined_coverage(candidates' proposals against existing.features) >= 0.95
    AND existing.quality_score <= 0.60                # quality from skill-performance.jsonl
    AND existing.lifecycle in {draft, active}
    AND not any_agent_depends_on(existing)
  →  invoke kiho-kb-manager op=kb-update on existing SKILL.md:
       frontmatter: deprecated: true, superseded_by: <new_or_merged_id>
     existing agents pointing to it are re-pointed at next memory-reflect

3.5.5  IMPROVE existing:
  for each existing skill where coverage in [0.60, 0.80) AND some candidate
  adds a clearly-useful feature:
    invoke skill-improve with { skill_id, proposed_delta: candidate_rationale }
    on approval, bump semver; all 4 candidates' skills_wanted updated to
    reference the improved version

3.5.6  AUTHOR truly-new:
  for each wanted where action == AUTHOR_NEW (after 3.5.3 dedupe collapses):
    reuse Phase 2.4 flow — kiho-researcher → skill-derive → kb-manager kb-add
    respect settings.recruit.max_skills_authored_per_recruit total budget
    (Phase 2 authorings + Phase 3.5 authorings summed)

3.5.7  RESOLVE candidate agent.md files:
  for each candidate:
    replace c.skills_wanted with the final resolved ID list from 3.5.2-3.5.6
    validate every ID resolves to $COMPANY_ROOT/skills/<id>/SKILL.md
    any unresolved → hard fail; Phase 2 is the only place unresolved IDs are
    allowed to live

3.5.8  Update $COMPANY_ROOT/skills/INDEX.md with additions, version bumps,
       and deprecations. Library is now conflict-free.
```

Detailed heuristics, scoring formulas, and tie-breaking rules:
`references/skill-reconciliation.md`.

## Phase 4 — Interview

Four candidates × four rounds = 16 interview runs, plus work-sample run.
Recruit compiles a `test_suite` from `references/interview-rounds.md` +
appended work-sample test and hands it to `interview-simulate(mode: full)`
per candidate. Recruit does not spawn interviewers inline.

Rounds (as in v5 careful-hire — see `references/interview-rounds.md`):

1. **r1-domain** — core domain knowledge (accuracy-weighted)
2. **r2-tools** — tool proficiency (tool_use-weighted)
3. **r3-edge** — ambiguous / adversarial input (refusal-weighted)
4. **r4-coherence** — value-hierarchy under pressure *(hard gate ≥ 4.0)*
5. **r5-team-fit** — red-line conflict with an existing teammate *(hard gate ≥ 4.0)*
6. **r6-reflection** — self-improvement reflection
7. **r7-work-sample** — the held-out task from role-spec.work_sample
8. **r8-drift** — 3× replay of a r1-variant; drift must be ≤ 0.20

Auditors: 4 personas spawned from `agents/kiho-auditor.md`:

- **Skeptic** (Agreeableness 2, Neuroticism 7)
- **Pragmatist** (Conscientiousness 6, Openness 5)
- **Overlap hunter** (Conscientiousness 8, Openness 4)
- **Cost hawk** (Conscientiousness 9, Neuroticism 5)

Each auditor reviews all 4 candidates' interview-simulate transcripts.

### Rubric & floors (unchanged from v5 careful-hire)

6-dimension rubric (Accuracy, Clarity, Persona fit, Tool use, Refusal,
Work-sample) with per-dim floors:

| Dim | Floor |
|---|---|
| Accuracy | 3.5 |
| Clarity | 3.0 |
| Persona fit | 4.0 |
| Tool use | 3.5 |
| Refusal | 4.0 |
| Work-sample | pass |

Composite: `rubric_avg >= 4.0 AND worst_dim >= 3.5 AND r4 >= 4.0 AND r5 >= 4.0 AND drift <= 0.20`.

## Phase 5 — Selection with SYNTHESIS

```
5.1  Rank candidates by rubric_avg. Read top1, top2.

5.2  delta = top1.score - top2.score

5.3  if settings.recruit.synthesis_when_complementary == true AND
        delta <= settings.recruit.synthesis_rubric_delta_max AND
        strength_overlap(top1, top2) is "small" (< 0.50 Jaccard on role_specialties):

       5.3a  Invoke design-agent op=synthesize_candidates with
               { top1: candidate_1, top2: candidate_2, role_spec, recipe }
             Produces a merged persona:
               role_generic:       top1.role_generic  (tie-break: more recently
                                                       authored tokens win)
               role_specialties:   top1.specialties ∪ top2.specialties
               skills:             top1.skills ∪ top2.skills  (re-validate via
                                                               Phase 3.5 dedupe)
               Big Five:           weighted mean, weight = rubric_avg per trait
                                   subject to coherence constraints
               values:             top-3 of (top1.values ∪ top2.values) ranked
                                   by combined rubric_avg contribution
               red_lines:          union (never narrows a red line)

       5.3b  Run a fresh Phase 4 interview suite against the synthesized
             candidate. Same test suite, same auditors.

       5.3c  if synth.rubric_avg >= max(top1.rubric_avg, top2.rubric_avg):
               hired = synthesized candidate
               hire_provenance.hire_type = "v6-synthesis"
             else:
               hired = top1
               hire_provenance.hire_type = "v6-auto-recruit"

     else:
       5.4  hired = top1
            hire_provenance.hire_type = "v6-auto-recruit"

5.5  Deploy the winner (Phase 6). Close out losers via rejection-feedback
     (inherited from v5) for memory-retained axis breakdowns.
```

Detail: `references/candidate-synthesis.md`.

## Phase 6 — Memory seed + intake

**New in v6.** Every hired agent `MUST` land with non-empty memory files.
Governed by `settings.recruit.memory_seed_on_hire == true` (default).

```
6.1  Create memory/ at $COMPANY_ROOT/agents/<id>/memory/
     (directory MUST exist — design-agent creates it at Step 7).

6.2  Seed lessons.md from the interview:
       - 1 lesson per rubric dim where the candidate scored < 4.5 ("IC must
         improve on <dim> — observed in r<round> — see transcript at <path>")
       - 1 lesson per auditor dissent
       - 1 "hire rationale" lesson summarizing why THIS candidate won over
         the other three (cite rubric_avg, strength deltas, synthesis path)
     Format matches memory/lessons.md schema from v5 memory-reflect output.

6.3  Seed todos.md from the work-sample + role-spec:
       - 1 todo per unresolved sub-task the work-sample surfaced
       - 1 orientation todo: "Read $COMPANY_ROOT/company/wiki/index.md and
         the referenced entries tagged <capability_keywords>"
       - 1 reflection todo: "After first wave, invoke memory-reflect to
         consolidate observations into lessons"

6.4  Seed observations.md from interview transcripts:
       - per-round 1-sentence observation extracted from the candidate's
         own response (what IT noticed while answering)
       - Keep verbatim tone; these are the agent's episodic seed memories

6.5  Set current_state:
       availability: "engaged"   (if active_project is being assigned this turn)
                     or "free"   (if hiring proactively without immediate assignment)
       active_project: <project_id or null>
       active_assignment: <wave/plan-item id or null>
       last_active: <iso_timestamp_utc>

6.6  Run bin/agent_md_lint.py against the finished agent.md:
       python ${CLAUDE_PLUGIN_ROOT}/bin/agent_md_lint.py \
         <agent_md_path> --company-root $COMPANY_ROOT
     In PR #2 the lint runs in warn-only mode; log any warnings to ledger as
       action: agent_md_lint_warning, rule: <RN>, message: <...>
     In PR #3 the lint runs in enforce mode and a failure rolls back the hire.
```

Detail: `references/memory-seed-on-hire.md`.

## Pre-emit gate (carried forward from v5.22)

Before writing the final `agent.md` to `$COMPANY_ROOT/agents/<id>/agent.md`,
recruit **MUST** confirm all of the following artifacts exist AND are
non-stale (created within this recruit session):

1. `role-spec.md` with Phase 1 four-field contract complete
2. Phase 2 validated recipe with zero unresolved skill IDs
3. Phase 3.5 reconciliation ledger with zero conflicts remaining
4. `interview-simulate` transcripts for 4 candidates (+ synth if triggered)
5. 4 auditor reviews captured
6. Phase 6 memory seed: `lessons.md`, `todos.md`, `observations.md` each
   exist and > 0 bytes
7. `rejection-feedback` written for every non-winning candidate

If ANY is missing, abort with:

```json
{ "status": "pre_emit_gate_failed", "missing": [<item-ids>] }
```

The emitted `agent.md` MUST include a `RECRUIT_CERTIFICATE:` HTML comment as
its first content (per v5.22 `pre_write_agent` PreToolUse hook contract):

```markdown
<!-- RECRUIT_CERTIFICATE:
       kind: v6-auto-recruit | v6-synthesis
       role_spec: <path>
       candidate_slug: <slug>
       interview_score: <aggregate_mean>
       committee_status: approved
       synthesis_applied: <bool>
       skills_authored_this_hire: [<ids>]
       skills_improved_this_hire: [<ids>]
       skills_deprecated_this_hire: [<ids>]
       emitted_at: <iso_timestamp>
-->
---
schema_version: 2
name: <agent_name>
...
```

## Phase 6.5 — Post-hire org sync + KB registration

After every successful hire:

1. Invoke `org-sync` with `event_type: hire`, agent_id, department, skills
   authored/improved this hire, rubric_score, synthesis_bool. Updates
   `$COMPANY_ROOT/agents/INDEX.md` + capability matrix.
2. Invoke `kiho-kb-manager op=kb-add page_type=entity` for the new agent
   (description, department, capabilities, reports-to, model tier).
3. Append to `<project>/.kiho/state/management-journals/<requestor>.md`:
   hire rationale + authored skills + deprecated skills.
4. Log `action: auto_recruit_complete, hired: <agent_id>, candidates: 4,
   synthesized: <bool>, skills_authored: <n>, skills_improved: <n>,
   skills_deprecated: <n>` to `.kiho/state/ceo-ledger.jsonl`.

If any registration step fails, log the failure but do not roll back the
deploy — the agent.md and memory exist; subsequent runs re-sync via
`org-sync`.

## Response shape

```json
{
  "status": "ok | v5_fallback_required | runaway_guard_hit | too_many_skills_needed | skill_fill_blocked | pre_emit_gate_failed | committee_rejected | error",
  "hired": {
    "agent_id": "eng-visual-qa-ic-01",
    "agent_path": "$COMPANY_ROOT/agents/eng-visual-qa-ic-01/agent.md",
    "rubric_score": 4.38,
    "hire_type": "v6-auto-recruit | v6-synthesis",
    "memory_seeded": true,
    "recruit_certificate_present": true
  },
  "candidates_evaluated": 4,
  "synthesized": false,
  "skills_authored": ["sk-visual-qa-invariants", "sk-screenshot-diff"],
  "skills_improved": [],
  "skills_deprecated": [],
  "rejected_candidates": ["candidate-2", "candidate-3", "candidate-4"],
  "reconciliation_ledger": ".kiho/state/recruit/<slug>/reconciliation-ledger.jsonl",
  "role_spec_path": ".kiho/state/recruit/<slug>/role-spec.md",
  "new_questions": [],
  "escalate_to_user": null
}
```

## Failure playbook

| Failure | Route |
|---|---|
| `settings.recruit.auto_trigger_on_gap == false` | Return `v5_fallback_required`; CEO runs v5 ASK_USER path |
| `max_auto_recruits_per_turn` exceeded | Return `runaway_guard_hit`; CEO ASK_USER |
| Phase 2 researcher cannot find seed material | ESCALATE; design-agent REVISES persona and retries; final failure → `skill_fill_blocked` |
| Phase 3 candidate fails own pass gates 2× | Regenerate; on third failure → `committee_rejected` |
| Phase 3.5 conflicts unresolvable | ASK_USER with the conflict map; require user to pick keep/merge/author-new per row |
| Phase 4 no candidate hits composite threshold | Return `committee_rejected`; CEO may ask user to widen role spec |
| Phase 5 synth fails to exceed top1 | Hire top1; log synthesis_failed |
| Phase 6 lint warn in PR #2 | Log warnings; proceed. In PR #3 enforce mode, rollback hire |
| `pre_emit_gate_failed` | Surface missing-items list; do not write agent.md |

## Interaction with existing v5.22 machinery

- `pre_write_agent` PreToolUse hook: still active. The v6
  `RECRUIT_CERTIFICATE:` marker includes new fields (hire_type,
  synthesis_applied, skills_*_this_hire) — the hook regex is a superset
  matcher, already permissive.
- `bin/ceo_behavior_audit.py` DONE step 11: v6 emits
  `action: auto_recruit_complete` with matching hire_provenance; audit
  continues to flag unpaired recruit intents as drift.
- `interview-simulate(mode: full)`: called per candidate AND per synthesized
  candidate. Interface unchanged.
- `rejection-feedback`: called for all non-winning candidates including
  top1 when synth wins.

## Anti-patterns

- **MUST NOT** skip Phase 1 stub. Pre-enumerated `required_skills` anchors
  design-agent to what already exists; the whole point of v6 is that the
  designer thinks freshly about what the ideal agent needs.
- **MUST NOT** run Phase 2 fill-back without honoring
  `max_skills_authored_per_recruit`. A recruit that authors 10 new skills is
  not a recruit — it's a library sprint.
- **MUST NOT** generate fewer than 4 candidates. `min_candidates_always` is
  a hard floor.
- **MUST NOT** skip Phase 3.5 reconciliation. Shipping 4 candidates whose
  skill lists pollute the library with near-duplicates is the main failure
  mode this whole flow exists to prevent.
- **MUST NOT** hire with empty memory. Phase 6 seed is non-optional.
- Do not run Phase 5 synthesis when top-2 strengths overlap heavily —
  synthesis only helps when the two candidates are **complementary**, not
  when they're the same agent with different names.
- Do not author a new skill in Phase 3.5 that would have been found by
  Phase 2 had design-agent looked — run Phase 3.5.2's semantic neighbor
  check with `semantic_neighbor_exists`.
- Do not let researcher spin indefinitely. Phase 2.4a honors
  researcher's own budget; at budget exhaustion, design-agent REVISES.

## Rejected alternatives

### A1 — Restore v5 quick-hire / careful-hire split

Rejected — the split was tier-based but user direction is *"4 candidates
always"* without exception. Two tiers create a selection problem (which
tier for which role?) that the universal reflex eliminates.

### A2 — Author all candidate-proposed skills independently, dedupe later

Rejected — the point of Phase 3.5 is to CONVERGE before interviews so
interview results reflect final-library skill coverage. Deferring to post-
hire cleanup lets the library accumulate near-duplicates that are hard to
merge after agents already depend on both.

### A3 — Run Phase 2 fill-back per-candidate rather than pre-candidate

Rejected — causes 4× the authoring traffic, compounds researcher budget,
and produces 4 conflicting skill versions that Phase 3.5 must then reconcile.
Phase 2 produces the shared recipe; Phase 3.5 reconciles extensions.

## Grounding

- **Four-candidate hard floor.** User direction: *"4 is absolute minimum
  always."* Matches MAST FM-1 evidence (Cemri et al., arXiv 2503.13657) that
  3+ heterogeneous candidates break correlated-error failure mode; 4 gives
  the synthesis path material to work with.
- **Synthesis when complementary.** User direction and Anthropic harness
  doctrine (`references/ralph-loop-philosophy.md`): merging two strong
  imperfect agents into one better agent is cheaper than interviewing a
  fifth candidate from scratch.
- **Phase 2 design-validate-fill-validate.** User direction: *"think what
  skill that agent need, design agent, validate, fill back skill,
  validate."* Encodes that as a bounded iterative loop.
- **Memory-seed.** v5 careful-hire produced empty memory dirs — observed in
  33Ledger `eng-backend-ic-01`, `eng-frontend-ic-01`, `eng-qa-ic-01`,
  `pm-ic-01` per v6 plan §2 Cluster A2.
- **Anthropic sprint-contract pattern** — *"Each criterion had a hard
  threshold, and if any one fell below it, the sprint failed."* Preserved
  as per-dim floors in Phase 4 rubric.
- **Schmidt & Hunter (1998) work-sample r=0.54** — ground for Phase 4
  work-sample dimension. Highest-validity single hiring predictor.
