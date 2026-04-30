# Content routing — KB / State / Memory (v6.4+)

This reference documents the deterministic 3-lane content classifier that runs in CEO INTEGRATE step (`agents/kiho-ceo.md` §LOOP step e). The classifier picks ONE destination per ≥0.90-confidence decision so the KB stays durable, state stays turn-scoped, and memory accumulates cross-project lessons.

## The three lanes

| Lane | Destination | What goes here |
|---|---|---|
| **A — STATE** | `.kiho/state/ceo-ledger.jsonl` (`action: state_decision`) + optional `.kiho/audit/<spec>/<turn-id>.md` | Turn-scoped artefacts: bug fixes with commit refs, single-route nav changes, "we shipped X this turn with proof Y". Reversible by re-running the turn's plan. |
| **B — KB** | `.kiho/kb/wiki/<page-type>/` via `kiho-kb-manager op=add --trigger=<A-F>` | Durable project knowledge: reusable principles, conventions ("use X when Y"), architectural decisions with trade-offs, concepts ("how does theming work"), entities (trusted sources, tools). |
| **C — MEMORY** | `agents/<name>/memory/lessons.md` (skill) + `~/.claude/projects/<encoded-cwd>/memory/feedback_*.md` (feedback) via `memory-write` skill | Cross-project reusable lessons: process discipline, QA rules, user preferences. Domain-independent — applies to any project using kiho. |

## Decision tree

```
Iteration produced a decision (confidence ≥0.90) OR a B/D/E/F trigger fired.

  Step 1 — Lane A check (any one sufficient):
    □ body cites file:line / source_seq / commit / screenshot AS evidence
    □ title contains feature/spec slug (BB-*, FU-*, s-*) without
      generalising verb (Use/Prefer/Always/Never/MUST/SHOULD/Avoid)
    □ "reusable principle" hidden inside body is ≤1 sentence
    □ decision is reversible by re-running this turn's plan
  → Yes → emit state_decision ledger entry. Done.
  → No  → continue to Step 2.

  Step 2 — Lane C check (any one sufficient):
    □ title starts with L- or contains lesson/rule/discipline
    □ content is process-shaped, not code-shaped
    □ reason chain is "we got burned by X, going forward Y"
    □ domain-independent (applies equally to other projects)
  → Yes → emit memory_write with memory_kind: skill | feedback. Done.
  → No  → continue to Step 3.

  Step 3 — Lane B check (must satisfy ≥3 of 4):
    □ title is generalisable noun phrase or imperative
    □ body would be useful 6 months later cold-read
    □ ≥1 reusable principle in 1-2 sentences (no commit reference)
    □ cross-references ≥1 existing KB entry via [[wikilink]]
  → Yes (≥3 pass) → kb-manager op=add --trigger=<A-F>. Done.
  → No  (<3 pass) → emit kb_deferred with reason: classification_ambiguous.
                    Surface for user confirmation in turn summary.

  Hybrid (principle is KB, evidence is state):
  → SPLIT into two ledger entries — one state_decision + one kb_add.
    Do not write the same body to both lanes.
```

## Lane A — STATE — worked examples

### Example A1: 2-LOC bugfix with commit reference

```
Iteration: fixed Ledger sticky-header transparent bg.
Decision: "Add backgroundColor: bgPrimary, zIndex: 2 to renderSectionHeader View at LedgerScreen.tsx:343."
Confidence: 0.95
```

**Routing**: Lane A. Reasons:
- File:line ref (`LedgerScreen.tsx:343`) is load-bearing.
- Reversible by re-running the turn (just revert the 2-LOC change).
- The reusable principle ("RN-Web sticky views need explicit bg") is ≤1 sentence — extract that to Lane B SEPARATELY as a hybrid split.

**Output**:
1. Ledger entry: `{action: state_decision, slug: ledger-sticky-fix, summary: "2-LOC bg fix on LedgerScreen.tsx:343", evidence_paths: ["src/screens/LedgerScreen.tsx:343"]}`
2. Optional Lane B nucleus: KB convention `CV-RN-WEB-STICKY-OPAQUE-BG` — *"On RN-Web, sticky `<View>` headers MUST set explicit `backgroundColor` from `useTheme().bgPrimary` and `zIndex≥1`."*

### Example A2: nav route change

```
Iteration: changed Home FIAT chip onPress from navigate("DraftModal", {mode: "routeB"}) to navigate("AccountRules").
Confidence: 0.92
```

**Routing**: Lane A. Reasons:
- Single-file edit (`HomeScreen.tsx`) with specific call-site reference.
- Reversible.
- The reusable UX principle is ≤1 sentence and goes to Lane B separately.

**Output**:
1. Ledger entry: `{action: state_decision, slug: home-fiat-to-account-rules, ...}`
2. Lane B nucleus: KB convention `CV-LIST-BEFORE-WIZARD` — *"When user invokes 'add new X', route to the existing-X listing first; the listing's `+` header opens the wizard."*

## Lane B — KB — worked examples

### Example B1: durable convention

```
Trigger: D (spec section that defines a project-wide convention) — PRD §3.3 says "all monetary amounts MUST be decimal-integer strings in the asset's smallest unit."
```

