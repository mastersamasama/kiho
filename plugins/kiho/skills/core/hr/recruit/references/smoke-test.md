# recruit smoke test — behavioral regression anchor

A canonical end-to-end scenario for the `recruit` skill. Serves as the **L3 Behavioral** regression anchor per the 7-layer quality framework (see `quality-scorecard.md`). Any future `skill-improve` pass on recruit should re-run this scenario and confirm the expected transcript shape still holds; drift from the expected outputs is a regression signal even when structural gates still pass.

**Why this exists.** Structural (L1) and semantic (L2) gates cannot detect the SkillsBench-documented failure mode where a skill *degrades* task outcomes. A paired "with-skill vs baseline" scenario is the minimum-viable behavioral check. Grounded in Anthropic's "Demystifying Evals" §step 6 (read transcripts, not just scores) and the SkillsBench paper (arXiv 2602.12670) §"16 of 84 tasks got worse with a curated skill injected".

## Scenario 1 — quick-hire backend IC (happy path)

### Invocation

```
recruit(
  department: engineering,
  role:       "Backend IC for Node.js API development on the /users and /auth endpoints",
  headcount:  1,
  tier:       quick-hire,
  conditions: "tools: Read, Glob, Grep, Write, Edit, Bash; model: sonnet",
  rubric_path: null,            # exercise the mini-committee rubric-design path
  requestor:  kiho-engineering-lead
)
```

### Expected transcript phases

