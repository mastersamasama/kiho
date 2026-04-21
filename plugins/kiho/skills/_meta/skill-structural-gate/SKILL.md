---
name: skill-structural-gate
description: Combined structural-integrity gate for kiho skill regenerations. Runs inbound-dependency + 4-anchor stale-path scan (former skill-graph) and sibling layout fingerprint-diff against canonical layouts (former skill-parity) as a single pre-regen gate. Wraps bin/kiho_rdeps.py for forward-edge scans, adds stale-path scan across CLAUDE.md + agents/*.md + README.md + templates/*.md, and diffs per-domain canonical layouts declared in references/canonical-layouts.md. Refuses downstream pipeline steps when any check fails. Used as Steps 2+3 of the skill-factory pipeline. Triggers on "check inbound deps", "validate path integrity", "sibling parity", "layout divergence", "pre-regen gate", "deprecation-check", or invoked as factory sub-step.
metadata:
  trust-tier: T3
  version: 1.0.0
  lifecycle: active
  kiho:
    capability: evaluate
    topic_tags: [validation, lifecycle, observability]
    data_classes: ["skill-definitions", "gate-observations"]
    supersedes: [skill-graph, skill-parity]
---
# skill-structural-gate

Combined pre-regen structural-integrity gate. Merges the former `skill-graph` (inbound rdeps + 4-anchor stale-path scan) and `skill-parity` (structural fingerprint vs per-domain canonical layout) into a single skill. The factory's combined Steps 2+3 — every regeneration **MUST** pass this gate before any file write.

Two scans, two axes:
- **Graph axis**: inbound consumers + cross-file path integrity (the "who breaks if I change this?" question)
- **Parity axis**: layout fingerprint vs canonical sibling template (the "does this match what other skills in this domain look like?" question)

Both scans are deterministic, stdlib-only Python. Combined verdict comes from `scripts/run_gate.py`; individual scripts (`graph_scan.py`, `parity_diff.py`) remain independently invocable for finer-grained calls.

## When to use

Invoke this skill when:

- The factory orchestrator is about to write to a skill (Steps 2+3 pre-gate)
- A user asks "who depends on `skill-X`?" or "what would break if I rename this?"
- A `skill-deprecate` invocation needs the consumer list before posting the shim
- A `skill-improve` invocation needs the consumer list before proposing a body diff
- A reviewer wants to audit catalog-wide layout consistency
- A new skill author wants to confirm "what layout should my new `core/harness` skill have?"

Do **NOT** invoke this skill when:

- You want runtime invocation traces — `bin/session_context.py` parses session logs
- You want catalog confusability metrics — `bin/catalog_walk_audit.py` covers that
- You want to rewrite stale paths automatically — that is a future possibility; today the gate reports, `skill-improve` fixes
- You want pattern compliance (P1-P9) — that is `pattern_compliance_audit.py`
- You want content-quality grading — that is `skill-critic` (Phase 2)

## Non-Goals

- **Not a runtime cache.** Per `references/storage-architecture.md` Tier-1/2 discipline, every scan is computed fresh. No on-disk reverse index, no incremental cache. Forward edges are authoritative, reverse views are recomputed.
- **Not an auto-fixer.** Surfaces broken links and layout divergence with suggested fixes; rewrites are `skill-improve`'s job under its own gates.
- **Not a runtime resolver.** Validation happens at evolution time (regen, deprecation), not at invocation time. The main-agent harness does not call this skill before running a target.
- **Not a catalog validator.** That is `bin/catalog_walk_audit.py` + Gate 19. This skill checks per-target integrity, not catalog-wide health.
- **Not a content validator.** Layout = file shape, not file content. Body content quality is `skill-critic`'s job.
- **Not a fuzzy matcher.** Path matches are exact-string; layout matches are exact-fingerprint. Renames need explicit alias files or sequential rename-then-scan-then-rewrite passes.
- **Not a single-layout enforcer.** Per GEPA Pareto frontier discipline, canonical layout per domain **MAY** differ. Layouts live in `references/canonical-layouts.md`; the gate enforces per-domain, not global.
- **Not extensible without committee vote.** New canonical layouts require CEO-committee approval per v5.16 controlled-set discipline.

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are interpreted per BCP 14 (RFC 2119, RFC 8174).

## Inputs

```
target_skill:    <path to SKILL.md OR skill name OR skill_id>
mode:            pre-regen | catalog-audit | deprecation-check | rename-audit
new_path:        <optional — for rename-audit, the proposed new path>
exception_ok:    <bool, default false; when true, parity-exception frontmatter satisfies the parity axis>
```

The `run_gate.py` wrapper invokes both scans when `mode ∈ {pre-regen, catalog-audit}`; parity is skipped in `deprecation-check` and `rename-audit` (those only need the graph axis).

## Anchor surfaces (graph axis)

Four anchor surfaces where stale paths historically hide:

1. `CLAUDE.md` — top-level plugin instructions
2. `agents/*.md` — agent definitions (including `skills:` frontmatter arrays)
3. `README.md` — plugin readme
4. `templates/*.md` — templates referencing skill paths

Any of these containing a path that no longer resolves triggers Route C.

## Structural fingerprint (parity axis)

For each target:

```yaml
fingerprint:
  frontmatter_keys:           [<sorted list of top-level frontmatter keys>]
  metadata_kiho_keys:         [<sorted list of metadata.kiho.* keys>]
  references_files:           [<sorted list of references/*.md filenames>]
  scripts_files:              [<sorted list of scripts/*.py filenames>]
  has_config_yaml:            <bool>
  has_assets_dir:             <bool>
  body_section_headings:      [<sorted list of `## ` headings>]
```

Fingerprint is diffed against the per-domain canonical in `references/canonical-layouts.md`.

## Failure playbook

**Severity**: error (blocks regen).
**Impact**: orchestrator cannot proceed; factory steps 2+3 refuse to advance.
**Taxonomy**: dep | path | rename | unresolvable | layout-drift | unknown-domain | unauthorized-exception.

### Decision tree

```
structural-gate failure
    │
    ├─ graph axis
    │   ├─ target skill does not exist              → Route A (usage error)
    │   ├─ inbound hard requires non-empty          → Route B (refuse deprecation)
    │   ├─ stale path reference in 4 anchors        → Route C (surface; refuse regen)
    │   ├─ rename audit: new_path collides          → Route D (refuse; suggest alternate)
    │   └─ unresolvable wiki-link in target body    → Route E (warning; not a hard fail)
    │
    └─ parity axis
        ├─ unknown parent_domain                    → Route F (require canonical-layouts.md update)
        ├─ fingerprint diverges from canonical      → Route G (refuse; surface diff; suggest fix)
        ├─ parity-exception without rationale       → Route H (refuse; require one-line rationale)
        └─ parity-exception with rationale          → Route I (warn, log to parity-exceptions.md, allow)
```

### Graph-axis routes

**Route A — target missing**: verify path / name / id resolves to a real SKILL.md. Exit 1 with `status: target_not_found` + search paths checked.

**Route B — inbound hard requires (deprecation only)**: run `bin/kiho_rdeps.py <target>` to enumerate consumers. If any consumer's `metadata.kiho.requires` contains the target, refuse. Exit 1 with `status: consumers_block` + consumer list.

**Route C — stale path reference**: for each anchor surface, Grep for any path containing the target's directory or filename anchors. For each hit, output `file:line: <stale_reference>` + suggested replacement. Exit 1 with `status: stale_path_references` + list.

**Route D — rename collision**: if `mode: rename-audit` and `new_path` exists, refuse. Exit 1 with `status: rename_collision` + colliding path.

**Route E — unresolvable wiki-link in body**: scan target body for `[[wiki-links]]` and `skills/...` paths. For unresolved, emit warning (NOT hard fail). Exit 0 with `status: ok_with_warnings` + unresolvable list.

### Parity-axis routes

**Route F — unknown domain**: target's `parent_domain` has no canonical entry in `references/canonical-layouts.md`. Exit 1 with `status: unknown_domain`. Fix: add the new canonical via CEO-committee vote, then retry.

**Route G — layout divergence**: diff target's fingerprint against canonical for its domain. Surface diff (missing files, extra files, missing headings, extra headings). Exit 1 with `status: layout_divergence`. Suggested fix: add missing artifacts OR move extras to canonical location (e.g., `bin/<x>.py` → `<skill>/scripts/<x>.py`).

**Route H — unauthorized exception**: frontmatter has `parity_exception: true` or `parity_layout: parity-exception` but no rationale. Exit 1 with `status: unauthorized_exception`.

**Route I — authorized exception**: record in `_meta-runtime/parity-exceptions.md` with timestamp + rationale. Exit 0 with `status: ok_with_exception`. Periodic CEO-committee review prunes stale exceptions.

## Worked examples

### Example 1 — combined gate, all clean

Invocation: `python skills/_meta/skill-structural-gate/scripts/run_gate.py --target skills/core/harness/org-sync/SKILL.md --mode pre-regen`

Expected:

```json
{
  "status": "ok",
  "target": "skills/core/harness/org-sync/SKILL.md",
  "mode": "pre-regen",
  "graph": {
    "status": "ok",
    "payload": {
      "consumers": {"hard_requires": [], "soft_mentions": [], "anchor_references": ["..."]},
      "stale_path_findings": []
    }
  },
  "parity": {
    "status": "ok",
    "payload": {
      "domain": "core/harness",
      "canonical_layout": "meta-with-scripts",
      "diff": []
    }
  }
}
```

Result: factory Steps 2+3 PASS; orchestrator advances to Step 8 citation grep.

### Example 2 — stale path reference detected

After a hypothetical rename of `skills/kiho/` → `skills/core/harness/kiho/`:

```json
{
  "status": "fail",
  "graph": {
    "status": "stale_path_references",
    "payload": {
      "stale_path_findings": [
        {"file": "agents/kiho-ceo.md", "line": 54, "suggested": "skills/core/harness/kiho/config.toml"},
        {"file": "README.md", "line": 55, "suggested": "skills/core/harness/kiho/"}
      ]
    }
  },
  "parity": {"status": "ok"}
}
```

Result: exit 1. Orchestrator routes to `skill-improve` to fix the 4 stale references before regen proceeds.

### Example 3 — deprecation blocked by hard consumer

Invocation: `--target skills/_meta/skill-create/SKILL.md --mode deprecation-check`

Expected: exit 1, `status: consumers_block`, consumer list emitted. Parity axis skipped (mode not in `{pre-regen, catalog-audit}`). Factory refuses the deprecation.

### Example 4 — parity-exception with rationale

A skill that legitimately diverges (e.g., `skills/_meta/skill-find/` declared as `parity-exception: "single-purpose retrieval, no narrative reference needed"`):

Expected: `graph.status: ok`, `parity.status: ok_with_exception`. Log entry appended to `_meta-runtime/parity-exceptions.md`. Combined `status: ok`.

## Response shape

```json
{
  "status": "ok | fail | internal_error",
  "target": "<path>",
  "mode": "pre-regen | catalog-audit | deprecation-check | rename-audit",
  "graph": {
    "status": "ok | ok_with_warnings | target_not_found | consumers_block | stale_path_references | rename_collision",
    "payload": {"consumers": {}, "stale_path_findings": [], "warnings": []}
  },
  "parity": {
    "status": "ok | ok_with_exception | unknown_domain | layout_divergence | unauthorized_exception | skipped",
    "payload": {"domain": "", "canonical_layout": "", "fingerprint": {}, "diff": []}
  }
}
```

For backward-compat with the old individual invocations, `graph_scan.py` and `parity_diff.py` remain directly invocable and produce their original JSON shapes unchanged.

## Anti-patterns

- **MUST NOT** persist a reverse-index cache to disk. Per `references/storage-architecture.md` T2-MUST-1, any cache of reverse edges must be regenerable from Tier 1; the gate chooses the simpler option of no cache at all.
- **MUST NOT** auto-rewrite stale paths or auto-move layout divergences. Surface them; let `skill-improve` mutate under its own gates.
- **MUST NOT** silently skip any anchor surface. CLAUDE.md, agents/*.md, README.md, templates/*.md are *the* historical drift surfaces; skipping any one defeats the gate.
- **MUST NOT** force a single global layout across domains. Each domain has its canonical layout; GEPA Pareto frontier — diversity is intentional.
- **MUST NOT** allow parity-exception without a one-line rationale. Exceptions without rationale produce unaudited drift over time.
- **MUST NOT** check parity post-write. Pre-gate or no gate — post-write checks are inspection, not prevention (Shingo).
- Do not treat `Route E — unresolvable wiki-link` as a hard fail. Warnings only.
- Do not cache scan results between invocations within a single factory batch. Each scan is fresh; consistency over performance.
- Do not extend `references/canonical-layouts.md` without CEO-committee vote.

## Rejected alternatives

### A1 — Persisted reverse-dependency cache

**What it would look like.** SQLite or JSON cache mapping skill_id → consumers, refreshed on demand.

**Rejected because.** Reverse caches go stale. The kiho v5.15 H5 framing — `pnpm why`, `cargo tree --invert`, `bazel rdeps` all walk forward edges fresh — is the right discipline. Cache adds complexity for no gain at kiho's scale. (A Tier-3 on-demand sqlite FTS index built per-turn would be acceptable under the storage-architecture spec, but persistent reverse cache is not.)

### A2 — Auto-rewrite stale paths or auto-move divergent layouts inline

**What it would look like.** When the gate finds a stale path or a misplaced script, it rewrites the file directly.

**Rejected because.** File mutations **MUST** go through `skill-improve`'s gates (Step 0 consumer review, validation). Inline auto-rewrite skips those gates and produces silent edits with no audit trail.

### A3 — Embedding-based fuzzy layout matching

**What it would look like.** Compute embedding similarity between target body and canonical template; pass if cosine > 0.8.

**Rejected because.** Layouts are structural, not semantic. Two skills with identical layouts but completely different content should both pass; two with similar content but different layouts should both fail. Exact structural matching is deterministic; embedding fuzziness is the wrong tool.

### A4 — Catalog-wide single canonical layout

**What it would look like.** Force every skill to use the same layout.

**Rejected because.** Wastes tokens (empty references/ dirs), not every skill needs scripts. GEPA Pareto frontier explicitly maintains diverse winning candidates per axis.

### A5 — Lint-style warn-not-fail mode

**What it would look like.** Always exit 0; emit warnings; let the user decide.

**Rejected because.** Warnings without fail are inspection-after, not prevention. Shingo's mistake-vs-defect distinction: hard fail with parity-exception escape valve is the right balance.

### A6 — Keep skill-graph and skill-parity as two separate skills

**What it would look like.** Status quo pre-2026-04-17.

**Rejected because.** Both are Step-2/Step-3 pre-regen structural validators invoked back-to-back by the factory. They share `When to use`, `Non-Goals`, `Failure playbook` boilerplate (~200 dedupe lines). Single combined skill reduces authoring overhead without changing semantics. Backward compat preserved via deprecation shims on the old two names.

## Future possibilities

Non-binding sketches per RFC 2561.

### F1 — Auto-rewrite via `skill-improve` chain

**Trigger condition**: ≥ 5 reports of "the gate keeps surfacing the same stale paths after my regens".

**Sketch.** Emit a structured rewrite proposal; a follow-up `skill-improve --auto-fix-stale-paths` consumes it and applies under improve's normal gates.

### F2 — Layout migration playbook

**Trigger condition.** A canonical layout changes.

**Sketch.** `--migrate-from <old> --migrate-to <new>` produces a per-skill migration plan; consumed by `skill-improve` in batch.

### F3 — Inbound-graph visualization

**Trigger condition.** CEO requests visual dep graph.

**Sketch.** Optional `--render mermaid` flag emits Mermaid diagram.

### F4 — Auto-suggest layout from sibling consensus

**Trigger condition.** A new domain added with < 3 skills.

**Sketch.** Bootstrap canonical from majority-vote across first 3 skills; CEO-committee ratifies.

### F5 — Cross-plugin parity

**Trigger condition.** Other Claude Code plugins adopt kiho-style layouts.

**Sketch.** Optional `--cross-plugin` flag. Defer until cross-plugin federation in scope.

## Grounding

- **Forward-edge / compute-on-demand discipline.**
  > **kiho v5.15 H5**: *"reverse references in every mature ecosystem are computed on demand, not stored."*
  Adopted: the gate computes fresh on every invocation. https://github.com/karpathy/autoresearch

- **Pre-flight check before write.**
  > **Backstage Software Templates §`if:` step gating**: *"steps can be conditionally executed using `if:` directives that consume earlier-step output."*
  Adopted as factory Steps 2+3 hard gate: Step 4+ **MUST NOT** execute if this gate fails. https://backstage.io/docs/features/software-templates/writing-templates

- **Devin autofix architecture.**
  > **Cognition Labs blog "Closing the agent loop"**: *"linters/CI flag → bot comment → agent patches."*
  This gate plays the linter role; `skill-improve` plays the agent-patcher. https://cognition.ai/blog/closing-the-agent-loop-devin-autofixes-review-comments

- **Mistake-prevention discipline.**
  > **Shingo Institute on mistake-proofing**: *"Mistakes are inevitable, but defects (mistakes that reach the customer) are preventable through poka-yoke."*
  The gate IS the poka-yoke for broken-inbound-link + layout-drift defect classes. https://shingo.org/mistake-proofing-mistakes/

- **Pareto-frontier discipline.**
  > **GEPA paper (Agrawal et al. 2025)**: *"maintains a Pareto frontier of candidate prompts to avoid local optima — outperforms GRPO by 6-20% with up to 35× fewer rollouts."*
  Rationale for per-domain canonical layouts rather than global enforcement. https://arxiv.org/abs/2507.19457

- **Controlled-set discipline.**
  > **CLAUDE.md §Working concepts (capability taxonomy, topic vocabulary)**: closed vocabularies with committee-vote extension.
  Same applied to layouts: closed set in `references/canonical-layouts.md`, extensions via committee.
