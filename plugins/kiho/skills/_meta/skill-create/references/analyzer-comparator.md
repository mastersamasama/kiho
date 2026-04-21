# Analyzer and comparator reference

Full reference for the two skill-create sub-agents introduced in v5.14:
- `agents/analyzer.md` — scores benchmark.json by assertion-discrimination
- `agents/comparator.md` — blind A/B picks a winner across iterations

## Contents
- [Grounding](#grounding)
- [Pipeline placement](#pipeline-placement)
- [Schemas](#schemas)
- [Per-iteration artifact layout](#per-iteration-artifact-layout)
- [Non-monotonic iteration rule](#non-monotonic-iteration-rule)
- [How Gate 11 feeds the analyzer](#how-gate-11-feeds-the-analyzer)
- [Failure routes](#failure-routes)
- [Worked examples](#worked-examples)
- [Anti-patterns](#anti-patterns)

## Grounding

Two primary sources drive this v5.14 addition:

1. **`anthropics/skills` commit `b0cbd3d` (Mar 6 2026)** — adds `agents/analyzer.md`, `agents/comparator.md`, and the `analysis.json` / `comparison.json` schemas in `references/schemas.md`. This is the canonical upstream pattern.
2. **Anthropic's "Harness design for long-running application development" (Mar 24 2026)** — establishes the evaluator/generator separation principle and the non-monotonic iteration observation: "I regularly saw cases where I preferred a middle iteration over the last one."

Read these two documents (offline excerpts at `kiho-plugin/references/v5.14-research-findings.md` and `kiho-plugin/references/ralph-loop-philosophy.md`) before editing the analyzer or comparator.

## Pipeline placement

```
Step 10 (v5.13)     Gate 11 transcript review  --> benchmark.json (with-skill)
                                                --> baseline.json (without-skill, NEW in v5.14)
Step 10.5 (v5.14)   Analyzer pass               --> analysis.json
                                                --> fail: back to Step 5 or Step 9
                                                --> pass: continue
                    Comparator (if iter > 1)    --> comparison.json in iterations/<n>/comparisons/
                                                --> picks current_best (non-monotonic)
Step 11             Register as DRAFT           --> only the current_best SKILL.md registers
```

Step 10.5 runs **inside every run_loop iteration** — not just at the end. If iteration 2 loses to iteration 1, iteration 1 stays as the current best and iteration 3 is drafted with iteration 2's loser_weaknesses as explicit guidance.

## Schemas

### analysis.json

```json
{
  "status": "ok | rejected_non_discriminating | rejected_anti_discriminating | incomplete_input",
  "request_id": "<uuid>",
  "benchmark_scenarios": 3,
  "assertion_count": 12,
  "discriminating_count": 7,
  "weak_count": 3,
  "saturated_count": 1,
  "anti_count": 1,
  "discrimination_ratio": 0.583,
  "per_assertion": [
    {
      "assertion_id": "handles-null-input",
      "delta": 0.42,
      "pass_with": 0.85,
      "pass_without": 0.43,
      "verdict": "discriminating"
    }
  ],
  "flaky_scenarios": [
    {"scenario_id": "multi-turn", "per_run_pass_rates": [0.80, 0.40, 0.80], "flakiness": 0.35}
  ],
  "efficiency_score": 0.62,
  "slow_scenarios": [],
  "expensive_scenarios": [],
  "improvement_suggestions": ["..."],
  "transcript_insights": ["..."]
}
```

### comparison.json

```json
{
  "status": "ok | both_fail | insufficient_input",
  "request_id": "<uuid>",
  "winner": "A | B | tie",
  "winner_iteration": 2,
  "loser_iteration": 3,
  "rubric": {
    "correctness": {"winner": 4, "loser": 3, "evidence": "..."},
    "scope_adherence": {"winner": 4, "loser": 4, "evidence": "..."},
    "efficiency": {"winner": 3, "loser": 5, "evidence": "..."},
    "instruction_clarity": {"winner": 4, "loser": 3, "evidence": "..."}
  },
  "winner_strengths": ["..."],
  "loser_weaknesses": ["..."],
  "instruction_following_delta": "...",
  "improvement_suggestions_for_next_iteration": ["..."]
}
```

## Per-iteration artifact layout

```
.kiho/state/drafts/sk-<slug>/
├── SKILL.md                      # current best (updated after run_loop picks winner)
├── run-loop.json                 # run_loop.py summary
├── iterations/
│   ├── 1/
│   │   ├── SKILL.md
│   │   ├── benchmark.json        # with-skill run
│   │   ├── baseline.json         # without-skill run (new in v5.14)
│   │   ├── analysis.json         # from analyzer / compute_discrimination.py
│   │   └── comparisons/          # only from iteration 2 onward
│   │       └── comparator-input-<req>.json
│   ├── 2/...
│   └── 3/...
├── benchmark.json                # symlink or copy of current best's benchmark
└── analysis.json                 # symlink or copy of current best's analysis
```

`run_loop.py` has three modes:
- `--mode discover` lists all iterations and their loaded status
- `--mode summarize` writes `run-loop.json` and detects non-monotonic winner
- `--mode pair` writes a comparator input file when a new iteration arrives

## Non-monotonic iteration rule

The winner of run_loop is **not necessarily the most recent iteration**.

Implementation:

1. Every new iteration is compared against the **current best**, not the immediately-previous iteration.
2. If the new iteration wins, it becomes the new current best.
3. If the new iteration loses, the current best is preserved unchanged. The loop may continue one more iteration using the loser's weaknesses as guidance, or halt.
4. `run_loop.py --mode summarize` walks every `comparisons/*.json` across iterations and tallies wins; the iteration with the most wins becomes the reported best. Ties break by higher `discrimination_ratio`, then lower `mean_tokens`.
5. If `non_monotonic_winner: true` appears in `run-loop.json`, the summary writer logs it to stderr and the calling skill-create step MUST use the indicated iteration's SKILL.md, not the most recent file on disk.

## How Gate 11 feeds the analyzer

Gate 11 (v5.13) spawns the draft skill on 3 scenarios and reviews the transcripts on 4 dimensions. v5.14 extends Gate 11 to also:

1. **Produce a baseline.json.** After running the with-skill pass, re-run each scenario with the draft SKILL.md removed from the consuming agent's context (or with an empty stub skill at the same path) and capture the same assertion grid.
2. **Use a separate skeptical evaluator.** The transcript review agent is NOT the same agent that spawned the skill in the first run. kiho spawns a fresh evaluator subagent via `Agent(subagent_type="skill-create-analyzer", ...)` tuned with a skeptical system prompt ("uncertainty defaults to FAIL; praise is affirmative and must be earned"). This is the H5 evaluator-generator separation.
3. **Route the benchmark.json + baseline.json to the analyzer.** The analyzer reads both files, runs `compute_discrimination.py`, and writes `analysis.json` before returning to skill-create.

## Failure routes

| Analyzer status | skill-create action |
|---|---|
| `ok` | proceed to Step 11 register |
| `rejected_non_discriminating` | return to Step 9 (replace weak/saturated assertions) or Step 5 if the body is the problem |
| `rejected_anti_discriminating` | HARD fail — return to Step 5 with the anti-assertion evidence attached |
| `incomplete_input` | return to Step 10 and re-run Gate 11 |

| Comparator status | skill-create action |
|---|---|
| `ok` + new iteration wins | continue run loop, new iteration is current best |
| `ok` + current best wins | one more retry with loser weaknesses, then halt |
| `both_fail` | halt run loop with `status: revision_limit_exceeded`, surface both iterations' weaknesses to the caller |
| `insufficient_input` | return to Step 10 and produce missing benchmark/analysis files |

## Worked examples

### Example 1: non-monotonic winner

iteration 1: discrimination_ratio 0.55, mean_tokens 2400 — current best after iter 1
iteration 2: discrimination_ratio 0.68, mean_tokens 2800 — wins, new current best
iteration 3: discrimination_ratio 0.61, mean_tokens 2200 — loses vs iter 2 (lower discrimination)

`run-loop.json`:
```json
{
  "status": "ok",
  "iterations_run": 3,
  "best_iteration": 2,
  "non_monotonic_winner": false,
  "selection_method": "comparator"
}
```

Iteration 3 is discarded; iteration 2's SKILL.md is written to `sk-<slug>/SKILL.md`.

### Example 2: anti-discriminating assertion

Gate 11 produced:
- `benchmark.json`: pass_rate 0.62
- `baseline.json`: pass_rate 0.68

Analyzer finds one assertion with `pass_with: 0.30, pass_without: 0.55, delta: -0.25` — `verdict: anti`.

`analysis.json`:
```json
{
  "status": "rejected_anti_discriminating",
  "anti_count": 1,
  "discrimination_ratio": 0.33
}
```

skill-create routes back to Step 5 with message: *"Assertion 'handles-markdown-tables' regresses from 0.55 to 0.30. The body's pdfplumber workflow broke table extraction. Revise the table handling section."*

## Anti-patterns

- **Do not run the analyzer without a baseline.** An analysis that compares with-skill to nothing is meaningless. Gate 11 must produce both runs.
- **Do not let the analyzer read the SKILL.md body.** It judges signal, not substance. Keep its tools list filesystem-read but body-blind via prompt discipline.
- **Do not let the comparator know which iteration is newer.** The `seed` parameter in the comparator input randomizes A/B mapping to prevent recency bias.
- **Do not auto-continue past `rejected_anti_discriminating`.** Anti-discriminating means the skill made things worse. Always route back to Step 5 with the evidence.
- **Do not merge analyzer and comparator into one sub-agent.** They have different inputs, different outputs, and different failure modes. Separating them is cheaper and more debuggable.
- **Do not fall back to "latest wins" when the comparator can't run.** The fallback in `run_loop.py` uses composite score, not iteration number. Monotonic iteration is a failure mode to avoid, not a tie-breaker.
