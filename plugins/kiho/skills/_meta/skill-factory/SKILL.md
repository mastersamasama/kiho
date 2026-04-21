---
name: skill-factory
description: Top-level orchestrator that chains the 10-step skill generation pipeline (skill-spec dry-run, skill-structural-gate combined graph + parity check, skill-create or skill-improve, skill-critic review, skill-optimize trigger-eval loop, skill-verify behavioral test, citation-Grep verbatim check, cousin-prompt robustness probe, stale-path scan) and emits a per-batch report with green / yellow / red triage so the CEO makes a single bulk decision per batch instead of reviewing each skill individually. Implements the v5.17 factory architecture: prevention upstream rather than inspection at the end. Phase 1 of the factory wires steps 1-3, 8, and 10 (deterministic Python only); Phase 2 adds steps 4-7 and 9 (LLM-loop infrastructure). Triggers when the user says "run the skill factory", "generate batch of skills", "factory regen", "skill-factory --batch", or invokes bin/skill_factory.py directly.
metadata:
  trust-tier: T3
  version: 1.2.0
  lifecycle: active
  kiho:
    capability: orchestrate
    data_classes: ["skill-definitions", "skill-drafts", "skill-factory-verdicts"]
    topic_tags: [authoring, lifecycle, orchestration]
---
# skill-factory

Top-level skill-generation orchestrator. The v5.17 factory entry point — chains the 10-step SOP across N skills in a batch, emits `_meta-runtime/batch-report-<id>.md` with green / yellow / red triage, and asks the CEO for one bulk decision per batch instead of per-skill review.

> **v5.21 cycle-aware.** This skill is the `factory` phase entry in `references/cycle-templates/skill-evolution.toml`. When run from cycle-runner, the cycle's `index.toml` carries the target skill from upstream `intake`; this skill's batch_id + verdict + verdicts_jsonl_ref write back into `index.factory.*` for downstream `critic` phase to evaluate. Atomic invocation remains supported for ad-hoc batch regeneration outside any cycle; both paths share the same JSONL audit trail (factory-verdicts.jsonl).

The architecture shift: from **inspection at the end** (24 gates after generation, manual review per skill) to **prevention upstream** (Steps 1-3 fail-fast at intake, Step 8/10 enforce poka-yoke surfaces, Step 5/6/7 catch behavioral defects before ship). Grounded in Toyota jidoka + Shingo's mistake-vs-defect distinction.

> **v5.20 scope trim.** Phase 2 (steps 4–7: generate/critic/optimize/verify LLM loop) will not be built. Evidence: zero call-sites for the stubs, behavioral gate responsibilities are covered by the existing `skill-improve` + `evolution-scan` loop, and shipping a partial Phase 2 would make the factory's green verdict structurally-only-valid but behaviorally-unverified. Step 1 is additionally redirected to `skill-intake` (sk-053), which merges the former architect + spec seam. See `.kiho/state/evolution/history.jsonl` for the full rationale.

> **v5.20 Wave 1.1 dual-write.** The factory now appends one JSONL row per skill per invocation to `_meta-runtime/factory-verdicts.jsonl` (data-storage-matrix row `skill-factory-verdicts`) in addition to the legacy `_meta-runtime/batch-report-<id>.md`. **The JSONL is the source of truth**; the markdown is a rendered view that can be re-derived via `python bin/render_batch_report.py --kind factory --batch-id <id>`. CEO trend queries (e.g. "how many step-3 failures across the last 30 days?") use the JSONL via `jq` or DuckDB; per-batch human review uses the markdown.

## When to use

Invoke when:

- Generating or regenerating ≥ 2 skills in one session — batch mode
- A telemetry trigger from `skill-watch` (Phase 2) surfaces regen candidates
- A reviewer wants end-to-end validation for a single skill
- Mass graduation underway (Phase 3 — lazy-graduation skills batch-regenerated)

Do **NOT** invoke when:

- A single trivial skill change is needed — use `skill-improve` directly
- A new skill is being prototyped — use `skill-create` until the spec stabilizes
- Only structural compliance is needed — `pattern_compliance_audit.py --all` suffices

## Non-Goals

- **Not a generator.** Orchestrates `skill-create` / `skill-improve` / `skill-derive` — does not produce artifacts itself.
- **Not a daemon.** Runs synchronously per invocation. Phase 2 `skill-watch` does queue aggregation; the factory consumes it on demand.
- **Not an auto-shipper.** Green verdicts still wait for CEO bulk decision. One approval per batch is not zero approvals.
- **Not a per-skill review surface.** Per-skill prompts during a batch are the anti-pattern this skill exists to eliminate.
- **Not an architecture changer.** Cannot add domains, change canonical layouts, or extend the capability/topic vocabulary. Those are CEO-committee decisions.
- **Not a runtime execution engine.** Produces markdown artifacts; the runtime is the user's Claude Code session.

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are interpreted per BCP 14 (RFC 2119, RFC 8174).

