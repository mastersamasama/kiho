# Phase 5 detail — candidate synthesis

This reference documents how recruit merges the top-2 candidates into a
synthesized candidate when their scores are close AND their strengths are
complementary.

## Why synthesis

User direction: *"if top 2 have complementary pros, merge them rather than
pick one."* Synthesis is cheaper than re-interviewing a fifth candidate
from scratch AND captures the strength of both — which a plain `max()`
pick discards.

## When synthesis fires

Phase 5 evaluates after ranking:

```
top1, top2 = sorted(candidates, key=lambda c: c.rubric_avg, reverse=True)[:2]
delta = top1.rubric_avg - top2.rubric_avg

fire_synthesis = (
    settings.recruit.synthesis_when_complementary == true
    and delta <= settings.recruit.synthesis_rubric_delta_max   # default 0.20
    and strength_overlap(top1, top2) <= 0.50                   # Jaccard on specialties
    and top1.rubric_avg >= settings.recruit.committee_gate_threshold
    and top2.rubric_avg >= settings.recruit.committee_gate_threshold
)
```

Short-circuit: if either top candidate failed its hard gate (r4 < 4.0 or
r5 < 4.0 or refusal_robustness < 1.0), synthesis does NOT fire — hire top1
directly if it passed, else return `committee_rejected`.

## Synthesis invocation

```
design-agent op=synthesize_candidates(
  top1: {agent_md_path, rubric_scores, role_specialties, skills, soul_sections},
  top2: {agent_md_path, rubric_scores, role_specialties, skills, soul_sections},
  role_spec: <path>,
  recipe: <validated Phase 2 recipe>
) → synthesized_candidate
```

## Merge rules

### role_generic

Use `top1.role_generic` if lint-clean. Tie-break: if both lint-clean, prefer
the one with more recent wording (by authoring-token frequency in Phase 2).

### role_specialties

```
specialties_merged = top1.specialties ∪ top2.specialties
```

Keep dedupe only on case-insensitive exact match.

### skills

```
skills_merged = top1.skills ∪ top2.skills
```

Then re-run Phase 3.5.7 resolve check — every merged ID must still resolve.
If one top candidate had skills deprecated during Phase 3.5, take the
`superseded_by` replacement.

### Big Five

Weighted mean per trait, weight = rubric_avg's relevant dimension
contribution:

```
for trait in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
    w1 = top1.rubric[dim_relevance[trait]]
    w2 = top2.rubric[dim_relevance[trait]]
    synth.trait = round((top1.trait * w1 + top2.trait * w2) / (w1 + w2))
```

`dim_relevance` mapping:
- openness → accuracy + clarity (innovation signal)
- conscientiousness → tool_use + accuracy (discipline signal)
- extraversion → persona_fit + clarity (communication signal)
- agreeableness → persona_fit + refusal (social signal, inverted for refusal)
- neuroticism → refusal + worst_dim inverted (calm-under-pressure signal)

### Values

```
candidate_values = top1.values + top2.values   # preserves duplicates
ranked = sort by (
    rubric_avg contribution of value's related rounds,
    declared rank in original candidate  (tie-break)
)
synth.values = ranked[:3]   # top 3 only
```

Red lines: UNION — never narrows a red line. If two candidates have
conflicting red lines (one refuses X, the other requires X), synthesis
FAILS with `status: synthesis_red_line_conflict`; hire top1.

### Soul §6 behavioral rules

Union, then dedupe by verb-object. If two rules conflict (same verb, same
object, different action), keep top1's rule and log the dissent.

### Other soul sections

§1 biography: merged narrative stitched from both (design-agent prompt
produces the merge).
§7 uncertainty thresholds: stricter of the two (lower act-alone, lower
consult-peer).
§8 decision heuristics: top1's unless top2 has a heuristic top1 lacks; then
union.
§10 strengths/blindspots: union, dedupe by topic.

## Re-interview the synthesized candidate

Critical: the merged agent is NOT pre-scored. Run a fresh Phase 4 test
suite against it:

```
interview-simulate(
  candidate_path: .kiho/state/recruit/<slug>/candidates/synth/agent.md.draft,
  test_suite: <same 7 tests as original Phase 4>,
  mode: full,
  timeout_per_test: 90
)
```

Score on same rubric with same floors.

## Selection after re-interview

```
if synth.rubric_avg >= max(top1.rubric_avg, top2.rubric_avg) and synth_passes_hard_gates:
    hired = synthesized
    hire_provenance.hire_type = "v6-synthesis"
    hire_provenance.synthesized_from = [top1.id, top2.id]
else:
    hired = top1
    hire_provenance.hire_type = "v6-auto-recruit"
    log_ledger(action="synthesis_failed", synth_score=synth.rubric_avg,
               top1_score=top1.rubric_avg, reason="synth did not exceed top1")
```

## Worked example

**Phase 4 rankings:**
- candidate 1: rubric 4.28, specialties {expo, nativewind, design-tokens}
- candidate 2: rubric 4.15, specialties {react-native, zustand, valibot}
- candidate 3: rubric 3.92
- candidate 4: rubric 3.81

**delta = 4.28 - 4.15 = 0.13 ≤ 0.20** → synthesis eligible.

**Overlap:** specialties Jaccard = |{}| / |{expo, nativewind, design-tokens,
react-native, zustand, valibot}| = 0 → complementary. Fire synthesis.

**Merged specialties:** {expo, nativewind, design-tokens, react-native,
zustand, valibot}

**Re-interview result:** synth.rubric_avg = 4.45 > 4.28 → hire synth.

Hire provenance:
```yaml
hire_type: v6-synthesis
synthesized_from: [cand-01, cand-02]
synthesized_rubric_avg: 4.45
rejected: [cand-02, cand-03, cand-04]   # cand-02 lost to synth, not top1
```

## Anti-patterns

- **MUST NOT** narrow red lines in merge. Union only.
- **MUST NOT** skip the re-interview. A synth that inherited two high
  scores does not automatically score high together — persona coherence
  often breaks during merge.
- **MUST NOT** synthesize when strengths overlap heavily. The whole point
  is to combine complementary agents; merging two similar agents produces
  a weaker agent with contradictions.
- Do not ignore hard-gate failures in the synth interview. r4/r5 < 4.0 →
  hire top1, not synth, regardless of mean.
- Do not synthesize three-way or four-way. Only top-2.
