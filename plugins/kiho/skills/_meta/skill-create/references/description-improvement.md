# Description iterative improvement (skill-create Step 4)

The `description` field is load-bearing — it's the only trigger signal Claude has at the router. When Gate 2 fails, do NOT manually guess at fixes. Run the two-phase improvement workflow.

## Contents
- [Two-phase workflow overview](#two-phase-workflow-overview)
- [Phase 1: binary 8-rule gate](#phase-1-binary-8-rule-gate)
- [Phase 2: train/test iterative rewriter (v5.13)](#phase-2-traintest-iterative-rewriter-v513)
- [The 8 effectiveness rules](#the-8-effectiveness-rules)
- [Rule 3 semantics (pushy language)](#rule-3-semantics-pushy-language)
- [Blind comparison and overfitting detection](#blind-comparison-and-overfitting-detection)
- [Loop procedure](#loop-procedure)
- [Using score_description.py](#using-score_descriptionpy)
- [Revision playbook](#revision-playbook)
- [Worked example](#worked-example)
- [Abort conditions](#abort-conditions)

## Two-phase workflow overview

The binary 8-rule scorer is cheap and catches obvious failures (missing trigger phrases, wrong voice, vague verbs). The train/test rewriter is expensive and catches the harder case where rules pass but actual triggering accuracy is still low. **Run them in that order** — don't invoke the expensive rewriter on a description that fails the binary gate.

```
draft description
    │
    ▼
Phase 1 — score_description.py  (fast, deterministic, 8 binary rules)
    │
    ├── score < 0.85  →  revise failed rules  →  re-score  (max 3 iterations)
    │                                                    │
    │                                                    └── still fails → abort: description_irrecoverable
    │
    └── score ≥ 0.85
        │
        ▼
Phase 2 — improve_description.py  (slow, iterative, train/test simulation)
    │
    ├── generate 20-prompt corpus (10 should-trigger + 10 should-not)
    ├── split 60/40 train/test (deterministic seed)
    ├── loop: score on train, rewrite from train failures, re-score
    │        (max 5 iterations, blind to test set)
    └── final train ≥ 0.90  AND  final test ≥ 0.75  →  ship
                                                   │
                                                   └── otherwise → abort or revise intent
```

This is what Anthropic's official `skill-creator` skill does. Source: the `improve_description.py` script in the `anthropics/skills` repo.

## Phase 1: binary 8-rule gate

Fast deterministic filter. Described in detail below under "The 8 effectiveness rules". Invoked via:

```bash
python skills/_meta/skill-create/scripts/score_description.py "<description>"
```

Exit 0 on pass (score ≥ 0.85), exit 1 on fail with diagnoses printed. Use it as a pre-filter; anything that fails here will definitely fail the more expensive Phase 2.

## Phase 2: train/test iterative rewriter (v5.13)

Grounded in Anthropic's Jan 2026 update to `improve_description.py` which added **blind comparisons** (the optimizer doesn't see the test set, learning only from the train split).

**Procedure:**

1. **Generate the 20-prompt corpus** via `scripts/generate_triggering_tests.py`. This produces 10 should-trigger prompts (varied natural phrasings of the skill's use cases) and 10 should-not-trigger prompts (superficially similar but out of scope).

2. **Split 60/40 deterministically.** The seed is derived from `sha256(intent + draft)[:8]` so re-runs produce the same split. This matters: if the split drifts between iterations, train/test accuracy numbers become uninterpretable.

3. **Score the current description on BOTH sets**, but only reveal train-set failures to the rewriter. The test set is held out.

4. **Rewrite based on train failures only.** Two edit patterns:
   - Missing trigger (`expected: trigger, actual: miss`): extract content words from the failed prompt, append as trigger hints: `"... Also triggers when the user mentions X, Y, Z."`
   - False positive (`expected: no_trigger, actual: false_positive`): append a disclaimer: `"... Does NOT handle A or B."`

5. **Re-score and track the train/test gap.** If train accuracy climbs but test accuracy lags (gap > 0.20), flag `overfitting_warning: true`. This is a signal that the rewriter is memorizing train prompts rather than generalizing.

6. **Stop conditions:** train accuracy ≥ 0.90 OR max 5 iterations OR char limit nearly hit.

7. **Ship criterion:** final test accuracy ≥ 0.75.

```bash
python skills/_meta/skill-create/scripts/improve_description.py <input.json>
```

Input JSON schema:

```json
{
  "draft_description": "...",
  "intent": "...",
  "use_cases": ["...", "..."],
  "trigger_phrases": ["...", "..."],
  "test_corpus": {
    "should_trigger":     ["...", "..."],
    "should_not_trigger": ["...", "..."]
  }
}
```

Output JSON:

```json
{
  "final_description": "...",
  "train_accuracy": 0.92,
  "test_accuracy": 0.88,
  "train_test_gap": 0.04,
  "overfitting_warning": false,
  "iteration_count": 2,
  "stopped_at": "train_accuracy_reached",
  "passed_ship_threshold": true,
  "history": [ ... ]
}
```

## The 8 effectiveness rules

Each rule is binary. Score = count of passes / 8. Pass threshold is 0.85 (7/8).

| # | Rule | Pass criterion |
|---|---|---|
| 1 | Concrete actions | At least 5 distinct concrete verbs (extract, merge, validate, generate, ...). Not vague verbs. |
| 2 | Trigger phrases | Contains at least one explicit trigger phrase — "if the user X", "when the user Y", "use when Z", "triggers on W" |
| 3 | **Pushy language** | Uses modal adverbs in trigger phrasing: "whenever", "must", "always", "make sure to use". **NOT** a requirement for imperative verbs — see rule 3 semantics below. |
| 4 | Third person | No first-person pronouns (I, me, my, we, our) and no second-person pronouns (you, your) |
| 5 | Single paragraph | No blank lines within the description (no `\n\n`) |
| 6 | Length | Between 50 and 1024 characters |
| 7 | No vague verbs | Does NOT contain handle, manage, process, work with, deal with, take care of, help with |
| 8 | No meta-commentary | Does NOT contain "this skill is designed to", "this skill helps", "this skill allows" |

## Rule 3 semantics (pushy language)

"Pushy" here means **modal adverbs + direct trigger phrasing**, NOT imperative verbs. The rule is about making the triggering condition unambiguous to the router, not about the grammatical mood of the sentence. Rule 3 is compatible with Rule 4 (third person) — they compose rather than conflict.

**Good examples (pass Rule 3 AND Rule 4):**
- "Use this skill whenever the user mentions PDFs..."
- "Must trigger when the user asks to extract text..."
- "Always invoke when the user wants to fill a form..."

Note: "the user" is the grammatical subject, not "you". These are all third-person.

**Anti-examples (fail):**
- "Extract text from PDFs" — imperative verb, no trigger signal, fails Rule 3
- "You can extract text" — second person, fails Rule 4
- "Can be useful for PDFs" — hedged, not pushy, fails Rule 3

## Blind comparison and overfitting detection

The Phase 2 rewriter NEVER sees the test set. It only receives `train_failures` — the prompts in the train split that the current description got wrong. This is the "blind comparison" pattern added to Anthropic's `improve_description.py` in its March 2026 update.

**Why blind comparison matters.** If the rewriter sees all 20 prompts and rewrites based on all failures, it can memorize the exact prompt wordings. The test set stops being an independent measurement of generalization — it just measures memorization.

**Overfitting signal:** a large `train_test_gap` (> 0.20) after the final iteration. The rewriter is getting train failures right while test failures persist. Action: manually sharpen the intent and re-run, because the rewriter has locally optimized against train prompts but the description still can't generalize.

**Ship threshold:** test accuracy ≥ 0.75 AND overfitting_warning == false. If the rewriter produces test accuracy ≥ 0.75 but with overfitting_warning, accept cautiously and note it in the audit block — the description may need human review.

## Loop procedure

1. **Score** the current draft description using `scripts/score_description.py`.
2. **If score ≥ 0.85**: accept. Record `iterative_description_score` and `iterative_description_loops` in the audit block. Proceed to Step 5 (body draft).
3. **Otherwise**: the script outputs a `diagnoses` array with one entry per failed rule. Read them in order.
4. **Rewrite** the description to address the failed rules specifically. Preserve passing elements. Do NOT rewrite from scratch — revise only what's failing.
5. **Re-score.** If still below threshold, loop. **Max 3 iterations.**
6. **If 3 iterations fail**, abort with `status: description_irrecoverable`. The underlying intent is too vague to be a discrete skill. Escalate to the caller.

This loop catches undertrigger at creation time, not during a real task.

## Using score_description.py

```bash
# Score a literal description
python skills/_meta/skill-create/scripts/score_description.py \
  "Use this skill whenever the user wants to extract, merge, split, rotate, or fill PDF forms. If the user mentions .pdf, use this skill."

# Score from a file
python skills/_meta/skill-create/scripts/score_description.py /tmp/draft-description.txt

# Score from stdin
echo "..." | python skills/_meta/skill-create/scripts/score_description.py -
```

Output is JSON:

```json
{
  "score": 0.75,
  "threshold": 0.85,
  "passed": false,
  "rule_count": 8,
  "rules_passed": 6,
  "results": {
    "r1_concrete_actions": true,
    "r2_trigger_phrases": true,
    "r3_pushy_language": false,
    ...
  },
  "diagnoses": [
    "r3_pushy_language: no pushy language; use 'whenever', 'must', 'always', 'make sure to use', or 'must invoke'",
    "r7_no_vague_verbs: vague verbs detected: ['process']; replace with concrete actions"
  ],
  "description_length": 187
}
```

Exit code is 0 on pass, 1 on fail, 2 on usage error.

## Revision playbook

Map each failure mode to a concrete revision pattern:

| Failed rule | Revision pattern |
|---|---|
| r1_concrete_actions | Add 3–5 more verbs from the use case list. "processing documents" → "extracting text, merging PDFs, rotating pages" |
| r2_trigger_phrases | Add `If the user <triggers>, use this skill.` at the end |
| r3_pushy_language | Replace "can be used for X" with "Use this skill whenever X". Replace "useful when Y" with "Must trigger when Y" |
| r4_third_person | Replace "I can..." / "You can..." with direct action verbs. "I help extract" → "Extracts" |
| r5_single_paragraph | Collapse blank lines. Use semicolons or commas instead |
| r6_length | Too short: add use cases + trigger phrases. Too long: remove meta-commentary and vague qualifiers |
| r7_no_vague_verbs | Replace "handle X" with specific verbs. "handle PDFs" → "extract, merge, split, rotate, encrypt PDFs" |
| r8_no_meta_commentary | Delete "This skill is designed to...", "The purpose of...", "This skill helps..." — start with the action verbs directly |

## Worked example

**Draft 1:**
> "This skill helps you work with PDF files. It can handle various document operations."

```
score: 0.25
diagnoses:
  - r1_concrete_actions: only 0 distinct action verbs (need >= 5)
  - r2_trigger_phrases: no explicit trigger phrase
  - r3_pushy_language: no pushy language
  - r4_third_person: wrong voice — second-person: ['you']
  - r7_no_vague_verbs: vague verbs detected: ['work with', 'handle']
  - r8_no_meta_commentary: meta-commentary detected
```

**Draft 2** (addressing all 6 failures):
> "Extracts text, merges, splits, rotates, and encrypts PDF files. Also fills forms, adds watermarks, and generates new PDFs from scratch."

```
score: 0.625
diagnoses:
  - r2_trigger_phrases: no explicit trigger phrase
  - r3_pushy_language: no pushy language
  - r6_length: length 142 is OK, but fails other checks
```

Wait — length is fine, but we're still missing trigger phrases and pushy language.

**Draft 3** (adding triggers + pushy language):
> "Extracts text, merges, splits, rotates, and encrypts PDF files. Also fills forms, adds watermarks, and generates new PDFs. Use this skill whenever the user mentions .pdf files or asks to produce one — make sure to invoke even if the user doesn't use the literal word 'PDF'."

```
score: 1.0
passed: true
```

Total iterations: 2 revisions, 3 scoring runs. Well under the max-3 cap.

## Abort conditions

If after 3 revisions the score is still below 0.85, the skill intent is probably one of:

- **Too vague** — the skill doesn't have a clear domain. Fix: sharpen the intent in Step 1 (Intake) and start over.
- **Too broad** — the description can't enumerate concrete actions because the skill does too many things. Fix: split into multiple narrower skills.
- **Too narrow** — the skill is really just a single tool call. Fix: delete the skill and use the tool directly.

In any of these cases, return `status: description_irrecoverable` with the final draft and diagnoses. The caller (usually design-agent Step 4d) must decide whether to reclassify the gap as Unfillable or adjust the candidate agent's soul to not depend on the problematic skill.
