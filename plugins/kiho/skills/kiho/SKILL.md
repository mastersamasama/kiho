---
name: kiho
description: Use this skill whenever the user invokes /kiho or asks kiho to do anything. Single entry point that parses mode flags, loads the CEO persona, spawns departments, runs the Ralph autonomous loop, delegates tasks, coordinates committees, integrates decisions into the KB, and evolves skills over time. Dispatches across all modes — /kiho feature, /kiho --bugfix, /kiho --refactor, /kiho --vibe, /kiho --debate, /kiho --resume, /kiho kb-init, /kiho evolve — plus implicit mode detection when the user passes a PRD file path or a plain description. Also triggers when the user says "kiho" or "have kiho" followed by any task (e.g., "have kiho build the auth flow"). Invoke this skill for multi-agent orchestration, cross-team planning, PRD ingestion, committee debate, agent recruitment, knowledge-base bootstrap, or skill evolution — even when the user does not explicitly say "kiho".
argument-hint: "<mode-or-description-or-prd-path>"
metadata:
  trust-tier: T3
  version: 2.1.0
  lifecycle: active
  kiho:
    capability: orchestrate
    topic_tags: [orchestration]
    data_classes: ["kiho-config", "ceo-ledger", "continuity", "plan"]
---

# kiho — entry-point skill

This file is the discoverable entry point that Claude Code's plugin harness finds at the conventional `skills/kiho/SKILL.md` path. The authoritative harness instructions (Ralph loop, CEO persona loading, mode dispatch, department spawning, committee coordination, KB integration, skill evolution) live at the canonical kiho-harness SKILL.md below.

## What to do when this skill triggers

Read the canonical harness SKILL.md and follow it to the letter. Do not perform the requested work inline — route everything through the CEO persona it instructs you to load.

**Canonical SKILL.md:** `${CLAUDE_PLUGIN_ROOT}/skills/core/harness/kiho/SKILL.md`

Use the Read tool on that path, then execute its instructions using the user's argument (the full text after `/kiho`) as the mode / description / PRD-path input.

## Why this shim exists

The kiho plugin organizes its internal skill catalog hierarchically under `skills/{_meta,core,kb,memory,engineering}/…/<skill>/SKILL.md` to keep the authoring taxonomy (capability verb × topic × domain) clean. Claude Code's plugin skill auto-discovery, however, looks for skills at the flat `skills/<name>/SKILL.md` path and does not recurse into nested category directories. This file exists solely to bridge that gap for the single user-facing entry point. All other kiho skills remain internal — the CEO persona loads them by file path from the canonical tree, so they do not need to appear in the harness's available-skills list.

## Do not modify the harness here

If you need to change kiho's harness behavior (Ralph loop semantics, mode flags, dispatch rules, CEO bootstrapping), edit the canonical file at `skills/core/harness/kiho/SKILL.md` — not this shim. This shim's frontmatter description **must** stay in sync with the canonical's description so triggering remains consistent; everything else delegates.