## The 10-step SOP

Gate semantics for each step live in the referenced skill's own SKILL.md — this table only names the ordering. The factory is pure sequencing; individual gate logic is not restated here.

| Step | Name | Source | Phase | Lifecycle |
|---|---|---|---|---|
| 1 | skill-spec | `skills/_meta/skill-spec/SKILL.md` | 1 | active |
| 2 | skill-structural-gate (graph axis) | `skills/_meta/skill-structural-gate/SKILL.md` | 1 | active |
| 3 | skill-structural-gate (parity axis) | `skills/_meta/skill-structural-gate/SKILL.md` | 1 | active |
| 4 | generate v1 | `skill-create` or `skill-improve` SKILL.md §Gates | 2 | active (upstream wired) |
| 5 | skill-critic | `skills/_meta/skill-critic/SKILL.md` | 2 | active (v5.19.4+) |
| 6 | skill-optimize | Phase 2 (planned) | 2 | **deferred** |
| 7 | skill-verify | Phase 2 (planned) | 2 | **deferred** |
| 8 | citation Grep | `skill-create/SKILL.md §Gates` (verbatim-check gate) | 1 | active |
| 9 | cousin-prompt robustness | Phase 2 (planned) | 2 | **deferred** |
| 10 | stale-path scan | `skills/_meta/skill-structural-gate/SKILL.md` (graph axis, defense-in-depth) | 1 | active |

Steps 2 and 3 are served by the combined `skill-structural-gate` via `scripts/run_gate.py`; the factory passes the same target to both axes and reads a single merged verdict.

**Phase 1** (shipped v5.11-v5.18): steps 1, 2, 3, 8, 10 deterministic.
**Phase 2 wave 1** (shipped v5.19.4): step 5 `skill-critic` wired; steps 4/6/7/9 still stubbed pass-through.
**Phase 2 wave 2** (deferred): steps 6 `skill-optimize`, 7 `skill-verify`, 9 `cousin-prompt` marked `lifecycle: deferred` until a CEO committee vote promotes them. Agents and the factory **MUST NOT** expect these gates to fire — the deterministic pass-through returns score=null, which the verdict aggregator treats as "not applicable", not "failed".

## Per-skill verdict

| Verdict | Meaning | CEO action |
|---|---|---|
| **green** | All applicable steps PASS | Auto-ship on bulk approval |
| **yellow** | Steps PASS with ≥ 1 warning (e.g., critic axis < 0.8) | Brief review; ship or defer |
| **red** | Jidoka-stop on ≥ 1 step | CEO judgment required; orchestrator did NOT write |

## Failure playbook

**Severity**: error per skill (does not block siblings).
**Impact**: failed skill ships as red; orchestrator continues with siblings; CEO triages reds in batch.

```
factory step failure
    │
    ├─ Step 1 spec fails        → red; spec violation surfaced (see skill-spec §Gates)
    ├─ Step 2/3 gate fails      → red; graph or parity verdict surfaced (see skill-structural-gate §Failure playbook)
    ├─ Step 8 citation fails    → red; verbatim mismatch surfaced with diff
    ├─ Step 10 stale-path fails → red; 4-anchor findings surfaced
    └─ infra error              → red; orchestrator log entry in _meta-runtime/factory-telemetry.jsonl
```

Per-route handling lives in the referenced skill's Failure playbook. The factory only records the verdict and moves to the next skill; it does not restate gate semantics.

## Worked examples

### Example 1 — single-skill regen, green

Invocation: `python bin/skill_factory.py --regen skills/core/harness/org-sync/SKILL.md`

Expected `_meta-runtime/batch-report-<id>.md`:

```markdown
# Factory batch report — 2026-04-16T10:23:00Z

## Summary
- Batch size: 1 skill
- Verdicts: 1 green / 0 yellow / 0 red

## Per-skill verdicts

### org-sync — green
- Step 1 (skill-spec): **green** — capability=update, topic_tags=[state-management], parity_layout=meta-with-scripts
- Step 2 (skill-structural-gate, graph): **green** — 3 consumers, 0 stale paths
- Step 3 (skill-structural-gate, parity): **green** — matches meta-with-scripts canonical
- Step 8 (citation-grep): **green** — 5 blockquotes, all verbatim
- Step 10 (stale-path): **green** — 0 stale anchor refs

## CEO bulk decision
Reply: "ship green, defer yellow, discuss red"
```

### Example 2 — dry-run preview

Invocation: `python bin/skill_factory.py --batch _meta-runtime/batch-spec-2026-04.md --dry-run`

Expected: tree-diff preview + verdict prediction per skill. No file writes.

### Example 3 — Phase 1 single-skill

Invocation: `python bin/skill_factory.py --regen skills/core/hr/recruit/SKILL.md --phase 1`

Expected: verdict based only on Steps 1, 2, 3, 8, 10. Steps 4-7, 9 stubbed pass.

## Response shape

