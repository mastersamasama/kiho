---
name: skill-critic
description: Use this skill to score a SKILL.md draft on eight deterministic quality axes (description, body length, structure, examples, anti-patterns, frontmatter completeness, capability validity, topic-tag validity). Returns a JSON report with per-axis scores, overall weighted score, and pass/fail against a threshold. Invoked as Step 5 of the skill-factory SOP during Phase 2, or standalone for ad-hoc quality checks before submitting a draft. Triggers on "critique this skill", "score skill quality", "skill-critic", or when skill-factory needs the Step 5 rubric verdict.
version: 1.0.0
lifecycle: active
metadata:
  trust-tier: T3
  kiho:
    capability: evaluate
    topic_tags: [validation, authoring]
    data_classes: ["skill-definitions", "skill-critic-verdicts"]
---
# skill-critic

Deterministic quality rubric for SKILL.md drafts. Emits a weighted score across 8 axes so the factory (and authors) can catch low-quality drafts before shipping. Read-only — never mutates the target.

## Contents
- [Scope](#scope)
- [Inputs](#inputs)
- [Axes and weights](#axes-and-weights)
- [Invocation](#invocation)
- [Verdict semantics](#verdict-semantics)
- [Response shape](#response-shape)
- [Integration with skill-factory](#integration-with-skill-factory)
- [Anti-patterns](#anti-patterns)

## Scope

skill-critic is the **Step 5 gate** in the `skill-factory` 10-step SOP. It is the highest-leverage Phase 2 gate — per the Anthropic grader/comparator/analyzer pattern, a content-quality grader catches most authoring defects that pass the structural gate (Steps 2-3) but would embarrass the catalog. Skills with overall score < 0.80 are marked **yellow** in the factory verdict; skills with structural hard-fail (no H1, empty body) are marked **red**.

The rubric is deterministic by design. No LLM calls, no nondeterminism. The axes are ported from `references/skill-authoring-standards.md` (v5.15.2 rules) plus the closed vocabularies `capability-taxonomy.md` and `topic-vocabulary.md`. If the vocabulary files are unreadable, the vocab-dependent axes skip gracefully (score 1.0, detail `"axis skipped"`) rather than crash.

## Inputs

```
skill_path: <absolute path to a SKILL.md file>
plugin_root: <path to the kiho-plugin root; default cwd> (optional)
threshold: <overall-score threshold; default 0.80> (optional)
```

## Axes and weights

Eight axes sum to weight 1.00. Per-axis score is a float in [0.0, 1.0]; the overall score is the weight-normalized average.

| Axis | Weight | What it checks |
|---|---|---|
| 1. description_quality | 0.20 | length 50-1024; third-person tone; ≥3 trigger-phrase hints |
| 2. body_length | 0.05 | under 500 lines (warn at 400-499; fail at ≥500) |
| 3. structure | 0.15 | has H1; at least 1 H2 (full credit at 3+ H2s) |
| 4. examples | 0.15 | at least one fenced code block AND/OR an "Example" heading |
| 5. anti_patterns | 0.15 | explicit Anti-patterns / Do not / Avoid / Never section |
| 6. frontmatter_completeness | 0.15 | name + description required; kiho.capability + topic_tags + data_classes recommended |
| 7. capability_valid | 0.05 | declared `metadata.kiho.capability` is in the closed 8-verb set |
| 8. topic_tags_valid | 0.10 | all declared `topic_tags` are in the controlled 18-tag vocabulary |

Axis-level rationale and edge cases are in `references/rubric.md`.

## Invocation

### Standalone (ad-hoc quality check)

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/_meta/skill-critic/scripts/critic_score.py \
    --skill-path <path-to-SKILL.md> \
    --plugin-root ${CLAUDE_PLUGIN_ROOT} \
    [--threshold 0.80]
```

### Via skill-factory (Phase 2)

`bin/skill_factory.py` invokes `critic_score.py` with `--plugin-root=${CLAUDE_PLUGIN_ROOT}` and the draft `SKILL.md` path. The factory reads the JSON report, merges the overall score into the per-skill verdict, and maps:

- `pass: true` + `status: ok` → green contribution
- `pass: false` + `status: ok` → yellow contribution
- `status: hard_fail` → red (factory short-circuits subsequent steps for this skill)

## Verdict semantics

The rubric is **advisory** on composition (description tone, examples) and **strict** on structure (no H1 + empty body = hard_fail). The threshold parameter controls the pass/fail cutoff but does not change the hard-fail rule.

- **Score ≥ threshold AND status=ok** → pass
- **Score < threshold AND status=ok** → fail (yellow in factory)
- **status=hard_fail** → fail (red in factory; overrides threshold)

Hard-fail triggers:
- No H1 heading anywhere in the body
- Body is effectively empty (< 20 newline-separated lines after frontmatter)

## Response shape

```json
{
  "status": "ok | hard_fail | malformed",
  "skill_path": "<path>",
  "overall_score": 0.955,
  "threshold": 0.80,
  "pass": true,
  "axes": {
    "description_quality": {"score": 1.0, "weight": 0.20, "detail": "length=448 (ok=True); tone_ok=True; trigger_hints=3/3"},
    "body_length": {"score": 1.0, "weight": 0.05, "detail": "lines=230 (threshold 500)"},
    "structure": {"score": 1.0, "weight": 0.15, "detail": "h1=True; h2_count=12"},
    "examples": {"score": 0.7, "weight": 0.15, "detail": "code_fence_pairs=7; example_heading=False"},
    "anti_patterns": {"score": 1.0, "weight": 0.15, "detail": "anti_patterns_heading=present"},
    "frontmatter_completeness": {"score": 1.0, "weight": 0.15, "detail": "name=True; description=True; capability=True; topic_tags=True; data_classes=True"},
    "capability_valid": {"score": 1.0, "weight": 0.05, "detail": "capability='create'; valid=True"},
    "topic_tags_valid": {"score": 1.0, "weight": 0.10, "detail": "declared=['ingestion']; invalid=[]"}
  },
  "warnings": ["examples: code_fence_pairs=7; example_heading=False"]
}
```

Exit codes (v5.15.2 convention):
- 0 — scored successfully (pass or fail both exit 0; reader checks `pass`)
- 1 — malformed or hard_fail (factory short-circuits to red)
- 2 — usage error (bad args, unreadable --skill-path)
- 3 — internal error (unexpected exception; report as kiho bug)

## Integration with skill-factory

skill-factory `bin/skill_factory.py` Step 5 will (during Phase 2 wiring):

1. For each `SKILL.md` under batch, invoke `critic_score.py --skill-path <path>`.
2. Parse the returned JSON.
3. Merge the per-skill `pass` + `status` into the verdict with the following rule:
   - All prior steps green + critic `pass: true` + `status: ok` → verdict stays green.
   - Critic `pass: false` + `status: ok` → demote verdict to yellow.
   - Critic `status: hard_fail` → demote verdict to red; do not run Steps 6-10 for this skill.
4. Include the critic JSON report in the batch-report under `_meta-runtime/batch-report-<id>.md` for CEO review.

Steps 6 (skill-optimize), 7 (skill-verify), 9 (cousin-prompt) remain `lifecycle: deferred` until a separate committee vote promotes them.

## Anti-patterns

- **Never use skill-critic output to auto-reject skills.** The score is advisory; CEO (or user, via factory batch report) makes the ship/defer call.
- **Never treat a perfect 1.0 as license to skip manual review.** The rubric catches common defects; it does not test for correctness, trigger coverage, or contract fidelity.
- **Never rewrite the target skill from within critic_score.py.** The critic is read-only. If a draft fails, route through skill-improve (the FIX operation), not the critic.
- **Never add new axes without updating `references/rubric.md` first.** Axis weights sum to 1.00; adding an axis requires re-normalizing every weight and re-running parity on the 45-skill catalog.
- **Never hard-code vocabulary.** The critic reads `capability-taxonomy.md` and `topic-vocabulary.md` at runtime so a committee vote to extend either file takes effect without editing the critic script.
