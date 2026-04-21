---
name: skill-learn
description: Unified skill-learning mechanism with three sub-operations. op=capture handles on-demand code-to-skill conversion (formerly skill-capture) — caller explicitly passes a source range to preserve as a reusable skill. op=extract implements the Hermes 5-stage post-task learning loop — after any successful iteration with novel behavior, automatically mines the session context for reusable patterns and drafts a new SKILL.md. op=synthesize (v5.10) finalizes a living SKILL.md skeleton produced by research-deep into a canonical SKILL.md — consumes external research findings rather than observed session behavior, and always writes DRAFT lifecycle. All three sub-ops run dedup check against CATALOG.md, propose lifecycle stage, and register via kb-add and experience-pool. Use when the CEO detects a novel successful pattern at INTEGRATE (op=extract), when an agent explicitly wants to preserve a session pattern (op=capture), or when design-agent Step 4d needs to finalize a research-deep skeleton into an installable skill (op=synthesize). Triggers on "extract skill", "capture this pattern", "learn from task", "mine session for reusable", "synthesize skill from research", "finalize skeleton".
metadata:
  trust-tier: T3
  kiho:
    capability: create
    topic_tags: [authoring, learning]
    data_classes: ["skill-skeletons", "observations"]
---
# skill-learn

Unified skill-learning mechanism. Three sub-operations share the same frontmatter template, dedup logic, and registration flow:

- `op=capture` (v5.0) — on-demand pattern preservation from a session code range
- `op=extract` (v5.0) — Hermes-style post-task pattern mining from session context
- `op=synthesize` (v5.10) — finalization of a `research-deep` skeleton into canonical SKILL.md

