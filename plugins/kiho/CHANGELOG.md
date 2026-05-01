# CHANGELOG — kiho plugin

Historical narration of kiho version milestones. Moved out of `CLAUDE.md` on 2026-04-17 to keep the main-agent instructions focused on load-bearing rules only.

Runtime load-bearing concepts (capability taxonomy, topic vocabulary, trust tiers, storage architecture) are referenced from `CLAUDE.md` and the `references/` index — this file is for history, not for runtime decisions.

---

## v6.6.0 — Lint sidecar multi-tool support (Biome + Oxlint) — 2026-05-01

### Added — Layer 2 sidecar now ships four toolchain paths

The theme-contrast-guard skill (sk-088, introduced in v6.5.0) had a single Layer 2 lint sidecar template — ESLint-only — even though many kiho-using projects use Biome or Oxlint. v6.6.0 closes that gap with a researched, four-path topology.

- **Biome v2 GritQL sidecar (works today, no npm dep):**
  - `plugins/kiho/templates/biome-kiho.template.json` — host config with `plugins[]` array and `overrides[].include` exemptions for theme/charts/tests.
  - `plugins/kiho/templates/grit/no-literal-theme-import.grit` — bans `import { palette | macaron | acColors }` outside theme module.
  - `plugins/kiho/templates/grit/no-color-scheme-in-app.grit` — bans `useColorScheme` import from `'react-native'` outside ThemeProvider.
  - `plugins/kiho/templates/grit/no-hex-in-jsx-style.grit` — bans literal `#xxx` / `rgb(...)` / `rgba(...)` / `hsl(...)` / `hsla(...)` inside JSX `style={...}` props.
  - Capability ceiling: diagnostic-only (no autofix) per Biome v2.4.x plugin API. Modeled on Biome's own "No inline style props" + "Ban hardcoded colors" + "No restricted imports" official recipes.

- **Oxlint sidecar (alpha plugin API):**
  - `plugins/kiho/templates/oxlint-kiho.template.json` — config skeleton referencing future `eslint-plugin-kiho` via `jsPlugins`. Loadable as-is once `eslint-plugin-kiho` is published; alpha API caveat documented inline.

- **grep-fallback (toolchain-agnostic stop-gap, works today):**
  - `plugins/kiho/templates/lint-fallback-grep.sh` — POSIX bash, three regex patterns, exits 1 with violation list.
  - `plugins/kiho/templates/lint-fallback-grep.ps1` — Windows PowerShell parity. Same exit semantics.

- **Research report (≥ 3 authoritative citations):**
  - `plugins/kiho/skills/engineering/theme-contrast-guard/references/lint-sidecar-research-2026-05-01.md` — survey of Biome GritQL plugin maturity, Oxlint JS plugin alpha status, recommended sidecar topology, per-toolchain migration paths. Citations: Biome Linter Plugins docs, Biome v2 announcement blog, Biome GritQL Recipes, Oxlint JS Plugins docs, Oxlint Writing JS Plugins docs.

### Updated

- `plugins/kiho/skills/engineering/theme-contrast-guard/SKILL.md` — Layer 2 row in the 4-layer table now reads "Lint-time sidecar (ESLint / Biome / Oxlint / grep-fallback)". A new "Layer 2 toolchain paths" sub-section documents the per-tool maturity matrix and pick-when guidance. Cross-references list the new templates.
- `plugins/kiho/skills/engineering/theme-contrast-guard/references/migration-playbook.md` — Phase 2 rewritten as four parallel paths (A: ESLint, B: Biome, C: Oxlint, D: grep-fallback) with concrete inventory commands per tool. Cross-project reuse table extended with v6.6.0 templates.

### Unchanged

- `plugins/kiho/templates/eslint-kiho-config.template.cjs` — preserved as-is. ESLint remains a first-class path.
- All Layer 1 / Layer 3 / Layer 4 templates and skill definitions unchanged.

### Why a fallback ships alongside the plugins

Three reasons: (a) `eslint-plugin-kiho` is not yet published — without the npm package, ESLint and Oxlint paths have a config but no rules; (b) Phase 0 / Phase 1 of the rollout deliberately defers the plugin install — a CI-side grep gives early signal; (c) heterogeneous monorepos (Biome at root + ESLint in one workspace) need a tool-agnostic backstop. The fallback's README documents that it is a stop-gap and should be removed once the plugin paths mature.

### Closes drift detected on 33Ledger 2026-05-01

Turn 5 cleanup task B identified the gap between the SKILL.md Layer 2 description and the single-tool template inventory. v6.6.0 widens template coverage without changing rule semantics or breaking existing v6.5 ESLint adopters.

### Migration

- v6.5.x ESLint adopters: no action required — the existing template is unchanged.
- v6.5.x projects on Biome / Oxlint that previously had no sidecar: copy the new template + (Biome only) the three `.grit` files; merge into existing config.
- All projects: optionally wire the grep-fallback as a non-blocking CI step during Phase 0/1 of rollout.

---

## v6.5.2 — 2026-05-01

### Bug fixes
- **strict Ralph: catch structural soft-stop in `next_action` field** — v6.5.1's `check_soft_stop_drift` only inspected natural-language narration; this release adds Signal 3 that scans the final structured summary's `next_action` field for "下個 /kiho / next /kiho / re-invoke" patterns and escalates to CRITICAL when plan.md Pending is non-empty. Closes drift first observed on 33Ledger 2026-05-01 (Turn 1.5 multi-provider).
- `agents/kiho-ceo.md` — invariant explicitly forbids `next_action` strings that defer to a future /kiho invocation; LOOP step g.CHECK COMPLETION clarifies that "Turn N" Pending items count as Pending.
- `skills/kiho/SKILL.md` — anti-pattern doc updated.

---

## v6.5.1 — strict Ralph loop invariant + Alert.alert hardcoded sweep

### Added
- **No-soft-stop invariant** in `agents/kiho-ceo.md` — CEO MUST NOT emit
  「要我繼續嗎」 / "shall I proceed" / "want me to start Turn N" prompts mid-loop;
  must either iterate or call `AskUserQuestion` or exit with `status: complete`.
- **`check_soft_stop_drift` audit** in `bin/ceo_behavior_audit.py` — flags
  `soft_stop_drift` MAJOR when DONE entry lacks `AskUserQuestion` AND
  `status != complete` AND plan.md Pending was non-empty (or matches the
  soft-stop regex pattern in the turn summary).
- **Alert.alert literal regex** in `bin/i18n_audit.py` — extends hardcoded-string
  detection to catch `Alert.alert("Title", "Body")` patterns. Surfaces 4+ findings
  on 33Ledger that previously slipped past.

### Closes drift detected on 33Ledger 2026-05-01 Turn 1 — CEO emitted three soft-stop prompts ("要不要繼續", "要我立刻開 Turn 1.5 嗎？", "要我繼續嗎") instead of iterating; plan.md had 5 turns of pending work after Turn 1.

### Migration
- Existing v6.4 / v6.5.0 sessions: no breaking changes. v6.5.1 audit script will start surfacing `soft_stop_drift` from the next CEO turn that uses the v6.5.1 cache.
- `claude plugin update kiho` to pull the new cache.

---

## v6.5.0 — i18n-audit + theme-contrast-guard

### Added
- **sk-087 i18n-audit** (`skills/engineering/i18n-audit/`) — 5 deterministic checks for kiho-using projects: locale parity, placeholder integrity, untranslated keys, hardcoded user-visible strings, dead-key detection. Glossary clarity heuristic stub for v6.6. Surfaces via `/kiho evolve --audit=i18n` or auto-detect on `project-card.toml::i18n_locales_path`. Output JSON + markdown to `<project>/.kiho/audit/i18n/<iso-date>.md` (Lane A). Exit-code matrix: 0 clean / 1 warn (dead-key) / 2 fail (parity / placeholder / hardcoded) / 3 crash.
- **sk-088 theme-contrast-guard** (`skills/engineering/theme-contrast-guard/`) — Layer 1 of 4-layer WCAG contrast defence. Reads `theme/tokens.ts` + optional `tokens.contract.ts`, computes fg×bg pair matrix per theme, fails on AA (4.5:1 body) / AAA (7:1 hero numbers) / 3.0:1 (large text & borders). Heuristic name-classifier when contract file missing — adoption forcing function for `tokens.contract.ts`. Surfaces via `/kiho evolve --audit=contrast`.
- **References**: `references/i18n-quality.md`, `references/i18n-allowlist.example.toml`, `references/i18n-known-jargon.md` (advisory), `references/accessibility-doctrine.md`. WCAG 1.4.3 / 1.4.6 / 1.4.11 grounded.
- **Templates**: `templates/i18n-audit.yml` (GitHub Action), `templates/eslint-kiho-config.template.cjs` (ESLint sidecar 3 rules), `templates/tokens.contract.template.ts`, `templates/runtime-contrast-warner.template.ts` (Layer 3 dev warner).

### Smoke tests on 33Ledger
- i18n-audit surfaced **3 real placeholder bugs** (`stats.tags.filterActive` ICU plural in `en.json` collapsed to plain `{count}` in zh-TW/zh-CN/ja — CLDR rules silently dropped) + 91 hardcoded user-visible strings + 108 dead-keys.
- contrast-audit surfaced **1 heuristic-mode false-positive** (`pro.transfer` cross-product against `pro.tabPillActive`) — resolves by adopting `tokens.contract.ts` with explicit `pairsWith: ["bg", "surface"]`. Demonstrates the contract-adoption forcing function.

### Closes drift detected on 33Ledger 2026-04-29 (i18n: 5 hardcoded ActionSheetIOS / a11y strings) and 2026-04-30 (theme: 27 files macaron.* + 5 files useColorScheme() + zero CI lint).

### Migration
- 33Ledger Day-1 (this turn): `apps/mobile/src/components/{AccountRow,BackHeader,FeeRuleComposer}.tsx`, `apps/mobile/src/screens/AssetProScreen.tsx` 4 hardcoded strings → `t()` (test fixture exempt).
- 33Ledger Day-1 (this turn): `apps/mobile/src/theme/tokens.contract.ts` + `runtime-contrast-warner.ts` log-only Layer 3 wired in `__DEV__`.
- Remaining sweeps (Turns 2-6): UX P3/P1/P2 (Rules sim → Inline edit → PnL display); ESLint sidecar lint roll-out + codemod; ThemeProvider context split.

---

## v6.4.0 (content-routing classifier — KB / State / Memory taxonomy)

Closes a v6.3.0 failure mode: the new "every confidence ≥0.90 → kb_add" enforcement was correct in spirit but conflated three different content types, dumping turn-state-disguised-as-decisions into KB. The user surfaced this on 33Ledger 2026-04-30 after the previous turn produced 5 KB entries that an empirical audit classified as 80% turn artefact / 15% reusable principle / 5% memory-eligible. v6.4.0 adds the content-classification gate that v6.3.0 lacked.

User signal that triggered this release (verbatim): *"not only kb, update the skill level, in other project should check this as well, why you determine as kb? ... kb is project related info/knowledge like what is the function of this module, should use what component in what case, when writing frontend should use theme system like this ... not just put every decision into kb, this is more closer to state instead of kb, and decision is better consolidate as memory if it can be reusable with reason taken."*

### Three-lane taxonomy (deterministic classifier)

| Lane | Destination | Heuristic gate |
|---|---|---|
| **A — STATE** | `.kiho/state/ceo-ledger.jsonl` (`action: state_decision`) + optional `.kiho/audit/<spec>/<turn>.md` | ≥1 of: evidence_paths cited / feature-spec slug without generalising verb / ≤1-sentence reusable principle / reversible by re-running plan |
| **B — KB** | `.kiho/kb/wiki/<page-type>/` via `kiho-kb-manager op=add --trigger=<A-F>` | ≥3 of 4: generalisable noun-phrase or imperative title / 6-month-cold-read useful / reusable principle without commit ref / cross-references ≥1 KB entry |
| **C — MEMORY** | `agents/<name>/memory/lessons.md` (skill) + `~/.claude/projects/<encoded-cwd>/memory/feedback_*.md` (feedback) | ≥1 of: L-* prefix or lesson/rule/discipline keyword / process-shaped not code-shaped / "we got burned by X" reason chain / domain-independent |

Hybrid decisions (principle is KB, evidence is state) MUST split into TWO ledger entries — one per lane. Ambiguous classifications (no lane fits ≥3 heuristics) → `action: kb_deferred, reason: classification_ambiguous` with user surface in turn summary.

### Six explicit KB-update trigger scenarios

A KB write fires under ANY of six triggers, not only the v6.3 ≥0.90 confidence path:
- **A** — decision with reusable principle ≥0.90 [legacy v6.3 path]
- **B** — user explicit canonicalisation ("remember this", "always X", Chinese 「以後都要」) — bypasses confidence gate, routes to `conventions/`
- **C** — recurring-pattern detection (3+ delegations same pattern in session)
- **D** — spec/PRD section that defines a project-wide convention (capture on first read)
- **E** — committee architectural choice ≥0.85 (routes to `decisions/` AND `synthesis/`)
- **F** — code-review canonicalisation (Eng IC reports "pattern X repeated in N≥3 files")

Triggers B and D bypass the confidence gate — explicit-intent paths. kb-manager validates trigger-specific required fields (`user_quote` for B, `prd_anchor` for D, `committee_id` for E, `affected_files[]` for F, etc.); missing fields → `status: rejected, reason: missing_trigger_field`.

### Changes

- **`agents/kiho-ceo.md`**:
  - Two new Invariants: `[v6.4] Content-routing classifier` + `[v6.4] KB capture is multi-trigger`.
  - LOOP step e (INTEGRATE) gains `[REQUIRED v6.4 — KB-update trigger scenarios]` block (six A-F triggers) + `[REQUIRED v6.4 — Content-routing classifier]` block (three lanes A/B/C with heuristics + hybrid + ambiguous handling).
  - Existing `[REQUIRED v6.3]` block updated to be Lane-B-conditional + adds `--trigger=<A-F>` flag to `kb-manager op=add`.

- **`bin/ceo_behavior_audit.py`**:
  - Existing `check_kb_integrate_discipline` → renamed `check_kb_integrate_or_classify_skipped`; backwards-compat alias preserved. Now accepts ANY of `{kb_add, state_decision, memory_write, kb_deferred}` as valid follow-up to ≥0.90 `subagent_return`. Drift code renamed `kb_integrate_or_classify_skipped`.
  - New `check_kb_classification_drift(kb_root, drifts, turn_from)` — walks `.kiho/kb/wiki/decisions/*.md`; computes weighted state-ness score (4 heuristics, 0.0-1.0); ≥0.50 → MAJOR drift `kb_state_artefact`. Use `--turn-from <iso>` to grandfather pre-v6.4 entries.
  - New `check_orphan_state_lessons(state_root, drifts)` — flags `*-lesson*.md` / `lessons-*.md` files leaked into state/ (should be in memory). MINOR drift `lesson_in_state_should_be_memory`.
  - New CLI flag `--kb-root <path>` to enable the classification-drift check.
  - Wired into `main()` as a sixth pass after the existing fifth pass.

- **`agents/kiho-kb-manager.md`** — three new invariants:
  - `[v6.4] Lane-B 4-of-4 heuristic gate` — refuse writes that fail with `status: rejected, reason: lane_mismatch, suggested_lane: state_decision | memory_write`.
  - `[v6.4] Trigger-specific required fields validator` — refuse with `status: rejected, reason: missing_trigger_field, required: [...]` if `--trigger=<A-F>` lacks its required fields.
  - `[v6.4] op=extract sub-op` — atomically extracts durable nuclei from a source entry into fresh `concepts/` / `conventions/` entries, archives source to `.kiho/audit/`, refreshes all 12 indexes. Used during retroactive cleanup of pre-v6.4 KB drift.

- **NEW `references/content-routing.md`** — full decision tree + 6 worked examples (2 per lane) + audit-script enforcement summary. Linked from kiho-ceo.md INTEGRATE block.

### Smoke verification

```bash
python ${CLAUDE_PLUGIN_ROOT}/bin/ceo_behavior_audit.py \
  --ledger <project>/.kiho/state/ceo-ledger.jsonl \
  --kb-root <project>/.kiho/kb/wiki \
  --turn-from 2026-04-30T00:00:00Z --json
```

Expected on 33Ledger as of 2026-04-30: status `major`, drifts include `kb_state_artefact` flagging 4-13 entries (depending on grandfather date) — D-FU-LEDGER-STICKY-OPAQUE / D-FU-NEW-FIAT-LIST-FIRST / D-FU-DARK-MODE-SWEEP / D-FU-ASSET-DETAIL-INDICATORS score ≥0.50 state-ness; D-FU-ASSETS-URL-COLLISION is genuinely hybrid and may pass.

### Net scope

- 4 files modified (`agents/kiho-ceo.md`, `bin/ceo_behavior_audit.py`, `agents/kiho-kb-manager.md`, `.claude-plugin/plugin.json`)
- 1 file modified for narration (this CHANGELOG)
- 1 new reference (`references/content-routing.md`)

### Migration note

Pre-v6.4 KB entries do NOT auto-fail `kb_state_artefact` IF you pass `--turn-from <v6.4-release-date>` to the audit script. Default `--turn-from` is null (no grandfather; flags every state-shaped entry regardless of age). Projects intending to grandfather their legacy KB should pass the v6.4 release date.

---

## v6.3.0 (CEO discipline enforcement — auto-KB integrate + ralph anti-stop)

Closes two long-running drift modes observed in real-world `/kiho` sessions: (1) the CEO routinely skipped mid-loop KB integration despite the LOOP step e text saying "never skip"; (2) the CEO routinely exited DONE while `plan.md` Pending still had items, claiming "next /kiho turn will continue". Both were textual rules without runtime enforcement; v6.3.0 adds the enforcement layer.

User signal that triggered this release: 33Ledger session 2026-04-22..2026-04-29 ran 195 ledger seqs across multiple turns with **0 `kb_add` invocations vs ~54 decisions ≥0.90 confidence**. The user explicitly demanded auto-KB triggers + ralph anti-stop be baked into the plugin, not left as discipline-by-prose. Lessons authored at session end as `L-KB-MID-LOOP-MANDATORY` and `L-RALPH-PENDING-NONEMPTY` are now codified as audit checks.

### Changes

- **`agents/kiho-ceo.md`** — three text strengthenings:
  - **LOOP step e (INTEGRATE)** the "confidence ≥0.90 → kb_add" rule is now `[REQUIRED v6.3]` with explicit alternative path `action: kb_deferred, reason: <why>` ledger entry; silent skip is unacceptable. New text: "every kb_add MUST atomically update wiki/index.md (catalog row) + wiki/log.md (chronological entry); kiho-kb-manager v6.3+ enforces this internally" — Karpathy compliance per L-KARPATHY-NAV-FILES.
  - **LOOP step g (CHECK COMPLETION)** explicit `[REQUIRED v6.3]` rule "MUST NOT exit DONE while plan.md Pending non-empty" with 4 enumerated legitimate exits: AskUserQuestion / max_iterations / budget_exceeded / all_pending_blocked. "Anything else is drift."
  - **Invariants section** two new load-bearing MUSTs: `[v6.3] Auto-KB integrate per iteration` and `[v6.3] Ralph anti-stop`. Both reference the audit script enforcement.

