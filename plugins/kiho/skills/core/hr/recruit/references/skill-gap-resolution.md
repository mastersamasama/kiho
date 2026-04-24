# Phase 2 detail — design-validate-fill-validate loop

This reference documents the heuristics, scoring rules, and failure routes
behind recruit's Phase 2. Phase 2 is the CORE reflex: it produces a
validated recipe (persona + resolved skill list) before any candidate is
drafted.

## Invariants

- Every skill ID in the final recipe **MUST** resolve to
  `$COMPANY_ROOT/skills/<id>/SKILL.md`.
- `settings.recruit.max_skills_authored_per_recruit` (default 3) caps new
  skill authoring per recruit. Overflow → ESCALATE.
- `settings.recruit.max_design_iterations` (default 3) caps the loop.
- Phase 2 never emits an unresolved skill downstream. Phase 3 receives a
  clean recipe.

## Feature-coverage scoring

When a proposed skill ID resolves to an existing SKILL.md, compute:

```
wanted_features  = set of bullet-point capabilities from design-agent's
                   rationale (feature_list), normalized via kebab-case
                   + stopword stripping
existing_features = set extracted from the existing SKILL.md §"Procedure",
                   §"Inputs", §"Worked examples" — same normalization

feature_coverage = |wanted_features ∩ existing_features| / |wanted_features|
```

Score bands drive the action:

| coverage | action | explanation |
|---|---|---|
| ≥ 0.80 | `RESOLVED_REUSE` | existing covers what the candidate wants; use as-is |
| [0.60, 0.80) | `PARTIAL_REUSE` → IMPROVE candidate | some overlap; skill-improve folds missing features in |
| [0.40, 0.60) | `PARTIAL_REUSE` → IMPROVE if approved, else AUTHOR_NEW | borderline; self-improvement committee gate decides |
| < 0.40 | `CONFLICT_NARROW` → AUTHOR_NEW or IMPROVE with big delta | existing too narrow; usually author new |

When no existing SKILL.md matches the ID hint but a semantically similar
skill exists (see §"Semantic-neighbor check" below), treat as
`NAMING_CONFLICT` and propose the existing skill's ID to design-agent.
Design-agent confirms or overrides; on override a new ID is authored.

## Semantic-neighbor check

Before marking an ID hint as `AUTHOR_NEW`, scan `$COMPANY_ROOT/skills/INDEX.md`
for candidates:

```
for row in INDEX.md:
  sim = jaccard(wanted.description.tokens, row.description.tokens)
       + jaccard(wanted.feature_list, row.topic_tags)
       + (2 * shared_domain(wanted.domain, row.domain))
  if sim >= 0.45:
    surface as naming-conflict candidate
```

The 0.45 threshold is conservative — false positives are cheap (design-agent
rejects), false negatives pollute the library.

If ≥ 1 candidates surface, design-agent decides:
- adopt an existing ID (resolves `NAMING_CONFLICT`)
- author under a new ID, noting the neighbor in `references/` of the new
  SKILL.md ("closest existing skill: sk-X — differs because Y")

## Researcher invocation contract (Phase 2.4a)

Invoked with:

```
kiho-researcher(
  query: "<wanted.description>. Must support: <wanted.feature_list>. Domain: <wanted.domain>.",
  cascade: ["kb", "trusted_sources", "web", "deepwiki", "clone", "ask_user"],
  budget: {
    tokens_max: 40000,
    tool_calls_max: 20,
    wall_clock_min: 10
  },
  return_format: {
    findings: "structured md sections",
    citations: "array of {url | path, excerpt, why_relevant}",
    synthesis_draft: "1-3 page initial draft",
    authoring_readiness: "high | medium | low"
  }
)
```

When researcher returns `authoring_readiness: low`, design-agent's Phase 2.5
REVISE path is preferred — try a narrower skill ID first.

## Skill-derive invocation contract (Phase 2.4c)

