---
name: design-agent
description: v6 agent designer producing fully-formed schema v2 agent.md files. Parses role spec, derives required_skills from role signals (proposes new skill IDs when needed), validates each skill against $COMPANY_ROOT/skills/ and triggers Phase 2 fill-back for missing, builds a persona with portable (no-project-names) role strings, builds a v5 12-section soul with portable biography, populates v2 frontmatter (schema_version=2, role_generic, role_specialties, experience=[], current_state.availability="free", skills=[resolved IDs], memory_path, hire_provenance), writes agent.md and runs bin/agent_md_lint.py inline, seeds memory/{lessons,todos,observations}.md from the interview + work-sample, emits a RECRUIT_CERTIFICATE marker. Also supports op=propose_recipe (Phase 2 THINK step) and op=synthesize_candidates (Phase 5 merge step). Use from recruit Phases 2/3/5 or directly when HR-lead commands agent drafting with a validated role spec. Supersedes the v5 12-step create path.
metadata:
  trust-tier: T2
  version: 3.0.0
  lifecycle: active
  kiho:
    capability: create
    topic_tags: [hiring, persona, schema-v2]
    data_classes: ["agent-souls", "agent-md"]
    storage_fit:
      reads: ["$COMPANY_ROOT/skills/**", "$COMPANY_ROOT/project-registry.md", "$COMPANY_ROOT/settings.md"]
      writes: ["$COMPANY_ROOT/agents/<id>/agent.md", "$COMPANY_ROOT/agents/<id>/memory/{lessons,todos,observations}.md"]
---
# design-agent (v6)

Deliberative agent designer. Produces FULLY-FORMED schema v2 `agent.md`
files — not thin persona stubs. Every output agent has `experience`,
`current_state`, validated `skills`, populated `memory/` directory, and
passes `bin/agent_md_lint.py`. Invoked by `recruit` in Phases 2, 3, and 5.

v6 replaces the v5 12-step pipeline with an 8-step v2-producing flow. The
v5 soul validation stays; the v5 thin frontmatter does not. Missing skills
are NOT a silent capability downgrade — they trigger Phase 2 fill-back via
`kiho-researcher + skill-derive`.

## Operations

This skill supports three ops called by `recruit`:

| op | Called from | Purpose |
|---|---|---|
| `propose_recipe` | recruit Phase 2.1 (THINK) | Propose persona + wanted_skills list given a role-spec stub; skills may be unresolved |
| `draft_candidate` (default) | recruit Phase 3 | Produce a full v2 agent.md draft from a validated recipe + diversity axis |
| `synthesize_candidates` | recruit Phase 5.3a | Merge top-2 agent.md files into a single synthesized candidate |

## Inputs (draft_candidate — default op)

```
role_spec_path: <path to role-spec.md from recruit Phase 1>
recipe: <validated recipe from Phase 2 — persona_draft + resolved skills>
diversity_axis: seniority | philosophy | specialty | any
axis_emphasis: <string — "experienced conservative" | "mid-level autonomous" | "safety-first" | "breadth over depth">
requestor: <agent-id — usually kiho-hr-lead>
is_synthesis: <bool — default false; true only when called by Phase 5>
```

## 8-step pipeline (draft_candidate)

```
Step 1  — Parse role-spec + recipe; derive required_skills
Step 2  — Validate each skill; trigger Phase 2 fill-back if missing
Step 3  — Build persona (portable, no project names — lint R3 clean)
Step 4  — Build v5 12-section soul (portable biography, portable red lines)
Step 5  — Populate v2 frontmatter (schema_version=2, current_state, experience=[],
           skills=[resolved IDs], memory_path, tools, hire_provenance stub)
Step 6  — Write agent.md; run bin/agent_md_lint.py; reject on R1-R6 errors
Step 7  — Seed memory/{lessons, todos, observations}.md from interview +
           role-spec.work_sample + persona coherence notes
Step 8  — Emit hire_provenance frontmatter + RECRUIT_CERTIFICATE marker
```

## Step 1 — Parse role-spec + derive required_skills

Read:
- `role_spec_path` — the four-field contract from recruit Phase 1
- `recipe.persona_draft` — role_generic, specialties, soul_traits_hint
- `recipe.skills_resolved` — list of validated skill IDs

`required_skills` for this candidate **MAY** extend or narrow `recipe.skills_resolved`
based on the candidate's `diversity_axis`:

- `seniority`-emphasis senior candidates often propose additional
  architectural-review skills (e.g., `sk-review-heuristics`)
