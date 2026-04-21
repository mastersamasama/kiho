# OpenSpace skill evolution semantics

Offline reference describing the three skill evolution operations (FIX, DERIVED, CAPTURED) and the supporting infrastructure for skill lifecycle management. Based on the OpenSpace skill evolution model.

## Contents
- [Skill storage model](#skill-storage-model)
- [Registry and discovery](#registry-and-discovery)
- [Evolution operations](#evolution-operations)
- [Execution analysis triggers](#execution-analysis-triggers)
- [Lineage tracking](#lineage-tracking)
- [Lifecycle states](#lifecycle-states)

## Skill storage model

Each skill is a directory containing:

```
skills/<skill-name>/
  SKILL.md              # the skill definition (frontmatter + body)
  changelog.md          # append-only history of changes (optional, created on first FIX)
  versions/             # archived prior versions (optional, created on first FIX)
    v1.0.0.md
    v1.0.1.md
  references/           # progressive-disclosure reference files (optional)
  templates/            # output templates (optional)
  scripts/              # executable helpers (optional)
```

The `SKILL.md` frontmatter contains a `.skill_id` field — a stable identifier that does not change across versions or renames. The skill_id is generated on creation and used for KB references, lineage tracking, and analytics.

### Frontmatter schema

```yaml
name: <kebab-case, max 64 chars>
skill_id: <uuid or slug — stable across versions>
version: <semver: MAJOR.MINOR.PATCH>
lifecycle: draft | active | deprecated
origin: authored | captured | derived
lineage:
  parents: [<parent-skill-name>]   # empty for authored/captured skills
  ancestor: <root ancestor name>    # null for authored/captured skills
description: <third-person, WHAT+WHEN, under 1024 chars>
tier: plugin | project | company
test_case:
  input: "<scenario description>"
  expected_output: "<expected outcome>"
  pass_criteria: "<how to verify>"
use_count: <integer>
last_used_at: <iso timestamp or null>
last_verified_at: <iso timestamp or null>
```

## Registry and discovery

Skills are discovered at runtime by `skill-find`, which globs across tiers and matches queries against frontmatter metadata.

The KB also maintains skill registrations as entity pages. When a skill is created, fixed, or deprecated, `kb-add` is called to keep the registry in sync. The entity page includes the skill's name, description, lineage, and a link to its `SKILL.md`.

`skill-solutions.md` in the KB maps entities and concepts to the skills that solve or support them. This enables reverse lookup: "which skills relate to authentication?" → find all skills tagged with or solving auth-related entities.

## Evolution operations

### FIX — patch in place

**Trigger:** A skill produces incorrect output, misses a trigger, or fails its test case.

**Scope:** Minimal diff — under 20 lines changed. One root cause per FIX.

**Effect:**
- Patches the existing `SKILL.md`
- Bumps PATCH version (1.0.0 → 1.0.1)
- Archives prior version in `versions/`
- Appends to `changelog.md`
- Updates KB registration

**Constraint:** If more than 20 lines need changing, the skill needs DERIVED instead.

See `skills/skill-improve/SKILL.md` for the full protocol.

### DERIVED — specialize from parents

**Trigger:** An existing skill almost fits a use case but would need significant changes (>20 lines) to cover it, or capabilities from multiple skills need combining.

**Scope:** New skill directory with its own `SKILL.md`. Inherits lineage from parents.

**Effect:**
- Creates a new `skills/<derived-name>/SKILL.md`
- Sets `origin: derived` and `lineage.parents`
- Starts at `lifecycle: draft`
- Registers in KB

**Constraint:** Must pass dedupe check. Must be genuinely different from parents.

See `skills/skill-derive/SKILL.md` for the full protocol.

### CAPTURED — extract from success

**Trigger:** An agent successfully handled a task that no existing skill covers. The pattern is reusable.

**Scope:** New skill directory, abstracted from a specific session.

**Effect:**
- Creates a new `skills/<captured-name>/SKILL.md`
- Sets `origin: captured` and empty `lineage.parents`
- Includes a generated test case
- Starts at `lifecycle: draft`
- Registers in KB

**Constraint:** Only capture from successful interactions. Must abstract properly (not too specific, not too generic).

See `skills/skill-capture/SKILL.md` for the full protocol.

## Execution analysis triggers

The evolution-scan skill periodically analyzes skill performance:

| Signal | Suggested operation |
|---|---|
| Skill failed its test case | FIX |
| Skill description missed a trigger that session-context shows was relevant | FIX (trigger-miss) |
| Skill output was correct but suboptimal (took more steps than necessary) | FIX (efficiency) |
| Agent manually overwrote skill output | FIX (instruction clarity) |
| Multiple skills were needed for one task | DERIVED (combine parents) |
| Existing skill needed >20 lines of adaptation for a new domain | DERIVED (specialize) |
| Agent succeeded at a task with no skill support | CAPTURED |
| Same manual pattern repeated 3+ times across sessions | CAPTURED |

## Lineage tracking

Lineage is a directed acyclic graph (DAG). Each derived skill points to its parents. The `ancestor` field shortcuts to the root.

```
kb-add (authored)
  ├── kb-add-rubric (derived from kb-add)
  │     └── kb-add-rubric-interview (derived from kb-add-rubric)
  └── kb-add-skill-registration (derived from kb-add)
```

Lineage enables:
- **Impact analysis:** When `kb-add` gets a FIX, check if derived skills need the same fix.
- **Genealogy:** Visualize skill evolution over time.
- **Deprecation cascading:** When a parent is deprecated, flag all derived skills for review.

## Lifecycle states

| State | Meaning | Transitions |
|---|---|---|
| `draft` | Created but not validated. May be incomplete. | → `active` (after test case passes + review) |
| `active` | Validated and in production use. | → `deprecated` (replaced or obsolete) |
| `deprecated` | No longer recommended. Kept for reference. | → (terminal, or → `active` if un-deprecated) |

Only `active` skills are returned by `skill-find` by default. `draft` skills are found only when explicitly searching for drafts. `deprecated` skills are found only when explicitly searching for deprecated.

Promotion from `draft` to `active` requires:
1. Test case passes
2. Review by CEO or department lead
3. KB registration via `kb-add`
4. Entry in `skill-solutions.md` (if the skill solves a known entity/concept)
