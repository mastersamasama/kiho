# kiho scaffold tree reference

Complete directory layouts that `kiho-setup` creates. Loaded only when the caller needs the full tree.

## Contents
- [Company tier layout](#company-tier-layout)
- [Project tier layout](#project-tier-layout)
- [Empty index file shell format](#empty-index-file-shell-format)
- [Template substitution variables](#template-substitution-variables)

## Company tier layout

Scaffolded at `$COMPANY_ROOT/`:

```
$COMPANY_ROOT/
├── company/
│   ├── knowledge-base.md             # from templates/kb-company-knowledge-base.template.md
│   ├── rules.md                      # from templates/kb-company-rules.template.md
│   ├── memos.md                      # from templates/kb-company-memos.template.md
│   ├── index.md                      # empty shell
│   ├── log.md                        # empty shell
│   ├── tags.md                       # empty shell
│   ├── backlinks.md                  # empty shell
│   ├── timeline.md                   # empty shell
│   ├── stale.md                      # empty shell
│   ├── open-questions.md             # empty shell
│   ├── graph.md                      # empty shell
│   ├── by-confidence.md              # empty shell
│   ├── by-owner.md                   # empty shell
│   ├── skill-solutions.md            # empty shell (with sections: entities/concepts/questions)
│   ├── cross-project.md              # empty shell
│   ├── raw/
│   │   ├── lessons/                  # empty dir
│   │   └── playbooks/                # empty dir
│   └── wiki/
│       ├── entities/                 # empty dir
│       ├── concepts/                 # empty dir
│       ├── principles/               # empty dir
│       ├── rubrics/                  # empty dir
│       └── synthesis/                # empty dir
├── agents/                           # empty dir (HR will populate)
├── skills/                           # empty dir (evolution will populate)
├── evolution-log.md                  # empty file
└── settings.md                       # empty shell with pointer to kiho/config.toml
```

## Project tier layout

Scaffolded at `<pwd>/.kiho/`:

```
.kiho/
├── CONTINUITY.md                     # from templates/CONTINUITY.md
├── state/
│   ├── org.json                      # from templates/org-bootstrap.json (deprecated — kept for backward compat)
│   ├── org-registry.md               # from templates/org-registry.template.md (replaces org.json)
│   ├── capability-matrix.md          # from templates/capability-matrix.template.md
│   ├── management-journals/          # empty dir (one .md per department leader)
│   ├── skill-invocations.jsonl       # empty file (skill usage tracking)
│   ├── agent-performance.jsonl       # empty file (per-agent task outcomes)
│   ├── ceo-ledger.jsonl              # empty file
│   ├── plan.md                       # from templates/plan.template.md
│   ├── AGENT.md                      # from templates/AGENT.template.md
│   ├── completion.md                 # from templates/completion.template.md
│   ├── briefs/                       # empty dir
│   └── research/                     # empty dir
├── committee/                        # empty dir
├── kb/
│   ├── knowledge-base.md             # from templates/kb-knowledge-base.template.md
│   ├── rules.md                      # from templates/kb-rules.template.md
│   ├── memos.md                      # from templates/kb-memos.template.md
│   ├── index.md                      # empty shell
│   ├── log.md                        # empty shell
│   ├── tags.md                       # empty shell
│   ├── backlinks.md                  # empty shell
│   ├── timeline.md                   # empty shell
│   ├── stale.md                      # empty shell
│   ├── open-questions.md             # empty shell
│   ├── graph.md                      # empty shell
│   ├── by-confidence.md              # empty shell
│   ├── by-owner.md                   # empty shell
│   ├── skill-solutions.md            # empty shell
│   ├── raw/
│   │   ├── sources/                  # empty dir
│   │   └── decisions/                # empty dir
│   ├── wiki/
│   │   ├── entities/                 # empty dir
│   │   ├── concepts/                 # empty dir
│   │   ├── decisions/                # empty dir
│   │   ├── conventions/              # empty dir
│   │   ├── synthesis/                # empty dir
│   │   └── questions/                # empty dir
│   └── drafts/                       # empty dir (kb-manager scratch)
├── specs/                            # empty dir (kiro-style spec folders land here)
├── agents/                           # empty dir (recruited project agents)
│   └── <name>/
│       └── memory/
│           └── soul-overrides.md     # trait-drift entries (written by memory-consolidate)
├── skills/                           # empty dir (project-tier skill overrides)
├── recruitment/                      # empty dir
└── cache/                            # empty dir (lint results, skill-find caches)
```

## Empty index file shell format

Every empty index file starts with this shell:

```markdown
---
generated_at: {{iso_timestamp}}
generated_by: kiho-setup
entry_count: 0
---

# {{index_name}} — {{tier}} tier

(empty — will be populated by kiho-kb-manager on first ingest)
```

Fill `{{index_name}}` with the human-readable index title, e.g. "Master index", "Tag cloud", "Backlinks map", "Timeline", "Stale pages", "Open questions", "Graph", "By confidence", "By owner", "Skill solutions".

## Template substitution variables

When copying template files, replace these variables before writing:

| Variable | Source | Example |
|---|---|---|
| `{{project_name}}` | Name of current directory (basename of pwd) | `33ledger` |
| `{{project_slug}}` | kebab-case version of project_name | `33ledger` |
| `{{user_name}}` | Current user (from environment or "user") | `wky` |
| `{{company_root}}` | Resolved `company_root` from config | `D:/Tools/kiho/` |
| `{{iso_timestamp}}` | Current UTC ISO-8601 with Z suffix | `2026-04-12T14:22:00Z` |

Use `Read` to load the template, substitute variables inline, then `Write` the result to the target path. Do not modify the original template file.

## Idempotency rule

For every target path:
- Exists and non-empty → skip, add to `skipped` list
- Missing → create from template, add to `created_files` list
- Exists but 0 bytes → replace from template, add to `created_files` list

Never overwrite non-empty content. User-modified KB files are preserved across re-runs.
