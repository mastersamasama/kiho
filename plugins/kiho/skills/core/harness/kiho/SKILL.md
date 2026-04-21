---
name: kiho-harness-legacy
description: Deprecated — historical location of the kiho harness skill. The authoritative dispatcher now lives at skills/kiho/SKILL.md. Do not route through this file.
metadata:
  lifecycle: deprecated
  superseded-by: skills/kiho/SKILL.md
  version: 5.22.0
---

# Deprecated — consolidated into `skills/kiho/SKILL.md`

The kiho harness skill has been consolidated into the flat entry skill at
`${CLAUDE_PLUGIN_ROOT}/skills/kiho/SKILL.md`. This file is retained only so the
directory stays valid — `config.toml` (read by `agents/kiho-ceo.md` and
`skills/core/harness/kiho-setup/`) continues to live alongside it.

## Why this file exists at all

Earlier kiho versions split the harness between a flat discoverable shim
(`skills/kiho/SKILL.md`) and a nested authoritative SKILL.md at this path. That
split was a workaround for Claude Code's non-recursive skill auto-discovery,
not a deliberate separation of concerns. It forced an extra `Read` tool call
on every invocation and required two files to stay frontmatter-synchronized.

v5.22 consolidated everything into the flat entry skill. The authoritative
dispatcher — startup sequence, mode parsing, failure playbook, invariants —
lives there now. This file is kept as a no-op because:

- `config.toml` still lives in this directory and is read by absolute path
- 39 references in docs and bin scripts cite `core/harness/kiho/` as the
  config/data-class location; rewriting all of them is out of scope for the
  consolidation
- The `.skill_id` sidecar has been moved to `skills/kiho/.skill_id`, so this
  directory no longer owns the sk-001 identity

## Where to go

- User-facing skill: `skills/kiho/SKILL.md` (triggered by `/kiho`, natural
  language "kiho …", PRD paths)
- Ralph loop, INITIALIZE/LOOP/DONE: `agents/kiho-ceo.md`
- Config: `skills/core/harness/kiho/config.toml` (unchanged location)
- Deep references: `skills/kiho/references/worked-examples.md`,
  `references/rejected-alternatives.md` (see §A5 for the consolidation
  rationale), `references/grounding.md`

## Do not modify this file

Changes to kiho's dispatch behavior — mode flags, startup sequence, failure
routes — belong in `skills/kiho/SKILL.md`. Leaving a TODO here instead of
editing the real file will be silently ignored.
