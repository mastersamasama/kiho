# Gate 11 — Transcript review (skill-create v5.13)

New in v5.13. The 11th validation gate runs between Step 8 (security scan) and Step 9 (eval generation). It simulates 2–3 realistic invocations of the draft skill, captures the transcripts, and reviews them for correctness before the skill is registered.

## Contents
- [Why a transcript review gate](#why-a-transcript-review-gate)
- [Scope — Gate 11 vs design-agent Step 7](#scope--gate-11-vs-design-agent-step-7)
- [Inputs](#inputs)
- [Procedure](#procedure)
- [Review prompt template](#review-prompt-template)
- [Pass criteria](#pass-criteria)
- [Failure handling](#failure-handling)
- [Anti-patterns](#anti-patterns)

## Why a transcript review gate

Anthropic's Jan 2026 blog "Demystifying Evals for AI Agents" calls out transcript review as step 7 of their 8-step eval-driven development pattern. The rationale: **scores alone miss behavioral issues.** A skill can pass an 8-rule binary description check, a rubric mean ≥ 4.0, and a triggering accuracy test, yet still:

- Use the wrong tool for the right operation (e.g., grep instead of Glob)
- Silently swallow errors that the SKILL.md body documents should escalate
- Scope-creep into unrelated domains when a prompt hints at them
- Produce output that doesn't match the declared Response shape section

Transcript review catches these by reading what the skill *actually does*, not just what it scores on.

## Scope — Gate 11 vs design-agent Step 7

Two different things called "review the skill's behavior", easy to confuse:

| | Gate 11 (this reference) | design-agent Step 7 |
|---|---|---|
| Who runs it | `skill-create` as part of skill authoring | `design-agent` as part of agent creation |
| What's under test | The **skill in isolation** — draft loaded, spawned against scenarios | The **consuming agent** — its soul + skills + tools all exercised together |
| When it runs | Before the skill is registered (pre-DRAFT) | Before the agent is deployed (pre-register) |
| Pass criterion | 3 transcripts score ≥ 4/5 on correctness rubric | `rubric_avg ≥ 4.0, worst_dim ≥ 3.5, drift ≤ 0.20, refusal_robustness == 1.0` |
| Failure action | Return to Step 5 (body draft) in skill-create | Return to Step 2 (draft candidate soul) in design-agent |

Gate 11 does NOT replace design-agent Step 7. Both run: Gate 11 catches skill-level bugs before the skill enters CATALOG; Step 7 catches agent-level bugs before the agent ships. A skill that passes Gate 11 can still fail design-agent Step 7 if the consuming agent doesn't know how to use it correctly.

## Inputs

Gate 11 runs after Step 8 (security scan) with:

```
draft_path:        .kiho/state/drafts/sk-<slug>/SKILL.md
test_corpus:       output from generate_triggering_tests.py
                   (uses the 10 should-trigger prompts; 3 are selected for review)
rubric:            assets/canonical-rubric.toml from interview-simulate
scenario_count:    default 3 (minimum 2, maximum 5)
```

## Procedure

1. **Select scenarios.** Pick the 3 should-trigger prompts from the test corpus that have the widest spread of intent (use diversity heuristic: max pairwise Jaccard distance on content words).

2. **Spawn the draft skill** against each scenario. This is a one-shot spawn — load the draft SKILL.md as the system prompt, pass the scenario as the user message, collect the response + tool calls.

   Because the skill is still in DRAFT (not registered in CATALOG), this requires spawning via `Agent` with an inline system prompt rather than `subagent_type: <name>`. The spawn is **ephemeral** — no state persists to `.kiho/state/` and no ledger entry is written.

3. **Capture transcripts.** For each spawn, record:
   - The scenario (exact prompt text)
   - The full response
   - Every tool call with args
   - Whether the response matches the declared Response shape in the SKILL.md body
   - Wall-clock time

4. **Run the review prompt** (see template below) on each transcript. The review produces a 1–5 score on 4 correctness dimensions:
   - **Tool use correctness** — right tool for each operation, no unnecessary calls
   - **Error handling** — documented error cases handled as the body says
   - **Scope adherence** — no drift into unrelated domains
   - **Output shape match** — response matches declared Response shape

5. **Aggregate.** Compute per-transcript score = mean of 4 dimensions. Compute overall Gate 11 score = min of per-transcript scores (not mean — any single failing transcript triggers revision).

6. **Apply pass criteria** (see below). Write the review result to `.kiho/state/drafts/sk-<slug>/transcript-review.md` for lineage.

## Review prompt template

Run this prompt for each of the 3 transcripts. The prompt is deliberately blind to the skill's scoring self-assessment — it only reads the declared intent and the captured transcript.

```text
You are reviewing a transcript from a draft skill being validated by
skill-create Gate 11. Do NOT try to be agreeable. Identify real issues.

Skill intent (from frontmatter):
{{intent}}

Skill's declared Response shape section (from body):
{{response_shape_section}}

Scenario given to the skill:
{{scenario}}

Actual response:
{{response}}

Tool calls made:
{{tool_calls}}

Score each of the 4 dimensions 1-5:

1. Tool use correctness (1-5):
   Did the skill pick the right tool for each operation? Were there
   unnecessary tool calls? Did it use any tools not in its declared
   allowlist?

2. Error handling (1-5):
   If the scenario surfaced an error condition the body documents,
   did the skill handle it per documentation? Silent failure or
   uncaught exceptions score 1.

3. Scope adherence (1-5):
   Did the response stay within the skill's declared responsibilities?
   Any drift into unrelated domains (even plausible ones) scores 3 or
   lower. Staying on-scope scores 5.

4. Output shape match (1-5):
   Does the response match the declared Response shape section?
   Exact match scores 5; close-but-missing-fields scores 3-4; wrong
   shape scores 1-2.

For each score below 4, provide a one-sentence justification naming
the specific issue. Scores of 4 or 5 don't need justification.

Output JSON:
{
  "tool_use": <1-5>,
  "error_handling": <1-5>,
  "scope_adherence": <1-5>,
  "output_shape": <1-5>,
  "mean": <calculated>,
  "issues": ["<one line per failing dimension>"]
}
```

## Pass criteria

Gate 11 passes when **all** of:

1. **Every** transcript has `mean >= 4.0`
2. **No** transcript has any single dimension < 3.0
3. At least 2 transcripts were successfully captured (if spawn failed on all 3, that's a hard fail and the skill returns to Step 5)

Gate 11's contribution to `design_score` in the skill's audit block:

```yaml
gate_11_transcript_review:
  scenario_count: 3
  min_mean: 4.3
  min_dim: 4.0
  issues_found: 0
  passed: true
```

## Failure handling

| Failure mode | Action |
|---|---|
| Gate 11 hard fail (any transcript < 4.0 mean) | Return to Step 5 (body draft) with transcript diagnoses attached. Specific issues are handed to the rewriter so it can fix the body before re-running Gate 11. |
| Gate 11 soft fail (mean OK but one dim < 3.0) | Same — return to Step 5. Don't ship skills with a known dimension gap. |
| Spawn error on all 3 scenarios | The skill is fundamentally broken. Abort skill-create with `status: gate_11_unrunnable` and escalate to the caller. |
| Review prompt times out | Retry once. If still failing, reduce scenario count to 2. If still failing, abort. |

Max 1 revision loop at Gate 11 (counts against the overall 3-loop budget in skill-create). If Gate 11 fails twice, the skill's intent is probably too vague or too broad to be a single discrete skill — reclassify as two skills or sharpen the intent.

## Anti-patterns

- **Treating Gate 11 as optional.** It's part of the 11-gate pipeline, not a bonus check. A skill that skips Gate 11 is likely to fail design-agent Step 7 later, at which point the revision loop is more expensive.
- **Using the same 3 scenarios across all skills.** Each skill's scenarios must come from its own test corpus (generate_triggering_tests.py output). Reusing scenarios across skills produces false-positive passes.
- **Running Gate 11 on a skill that hasn't passed the secret scan.** Gate 11 spawns the draft. If the draft contains secrets, they end up in the transcript and potentially in the review logs. Always run Gate 9 first.
- **Writing the review prompt inline instead of using the template.** The blind review is load-bearing — the reviewer must not see the skill's self-scoring or it'll anchor on it.
- **Accepting a "warn" as a pass.** Gate 11 is binary: pass or return to Step 5. There's no warn tier here (unlike Gate 3 token budget).
- **Simulating more than 5 scenarios.** Budget is real. 3 is the right number for most skills; 5 is only for skills with exceptionally broad scope, and in that case the skill should probably be split.
