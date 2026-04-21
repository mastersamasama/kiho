---
name: skill-architect
description: Reads raw user intent (free-form natural language) and proposes a complete validated skill_spec struct with per-field rationales for review at the user-confirmation step, before any artifact is generated. Closes the v5.17 factory's intake gap by deriving structural choices (capability, topic_tags, scripts_required, references_required, parity_layout, parent_domain) from intent rather than requiring the user to declare them up front. Implements the deterministic Step A signal extraction + Step B decision-tree proposal + Step C sibling pattern observation + optional Step D LLM critic refinement; output flows into Step E user confirmation, then handoff to skill-spec at Step 1 of the factory pipeline. Triggers on "what should my new skill look like", "propose a spec for", "architect this intent", "skill factory --from-intent", or invoked as Step 0 of the orchestrator before skill-spec dry-run.
metadata:
  trust-tier: T3
  version: 1.1.0
  lifecycle: deprecated
  kiho:
    capability: evaluate
    topic_tags: [authoring, validation]
    deprecated: true
    deprecated-at: 2026-04-17
    data_classes: ["skill-skeletons"]
    superseded-by: skill-intake
---

> **v5.20 deprecation notice.** Superseded by `skill-intake` (sk-053), which folds the former architect + spec seam into a single pre-intake pass. This skill remains for one release for in-flight invocations; new authors should route through `skill-intake`.

# skill-architect — deprecated

> This skill has been deprecated. Use **`skill-spec --from-intent`** instead.
>
> Rationale: `skill-architect` (Step 0 intent→spec) and `skill-spec` (Step 1 validate declared spec) had a thin boundary — architect already self-validated at Step E. Merging them into `skill-spec` with two modes (`--from-intent` and `--validate`) removes the "two places for spec logic" authoring drift without changing semantics.
>
> Deprecated in version 1.1.0 on 2026-04-17 via the CLAUDE.md slim-and-consolidate initiative.

## Migration guidance

If you previously invoked `skill-architect`, switch to `skill-spec --from-intent`. The combined skill:

- Exposes the same 4 scripts at `skills/_meta/skill-spec/scripts/{extract_signals,propose_spec,observe_siblings,render_proposal}.py` (content unchanged).
- Moves the critic subagent to `skills/_meta/skill-spec/agents/critic.md` (content unchanged).
- Moves references to `skills/_meta/skill-spec/references/{signal-taxonomy,intent-to-structure-rules}.md` (content unchanged).
- Preserves all 6 sub-steps (A extract → B propose → C observe → D critic → E confirm → F handoff), all 7 decision routes (G–M in the merged playbook), and the non-bypassable Step E user confirmation.

Invocation translation:

```
# OLD
python bin/skill_factory.py --from-intent "<text>"
# (internally dispatched to skill-architect Step 0)

# NEW — same CLI, internally dispatches to skill-spec --from-intent mode
python bin/skill_factory.py --from-intent "<text>"
```

The factory's `--from-intent` flag is unchanged; only the internal script paths (`EXTRACT_SIGNALS_SCRIPT`, `PROPOSE_SPEC_SCRIPT`, `OBSERVE_SIBLINGS_SCRIPT`) now point at `skills/_meta/skill-spec/scripts/` instead of `skills/_meta/skill-architect/scripts/`.

Subagent dispatch: critic is now `skill-spec-critic` (was `skill-architect-critic`). If you have tooling that spawns the critic directly by subagent_type, update the type string.

If you find yourself needing a specific capability that `skill-spec --from-intent` does not cover, open an issue with the CEO committee — re-activating a deprecated skill is an exceptional action and requires re-review.

## History

The pre-deprecation body remains in git history at version 1.0.0.
