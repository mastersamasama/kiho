---
name: skill-derive
description: Creates a DERIVED skill by specializing one or more parent skills for a new use case, following OpenSpace semantics. Reads parent skills, drafts a new SKILL.md in its own directory, sets lineage.parents, starts at lifecycle=draft, and registers via kb-add. Use when an existing skill almost fits but needs significant specialization that would break the parent (>20 lines of changes), when combining capabilities from multiple skills, or when the evolution-scan identifies a DERIVED candidate. Triggers on "derive a skill", "specialize skill", "create variant of".
metadata:
  trust-tier: T3
  kiho:
    capability: create
    topic_tags: [authoring]
    data_classes: ["skill-definitions", "skill-drafts"]
---
# skill-derive

The DERIVED operation from OpenSpace's skill evolution model. Creates a new specialized skill from one or more parent skills. Unlike FIX (which patches in place), DERIVE produces a new independent skill that inherits lineage from its parents.

## Contents
- [Inputs](#inputs)
- [Derive procedure](#derive-procedure)
- [Lineage tracking](#lineage-tracking)
- [Quality gates](#quality-gates)
- [Response shape](#response-shape)
- [Anti-patterns](#anti-patterns)

## Inputs

```
parent_paths: [<path to parent skill 1>, <optional path to parent skill 2>]
use_case: <description of the new specialized use case>
proposed_name: <optional — auto-generated if not provided>
```

## Derive procedure

### Analyze parents

1. Read each parent's `SKILL.md` — frontmatter and body.
2. Identify which elements to inherit:
   - **Keep:** core procedure, anti-patterns, response shape conventions
   - **Specialize:** description (new triggers), examples (new domain), inputs (narrower or different)
   - **Drop:** parent-specific content that does not apply to the new use case

3. If multiple parents, identify overlap and unique contributions from each.

### Draft the derived skill

4. Generate a skill name: kebab-case, descriptive of the specialization (e.g., `kb-add` parent → `kb-add-rubric` derived for rubric-specific ingestion).

5. Write `SKILL.md` in a new directory `skills/<derived-name>/`:

```yaml
---
name: <derived-name>
description: <specialized description following skill-authoring-standards>
version: 1.0.0
lifecycle: draft
origin: derived
lineage:
  parents:
    - <parent-1-name>
    - <parent-2-name>
  ancestor: <oldest parent in the chain, if parents are themselves derived>
---
```

6. Write the body following `references/skill-authoring-standards.md`:
   - Topic-based sections (not step-based)
   - Under 500 lines
   - At least one concrete example specific to the new use case
   - Imperative language
   - Anti-patterns section that includes parent anti-patterns plus any new ones

### Dedupe check

7. Run `skill-find` with the new skill's description as the query. If an existing skill scores > 0.85, flag a potential duplicate:
   - If the existing skill is a better fit, abort with `status: duplicate`
   - If the existing skill is similar but distinct, proceed and note the relationship

### Register

8. Call `kb-add` with `page_type: entity` to register the new skill in the KB:
   - Title: `skill-<derived-name>`
   - Tags: derived, skill, <parent-name(s)>
   - Content: the skill's description + lineage

## Lineage tracking

Every derived skill tracks its lineage in frontmatter:

```yaml
lineage:
  parents: [kb-add]        # immediate parents
  ancestor: kb-add          # root of the lineage chain
```

If a parent is itself derived:
```yaml
# Parent: kb-add-rubric (derived from kb-add)
# New child: kb-add-rubric-interview

lineage:
  parents: [kb-add-rubric]
  ancestor: kb-add
```

Lineage enables:
- Impact analysis when a parent is updated (find all derived skills)
- Skill genealogy visualization in `kiho-inspect`
- Automatic FIX propagation suggestions (if parent gets a fix, derived skills may need it too)

## Quality gates

Before marking the derived skill as `draft` (ready for testing):

- [ ] Name follows `references/skill-authoring-standards.md` naming rules
- [ ] Description is third-person, combines WHAT + WHEN, under 1024 chars
- [ ] Body is under 500 lines with topic-based sections
- [ ] At least one concrete example specific to the new use case
- [ ] Anti-patterns section includes all parent anti-patterns (pruned if irrelevant)
- [ ] Lineage frontmatter is correct
- [ ] Dedupe check passed (no score > 0.85 with existing skills)
- [ ] `lifecycle: draft` is set (never start as `active`)

## Response shape

```json
{
  "status": "ok | duplicate | error",
  "skill_path": "skills/<derived-name>/",
  "skill_name": "<derived-name>",
  "parents": ["<parent-1>"],
  "lifecycle": "draft",
  "kb_registered": true,
  "duplicate_warning": null
}
```

## Anti-patterns

- Never derive when a FIX would suffice. If the specialization is under 20 lines of changes to the parent, use `skill-improve` instead.
- Never create a derived skill that is functionally identical to its parent. The use case must be genuinely different.
- Never start a derived skill at `lifecycle: active`. All derived skills begin as `draft` and must pass their test case before promotion.
- Never break lineage tracking. Always set `parents` and `ancestor` correctly.
- Never derive from a deprecated parent without first checking if a replacement exists.