- **`bin/ceo_behavior_audit.py`** — two new check functions:
  - `check_kb_integrate_discipline(entries, drifts)` — finds every `subagent_return` with confidence ≥0.90 and status ok/complete; verifies subsequent `kb_add` / `kb_deferred` / `kb_add_batch` entry within the same turn (between this entry and the next `tier_declared`/`initialize`/`done` boundary). Missing match = MAJOR drift `kb_integrate_skipped`.
  - `check_ralph_anti_stop(entries, project_root, drifts)` — for each `action: done` entry, walks back to turn start (last `tier_declared`/`initialize`), verifies presence of legitimate escalation entry (`ask_user`, `max_iterations_hit`, `checkpoint_via_route_d`, `budget_exceeded`, `all_pending_blocked`); else, naive scan of plan.md Pending section — if non-empty AND no escalation = MAJOR drift `ralph_stopped_early`.
  - Both wired into `main()` as a new "fifth pass" alongside existing OKR / approval-chain checks. Backward-compatible: pre-v6.3 ledger entries still flow through the new checks but are typically caught by `ledger_epoch: v5.22_active` amnesty unless `--full` is passed.

### Smoke verification

Run on a project ledger that has documented drift (e.g., 33Ledger session 2026-04-29):

```bash
python ${CLAUDE_PLUGIN_ROOT}/bin/ceo_behavior_audit.py --ledger <project>/.kiho/state/ceo-ledger.jsonl --json
```

Expected output: status `major` with `kb_integrate_skipped` + `ralph_stopped_early` drift entries surfaced. Baseline OKR / delegate / approval-chain checks unchanged.

### Net scope

- 2 files modified (`agents/kiho-ceo.md` + `bin/ceo_behavior_audit.py`)
- 1 file modified for version + narration (this CHANGELOG + plugin.json)
- 0 new skills / templates / hooks
- ~120 lines of Python added (2 audit check functions)
- ~20 lines of Markdown added (kiho-ceo.md text strengthening)
- Backward-compatible: rules apply forward; pre-v6.3 ledger amnesty preserved
- No breaking changes; existing `action` schemas unchanged

### Companion lessons (project-tier KB, not plugin-shipped)

These lessons should be authored in any project KB that shipped pre-v6.3 sessions:
- `L-KB-MID-LOOP-MANDATORY` — every confidence ≥0.90 decision → immediate kb_add or explicit kb_deferred
- `L-RALPH-PENDING-NONEMPTY` — Ralph LOOP must not exit DONE while Pending non-empty without escalation
- `L-KIHO-SPEC-ROUTING` — feature/bugfix/refactor MUST route through kiho-spec; bypass requires explicit kiho_spec_bypass_taken ledger
- `L-KARPATHY-NAV-FILES` — every project KB MUST maintain `wiki/index.md` + `wiki/log.md` per Karpathy LLM Wiki pattern

The kiho-kb-manager skill should be enhanced in v6.3.x patch releases to auto-author these on every `kb-init`.

---

## v6.0.1 (skill-search wiring — post-v6.0.0 audit fixes — forward-ported patch)

Closes 4 skill-search wiring gaps identified in the post-v6.0.0 audit (see plan §10.2b). v6.0.0 shipped the primitives (`skills/core/search/unified-search/`, `skills/_meta/skill-discover/`, `bin/embedding_util.py`, `external-skills-catalog.json`) but several decision points in recruit + CEO never actually invoked them. v6.0.1 wires every shipped primitive into the hot paths it was designed for, without adding any new skills, templates, or invariants.

This patch is forward-ported onto the v6.2.x line (current plugin version bumped from 6.2.1 → 6.2.2). The `v6.0.1` label refers to the post-v6.0.0 audit scope; the actual release carries the semantic forward-port version.

### Gaps closed

- **[P2 HIGH — recruit 2.4 external catalog].** `skills/core/hr/recruit/SKILL.md` Phase 2.4 now runs a new `2.4a-EXTERNAL` step BEFORE invoking `kiho-researcher`. For each `to_author` / `conflict_narrow` skill, it consults `$COMPANY_ROOT/external-skills-catalog.json` via `embedding_util.text_similarity(wanted.description, candidate.description)`; matches with `similarity >= 0.75` record an `external_reference_candidate` and SKIP `kiho-researcher` + `skill-derive`, instead authoring a thin wrapper skill that references the external plugin skill. Mirrors design-agent Step 2.3 (lines 123-150 of `core/hr/design-agent/SKILL.md`) — the two reflex paths now have equivalent external-catalog behavior. Guarded by `settings.external_skills.allow_references` and catalog-file existence.

- **[P3 HIGH — recruit 3.5 real helpers].** `skills/core/hr/recruit/references/skill-reconciliation.md` now contains concrete python-style `semantic_neighbor_exists()` and `feature_overlap()` helpers (real `unified_search(...)` calls and real `embedding_util.text_similarity(...)` calls) replacing the prior pseudocode placeholders. Phase 3.5.2 cross-candidate classify and 3.5.3 dedupe in the main `SKILL.md` now explicitly reference these helpers instead of pseudocode fig leaves. Jaccard remains as the import-failure fallback for `feature_overlap`.

- **[P6 MEDIUM-HIGH — CEO LOOP step b/c unified-search].** `agents/kiho-ceo.md` pre-delegation skill-gap check no longer escalates straight to `kiho-hr-lead op=auto-recruit` on a missing `skill_id`. It first invokes `unified-search(query: <skill_description>, scope: ["skills", "external"], limit: 3, min_score: 0.75)`; top hits with `score >= 0.75` substitute into `required_skills` and the original recruit is skipped, emitting a new `action: skill_substitution_via_search` ledger entry. On no match (or when unified-search is not scaffolded), the legacy recruit-escalate path runs unchanged. Guarded by `unified-search/SKILL.md` existence so fresh installs still work.

- **[P1 MEDIUM — recruit 2.3 semantic pre-check].** `skills/core/hr/recruit/SKILL.md` Phase 2.3 now runs a semantic pre-check in the `else (not Path.exists())` branch: invokes `unified-search` with `scope: ["skills"], min_score: 0.70`; if the top hit scores `>= 0.75`, renames `wanted.id_hint` to the matched ID and marks `resolved_reuse` with a `skill_semantic_match_in_validate` ledger entry. Falls through to `mark "to_author"` (legacy) on no match. Guarded by `unified-search/SKILL.md` existence.

- **[P7 LOW-MEDIUM (shipped) — scope-promote-classifier duplicate check].** `skills/kb/scope-promote-classifier/SKILL.md` Step 7 now prefers `unified-search(scope: ["company"], min_score: 0.80)` for its duplicate detection. The legacy TF-IDF heuristic remains as the fallback when `unified-search/SKILL.md` is absent. The output adds a `duplicate_source: "unified-search" | "tfidf"` field so downstream `kb-add` can weigh the signal appropriately.

### Invariants preserved

- PreToolUse hooks unchanged.
- CEO INITIALIZE required steps unchanged.
- CEO DONE step order unchanged.
- Recruit Phase 1-6 structure unchanged; only Phase 2.3, 2.4, and 3.5 received surgical insertions (new `2.4a-EXTERNAL` pre-step; new semantic-neighbor branch in 2.3; concrete helpers in 3.5.2/3.5.3). Existing 2.4a/b/c/d/e step labels are intact; 2.4a-EXTERNAL is an ADDITIONAL pre-step.
- Every unified-search invocation is guarded with `$COMPANY_ROOT/skills/unified-search/SKILL.md` existence so the patch is backward-compatible on installs where unified-search has not yet been scaffolded.
- No version bump beyond patch; no new skills; no new templates.

### Verification (per plan §10.2b)

1. Start a fresh `/kiho` turn on a project whose required capabilities partially overlap with an already-discovered external plugin skill (e.g. 33Ledger needs "agent-browser" and `onchainos:okx-dex-token` is in the catalog). Trigger auto-recruit; expect ledger entry `action: external_reference_candidate_matched, similarity_score: 0.xx`. Hired agent's skill list should include the authored thin wrapper (not a from-scratch re-implementation).
2. CEO delegates mid-wave to a role where `sk-X` is missing but `sk-Y` covers it semantically. Expect `action: skill_substitution_via_search, original, matched, score` — no new recruit fired.
3. Cross-candidate recruit with 4 candidates proposing nearly-duplicate skills should emit `action: candidates_deduplicated` with the merged `skill_id` — not 4 different authored skills.

### Net scope

- 4 files modified (3 for required fixes + 1 optional Tier 3): `skills/core/hr/recruit/SKILL.md`, `skills/core/hr/recruit/references/skill-reconciliation.md`, `agents/kiho-ceo.md`, `skills/kb/scope-promote-classifier/SKILL.md`
- 1 file modified for version + narration: `CHANGELOG.md` + `.claude-plugin/plugin.json`
- Python: 0 changes (pure markdown patch)
- Tests: 0 new (wiring surface — exercised via the verification flow above)
- Zero breaking changes; every new call site is guarded by existence checks or setting flags.

---

## v6.2.1 (OKR auto-flow gap fixes — wire the narratives)

Closes 10+ gaps identified in the post-v6.2.0 audit. v6.2.0 shipped narratives of auto-flow without fully wiring them; v6.2.1 converts every shipped claim into working code. Full report at `_proposals/v6.2.1-gap-fixes/00-gap-closure-report.md`.

### Hard auto-trigger gaps (closed)

- **Gap H**: `bin/cycle_runner.py:59` `HOOK_VERBS` frozenset now includes `"okr-checkin"`. CEO INTEGRATE step e extended with concrete hook handler — shells out to `bin/okr_derive_score.py`, then `Agent(subagent_type="kiho:kiho-okr-master")`. Cycle-close auto-checkin goes from decorative to functional.
- **Gap D**: `committee/SKILL.md` §Clerk extraction new step 6 — OKR-topic unanimous committees emit `committee_requests_okr_set` ledger action with clerk-assembled payload + `DEPT_COMMITTEE_OKR_CERTIFICATE`. CEO INTEGRATE dispatches `okr-master`.
- **Gap C**: `onboard/SKILL.md` step 8 rewritten. Dead-letter mentor-memory todo replaced with explicit `okr_individual_schedule_onboard` ledger entry carrying `fires_at` timestamp. Scanner pass-7 detects fired schedules and emits `onboard-dispatch` action.
- **Gap J**: `kiho-plan/SKILL.md` §Procedure new step 5a — Jaccard token-overlap auto-link from plan items to active OKRs. Auto-tag at ≥0.30, suggest at 0.15–0.30.
- **Gap A**: CEO step 17.5 rewritten with concrete `Agent(subagent_type=..., prompt=...)` and `AskUserQuestion({...})` invocation templates per action kind. Seven action kinds now have template dispatch.
- **Gap B**: Architectural clarification — scanner-dispatch is primary + REQUIRED; `okr-period.toml` cycle template is optional alternative for cycle-tracked periods.

### `$COMPANY_ROOT` compliance gaps (closed)

- **Gap E**: `okr_scanner.load_okrs` reads BOTH project-tier AND `$COMPANY_ROOT/company/state/okrs/`. Company-tier OKR in any location suppresses cross-project `propose-company` re-nudges.
- **Gap F**: `kiho-setup` new op `scaffold-okr-master` copies `kiho-okr-master.md` to `$COMPANY_ROOT/agents/` + seeds memory. CEO INITIALIZE step 1f auto-invokes.
- **Gap G**: `okr_scanner._load_cfg` layers config: DEFAULT → plugin → `$COMPANY_ROOT/settings.md` `[okr]` (TOML-in-markdown) → project `config.toml`.
- **Gap I**: `okr-individual-dispatch` stage 1 filter falls back to company-tier `agent-score-<period>.jsonl`; also checks both tiers for existing individual Os.

### Audit gap (closed)

- **Gap K**: `ceo_behavior_audit.py` two new MAJOR drift classes — `okr_hook_without_checkin` (cycle close with `aligns_to_okr` but no subsequent `okr_auto_checkin_from_cycle`) and `okr_committee_without_okr_set` (OKR-topic unanimous committee without `committee_requests_okr_set` / `okr_set` / `okr_set_request_skipped`). 8 new unit tests.

### Net scope

- 8 files modified + 1 new proposal doc + 0 deleted
- Python: +1 hook verb, +~180 lines scanner (company-tier + settings-md + onboard-dispatch + parse_timestamp), +~80 lines audit (2 new drift classes)
- Tests: +6 scanner tests, +8 audit tests → **59/59 passing** (was 45)
- 5 approval chains validate (unchanged from v6.2.0)
- Zero breaking changes; all changes additive or parameterized

### Why this is a patch release (not minor)

Every v6.2.1 change closes a gap in a v6.2.0 claim. No new user-facing capability shipped; the change set makes v6.2.0's advertised capability actually work. Backward-compat: `[okr] auto_trigger_enabled = false` still reverts to v6.1 explicit-only.

---

## v6.2.0 (OKR auto-flow — user reversal of committee-01)

Turns the v6.1 explicit-only OKR flow into a full-auto-with-user-acceptance-for-company-intent lifecycle. See `_proposals/v6.2-okr-auto-flow/00-reversal.md` for the user-direct-override record and `01-architecture.md` for the architectural reference.

