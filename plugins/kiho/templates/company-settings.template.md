---
# kiho v6 company-level settings
#
# Location: $COMPANY_ROOT/settings.md
# Read by: CEO INITIALIZE step 1 (after plugin config.toml).
# Precedence: company settings OVERRIDE plugin defaults; missing keys FALL BACK to plugin.
# Scaffolded automatically by kiho-setup on first v6 turn when the file is missing.
# Edit by hand; no CLI required. Propagation is live — next turn picks up changes.

schema_version: 1

# ---- Company metadata ----

company_metadata:
  name: "My Kiho Workshop"
  primary_timezone: "Asia/Hong_Kong"

# ---- Language & tone (live-propagates to committee transcripts, CEO narration, subagent briefs) ----

# Output language for all CEO narration, committee transcripts, and subagent briefs.
# BCP 47 code. Common values: en | zh-TW | zh-CN | ja | ko.
# When set, every subagent brief appends a "Company output constraints" section
# with `Output language: <value>` (see §3.7 of v6 plan).
official_language: "zh-TW"

tone:
  # collaborative-formal | terse | playful
  formality: "collaborative-formal"
  # Whether agent-produced output can include emoji. UI-facing content (like the
  # 33Ledger app) is unaffected; this governs kiho's orchestration output.
  emoji_in_agent_output: false

# ---- Recruit (gap-healing reflex, §3.3) ----

recruit:
  # v6 core: trigger auto-recruit when capability gap detected — either from
  # RACI fail on a plan item OR mid-wave CEO realizing no agent covers a need.
  # When false, CEO falls back to ASK_USER as in v5.
  auto_trigger_on_gap: true

  # Hard minimum candidates produced by recruit. User direction: always 4, no
  # more quick/careful split. Can be raised; cannot be lowered below 4.
  min_candidates_always: 4

  # Rubric score required by the hiring committee to close without re-interview.
  committee_gate_threshold: 4.0

  # When top-2 candidates are within this delta AND have non-overlapping
  # strengths, design-agent synthesizes a merged persona. Re-interviewed; if
  # score >= max(top1, top2) the synth wins, else top1.
  synthesis_when_complementary: true
  synthesis_rubric_delta_max: 0.20

  # After hire, populate agents/<id>/memory/{lessons,todos,observations}.md
  # from the interview + work-sample output. Prevents the empty-memory drift
  # seen in v5 careful-hires.
  memory_seed_on_hire: true

  # Runaway guard. If more than this many auto-recruits are needed in one turn,
  # CEO prompts the user instead of silently spawning.
  max_auto_recruits_per_turn: 2

  # Within recruit Phase 2: if the agent's skill proposal names a skill absent
  # from the company library, research + author it BEFORE moving to Phase 3.
  skill_research_before_design: true

  # Cap on new skills authored by a single recruit. Overflow → multiple recruits.
  max_skills_authored_per_recruit: 3

# ---- Skill library ----

skill_library:
  # Promote reusable research to skills automatically when the same artefact
  # is referenced >= reuse_threshold_count times across turns.
  auto_consolidate_research: true
  reuse_threshold_count: 2

  # Consolidation cycle (merge overlapping, deprecate stale). Cadence in days
  # OR after N new skills authored (whichever first). 0 disables.
  consolidate_cadence_days: 30
  consolidate_cadence_new_skill_count: 5

  # Skills with zero invocations in this many days AND no dependents become
  # candidates for deprecation by consolidate-skill-library.
  stale_days: 60

# ---- Project-KB / company-KB consolidation ----

kb_consolidation:
  # Run consolidate-project-kb every N CEO turns on a given project.
  project_kb_cadence_turns: 10
  # Run consolidate-company-kb every M days OR after P cross-project turns
  # (whichever first).
  company_kb_cadence_days: 30
  company_kb_cadence_turns: 20

# ---- Startup behavior ----

startup:
  # Read this file + $COMPANY_ROOT/company/wiki/index.md + skills/INDEX.md at
  # every CEO INITIALIZE. Disable only for debugging.
  read_company_wiki_on_init: true
  read_settings_on_init: true

  # Warn when company KB files are stale (not modified in this many days).
  warn_if_stale_days: 7

  # Warn when an agent is assigned to the active project but agent.md mtime
  # is older than the project's most recent activity.
  warn_if_agent_mtime_older_than_project: true

# ---- Scope boundary (CEO DONE scope-promote sweep, §3.4) ----

promote:
  # CEO DONE step 3 runs scope-promote-classifier against new .kiho/audit/**
  # and .kiho/state/research/** files created this turn. false = no auto sweep.
  auto_scope_classify_on_done: true

  # Dry-run diff presented to user before any write to $COMPANY_ROOT.
  dry_run_before_write: true

# ---- Performance amplification (§3.10) ----

performance:
  # Rank candidate skills (in USE/IMPROVE/CREATE decision) by a blend of
  # success rate, user correction rate, and freshness.
  rank_skills_by_performance: true

  # Formula weights (must sum to 1.0).
  rank_weights:
    success_rate: 0.5
    inverse_correction_rate: 0.3
    freshness: 0.2

# ---- External skill referencing (§3.9) ----

external_skills:
  # When skill-discover scans $CLAUDE_PLUGINS and finds candidates, allow
  # authoring skills that reference them (instead of reimplementing).
  allow_references: true

  # TTL on the external-skills-catalog cache at $COMPANY_ROOT/external-skills-catalog.json.
  catalog_ttl_days: 7

---

# Company Settings — $COMPANY_ROOT/settings.md

This file is read by the CEO at every INITIALIZE (step 1) **after** the plugin-level
`config.toml`. Values here **override** plugin defaults. Missing keys fall back.

## Editing

Edit the YAML frontmatter above; save. The next `/kiho` turn picks up the change.
No CLI required. `kiho-setup op=scaffold-settings` regenerates this file from the
template if deleted or corrupted.

## Propagation

Setting changes propagate live:

- `official_language` → every subagent brief receives `Output language: <value>`;
  committee transcripts written in that language; CEO narration mirrors it.
- `tone.emoji_in_agent_output` → subagent briefs include `Emoji: forbidden` or allowed.
- `recruit.*` → next RACI assignment / mid-wave capability gap triggers
  auto-recruit with the configured thresholds and candidate count.
- `kb_consolidation.*` → consolidation skills run on the configured cadence.

## Fields reference

See `plugins/kiho/references/company-settings-schema.md` for per-field documentation,
valid ranges, and interaction rules. For v6 plan context: `.kiho/plans/zany-greeting-cookie.md` §3.1.