| Phase | Key observation | Assertion |
|---|---|---|
| 1. Rubric prerequisite | kb-search for matching rubric → none found → mini-committee convenes → rubric written to `wiki/rubrics/rubric-backend-ic.md` | `rubric_path` set in internal state before role-spec phase |
| 2. Role-spec planner | `.kiho/state/recruit/eng-backend-ic/role-spec.md` written with all 6 fields filled (objective / output_format / tool_boundaries / termination / scaling_rule / work_sample) | `work_sample` is non-empty and concrete (e.g., "add a POST /auth/refresh endpoint with JWT rotation") |
| 3. Candidate generation | `design-agent` invoked 2×; candidates differ on ≥2 of {persona_seed, tool_manifest, model_tier} | `diversity_check.passed: true` in recruit's internal log |
| 4. Pre-score check | Both candidates pass design-agent Step 7 (rubric_avg ≥ 3.8, worst_dim ≥ 3.0, work_sample=pass) | `pool_to_committee.length == 2` |
| 5. Mini-committee | HR lead + engineering lead receive both candidates + transcripts + per-dim floor report + rubric | `committee_rounds == 1`, selection rationale is non-empty |
| 6. Deploy + register | Winning candidate's .md written to `agents/_templates/eng-backend-ic.md`; `kb-add` called with `page_type: entity`; `org-sync` invoked with `event_type: hire` | all three artifacts present post-run |
| 7. Response shape | JSON matches the documented [Response shape](../SKILL.md#response-shape) | `status == "ok"`, `hired.length == 1`, `per_dim_floors` populated for 6 dimensions including work_sample |

### Expected response (sample)

```json
{
  "status": "ok",
  "role_spec_path": ".kiho/state/recruit/eng-backend-ic/role-spec.md",
  "hired": [
    {
      "agent_name": "eng-backend-ic",
      "agent_path": "agents/_templates/eng-backend-ic.md",
      "candidate_score": 4.1,
      "worst_weakness": 3.6,
      "drift": null,
      "persona_stability": null,
      "work_sample": "pass",
      "per_dim_floors": {
        "accuracy": 4.0,
        "clarity": 3.6,
        "persona_fit": 4.2,
        "tool_use": 3.8,
        "refusal": 4.4,
        "work_sample": "pass"
      },
      "auditor_consensus": null,
      "simulation_transcript": ".kiho/runs/interview-simulate/<timestamp>-eng-backend-ic.jsonl"
    }
  ],
  "rejected": ["eng-backend-ic-fast"],
  "rubric_used": "wiki/rubrics/rubric-backend-ic.md",
  "kb_registered": true
}
```

Notes: `drift` and `persona_stability` are `null` for quick-hire — only careful-hire runs the 3× drift replay and the 8-round probe. `auditor_consensus` is `null` because mini-committee doesn't use the 4-auditor panel.

## Scenario 2 — careful-hire lead (full pipeline)

### Invocation

```
recruit(
  department: pm,
  role:       "Product Lead for B2B analytics suite — owns roadmap, PRD, and committee chairing",
  headcount:  1,
  tier:       careful-hire,
  conditions: "model: opus; must have Agent tool",
  requestor:  ceo-01
)
```

### Expected differences from Scenario 1

| Phase | Difference |
|---|---|
| 2. Role-spec planner | Full template (success metrics + red-line scenarios populated), not 1-paragraph form |
| 3. Candidate generation | 4 candidates (headcount × 4); pool spans ≥3 generation strategies |
| 4. Pre-screen + interview rounds | Pool pre-screened; survivors run full `r1-r8` including work-sample + 3× drift replay |
| 5. Persona-stability probe | 8-round off-topic/adversarial conversation; persona_stability ≥ 0.80 gate |
| 6. Auditor review | 4 auditors (Skeptic / Pragmatist / Overlap hunter / Cost hawk), each with persona soul-override |
| 7. Hiring committee | Full committee (HR lead + 4 auditors), max_rounds 2 |
| 8. Response shape | `drift`, `persona_stability`, `auditor_consensus` all populated with real values |

## Scenario 3 — work-sample catches averaged-rubric blind spot (adversarial)

### Setup

Inject a candidate whose `interview-simulate` scores average 4.4 but whose `r8-work-sample` test fails. A naive averaged-score gate would hire this candidate.

### Expected outcome

```json
{
  "status": "ok",
  "hired": [{"name": "eng-backend-ic-b", "rubric_avg": 3.9, "work_sample": "pass", "per_dim_floor_check": "pass"}],
  "rejected": [
    {
      "name": "eng-backend-ic-a",
      "rubric_avg": 4.4,
      "work_sample": "fail",
      "per_dim_floor_check": "fail — work_sample below floor",
      "rationale": "averaged rubric would have hired; per-dim floor rejected on work-sample"
    }
  ]
}
```

**Assertion:** The high-averaged candidate is rejected; the lower-averaged but work-sample-passing candidate wins. This is the empirical demonstration of H2 + H5 from the v5.16.6 research integration.

## Scenario 4 — abstract role, work-sample undesignable (degraded-mode probe)

### Setup

```
recruit(
  department: hr,
  role:       "HR strategy advisor — pure deliberation, no artifacts produced",
  tier:       careful-hire
)
```

### Expected behavior (currently undocumented — gap surfaced by this smoke test)

The role-spec planner's `work_sample` field is required. For pure-deliberation roles, the planner cannot invent a concrete held-out job. Today's SKILL.md has no documented escape hatch. **This is a real gap** — future work (Failure playbook Route G): accept `work_sample: waived` with CEO-committee approval logged in role-spec, and drop the work-sample dimension from the rubric for this candidate.

Until Route G exists, the smoke test expects recruit to return `status: rubric_failed` with rationale `"work_sample undesignable for pure-deliberation role"`.

## How to run this smoke test

Smoke tests are not automated in v5.16.7 — running them is a manual "dog-food your own skill" exercise by the HR lead or kiho-kb-manager. Future F1 (regression harness for deployed skills) will automate this.

Manual run:
1. Set up an isolated kiho project (fresh `.kiho/state/`).
2. Invoke recruit with the Scenario 1 input.
3. Capture the full turn transcript to `references/smoke-test-runs/<date>-scenario-1.md`.
4. Diff against the "Expected transcript phases" table; flag any deviation.
5. Repeat for Scenarios 2-4 as time permits.

## What this smoke test does NOT cover

- **Trigger-eval loop (Lever 1).** Description-level firing accuracy. Requires the 20-query eval corpus and 3× replay — separate artifact.
- **Cousin-prompt robustness (Lever 3).** Paraphrase resilience. Requires PromptBench-style perturbations.
- **LLM-as-judge body rubric (Lever 5).** Naming / progressive-disclosure / signal-to-noise assessment. Best run on the skill body, not on invocation transcripts.

These three levers + this smoke test together form the behavioral-quality floor (L3 + L4 + partial L6 of the 7-layer framework).
