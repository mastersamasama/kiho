---
name: evolution-scan
description: Karpathy-style autoresearch loop for skill evolution. Examines a skill (or all active skills), identifies one improvement, validates it, and applies or discards — one skill, one change, per iteration. Runs on-demand only via /kiho evolve. Each iteration follows examine-propose-validate-keep/discard-log. Fixed budget prevents runaway loops. Use when the CEO triggers skill maintenance, when a user says "/kiho evolve", "tune skills", "improve skills", or when post-session analysis shows skill underperformance. Never runs automatically.
metadata:
  trust-tier: T3
  kiho:
    capability: evaluate
    topic_tags: [lifecycle, validation]
    data_classes: ["skill-definitions", "skill-invocations", "drift-trend", "evolution-scan-audits"]
version: 2.0.0
lifecycle: active
---
# evolution-scan

The skill evolution loop. Inspired by Karpathy's autoresearch pattern: examine state, pick one change, validate, keep or discard, log, repeat. One skill, one change, per iteration. Binary decisions. Simplicity over ambition.

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119, RFC 8174) when, and only when, they appear in all capitals.

## When to use

Invoke evolution-scan when:

- The user types `/kiho evolve` (optionally followed by a skill name or `all`) — this is the canonical trigger
- The CEO's ledger shows a shelved self-improvement proposal that needs deeper deliberation (`agents/kiho-ceo.md:360, 380`)
- Post-session analysis shows a skill was invoked but produced suboptimal output, missed a trigger, or was worked around manually
- Periodic skill audit is warranted (e.g., stale skills with use_count drops, test_case failures, 30+-day inactivity)
- The user says "tune skills", "improve skills", or "evolve the catalog"

Do **NOT** invoke evolution-scan for:

- **Feature / bugfix / refactor flows** — evolution is a maintenance mode, not an in-band skill authoring step (use `skill-create` for greenfield, `skill-improve` for single-skill mutations inside a feature flow).
- **Batch `_meta/` skill regeneration** — use `bin/skill_factory.py --regen` (v5.17) with green/yellow/red triage; evolution-scan is the tactical per-skill loop, factory is the strategic batch.
- **KB lint / quality audit** — use `kb-lint` for KB-wiki staleness and `pattern_compliance_audit.py` for per-skill P1-P9 scoring.
- **Skill deprecation** — use `skill-deprecate` with explicit `superseded_by` + consumer review; evolution-scan does not retire skills.

## Non-Goals

- **Not automatic.** Runs only on explicit `/kiho evolve` invocation. No cron mode, no post-session trigger, no background daemon.
- **Not multi-change-per-iteration.** One skill, one change, per iteration. No batching. Rollback granularity MUST stay at single-change fidelity.
- **Not retroactive.** Does not rewrite history. LOG records outcomes forward. Past discards stay discarded; past applies stay applied.
- **Not a planning-then-executing split.** Each iteration is independent. The loop does not plan ahead or accumulate a changeset before applying. Matches Karpathy autoresearch loop discipline.
- **Not the skill factory.** `bin/skill_factory.py` (v5.17) handles batch regeneration with green/yellow/red triage + single CEO checkpoint per batch. evolution-scan is the tactical per-skill loop; factory is the strategic out-of-band pass.
- **Not a security gate.** Anti-pattern, OWASP, and Lethal Trifecta detection live in `skill-create` Gate 9. evolution-scan trusts the existing safety floor and does not re-scan at evolution time.

