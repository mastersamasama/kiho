# Decision — OKR framework (committee okr-framework-2026-04-23)

## Status

Accepted by unanimous close at aggregate confidence 0.91, 2 rounds. See `transcript.md` for full deliberation.

## Context

Lark, Workday, and most modern HR/productivity suites ship OKRs as a top-level surface: quarterly Objectives (O) with 3–5 weighted Key Results (KR) each, arranged in an alignment tree where department Os align upward to company Os and individual Os align upward to department Os. Scoring is 0.0–1.0 per KR, aggregated via weighted mean. Mid-cycle check-ins surface drift.

kiho has no company-level goal hierarchy today. `plan.md` is a flat RACI task list. Cycle-runner has per-cycle budgets (iters, wall-clock, pages) but no cross-cycle goal linkage. An IC cannot cite "which company-level intent does this task serve?". This is the user's stated pain point ("lark can let user setup okr, and we may integrate to ket agent make okr").

## Decision

Introduce a new `core/okr/` skill portfolio with **three** skills (not five — scope held by auditor challenge):

| Skill | Capability | Purpose |
|---|---|---|
| `okr-set` | `create` | Create a new O (with 3–5 nested KRs) under strict RACI pre-emit gate |
| `okr-checkin` | `update` | Mid-cycle KR progress update (0.0–1.0 score per KR + comment) |
| `okr-close` | `update` | End-of-period OKR close — compute final weighted score + archival move |

Alignment (`okr-align`) and reporting (`okr-report`) are **deferred** to v5.24+ pending real demand.

**Storage**: Tier-1 markdown at `<project>/.kiho/state/okrs/<period>/<o-id>.md`. Each file is a single Objective with YAML frontmatter (`o_id`, `okr_level`, `period`, `owner`, `aligns_to`, `status`) and a `## Key Results` section listing weighted KRs. This follows the Karpathy-wiki "one concept per file" discipline rather than ballooning `plan.md`.

**RACI pre-emit gate** on `okr-set` (mirrors the v5.22 `recruit` certificate pattern — poka-yoke upstream, not inspection at end):

- `okr_level: company` → requires user-set via CEO `AskUserQuestion` escalation. The skill refuses to emit without a `USER_OKR_CERTIFICATE:` line in the intended file content.
- `okr_level: department` → requires a `decisions/<dept>-okr-<period>.md` committee decision page as prerequisite (committee must close before `okr-set` may run).
- `okr_level: individual` → requires dept-lead sign-off. Mechanism: the approval-chain DSL to be designed by committee 02. Interim stub: manually-inserted `DEPT_LEAD_OKR_CERTIFICATE:` line in the O file, to be replaced by committee 02's general mechanism when it lands.

**Cadence**: No automatic cadence. `okr-checkin` is invoked explicitly by the responsible agent (R per RACI) on an irregular basis. No Ralph-loop-turn trigger. The auditor vetoed "checkin every turn" as ceremony noise.

**Scoring**: Per KR: 0.0–1.0 (committed, not stretch). Aggregate: weighted mean (weights sum to ≤ 100, normalized). A stretch KR may be marked `stretch: true` in its frontmatter; stretch KRs scoring > 0.7 count as committed-0.7 for aggregate purposes (prevents stretch-double-counting gaming).

**No new cycle template**. Cycle-runner is for terminating work; OKRs are guides for that work. A cycle MAY cite the OKR it serves via `aligns_to_okr: O-2026Q2-*` in its `index.toml` frontmatter, but the cycle does not BECOME an OKR.

**No runtime (PreToolUse) hook**. The pre-emit gate is sufficient (it's a skill-internal check, not a tool-boundary gate). The RACI violations are caught in the skill's own prerequisite check.

## Consequences

### Positive

- Closes the user-identified gap: company-level goal hierarchy with O→KR→task linkage becomes expressible.
- Low implementation cost: 3 skills, 1 storage row, no new cycle template, no new hook.
- Poka-yoke RACI: goal-hacking via agent-proposed individual Os is blocked at skill emission, not after the fact.
- Composable: when committee 02 (approval) ships, the individual-O approval upgrades mechanically.
- Preserves kiho's Karpathy-wiki discipline — one file per O keeps `plan.md` scannable.

### Negative

- Three new skills is three more to maintain, one more storage row to document, one more user-facing surface.
- Without `okr-align` in v5.23, the alignment-tree is implicit (follow `aligns_to` frontmatter by hand). Readers must trace links manually.
- Without `okr-report`, aggregate period rollup requires manual scan or future dashboard (committee 06 may cover).
- Committee 02 dependency on the individual-O gate — if committee 02 produces a surprising DSL, the interim stub may need refactor.

## Alternatives considered and rejected

- **Shape (a): extend `plan.md` with an `## OKRs` section** — rejected because `plan.md` scannability degrades, and the Karpathy-wiki one-concept-per-file discipline argues for separate files.
- **Shape (c): make OKRs a cycle template `okr-quarterly`** — rejected because cycle-runner semantics is "terminating work with budgets". OKRs are *goals that guide work*, not the work itself. Overloading breaks semantics.
- **Five skills** (`okr-set`, `okr-checkin`, `okr-close`, `okr-align`, `okr-report`) — rejected by auditor as scope creep; alignment and reporting deferred to v5.24.
- **Auto cadence** (checkin every turn / every cycle close) — rejected as ceremony noise; explicit agent invocation preserves signal.

## Scope estimate

- 3 new skills (~200 lines SKILL.md each + references)
- 1 new data-storage-matrix row (triggers a Storage-fit follow-up committee)
- 0 new cycle templates
- 0 new PreToolUse hooks
- Estimated implementation: ~6 hours agent-authoring time via skill-factory (Phase 2 subagent-request bundles)

## Dependencies

- Committee 02 (approval chains) — the individual-O gate mechanism upgrade depends on committee 02's DSL. Interim stub works standalone.
- Storage-fit committee (follow-up) — required for the new `okrs/<period>/<o-id>.md` data class matrix row.

## Next concrete step

A future implementation plan authorizes kiho skill-factory to generate the 3 skill scaffolds (spec → graph → parity → generate → critic → optimize → verify → citation → cousin-prompt → stale-path), with the RACI pre-emit gate inlined into each SKILL.md's Procedure section.