**Routing**: Lane B → `conventions/CV-MONEY-FORMAT.md`.

**Lane-B 4-of-4 check**:
- ✓ Generalisable imperative ("Render smallest-unit balances via `formatAmount(raw, decimals)` + `currencySymbol(asset)`").
- ✓ Useful 6 months later cold-read (every UI render of money hits this).
- ✓ Reusable principle in 1-2 sentences without commit ref.
- ✓ Cross-references ≥1 existing KB entry (links `[[D-AC-VISION]]`, `[[D-THEME-PROVIDER]]`).

**kb-manager call**: `op=add --trigger=D --prd-anchor "doc/project.md §3.3"`

### Example B2: architectural decision with trade-offs

```
Trigger: A (decision with reusable principle ≥0.90) + E (cross-area committee verdict).
Decision: "Adopt Zustand persist middleware with partialize for theme + BYOK + AI-provider preferences."
Confidence: 0.95
```

**Routing**: Lane B → `decisions/D-THEME-PERSIST.md` AND `synthesis/2026-04-zustand-vs-jotai.md` (committee synthesis).

**kb-manager call**: `op=add --trigger=E --committee-id "2026-04-30-state-mgmt"`

## Lane C — MEMORY — worked examples

### Example C1: process discipline lesson

```
Observation: 17-screen visual QA sweep tested only light mode; user immediately found 6 dark-mode regressions on the next turn.
```

**Routing**: Lane C, `memory_kind: skill`.

**Lane-C check**:
- ✓ Title `L-DARK-MODE-VERIFY` (L- prefix).
- ✓ Process-shaped ("always test both themes during visual QA").
- ✓ Reason chain ("we got burned by light-only sweeps, going forward toggle to 深色 + repeat").
- ✓ Domain-independent (any kiho-using project benefits).

**Output**: write to `agents/<qa-engineer>/memory/lessons.md` (kiho-internal, accumulates across all kiho-using projects).

### Example C2: user-facing feedback rule

```
User said: "Don't summarise what you just did at the end of every response — I can read the diff."
```

**Routing**: Lane C, `memory_kind: feedback`.

**Output**: write to `~/.claude/projects/<encoded-cwd>/memory/feedback_no_trailing_summaries.md` per Claude Code's auto-memory schema (frontmatter `name/description/type: feedback`, body with `**Why:**` + `**How to apply:**` lines).

## Six trigger scenarios

A KB write fires under ANY of six triggers (see `agents/kiho-ceo.md` Invariants list):

| Trigger | When | Required field |
|---|---|---|
| **A** | confidence ≥0.90 + reusable principle | `confidence` |
| **B** | user says "remember", "always X", "next time prefer Y" | `user_quote` |
| **C** | 3+ delegations same pattern in session | `pattern_occurrences`, `source_paths` |
| **D** | spec/PRD defines a project-wide convention | `prd_anchor` |
| **E** | committee architectural decision ≥0.85 | `committee_id` |
| **F** | code review reports recurring pattern in ≥3 files | `affected_files[]` |

Triggers **B** and **D** bypass the ≥0.90 confidence gate — they are explicit-intent triggers.

## Hybrid handling (split decision)

A decision can carry both a durable principle (Lane B) and load-bearing turn evidence (Lane A). Example: "Metro reserves `/assets/*` middleware; we changed our deep-link from `assets/category/cash` to `asset-category/cash`."

**Output**: TWO ledger entries:
1. `{action: state_decision, slug: assets-url-collision-fix-2026-04-30, evidence_paths: ["src/navigation/linking.ts:41", "screenshots/v1-qa-sweep-2026-04-30/"]}`
2. `{action: kb_add, slug: c-metro-assets-prefix, type: concept, ...}` — the durable nucleus only, no turn evidence.

Do NOT write the same body to both. The state_decision references the principle by `[[wikilink]]`; the KB entry references the state archive by `evidence_archive: .kiho/audit/...`.

## Ambiguous handling (kb_deferred)

If no lane fits ≥3 heuristics, emit `{action: kb_deferred, slug_intent: <slug>, reason: classification_ambiguous}` and surface in turn summary. The audit script does NOT flag deferred-with-reason as drift — the user resolves on the next turn.

## Audit-script enforcement (v6.4+)

`bin/ceo_behavior_audit.py` runs three classifier-related checks on DONE:

1. **`check_kb_integrate_or_classify_skipped`** — every ≥0.90 `subagent_return` must have a follow-up entry of any kind: `kb_add | state_decision | memory_write | kb_deferred`. Missing all four = MAJOR drift.
2. **`check_kb_classification_drift`** — walks `.kiho/kb/wiki/decisions/*.md` modified during the turn window. State-ness score ≥0.50 (4 weighted heuristics) = MAJOR drift `kb_state_artefact`. Use `--turn-from <iso>` to grandfather pre-v6.4 entries.
3. **`check_orphan_state_lessons`** — `.kiho/state/` should not contain `*-lesson*.md` / `lessons-*.md`; those belong in memory. MINOR drift `lesson_in_state_should_be_memory`.

The classifier prevents the v6.3 failure mode where every ≥0.90 decision was dumped into KB regardless of whether it was state-shaped, KB-shaped, or memory-shaped.