```
skill-derive(
  parent_paths: [],                      # no parent — fresh author
  use_case: <wanted.description>,
  seed_findings: <researcher.findings>,
  seed_citations: <researcher.citations>,
  proposed_name: <wanted.id_hint>,
  rationale: <wanted.rationale>,
  target_lifecycle: "draft",             # skills authored in recruit start draft
  target_tier: "T3"                       # default — skill-derive may upgrade
)
```

Returns `{ skill_path, skill_id, frontmatter_emitted }`. Recruit then:

1. Runs `skill-lint` (existing v5 skill) on the emitted SKILL.md.
2. Calls `kiho-kb-manager op=kb-add page_type=entity` with the skill as the
   entity.
3. Verifies `$COMPANY_ROOT/skills/INDEX.md` has the new row.
4. Records the authoring in `.kiho/state/recruit/<slug>/skills-authored.jsonl`.

## Skill-improve path (Phase 2.4e)

Invoked when `action == PARTIAL_REUSE`:

```
skill-improve(
  skill_id: <id_hint>,
  proposed_delta: {
    new_features: <wanted.features \ existing.features>,
    rationale: <wanted.rationale>
  },
  committee_mode: "light",                # mini-committee, not full
  authorized_by: "kiho-hr-lead"
)
```

If skill-improve's coherence gate or committee rejects the delta, the skill
stays as-is and design-agent receives `action: improve_rejected` — it may
author under a new ID or REVISE the persona to drop the feature demand.

## REVISE vs ESCALATE (Phase 2.5)

When Phase 2.5 cannot resolve a skill after fill-back:

**REVISE** — design-agent modifies the persona internally:
- drops the unresolvable skill if it was non-critical
- substitutes an adjacent available skill ("use sk-X instead of authoring
  sk-Y")
- narrows the role scope to not need the skill

REVISE is cheap and the preferred path. It costs one more iteration of the
loop. When `max_design_iterations == 3`, REVISE is fine if it happens once
or twice.

**ESCALATE** — return `status: skill_fill_blocked` to the caller:
- researcher hit a budget wall and cannot complete
- user rejected the install of an MCP needed for the skill's runtime
- the capability is fundamentally unfillable in this org (e.g., requires
  physical hardware)

Recruit's caller (CEO) decides whether to ASK_USER, widen the role spec, or
cancel the recruit.

## Worked example — visual QA gap

A `/kiho --vibe "check UI for spacing issues"` request; no agent has a
visual-QA skill.

**Phase 1 stub:**
- objective: screenshot-based UI regression detection on overflow, spacing,
  touch-target size
- work_sample: run on 33Ledger 3 screens, produce a rubric with severity
  tags

**Phase 2 iteration 1:**
- design-agent proposes persona "QA Visual Engineer IC" with
  `skills_wanted: [sk-visual-qa-invariants, sk-screenshot-diff, sk-a11y-tap-targets]`
- Validate: all three mark `to_author`
- Fill-back budget check: 3 new skills ≤ `max_skills_authored_per_recruit=3`. OK.
- Researcher query 1: "best practices for invariant-based UI QA overflow
  touch-target" → returns structured findings with citations to Playwright
  docs, Apple HIG, MUI spacing spec
- skill-derive authors `sk-visual-qa-invariants/SKILL.md`
- kb-add registers; INDEX updated
- Repeat for `sk-screenshot-diff` and `sk-a11y-tap-targets`
- Validate again: all three resolve. Loop exits.

**Output of Phase 2:** validated recipe with 3 authored skills. Phase 3
produces 4 candidates all referencing these three IDs; Phase 3.5 may still
dedupe if candidates propose EXTENSIONS (e.g., candidate 3 wants
`sk-visual-regression-testing` which has 0.72 overlap with
`sk-visual-qa-invariants` → MERGE).

## Idempotency

If a recruit restarts mid-Phase 2 (crash, resume), the already-authored
skills under `$COMPANY_ROOT/skills/` are **kept**. Phase 2.3 will now mark
them `RESOLVED_REUSE` on the restarted iteration. This is why skill-derive
always writes to the canonical path, never a staging directory.
