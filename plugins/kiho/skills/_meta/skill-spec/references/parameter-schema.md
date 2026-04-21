# skill-spec parameter schema (canonical)

The strict YAML schema every kiho `skill-create` / `skill-improve` / `skill-derive` invocation **MUST** resolve to before any file write. Validated by `skills/_meta/skill-spec/scripts/dry_run.py`.

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are interpreted per BCP 14 (RFC 2119, RFC 8174).

## Non-Goals

- **Not a JSONSchema file.** Per CLAUDE.md §"Not a runtime database", schema is markdown + hand-coded validator, not a `.schema.json` requiring a PyPI dep.
- **Not a frontmatter spec.** Frontmatter rules live in `templates/skill-frontmatter.template.md` and `references/skill-authoring-standards.md`. This file specs *invocation parameters*, not *artifact frontmatter*.
- **Not extensible without committee vote.** New keys, new capability verbs, new topic tags require CEO-committee approval per v5.16 controlled-set discipline.

## Schema (canonical)

```yaml
skill_spec:
  # Required keys
  name:                <string, kebab-case, [a-z][a-z0-9-]{1,63}, lowercase, no "anthropic" or "claude">
  parent_domain:       <one of: _meta | core/harness | core/hr | core/inspection | core/knowledge | core/planning | kb | memory | engineering>
  capability:          <one of the 8 verbs in references/capability-taxonomy.md>
  topic_tags:          <list of 1+ tags from references/topic-vocabulary.md>
  description_seed:    <string, 200 ≤ length ≤ 1024 chars; first paragraph of intended description>
  scripts_required:    <list of script filenames the skill will ship under scripts/>
  references_required: <list of reference markdown filenames the skill will ship under references/>
  parity_layout:       <one of: standard | meta-with-scripts | meta-with-refs | meta-with-both | parity-exception>

  # Optional keys
  parity_exception:    <one-line rationale; REQUIRED iff parity_layout == parity-exception>
  batch_id:            <UUID set by orchestrator when running in batch mode; absent otherwise>
  on_failure:          <one of: jidoka-stop | escalate | rollback; default jidoka-stop>
```

## Per-key validation rules

### name

- **Format**: `^[a-z][a-z0-9-]{1,63}$` (kebab-case, lowercase, ≤ 64 chars)
- **MUST NOT** contain the substring "anthropic" or "claude" (reserved namespace)
- **MUST NOT** collide with any existing skill in `skills/**/SKILL.md`
- **On collision**: route to `skill-improve` against the existing target

### parent_domain

- One of the 9 canonical paths (matches v5.16 hierarchical-walk-catalog Stage D)
- Determines which sub-CATALOG the skill registers under

### capability

- Must be one of the 8 verbs from `references/capability-taxonomy.md` (closed set)
- Promoted only via CEO-committee vote (extension is rare, expected < 1/year)

### topic_tags

- Each entry **MUST** be in `references/topic-vocabulary.md` (controlled vocab, ~18 tags as of v5.16)
- Vocabulary expansion via CEO-committee vote
- Prefer 1-2 tags per skill; > 3 dilutes facet retrieval

### description_seed

- 200 ≤ length ≤ 1024 chars
- This is the **first paragraph** of the intended description, not the full description
- Will be expanded by `skill-create` Step 4 (iterative description improvement)
- Must include at least one trigger phrase (`Use when X` / `Triggers on Y`)

### scripts_required

- List of filenames the skill will ship under its `scripts/` subdirectory
- Each script **MUST** follow 0/1/2/3 exit-code convention (P9)
- Empty list `[]` is valid (skill ships no scripts)
- Cross-skill scripts go in `bin/`, NOT in `<skill>/scripts/` — those are not declared here

### references_required

- List of filenames under the skill's `references/` subdirectory
- Each reference **MUST** score ≥ 6/9 on the pattern-compliance audit (P1-P9 review checklist)
- Empty list `[]` is valid

### parity_layout

Five options, mapping to canonical layout templates in `skills/_meta/skill-parity/references/canonical-layouts.md`:

| Layout | Used by |
|---|---|
| `standard` | most kb/, memory/, engineering/ skills (SKILL.md only) |
| `meta-with-scripts` | core/harness/* (kiho config + scripts), some _meta with scripts |
| `meta-with-refs` | _meta skills with references/ but no scripts |
| `meta-with-both` | _meta skills shipping both scripts/ and references/ (skill-create, skill-spec) |
| `parity-exception` | explicit opt-out; requires `parity_exception:` rationale |

### parity_exception

- Required ONLY if `parity_layout == parity-exception`
- One-line rationale documenting why this skill cannot fit a canonical layout
- Logged in `_meta/parity-exceptions.md` for periodic review

### on_failure

Three options for orchestrator failure-handling:

- `jidoka-stop` (default): on any pipeline-step failure, halt; require CEO judgment
- `escalate`: emit warning, surface to next CEO checkpoint, continue with sibling skills in batch
- `rollback`: revert any partial writes for this skill; continue with siblings

## Examples

### Valid spec — new `_meta` skill

```yaml
skill_spec:
  name: skill-watch
  parent_domain: _meta
  capability: orchestrate
  topic_tags: [observability, lifecycle]
  description_seed: "Telemetry-driven regeneration trigger. Aggregates failed eval signals, parity drift, and broken inbound deps into a ranked queue and presents the CEO with a single batch decision per session. Used as Step T of the skill-factory pipeline."
  scripts_required: [queue_watch.py]
  references_required: [signal-sources.md]
  parity_layout: meta-with-both
  on_failure: jidoka-stop
```

### Valid spec — skill-improve on existing target

```yaml
skill_spec:
  name: kiho
  parent_domain: core/harness
  capability: orchestrate
  topic_tags: [orchestration]
  description_seed: "<first 200-1024 chars of updated description>"
  scripts_required: []
  references_required: []
  parity_layout: meta-with-scripts
  parity_exception: null
```

For `skill-improve`, the spec describes the **target state**, and the orchestrator routes through the improve pipeline rather than create.

### Invalid spec — name collision

```yaml
skill_spec:
  name: kiho           # already exists at sk-001
  ...
```

`dry_run.py` exits 1 with `status: name_collision`, suggesting `skill-improve --target skills/core/harness/kiho/SKILL.md`.

## Schema versioning

Schema version is implicit in the skill-spec source code. Future breaking changes will require a `schema_version: <N>` field; for v1 (current), absence of the field implies v1.

## Migration from pre-v5.17 invocations

Pre-v5.17 `skill-create` invocations used free-form prose. The factory orchestrator (`bin/skill_factory.py`) infers a v1 skill_spec from prose for backward compat, but the spec **MUST** be made explicit before the artifact ships. Free-form prose is a transitional convenience, not a long-term path.

## Grounding

- Backstage Software Templates `parameters:` JSONSchema pattern — https://backstage.io/docs/features/software-templates/writing-templates
- v5.17 research findings §"7 missing pieces #1" — https://github.com/anthropics/skills (skill-creator's frontmatter-as-spec convention)
- v5.16 controlled-set discipline (capability + topic vocabulary) — `references/skill-authoring-standards.md`
