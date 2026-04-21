---
name: skill-graph
description: Inbound dependency scanner and cross-file path-integrity checker for kiho skill regenerations. Pre-gate that runs BEFORE any skill is regenerated or deprecated. Wraps bin/kiho_rdeps.py for the forward-edge inbound-dep scan and adds a 4-anchor stale-path scan across CLAUDE.md, agents/*.md, README.md, and templates/*.md to catch references to renamed or moved files. Refuses to let downstream pipeline steps proceed if any inbound link would break, surfacing each broken link with file:line and a suggested fix. Used as Step 2 of the skill-factory pipeline. Triggers on "scan inbound deps", "check who depends on this skill", "validate path integrity", "graph audit before regen", or invoked as factory sub-step.
metadata:
  trust-tier: T3
  version: 1.1.0
  lifecycle: deprecated
  kiho:
    capability: evaluate
    topic_tags: [validation, observability]
    deprecated: true
    deprecated-at: 2026-04-17
    data_classes: ["skill-definitions"]
    superseded-by: skill-structural-gate
---
# skill-graph — deprecated

> This skill has been deprecated. Use **`skill-structural-gate`** instead.
>
> Rationale: `skill-graph` and `skill-parity` are both factory pre-regen structural validators invoked back-to-back. They share ~200 lines of boilerplate (When to use, Non-Goals, Failure playbook). Combining them into `skill-structural-gate` reduces authoring overhead without changing semantics.
>
> Deprecated in version 1.1.0 on 2026-04-17 via the CLAUDE.md slim-and-consolidate initiative.

## Migration guidance

If you previously loaded `skill-graph`, switch to `skill-structural-gate`. The combined skill:

- Exposes the same `graph_scan.py` at `skills/_meta/skill-structural-gate/scripts/graph_scan.py` (unchanged behavior).
- Adds `scripts/run_gate.py` that returns a merged graph + parity verdict in one JSON payload.
- Preserves all four anchor surfaces (CLAUDE.md, agents/*.md, README.md, templates/*.md) and all decision routes A–E.

Invocation translation:

```
# OLD
python skills/_meta/skill-graph/scripts/graph_scan.py --target <x> --mode pre-regen

# NEW (equivalent — same script, new location)
python skills/_meta/skill-structural-gate/scripts/graph_scan.py --target <x> --mode pre-regen

# NEW (combined graph + parity gate)
python skills/_meta/skill-structural-gate/scripts/run_gate.py --target <x> --mode pre-regen
```

If you find yourself needing a specific capability that `skill-structural-gate` does not cover, open an issue with the CEO committee — re-activating a deprecated skill is an exceptional action and requires re-review.

## History

The pre-deprecation body is preserved at `versions/v1.0.0.md` for reference if ever archived; the v1.0.0 body remains in git history.