- `philosophy`-emphasis safety-first candidates often narrow the skill set
  and add `sk-refusal-patterns`
- `specialty`-emphasis breadth candidates propose adjacent specialties

When this candidate proposes NEW skill IDs beyond the recipe, emit
`new_skill_proposals: [{id_hint, description, feature_list, rationale}]` —
recruit Phase 3.5 will reconcile them.

## Step 2 — Validate each skill; trigger Phase 2 fill-back if missing

```
for skill_id in required_skills:
    path = $COMPANY_ROOT / "skills" / skill_id / "SKILL.md"
    if path.exists():
        mark "resolved"
    else:
        mark "missing_to_fill_back"
```

### Step 2.3 — Performance ranking (v6 §3.10 — PR #3)

When `skill-find` or `unified-search` surfaces multiple existing skills
that could cover the same need, consult
`references/skill-ranking.md` (co-located in this skill's references).

Read `$COMPANY_ROOT/company/skill-performance.jsonl` (produced by
`bin/kiho_telemetry_rollup.py --company-root` at CEO DONE step 10).
Compute `score = w_s·success_rate + w_c·(1-correction_rate) + w_f·freshness`
with weights from `settings.performance.rank_weights` (defaults 0.5/0.3/0.2).

Routing:

- **Top** → USE (include in `skills[]`)
- **Middle** → add to `improve_suggestions[]` in the recipe output
- **Bottom (score < 0.4 AND no dependents per `bin/kiho_rdeps.py`)** → add
  to `deprecate_candidates[]` for next `consolidate-skill-library` cycle

When the `skill-performance.jsonl` file is missing (first CEO turn after
PR #3 ships): skip ranking, fall back to v5 behavior (prefer lexicographic
or first-found). Log the fallback.

On `missing_to_fill_back`: emit a `FILL_BACK_REQUEST` return to recruit with
the missing IDs and their descriptions. Recruit runs Phase 2.4 pipeline
(researcher → skill-derive → kb-add) and re-invokes design-agent once the
skill lands. Design-agent does NOT invoke the researcher directly — that
contract belongs to recruit's orchestration.

**External skill reference check (v6 §3.9 — PR #3).** BEFORE emitting
`FILL_BACK_REQUEST`, consult `$COMPANY_ROOT/external-skills-catalog.json`
(produced by `skill-discover`). If a catalog entry's description has
`text_similarity >= 0.75` (via `bin/embedding_util.py`) with the missing
skill's description, emit an `external_reference_candidate` on the
persona recipe instead of a fill-back request:

```json
{
  "id_hint": "sk-onchain-market-data",
  "description": "...",
  "external_reference_candidate": {
    "type": "plugin_skill",
    "plugin": "onchainos",
    "skill_id": "okx-dex-token",
    "similarity_score": 0.82,
    "purpose": "market data reads; avoids reimplementing the provider"
  }
}
```

Recruit Phase 2.4 then wraps the external skill in a thin internal skill
whose frontmatter carries `references: [{type: plugin_skill, ...}]` — per
`references/skill-frontmatter-schema.md §references:`.

If `settings.external_skills.allow_references == false` OR the catalog
file is missing: skip this check and proceed with FILL_BACK_REQUEST
(legacy behavior).

**Why:** this keeps design-agent stateless; repeated design-agent calls
during Phase 2 iterations do not accumulate in-flight researcher
invocations; recruit owns the budget tracking for authored skills.

## Step 3 — Build persona (portable, no project names — lint R3 clean)

```yaml
persona:
  name: <stable_human_name_never_project_locked>
  id: <dept>-<role-slug>-ic-<NN>   # or kiho-<dept>-lead
  role_generic: <GENERIC discipline — no project names>
  role_specialties: [<framework/language/methodology tags>]
```

**Lint R3 rule:** `role_generic` and every `role_specialties[i]` — none
contain any case-insensitive substring match against
`$COMPANY_ROOT/project-registry.md` lines.

Examples:

| Input hint | GOOD role_generic | BAD role_generic (lint fail) |
|---|---|---|
| "React Native IC for 33Ledger" | "React Native + Web Senior IC" | "33Ledger Mobile Lead" |
| "PM for kirito project" | "Product Manager" | "Kirito PM" |
| "Visual QA for design-review" | "QA Visual Engineer IC" | "Cybermoe QA Lead" |

Generate 3 candidate role_generic strings; design-agent scans each against
`project-registry.md` and picks the first lint-clean one. If all 3 fail,
REVISE and retry up to 3 times; final failure → escalate.

`role_specialties` similarly — generated in pairs, each scanned and
lint-cleaned.

## Step 4 — Build v5 12-section soul (portable biography, portable red lines)

Full v5 soul per `references/soul-architecture.md` — all 12 sections MUST
be populated. Empty section = Step 3 failure in v5, continues to apply.

v6 additions:

- **§1 biography:** MUST NOT contain any project name. If the diversity
  axis mentions "senior IC who worked on 33Ledger and kirito", the
  biography is rewritten as "senior IC with a multi-project mobile
  portfolio". Project names move to `experience[]` post-assignment, not
  here.
- **§4 red-line objects:** stated in generic terms. "I refuse to ship
  33Ledger without Rust core tests" → "I refuse to ship a financial
  application without safety-critical tests on core computation paths."
- **§11 exemplar interactions:** may use generic project placeholders
  (`<project>`) or scenario descriptions; MUST NOT name real projects.

Apply the v5 coherence check (Big Five × Values × Red lines × Behavioral
rules) as in v5 Step 3 + Step 3b. Gate: `coherence_score >= 0.70` after
self-audit contribution. Failure → REVISE and retry up to 3 times.

Apply v5 tool allowlist validation (Step 4b) — every behavioral rule
traces to an allowed tool; every tool serves at least one rule or
responsibility. Gate: `alignment_subscore_tools >= 0.70`.

Apply v5 model tier selection (Step 4c) — use the task profile signals
from role-spec to pick sonnet/opus/haiku. Record rationale.

## Step 5 — Populate v2 frontmatter

Exact output shape per `templates/agent-md-v2.template.md`:

```yaml
---
<!-- RECRUIT_CERTIFICATE marker (populated in Step 8) -->
schema_version: 2

name: <stable_human_name>
id: <agent_id>

role_generic: <lint-clean role>
role_specialties:
  - <specialty_1>
  - <specialty_2>

soul_version: v5

experience: []

current_state:
  availability: "free"                      # overridden to "engaged" at assignment time
  active_project: null
  active_assignment: null
  last_active: <iso_timestamp_utc>

skills:
  - <resolved_skill_id_1>
  - <resolved_skill_id_2>

memory_path: "$COMPANY_ROOT/agents/<agent_id>/memory/"

tools:
  - Read
  - Glob
  - Grep
  # add Write, Edit, Bash per role; Agent only for leads

hire_provenance:
  recruit_turn: <iso_timestamp_at_recruit_start>
  rubric_score: <placeholder — filled after Phase 4 interview>
  auditor_dissent: <placeholder>
  hire_type: <placeholder>
  recruit_certificate: <placeholder>
---
```

Note: `hire_provenance.rubric_score` and `hire_type` are stubs at Step 5.
Recruit Phase 5 fills them AFTER the interview result is known.
Step 8 closes the loop.

## Step 6 — Write agent.md; run bin/agent_md_lint.py; reject on errors

Write path: `$COMPANY_ROOT/agents/<agent_id>/agent.md`.

Before completing Step 6, run:

```bash
python ${CLAUDE_PLUGIN_ROOT}/bin/agent_md_lint.py \
  $COMPANY_ROOT/agents/<agent_id>/agent.md \
  --company-root $COMPANY_ROOT
```

**PR #2 behavior (warn-only):** parse stdout for warnings; log each as
`action: agent_md_lint_warning, rule: <RN>, message: <...>` in recruit's
ledger; proceed. This mirrors the PR #1 scaffold.

**PR #3 behavior (enforce):** if exit == 1, roll back the write and return
`status: lint_failed, violations: [...]`. Recruit retries with REVISE up to
2 more times; final failure aborts the candidate.

Common lint R3 traps (project-coupling):
- Biography mentions the project name the role-spec came from. Fix: rewrite
  §1 with generic industry framing.
- Red-line object contains a product name. Fix: generalize to product class.
- Specialty list repeats a project name as a "framework". Fix: delete.

## Step 7 — Seed memory/{lessons, todos, observations}.md

Design-agent creates the directory:

```bash
mkdir -p $COMPANY_ROOT/agents/<agent_id>/memory/
touch $COMPANY_ROOT/agents/<agent_id>/memory/.last-reflect
echo "1970-01-01T00:00:00Z" > $COMPANY_ROOT/agents/<agent_id>/memory/.last-reflect
```

The CONTENT of `lessons.md`, `todos.md`, `observations.md` is composed by
**recruit Phase 6** — design-agent creates empty-but-present stubs in Step
7, and recruit fills them from interview + work-sample output in Phase 6.

This split is intentional:
- Design-agent runs pre-interview (in Phase 3); it doesn't have interview
  output yet.
- Recruit Phase 6 runs post-interview; has everything needed.

Step 7 stub content (overwritten by Phase 6):

```markdown
<!-- lessons.md stub — filled by recruit Phase 6 memory-seed -->

(placeholder — will be populated at hire close)
```

The placeholder is non-zero-byte, satisfying lint R5 pre-seed. Phase 6
overwrites with real content; post-phase-6, the files are real seeds.

See `references/memory-seed-template.md` for the templates recruit uses.

## Step 8 — Emit hire_provenance + RECRUIT_CERTIFICATE marker

Called by recruit Phase 5 AFTER selection. Design-agent re-opens the winner's
`agent.md`, updates frontmatter `hire_provenance` block:

```yaml
hire_provenance:
  recruit_turn: <iso_at_recruit_start>
  rubric_score: <final_interview_rubric_avg>
  auditor_dissent: <count_of_dissenting_auditors_0_to_4>
  hire_type: "v6-auto-recruit"   # or "v6-synthesis"
  synthesized_from: [<top1_id>, <top2_id>]   # only if hire_type == v6-synthesis
  recruit_certificate: "v6-auto-recruit-<slug>-<iso>"
```

And prepends the RECRUIT_CERTIFICATE HTML comment as the first content (per
v5.22 `pre_write_agent` PreToolUse hook contract):

```markdown
<!-- RECRUIT_CERTIFICATE:
       kind: v6-auto-recruit | v6-synthesis
       role_spec: <path>
       candidate_slug: <slug>
       interview_score: <aggregate_mean>
       committee_status: approved
       synthesis_applied: <bool>
       skills_authored_this_hire: [<ids>]
       emitted_at: <iso>
-->
---
schema_version: 2
...
```

The hook's regex was designed to be superset-matching; v6 keys (synthesis,
skills_authored) do not break the pre-write gate.

## op=propose_recipe (Phase 2 THINK)

Input:

```
role_spec_path: <path>
iteration: <int — 1, 2, or 3>
prior_attempt: <optional — previous recipe + fill-back result if this is a retry>
```

Behavior: Steps 1-4 above (parse, validate, persona, soul draft) but STOP
before Step 5. Return:

```json
{
  "status": "ok | revise_needed",
  "persona_draft": {
    "role_generic": "...",
    "role_specialties": [...],
    "soul_traits_hint": {...}
  },
  "wanted_skills": [
    {
      "id_hint": "sk-visual-qa-invariants",
      "description": "...",
      "feature_list": [...],
      "rationale": "...",
      "estimated_authoring_complexity": "low | med | high"
    }
  ],
  "persona_satisfied": true
}
```

`persona_satisfied: false` signals design-agent has unresolved conflicts in
the persona itself (e.g., wants conflicting specialties), and the caller
(recruit) should either provide more role_spec detail or ASK_USER.

## op=synthesize_candidates (Phase 5.3a)

Input:

```
top1: {agent_md_path, rubric_scores, role_specialties, skills}
top2: same shape
role_spec: <path>
recipe: <validated Phase 2 recipe>
```

Behavior: apply the merge rules from
`references/candidate-synthesis.md` (in the recruit skill's references).

Specifically:

1. **role_generic:** use top1's (already lint-clean). Tie-break by
   authoring recency if both clean.
2. **role_specialties:** union, dedupe on case-insensitive match.
3. **skills:** union, then revalidate via Phase 3.5 dedupe (existing IDs
   only; no new authoring permitted inside synthesis).
4. **Big Five:** weighted mean per trait, weights from `dim_relevance`
   table (see candidate-synthesis.md §"Big Five").
5. **Values top-3:** union, rank by rubric_avg contribution of related
   rounds.
6. **Red lines:** UNION — never narrow. On conflict (one refuses X, other
   requires X), return `status: synthesis_red_line_conflict`; recruit
   hires top1.
7. **Soul §6 rules:** union, dedupe by verb-object. Conflicts → keep top1.
8. **Soul §1 biography:** stitched merge.

Output: a synthesized `agent.md` draft at
`.kiho/state/recruit/<slug>/candidates/synth/agent.md.draft` — recruit
re-interviews this draft.

## Pass gates (draft_candidate op)

| Step | Gate | Threshold | Action on fail |
|---|---|---|---|
| 2 | All skills resolved post-fill-back | 100% resolved | Iterate Phase 2; max 3; then escalate |
| 3 | Persona lint-clean | No R3 violations | Generate 3 alternatives; pick clean; else REVISE |
| 4 | coherence_score | ≥ 0.70 | REVISE soul sections 3/3b; max 3 |
| 4 | alignment_subscore_tools | ≥ 0.70 | REVISE §6 rules or tool allowlist; max 3 |
| 6 | agent_md_lint | 0 errors (PR #3 enforce) / 0 R1-R2 errors (PR #2 warn) | Rewrite offending fields; max 2 |
| 7 | memory dir created, .last-reflect present | all present | hard fail; recruit retries |

## Response shape (draft_candidate)

```json
{
  "status": "ok | fill_back_required | lint_failed | coherence_failed | revision_limit_exceeded",
  "agent_id": "eng-visual-qa-ic-01",
  "agent_path": "$COMPANY_ROOT/agents/eng-visual-qa-ic-01/agent.md",
  "memory_path": "$COMPANY_ROOT/agents/eng-visual-qa-ic-01/memory/",
  "role_generic": "QA Visual Engineer IC",
  "role_specialties": ["playwright", "screenshot-diff", "a11y"],
  "skills": ["sk-visual-qa-invariants", "sk-screenshot-diff"],
  "new_skill_proposals": [],
  "fill_back_requests": [],
  "coherence_score": 0.82,
  "alignment_subscore_tools": 0.91,
  "model": "sonnet",
  "model_justification": "sonnet: standard IC work with multi-step tool chains",
  "lint_report": {
    "errors": 0,
    "warnings": 0,
    "violations": []
  },
  "diversity_axis": "seniority",
  "axis_emphasis": "experienced conservative"
}
```

## Response shape (synthesize_candidates)

```json
{
  "status": "ok | synthesis_red_line_conflict | error",
  "synth_agent_path": ".kiho/state/recruit/<slug>/candidates/synth/agent.md.draft",
  "synth_role_generic": "...",
  "synth_role_specialties": [...],
  "synth_skills": [...],
  "big_five_merged": {"openness": 7, "conscientiousness": 8, ...},
  "values_merged": [...],
  "red_lines_merged": [...],
  "red_line_conflicts_detected": []
}
```

## Anti-patterns

- **MUST NOT** ship a schema v1 (v5) agent.md. v6 requires schema_version: 2
  with all mandatory keys.
- **MUST NOT** include project names in role_generic, role_specialties,
  soul §1, or soul §4 red-line objects. Agents are portable professionals.
- **MUST NOT** list a skill in `skills[]` that does not resolve to
  `$COMPANY_ROOT/skills/<id>/SKILL.md`. Silent capability downgrade is a v5
  bug this step exists to prevent.
- **MUST NOT** skip Step 6 lint. Even in warn-only PR #2, the lint output
  flows into recruit's ledger — skipping it means post-hire audits won't
  catch R3 leaks.
- **MUST NOT** populate `memory/` files with final content in Step 7 —
  that's recruit Phase 6's job. Step 7 creates empty-but-present stubs.
- Do not hand-pick a model tier. Step 4c's decision table (inherited from
  v5) exists because "sonnet for everything" misses long-horizon ICs that
  need opus.
- Do not invoke `kiho-researcher` or `skill-derive` directly from
  design-agent. Recruit owns the Phase 2 fill-back orchestration.
- Do not merge more than 2 candidates in synthesize_candidates. Top-2 only.

## Interaction with v5 skill-derive / skill-improve

- `skill-derive` is called by recruit Phase 2.4c, not by design-agent.
- `skill-improve` is called by recruit Phase 2.4e or Phase 3.5.5, not by
  design-agent.
- Design-agent's role is to DECLARE what skills it needs (with rationale)
  and let recruit orchestrate fill-back.

## Grounding

- **Schema v2 enforcement.** v6 plan §3.2 Clusters A1-A7. User direction:
  *"v5 create-agent output is thin — even when a soul skeleton is produced,
  experience[] is absent, current_state is absent, memory_path points to
  an empty dir."*
- **Portable role strings.** v6 plan §2 Cluster A1 evidence: 4 agent.md
  files with "33Ledger" in `role:`.
- **Lint-first pre-write.** Per PR #1 `bin/agent_md_lint.py`: every v6
  agent.md must pass R1-R6. Design-agent runs lint inline so violations
  surface at write time, not at next-turn audit.
- **v5 12-section soul preserved.** v6 plan §3.2: *"Don't rewrite the v5
  soul 12-section structure — it's good; just wrap it in v2 frontmatter."*
- **design-agent stateless re fill-back.** Phase 2 is recruit-owned so
  repeated design-agent iterations don't cascade researcher invocations.