```json
{
  "status": "ok | ok_with_yellow | red_present | error",
  "batch_id": "<UUID>",
  "report_path": "_meta-runtime/batch-report-<id>.md",
  "verdicts": {"green": 3, "yellow": 1, "red": 1},
  "per_skill": [
    {"name": "skill-A", "verdict": "green", "step_results": {"1": "green", "2": "green", "3": "green", "8": "green", "10": "green"}},
    {"name": "skill-B", "verdict": "yellow", "warnings": ["..."]},
    {"name": "skill-C", "verdict": "red", "errors": ["Step 3 layout_divergence: scripts_files unexpected"]}
  ],
  "ceo_action_required": true,
  "telemetry_path": "_meta-runtime/factory-telemetry.jsonl"
}
```

## Anti-patterns

- **MUST NOT** write any artifact before CEO bulk approval. Orchestrator is intent-only until CEO replies.
- **MUST NOT** skip a step because it looks fine. Every step runs every time.
- **MUST NOT** prompt the CEO mid-batch. Single checkpoint is the whole point.
- **MUST NOT** silently downgrade red to yellow. Jidoka stops are jidoka stops.
- Do not run skill-factory inside a sub-agent — CEO-only invariant.
- Do not extend the 10-step SOP without an RFC. The pipeline shape is a controlled set.

## Rejected alternatives

### A1 — Per-skill CEO review (pre-v5.17 status quo)

Each invocation prompts the CEO. Rejected: inspection-at-end pattern Deming warns against. Does not scale, does not prevent defects.

### A2 — Fully autonomous, zero CEO review

Ship green skills with no CEO involvement. Rejected: v5.14 trust-tier doctrine requires CEO on new artifacts in a controlled catalog. One bulk approval is the right oversight dose.

### A3 — Distributed orchestration via subagent fanout

Each skill a separate sub-agent task. Rejected: for batches > 5 skills, fanout would breach the depth-3/fanout-5 cap. Sequential loop is correct.

### A4 — Replace with Airflow / Prefect / Dagster

Rejected: adds runtime dependency + scheduler. Hand-coded per-step Python matches existing `bin/catalog_gen.py` composition pattern.

### A5 — Keep gates duplicated inside the factory SKILL.md

Rejected (2026-04-17 slim-and-consolidate): per-step gate logic lives in the owning skill's SKILL.md (`skill-spec`, `skill-structural-gate`, `skill-create`). Restating gate routes here created drift — two places to update when a gate's behavior changed. Cross-links via the 10-step table are the single source of truth.

## Future possibilities

Non-binding sketches per RFC 2561.

### F1 — Phase 2 wiring

**Status (v5.19.4)**: partially shipped. `skill-critic` (step 5) is now active. `skill-optimize` (step 6), `skill-verify` (step 7), and `cousin-prompt` (step 9) remain `lifecycle: deferred` pending a CEO-committee decision on priority. The deferred trio is a bigger multi-session design effort and intentionally stays off the active path until justified by telemetry.
**Promotion trigger**: any of the three deferred steps becomes a candidate for Phase 2 wave 2 once (a) the critic's axes show a consistent blind-spot that the missing step would catch, OR (b) skill-improve FIX rate stays >20% over a calendar month (suggests the upstream gate needs hardening).

### F2 — Parallel sibling-batch execution

**Trigger**: median batch wall-clock > 10 min.
**Sketch**: for batches of N independent skills, parallelize within fanout cap 5; synchronize at batch-report assembly.

### F3 — Live progress streaming

**Trigger**: CEO requests real-time progress.
**Sketch**: stream per-skill verdicts to `_meta-runtime/batch-progress.jsonl`; batch-report still produced atomically at end.

## Grounding

- **Single-checkpoint reduction.**
  > **Cognition Labs "Closing the agent loop"**: *"the human's job narrows to decisions requiring judgment like architecture and product direction; everything mechanical gets caught and fixed before review."*
  Adopted: one CEO bulk decision per batch, not per skill. https://cognition.ai/blog/closing-the-agent-loop-devin-autofixes-review-comments

- **Pipeline as controlled set.**
  > **Backstage Software Templates §`spec.steps[]`**: *"templates define an ordered list of steps with `if:` directives and typed inputs."*
  Adopted as the 10-step SOP shape. https://backstage.io/docs/features/software-templates/writing-templates

- **Mistake-prevention vs defect-inspection.**
  > **Shingo Institute on mistake-proofing**: *"Mistakes are inevitable, but defects (mistakes that reach the customer) are preventable through poka-yoke."*
  Gates 1-3 + 8 + 10 are the structural poka-yokes. https://shingo.org/mistake-proofing-mistakes/

- **Compose existing scripts; do not reinvent.**
  > **`bin/catalog_gen.py` post-hook pattern**: the factory chains `bin/kiho_rdeps.py`, `skill-spec/dry_run.py`, `skill-structural-gate/run_gate.py` — no script rewrites.
