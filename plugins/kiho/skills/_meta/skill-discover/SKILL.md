---
name: skill-discover
description: Scans the local Claude Code ecosystem for external skills the kiho org can REFERENCE (not duplicate). Walks `$CLAUDE_PLUGINS` root (typically `~/.claude/plugins/cache/`) and the built-in skill registry, reads each plugin's `plugins/*/skills/**/SKILL.md` frontmatter, and writes a time-stamped catalog at `$COMPANY_ROOT/external-skills-catalog.json` consumed by `skill-derive` and `design-agent` Phase 2 before authoring a new skill. TTL from `settings.external_skills.catalog_ttl_days` (default 7). READ-only — never modifies other plugins' files. When a match is found, callers propose `references:` entries (schema in `references/skill-frontmatter-schema.md`) instead of authoring from scratch.
metadata:
  trust-tier: T3
  version: 1.0.0
  lifecycle: draft
  kiho:
    capability: read
    topic_tags: [discovery, curation]
    data_classes: ["skill-definitions"]
    storage_fit:
      reads: ["$CLAUDE_PLUGINS/**/plugins/*/skills/**/SKILL.md", "$COMPANY_ROOT/settings.md"]
      writes: ["$COMPANY_ROOT/external-skills-catalog.json"]
---
# skill-discover

Enumerates external Claude Code skills installed alongside kiho and
catalogs them so kiho skills can REFERENCE rather than reimplement. The
catalog is a read-only snapshot; it does not modify any other plugin.

## When to use

Invoke from:

- `skill-derive` Phase 2 (before authoring a new skill) when
  `settings.external_skills.allow_references == true` — check whether an
  existing plugin skill already covers the need
- `design-agent` Phase 2 recipe validation — propose `references:` entry
  instead of skill authoring
- `unified-search` when `scope: external` is requested
- CEO ad-hoc invocation when user asks "what Claude Code plugins are
  installed"

Do NOT invoke:

- During mid-LOOP work unless the current plan item is a recruit Phase 2
  authoring decision — the discovery scan touches the filesystem
- When `settings.external_skills.allow_references == false` — respects
  the opt-out toggle

## BCP 14

MUST / MUST NOT / SHOULD — per RFC 2119 + RFC 8174.

## Inputs

```
company_root: <path>                   # target for catalog write
claude_plugins_root: <path>            # override; default env $CLAUDE_PLUGINS or ~/.claude/plugins/cache/
ttl_days: <int>                        # override; default from settings.external_skills.catalog_ttl_days (7)
force_refresh: <bool>                  # default false — skip cache, re-scan
```

## Procedure

### Phase 1 — Resolve roots

1. Read `$COMPANY_ROOT/settings.md` → `external_skills.catalog_ttl_days` (fallback 7).
2. Resolve `claude_plugins_root`:
   - Explicit input if passed
   - Else env `$CLAUDE_PLUGINS`
   - Else platform default:
     - Windows: `%USERPROFILE%\.claude\plugins\cache\`
     - Unix/Mac: `~/.claude/plugins/cache/`
3. If the directory doesn't exist, emit `{status: "no_plugins_dir", catalog_path: null}` and return. This is common on fresh installs.

### Phase 2 — Cache TTL check

1. Check `$COMPANY_ROOT/external-skills-catalog.json` existence + frontmatter `ttl_expires_at`.
2. If the cache is valid (current UTC < `ttl_expires_at`) AND `force_refresh == false`: return the cached catalog summary with `{status: "cache_fresh"}`.
3. Else proceed to Phase 3.

### Phase 3 — Enumerate plugins

1. `glob <claude_plugins_root>/*/` — each top-level directory is one plugin namespace.
2. For each plugin dir, search for `SKILL.md` files under the typical Claude Code plugin layouts:
   - `<plugin>/plugins/*/skills/**/SKILL.md` (kiho-style nested)
   - `<plugin>/skills/**/SKILL.md` (flat)
   - `<plugin>/*.skill/SKILL.md` (alt convention)
3. Deduplicate paths.

### Phase 4 — Parse skill frontmatter

For each `SKILL.md`:

1. Read the file.
2. Extract YAML frontmatter (between `---` markers) — same parser as `bin/agent_md_lint.py`.
3. Capture: `name`, `description`, `metadata.version` (optional), `metadata.lifecycle` (optional), `metadata.kiho.capability` (if present), `metadata.kiho.topic_tags` (if present), and the plugin namespace (outer dir name).
4. Skip entries where frontmatter parsing fails or `name` is missing.

### Phase 5 — Write the catalog

Write `$COMPANY_ROOT/external-skills-catalog.json`:

```json
{
  "schema_version": 1,
  "generated_at": "<iso>",
  "ttl_expires_at": "<iso + ttl_days>",
  "claude_plugins_root": "<resolved>",
  "kiho_plugin_excluded": true,
  "discovered_skills": [
    {
      "plugin": "onchainos",
      "skill_id": "okx-dex-token",
      "skill_path": "<absolute path>",
      "description": "...",
      "version": "1.2.0",
      "lifecycle": "active",
      "capability": "read",
      "topic_tags": ["market-data"],
      "discovered_at": "<iso>"
    }
  ]
}
```

**Hard exclusion:** skip any plugin directory named `kiho` — we don't
self-catalog. (kiho's own skills are in `$COMPANY_ROOT/skills/` not in
external-skills-catalog.)

### Phase 6 — Summary return

```json
{
  "status": "ok | no_plugins_dir | cache_fresh | error",
  "catalog_path": "<path>",
  "plugins_scanned": <int>,
  "skills_discovered": <int>,
  "ttl_expires_at": "<iso>",
  "new_since_last_scan": <int>
}
```

## Consumer guidance

### `skill-derive` Phase 2 consumption

When about to author a new skill from a parent:
1. Load `external-skills-catalog.json` (invoke `skill-discover` inline if missing/stale).
2. Compute `text_similarity(new_skill_description, each catalog_entry.description)` via `bin/embedding_util.py`.
3. If best match `>= 0.75`, propose to the caller:
   > "Plugin skill `<plugin>:<skill_id>` already covers this need. Recommend adding a `references:` entry instead of authoring a new skill."
4. Caller (recruit Phase 2, design-agent) decides.

### `design-agent` Phase 2 consumption

During `op=propose_recipe`, scan the catalog for each `wanted_skills[*].description`. If a plugin skill matches, surface it in `wanted_skills[i].external_reference_candidate` so recruit can skip the author-skill-first gate for that entry.

## Anti-patterns

- MUST NOT write into other plugins' directories. Catalog writes only to `$COMPANY_ROOT/external-skills-catalog.json`.
- MUST NOT trust every plugin's frontmatter blindly. The catalog captures the plugin's SELF-description; downstream code should still verify via a sandboxed test invocation before REQUIRING the referenced skill.
- MUST NOT refresh on every turn. TTL exists for a reason — a full scan walks every plugin SKILL.md.
- Do NOT catalog `kiho` itself — it's the host plugin. Self-reference is handled via internal_skill types.
- Do NOT try to "install" a plugin that isn't present — discovery is read-only.

## Grounding

v6 plan §3.9. References schema in `references/skill-frontmatter-schema.md`. Settings at `settings.external_skills.{allow_references, catalog_ttl_days}`.