**Context.** Committee-01 of v5.23 decided "no auto-cadence" — OKRs only invoked explicitly by the user. That conflicted with kiho's full-auto-org philosophy: every other ceremony in kiho is agent-autonomous (retrospective, shift-handoff, memo-inbox-read, org-sync, etc.). On 2026-04-24 the user directly reversed the cadence decision while preserving the committee's other invariants (three-level structure, certificate markers, stretch cap, one-concept-per-file storage). Time-based cadence remains rejected (committee's "ceremony noise" concern was valid); event-driven auto-flow is now adopted.

**Additional user requirement** layered on top: "HR called the agent work and agent base on its experience to work on and check by lead and HR and OKR master or even user." Implemented as: HR-lead dispatches candidate agents with an experience-using brief; agent drafts from its own memory (lessons/todos/observations) cited by ref; lightweight 1-round committee reviews (dept-lead + HR-lead + OKR-master + optional user).

### Shipped

1. **PR 1 — Skeleton** (`c3ed4eb`): new `kiho-okr-master` agent (parallel to kb-manager, sole OKR-tree coordinator, committee member not convener, certificate auditor not emitter). New `references/cycle-templates/okr-period.toml` 6-phase lifecycle template. New `skills/core/okr/okr-auto-sweep/` (sk-083) wrapping `bin/okr_scanner.py` deterministic scanner (10 unit tests). New CEO INITIALIZE step 17.5 (REQUIRED) that runs the scanner and routes per action kind. New `[okr]` config section with independent switches for each auto feature.

2. **PR 2 — HR-dispatched individual-O drafting** (`3b1c085`): the load-bearing PR. New `skills/core/okr/okr-dept-cascade/` (sk-084) for OKR-master → dept-lead memo fanout. New `skills/core/okr/okr-individual-dispatch/` (sk-085) orchestrating the full flow: filter candidates (capability-matrix ≥ 3 + agent-score ≥ 0.70) → spawn with experience-using brief → collect drafts → convene lightweight 1-round review committee (3-4 members) → approve/revise/reject per committee outcome. Brief template at `references/agent-brief.md` requires 4 memory-query invocations before drafting; validator checks `rationale_from_lessons` array cites memory refs by regex-checkable path. Committee spec at `references/review-committee.md` with 4 user-seat triggers (new agent / no prior OKR / score < 0.70 / 5 KRs). `skills/core/hr/onboard/SKILL.md` step 8 added: schedule individual-O proposal at iteration `[okr.auto_set] onboard_threshold_iter` (default 30).

3. **PR 3 — Cycle-close checkin + period-end cascade close** (`f58c1de`): new `skills/core/okr/okr-close-period/` (sk-086) batch + cascade close orchestrator walking the alignment tree leaf-first. New `bin/okr_derive_score.py` conservative score-delta deriver (formula: `0.05 × weight/100 × success_weight`, stretch ×0.5 multiplier, cap at 1.0; 9 unit tests). Cycle-runner `okr-checkin` hook verb registered in `orchestrator-protocol.md` — cycle close auto-updates aligned KRs via derive formula. `bin/ceo_behavior_audit.py` gains two new drift classes: `okr_stale_o` (MINOR: active O no-checkin > stale_days) and `okr_period_overrun` (MAJOR: period ended without close ledger entry).

### Five event triggers (no time-based cadence)

| Event | Action | Consumer |
|---|---|---|
| CEO INITIALIZE each turn | scanner emits action list | INITIALIZE step 17.5 |
| Period boundary (first 30 days + no company O) | `propose-company` → user AskUserQuestion | OKR-master + CEO |
| Company O set + missing dept Os | `cascade-dept` → memo dept-leads | OKR-master |
| Dept O set + missing individual Os | `cascade-individual` → HR dispatch | HR-lead (load-bearing flow) |
| Cycle close success + `aligns_to_okr` | `on_close_success` hook → `okr-checkin` | cycle-runner |
| Period end | `period-close` → batch leaf-first | OKR-master via `okr-close-period` |
| Parent O closed | `cascade-close` → defer/archive children | OKR-master |
| Onboard agent reaches threshold | `okr-individual-dispatch` single-agent | HR-lead via onboard |

### Invariants preserved from v6.1 committee-01

- Three-level O structure (company / department / individual) — unchanged
- Certificate markers: `USER_OKR_CERTIFICATE`, `DEPT_COMMITTEE_OKR_CERTIFICATE`, `DEPT_LEAD_OKR_CERTIFICATE` — unchanged
- Stretch KR cap at 0.7 for aggregate — unchanged
- One-file-per-O Tier-1 storage at `.kiho/state/okrs/<period>/` — unchanged
- `okr-set` / `okr-checkin` / `okr-close` atomic primitives — unchanged
- PreToolUse hook enforcement via `bin/hooks/pre_write_chain_gate.py` — unchanged
- "Only CEO calls AskUserQuestion" invariant — unchanged (OKR-master prepares preview; CEO bubbles)
- No time-based cadence — unchanged (v6.2 is event-driven, not time-driven)

### Net scope

- +4 new skills (sk-083 / 084 / 085 / 086), total now 86
- +1 new agent (`kiho-okr-master`)
- +2 new Python helpers (`okr_scanner.py`, `okr_derive_score.py`) + 2 new test files (19 new tests)
- +1 new cycle template (`okr-period.toml`)
- +1 new hook verb (`okr-checkin` in cycle-runner)
- +2 new audit drift classes
- +1 new `[okr]` config section with 8 independently-disableable switches
- +2 proposal docs (`_proposals/v6.2-okr-auto-flow/00-reversal.md` + `01-architecture.md`)

### Release posture

- `plugin.json` 6.1.0 → 6.2.0
- `marketplace.json` 6.1.0 → 6.2.0
- 45 unit tests pass (26 v5.22/v5.23 + 10 okr_scanner + 9 okr_derive_score)
- 5 approval chains validate (unchanged)
- Zero regression on v6.1 OKR explicit-invocation flow (atomic primitives unchanged)
- Backward-compat: setting `[okr] auto_trigger_enabled = false` in config reverts to v6.1 behavior

---

## v6.1.0 (v5.23 OA-integration — all six committees landed)

Committee-driven delta landed from `_proposals/v5.23-oa-integration/` (six committees closed unanimously at confidence ≥ 0.90 per `/kiho` planning turn 2026-04-23 and implementation turn 2026-04-24). Phase ordering followed `_proposals/v5.23-oa-integration/99-v5.23-roadmap.md`. **Five of six committees rejected adding new skill portfolios in favor of minimal extensions + small scripts on existing primitives** — only committee 01 OKR produces new skills (three). Net release scope: 3 new skills, 5 new Python helpers, 5 new data-storage-matrix rows, 5 approval chains (was 2), zero new agent roles, zero new PreToolUse hook scripts.

### Shipped — Phase A (pulse + broadcast)

1. **Committee 04 — pulse surveys (rejected new surface, three small reinforcements).** Documented `lightweight-committee` variant in `references/committee-rules.md` §Special committee types (min 2 members, 1-round cap, `research + choose` phases required, `suggest + challenge` optional). Added mandatory `process_friction` section to `skills/core/ceremony/retrospective/SKILL.md` — each participant's one-sentence answer to "What in this period's process blocked or slowed you?". Shipped `bin/pulse_aggregate.py` (stdlib-only, reads `values-flag.jsonl`, groups by topic with threshold-flagging).

2. **Committee 03 — broadcast (minimal extension).** Added wildcard recipients to `memo-send` SKILL: `@all`, `@dept:<name>`, `@capability:<verb>`. Wildcard emission auto-emits to the new `.kiho/state/announcements/<yyyy-mm-dd>-<slug>.md` Tier-1 surface (bulletin-board distinct from mailbox). Introduced `announcements` row in `references/data-storage-matrix.md`. Extended `shift-handoff` ceremony with an `unread-announcements` fifth section and the corresponding digest count. Added ledger actions `announcement_published` + `announcement_acknowledged`. Emission RACI: CEO / dept-leads emit freely; other agents require `basis: <committee-decision-path>` pre-emit check (skill-internal gate — no PreToolUse hook needed).

### Shipped — Phase B (infrastructure)

3. **Committee 02 — approval chains (declarative registry replaces Python-baked hooks).** Shipped `references/approval-chains.toml` with three chain definitions (`recruit-hiring`, `kb-writes`, `okr-individual`) — the existing v5.22 patterns re-expressed declaratively plus the new OKR chain from committee 01. Shipped `bin/approval_chain.py` helper (TOML loader, path→chain matcher, certificate-marker lister, `verify_ran` ledger-stage auditor; `--validate` / `--list-chains` / `--chain-for-path` CLI). Unified `bin/hooks/pre_write_agent.py` + `pre_write_kb.py` into single chain-aware `bin/hooks/pre_write_chain_gate.py` — reads `approval-chains.toml` at runtime and blocks any Write/Edit to a governed path lacking the chain's certificate_marker. Adding a new chain is now ≤ 20 lines of TOML with zero Python edits. `hooks.json` updated to register the unified gate for `Write|Edit`; old scripts kept as deprecation shims that delegate to the new gate. Extended `bin/ceo_behavior_audit.py` with `approval_chain_skipped` CRITICAL drift class — catches a chain_closed:granted ledger entry missing any `approval_stage_granted` entries. Added 13 unit tests covering schema validation, path matching, and verify_ran correctness (all 26 total tests — v5.22 + v5.23 — pass).

4. **Committee 06 — dashboard (regenerable T2).** Shipped `bin/dashboard.py` with six metrics (velocity, reliability + MTTR, hiring, committees, skill factory, KB) sourced entirely from existing JSONL streams + committee transcript close blocks. Per-cycle and quarterly periods. Output to `.kiho/state/dashboards/<period>.md` (new matrix row `dashboard-period-md`). Each metric gates its own inclusion by a named downstream consumer per cost-hawk veto rule — no decorative metrics. Integrated into `retrospective` SKILL's step 1 Gather — retrospectives open by loading the dashboard so narrative anchors to numbers. The seventh metric (top/bottom agent scores) stubs to "unavailable" until the agent-score JSONL from Phase C1 lands.

### Shipped — Phase C1 (quantitative performance)

5. **Committee 05 — agent cycle-outcome score (rejected peer-360, adopted telemetry-derived quantitative score).** Shipped `bin/agent_cycle_score.py` with formula `0.40 × invocation_rate + 0.30 × phase_owner_rate + 0.20 × committee_win_rate + 0.10 × kb_weight`. Output to `.kiho/state/agent-score-<period>.jsonl` (new matrix row `agent-cycle-score-jsonl`). Auditor personas (skeptic, pragmatist, cost_hawk, overlap_hunter) are excluded from `committee_win_rate` so challenging well-supported positions cannot depress their score. `agent-promote` SKILL step 2a added — promotion committees MUST cite the cycle-outcome score alongside capability-matrix + narrative; score < 0.70 hard-blocks `promote` / `cross_train` lateral widening unless committee decision explicitly counter-argues with cited evidence. Threshold and weighting are speculative at ship time; a recalibration committee is scheduled at end of the v5.23 period per decision.md explicit flag. Metric 7 in `bin/dashboard.py` automatically picks up the agent-score JSONL once emitted.

### Shipped — Phase C2 (OKR skill portfolio)

6. **Committee 01 — OKR framework (3 new skills + user-facing primer).** Authored `core/okr/` with `okr-set` (sk-080, capability `create`), `okr-checkin` (sk-081, capability `update`), `okr-close` (sk-082, capability `update`). All three skills gate against Tier-1 markdown at `<project>/.kiho/state/okrs/<period>/O-<period>-<level>-<slug>-<n>.md` per the new `okrs-period-md` data-storage-matrix row. `okr-set` enforces a RACI pre-emit gate per level: `company` → user-accept via `AskUserQuestion` (`USER_OKR_CERTIFICATE`), `department` → closed committee decision page prerequisite (`DEPT_COMMITTEE_OKR_CERTIFICATE`), `individual` → dept-lead approval via the existing `okr-individual` chain (`DEPT_LEAD_OKR_CERTIFICATE`). The approval-chains registry now has FIVE chains (was 3 at Phase B1 landing) — two added for OKR: `okr-company` and `okr-department`. `okr-checkin` appends per-KR history with > 0.20 regression detection via `values-flag`. `okr-close` computes weighted-mean aggregate with stretch KRs capped at 0.7, marks `status: closed`, optionally archives to `_closed/`. New user-facing primer at `references/okr-guide.md` covers when to set OKRs, the three levels, how OKRs help (alignment / focus / measurement) and — critically — how the framework makes **kiho itself** better (cycles can `aligns_to_okr`, dashboard metric 7 rolls up closed OKR scores, retrospectives get quantitative anchors, `agent-promote` step 2a cites closed individual OKRs as promotion evidence). `bin/dashboard.py` metric 7 automatically surfaces OKR aggregates once files exist. CATALOG.md routing block updated with `core.okr` sub_domain. Skill-factory 10-step pipeline was NOT invoked (factory targets greenfield authoring from user intent); instead the skills were authored directly with frontmatter-schema + authoring-pattern compliance, following the recruit/agent-promote precedent for hand-authored core skills. Cadence is explicit — no auto-triggers — matching the committee decision.

### Release posture — v6.1.0

- **Version bumped.** `plugin.json` 6.0.0 → **6.1.0**. `marketplace.json` was stale at 5.22.0 → synced to **6.1.0** with description reflecting the full v5.23 landing. Marketplace `metadata.version` bumped 1.0.0 → 1.1.0 to reflect the marketplace-manifest update itself.
- **Keyword additions**: `v5.23`, `v6.1.0`, `approval-chains`, `okr`, `dashboard`, `cycle-outcome-score`.
- **CLAUDE.md invariant additions — pending.** Committee 02 noted that `approval-chains-are-TOML-declared` MAY become a load-bearing invariant once in-the-wild use confirms no edge cases. Deferred to v6.2 after first real-project adoption.
- **Replay harness scenarios** (v5.22 shipped) should gain (a) approval-chain-skipped drift (CRITICAL, exit 3), (b) broadcast wildcard emission without basis (status: broadcast_basis_required), (c) OKR-set at each of the three levels with the pre-emit gate exercised. Deferred to v6.2 — harness addition is a separate cycle.

### Test regression

- All 26 unit tests pass (13 existing v5.22 `ceo_behavior_audit` + 13 new v5.23 `approval_chain`). Manual smoke verified:
  - Chain gate blocks all three OKR paths without certificate (exit 2) and allows with certificate (exit 0). All 5 chains pass `--validate`.
  - Dashboard renders 7-metric rollup from synthetic telemetry; idempotent modulo `Generated:` header.
  - Agent cycle score computes 0.867 / 0.900 / 0.050 for three-agent synthetic case with auditor exclusion verified.
  - Pulse aggregate correctly identifies threshold-exceeded topics within the window.
  - OKR hook gate distinguishes company vs department vs individual paths via terminal_path_pattern — no chain cross-talk.

### Summary for readers

- **3 new skills** (`okr-set`, `okr-checkin`, `okr-close`)
- **5 new Python helpers** (`approval_chain.py`, `pre_write_chain_gate.py` unified, `dashboard.py`, `agent_cycle_score.py`, `pulse_aggregate.py`)
- **5 new data-storage-matrix rows** (`announcements`, `dashboard-period-md`, `agent-cycle-score-jsonl`, `okrs-period-md`, implicit via approval-chains.toml)
- **5 approval chains** in `references/approval-chains.toml` (was 2 pre-v5.23)
- **1 user-facing reference** (`references/okr-guide.md`)
- **~2,700 lines** total across ~15 modified files + 9 new files
- **26 passing unit tests** (13 existing + 13 new); zero regression on v5.22 hook behavior

---

## v6.0.0 (PR #3 — final auto-evolution wave)

PR #3 closes the v6 evolution arc opened by PR #1 (non-behavioral scaffolding: templates, config, lint) and PR #2 (universal gap-healing reflex: recruit v6, auto-recruit on capability gap, settings propagation foundation). v6.0.0 turns kiho into a self-healing organization: missing files are auto-scaffolded inline, v5 agents auto-migrate on first v6 turn, the skill library and both KBs consolidate on cadence, external plugin skills are discoverable and referenceable (not re-implementable), skill ranking is performance-driven, and every retrieval flows through a single unified-search primitive.

### A. Self-healing + settings propagation (§3.7)

1. **`kiho-setup` auto-scaffolds missing files.** New targeted ops: `scaffold-settings` (writes `$COMPANY_ROOT/settings.md` from the PR #1 template), `scaffold-project-registry` (seeds detected projects from `$CLAUDE_PROJECTS`), `scaffold-company-index` (`$COMPANY_ROOT/company/wiki/index.md` shell), `scaffold-skills-index` (`$COMPANY_ROOT/skills/INDEX.md` shell). Each op is non-destructive (skips non-empty files) and callable inline by the CEO without running the full scaffolder.

2. **CEO INITIALIZE step 1 extended.** Reads plugin `config.toml`, then `$COMPANY_ROOT/settings.md` (merged key-by-key, company wins), then `company/wiki/index.md` + `skills/INDEX.md` + `project-registry.md`. Missing files trigger inline `kiho-setup op=scaffold-*` (non-blocking). Logs per action (`company_settings_merged`, `company_wiki_index_read`, `skill_library_size`, `project_registry_loaded`). New debug opt-out: `settings.startup.read_settings_on_init = false`.

3. **CEO INITIALIZE step 4.5 NEW — auto-migrate v5 agents.** For each `$COMPANY_ROOT/agents/*/agent.md` with `schema_version != 2`, invokes `bin/migrate_v5_to_v6.py --auto-apply`. Script produces `agent.md.v6proposed`, runs `agent_md_lint.py --enforce`, atomic-swaps on clean (keeps `.v5bak` backup) or writes `.migration-blocker` note on violations. Cap of 20 migrations per INITIALIZE guards against flooding; overflow logs `action: migration_cap_hit`.

4. **Settings propagation helpers.** New `bin/brief_builder.py` with `build_company_output_constraints(settings)` producing the `## Company output constraints` block (Output language / Tone / Emoji). CEO's DELEGATE step now pre-pends this block to every brief via a Bash call to `brief_builder.py build-constraints`. Committee skill reads `settings.official_language` before opening a transcript and writes every round's message bodies in that language. Agent labels + phase tags stay in English for parseability.

5. **`bin/migrate_v5_to_v6.py` auto-apply** (contract per `references/agent-schema-v2.md §Migration from v5`): parses v5 frontmatter, extracts project from `role:` → seeds `experience[0]`, strips to `role_generic`, sets `current_state.{availability:"free", active_project: null, last_active:<mtime>}`, preserves skills/tools/soul, seeds `memory/{lessons,todos,observations}.md` with non-empty stubs, writes `schema_version:2, soul_version:v5, hire_provenance.hire_type:"v5-migrated"`, runs lint, swaps atomically on pass. Supports `--dry-run`, `--agent-id`, `--agent-md`, `--all`, `--json`. Exit codes: 0 applied/already-v6/dry-run-proposed; 1 all blocked; 2 usage error.

6. **`bin/agent_md_lint.py --enforce` default.** Exits 1 on any R1-R6 violation. Opt-out via `--warn-only` preserved for alpha-site compatibility. Updated docstring + argparse defaults.

### B. Consolidation cycles (§3.8)

1. **Three new `_meta/` skills:**
   - `consolidate-project-kb/SKILL.md` — scans `<project>/.kiho/kb/wiki/` for clusters via `bin/embedding_util.py`, drafts `synthesis/<topic>.md`, routes via `kb-manager op=kb-add`
   - `consolidate-company-kb/SKILL.md` — same clustering at company scope + pair-wise dedupe at similarity ≥ 0.80 via `kb-manager op=kb-update`
   - `consolidate-skill-library/SKILL.md` — pair-wise feature overlap ≥ 0.70 → `skill-improve` merge; zero invocations ≥ `stale_days` with no dependents → `skill-deprecate`; ≥ 3 improvements in 90 days → `lifecycle: mature` tag proposal

2. **`bin/embedding_util.py` NEW** — cluster + similarity helper with 3-tier backend auto-select (sentence-transformers → sklearn+numpy TF-IDF → pure-Python stdlib TF-IDF). Public API `text_similarity(a,b)`, `cluster_files(paths, threshold)`, `cluster_texts(texts, threshold)`. CLI `similarity` / `cluster` subcommands for debugging.

3. **CEO DONE step 10b NEW — consolidation cadence gate.** Reads `settings.kb_consolidation.*` + `settings.skill_library.*`; three independent gates (project-kb turns, company-kb days OR turns, skill-library days OR new-skill count). Each gate, when fires, invokes the corresponding consolidate skill via kb-manager / hr-lead; proposals route through `AskUserQuestion` when `dry_run_before_write == true` (default). Cadence values ≤ 0 disable individual gates. New ledger `<project>/.kiho/state/consolidation-ledger.jsonl` tracks `last_*_consolidation_ts` + counters.

### C. External skill referencing (§3.9)

1. **Extended SKILL.md schema.** New `references:` block documented in `references/skill-frontmatter-schema.md` with 4 entry types: `internal_skill` (another company skill), `plugin_skill` (e.g. `onchainos:okx-dex-token`), `claude_global_skill` (e.g. `firecrawl:firecrawl`), `external_docs` (URL with purpose). 4-rule validation at authoring time.

2. **`skills/_meta/skill-discover/SKILL.md` NEW.** Scans `$CLAUDE_PLUGINS` (or `~/.claude/plugins/cache/`) for plugin SKILL.md files, parses frontmatter, writes `$COMPANY_ROOT/external-skills-catalog.json` with TTL from `settings.external_skills.catalog_ttl_days` (default 7). Hard-excludes `kiho` itself. Consumed by `skill-derive` Phase 2 and `design-agent` Phase 2 — before authoring, check whether a catalog entry ≥ 0.75 similarity already covers the need; if so, propose a `references:` entry instead.

3. **design-agent Phase 2 update.** Before emitting `FILL_BACK_REQUEST`, consults external-skills-catalog. If match found, emits `external_reference_candidate` on the recipe; recruit Phase 2.4 authors a thin internal wrapper whose frontmatter carries `references:` instead of a full implementation.

### D. Performance amplification (§3.10)

1. **`bin/kiho_telemetry_rollup.py` extended** with `--company-root` + `--performance-window-days` flags. Emits `$COMPANY_ROOT/company/skill-performance.jsonl` — one row per skill per 30-day window: `{skill_id, invocations, success_rate, median_duration_ms, user_correction_rate, last_invoked}`. Aggregates across every project's `skill-invocations.jsonl` found under env `$CLAUDE_PROJECTS` or standard default roots.

2. **Skill ranking doc.** New `skills/core/hr/design-agent/references/skill-ranking.md` with the formula `score = w_s·success_rate + w_c·(1−correction_rate) + w_f·freshness` where `freshness = max(0, 1 − days_since_last/90)`, weights from `settings.performance.rank_weights` (must sum to 1.0).

3. **design-agent Phase 2.3 update.** When multiple existing skills could cover a need, rank via the formula. Top → USE (in `skills[]`), middle → IMPROVE (flagged for next evolution cycle), bottom with `score < 0.4` AND no reverse dependents → DEPRECATE candidate for next `consolidate-skill-library` run. Cold-start rule (< 5 invocations → use `success_rate` alone).

### E. Orchestrated unified search (§3.11)

1. **`skills/core/search/unified-search/SKILL.md` NEW.** Single entry point for retrieval across project KB, company KB, skill library, external plugin skills. Inputs `{query, scope: [project|company|skills|external|all], filter?, limit?}`. Ranking blends embedding similarity with `perf_multiplier = 1 + 0.5·success_rate·freshness` (skills), `reuse_multiplier = 1 + min(0.3, reuse_count·0.05)` (KB), and additive `scope_bonus`. Fallback chain: sentence-transformers → sklearn+numpy TF-IDF → pure-Python stdlib TF-IDF.

2. **CEO INITIALIZE step 7 enhancement.** When unified-search is available, CEO prefers it for the KB seed check — richer retrieval than `kb-search` alone. Falls back to `kb-search` when unified-search is missing/errors. Preserves the existing log semantics.

### Migration

- **v5 → v6 auto.** First v6 turn auto-migrates every v5 agent.md (step 4.5); settings.md auto-scaffolded from template (step 1); company/skills INDEX skeletons written if missing. No user action required.
- **Enforce default.** `agent_md_lint.py` now enforces by default. Alpha sites that relied on warn-only pass `--warn-only` explicitly for one more release cycle; enforce becomes hard-mandatory in v6.1.
- **`.v5bak` retention.** The migration script keeps `agent.md.v5bak` indefinitely (no auto-cleanup). A future utility will sweep backups older than 30 days.

### Files

- new `bin/brief_builder.py`
- new `bin/migrate_v5_to_v6.py`
- new `bin/embedding_util.py`
- new `skills/_meta/consolidate-project-kb/SKILL.md`
- new `skills/_meta/consolidate-company-kb/SKILL.md`
- new `skills/_meta/consolidate-skill-library/SKILL.md`
- new `skills/_meta/skill-discover/SKILL.md`
- new `skills/core/search/unified-search/SKILL.md`
- new `skills/core/hr/design-agent/references/skill-ranking.md`
- new `references/skill-frontmatter-schema.md`
- modified `bin/agent_md_lint.py` (enforce default)
- modified `bin/kiho_telemetry_rollup.py` (+`performance_rollup`, +`collect_project_invocations`, `--company-root` flag)
- modified `agents/kiho-ceo.md` (INITIALIZE step 1 rebuilt, step 4.5 inserted, DELEGATE constraints prefix, DONE step 10b inserted)
- modified `skills/core/harness/kiho-setup/SKILL.md` (4 new scaffold ops)
- modified `skills/core/planning/committee/SKILL.md` (language pre-check)
- modified `skills/core/hr/design-agent/SKILL.md` (Step 2.3 performance ranking, Step 2 external reference check)
- bumped `.claude-plugin/plugin.json` version to `6.0.0`

### Version

Plugin version bumped `5.22.0` → `6.0.0`. The jump is intentional: v6.0.0 is the first version in which auto-evolution behaviors ship — capability-gap recruitment, cross-turn consolidation, performance-driven ranking — making kiho recognizably a self-maintaining org rather than a disciplined runner of user-delegated work. The v5 schema remains readable via the v5bak backups and the migrator.

---

## v6.0.0-alpha.1 (PR #1 foundation — templates, config, lint scaffold)

**Problem v6 solves.** After 14 `/kiho` waves on 33Ledger, 5 systemic gaps
surfaced. Docs in `<project>/.kiho/plans/*.md` (v6 evolution plan):

- Agents hardcode project names (`role: "33Ledger Mobile Lead"`) → not portable
- `memory/` dirs empty after careful-hire → lessons never seed
- Recruit waits for user on RACI fail → no gap-healing reflex
- `$COMPANY_ROOT/company/wiki/**` 100% empty → research stays project-locked
- No per-company settings file → can't set `official_language = zh-tw`

PR #1 is **non-behavioral** scaffolding. PR #2 wires the universal gap-healing
reflex (recruit v6). PR #3 wires auto-evolution (consolidation, propagation,
external refs, search).

### What shipped

1. **`templates/company-settings.template.md`** — schema for `$COMPANY_ROOT/settings.md`.
   Frontmatter: `official_language`, `tone.*`, `recruit.*` (4-candidate hard floor,
   synthesis, memory-seed), `skill_library.*`, `kb_consolidation.*`, `startup.*`,
   `promote.*`, `performance.*`, `external_skills.*`. Full doc at
   `references/company-settings-schema.md`.

2. **`templates/agent-md-v2.template.md`** — new v2 schema for
   `$COMPANY_ROOT/agents/<id>/agent.md`. Mandatory fields: `schema_version: 2`,
   `role_generic` (portable, no project names), `experience[]`, `current_state`,
   `memory_path` (must be populated), `skills[]` (every ID must resolve),
   `hire_provenance`. v5 soul §1-§12 body kept unchanged. Full doc at
   `references/agent-schema-v2.md`.

3. **`templates/project-registry.template.md`** — lint seed list. When
   present at `$COMPANY_ROOT/project-registry.md`, the lint blocks project
   strings from appearing in portable fields.

4. **`templates/config.default.toml`** — added 8 new `[section]`s: `[recruit]`,
   `[skill_library]`, `[kb_consolidation]`, `[startup]`, `[promote]`,
   `[performance]`, `[performance.rank_weights]`, `[external_skills]`, `[tone]`.
   All are fallbacks — `$COMPANY_ROOT/settings.md` overrides these key by key
   at CEO INITIALIZE step 1 once PR #3 wires the read path.

5. **`bin/agent_md_lint.py`** — warn-only validator (PR #1 default). 6 rules:
   R1 schema_version, R2 required keys, R3 project-coupling detection against
   registry, R4 skills resolve, R5 memory populated, R6 active_project in
   experience. Switches to enforce mode (exit 1) in PR #3 via `--enforce`.

### What does NOT ship in alpha.1

- Recruit rewrite (Phases 1-6 with 4-candidate + synthesis + memory-seed) — PR #2
- Universal gap-healing reflex wired into CEO INITIALIZE / LOOP — PR #2
- `scope-promote-classifier` skill — PR #2
- Auto-scaffold of `settings.md` on first turn — PR #3
- Settings live-propagation (language → briefs / committee / narration) — PR #3
- Consolidation cycles (project KB / company KB / skill library) — PR #3
- External skill referencing + `skill-discover` — PR #3
- Performance amplification + `unified-search` — PR #3
- `bin/migrate_v5_to_v6.py` — PR #3 (auto-apply mode)

### Migration notes for alpha testers

v5.22 sites can install alpha.1 without breakage — nothing in PR #1 is wired
into runtime yet. Running `python plugins/kiho/bin/agent_md_lint.py
--warn-only $COMPANY_ROOT/agents/` on a v5 company root will surface the gaps
(role coupling, missing memory, unresolvable skill IDs) as warnings so you
can plan the migration before PR #3 auto-applies it.

---

## v5.22 (runtime gates — invariants become enforced, not prescriptive)

**Problem v5.22 solves.** A post-hoc audit of 6 `/kiho` sessions on a real project
(`web3-quant-engine`) found ~10 CRITICAL and 2 MAJOR ledger drifts where the CEO
claimed canonical subagent targets (`kiho-researcher`, `kiho-kb-manager`) but
actually spawned `general-purpose` or wrote the files directly. The root cause
was not incompetence — it was architectural: kiho v5.21 encoded its invariants
as *prose*, not as *gates*. When convenience and correctness diverged, the LLM
picked convenience. Full diagnosis in `_proposals/v5.22-gap-fix/00-gap-analysis.md`.

### What shipped

1. **PreToolUse hooks** (`hooks/hooks.json`, `bin/hooks/pre_write_agent.py`,
   `bin/hooks/pre_write_kb.py`). Direct Writes to `$COMPANY_ROOT/agents/*/agent.md`
   are blocked unless the content carries a `RECRUIT_CERTIFICATE:` marker emitted
   only by the recruit skill. Direct Writes/Edits to `.kiho/kb/wiki/*.md` are
   blocked unless the content carries a `KB_MANAGER_CERTIFICATE:` marker emitted
   only by kiho-kb-manager. The hook schema now matches Claude Code's documented
   format (`hooks.json` nested under `{"hooks": {"PreToolUse": [...]}}`); the
   v5.21 flat `session-start.json` was replaced.

2. **INITIALIZE step 7 and step 14 promoted from LAZY to REQUIRED.** Step 7
   (KB seed check) now explicitly logs `kb_empty_acknowledged` on fresh projects
   instead of silently skipping. Step 14 (CEO self-reflection) auto-seeds the
   `.kiho/agents/ceo-01/memory/` directory with an epoch-0 `.last-reflect` so
   reflection actually fires — in v5.21 this almost never ran because the
   directory rarely existed. The REQUIRED set grew from `{1, 3, 5, 10, 11, 12}`
   to `{0, 1, 3, 5, 7, 10, 11, 12, 14}`.

3. **DONE step 11 ledger integrity self-audit.** Every `/kiho` turn now ends
   with `bin/ceo_behavior_audit.py` cross-checking each `action: delegate` and
   `action: kb_add` ledger entry against actual artifacts on disk. Narrative-
   style targets (`kiho-researcher-x5`) are flagged MAJOR; concatenated tool
   lists (`deepwiki+websearch`) are flagged CRITICAL. On CRITICAL drift the
   user summary is prepended with `⚠️` and the drift count — suppression is
   explicitly forbidden.

4. **`recruit` pre-emit gate.** Before emitting any `agent.md`, `recruit` now
   verifies that role-spec, interview-simulate transcript, auditor reviews (for
   careful-hire), committee decision, and rejection-feedback all exist. If any
   is missing, `recruit` aborts with `status: pre_emit_gate_failed`. The emitted
   `agent.md` carries the `RECRUIT_CERTIFICATE:` comment the hook looks for.

5. **`--tier=<minimal|normal|careful>` modifier** on `/kiho`. Users can now
   explicitly accept simplification (`minimal`) or demand full machinery
   (`careful`) instead of the CEO silently shortcutting. Tier is declared as
   the first visible line of every CEO response and logged as the first
   ledger entry. New step 0 in INITIALIZE.

6. **Correction-driven reflection.** When the user's reply to an
   `AskUserQuestion` contains correction signals (keywords like "actually",
   "wrong", "should", "bypass" + Chinese equivalents), the CEO invokes
   `memory-reflect` with `trigger_type: user_correction` before resuming the
   loop. Corrections update the CEO soul §6/§10 via `soul-apply-override`
   instead of being lost in the management journal.

7. **Preferred-subagents cheat sheet** at `references/preferred-subagents.md`,
   read at INITIALIZE step 5b. Maps Intent → `subagent_type` so the CEO picks
   `kiho:kiho-researcher` instead of `general-purpose`. Silent substitution
   becomes a MINOR drift flag unless the ledger entry explains why.

8. **Replay harness + 2 scenarios** at `skills/_meta/ceo-replay-harness/`.
   Scenarios session1 (research) and session5 (hiring) encode expected v5.22
   behavior; `runner.py` checks a real `ceo-ledger.jsonl` against the
   expectations. This is a regression net for future kiho changes.

9. **Ledger epoch marker.** First v5.22 turn per project writes
   `action: ledger_epoch_marker, payload: {epoch: v5.22_active}`. Pre-marker
   entries are amnestied by the audit script unless `--full` is passed, so
   v5.21 drift doesn't pollute the first v5.22 audit.

### What it cost

- ~1600 new lines across 6 PRs
- ~50-100ms hook latency on every Write/Edit (Python startup)
- One additional Bash call per `/kiho` turn (the DONE self-audit)
- Pre-v5.22 `agent.md` files without the RECRUIT_CERTIFICATE marker are
  re-writable via Edit (the hook matches on Write only for agent path), so
  no breaking change; new agents go through recruit.

### Grounding

Enforcing runtime gates rather than relying on prose invariants mirrors
Anthropic's own generator/evaluator-separation guidance (harness-design
doc): when the generator is asked to evaluate its own output it defaults to
praise; an independent evaluator is far more tractable. `ceo_behavior_audit.py`
is kiho's independent evaluator. Proposal + diagnosis at
`_proposals/v5.22-gap-fix/` (committed alongside PR 1 for traceability).

---

## v5.21 (cycle-runner kernel — single orchestrator for the whole system)

The largest architectural change since v5.0. Every kiho lifecycle (talent-acquisition, incident-handling, skill-evolution, kb-bootstrap, decision-cycle, value-alignment, research-discovery) now runs through a single declarative orchestrator: `cycle-runner`.

### Why this change

Pre-v5.21, lifecycles were loose compositions of skills. CEO chained skill A → skill B → skill C with state spread across `plan.md`, `ceo-ledger.jsonl`, `state/incidents/`, `state/recruit/`, `committees/<id>/`, `state/actions/`, etc. This produced four chronic problems: no SSoT per lifecycle; CEO mental load growing with lifecycle count; evolution requiring code edits across many files; and per-lifecycle resume/replay/cancel/budget reimplementations.

v5.21 solves this with a single declarative kernel: one orchestrator (`cycle-runner`), one DSL (cycle templates), one per-cycle SSoT (`index.toml`), one master view (`INDEX.md`). The orchestrator does not know any lifecycle by name — it knows phases, transitions, success conditions, and budgets. Adding a new lifecycle means writing a new TOML template; orchestrator code does not change.

### What shipped

- **Orchestrator skill**: `skills/_meta/cycle-runner/` with full SKILL.md + 2 references (`template-dsl.md`, `orchestrator-protocol.md`)
- **Implementation**: `bin/cycle_runner.py` (open / advance / status / pause / resume / cancel / replay / validate-template; pure stdlib; ~700 LOC)
- **Master architecture doc**: `references/cycle-architecture.md`
- **Closed 7-verb registry**: `references/core-abilities-registry.md` (research / decide / build / validate / deploy / monitor / communicate)
- **7 production templates**: `references/cycle-templates/{talent-acquisition,skill-evolution,kb-bootstrap,incident-lifecycle,decision-cycle,value-alignment,research-discovery}.toml`
- **5 new data-storage-matrix rows (Wave A)**: `cycle-templates`, `cycle-index`, `cycle-master-index`, `cycle-handoffs`, `cycle-events`
- **6 additional data-storage-matrix rows (Wave B, gap-fill)**: `values-flags` (§1 T1 markdown ruling), `integrations-registry` (§3 T1 markdown table), and new §10c **Inboxes & pending queues** with `memo-inbox`, `handoff-receipts`, `feedback-queue`, `commit-ceremony-pending` (all T2 JSONL with explicit eviction). Closed the 11-skill UNDECLARED gap (memo-send/memo-inbox-read, handoff-accept, user-feedback-request, integration-audit/register, commit-ceremony, values-flag → declared real slugs; storage-broker + engineering-kiro × 2 → declared `[]` with new audit semantic)
- **Audit semantic patch**: `skills/_meta/evolution-scan/scripts/storage_fit_scan.py` now treats `data_classes: []` as `ALIGNED` with `declared_empty: true` (was `UNDECLARED`). Reserves the empty form for pure-infrastructure dispatchers (storage-broker) and vendor-sandbox skills (engineering-kiro × 2); aligns audit behaviour with the `data_classes_backfill.py` docstring intent. Post-patch tally: **80/80 ALIGNED, 0 UNDECLARED, 0 DRIFT, 0 MATRIX_GAP** across 57 matrix rows
- **Tooling**: `bin/cycle_index_gen.py` (master INDEX.md regeneration at CEO DONE), `bin/cycle_replay.py` (per-cycle timeline reconstruction), `bin/kiho_telemetry_rollup.py` extended with `--cycles-jsonl` flag + `cycle_rollup()` producing `_meta-runtime/cycle-health.jsonl` (per-cycle row + per-template row with `needs_attention` flag for blocked-rate / low success-rate); CEO INITIALIZE step 17 + DONE step 9 updated to consume both rollups in one invocation
- **CEO loop integration**: INITIALIZE step 18 reads `cycles/INDEX.md`; LOOP step c routes cycle items via `cycle-runner advance`; DONE step 10 regenerates INDEX.md
- **CLAUDE.md sync**: new "Cycle-runner kernel (v5.21)" entry under Working concepts; References list adds `cycle-architecture.md`, `core-abilities-registry.md`, `cycle-templates/`, `cycle-runner SKILL.md`; CHANGELOG range advanced to "v5 through v5.21"
- **kiho-setup bootstrap**: state-tree scaffolder ships 8 new v5.21 paths (`cycles/`, `inbox/`, `handoffs/`, `feedback/{requests,responses}.jsonl`, `commit-ceremony/`, `integrations.md`, `values-flags/`)
- **Catalog regeneration**: 13 wave 3/4 skills (sk-061 cycle-runner + sk-062 → sk-073) registered with `.skill_id` sidecars; CATALOG.md grew from 66 → 79 entries; routing block auto-refreshed by `bin/routing_gen.py`
- **Skill-authoring standards**: new "v5.21 cycle-phase-aware skill authoring" section
- **Cycle-aware notes** added to 17 skills: `incident-open`, `postmortem`, `retrospective`, `recruit`, `onboard`, `rejection-feedback`, `performance-review`, `committee`, `decision-audit`, `values-alignment-audit`, `skill-adoption-check`, `research`, `research-deep`, `kiho-init`, `skill-factory`, `skill-intake`, `skill-improve`

### How kiho evolves now

| Change | What you do |
|---|---|
| Add a new lifecycle | Write a new `references/cycle-templates/<name>.toml`; validate via `cycle_runner validate-template`; PR through skill-intake/factory/critic gates |
| Add a new core ability (verb) | CEO-committee vote (regime same as adding a verb to capability-taxonomy.md) |
| Add an atomic skill under existing ability | Normal skill-create path; append a row in `core-abilities-registry.md`; no vote |
| Modify a phase in a template | Edit + bump template version; in-flight cycles use pinned old version, new cycles use new |
| Add a new escalation kind | Code change in `cycle_runner.py` (rare; well-bounded) |

### Backward compatibility

All atomic skills (committee, research-deep, recruit, incident-open, postmortem, onboard, etc.) remain callable directly. Cycle-runner is a wrapper that composes them into a state machine; it does not replace them. Pre-v5.21 invocation paths still work; cycle-routed paths are recommended for new lifecycles.

### Verification

- `python bin/cycle_runner.py validate-template --path <X>` returns valid for all 7 templates
- End-to-end smoke test (incident-lifecycle): 13 handoff rows from open → triage → mitigation → postmortem → close-success
- Storage-fit audit (post Wave B): **80 ALIGNED / 0 UNDECLARED / 0 DRIFT / 0 MATRIX_GAP** across 80 skills + 57 matrix rows
- Telemetry rollup smoke: `python bin/kiho_telemetry_rollup.py --cycles-jsonl _meta-runtime/cycle-events.jsonl` flags 1 template (`incident-lifecycle`) for attention and 1 blocked cycle from the prior smoke runs
- Replay tool reconstructs full timeline from handoffs.jsonl + index.toml

### Out of scope (deferred to v5.22+)

- Parallel phase execution within a cycle
- Sub-template / nested cycle templates
- Cycle Tier-3 sqlite index (cycle count <50; markdown INDEX is enough)
- Workflow editor UI
- Auto-template-generation from user prompts
- Cross-plugin cycle template sharing

---

## v5.19 concepts (storage redesign — in progress)

- **v5.19.5.1 doctrine hygiene (Tier F).** Post-v5.19.5 audit found two stale doctrine sections in `references/data-storage-matrix.md`: the §"Summary counts" list was not updated when `canonical-rubric` flipped MIGRATING→FIT and `experience-pool-cross-project` flipped GAP→FIT during v5.19.5, so it still cited pre-migration counts (`MIGRATING: 3`, `GAP/DEFERRED: 3`); the §8 compound-row header (`### backlinks / tags / graph / by-confidence / by-owner / timeline / stale / open-questions — FIT`) omitted `index` and `cross-project` from the parity-checked list, even though those two indexes shipped checkers in v5.19.5 (`bin/kb_lint_index.py`) and Tier D (`bin/kb_lint_cross_project.py`) respectively, and the row didn't point at log.md's doctrinal exclusion either. Both drifts fixed: Summary counts now read `36 FIT / 1 MIGRATING / 4 NEW / 1 NEW-GAP / 1 DEFERRED / 1 NEW-PATTERN` with a `Last verified 2026-04-19` trailer; the §8 compound-row header now enumerates all 10 parity-checked derived indexes (`index / backlinks / tags / graph / cross-project / timeline / stale / open-questions / by-confidence / by-owner`) and gains a `notes:` field pointing at `bin/kb_lint_common.py` scaffold and `agents/kiho-kb-manager.md` §"Index rebuild protocol" for the log.md append-only exclusion rationale. **No code changes; no schema changes; no new doctrine. Documentation hygiene only.** Post-Tier-F the v5.19 backlog reduces to lazy-by-design / committee-gated items (recruit-role-specs MIGRATING; committee-index-sqlite NEW-GAP lazy; semantic-embedding-cache DEFERRED with revisit trigger now instrumented; I4-wave-2 skill-optimize/skill-verify/cousin-prompt awaiting committee vote) — none are unilaterally shippable.
- **v5.19.5 Tier-E gap closure — kb-lint coverage reaches 11/12 indexes; telemetry wiring; semantic-embedding revisit trigger instrumented; canonical-rubric migrated; experience-pool cross-project op shipped.** Five gap closures. (a) **I5 wave 2 — six new kb-lint parity checkers**: `bin/kb_lint_index.py` (per-type set-parity), `bin/kb_lint_timeline.py` (ordered parity on `updated_at` desc), `bin/kb_lint_stale.py` (content invariant: `last_verified > 90d`), `bin/kb_lint_open_questions.py` (set-parity on `wiki/questions/*.md` with `status: open`), `bin/kb_lint_by_confidence.py` (ordered parity on `confidence` asc), `bin/kb_lint_by_owner.py` (grouped set-parity on `author_agent`). All six reuse the Tier-D `bin/kb_lint_common.py` scaffold; each file stays ≤~140 LOC. Order checkers emit both set-diff (`missing_from_index` / `extra_in_index`) and first-misorder detection. Stale checker adds `--threshold-days` and `--today` override flags for fixture testing. Verified end-to-end on a synthetic wiki fixture with one drift scenario per checker: aligned → exit 0, drift → exit 1 with correct findings. **`log.md` explicitly excluded** from the parity family — it is append-only (no rebuildable source-of-truth set); the exclusion is documented with rationale in `agents/kiho-kb-manager.md` §"Index rebuild protocol" step 5 so future authors don't wonder why it's skipped. Post-Tier E coverage: **11/12 derived indexes have parity checkers + log.md doctrinal exclusion**. (b) **N2 — telemetry wiring for kb_lint + catalog_walk_audit**: `kb_lint_common.py` gains a `safe_telemetry_record()` helper (swallows ImportError and any `record()` exception — telemetry MUST NOT break kb_lint behavior; matches the `bin/skill_catalog_index.py` pattern). `dispatch()` emits one `op=kb_lint` event per invocation (`key=<checker_name>`, duration_ms, tier, aligned bool, drift_count, tiers_ran). Gated on `wiki_exists: true` so empty-wiki no-ops stay quiet. `kb_lint_stale.py` (custom `main()` for `--threshold-days` / `--today`) imports `safe_telemetry_record` directly. `bin/catalog_walk_audit.py` instruments its 3 existing checks (orphan/stale_draft/confusability) with per-check `op=catalog_audit` events carrying warn/error counts and per-check `duration_ms`. (c) **N4 — semantic-embedding revisit-trigger instrumentation**: `skills/_meta/skill-find/scripts/facet_walk.py` appends one JSONL line per 10-candidate ceiling hit to `<plugin-root>/.kiho/state/tier3/semantic-embedding-triggers.jsonl` (schema: `{ts, query, candidate_count, hard_ceiling}`). Emission is best-effort (`OSError` swallowed so gate-mode behavior is unchanged). `catalog_walk_audit.py` gains a 4th check `check_embedding_trigger()` that rolls up hits over the last 30 days; warn at ≥5 hits/30d, error at ≥15 hits/30d. Error-level firing twice in a quarter is the documented trigger to re-open the semantic-embedding-cache committee vote (`references/storage-tech-stack.md` §6). `--embed-trigger-warn` / `--embed-trigger-err` CLI flags expose the thresholds for CI tuning. Verified with 6 synthetic hits within 30d + 1 stale entry: check reports `rolling_hit_count: 6, level: warn`. (d) **N3 — experience-pool op=render-company-pool**: `bin/experience_pool_render.py` (~230 LOC stdlib) scans `$COMPANY_ROOT/company/wiki/cross-project-lessons/*.md`, groups by frontmatter `topic:`, dedups within each topic via char-3-gram Jaccard similarity > 0.85 (same threshold as kb-promote; char-n-gram Jaccard is the established v5.19 deterministic similarity baseline, no ML), sorts each topic group by confidence desc + updated_at desc + slug asc, and emits a single synthesized `experience-pool.md` with frontmatter (`scope: cross-project`, `generated_by`, `generated_at`). `--dry-run` flag prints markdown + one-line JSON report (topics / lessons_scanned / lessons_after_dedup / dedup_dropped). `skills/core/knowledge/experience-pool/SKILL.md` ops table gains a `render-company-pool` row; a new §"Render-company-pool procedure (v5.19.5+)" section documents the 4-step flow (invoke helper → interpret report → submit via `kb-manager op=update` → kb-manager post-write protocol rebuilds indexes automatically). Idempotent modulo the `generated_at` frontmatter timestamp. `references/data-storage-matrix.md` §10 `experience-pool-cross-project` row flips **GAP → FIT** with the helper invocation as the canonical regeneration recipe. Verified end-to-end on a 3-lesson fixture (2 ralph-loop near-duplicates, 1 storage lesson): 3 scanned → 2 after dedup, 2 topic groups, 0 exit. (e) **N5 — canonical-rubric YAML → TOML migration**: `skills/core/planning/interview-simulate/assets/canonical-rubric.yaml` → `canonical-rubric.toml`. Hand-rewritten because the multi-level nesting (`dimensions.<name>.scale.<level>` + `weight_presets.<preset>`) exceeds `bin/yaml_to_toml.py`'s narrow-schema converter — noted in `yaml_to_toml.py` docstring (the converter's `status: unsupported` exit was caught at conversion attempt, per Tier E risk table). Semantic round-trip verified via `tomli.loads == yaml.safe_load` on the v5.19.4 YAML file: IDENTICAL. Nine cross-references updated from `.yaml` to `.toml`: `interview-simulate/SKILL.md`, `skill-create/references/transcript-review.md`, `skill-structural-gate/references/canonical-layouts.md`, `storage-tech-stack.md §1`, `storage-architecture.md`, `skill-authoring-standards.md` (2 mentions), `skill-improve/SKILL.md` (v5.19.3 hook note), `_meta-runtime/data-class-inventory.md`, `bin/yaml_to_toml.py` docstring. Legacy `.yaml` retained one cycle with a DEPRECATED header comment pointing to the new path; scheduled for deletion in v5.19.6. `data-storage-matrix.md` §2 `canonical-rubric` row flips **MIGRATING → FIT** with a `migration-note` field documenting the hand-rewrite rationale. **Regression guard (cross-ref)**: `skill-improve/SKILL.md` lazy YAML→TOML migration hook now notes `canonical-rubric` is no longer MIGRATING, preventing future improve runs from trying to re-migrate the already-migrated file. **Verification**: all six new kb_lint scripts drift-tested on synthetic fixture (aligned exit 0, drift exit 1); telemetry stream at `.kiho/state/storage-events.jsonl` grew by 4 events after one invocation each of `kb_lint_stale`, `catalog_walk_audit` (3 sub-check events); `experience_pool_render.py` --dry-run on fixture reports the expected dedup count and JSON status; `storage_fit_scan.py --plugin-root .` still exits 0 post-migration (no new UNDECLARED verdicts). **Deferred (explicit Tier-E non-goals)**: I4 wave 2 (skill-optimize/skill-verify/cousin-prompt — needs committee vote + multi-session design; promotion trigger: axis-blind-spot telemetry OR skill-improve FIX-rate >20% for a month per v5.19.4 factory doctrine); N7 (committee-records sqlite cross-index — lazy; ships on first cross-committee query). Two v5.19 gaps remain in backlog (I4-wave-2, N7) plus the doctrinal log.md exclusion above.
- **v5.19.4 Tier-D gap closure — Phase 2 gates advance; kb-lint coverage expands; N1 resolved as no-op.** Three gap closures bringing the skill-factory Phase 2 wave 1 to `active` and covering 5 of the 12 kb-manager derived indexes with deterministic post-write parity checkers. (a) **I4 — `skills/_meta/skill-critic/` shipped**: the highest-leverage Phase 2 gate (per the Anthropic grader/comparator/analyzer pattern) ships as a read-only deterministic rubric. `scripts/critic_score.py` (~320 LOC stdlib) scores a draft SKILL.md on 8 axes with documented weights (description_quality 0.20, body_length 0.05, structure 0.15, examples 0.15, anti_patterns 0.15, frontmatter_completeness 0.15, capability_valid 0.05, topic_tags_valid 0.10, sum 1.00). Overall weighted score in [0.0, 1.0]; threshold 0.80 by default (configurable via `--threshold`). Hard-fail short-circuit triggers on no-H1 or sub-20-line body (`status: hard_fail`, exit 1) — overrides threshold. Graceful degradation when `references/capability-taxonomy.md` or `references/topic-vocabulary.md` are unreadable (axis scores 1.0 with detail `"axis skipped"` — never crashes the critic). `references/rubric.md` documents per-axis rationale, sub-check formulas, and weight-tuning protocol. Self-test: critic scores its own SKILL.md at 0.955 (pass). Cross-regression: critic scores `skills/kb/kb-add/SKILL.md` at 0.955 (pass, consistent with the known-good reference skill). `skills/_meta/skill-factory/SKILL.md` §"The 10-step SOP" table gains a `Lifecycle` column: step 5 `skill-critic` marked `active (v5.19.4+)`; steps 6 `skill-optimize`, 7 `skill-verify`, 9 `cousin-prompt` marked **deferred** with explicit "MUST NOT expect these gates to fire" rule so the pass-through aggregator treats them as "not applicable" not "failed". §F1 Phase 2 wiring status rewritten from "planned" to "partially shipped" with a concrete promotion trigger for the deferred trio (axis-blind-spot telemetry OR FIX-rate >20% for a month). (b) **I5 partial — 4 kb-lint parity checkers shipped**: `bin/kb_lint_tags.py`, `bin/kb_lint_backlinks.py`, `bin/kb_lint_graph.py`, `bin/kb_lint_cross_project.py` each follow the `kb_lint_skill_solutions.py` template (exit codes 0/1/2/3 per v5.15.2, `--project-root / --company-root / --tier` CLI, advisory no-op on missing wiki). Shared helper `bin/kb_lint_common.py` (~180 LOC) centralizes frontmatter parsing (inline-array + block-list forms), wikilink extraction, H2-section parsing, tier dispatch scaffold, and the canonical 12-filename `DERIVED_INDEX_FILENAMES` frozenset so all checkers filter derived-index files uniformly when scanning source pages (prevents false drift from sibling indexes' wikilinks leaking into another checker's "source" set). Per-checker invariants: `tags` compares `tags:` frontmatter union against `tags.md` section-header set (asymmetric drift); `backlinks` compares wikilink-target union against `backlinks.md` section-header set; `graph` compares page-slugs-with-outgoing-links against `graph.md` section-header set; `cross-project` (company-tier only) compares `scope: cross-project` OR `projects: [≥2]` OR `cross_project: true` frontmatter signals against `cross-project.md` wikilink set. All 4 verified end-to-end against a synthetic wiki fixture (`C:/tmp/kiho-wiki-fixture/`): aligned cases exit 0; drift cases exit 1 with correct `missing_from_index` / `extra_in_index` populated. `agents/kiho-kb-manager.md` §"Index rebuild protocol" step 5 now lists 5 checker invocation lines (was 1), explicitly naming the 7 remaining unchecked indexes (`index.md`, `log.md`, `timeline.md`, `stale.md`, `open-questions.md`, `by-confidence.md`, `by-owner.md`) as follow-up work. (c) **N1 — resolved as no-op doctrine clarification**: re-survey on 2026-04-19 found the prior "kiho-clerk agent orphaned" claim was stale. `skills/core/planning/committee/SKILL.md` lines 30, 112, 120, 158 already spawn `kiho-clerk` as a neutral extractor when the convening leader has a stake in the outcome. No deprecation, no re-wiring — just doctrine accuracy correction in the plan file. **Deferred (Tier D explicit non-goals)**: the other 3 Phase 2 gates (skill-optimize, skill-verify, cousin-prompt) remain `lifecycle: deferred` pending a CEO-committee vote on priority; the other 7 kb-lint checkers stay on backlog for a dedicated kb-lint sprint. **Verification**: `critic_score.py` sanity-tested (kb-add 0.955 pass, critic-itself 0.955 pass, missing-file exit 2); 4 kb-lint checkers smoke-tested on no-wiki (exit 0, no_wiki advisory) and drift-tested on synthetic fixture (tags/backlinks/cross-project exit 1 with correct findings; graph exit 0 on aligned fixture); all Tier A/B/C regression paths still pass (`skill_catalog_index build/evict` exit 0, `kiho_clerk --self-test` exit 0 with 7 rows, `storage_fit_scan` exit 0 with `elapsed_source=auto`). Six v5.19 gaps remain in backlog (I4 wave 2 — skill-optimize/skill-verify/cousin-prompt; I5 remaining 7 kb-lint checkers; N2 telemetry breadth; N3 experience-pool cross-project op; N4 semantic-trigger instrumentation; N5 canonical-rubric.yaml TOML; N6 kb-manager cross-project rollup details; N7 committee-records sqlite cross-index — lazy, skip). See plan file §"Gap catalog" for Tier E scope.
- **v5.19.3 Tier-C gap closure — lazy-migration infrastructure proven.** Two gaps closed that demonstrate the v5.19 migration discipline on two real artifacts: one config file migrated YAML→TOML, and 43 SKILL.md files gain the `data_classes:` frontmatter field. (a) **I3 — YAML→TOML lazy migration**: `bin/yaml_to_toml.py` ships as a stdlib-only narrow-schema converter (~450 LOC, accepts scalars + one level of nested maps + simple lists + inline comments; exits 1 on unsupported features rather than producing subtly-wrong output). Known limitation documented: TOML requires top-level scalars before any `[table]` block, so section-header comments adjacent to nested-map sections need one-line manual reorganization after automated conversion. Proof migration: `skills/core/harness/kiho/config.yaml` → `config.toml`, content verified via `tomli.load()` (all 20 keys + 3 nested tables round-trip cleanly). Cascade updates: `agents/kiho-ceo.md:54`, `CLAUDE.md:59`, `README.md:55`, `skills/core/harness/kiho/SKILL.md` (6 mentions), `skills/core/harness/kiho-setup/SKILL.md` (4 mentions) + `scaffold-tree.md`, `skills/_meta/skill-structural-gate/SKILL.md` + `canonical-layouts.md` + `parity_diff.py` (accepts either `config.toml` or `config.yaml`), `skills/_meta/skill-spec/references/signal-taxonomy.md`, `templates/kb-knowledge-base.template.md`, `references/storage-architecture.md` (2 mentions), `references/storage-tech-stack.md §1`, `references/data-storage-matrix.md §2 kiho-config` row (MIGRATING → FIT). `storage_fit_scan.py::load_ship_date()` regex now matches both TOML `key = "YYYY-MM-DD"` and legacy YAML `key: YYYY-MM-DD` with two-probe fallback (`.toml` primary, `.yaml` secondary). `skills/_meta/skill-improve/SKILL.md` gains a new §"Lazy YAML→TOML migration hook" under Diff constraints documenting the trigger: on edit to any MIGRATING class file adjacent to SKILL.md (checked against `data-storage-matrix.md §2`), author invokes `bin/yaml_to_toml.py convert --in <path> --in-place` first. (b) **O1 — `data_classes:` backfill across 43/45 skills**: `bin/data_classes_backfill.py` ships with a hand-curated path→row mapping for all 45 skills in a `_MAPPING` dict (lightly documented per skill based on reading SKILL.md Inputs + Procedure sections). Dry-run default (`propose` subcommand) exits 1 on unmapped or invalid-slug violations; `apply` writes `data_classes: [...]` into each SKILL.md's `metadata.kiho` frontmatter block in flow-list form. Doctrine compliance: the dry-run review step satisfies `storage-audit-lens.md §138` ("Do NOT auto-rewrite SKILL.md to add `data_classes:` without the author's review") — the author reviews the JSON proposal before invoking apply. Apply succeeded on 44 skills in one invocation; 1 skill (`kb-add`) was already written as the single-skill sanity check. Post-apply audit: `storage_fit_scan` reports 43 ALIGNED, 2 UNDECLARED (both `engineering/engineering-kiro*` — external vendor skills declared with `data_classes: []`, treated as UNDECLARED per `storage-audit-lens.md §24` which considers empty-list identical to missing-field; this is intentional doctrine to surface "empty-by-design" declarations for author review and does not indicate a bug). **Verification**: storage_fit_scan post-migration reports `status=ok, elapsed_source=auto (config v5_19_ship_date=2026-04-18)`, proving the grace-window auto-detection still reads the new TOML config; skill_catalog_index.py build/evict regression-free (still indexes 45 skills in ~90ms); kiho_clerk.py self-test unchanged (7 rows across 2 fixtures); yaml_to_toml converter self-test emits idempotent TOML for a simple fixture. Nine v5.19 gaps remain in backlog (I4 Phase 2 factory gates, I5 10 kb-lint parity checkers, N1 kiho-clerk agent decision, N2 telemetry breadth, N3 experience-pool cross-project op, N4 semantic-trigger instrumentation, N5 canonical-rubric.yaml TOML, N6 kb-manager cross-project rollup details, N7 committee-records sqlite cross-index) — see `C:/Users/wky/.claude/plans/you-should-analyze-again-linked-bunny.md` §"Gap catalog" for Tier D/E cycles.
- **v5.19.2 Tier-B gap closure — committee-records Wave 2 unblocked.** Four gap closures that remove the remaining barriers to running a real committee deliberation through the v5.19 storage pipeline. (a) **I1 — `bin/kiho_clerk.py extract-rounds`**: ~500 LOC stdlib-only deterministic parser that walks `transcript.md` (frontmatter YAML + `## Round N` blocks with `### research|suggest|challenge|choose` H3 subsections + `## Close` block) and emits one JSONL row per message event plus one close row per transcript. Schema: `{committee_id, chartered_at, round, phase, author, confidence, position, rationale?}` for messages; close rows add `{outcome, final_confidence, rounds_used, decision}`. Idempotent: re-running yields byte-identical JSONL. Built-in `--self-test` runs two canned fixtures (one valid unanimous, one malformed missing Close) and exits 0/1 accordingly. Exit codes 0/1/2/3 per v5.15.2. (b) **I2 — `references/committee-rules.md` §"Transcript format"**: new section after §"Quorum and membership" specifying frontmatter schema (committee_id, topic, chartered_at ISO-8601, members list, quorum), round/phase/close block structure, message bullet grammar `- **@agent** (confidence: 0.XX) — <position>` with optional `> <rationale>` blockquote, two byte-identical worked examples (1-round unanimous color pick; 3-round LFU cache eviction with challenge resolution), and BCP 14 MUST/MUST NOT rules (two-decimal-place confidence, member listing, single `## Close` block, no hand-writing to records.jsonl). Regeneration contract pins `kiho_clerk` as sole canonical parser. (c) **I6 — grace-window auto-detect**: `skills/core/harness/kiho/config.yaml` gains `v5_19_ship_date: 2026-04-18` key under a new `# ---- Storage-fit grace window (v5.19+) ----` block. `skills/_meta/evolution-scan/scripts/storage_fit_scan.py` gains `load_ship_date()` helper (stdlib regex, no PyYAML dep) plus `--config-path` override flag; `--elapsed-days` default changes from 0 to None (auto-compute). Summary JSON now includes `elapsed_days`, `elapsed_source` (`auto|fallback|override`), `grace_days`, `beyond_grace` for transparency. Preserves `--elapsed-days N` as manual override. Fallback to elapsed_days=0 on config read failure keeps grace safe-by-default. (d) **O3 — Phase 1 ratification audit row**: `_meta-runtime/phase1-committee-minutes.md` gains a "User ratification" table at the end of §"Phase 4 pilot selection vote" recording 2026-04-18 user accept of Option C (skill-catalog Tier-3 sqlite) at committee-confidence 0.90. Closes the audit trail so future auditors can distinguish user-approved decisions from unilateral CEO adoption. **Cross-reference fix**: `references/data-storage-matrix.md` §5 `committee-records-jsonl` row now cites the shipped parser path (`bin/kiho_clerk.py`), concrete command line, schema fields, and the committee-rules.md §"Transcript format" anchor — replaces the "to be implemented Wave 2" placeholder. **Verification**: all four paths exit-code tested — storage_fit_scan auto-mode exits 0 with `elapsed_source: "auto (config.yaml v5_19_ship_date=2026-04-18)"`, override-mode at 65 days exits 1; kiho_clerk `--self-test` exits 0 (7 JSONL rows emitted across 2 fixtures), real transcript parse byte-identical on re-run, malformed transcript exits 1 with `status: malformed`, missing transcript exits 2. **Regression guard**: `storage_fit_scan.py --elapsed-days 0` still forces grace-in-effect (existing manual override path unchanged); `storage_fit_scan.py` without config.yaml still falls back cleanly to elapsed_days=0. Eleven other v5.19 gaps (committee-records sqlite cross-index N7, YAML→TOML lazy migration I3, 10 kb-lint parity checkers I5, Phase 2 factory gates I4, cross-project rollup wiring N6, kiho-clerk agent deprecate-or-wire N1, experience-pool cross-project N3, semantic-embedding-cache N4, canonical-rubric.yaml TOML N5, kb_lint/catalog_walk_audit telemetry N2, data_classes backfill O1) remain in the backlog at `C:/Users/wky/.claude/plans/you-should-analyze-again-linked-bunny.md` §"Gap catalog" for Tier C/D/E future cycles.
- **v5.19.1 Tier-A gap closure — pilot becomes functionally live.** Three blocker hooks that wire the v5.19 Phase 4 pilot into CEO orchestration: (a) `agents/kiho-ceo.md` §INITIALIZE gains step 16 invoking `python bin/skill_catalog_index.py build --plugin-root ${CLAUDE_PLUGIN_ROOT}` on every `/kiho` turn; on non-zero exit logs `action: skill_catalog_index_unavailable` and continues (T3-MUST-2 idempotent-safety). (b) §DONE gains step 8 invoking `skill_catalog_index.py evict` before the user report; tolerates "no file" case (evicted: false, exit 0); logs `action: session_scope_eviction` to ceo-ledger. YAGNI guard: do not centralize into helper until 3+ T3 artifacts exist. (c) LOOP §d. DELEGATE Evolve case now parses `--audit=<lens>` off the payload; `--audit=storage-fit` routes to `evolution-scan` with `audit_lens="storage-fit", report_only=true`, landing batch report in `_meta-runtime/`; unknown lens escalates via ASK_USER with known values; absent flag preserves current evolution-loop behavior. Harness `skills/core/harness/kiho/SKILL.md` mode-parsing table extends the `evolve` row's payload column with the `--audit` flag documentation. **Regression guard**: `/kiho evolve` without `--audit` still routes to the normal examine loop unchanged. **Verification**: manual invocation of all three referenced scripts (`build --plugin-root .`, `evict --plugin-root .`, `storage_fit_scan.py`) passes exit-code checks (0/0/0) with `storage-events.jsonl` recording build + evict events, batch-report-storage-audit file emitted. Twelve other v5.19 gaps (committee-records Wave 2, YAML→TOML lazy migration, 10 kb-lint parity checkers, Phase 2 factory gates, cross-project rollup wiring, nice-to-haves) remain in the backlog at `C:/Users/wky/.claude/plans/you-should-analyze-again-linked-bunny.md` §"Gap catalog" for future cycles.
- **Phase 4: skill-catalog-index Tier-3 sqlite pilot shipped.** First-ever Tier-3 artifact in kiho. `bin/skill_catalog_index.py` (~450 LOC stdlib sqlite3 + re + hashlib) builds a session-scope sqlite + FTS5 virtual table over 45 SKILL.md frontmatter entries in ~90ms cold / ~30ms warm (hash-match reuse). Schema: `skills` (skill_id PK, domain, capability, topic_tags, requires, mentions, description, disk_mtime) + `skills_fts` (FTS5 over name/description/capability/topic_tags) + `kiho_index_meta` (hash, built_at, skills_root). Reconstruction recipe: walk `skills/**/SKILL.md`, re-parse frontmatter; idempotent-safe (T3-MUST-2). Eviction: session-scope via explicit `--evict` subcommand or deletion of file; any stale file on disk triggers rebuild on next INITIALIZE. CLI subcommands: `build` / `query-facet` / `query-fts` / `evict` / `parity-test`. **Parity test passes 100%**: indexed queries for every capability verb and every domain match ground-truth re-parse exactly across all 45 skills; 5 domain checks + 8 capability checks all aligned. Telemetry via `bin/storage_telemetry.py` (~110 LOC) emits append-only JSONL events to `<project>/.kiho/state/storage-events.jsonl` with `ts, op, key, duration_ms, extra`; events: `index.build`, `index.reuse`, `index.evict`, `query.facet`, `query.fts`. Observed query latency: ~1ms for facet + FTS, demonstrating the 32-script-reparse pain-point (~6.4s aggregate) is eliminated. Best-effort telemetry never breaks callers (import failure tolerated). Default path `<project>/.kiho/state/tier3/skill-catalog.sqlite`; overridable via `--db-path`. Exit codes 0/1/2/3 per v5.15.2. One-week checkpoint queued: review `storage-events.jsonl` aggregates before Wave 2 migration approvals.
- **Phase 3: `skills/_meta/evolution-scan` extended with storage-fit audit mode.** New `scripts/storage_fit_scan.py` (~300 LOC stdlib-only) walks `skills/**/SKILL.md`, parses `metadata.kiho.data_classes:` frontmatter, cross-references `references/data-storage-matrix.md`, emits per-skill verdicts ALIGNED / UNDECLARED / DRIFT / MATRIX_GAP / ERROR. Zero mutations. Outputs `_meta-runtime/batch-report-storage-audit-<ts>.md` following the existing single-CEO-bulk-decision convention. Grace window flag (`--grace-days 60 --elapsed-days N`) honors the legacy-skill backfill discipline. Full 45-skill self-audit passes at 45/45 UNDECLARED within grace (exit 0) + 43 matrix rows successfully indexed. Fixture-verified for DRIFT (unknown slug), MATRIX_GAP (declared row is GAP/DEFERRED), ALIGNED, UNDECLARED-beyond-grace, and usage-error paths. Reference doc `skills/_meta/evolution-scan/references/storage-audit-lens.md` describes verdict taxonomy, report skeleton, and integration with the main evolution-scan loop. SKILL.md gains `audit_lens: storage-fit | null`, `report_only: bool` inputs + new signal-table row + §"Storage-fit audit mode" subsection + audit-mode response shape.
- **Phase 2: `references/data-storage-matrix.md` + `references/storage-tech-stack.md` shipped.** ~45 data classes across 11 categories mapped to tier × scope × format × gatekeeper × eviction × regeneration with one row per class. Companion tech-stack record captures the 9 Phase 1 committee votes (mean confidence 0.87, unanimous close on all 9). Key decisions: TOML replaces YAML for typed config (stdlib `tomllib`); JSONL stays canonical for 5 telemetry streams (DuckDB optional read overlay); capability-matrix stays markdown + in-memory dict Tier-3 (no sqlite); committee records get JSONL-per-committee + sqlite cross-index Tier-2 with `transcript.md` as T1 regenerability source; FTS over narrative uses sqlite-FTS5 Tier-3 per-turn; semantic similarity explicitly deferred with 3 revisit triggers; session scratch stays decentralized; **skill-catalog Tier-3 sqlite** selected as Phase 4 pilot (pattern proof; ~6.4s → 50ms at 44 skills); cross-project rollup ships via kb-manager wiki promotion without new Tier-3. Doctrine edits: CLAUDE.md §What-kiho-IS rewritten; `skill-authoring-standards.md` adds `metadata.kiho.data_classes:` frontmatter rule (warn 60d / error 180d lazy migration); `committee-rules.md` adds "Storage-fit committee" type; `storage-architecture.md` adds §"Practical matrix" cross-reference + Tier-3 inventory update. Lazy migration discipline preserved — skill-improve touches migrate one skill at a time.
- **Pre-work: `bin/kb_lint_skill_solutions.py` — first post-hook parity checker.** Deterministic script that verifies `<wiki>/skill-solutions.md` matches the union of `skill_solutions:` frontmatter across all wiki pages on project and/or company tier. Filters page-path wikilinks (contain `/`) from the "extra" drift set so cross-linking to KB entries is not flagged. Referenced from `agents/kiho-kb-manager.md` §"Index rebuild protocol" step 5 (optional, advisory). Exit codes 0 aligned / 1 drift / 2 usage / 3 internal per v5.15.2 convention. **Pattern proven for Wave 2**: auto-generated indexes get a deterministic post-hook parity checker rather than relying solely on the sub-agent rebuilder. Fixture-verified for drift detection (missing index entries + orphan references), advisory no-op when wiki absent.
- **Doctrine realignment — markdown-only misreadings removed.** Two load-bearing lines previously conflated "canonical state" with "markdown": `CLAUDE.md` line 21 ("Canonical state is markdown; processing artifacts and agentic memory use appropriate storage...") and `references/skill-authoring-standards.md` Non-Goal §3 (which listed "markdown-only state" as a CLAUDE.md invariant). Both rewritten 2026-04-18 to reflect the three-tier ReAct doctrine already specified in `references/storage-architecture.md` (v5.18) — Tier-1 markdown for committee-reviewable state, Tier-2 JSONL/YAML/JSON for processing artifacts, Tier-3 on-demand sqlite/embeddings with eviction for agentic working memory. The data shape chooses the tier; markdown is not the default.
- **Motivation.** v5.18 shipped `skill-architect` which already reasons ReAct-style (deterministic decision tree first, LLM only on ambiguous nodes), and `storage-architecture.md` v1.0 already permits all three tiers. But 100% of 44 skills ship markdown-only in practice, `skill-create`'s 32 Python scripts re-parse every SKILL.md on each run, and agents read "Canonical state is markdown" as a blanket default. This entry is the first step of a multi-phase redesign: Phase 0 data-class inventory, Phase 1 per-category tech-stack committee, Phase 2 `references/data-storage-matrix.md` practical spec, Phase 3 `evolution-scan --audit=storage-fit` tooling, Phase 4 pilot migration (capability-matrix vs committee-records; committee-chosen).
- **Non-goals for v5.19.** Not a mass migration; not a rewrite of `storage-architecture.md` invariants; not an MCP server; not a persistent runtime database. Pilot ships one skill's storage at Tier-3; every other skill stays where it is until a separate committee vote.