## Contents
- [Inputs](#inputs)
- [Evolution loop](#evolution-loop)
- [Examine phase](#examine-phase)
- [Propose phase](#propose-phase)
- [Validate phase](#validate-phase)
- [Decision phase](#decision-phase)
- [Budget and termination](#budget-and-termination)
- [Response shape](#response-shape)
- [Worked examples](#worked-examples)
- [Failure playbook](#failure-playbook)
- [Anti-patterns](#anti-patterns)
- [Rejected alternatives](#rejected-alternatives)
- [Future possibilities](#future-possibilities)
- [Grounding](#grounding)

## Inputs

```
target: <skill-name | "all">  (default: "all" — scan all ACTIVE skills)
budget:
  max_iterations: <default 5>
  max_tool_calls: <default 50>
session_context_path: <optional — path to recent session context for evidence>
audit_lens: <null | "storage-fit" | "critic-drift">  (default: null — normal examine loop)
  - "storage-fit"  → deterministic data_classes audit via storage_fit_scan.py;
                     writes _meta-runtime/storage-audit.jsonl + rendered md
  - "critic-drift" → derives evolve agenda from critic-verdicts.jsonl via
                     bin/evolve_trigger_from_critic.py; finds skills whose
                     average critic score has fallen below threshold or trended
                     down over the last N runs; emits a JSON agenda the CEO
                     pipes into per-skill skill-improve invocations
report_only: <bool, default false>  (must be true when audit_lens is set; read-only
  audit never mutates SKILL.md)
```

## Evolution loop

```
INITIALIZE
  Read target skill(s) metadata
  Read session context (if provided)
  Read changelog history

LOOP (while budget allows):
  EXAMINE  → identify one opportunity
  PROPOSE  → draft one change (FIX, DERIVED, or CAPTURED)
  VALIDATE → test the change
  DECIDE   → keep or discard (binary)
  LOG      → record the outcome
  NEXT     → pick the next skill (or exit)
```

This is NOT a planning-then-executing model. Each iteration is independent. The loop does not batch changes or plan ahead. One iteration, one change.

## Examine phase

For each skill (or the single target skill):

1. Read `SKILL.md` frontmatter — name, version, lifecycle, use_count, last_verified_at
2. Read `changelog.md` if it exists — recent change history
3. Read session context (if provided) — look for evidence of the skill being used, misused, or missed
4. Read the skill's `test_case` from frontmatter

Produce an assessment:

| Signal | Classification | Operation |
|---|---|---|
| Skill failed its test case | fix-needed | FIX |
| Skill was invoked but produced suboptimal output (evidence in session context) | underperformance | FIX |
| Skill description missed a trigger (session shows relevant query that did not match) | trigger-miss | FIX |
| Agent manually worked around a skill limitation | workaround-detected | FIX or DERIVED |
| Multiple skills were combined for one task | combine-opportunity | DERIVED |
| Agent succeeded without skill support (novel pattern) | capture-opportunity | CAPTURED |
| Skill has not been used in 30+ days | staleness-check | verify test case, possibly deprecate |
| Skill's `metadata.kiho.data_classes:` mismatches `references/data-storage-matrix.md` | storage-fit | REPORT only — routes to audit lens (see below); no FIX |
| Skill's average critic score < 0.80 over the last 5 runs OR trended down ≥ 0.05 | critic-drift | FIX via skill-improve (use agenda from critic-drift lens; see below) |
| No issues found | healthy | skip |

Pick the highest-priority assessment for this skill. If "healthy", skip to the next skill.

## Storage-fit audit mode (v5.19)

When `audit_lens: "storage-fit"` and `report_only: true` are set, evolution-scan switches to a deterministic audit mode that:

- Walks `skills/**/SKILL.md` and checks each skill's `metadata.kiho.data_classes:` against `references/data-storage-matrix.md`
- Emits a single batch report at `_meta-runtime/batch-report-storage-audit-<ts>.md`
- Does NOT propose changes, does NOT invoke `skill-improve`, does NOT mutate any SKILL.md
- Respects the single-CEO-bulk-decision pattern: one CEO reply per run
- Exits 0/1/2/3 per v5.15.2 convention

Implementation: `scripts/storage_fit_scan.py` is the single deterministic entry point. Reference taxonomy + report skeleton: `references/storage-audit-lens.md`.

Audit mode bypasses the normal signal table and the Propose/Validate/Decide/Log flow. It is a standalone read-only pass. Remediation for DRIFT / MATRIX_GAP verdicts happens later via per-skill `skill-improve` iterations driven by the CEO's bulk decision.

Invocation example (from CEO loop or shell):

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/_meta/evolution-scan/scripts/storage_fit_scan.py \
  --plugin-root <plugin> \
  --elapsed-days <days-since-v5.19-ship>
```

See `references/storage-audit-lens.md` for verdict taxonomy (ALIGNED / UNDECLARED / DRIFT / MATRIX_GAP / ERROR), grace-window semantics, and report skeleton.

## Critic-drift audit mode (v5.20 Wave 1.2)

When `audit_lens: "critic-drift"` and `report_only: true`, evolution-scan derives an evolve agenda from `_meta-runtime/critic-verdicts.jsonl` (the JSONL stream populated by `skills/_meta/skill-critic/scripts/critic_score.py` and the factory's Step 5 invocations). This is the kiho-blessed alternative to building a separate `skill-optimize` step (the v5.20 committee explicitly chose to extend `skill-improve` rather than introduce step 6 — see skill-factory SKILL.md).

The lens triggers a skill into the agenda when, over the last N runs:

- `score-floor`  — average overall_score is below the threshold (default 0.80), OR
- `downward-trend` — most-recent score is at least 0.05 lower than the oldest in the window

Each agenda entry records the recent average, score delta, axis blindspots (axes that scored < 0.7 in ≥ half of recent runs), and a recommended next action: invoke `skill-improve` with the failure evidence pre-filled.

Implementation: `bin/evolve_trigger_from_critic.py` is the single deterministic entry point. Output is JSON to stdout (or `--out <path>`) so the CEO can pipe it through a follow-up loop.

Invocation example:

```bash
python ${CLAUDE_PLUGIN_ROOT}/bin/evolve_trigger_from_critic.py \
  --threshold 0.80 --window 5 --min-runs 2 --lens both
```

CEO follow-up: for each agenda entry, invoke `skill-improve` with `failure_evidence` populated from the entry's axis blindspots and score delta. After each FIX, the skill MUST be re-scored with `critic_score.py --invocation-source evolve-trigger` to confirm the patch improved the score; reject any patch that did not (see `skill-improve` SKILL.md §Validation).

## Propose phase

Before proposing any change to an existing skill, invoke `skill-structural-gate` on the target with `mode: pre-regen`:

```
python skills/_meta/skill-structural-gate/scripts/run_gate.py --target <target-SKILL.md> --mode pre-regen
```

If the gate returns `status: fail` (graph axis finds stale paths or broken inbound deps; parity axis finds layout divergence without exception), **STOP the iteration** before proposing. A FIX that would break an inbound consumer, or a DERIVED that would produce a layout-divergent artifact, must not be attempted here — route to `skill-improve` for an explicit migration pass instead. This closes the architectural gap where evolution-scan could propose breaking changes that only surface at apply time.

Skipping this pre-check is an anti-pattern.

Based on the assessment and a passing structural gate, propose exactly ONE change:

- **FIX:** call `skill-improve` with the failure evidence. Receive a proposed diff.
- **DERIVED:** call `skill-derive` with the parent skill(s) and use case. Receive a draft skill.
- **CAPTURED:** call `skill-learn op=capture` with the session context slice. Receive a draft skill. (The legacy name `skill-capture` was unified into `skill-learn op=capture` per `skill-learn/SKILL.md`.)

The proposal is a concrete artifact — a diff for FIX, a new SKILL.md for DERIVED/CAPTURED.

## Validate phase

For FIX proposals:
- Re-run `skill-structural-gate` on the diffed target to confirm the diff introduced no layout drift or broken anchors
- Replay the skill's test case against the proposed diff
- If both structural gate and test case pass: mark as validated
- If either fails: mark as invalid

For DERIVED/CAPTURED proposals:
- Run `skill-structural-gate` on the new draft to confirm canonical-layout alignment
- Run the new skill's test case
- Check dedupe via `skill-find`
- If structural gate + test passes + no duplicate: mark as validated
- Otherwise: mark as invalid

Validation is binary: pass or fail. No partial credit.

## Decision phase

**Keep:** Apply the change.
- FIX: `skill-improve` applies the diff, bumps version, archives old version
- DERIVED: the new skill directory is committed as `lifecycle: draft`
- CAPTURED: the new skill directory is committed as `lifecycle: draft`

**Discard:** Do not apply.
- Log the reason for discarding
- Move to the next skill

The decision is binary. No "maybe" or "try again." If a proposal does not clearly pass validation, discard it.

## Budget and termination

The loop terminates when any of:
- `max_iterations` reached
- `max_tool_calls` reached
- All target skills have been examined with no opportunities found
- Three consecutive discards (the remaining skills are likely healthy)

## Response shape

```json
{
  "status": "ok",
  "iterations_run": 4,
  "changes_applied": [
    {
      "skill": "kb-add",
      "operation": "FIX",
      "classification": "trigger-miss",
      "version": "1.0.0 → 1.0.1",
      "summary": "Added 'ingest page' to description triggers"
    },
    {
      "skill": "session-parser",
      "operation": "CAPTURED",
      "lifecycle": "draft",
      "summary": "New skill for parsing session-context into structured events"
    }
  ],
  "changes_discarded": [
    {
      "skill": "kb-search",
      "operation": "FIX",
      "reason": "Test case failed after proposed change"
    }
  ],
  "skills_healthy": ["memory-read", "memory-write"],
  "budget_remaining": {
    "iterations": 1,
    "tool_calls": 12
  }
}
```

### Audit-mode response shape (v5.19)

When `audit_lens: "storage-fit"` and `report_only: true` are set, the response shape is flattened (no iterations; no changes_applied/discarded):

```json
{
  "status": "ok",
  "total": 45,
  "tally": {
    "ALIGNED": 0,
    "UNDECLARED": 45,
    "DRIFT": 0,
    "MATRIX_GAP": 0,
    "ERROR": 0
  },
  "matrix_rows": 43,
  "beyond_grace": false,
  "report_md": "_meta-runtime/batch-report-storage-audit-<ts>.md"
}
```

`status: "drift"` replaces `"ok"` when any DRIFT, MATRIX_GAP, or UNDECLARED-beyond-grace verdict is present.

## Worked examples

### Example 1 — FIX after test failure

**Input**
```
target: kb-add
session_context_path: .kiho/state/session-contexts/2026-04-16-ceo-turn-3.md
```

**Flow**
1. Examine: `kb-add` test_case fails after a frontmatter migration changed `topic_tags` from list → comma-string.
2. Propose: FIX via `skill-improve` — diff updates the tag parser to handle both shapes.
3. Validate: replay test_case against proposed diff → PASS.
4. Decide: keep. `skill-improve` applies the diff, bumps `1.0.0 → 1.0.1`, archives old version.

**Output**
```json
{
  "status": "ok",
  "iterations_run": 1,
  "changes_applied": [{
    "skill": "kb-add",
    "operation": "FIX",
    "classification": "fix-needed",
    "version": "1.0.0 → 1.0.1",
    "summary": "Parser accepts both list and comma-string topic_tags (frontmatter migration compat)"
  }],
  "changes_discarded": [],
  "skills_healthy": [],
  "budget_remaining": {"iterations": 4, "tool_calls": 45}
}
```

### Example 2 — DERIVED from combine-opportunity

**Input**
```
target: all
session_context_path: .kiho/state/session-contexts/2026-04-16-knowledge-work.md
```

**Flow**
1. Examine: session shows `kb-search` + `kb-promote` chained 3× in one task (combine-opportunity).
2. Propose: DERIVED via `skill-derive` — draft `kb-search-and-promote` composing both parents.
3. Validate: run draft test_case + `skill-find` dedupe check → PASS, no duplicate.
4. Decide: keep. New skill committed at `lifecycle: draft` for committee review at next CEO turn.

**Output**
```json
{
  "status": "ok",
  "iterations_run": 1,
  "changes_applied": [{
    "skill": "kb-search-and-promote",
    "operation": "DERIVED",
    "classification": "combine-opportunity",
    "lifecycle": "draft",
    "summary": "Composes kb-search → kb-promote for single-call knowledge elevation"
  }],
  "changes_discarded": [],
  "skills_healthy": [],
  "budget_remaining": {"iterations": 4, "tool_calls": 42}
}
```

### Example 3 — discard after invalid

**Input**
```
target: memory-reflect
```

**Flow**
1. Examine: session context slice suggests memory-reflect trigger phrase could cover "introspect self".
2. Propose: FIX via `skill-improve` — diff adds the phrase to description triggers.
3. Validate: replay test_case → FAIL. The new phrase causes over-triggering on unrelated introspection queries.
4. Decide: discard. Log reason. Move to next skill (none — single target).

**Output**
```json
{
  "status": "ok",
  "iterations_run": 1,
  "changes_applied": [],
  "changes_discarded": [{
    "skill": "memory-reflect",
    "operation": "FIX",
    "reason": "Test case failed: new trigger caused over-activation on introspection queries"
  }],
  "skills_healthy": [],
  "budget_remaining": {"iterations": 4, "tool_calls": 44}
}
```

## Failure playbook

**Severity**: error (budget exhaustion + target-not-found block the loop)
**Impact**: one or more proposed changes discarded or not applied; user may need to re-invoke with different target or higher budget
**Taxonomy**: budget | target | dependency | infra | termination | lifecycle

```
  evolution-scan failure
      │
      ├─ max_iterations or max_tool_calls reached     → Route A (budget)
      ├─ target skill not found                       → Route B (target)
      ├─ dependency on stale skill name (e.g., skill-capture) → Route C (dependency)
      ├─ validate phase flake (test infra unavailable, not skill defect) → Route D (infra)
      ├─ three-consecutive-discards trigger            → Route E (termination)
      └─ target lifecycle != active                   → Route F (lifecycle)
```

### Route A — budget exhausted

1. Exit cleanly with `status: ok` and partial results (whatever was applied up to this point is kept — no rollback).
2. Report `budget_remaining: {iterations: 0, tool_calls: ...}` so the caller knows it was a budget stop, not a natural stop.
3. Suggest to user: `"budget exhausted; re-invoke /kiho evolve with --max-iterations=N if more work needed"`.

### Route B — target skill not found

1. Verify the target name via `skill-find` fuzzy-match; if a close match exists, surface it.
2. If single-target invocation: exit with `status: target_not_found` and the close-match suggestion.
3. If `target: all` and one skill has an unreadable SKILL.md: log the error, continue to next skill (do not abort the loop).

### Route C — stale skill name dependency

1. If the Propose phase tries to call a skill that no longer exists (e.g., legacy `skill-capture`), resolve to current name via CATALOG lookup or `kiho_rdeps` forward scan.
2. If resolution succeeds (e.g., `skill-capture` → `skill-learn op=capture`), retry with the correct name and log the rename for author awareness.
3. If resolution fails, escalate to CEO: unresolvable dependency — likely the referenced skill was deprecated without superseding pointer.

### Route D — validate phase flake

1. Distinguish **test infra failure** (missing fixtures, network unreachable, corrupt replay harness) from **skill defect** (test_case returns wrong output).
2. If infra: discard the proposed change BUT do not penalize the skill; log `reason: validate_infra_flake` and skip to next iteration.
3. If defect: discard normally and log `reason: test_failed`.
4. If three consecutive iterations hit infra flakes, exit with `status: validate_infra_unavailable` — calling user must fix infra before re-invoking.

### Route E — three consecutive discards

1. Treat as natural termination signal — remaining skills are likely healthy.
2. Exit with `status: ok` and report `skills_remaining` list for the caller's awareness.
3. Do NOT continue to `max_iterations` — three discards in a row is the stop heuristic.

### Route F — target lifecycle != active

1. If target is `lifecycle: draft`: skip with rationale `"drafts are evolved via committee review, not evolution-scan"`.
2. If target is `lifecycle: deprecated`: skip with rationale `"deprecated skills are retired via skill-deprecate; evolution does not apply"`.
3. If target is `lifecycle: archived`: skip with rationale `"archived skills are read-only historical records"`.

## Anti-patterns

- **MUST NOT** run evolution automatically. It runs only on explicit `/kiho evolve` invocation.
- **MUST NOT** batch multiple changes to the same skill in one iteration. One skill, one change.
- **MUST NOT** skip validation. Every proposed change is tested before the keep/discard decision.
- **MUST NOT** return a "maybe" verdict — the decision is binary. Keep or discard.
- **MUST NOT** exceed the budget. If budget is exhausted, stop cleanly and report.
- Do not evolve skills during a feature/bugfix/refactor flow. Evolution is a separate maintenance mode.

## Rejected alternatives

### A1 — Batch multiple changes per iteration

**What it would look like**: collect 5 fixes across 5 skills, apply atomically at end of loop.

**Rejected because**: violates Karpathy's "one change per iteration" principle; rollback granularity collapses (can't undo just the change that caused regression); debugging which change broke what becomes impossible when the bundle is large.

**Source**: Karpathy autoresearch (Mar 2026); Reflexion (arXiv 2303.11366) §3 episodic-boundary discipline; Self-Refine (arXiv 2303.17651) §4 explicit-revise boundaries.

### A2 — LLM-judge validation instead of test_case replay

**What it would look like**: ask Claude "did this change improve the skill?" to score.

**Rejected because**: non-deterministic across runs; defeats the binary keep/discard discipline; correlated failures when judge and author share the same hidden bias. Deterministic test-case replay is the only validator that keeps the decision truly binary.

**Source**: kiho v5.14 evaluator-generator separation doctrine; Anthropic Mar 2026 Harness Design §generator/evaluator separation — *"the evaluator must not be the generator."*

### A3 — Background daemon mode (continuous evolution)

**What it would look like**: cron-schedule `/kiho evolve --continuous` every N hours.

**Rejected because**: violates the kiho CLAUDE.md Non-Goal *"Not a zero-interaction autonomous system"*. CEO-only user interaction invariant requires explicit invocation. Autonomous evolution could silently apply changes the user has not reviewed — precisely the drift risk the trust-tier doctrine is designed to prevent.

**Source**: CLAUDE.md Non-Goals (`kiho-plugin/CLAUDE.md`); v5.14 T1-T4 trust tiers; v4 invariants.

### A4 — Unified Improve+Derive+Capture op (single endpoint)

**What it would look like**: collapse FIX / DERIVED / CAPTURED into one `skill-evolve` operation with a polymorphic handler.

**Rejected because**: each operation has distinct validation logic (FIX replays existing test_case; DERIVED+CAPTURED run a new test_case + `skill-find` dedupe), distinct lifecycle implications (FIX bumps version in-place; DERIVED/CAPTURED create a new `lifecycle: draft` artifact), and distinct CEO-committee review paths. Merging hides the decision tree and makes the loop harder to debug.

**Source**: kiho v5 design rationale; Single Responsibility Principle.

## Future possibilities

*The following are sketches, not commitments. Per RFC 2561, these items describe possible future directions and are not binding on any implementer.*

- **F1 — Confidence-weighted signal prioritization.** Trigger: ≥3 cycles where Examine's "highest-priority assessment" misranks and CEO overrides the pick. Sketch: weight signal-table rows by historical hit-rate mined from `.kiho/state/evolution-history.jsonl`. Would require a new telemetry stream + weight-update script.
- **F2 — Cross-skill diff cluster detection.** Trigger: ≥3 cycles where 2+ skills receive correlated FIXes sharing the same root cause (e.g., same frontmatter migration). Sketch: pre-pass detects shared diff patterns via Jaccard; surfaces a single ADR with per-skill diffs in one batch. Would still respect "one change per iteration" — batch as presentation, not as atomic commit.
- **F3 — Integration with `bin/skill_factory.py` Phase 2.5.** Trigger: `skill-watch` ships (Phase 2.5). Sketch: factory auto-queues low-performing skills for `/kiho evolve` based on `.kiho/state/skill-invocations.jsonl` telemetry. Factory handles the batch triage; evolution-scan handles per-skill tactical changes.

**Do NOT** add:
- Continuous / autonomous mode (rejected A3).
- LLM-judge validation (rejected A2).
- Batch-changes atomic commit (rejected A1).
- Retroactive history rewrites (Non-Goal).

## Grounding

The one-change-per-iteration discipline traces to **Karpathy autoresearch (Mar 2026)** — examine, propose, validate, keep-or-discard, log, repeat — with each iteration independent and no planning-execute split. Full philosophical foundation: `kiho-plugin/references/karpathy-autoresearch-loop.md`.

> **Self-Refine (arXiv 2303.17651) §4**: *"explicit critique → revise → keep-or-discard outperforms continuous refinement without episodic boundaries."* — grounds the binary keep/discard decision phase. https://arxiv.org/abs/2303.17651

> **Reflexion (arXiv 2303.11366) §3**: *"verbal reinforcement requires episodic boundaries — without a bounded budget and explicit termination, feedback loops degrade into thrashing."* — grounds the bounded budget + 3-consecutive-discards termination. https://arxiv.org/abs/2303.11366

> **Anthropic Mar 2026 Harness Design §generator/evaluator separation**: *"the evaluator must not be the generator. When the author scores its own output, confidence calibrations collapse."* — grounds calling `skill-improve` as generator while evolution-scan remains orchestrator-evaluator, not diff author. https://anthropic.com/engineering/

The on-demand-only invocation discipline derives from **kiho v5.0 invariants** (`kiho-plugin/CLAUDE.md`, `references/ralph-loop-philosophy.md`): depth cap 3, fanout cap 5, no autonomous skill mutation without CEO authorization.