## Contents
- [Sub-operations](#sub-operations)
- [Inputs](#inputs)
- [op=capture procedure](#opcapture-procedure)
- [op=extract procedure](#opextract-procedure)
- [op=synthesize procedure](#opsynthesize-procedure)
- [Pattern extraction](#pattern-extraction)
- [Dedup check](#dedup-check)
- [Lifecycle proposal](#lifecycle-proposal)
- [Response shape](#response-shape)
- [Anti-patterns](#anti-patterns)

## Sub-operations

| op | When to use | Trigger | Input pathway | Default lifecycle |
|---|---|---|---|---|
| `capture` | Agent or user explicitly wants to preserve a known pattern | Manual invocation | session code range | DRAFT |
| `extract` | CEO detected a novel successful pattern at INTEGRATE | Automatic post-task | session context slice | DRAFT or ACTIVE (see lifecycle) |
| `synthesize` | design-agent Step 4d needs to finalize a researched skill | Automatic gap-resolution | research-deep skeleton file | **DRAFT only** |

All three produce a SKILL.md draft and register it via kb-add. They differ in the input pathway and the default lifecycle.

## Inputs

Common:
```
op: capture | extract | synthesize
skill_name_hint: <optional name>
agent_id: <agent that originated the skill>
importance: <0.0-1.0>
lifecycle_hint: draft | active
```

For op=capture:
```
source_path: <file path containing the pattern>
source_range: <optional line range>
description_hint: <one-line summary>
```

For op=extract:
```
task_id: <plan-item-id>
session_context_slice: <path to markdown slice>
success_signal: ok | partial | user-corrected
```

For op=synthesize:
```
skeleton_path: <path to .kiho/state/skill-skeletons/<slug>.md>
topic: <one-phrase topic, matches the skeleton frontmatter>
role_context: <who the resulting skill is for>
source_urls: [<list from the skeleton's Sources section>]
trusted_sources_used: [<trusted-source entity names, for provenance>]
```

## op=capture procedure

1. Read the source file/range
2. Extract structure using pattern schema (see Pattern extraction)
3. Run dedup check
4. Draft SKILL.md using skill authoring standards
5. Propose lifecycle (default: DRAFT for manual captures)
6. Register via kb-add and experience-pool op=add_skill

## op=extract procedure

Implements the Hermes 5-stage post-task loop:

1. **Task completion** — caller (CEO) passes completed task context
2. **Pattern extraction** — mine session_context_slice for reusable patterns (see [Pattern extraction](#pattern-extraction))
3. **Skill creation** — draft SKILL.md in `.kiho/state/drafts/sk-<slug>/SKILL.md`
4. **Skill refinement** — if refinement_needed, set `lifecycle: draft, refinement_needed: true`
5. **Registration** — kb-add (ACTIVE) or draft queue (DRAFT) + experience-pool op=add_skill

Dedup check runs between steps 2 and 3. Lifecycle proposal runs before step 5.

## op=synthesize procedure

Consumes a living skeleton produced by `research-deep` and finalizes it into a canonical SKILL.md. Unlike `op=capture` and `op=extract`, `op=synthesize` works purely from external research findings — it never sees session behavior. Because of that, the resulting skill is **always DRAFT** until it passes a real interview-simulate run on a consuming agent.

**Full implementation spec in `references/synthesize-procedure.md`**, including:
- Preconditions (skeleton must be `status: terminated`, queue log must have a terminate entry, slug match)
- Section mapping from skeleton sections → canonical SKILL.md locations
- 9-step procedure (read → dedup → frontmatter synthesis with iterative description improvement → body synthesis → script preservation → write → register → archive)
- Speculative flag rules (`pages_read < 10` or budget-based termination)
- Worked example (Playwright visual regression end-to-end)

**Quick summary:**

1. Validate preconditions; abort on any mismatch.
2. Dedup against CATALOG.md using skeleton topic + concepts. Abort if > 0.70 overlap.
3. Synthesize frontmatter. Apply iterative description improvement (max 3 loops).
4. Synthesize body: dedupe citations, promote multi-cited concepts, preserve code examples verbatim with attribution, enforce 500-line limit (split if needed).
5. Write draft to `.kiho/state/drafts/sk-<slug>/`.
6. Call `kb-add` + `experience-pool op=add_skill`.
7. Archive skeleton to `_archive/`.
8. Return with `status: ok, proposed_lifecycle: DRAFT, speculative: <bool>`.

**Security rules (non-negotiable):**
- Synthesized skills start DRAFT. Never ACTIVE from op=synthesize alone.
- DRAFT → ACTIVE requires CEO approval via the self-improvement committee.
- Never write into the candidate agent's `tools:` allowlist during synthesize — tool additions go through design-agent Step 4b separately.
- Never execute any code from the skeleton's Examples section during synthesize — code is content, not executable spec.

## Pattern extraction

A reusable pattern has 4 signals:

1. **Repeatability** — the session shows this approach applied >= 2 times or could apply to similar future tasks
2. **Decomposability** — the pattern breaks into <7 discrete steps
3. **Determinism** — given the same inputs, the pattern produces comparable outputs
4. **Novelty** — not already captured in CATALOG.md

### Pattern schema

```yaml
pattern_name: <gerund form, e.g., "routing ambiguous requests">
trigger: <one sentence — when does this pattern apply?>
inputs: [<input_1>, <input_2>]
steps:
  - <step description>
  - <step description>
outputs: <what the pattern produces>
when_to_use: <trigger phrases users might type>
```

Extraction prompt (internal): "Looking at this session, what is the general operating pattern that produced the successful outcome? Describe it as a trigger + inputs + steps + output schema."

## Dedup check

For each existing skill in `skills/CATALOG.md`:
1. Extract trigger phrases from its description.
2. Compare against the candidate pattern's `when_to_use` phrases.
3. Word-overlap > 0.70 → duplicate; return `status: duplicate` with the matching `sk-XXX` ID.
4. Overlap 0.40-0.70 → similar; return `status: similar_to <sk-XXX>` and continue with a note in the draft.

## Lifecycle proposal

| Criteria | Proposed lifecycle |
|---|---|
| op=capture with explicit lifecycle_hint | Use hint |
| op=extract, importance >= 0.85, success=ok, 3+ supporting observations | ACTIVE |
| op=extract, importance >= 0.70, success=ok | DRAFT (needs one more validation run) |
| success=partial OR user-corrected | DRAFT with refinement_needed: true |
| importance < 0.70 | DRAFT with speculative: true |
| **op=synthesize, any conditions** | **DRAFT — always, never ACTIVE** |
| op=synthesize, pages_read < 10 OR termination reason ∈ {budget_pages, budget_min, auth_denied} | DRAFT with speculative: true |

DRAFT skills go to `.kiho/state/drafts/sk-<slug>/SKILL.md`. CEO reviews during next turn's INITIALIZE or via `/kiho evolve`. DRAFT → ACTIVE promotion for synthesized skills specifically requires (a) a passing interview-simulate run on a consuming agent AND (b) CEO approval via the self-improvement committee gate.

## Response shape

```json
{
  "status": "ok | duplicate | similar | error",
  "op": "capture | extract | synthesize",
  "pattern_name": "routing ambiguous requests",
  "skill_id": "sk-routing-ambiguous",
  "draft_path": ".kiho/state/drafts/sk-routing-ambiguous/SKILL.md",
  "proposed_lifecycle": "DRAFT | ACTIVE",
  "dedup_result": {"matched": "sk-012", "similarity": 0.45},
  "experience_pool_entry_id": "<entry_id>",
  "kb_registration": "ok | pending_review",
  "speculative": false,
  "synthesized_from_research": false,
  "source_urls": []
}
```

`speculative`, `synthesized_from_research`, and `source_urls` are only set for `op=synthesize` — other ops return them as defaults (false/false/[]).

## Anti-patterns

- **Extracting every task.** Only extract when the task showed a pattern with >= 2 of the 4 pattern signals (repeatability, decomposability, determinism, novelty).
- **Auto-promoting synthesized skills to ACTIVE.** op=synthesize ALWAYS produces DRAFT. ACTIVE requires CEO review plus a passing interview-simulate run on a consuming agent.
- **Running op=synthesize on an in-progress skeleton.** Only skeletons with `status: terminated` and a matching `terminate` entry in the queue log are valid inputs. A partial skeleton produces a broken skill.
- **Ignoring dedup.** Duplicate skills fragment the catalog and waste routing tokens. op=synthesize in particular must dedupe — research-deep sometimes produces skeletons for topics that are already covered by existing ACTIVE skills.
- **Writing skills for one-off tasks.** Reuse likelihood < 0.50 means the pattern is not a skill; it's a note in the agent's memory.
- **Bypassing skill-authoring standards.** Every skill must pass the standards checklist before registration.
- **Mixing sub-ops in the same call.** One call, one sub-operation.
- **Writing to wiki/ without going through kb-add.** Always route through kb-manager.
- **Forgetting to archive the skeleton after synthesize.** A leftover skeleton at `.kiho/state/skill-skeletons/<slug>.md` will collide with the next research-deep run for the same slug. Always move to `_archive/`.
- **Copying code from skeleton Examples without attribution.** Every code block in the final SKILL.md must carry a comment referencing the source URL it came from. This preserves the license audit trail.