## v5.18 concepts (skill-architect — Phase 2.0)

- **Closes the v5.17 intake gap.** v5.17 factory enforces declared `skill_spec` but cannot derive it from intent. v5.18 ships `skill-architect` as **Step 0** of the SOP — reads raw user intent and proposes a complete validated `skill_spec` struct before skill-spec validates it. Result: when authoring org-sync from scratch, the user no longer has to ask "no need any script?" — architect proposes `scripts: [recompute.py]` from intent signals. Verified end-to-end via `bin/skill_factory.py --from-intent "<text>"`.
- **6-substep architect pipeline.** Step A `extract_signals.py` (deterministic; tokenize + match against signal taxonomy); Step B `propose_spec.py` (deterministic decision tree → full spec proposal + per-field rationales); Step C `observe_siblings.py` (sibling-pattern observation; modal layout + divergence score); Step D `agents/critic.md` LLM subagent (fires conditionally when confidence < 0.85 OR sibling divergence > 0.30); Step E user confirmation (main conversation only; per-field accept / override / reject); Step F handoff to skill-spec.
- **`skills/_meta/skill-architect/`** — new skill at 8/8 patterns. Ships `scripts/extract_signals.py` (~300 lines, deterministic), `scripts/propose_spec.py` (~200 lines), `scripts/observe_siblings.py` (~150 lines), `agents/critic.md` (Step D subagent), `references/signal-taxonomy.md` (closed signal vocabulary — 5 categories: capability verbs, scripts-needed signals, references-needed signals, parity-layout joint, topic-tag signals), `references/intent-to-structure-rules.md` (worked examples + escalation paths + override semantics).
- **Closed signal vocabulary** (Gap 6 fix). Hand-curated initial vocab in `signal-taxonomy.md`: 8 capability verb buckets, 6 script-signal classes (arithmetic / data-shape / scale / determinism / file-format / side-effect), 5 reference-signal classes (multi-step / narrative / reference-data / body-length / domain-knowledge), 18 topic-tag mappings, 9 domain-keyword sets. Vocabulary expansion via CEO-committee vote per v5.16 controlled-set discipline.
- **Telemetry-driven canonical** (Gap 4 fix). New `parity_diff.py --telemetry-driven` flag computes the modal layout for a domain from observed siblings (≥5 siblings, ≥80% consensus). Detected drift on day-1: `core/harness` declared canonical = `meta-with-scripts`, observed canonical = `standard` (4 of 5 siblings — only org-sync ships scripts/, and only post-Phase 1.5 relocation). Warnings only; canonical changes still require CEO-committee vote.
- **Detector regex P3 enhancement.** `pattern_compliance_audit.py` Route subsection regex now also accepts `**Route N-A — ...**` bullet style (in addition to `### Route X` headings and `### N-A` numbered routes). Result: skill-create moves 6/8 → 7/8 (P4 still genuinely absent — F4 known debt).
- **Step E user confirmation is non-bypassable.** Even confidence=1.0 proposals require explicit user accept. CEO-only invariant + trust-tier doctrine — no autonomous shipping. Override telemetry logged to `_meta-runtime/architect-overrides.jsonl` for periodic CEO-committee weight tuning.
- **Backward compat.** If user provides a complete `skill_spec` upfront via `--regen <path>` or `--batch <yaml-file>`, Step 0 is skipped. Architect is opt-in via `--from-intent <text>` flag. Existing v5.17 invocation patterns continue to work.
- **Honest escalation.** When signals are too weak to derive a field (e.g., kiho's description matches multiple domains equally), architect returns `status: ambiguous` with `domain_tied_candidates` list rather than guessing alphabetically. Better to escalate than ship wrong.
- **Known v5.18.0 limitations** (vocabulary coverage, not architecture). For descriptions that focus on user-facing outcome rather than implementation (e.g., "synchronizes state" without mentioning JSONL/recompute), architect's deterministic Step B may miss scripts-needed signals. The Step D LLM critic catches these via intent-vs-implementation reasoning. Phase 2.5 (`skill-critic`) hardens this further.
- **Grounding.** Same primary sources as v5.17 (DSPy MIPROv2/GEPA, Anthropic skill-creator, Backstage, Karpathy autoresearch, Self-Refine + Reflexion + Voyager, Constitutional AI, Cognition Labs Devin) plus new explicit citation of Anthropic skill-creator's `agents/grader.md` / `comparator.md` / `analyzer.md` pattern as the architect critic-subagent reference architecture. Full provenance in `references/v5.18-research-findings.md`.

## v5.17 concepts

- **Skill factory architecture (prevention upstream, not inspection at end).** Per Toyota jidoka + Shingo's mistake-vs-defect distinction, the v5.17 factory installs poka-yoke gates *before* artifact generation rather than catching defects post-hoc. Adopted because 4 manual regen passes (kiho v5.16.3, recruit v5.16.6, org-sync v5.16.8, plus citation drift) all surfaced gaps via user review that no in-pipeline check prevented. The factory's goal: single CEO bulk decision per batch (green / yellow / red triage in `_meta-runtime/batch-report-<id>.md`), not per-skill review prompts.
- **Four new `_meta` skills + bin orchestrator.** `skills/_meta/skill-spec/` (typed-parameter resolver + dry-run), `skills/_meta/skill-graph/` (inbound rdeps + 4-anchor stale-path scan), `skills/_meta/skill-parity/` (sibling structural diff vs canonical layouts), `skills/_meta/skill-factory/` (10-step orchestrator). Plus `bin/skill_factory.py` chains all four scripts + the existing skill-create gates into per-skill verdicts.
- **10-step SOP** (per skill in batch). Step 1 skill-spec, Step 2 skill-graph, Step 3 skill-parity, Step 4 generate v1 (skill-create / skill-improve), Step 5 skill-critic (Phase 2), Step 6 skill-optimize trigger-eval (Phase 2), Step 7 skill-verify behavioral test (Phase 2), Step 8 citation Grep, Step 9 cousin-prompt robustness (Phase 2), Step 10 stale-path scan. Phase 1 wires steps 1-3, 8, 10 deterministically. Phase 2 (planned) wires steps 4-7, 9 via new skill-critic / skill-verify / skill-optimize / skill-watch.
- **Detector regex fixes in `pattern_compliance_audit.py`.** P3 now recognizes embedded route patterns (`Route N-A` in skill-create's prose-tree style, `### Route X` in kiho/recruit/org-sync's section style, `**Route X** ` in bullet style); P9 now detects `bin/*.py` references in addition to `scripts/*.py`. Result: kiho stays 7/7, skill-create moves 6/8 → 7/8 (P4 still genuinely absent — F4 known debt), org-sync 7/8 → **8/8** (P9 now applicable AND passing post-org_sync.py exit-code upgrade), recruit 7/7 unchanged.
- **Canonical layouts** (`skills/_meta/skill-parity/references/canonical-layouts.md`). Five templates: `standard` (SKILL.md only — most kb/, memory/, engineering/), `meta-with-scripts` (core/harness/* + ships scripts), `meta-with-refs` (_meta/* + ships refs only), `meta-with-both` (heavy _meta/* — skill-create, skill-spec, skill-parity, skill-factory), `parity-exception` (explicit opt-out with one-line rationale logged to `_meta-runtime/parity-exceptions.md`). New layouts require CEO-committee vote.
- **Catalog audit baseline (Apr 16 2026).** `parity_diff.py --mode catalog-audit` reports 42 total skills: 31 ok, 0 with exception, 11 divergent. Most divergences are pre-v5.17 layout-drift that Phase 3 mass graduation will close.
- **`bin/skill_factory.py --regen <SKILL.md>` interface.** Single-skill regen via the factory pipeline. Exit codes 0 (all green) / 1 (any yellow/red) / 2 (usage) / 3 (internal). Use `--dry-run` to print batch-report.md without writing; `--phase 1` (default) wires only Phase 1 steps; `--phase full` wires Phase 2 stubs (currently pass-through pending Phase 2 build).
- **Single CEO checkpoint per batch.** Replaces per-skill review prompts. CEO reads `_meta-runtime/batch-report-<id>.md` and replies once: `ship green, defer yellow, discuss red` (or variants). Mirrors Cognition Labs Devin reduction: *"the human's job narrows to decisions requiring judgment like architecture and product direction; everything mechanical gets caught and fixed before review"*.
- **Phase 2 deferred work.** `skill-critic` (grader/comparator/analyzer subagents per Anthropic skill-creator pattern), `skill-verify` (single-source behavioral test harness per Karpathy autoresearch keep-or-discard), `skill-optimize` (20-query trigger-eval loop, 60/40 train/test, best-by-test-score per Anthropic skill-creator), `skill-watch` (telemetry-driven regen queue per Langfuse + Devin bot-comment-as-trigger).
- **Grounding.** DSPy + GEPA (arXiv 2507.19457 ICLR 2026 Oral), Anthropic skill-creator (`agents/grader.md`, `comparator.md`, `analyzer.md` + `scripts/run_loop.py`), Backstage Software Templates (parameters JSONSchema + dry-run), Karpathy autoresearch (Mar 2026), Self-Refine (arXiv 2303.17651) + Reflexion (arXiv 2303.11366) + Voyager (arXiv 2305.16291), Constitutional AI (arXiv 2212.08073), Cognition Labs Devin autofix (Apr 2026), Toyota / Jidoka / Shingo / Deming canon. Full provenance in `references/v5.17-research-findings.md`.

## v5.16 concepts

- **Attention budget, not token budget.** The v5.16 pipeline drops token-count framing as the primary discoverability metric. Gate 3 (body token budget) is demoted from error to warn — body length is a kiho authoring preference, not a platform constraint or an attention failure. The new Gate 22 (candidate-set budget) measures what actually matters: *how many options does an agent face when picking this skill*. Grounded in arXiv 2601.04748 §5.2 (selection accuracy plateau at |S|≤20, collapse at |S|≥30, ~20% at |S|=200 on flat catalogs) + §5.3 (semantic confusability dominates skill count).
- **Three architectural primitives.** Primitive 1: **hierarchical walk-catalog** with max depth 3 (top-level → domain → sub-domain → skill). `skills/CATALOG.md` is now a domain index only (~50 lines); each domain has its own per-domain sub-catalog. `core` has been split into 5 sub-groups as part of the v5.16 migration: `harness/` (kiho, kiho-spec, kiho-setup, kiho-init, org-sync), `hr/` (recruit, design-agent), `inspection/` (kiho-inspect, session-context, state-read), `knowledge/` (research, research-deep, experience-pool), `planning/` (kiho-plan, committee, interview-simulate). Primitive 2: **closed 8-verb capability taxonomy** (`create | read | update | delete | evaluate | orchestrate | communicate | decide`), modeled on Kubernetes API verbs. Every skill's `metadata.kiho.capability` **MUST** be one of these eight. Primitive 3: **controlled 18-tag topic vocabulary** + **faceted retrieval**. Every skill's `metadata.kiho.topic_tags` entries **MUST** come from `references/topic-vocabulary.md`.
- **`routing:` YAML block populated in skills/CATALOG.md.** The block was designed in v5.14 but never implemented — `catalog_fit.py` (Gate 14) had been silently broken for months, parsing a block that didn't exist and falling through to permissive passes. v5.16 Stage A fixes this via `bin/routing_gen.py` (TF-IDF for `routing-description`, hand-curated overrides for semantic precision) invoked as a post-hook by `bin/catalog_gen.py`. The block lives inside `<!-- routing-block-start -->` / `<!-- routing-block-end -->` HTML-comment fences for idempotent regen. Nested `sub_domains:` entries carry the hierarchical layout. Gate 14 now exits 1 with `status: routing_block_missing` when the block is absent (regression test for the silent bug).
- **`bin/catalog_gen.py` is now hierarchy-aware.** Walks `skills/<domain>/<sub>/<skill>/SKILL.md` in addition to the flat `skills/<domain>/<skill>/SKILL.md` layout. Emits per-sub-domain sub-headings in the top-level CATALOG.md for hierarchical domains. `.skill_id` sidecars preserve stable identity across the directory moves.
- **`skill-find` rewritten for facet walking.** New `skills/_meta/skill-find/scripts/facet_walk.py` implements the 5-step deterministic walk: (1) tokenize query, (2) infer capability via a keyword → verb mapping (~50 synonyms), (3) infer domain by routing-description overlap with a ≥2× tiebreaker, (4) infer topic tags by exact vocab match, (5) enforce ≤10 candidate-set ceiling. Lexical scoring runs ONLY inside the filtered set. Underspecified queries fail fast with `status: underspecified` rather than returning garbage. Old lexical path kept as fallback when all facets are unresolvable.
- **Gates 19-24 added; pipeline grows 18 → 24.** Gate 19 (routing-block sync, error), Gate 20 (capability declared, error), Gate 21 (topic-vocab check, error), Gate 22 (candidate-set budget, error, **primary attention gate**), Gate 23 (trigger-phrase uniqueness, error, ≥0.70 Jaccard blocks), Gate 24 (agent portfolio density, warn, per-capability and per-domain thresholds). All six scripts are deterministic Python, stdlib-only, follow the 0/1/2/3 exit-code convention from v5.15.2 Pattern 9.
- **Migration verified clean on the current 38-skill catalog.** All 38 skills annotated with capability + topic_tags via one-shot `capability_apply.py` + `topic_apply.py`. Gate 19 reports 0 ghosts/orphans/mismatches/deprecated post-split. Gate 20 passes 38/38. Gate 21 passes 38/38. Gate 22 passes 38/38 when the skill's own capability + topic_tags are forced as facets. Gate 23 reports 0 trigger collisions. Gate 24 reports 2 warnings (CEO at 8 core skills, kb-manager at 8 kb skills) — both under the error threshold of 12. `catalog_walk_audit.py` reports 0 orphans, 0 stale DRAFTs, mean-pairwise Jaccard 0.0145 (matches v5.15 baseline 0.0146).
- **`bin/catalog_walk_audit.py` — weekly catalog health check.** Consolidates the demoted orphan / stale-DRAFT / confusability checks into one cron-friendly script. Runs in <5s on the 38-skill tree. Advisory by default (exit 0 with warnings); `--fail-on-warn` flag available for CI. kb-manager runs it on schedule per the v5.16 addition in `agents/kiho-kb-manager.md`.
- **`references/capability-taxonomy.md` and `references/topic-vocabulary.md`** — the two canonical files defining the closed capability verb set (8) and the controlled topic vocabulary (18). Both carry Non-Goals sections, BCP 14 declarations, committee-vote procedures for additions, and Changelog tables. Gate 20 / Gate 21 read the closed sets directly from these files via regex scan on `### \`verb\`` / `### \`tag\`` headings.
- **`references/v5.16-research-findings.md` + `skills/_meta/skill-create/references/v5.16-facet-retrieval.md`.** The durable provenance anchor (same arXiv + K8s + Library of Congress primary sources as v5.15 but with new empirical measurements) and the full architectural reference (three primitives, 6 gates, failure playbooks, 18-tag seed). Every v5.16 design decision traces to a primary source in one of these two files.
- **`skill-authoring-standards.md` v5.16 additions section.** Documents the three primitives as normative rules with BCP 14 keywords, the closed verb set, the controlled vocabulary, Gate 19-24 tiers and decision trees, the explicit "kiho is NOT a token-budget-driven organization system" stance, and the "attention budget replaces token budget" rationale. The v5.14/v5.15 sections are preserved below it.
- **Plugin bumped 0.4.7 → 0.4.8.** plugin.json description updated to reflect the 24-gate pipeline, attention-budget framing, closed 8-verb taxonomy, 18-tag vocabulary, core sub-domain split, and Gate 3 demotion.

## v5.15.2 concepts

- **`references/skill-authoring-patterns.md` (new).** Nine research-validated documentation patterns distilled from `novel-contribution.md` (the highest-scoring kiho reference as of Apr 2026). Every reference file written after v5.15.2 MUST score ≥ 6/9 on the review checklist. Old references graduate lazily on touch. The 9 patterns:
  1. **Non-Goals section** (KEP canonical; formerly called "negative-space opener")
  2. **Primary-source quotes with § references** (convention, not standard; inspired by PEP 12 and Rust RFCs)
  3. **Playbook decision trees** (Google SRE Workbook canonical; failure modes as runnable paths, not error lists)
  4. **Worked examples with byte-identical I/O** (OpenAPI Example Object + Go golden-file pattern)
  5. **Future-Possibilities sketches** (Rust RFC 2561; every sketch carries the non-binding disclaimer)
  6. **BCP 14 normative guardrails** (RFC 2119 MUST NOT / SHOULD NOT severity gradation; bare "Do not" is informal only)
  7. **MADR 4.0 decision records** (NOT Nygard's original — which has no Alternatives section; MADR 4.0 has first-class Considered Options)
  8. **Gate graduation ladder: tracked / warn / error** (convention, not standard; ESLint-compatible naming; closest canonical analog is K8s Alpha/Beta/Stable)
  9. **Exit-code convention: 0/1/2/3** (0=success, 1=policy violation, 2=usage error, 3=internal error; distinct from BSD sysexits; audit-confirmed compliant across all v5.14+ scripts in Apr 2026)
- **Non-Goals sections in CLAUDE.md and skill-create/SKILL.md.** Per Pattern 1, both files now open with explicit Non-Goals lists. kiho: not a runtime database, not an MCP server, not an embedding-based retrieval system, not a runtime dependency resolver, not a multi-user platform, not a container orchestrator, not a zero-interaction autonomous system. skill-create: not a fast-path generator, not an LLM judge at every gate, not a lint-only check, not a retroactive auditor, not an automated promoter, not a merge tool, not a multi-author collaboration tool.
- **Gate tier column in skill-create validation table.** Per Pattern 8, every gate now carries a `tier` (tracked / warn / error). All 17 existing gates are grandfathered at `error` tier because they were introduced before the ladder. New gates start at `tracked` and graduate via CEO-committee vote based on empirical data from `.kiho/state/gate-observations.jsonl` (v5.16 artifact). Gate 17's per-draft similarity scan is at `error`; the complementary `--catalog-health` metric is at `tracked`.
- **Exit-code convention documented in skill-authoring-standards.md.** Per Pattern 9, every Python script under `kiho-plugin/skills/**/scripts/` and `kiho-plugin/bin/` MUST follow 0/1/2/3. The convention was audited in Apr 2026 across 13 v5.14+ scripts plus `bin/kiho_rdeps.py` and `bin/catalog_gen.py` — all compliant. Pre-v5.14 scripts in `bin/` (org_sync, session_context) graduate lazily on touch.
- **`novel-contribution.md` rewritten to 632 lines** with empirical baseline (39 skills, 741 pairs, max Jaccard 0.1049, mean 0.0146 — thresholds have 3-6× headroom), Common pitfalls (5 pitfalls including --exclude self-match and STOP_WORDS eating discriminators), Troubleshooting Q&A (6 questions), Failure routes as explicit decision tree with 5 routes (A-E) and concrete re-run workflow, "When NOT to force" subsection with 7 hard-NO cases, Success metrics (6 quarterly metrics with concrete targets for post-rollout validation), Rejected alternatives section (A1-A6: LLM judge, embeddings, TF-IDF, 3-shingles, retroactive gate, AST extraction) each with "what it would look like" + "rejected because" + primary source. Scale upgrade path now has concrete trigger conditions (>3s wall-clock, >150 skills, >11k pairs) and a 6-step recipe.
- **Research provenance.** `v5.15.2` incorporates corrections from an isolated Apr 2026 research pass (24 WebSearches, 19 WebFetches) that validated all 9 patterns against primary sources. Major corrections from v5.15.1: Pattern 7 corrected from "Nygard ADR" to "MADR 4.0" (Nygard's original has no Alternatives section — this was a material error); Pattern 8 acknowledged as "convention, not standard" with ESLint off/warn/error as closest canonical analog; Pattern 1 renamed to "Non-Goals" per KEP canonical terminology; Pattern 5 added Rust RFC 2561 non-binding disclaimer; Pattern 9 documented the collision surface (POSIX 125-128, Rust panic 101, GNU ls/bash builtin=2, expr=3).
- **skill-create itself now scores 9/9 on the pattern checklist** (previously 2/9 at the initial v5.15.2 audit). Eight patches applied: (1) plugin-level references subsection listing `skill-authoring-patterns.md` and `skill-authoring-standards.md`; (2) BCP 14 key-words declaration block after Non-Goals; (3) two normative prohibitions upgraded to uppercase `MUST NOT` (top-level `requires:` field at Step 3, nested references at Step 5); (4) **Rejected alternatives** section with 6 MADR 4.0-lite entries (A1 LLM judge at every gate, A2 single-phase description loop, A3 author self-evaluation at Gate 11, A4 flat CATALOG with no routing block, A5 top-level `requires:` field, A6 auto-promote DRAFT→ACTIVE); (5) **Future possibilities (non-binding)** section with RFC 2561 disclaimer and 6 items (F1 Gate 18 automation script, F2 catalog-health graduation, F3 regression harness for deployed skills, F4 byte-identical worked-example CI, F5 cross-model consensus at Gate 11, F6 mcp-scan as advisory check) plus a `Do NOT on the upgrade path` list with 5 MUST NOT rules; (6) **Failure playbook** blocks for Steps 4, 10, 10.5 with severity / impact / taxonomy tags and numbered decision routes (4-A/4-B/4-C, 10-A/10-B/10-C/10-D, 10.5-A/10.5-B/10.5-C/10.5-D); (7) **Grounding** section consolidating 6 primary-source citations with verbatim quotes and § references (arXiv 2601.04748 §5.2 + §5.3, Anthropic Jan 2026 Demystifying Evals §step 7, Anthropic Mar 2026 Harness Design, arXiv 2603.02176 §2.1.1, arXiv 2604.02837 §4, Snyk ToxicSkills Feb 2026) plus `anthropics/skills` commit `b0cbd3d`; (8) **Gate 18 — pattern compliance** added to the validation gate table at `tracked` tier (reviewer-driven against `skill-authoring-patterns.md` §Review checklist; score ≥6/9; logs to `.kiho/state/gate-observations.jsonl`; graduates to warn/error via F1 when automation ships). Final audit: **P1-P9 all PASS**. skill-create/SKILL.md grew from 591 → 868 lines (+47%); plugin.json bumped 0.4.6 → 0.4.7. The skill that produces pattern-compliant skills now practices pattern compliance itself.

## v5.15 concepts

- **Gate 17 novel-contribution similarity scan.** `skills/_meta/skill-create/scripts/similarity_scan.py` runs after Gate 14 (catalog-fit) and before Gate 15 (budget pre-flight). It compares the draft description against every existing skill's description via Jaccard on unigrams + bigrams (after stop-word removal — same `STOP_WORDS` set as Gate 14). Thresholds: `Jaccard ≥ 0.60` blocks with `status: near_duplicate`; `0.30 ≤ Jaccard < 0.60` warns with `status: related_review`; `Jaccard < 0.30` passes. Top-3 matches are surfaced with `shared_sample`, `unique_to_draft_sample`, and `suggested_action` (`improve <top-match>` or `consider derive from <top-match>`). Full reference: `skills/_meta/skill-create/references/novel-contribution.md`. Grounding: arXiv 2601.04748 §5.3 (semantic confusability drives the phase transition — two similar skills hurt more than two extra unrelated skills; kiho at 37 skills is past |S|=30 inflection), Nelhage fuzzy-dedup, arXiv 2411.04257 LSHBloom.
- **Forward-only `metadata.kiho.*` dependency declarations.** Five namespaced fields: `requires` (hard — blocks deprecation of targets), `mentions` (soft — body links), `reads` (KB page paths), `supersedes`/`deprecated`/`superseded-by` (managed by skill-deprecate, authors never populate by hand). **No top-level `requires:` field** — Gate 2 rejects it as a spec violation per Claude Code issue #27113 (closed "not planned") and agentskills RFC #252 precedent. All declarations are forward-only; reverse queries are computed on demand. Grounding: kiho v5.15 H2.
- **On-demand reverse-lookup via `bin/kiho_rdeps.py`.** Walks six forward-edge sources fresh on every invocation: `metadata.kiho.requires`/`mentions` across SKILL.md files, agent `skills: [...]` arrays, CATALOG.md `parent_of` lists, wiki-link mentions in SKILL.md bodies, and `.kiho/kb/wiki/skill-solutions.md` back-refs. **Zero on-disk cache.** Matches the universal pattern of `pnpm why` / `cargo tree --invert` / `go mod why` / `bazel rdeps` / Terraform destroy-walk / Kubernetes `ownerReferences` — forward edges are authoritative, reverse views are computed never persisted. Exit 0 with JSON report; exit 1 when target does not resolve. Grounding: kiho v5.15 H5.
- **`skill-deprecate` lifecycle skill.** New skill at `skills/_meta/skill-deprecate/` for retiring a skill via the deprecation shim pattern from npm `deprecate` and cargo rename. Procedure: (1) run `kiho_rdeps` consumer review — ABORT if any `hard_requires` consumer exists; (2) rewrite body to one-paragraph "use `<superseded_by>` instead" redirect; (3) set `metadata.lifecycle: deprecated` + `metadata.kiho.deprecated: true` + `metadata.kiho.superseded-by: <slug>`; (4) bump minor version, preserve old in `versions/v<old>.md`; (5) call kb-update to cascade to `skill-solutions.md`; (6) regenerate CATALOG.md. The file stays present so slug resolution still works. **Distinct from skill-improve** (improve mutates a skill forward to fix problems; deprecate declares the skill is no longer the answer). Full reference: `skills/_meta/skill-create/references/deprecation-shim.md`.
- **`metadata.kiho.requires` vs `metadata.kiho.mentions` semantics.** `requires` is a **contract** enforced at evolution time — a skill cannot be deprecated while any other skill hard-requires it. `mentions` is an **audit trail** — kb-lint reports stale mentions but does not block. Neither is runtime-enforced at invocation (kiho has no runtime resolver); both are enforced at the points where breaking them would cause silent damage — deprecation (for `requires`) and lint (for `mentions`).
- **`kb-lint` stale_reference check (12th check).** For every skill and every agent portfolio, parse forward declarations and check whether any target has `metadata.kiho.deprecated: true`. Emit `stale_reference: <consumer> → <deprecated-target>` findings. Advisory by default; exits 1 only when stale count exceeds `stale_reference_threshold` (default 5). Also checks `inconsistent_deprecation` — both `metadata.lifecycle: deprecated` and `metadata.kiho.deprecated: true` must agree. Full spec in `skills/kb/kb-lint/SKILL.md`.
- **`skill-improve` Step 0 consumer review.** Before proposing a diff, `skill-improve` runs `bin/kiho_rdeps.py` against the target and records the consumer list in `.kiho/state/improve/<slug>/consumer-review.json`. Consumer counts are surfaced in the committee proposal and the changelog entry. Unlike `skill-deprecate`, consumer hits do NOT block `skill-improve` — improve preserves the contract — but authors must acknowledge any diff that touches a section listed in a consumer's `metadata.kiho.reads` path.
- **Semantic confusability catalog health metric.** `similarity_scan.py --catalog-health` computes the mean-pairwise Jaccard across all 37 skills. April 2026 baseline: 0.015 (very clean). Tracked as an informational metric in v5.15; may become a gate in v5.16 if confusability climbs past ~6-7× baseline.
- **No reverse-index cache, no embedding similarity, no mechanical merge, no AST body parsing.** These are explicit v5.15 non-goals grounded in primary sources: H5 (reverse index staleness), Q2 (embedding requires daemon), H4 (skill merge is an open problem per arXiv 2602.12430 and 2603.02176), Q9 (arXiv 2604.02837 §4 rejects AST-based behavioral-scope extraction).
- **Research findings offline reference.** `references/v5.15-research-findings.md` is the durable provenance anchor for every v5.15 change. All primary sources cited with URLs; H1-H5 headline findings; 10 Q&A answers; deliberately-NOT-added rationale; source index with primary + secondary + uncertain sections.

## v5.14 concepts

- **Analyzer + comparator sub-agents.** `skill-create` now has two dedicated sub-agents at `skills/_meta/skill-create/agents/`: `analyzer.md` scores benchmark.json by assertion-discrimination delta (with-skill pass rate minus without-skill baseline) and `comparator.md` performs blind A/B between iterations using a 4-dim rubric (correctness, scope, efficiency, instruction clarity). The analyzer rejects skills where >50% of assertions have delta < 0.20 (not discriminating) or any assertion has delta < 0.00 (anti-discriminating). Grounded in `anthropics/skills` commit `b0cbd3d` (Mar 6 2026) and the `analysis.json` + `comparison.json` schemas. Full reference in `skills/_meta/skill-create/references/analyzer-comparator.md`.
- **Non-monotonic iteration rule.** `scripts/run_loop.py` tracks all iterations of a draft skill and selects the historical best via comparator verdicts, not iteration number. `run-loop.json` reports `non_monotonic_winner: true` when the best iteration is not the most recent. Grounded in Anthropic's Mar 24 2026 "Harness design for long-running application development" post: "I regularly saw cases where I preferred a middle iteration over the last one."
- **Evaluator-generator separation.** Gate 11 transcript review is always performed by a fresh skeptical evaluator subagent — never the agent that authored the skill, never the agent that ran the scenario. System prompt prefix: "Uncertainty defaults to FAIL. Praise is affirmative and must be earned." Gate 11 now also produces a `baseline.json` (same scenarios with the draft SKILL.md removed) alongside `benchmark.json`, feeding the analyzer's discrimination calculation.
- **Capability vs regression eval buckets.** Every skill's eval suite splits into `evals/capability/` (iterative, free to mutate, gated on F1/balanced-accuracy, retired on saturation) and `evals/regression/` (frozen, populated after first ACTIVE promotion, gated on raw pass rate ≥ 95%, retired only via CEO committee). Conflating them was the top mistake Anthropic called out in the Jan 9 2026 Demystifying Evals post. Detail in `skills/_meta/skill-create/references/capability-regression-split.md`.
- **Precision + recall + F1 description scoring.** `scripts/compute_precision_recall.py` computes F1 and balanced_accuracy alongside raw accuracy for description triggering tests. Gate 2 now requires test F1 ≥ 0.80 AND balanced_accuracy ≥ 0.80 (was raw accuracy ≥ 0.75). The stratified 60/40 train/test split is balanced by `should_trigger` true/false.
- **Snyk 8-category security taxonomy** replacing Lethal Trifecta. Gate 9 now runs deterministic category-specific scans: prompt injection, malicious code, suspicious downloads, credential handling, hardcoded secrets, third-party content exposure, unverifiable dependencies, direct money access. Grounded in Snyk ToxicSkills (Feb 5 2026, 3,984 skills scanned, 13.4% critical). Detail in `skills/_meta/skill-create/references/security-v5.14.md`.
- **T1–T4 trust tiers + delta-consent.** Every skill carries `metadata.trust-tier: T1|T2|T3|T4`. T1 = unvetted (skill-create default), T2 = community (automatic after ≥3 agents × ≥2 sessions), T3 = trusted (CEO committee), T4 = fully-trusted (CEO + user approval). Any skill that changes >10% of bytes OR (for script-bearing skills) any script change at all, auto-downgrades to T1 and must re-pass Gate 11 + 12 + 13 + committee. Grounded in arXiv 2602.12430 (4-tier framework) and arXiv 2604.02837 (delta-consent).
- **2.12× rule for script-bearing skills.** Scripts increase vulnerability risk by 2.12× per arXiv 2602.12430. kiho enforces this by requiring script-bearing skills to carry 1 extra eval, 1 extra Gate 11 scenario, a tighter token budget (body ≤ 4500), and a 15% grader review sample rate (vs 10% for instructions-only).
- **Gates 12–16 (new).** Gate 12 isolation manifest (`isolation_manifest.py`) — every fs/env-var/network dep declared, harness cleans between trials. Gate 13 grader review (`grader_review.py`) — 10% deterministic sample of graded transcripts audited by kiho-kb-manager. Gate 14 catalog-fit (`catalog_fit.py`) — new skill's description must overlap parent domain's routing-description. Gate 15 budget pre-flight (`budget_preflight.py`) — sum of ACTIVE descriptions ≤ 90% of Claude Code's 1%/8k-char budget, per-skill ≤ 1,536 chars. Gate 16 compaction budget (`compaction_budget.py`) — top-N recent-invocation skills ≤ 80% of 25k post-compaction ceiling.
- **CATALOG.md routing descriptions.** `skills/CATALOG.md` now starts with a YAML-fenced `routing:` block giving each domain (`_meta`, `core`, `kb`, `memory`, `engineering`) a `routing-description` with keywords and `parent_of` skill-ID lists. Gate 14 enforces the parent overlap. Grounded in AgentSkillOS (arXiv 2603.02176, March 2026) — hierarchical catalogs score Bradley-Terry 100.0 vs flat 24.3 at 200 skills.
- **Claims extraction (Gate 11 evaluator addendum).** The evaluator extracts a `claims[]` array from each transcript with implicit factual / process / quality claims. Factual claims verify against tool outputs; process claims verify against the tool-call log; quality claims are subjective. **Uncertainty defaults to FAIL.** >50% unverifiable claims on a transcript auto-fails Gate 11. Grounded in `anthropics/skills/agents/grader.md`. Detail in `skills/_meta/skill-create/references/claims-extraction.md`.
- **Research findings offline reference.** `references/v5.14-research-findings.md` is the durable provenance anchor for every v5.14 change. All primary sources cited with URLs; per-thread findings; what was deliberately NOT added and why.

## v5.13 concepts

- **Train/test split description rewriter.** `skill-create` Step 4 is now two-phase: a fast binary 8-rule gate (`scripts/score_description.py`) followed by an iterative train/test rewriter (`scripts/improve_description.py`) modeled on Anthropic's official `skill-creator` workflow. The rewriter generates 20 test prompts via `scripts/generate_triggering_tests.py`, splits 60/40 train/test with a deterministic seed, rewrites the description based on train-set failures only (blind comparison — the optimizer never sees the test set), and reports final train/test accuracy with an overfitting warning if the gap exceeds 0.20. Max 5 iterations. Ship threshold: test accuracy ≥ 0.75.
- **20-prompt triggering test corpus.** Every new skill gets a deterministic 10-should-trigger + 10-should-not-trigger prompt set generated from intent + use_cases + trigger_phrases. Consumed by the Phase 2 rewriter and by the new `triggering_accuracy` test type in Step 9 eval generation. Re-runs with the same inputs produce the same corpus (hash-derived seed) so the held-out test split stays stable across iterations.
- **Gate 11: transcript review.** New gate between Step 9 (eval generation) and Step 11 (register). Spawns the draft skill against 3 scenarios from the 20-prompt corpus, captures real transcripts, runs a blind review prompt that scores 4 correctness dimensions (tool use, error handling, scope adherence, output shape match). Pass: every transcript ≥ 4.0 mean with no dim < 3.0. Fail: return to Step 5 (body draft) with diagnoses. Grounded in Anthropic's Jan 2026 "Demystifying Evals" 8-step pattern: *review transcripts, not just scores*. Full spec in `skills/_meta/skill-create/references/transcript-review.md`. Distinct from design-agent Step 7 (which validates a consuming agent; Gate 11 validates the skill in isolation).
- **Token-budget measurement.** Gate 3 now measures body tokens via `scripts/count_tokens.py` (tiktoken cl100k_base when available, word_count × 1.3 fallback). Budget: pass < 4000, warn 4000–5000, reject > 6000, hard limit 8000. Replaces pure line-count enforcement — a 500-line body of YAML tables and code blocks can easily exceed 6000 tokens, which the line-count rule missed.
- **Eval minimum raised from 3 to 5.** Every new skill now ships with basic + edge + refusal + **triggering_accuracy** (corpus-based) + **transcript_correctness** (Gate 11 snapshot). The two new types make description effectiveness and behavioral correctness durable regression anchors that `skill-improve` mutations can test against.
- **agentskills.io open standard alignment.** The 6 canonical top-level frontmatter fields are `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`. kiho-specific extensions (version, lifecycle, topic_tags, requires, audit block) now live under `metadata:` to preserve standard compatibility. Fields I speculatively added in v5.11 (`cache-control`, `priority`, `deprecated_at`, `required_versions`) are removed from templates — they're not in the spec.
- **Eval-driven skill development (8-step pattern) documented.** `references/skill-authoring-standards.md` now has a dedicated section citing Anthropic's Jan 2026 engineering blog: start with 20–50 real failures, automate manual tests, write unambiguous specs, balance positive/negative, isolated harnesses, appropriate graders, review transcripts, monitor saturation. This is guidance for skill authors; the 11 validation gates remain the hard pre-ship checks.
- **kiho vs Anthropic skill-creator divergences documented.** New section in skill-authoring-standards listing intentional divergences (kiho has explicit gates, OWASP security enforcement, versioning/lifecycle, CEO committee promotion; Anthropic skill-creator relies on human review) and shared patterns (train/test split, 1024-char limit, topic-based bodies, progressive disclosure tiers, one-level-deep references).

## v5.12 concepts

- **Skills now use per-skill `references/`, `scripts/`, and `assets/` subdirectories** — practicing the progressive disclosure we documented. Previously every skill body carried all its detail inline (design-agent hit 590 lines, violating the 500-line rule we wrote). v5.12 splits bodies down to a quick reference + explicit pointers into bundled resources. design-agent: 590 → 450. skill-create: body trimmed, 3 references added (description-improvement, security-scan, eval-generation). skill-learn: op=synthesize detail moved to `references/synthesize-procedure.md`. design-agent: Step 4d detail moved to `references/capability-gap-resolution.md` + `references/output-format.md`.
- **Executable scripts for deterministic operations.** Three skills gained `scripts/` subdirectories with Python utilities the LLM can shell out to for objective answers:
  - `skills/_meta/skill-create/scripts/score_description.py` — 8-rule description effectiveness scorer (exit 0 pass, 1 fail). Used by skill-create Step 4 iterative improvement loop; returns JSON with score, per-rule results, and actionable diagnoses.
  - `skills/core/planning/interview-simulate/scripts/score_drift.py` — persona drift calculator from N replay responses. Prefers sentence-transformers cosine distance; falls back to Jaccard token distance when no embedding backend is available. Emits pass/warn/fail/hard_fail status per tier thresholds (IC 0.20, lead 0.15, CEO 0.10).
  - `skills/core/knowledge/research-deep/scripts/robots_check.py` — robots.txt compliance check for every seed URL before research-deep starts fetching. Deny-on-disallow, fail-open on unreachable robots.txt with explicit logging.
- **Assets for structured data.** `skills/core/planning/interview-simulate/assets/canonical-rubric.yaml` is now the single source of truth for the 5-dimension rubric (accuracy/clarity/persona_fit/tool_use/refusal), default weights, per-test-type weight presets (domain_knowledge, tool_proficiency, soul_coherence, team_fit, refusal_focused), and aggregate pass gates.
- **Plugin-level vs per-skill references** — clarified two-tier pattern: plugin-level `references/*.md` are shared canonical specs (soul-architecture, skill-authoring-standards, capability-gap-resolution, deep-research-protocol, trusted-source-registry) loaded across multiple skills. Per-skill `<skill-dir>/references/*.md` are skill-specific implementation detail. Neither replaces the other; they layer.

## v5.11 concepts

- **skill-create (sk-create).** New `_meta` skill for **greenfield skill authoring** aligned with the 2026 SKILL.md open standard. Takes a structured intent (domain, consumer agents, trigger phrases, use cases) and runs a 10-step deliberative pipeline: dedup check → frontmatter draft → description iterative improvement (8-rule scoring, max 3 loops) → body with progressive disclosure → scripts/references/templates → 10 validation gates → security scan (OWASP Agentic Skills Top 10 + Lethal Trifecta) → eval generation (3 minimum) → DRAFT register. Distinct from `skill-learn` (mines sessions), `skill-derive` (specializes parents), and `skill-improve` (mutates existing). Used when cold-start authoring is needed and no prior content exists.
- **Updated skill-authoring-standards (2026).** `references/skill-authoring-standards.md` now incorporates: the full 2026 optional frontmatter spec (`disable-model-invocation`, `allowed-tools`, `context: fork`, `paths`, `shell`, `requires`, etc.), description effectiveness 8-rule checklist, versioning/lifecycle metadata (`version`, `lifecycle`), evals schema, OWASP Agentic Skills Top 10 security section, the Lethal Trifecta rule, 10 validation gates, and iterative description improvement protocol. The v3 content that was directionally correct is preserved.
- **design-agent Step 4d Researchable dual sub-path.** The Researchable gap class now splits into (a) research-deep + synthesize when external docs must be crawled, and (b) skill-create direct when intent is clear and no doc traversal is needed. Decision rule in the step body — research-deep is budget-expensive and only justified when there is a doc tree to BFS.
- **Templates: skill-frontmatter + skill-evals.** New canonical templates at `templates/skill-frontmatter.template.md` (2026 frontmatter with all optional fields annotated and usage guidance) and `templates/skill-evals.template.md` (3-minimum eval suite with basic/edge/refusal coverage and per-test rubric weight overrides).

## v5.10 concepts

- **Capability gap resolution (design-agent Step 4d).** When `design-agent` drafts a candidate and discovers a missing skill or tool (e.g., frontend-qa needs `sk-playwright-visual-regression` which doesn't exist yet), it classifies the gap into Derivable / Researchable / MCP / Unfillable and resolves via a cascade: `skill-derive` → `research-deep` + `skill-learn op=synthesize` → CEO escalation (MCP install / auth) → deployment deficit. Full spec in `references/capability-gap-resolution.md`. Security hard rules: no auto-install ever, synthesized skills always DRAFT, manifest review before install prompts, credentials only in OS keychain.
- **Trusted-source registry.** `research` now consults a persistent company-tier KB index of useful sources BEFORE hitting open web. Every successful cascade run auto-registers or updates the winning URL. Trust levels (`official` / `community` / `unverified` / `demoted` / `blocked`) promote and demote automatically based on success/failure counters. Schema + seed entries (playwright.dev, react.dev, storybook, mdn, deepwiki, ossinsight, mcp-registry, npm, pypi, crates, arxiv, owasp, web.dev) in `references/trusted-source-registry.md`. Never auto-promoted to `official` — that's CEO-only.
- **Deep research protocol (research-deep skill, sk-rdp).** BFS doc-tree traversal with link-graph state, skeleton-first incremental skill build, content-novelty termination (stops when 3 consecutive pages add 0 new concepts, not just on page/time budgets). Complements the single-pass `research` cascade — `research-deep` reads a whole doc tree and produces a living SKILL.md skeleton that `skill-learn op=synthesize` finalizes. State files: `.kiho/state/research-queue/<slug>.jsonl`, `.kiho/state/skill-skeletons/<slug>.md`. Full spec in `references/deep-research-protocol.md`.
- **Auth escalation via Playwright MCP.** When `research-deep` hits an auth-walled seed, it emits `escalate_to_user: auth-needed`. CEO spawns `mcp__playwright__browser_navigate` for interactive login, captures the session cookie via `mcp__playwright__browser_evaluate`, stores it in OS keychain scoped to the host. Cookies never touch KB or state files. Session expiry re-escalates. Full protocol in `references/deep-research-protocol.md` §"Auth escalation via Playwright MCP".
- **skill-learn op=synthesize.** Third sub-operation of `skill-learn` — consumes a research-deep skeleton (not session behavior) and finalizes it into canonical SKILL.md. Always writes DRAFT lifecycle; DRAFT → ACTIVE promotion requires a passing `interview-simulate` on a consuming agent + CEO committee approval.
- **CEO install-mcp and auth-needed escalation handlers.** Two new rows in the CEO escalation decision table route the design-agent / research-deep escalations into `AskUserQuestion` prompts that include manifest review (for install-mcp) and explicit cookie-scope explanation (for auth-needed). Kiho never runs install commands itself; user runs them and re-invokes `/kiho`.

## v5.9 concepts

- **Real pre-deployment simulation.** `design-agent` Step 7 no longer scores candidates theoretically. It invokes the new `skills/core/planning/interview-simulate/` skill to actually spawn the candidate, run the 7-test suite (5 originals + persona drift + refusal robustness), and score real outputs on the 5-dim rubric. Gate: rubric_avg ≥ 4.0, worst_dim ≥ 3.5, drift ≤ 0.20, refusal_robustness = 1.0.
- **Shared simulation engine.** `recruit` careful-hire's 6 interview rounds now delegate per-candidate spawn+score to `interview-simulate(mode: full)`. Recruit owns candidate pool generation, auditor review, and the hiring committee; it does not run inline simulation loops. Round definitions live in `skills/core/hr/recruit/references/interview-rounds.md` as data templates.
- **12-step design-agent pipeline.** Adds Step 0 (Intake — design brief), Step 2b (Memory block architecture — Letta-style persona/domain/user blocks), Step 3b (Self-contradiction audit — candidate audits its own draft), Step 4b (Tool allowlist validation — every behavioral rule must trace to an allowed tool), Step 4c (Model tier selection — opus/sonnet/haiku from task profile signals).
- **Optional red-line DSL.** Soul Section 4 red lines may carry an AgentSpec-style `dsl:` block (IF / AND / THEN) for precise runtime enforcement at the CEO pre-committee gate. Prose is still the documentation surface; DSL is additive precision. See `references/agent-design-best-practices.md` and `references/soul-architecture.md`.
- **Canonical best-practices reference.** `references/agent-design-best-practices.md` consolidates the 10 must-haves for 2026 agent definitions (role+goal, tool allowlist, red-line DSL, persona block 4–8k chars, 2–5 exemplars, memory architecture, explicit output shape, intent routing, simulation test suite, model tier), the red-line DSL grammar with 6 worked examples, the persona drift algorithm and thresholds, the model-tier decision table, and the kiho-vs-best-practices gap map.

## v5 concepts

- **Rich Soul v5 (12 sections).** Every agent .md has a `## Soul` section with 12 sections: Core identity, Emotional profile, Big Five with behavioral anchors, Values with red lines, Expertise + knowledge limits, Behavioral rules (5-7 if-then), Uncertainty tolerance thresholds, Decision heuristics, Collaboration preferences, Strengths + blindspots, Exemplar interactions, Trait history. Each section has a runtime role — none are decorative. Frontmatter carries `soul_version: v5`.
- **Deliberative agent creation.** `design-agent` is now a 10-step pipeline with pass gates: draft → coherence check → skill alignment → team-fit → test generation → rubric validation → (committee for careful-hire) → deploy → register. Minimum gates: coherence >= 0.70, alignment >= 0.70, fit >= 0.60, rubric avg >= 4.0/5.0.
- **Hermes-style auto-evolution.** `skill-learn` is the merged skill-capture + skill-extract with two sub-operations: `op=capture` (on-demand) and `op=extract` (post-task Hermes 5-stage loop). Auto-triggered at CEO INTEGRATE on novel successful iterations. Dedup check before publication.
- **Shared experience pool.** Project + company tiered pools at `.kiho/state/experience-pool/` and `$COMPANY_ROOT/experience-pool/`. Pool is a **view, not a store** — source of truth stays per-agent. Indexes skills, reflections, failure cases. Promotion path via kb-promote sanitization.
- **Cross-agent learning queue.** `memory-cross-agent-learn` writes notifications to `.kiho/state/cross-agent-learnings.jsonl`. CEO consumes at INITIALIZE step 15 when target agent is about to spawn — respects fanout-cap-of-5.
- **Soul drift propagation.** `soul-apply-override` applies authorized drift corrections from `soul-overrides.md` into live agent .md files. Runs coherence recheck before writing. Red line changes require CEO authorization specifically.
- **CEO self-reflection every turn.** CEO runs `memory-reflect` with `scope: ceo` at every `/kiho` INITIALIZE. Reads ceo-ledger + agent-performance + management-journals. Detects CEO's own drift. Outputs organization health report.
- **Pre-committee coherence gate.** Before convening self-improvement committees, CEO checks if proposed change matches any committee member's red line. Hard match → auto-dissent. Soft value conflict → convene with pre-seeded dissent note.
