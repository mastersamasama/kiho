# Skill frontmatter schema (kiho v6)

Canonical reference for the fields every kiho `SKILL.md` carries in its YAML frontmatter. Templates at `templates/skill-frontmatter.template.md` and `templates/skill-skeleton.template.md`. Validation happens via `skill-create` / `skill-factory` / `skill-critic` (authoring time) and the `skill_catalog_index.py` build step (runtime catalog).

## Canonical (agentskills.io open standard)

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | kebab-case, ≤ 64 chars, unique across company skill library |
| `description` | string | yes | trigger-rich description; see `references/skill-authoring-standards.md` §Description |
| `license` | string | no | SPDX identifier (MIT, Apache-2.0, ...) |
| `compatibility` | string | no | environment notes |
| `allowed-tools` | string | no | narrow-scope tool list; never `Bash(*)` |

## `metadata` block

### Lifecycle
- `version` (semver string) — bumped by `skill-improve` / `skill-derive`
- `lifecycle` — `draft | active | mature | deprecated` (mature added in v6 §3.8)

### `kiho.*`
- `capability` — one of 8 verbs: `create | read | update | delete | evaluate | orchestrate | communicate | decide`
- `topic_tags` — 1-3 tags from `references/topic-vocabulary.md`
- `trust-tier` — `T1 | T2 | T3` (runtime blast radius; see `references/storage-architecture.md`)
- `requires` — hard deps; skill fails if missing (e.g., `[sk-013]`)
- `mentions` — soft refs
- `reads` — KB page paths the skill reads
- `supersedes` — skills this one replaces
- `deprecated` (bool)
- `superseded-by` (string) — set by `skill-deprecate`

### `kiho.data_classes` + `kiho.storage_fit`
Required by v5.19+ — see `references/data-storage-matrix.md`:
- `data_classes: [<class>, ...]`
- `storage_fit.reads: [<glob>, ...]`
- `storage_fit.writes: [<glob>, ...]`

---

## `references:` block (NEW in v6 §3.9)

External and internal skill references. When `settings.external_skills.allow_references == true`, a skill MAY reference capabilities in other kiho skills (internal), other Claude Code plugins (plugin_skill / claude_global_skill), or external documentation URLs (external_docs) instead of re-implementing them.

Enables composition across the broader Claude Code ecosystem without duplicating logic. Consumed by `skill-derive` (Phase 2 authoring check — prefer `references:` over re-author when a good match exists in the external catalog) and `design-agent` (Phase 2 recipe validation).

### Schema

```yaml
references:
  - type: internal_skill
    skill_id: <another-company-skill-id>
    purpose: "why this skill needs that internal skill"

  - type: plugin_skill
    plugin: onchainos
    skill_id: okx-dex-token
    purpose: "why this plugin skill is consulted"

  - type: claude_global_skill
    skill: firecrawl:firecrawl
    purpose: "why this global skill is consulted"

  - type: external_docs
    url: https://docs.example.com/api/v3
    purpose: "runtime spec for the <X> protocol"
```

### Validation (authored-time)

Four rules enforced by `skill-create` / `skill-factory` and re-checked by `skill-critic`:

1. Each entry MUST have exactly one of `skill_id`, `skill`, or `url` depending on `type`.
2. `type: internal_skill` — `skill_id` MUST resolve under `$COMPANY_ROOT/skills/<id>/SKILL.md`.
3. `type: plugin_skill` — plugin + skill_id combination MUST appear in the cached `$COMPANY_ROOT/external-skills-catalog.json` written by `skill-discover`. Lint warns (not errors) when the cache is absent or stale (TTL expired).
4. `type: external_docs` — URL MUST be absolute; `purpose` MUST be ≥ 10 chars (discourages drive-by link-dumps).

### Runtime consumption

- `design-agent` Phase 2: when authoring a recipe, scans the external catalog for matches to `wanted_skills[*].description`. If match confidence ≥ 0.75, proposes a `references:` entry instead of authoring a new internal skill from scratch.
- `skill-derive` Phase 2: same check — avoids creating yet another plugin-skill wrapper when a direct reference suffices.
- `unified-search`: `scope: external` consults the catalog + any skill's `references:` entries.

### Anti-patterns

- Don't stuff `external_docs` with every URL the author consulted during research. The field is for runtime-relevant specs, not a bibliography.
- Don't bypass the cache — references to `plugin_skill` types without a corresponding catalog entry trigger a lint warning; the author should either run `skill-discover` or document why the plugin is expected to be installed.

---

## CLAUDE Code top-level extensions (optional)

| Field | Purpose |
|---|---|
| `argument-hint` | surfaced to users when the skill is selectable |
| `model` | override the model tier for this skill's invocations |

## Related

- `references/skill-authoring-standards.md` — how to write the description, triggers, body
- `references/capability-taxonomy.md` — the 8-verb closed set
- `references/topic-vocabulary.md` — controlled tag list
- `references/data-storage-matrix.md` — storage_fit + data_classes enforcement
- `references/company-settings-schema.md §external_skills` — runtime toggle + TTL
- `skills/_meta/skill-discover/SKILL.md` — catalog generator (v6 §3.9)
