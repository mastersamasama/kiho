---
name: skill-parity
description: Cross-sibling structural-diff gate that enforces layout consistency across kiho skills inside the same domain. For every skill regeneration, computes a structural fingerprint (frontmatter shape, references/ files, scripts/ files, body section headings) and diffs against the canonical layout for that domain (declared in references/canonical-layouts.md). Refuses regeneration when layout diverges from canonical without an explicit parity-exception frontmatter key with a one-line rationale. Used as Step 3 of the skill-factory pipeline. Triggers on "check sibling parity", "validate layout consistency", "diff against canonical layout", "parity audit", or invoked as a factory sub-step before a skill is generated or regenerated.
metadata:
  trust-tier: T3
  version: 1.1.0
  lifecycle: deprecated
  kiho:
    capability: evaluate
    topic_tags: [validation, lifecycle]
    deprecated: true
    deprecated-at: 2026-04-17
    data_classes: ["skill-definitions"]
    superseded-by: skill-structural-gate
---
# skill-parity — deprecated

> This skill has been deprecated. Use **`skill-structural-gate`** instead.
>
> Rationale: `skill-graph` and `skill-parity` are both factory pre-regen structural validators invoked back-to-back. Combining them into `skill-structural-gate` reduces ~200 lines of shared boilerplate (When to use, Non-Goals, Failure playbook) without changing semantics.
>
> Deprecated in version 1.1.0 on 2026-04-17 via the CLAUDE.md slim-and-consolidate initiative.

## Migration guidance

If you previously loaded `skill-parity`, switch to `skill-structural-gate`. The combined skill:

- Exposes the same `parity_diff.py` at `skills/_meta/skill-structural-gate/scripts/parity_diff.py` (unchanged behavior).
- Moves `references/canonical-layouts.md` to `skills/_meta/skill-structural-gate/references/canonical-layouts.md` (content unchanged).
- Adds `scripts/run_gate.py` that returns a merged graph + parity verdict in one JSON payload.
- Preserves all parity fingerprint axes (frontmatter keys, metadata.kiho keys, references files, scripts files, body headings) and all decision routes F–I.

Invocation translation:

```
# OLD
python skills/_meta/skill-parity/scripts/parity_diff.py --target <x> --mode pre-regen

# NEW (equivalent — same script, new location)
python skills/_meta/skill-structural-gate/scripts/parity_diff.py --target <x> --mode pre-regen

# NEW (combined graph + parity gate)
python skills/_meta/skill-structural-gate/scripts/run_gate.py --target <x> --mode pre-regen
```

The `parity-exception` semantics (explicit opt-out with one-line rationale logged to `_meta-runtime/parity-exceptions.md`) are unchanged in `skill-structural-gate`.

If you find yourself needing a specific capability that `skill-structural-gate` does not cover, open an issue with the CEO committee — re-activating a deprecated skill is an exceptional action and requires re-review.

## History

The pre-deprecation body remains in git history at version 1.0.0.
