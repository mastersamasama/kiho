# Agent schema v2 (kiho v6)

**Status:** foundation shipped in v6.0.0-alpha.1 (PR #1).
**Full behavior wired:** v6.0.0-beta.1 (PR #2 — design-agent upgrade, auto-recruit, memory-seed).

This document is the canonical reference for the `agent.md` file format at `$COMPANY_ROOT/agents/<id>/agent.md`. It supersedes the implicit v5 schema defined only by `templates/soul.template.md`.

## Why v2

v5 agents were persona + soul stubs. Users observed:

- `role` fields named the project (e.g., "33Ledger Mobile Lead") → the agent couldn't work on a second project without rewriting
- `memory/` directories were empty after careful-hire → no lessons / todos / observations to carry forward
- `skills:` was a bare string list → no validation that an ID actually resolved to a file in the company skill library
- No record of what projects the agent has worked on → no portfolio, no interview tiebreaker
- No current-state tracking → CEO couldn't tell whether an agent was busy, free, on leave, or retired

v2 enforces: **agents are portable professionals with persistent experience, rolling state, validated skill references, and seeded memory.** Projects come and go; the agent continues.

## File shape

```
$COMPANY_ROOT/agents/<id>/
├── agent.md           # persona + schema v2 frontmatter + soul body + portfolio
├── memory/
│   ├── lessons.md     # semantic reflections (τ 180d)
│   ├── todos.md       # pending work items
│   ├── observations.md # episodic observations (τ 14d)
│   └── .last-reflect  # ISO-8601 timestamp of last memory-reflect
└── soul-overrides/    # jsonl drift queue (v5.20 format; kept)
```

## Frontmatter fields

| Field | Type | Required | Enforced by |
|---|---|---|---|
| `schema_version` | integer | yes | lint — must equal 2 for v6 |
| `name` | string | yes | lint — non-empty |
| `id` | string | yes | lint — must match directory name |
| `role_generic` | string | yes | lint — must NOT contain any project name in `$COMPANY_ROOT/project-registry.md` |
| `role_specialties` | string[] | yes | lint — each entry must NOT contain any project name |
| `soul_version` | string | yes | must be `v5` for v6 (we kept the 12-section soul) |
| `experience` | object[] | yes (may be `[]`) | lint — if non-empty, each entry must have `project`, `role_on_project`, `started` |
| `current_state.availability` | enum | yes | `engaged` \| `free` \| `on_leave` \| `retired` |
| `current_state.active_project` | string or null | yes | nullable; when non-null, must appear in `experience[]` |
| `current_state.active_assignment` | string or null | yes | nullable |
| `current_state.last_active` | ISO-8601 | yes | updated by CEO at every turn the agent is invoked |
| `skills` | string[] | yes | lint — every ID must resolve to `$COMPANY_ROOT/skills/<id>/SKILL.md` |
| `memory_path` | string | yes | lint — directory must exist with `lessons.md`, `todos.md`, `observations.md` non-empty |
| `tools` | string[] | yes | standard Agent tool list subset |
| `hire_provenance` | object | yes | written at recruit, immutable |

## Soul body (`## Soul` heading)

Unchanged from v5 — 12 sections, append-only trait history. See `templates/soul.template.md`.

Constraint: §1 biography and §4 red-line objects MUST NOT name any project. Lint checks with substring match (case-insensitive) against `$COMPANY_ROOT/project-registry.md`.

## Portfolio (`## Portfolio` heading)

Auto-rendered from `experience[]` by `bin/portfolio_render.py` (ships in PR #2). Do not edit by hand. The generator's last-run timestamp is embedded as an HTML comment.

## Lint rules (PR #1 warn-only, PR #3 enforce)

`bin/agent_md_lint.py` enforces:

1. `schema_version == 2`
2. Frontmatter contains all required fields above
3. `role_generic`, `role_specialties[i]`, soul §1 biography, soul §4 red-line objects — none contain a case-insensitive substring match against any line in `$COMPANY_ROOT/project-registry.md`
4. Every `skills[i]` — file `$COMPANY_ROOT/skills/<skills[i]>/SKILL.md` exists
5. `memory_path` directory exists; `lessons.md`, `todos.md`, `observations.md` all present and each > 0 bytes
6. `current_state.active_project` — if non-null, must equal the `project` of some entry in `experience[]`

Warn-only mode (PR #1): emits warnings on stdout, exits 0.
Enforce mode (PR #3): emits errors, exits 1.

## Migration from v5

`bin/migrate_v5_to_v6.py` rewrites existing v5 agent.md:

- Extracts project name from `role` → creates first entry in `experience[]`
- Strips project name from `role` → `role_generic` (warn if no clean generic form found)
- Sets `current_state.availability = "free"`, `active_project = null`, `last_active = mtime of v5 file`
- Preserves `skills[]`, `tools`, soul body
- If `memory_path` doesn't exist: creates directory + seeds `lessons.md` with "migrated from v5" marker + `todos.md`/`observations.md` empty stubs (non-empty)
- Writes `schema_version: 2`, `soul_version: v5`
- Writes provisional `hire_provenance` extracted from any existing RECRUIT_CERTIFICATE marker; else marks `hire_type: "v5-migrated"` with nullable fields

Dry-run mode (PR #1): writes `agent.md.v6proposed` sibling, runs lint on it, presents diff, does not replace. Default.
Auto-apply mode (PR #3): swaps atomically if lint passes; otherwise keeps v5 and logs `.migration-blocker`.

## Related

- `templates/agent-md-v2.template.md` — template used by design-agent
- `templates/company-settings.template.md` — company settings schema
- `templates/project-registry.template.md` — lint seed list
- `bin/agent_md_lint.py` — validator
- `bin/migrate_v5_to_v6.py` — migration
- `references/company-settings-schema.md` — companion doc for `$COMPANY_ROOT/settings.md`
- v6 evolution plan — see PR-attached plan doc
