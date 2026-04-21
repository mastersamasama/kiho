---
name: kb-init
description: Use this skill when kb-manager receives a request to bootstrap a fresh knowledge-base tier. Creates the root files (knowledge-base.md, rules.md, memos.md), all 12 empty index shells, and the raw/ + wiki/ + drafts/ subdirectories from templates. Idempotent — existing files are preserved. Normally called by kiho-setup during first-run scaffolding, not by end users. Only kb-manager should load this skill directly.
argument-hint: "tier=<project|company> root=<absolute-path>"
metadata:
  trust-tier: T2
  kiho:
    capability: create
    topic_tags: [bootstrap]
    data_classes: ["kb-wiki-articles", "templates"]
---
# kb-init

Bootstrap an empty knowledge-base tier. Called by kb-manager when a fresh KB is needed; normally triggered once per tier per project.

## Inputs

- `TIER` — `project` or `company`
- `ROOT` — absolute path to the tier root (`<project>/.kiho/kb/` or `$COMPANY_ROOT/company/`)

## Procedure

1. **Check existing state.** If `ROOT/knowledge-base.md` exists AND is non-empty, return `status: noop` with `already_initialized: true`. Do NOT overwrite.

2. **Create directories** using `Bash mkdir -p`:
   - `ROOT/raw/sources/` (project) or `ROOT/raw/lessons/` + `ROOT/raw/playbooks/` (company)
   - `ROOT/raw/decisions/` (project only)
   - `ROOT/wiki/entities/`
   - `ROOT/wiki/concepts/`
   - `ROOT/wiki/decisions/` (project only)
   - `ROOT/wiki/conventions/` (project only)
   - `ROOT/wiki/principles/` (company only)
   - `ROOT/wiki/rubrics/` (company only)
   - `ROOT/wiki/synthesis/`
   - `ROOT/wiki/questions/` (project only)
   - `ROOT/drafts/`

3. **Copy root files from templates:**

   For `project` tier:
   - `ROOT/knowledge-base.md` ← `templates/kb-knowledge-base.template.md`
   - `ROOT/rules.md` ← `templates/kb-rules.template.md`
   - `ROOT/memos.md` ← `templates/kb-memos.template.md`

   For `company` tier:
   - `ROOT/knowledge-base.md` ← `templates/kb-company-knowledge-base.template.md`
   - `ROOT/rules.md` ← `templates/kb-company-rules.template.md`
   - `ROOT/memos.md` ← `templates/kb-company-memos.template.md`

   Apply template substitutions (`{{project_name}}`, `{{user_name}}`, `{{iso_timestamp}}`, `{{company_root}}`) before writing.

4. **Create empty index shells** — all 12 (13 for company tier). Each file is:

   ```markdown
   ---
   generated_at: {{iso_timestamp}}
   generated_by: kb-init
   entry_count: 0
   ---

   # {{index_title}} — {{tier}} tier

   (empty — will be populated by kiho-kb-manager on first ingest)
   ```

   Index files to create (same set for both tiers, plus `cross-project.md` for company only):
   - `index.md` (title: "Master index")
   - `log.md` (title: "Activity log")
   - `tags.md` (title: "Tag cloud")
   - `backlinks.md` (title: "Backlinks map")
   - `timeline.md` (title: "Timeline")
   - `stale.md` (title: "Stale pages")
   - `open-questions.md` (title: "Open questions")
   - `graph.md` (title: "Wiki graph")
   - `by-confidence.md` (title: "By confidence")
   - `by-owner.md` (title: "By owner")
   - `skill-solutions.md` (title: "Skill solutions") — include these section headers:
     ```markdown
     ## By entity
     (empty)

     ## By concept
     (empty)

     ## By question (open)
     (empty)
     ```
   - `cross-project.md` (company tier only, title: "Cross-project provenance")

5. **Return a receipt:**

   ```markdown
   ## Receipt <REQUEST_ID>
   OPERATION: init
   TIER: <tier>
   STATUS: ok
   ROOT: <root>
   CREATED_FILES: [<list of new files>]
   SKIPPED: [<list of files that already existed>]
   ```

## Anti-patterns

- Never overwrite existing content. Idempotent create-only.
- Never create a `.git/` directory. kiho does not assume git.
- Never write to any path outside `ROOT`. If `ROOT` resolution failed, return `status: error`.
- Never call `kb-add`, `kb-update`, or any other KB op from within `kb-init`. This skill only scaffolds empty structure.
