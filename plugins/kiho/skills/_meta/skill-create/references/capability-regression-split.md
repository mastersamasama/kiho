# Capability vs regression eval split (v5.14)

kiho separates a skill's eval suite into two named buckets — **capability** evals and **regression** evals — because they serve different purposes, follow different lifecycles, and should be graded with different tolerances. Conflating them is the top mistake called out in Anthropic's Jan 9 2026 "Demystifying Evals for AI Agents" post.

## Contents
- [Why the split matters](#why-the-split-matters)
- [Layout on disk](#layout-on-disk)
- [Lifecycle semantics](#lifecycle-semantics)
- [What goes where](#what-goes-where)
- [Pass thresholds](#pass-thresholds)
- [Migration from v5.13](#migration-from-v513)
- [Anti-patterns](#anti-patterns)

## Why the split matters

> "Capability evals are a hill to climb; regression evals are a cliff to avoid falling off."
> — Anthropic "Demystifying Evals for AI Agents", Jan 9 2026

**Capability evals** measure *whether the skill can do the thing at all*. They typically start at low pass rates (30-60%), guide iterative improvement, and saturate over time. Once they saturate, they stop providing signal and should be replaced or deprecated — a test that always passes is not measuring anything.

**Regression evals** measure *whether the skill is still doing the thing*. They start at near-100% pass rate (they're not added to the bucket until they pass cleanly) and any dip is a signal that something broke. They're load-bearing across model upgrades, body edits, and run_loop iterations.

**Conflation failure modes:**

- A saturated test in the capability bucket quietly stops measuring capability while everyone assumes it does. This is how "passes all evals" becomes meaningless.
- A noisy capability test in the regression bucket causes false alarms on every model upgrade and trains reviewers to ignore regression alerts.
- A regression threshold applied to capability tests aborts iteration before the skill even gets a chance to improve.
- A capability threshold applied to regression tests allows silent regression to ship.

## Layout on disk

Under `.kiho/state/drafts/sk-<slug>/evals/`:

```
evals/
├── capability/
│   ├── basic.json
│   ├── edge.json
│   ├── refusal.json
│   └── triggering.json
├── regression/
│   └── (empty at DRAFT creation — populated after first ACTIVE promotion)
├── isolation.manifest.json      # Gate 12 output
└── grading.json                 # assertion rubric shared by both buckets
```

At DRAFT creation (Step 9), only the `capability/` bucket is populated. The `regression/` bucket is created empty and populated lazily: after the first successful ACTIVE promotion, the capability tests that passed cleanly are *copied* (not moved) into `regression/` as frozen regression anchors. Each subsequent `skill-improve` mutation runs against both buckets and must keep regression at near-100%.

## Lifecycle semantics

### Capability bucket

- **Created at Step 9** from the intent + use cases.
- **Iterated freely** during run_loop; tests can be added, replaced, or removed between iterations.
- **Graded on F1 / balanced accuracy** (not raw accuracy — class imbalance is common).
- **Retired** when they saturate (`pass_rate > 0.95` across all iterations for 2 consecutive run_loops) OR when analyzer flags them as non-discriminating (assertion `delta < 0.20`).
- **Tolerances**: low pass rate is expected and informative. A capability test passing at 0.55 is useful signal; the same number on a regression test would be a P0 alert.

### Regression bucket

- **Created lazily** after first DRAFT → ACTIVE promotion.
- **Frozen**: tests in the regression bucket don't change between skill-improve iterations unless CEO explicitly retires them via committee.
- **Graded on pass rate**, must be ≥ 95% on every run.
- **Retired** only by explicit CEO committee decision.
- **Tolerances**: any dip below 95% is a hard fail that routes the mutation back to Step 5.

## What goes where

| Test type | v5.13 bucket | v5.14 capability | v5.14 regression |
|---|---|---|---|
| basic (happy path) | evals | ✓ (while iterating) | ✓ (frozen after promotion) |
| edge (ambiguity) | evals | ✓ | ✓ |
| refusal | evals | ✓ | ✓ |
| triggering_accuracy (corpus) | evals | ✓ | ✓ |
| transcript_correctness (Gate 11) | evals | ✓ | ✓ |
| **new-feature probe** (P0 feature request the skill hasn't shipped yet) | — | ✓ only | ✗ |
| **previous-bug-regression** (bug caught in a prior skill-improve) | — | ✗ | ✓ only |

New-feature probes are strictly capability — they should start at 0% pass rate and guide iteration. Previous-bug regressions are strictly regression — they're added *after* the bug is fixed and guard against re-introduction.

## Pass thresholds

Thresholds are declared per-bucket in the draft's `evals/<bucket>/meta.json`:

```json
{
  "bucket": "capability",
  "gate_metric": "f1",
  "gate_threshold": 0.70,
  "gate_on": "test_split",
  "tolerate_zero_pass": true,
  "saturation_check": true
}
```

```json
{
  "bucket": "regression",
  "gate_metric": "pass_rate",
  "gate_threshold": 0.95,
  "gate_on": "all",
  "tolerate_zero_pass": false,
  "saturation_check": false
}
```

`tolerate_zero_pass: true` in the capability bucket allows a test to exist at 0% pass rate — that's the starting point for the iteration loop. `tolerate_zero_pass: false` in regression means any test failure fails the whole bucket.

## Migration from v5.13

v5.13 skills have one flat `evals/` directory. The migration path:

1. `bin/catalog_gen.py` (or a one-off script) walks every existing ACTIVE skill.
2. For each skill, move all existing evals into `evals/capability/`.
3. Leave `evals/regression/` empty — the migration does not auto-populate regression.
4. On each skill's next `skill-improve` mutation, the run_loop populates `evals/regression/` from the capability tests that passed cleanly against the pre-mutation skill.

Migration is idempotent; re-running is safe.

## Anti-patterns

- **Promoting a test to regression before it has stabilized.** Wait until the test has passed cleanly across 2 full run_loops before copying it into regression.
- **Letting regression tests mutate.** Any change to a regression test is a CEO committee decision, not a skill-improve decision. Unless the committee explicitly retires a regression, it stays frozen.
- **Grading regression on F1.** Regression is gated on raw pass rate. F1 hides 5% drops on the minority class — which is exactly the kind of drift regression is supposed to catch.
- **Deleting a capability test because it's "too hard."** If the test is measuring a real capability, failing it is informative. Only retire on saturation (>95%) or non-discrimination (delta < 0.20).
- **Running regression tests during Step 4 description iteration.** Regression is for post-promotion validation; running it inside the description loop burns budget and contaminates the signal.

## Grounding

- Anthropic "Demystifying Evals for AI Agents", Jan 9 2026 — capability vs regression framing
- `anthropics/skills` `run_eval.py` — uses the `0.5 trigger-rate threshold` for description effectiveness (capability-style); regression is implemented separately in the bundled example repos
- kiho v5.14 H1 — eval pipeline isolation + grader review + bucket split
- Full research excerpt at `kiho-plugin/references/v5.14-research-findings.md`
