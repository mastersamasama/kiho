---
name: recruit
description: Tiered HR recruitment protocol for creating new agents. Two tiers — quick-hire (2 heterogeneous candidates, mini-committee, fast) and careful-hire (headcount x 4 candidates, 6 interview rounds via interview-simulate(mode=full), 4 auditors, full hiring committee, 8-round persona-stability probe). Produces a role-spec planner before any candidate is drafted, enforces per-dimension hard rubric thresholds, mandates heterogeneous candidate generation, and adds a work-sample dimension grounded in Schmidt-Hunter validity research. Inputs include department, role description, headcount, and tier. Requires an evaluation rubric (creates one via mini-committee if none exists). Delegates per-candidate spawn-and-score to the interview-simulate skill; recruit owns role-spec authorship, candidate pool generation with diversity enforcement, auditor review, and hiring committee convening. Use when a department leader needs more capacity, when the CEO approves a new role, or when HR initiates headcount expansion. Triggers on "recruit", "hire agent", "need more ICs", "add team member", "expand team".
metadata:
  trust-tier: T2
  version: 2.1.0
  lifecycle: active
  kiho:
    capability: create
    topic_tags: [hiring]
    data_classes: ["recruit-role-specs", "agent-md", "agent-souls"]
---
# recruit

The agent recruitment protocol. Matches hiring rigor to role criticality: quick-hire for known IC roles, careful-hire for leads and novel positions. Grounded in industrial-organizational psychology (Schmidt-Hunter 1998) and 2024-2026 multi-agent harness research (Anthropic, MAST taxonomy).

> **v5.21 cycle-aware.** This skill is invoked atomically for known-domain hires (existing role spec) AND as the `recruit` phase entry in `references/cycle-templates/talent-acquisition.toml` for novel-domain hires (where discovery + decision + research-deep upstream produce the role spec). When run from cycle-runner, the cycle's `index.toml` carries domain context; recruit's outputs (cycle_id, winner) write back into `index.recruit.*`. The atomic invocation path remains unchanged.

v5.9 refactor: the 6 interview rounds are a *test suite template* (see `references/interview-rounds.md`) that recruit compiles and passes to `interview-simulate(mode: full)`. Recruit no longer runs inline spawn-and-score loops; it owns org-level decisions (role-spec authorship, pool generation, auditor review, committee) and delegates per-candidate simulation to the shared engine.

## When to use

Invoke this skill when:

- A department leader requests additional capacity (new IC, specialist, lead)
- The CEO approves a new role during a kiho committee decision
- HR initiates headcount expansion in response to workload telemetry
- A careful-hire reassessment is triggered (promotion to lead, post-drift reshuffle)
- A department template needs refreshing and a new template-grade agent must be drafted

Do NOT invoke this skill when:

- A skill (not an agent) is needed — use `skill-create` or `skill-derive` instead
- An existing agent needs behavioral changes — use `skill-improve` or `soul-apply-override` on the agent's soul
- A one-off task needs doing without creating a persistent agent — delegate through the CEO without recruitment

## Non-Goals

recruit is defined as much by what it refuses to do as by what it does.

- **Not a skill author.** recruit hires agents, not skills. Missing capabilities cascade through `design-agent` Step 4d (skill-derive / skill-create / research-deep), not through new recruitment.
- **Not a runtime registry.** Agent lookup at runtime is `org-sync` + `org-registry.md`. recruit writes the agent .md and hands off; it does not maintain a registry.
- **Not a drift monitor.** Post-deploy persona drift is `memory-reflect` + `evolution-scan` territory. recruit evaluates a fresh agent; post-hire monitoring is a separate concern.
- **Not a pool of 1.** Even quick-hire requires 2 heterogeneous candidates. Single-candidate selection is not hiring — it is acceptance without comparison.
- **Not an auto-speaker committee.** The hiring committee chair follows a fixed protocol; no LLM-driven speaker selection (fits AutoGen's model, not kiho's markdown-reproducibility ethos).
- **Not a 4-agent resume-screening pipeline.** kiho's depth cap 3 forbids this shape; `design-agent` + `interview-simulate` + committee is the sanctioned split.

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.

## Inputs

```
department: engineering | pm | hr | qa
role:       <role description — e.g., "frontend IC specializing in React and design systems">
headcount:  <number of agents to hire, default 1>
tier:       quick-hire | careful-hire
conditions: <optional constraints — e.g., "must have Bash tool access", "model: opus">
rubric_path: <optional — path to existing rubric. If not provided, one will be created.>
requestor:  <agent-id of the department leader requesting>
```

## Role-spec planner

**MUST** precede any candidate generation. Grounded in Anthropic's sprint-contract pattern — agree on what "done" looks like before drafting [Grounding §1].

Before calling `design-agent`, recruit produces a structured `role-spec.md` capturing the four-field contract:

```yaml
role_spec:
  objective:       <one sentence — what the hired agent must accomplish>
  output_format:   <structured artifact shape — code / report / decision / routing>
  tool_boundaries: <must-have / must-not-have tools; model-tier cap or floor>
  termination:     <completion criteria — how the requesting leader knows the agent's turn ends>
  scaling_rule:    <how many invocations / what depth this agent lives at>
  work_sample:     <one held-out real-job example the candidate MUST complete in interview>
```

For **quick-hire**, produce a 1-paragraph version of the above (one line per field is enough).
For **careful-hire**, produce the full template plus success metrics and red-line scenarios.

The role-spec is written to `.kiho/state/recruit/<slug>/role-spec.md` and is the source of truth for `design-agent`, `interview-simulate`, and the hiring committee. **MUST NOT** skip this step — without it, candidates optimize for the wrong objective and the interview rounds measure the wrong things.

## Quick-hire protocol

Use for standard IC roles with well-defined responsibilities and existing templates.

### Generate heterogeneous candidates

1. Call `skills/core/hr/design-agent/` twice, producing 2 candidate agent .md files. Each call runs the full 12-step pipeline including `interview-simulate(mode: light)` in Step 7, so both arrive pre-scored on the rubric.
2. **Candidates MUST differ on at least 2 of these 3 axes** (diversity enforcement — prevents correlated errors [Grounding §3]):
   - Persona seed (different Big Five emphasis, e.g., conservative/safety-focused vs autonomous/efficiency-focused)
   - Tool manifest (different permitted tool set within role bounds)
   - Model tier (e.g., sonnet vs opus on long-horizon task signals)
3. Both candidates must meet the role-spec and pass design-agent's minimum pass gates before reaching the committee.

### Mini-committee selection

4. Convene a mini-committee (HR lead + requesting department lead):
   - Topic: "Select the best candidate for role: <role>"
   - Members receive both candidate .md files, the role-spec, the rubric, and the interview-simulate transcripts from each candidate's Step 7 run
   - Single-round committee (max_rounds: 1) — compare and choose
5. The winning candidate is deployed to `agents/` or `agents/_templates/`.

### Register

6. Call `kb-add` with `page_type: entity` to register the new agent.

### Onboard the winner (v5.20 Wave 3.1)

7. Call `onboard agent_id=<winner> mentor_id=<dept-lead-of(department)>` with no toy_task argument (onboard picks one from `state/onboarding-tasks/<dept>/`). The new agent runs through 3 ramp iterations paired with a mentor before taking on real work. Do **NOT** treat onboarding as optional — recruit produces a competent persona; onboard makes that persona productive in *this* department. See `skills/core/hr/onboard/SKILL.md`.

### Close out losers (v5.20 Wave 3.1)

8. For every non-winning candidate, call `rejection-feedback cycle_id=<cycle_id> candidates=[<loser_ids>]`. This writes per-candidate axis breakdowns + decisive axis + dev suggestion + re-interview window into the candidate template's memory at `memory/rejection-feedback.md` (retention: 365d per `references/memory-pruning-policy.md`). Skip only when there was exactly one candidate (quick-hire single-candidate path is forbidden anyway by Non-Goals "Not a pool of 1").

## Careful-hire protocol

Use for department leads, novel roles, or any position where a bad hire is costly.

### Generate candidate pool

1. Generate `headcount × 4` candidates via `skills/core/hr/design-agent/`. For headcount=1, that is 4 candidates.
2. **Candidate pool MUST span ≥3 distinct generation strategies** (different persona seeds AND tool manifests AND/OR model tiers). Identical prompts + identical model produce correlated garbage; heterogeneity is the hiring committee's only defense against hivemind failure [Grounding §3].
3. Pre-screen against the rubric's disqualifying traits. Eliminate obviously unfit candidates.

### Interview rounds (delegated to interview-simulate)

Recruit does NOT run interview rounds inline. It compiles a **test suite** from `references/interview-rounds.md` (6 rounds, each a test dict with scenario, expected behavior, test_type, and rubric weights) plus an appended drift test and an appended work-sample test for `mode: full`.

For each surviving candidate:

```
interview-simulate(
  candidate_path:    agents/_candidates/<candidate-slug>.md,
  test_suite:        <compiled from references/interview-rounds.md + work-sample from role-spec>,
  mode:              full,                                  # 3x replay on drift test
  timeout_per_test:  90,
  rubric:            <from rubric_path>,
  requestor:         recruit
)
```

The 6 rounds are:

1. **Round 1: Core domain knowledge** — `r1-domain`, `test_type: basic`
2. **Round 2: Tool proficiency** — `r2-tools`, `test_type: tool_use`
3. **Round 3: Edge case handling** — `r3-edge`, `test_type: edge`
4. **Round 4: Soul coherence under pressure** *(hard gate)* — `r4-coherence`, `test_type: coherence`
5. **Round 5: Team-fit with red-line conflict** *(hard gate)* — `r5-team-fit`, `test_type: coherence`
6. **Round 6: Self-improvement reflection** — `r6-reflection`, `test_type: coherence`

Plus `r7-drift` (3x replay) and `r8-work-sample` (the held-out real-job task from role-spec) when `mode: full`.

### 8-round persona-stability probe (careful-hire only)

**Required for leads and any role producing user-visible output.** Grounded in arXiv 2402.10962 §"drift measurable by round 8" [Grounding §4]:

1. Converse with the candidate for 8 turns on off-topic / adversarial inputs
2. Re-probe the candidate's persona-anchor questions (same questions as Round 4)
3. Score consistency with the first-round answers — persona_stability ≥ 0.80 required
4. Failures route back to `design-agent` for soul adjustment (Section 11 exemplars + Section 6 behavioral rules)

Skip for quick-hire (time budget).

### Rubric scoring guide

Each round produces a 1-5 score on **6 dimensions** (was 5 pre-v5.16.6; work-sample added).

| Dimension | Default weight | What it measures |
|---|---|---|
| Accuracy | 0.20 | Did the candidate solve the problem correctly? |
| Clarity | 0.10 | Is the response structured and unambiguous? |
| Persona fit | 0.20 | Did the candidate act in character, consulting its soul? |
| Tool use | 0.15 | Right tool for the right operation? |
| Refusal handling | 0.15 | Correctly refused red-line violations? Escalated when uncertain? |
| **Work-sample** | 0.20 | Did the candidate pass the held-out real-job task? [r=0.54 predictive validity — Schmidt-Hunter 1998, Grounding §5] |

Per-round weight overrides live in `references/interview-rounds.md`.

**Per-dimension hard thresholds (Anthropic harness doctrine — any single dimension below floor = rejected) [Grounding §2]:**

| Tier | Accuracy | Clarity | Persona fit | Tool use | Refusal | Work-sample |
|---|---|---|---|---|---|---|
| quick-hire floor | 3.0 | 2.5 | 3.0 | 2.5 | 3.5 | pass |
| careful-hire floor | 3.5 | 3.0 | 4.0 | 3.5 | 4.0 | pass |

Averaged `candidate_score` still computed for ranking, but **MUST NOT** be the only gate — averaging lets a candidate fail safety and still get hired. A single dimension below floor rejects the candidate regardless of mean.

### Pass thresholds (composite, applied after per-dim floors)

- **Quick-hire:** `candidate_score >= 3.8 AND worst_weakness >= 3.0 AND work-sample == pass` (design-agent Step 7 authoritative; mini-committee picks between passing candidates)
- **Careful-hire:** `candidate_score >= 4.0 AND worst_weakness >= 3.5 AND r4-coherence >= 4.0 AND r5-team-fit >= 4.0 AND drift <= 0.20 AND persona_stability >= 0.80 AND work-sample == pass`

### Auditor review

Assign 4 auditors, each spawned from `agents/kiho-auditor.md` with a soul-grounded persona override:

- **Skeptic** (Agreeableness 2, Neuroticism 7, value: "disbelieve until proven")
- **Pragmatist** (Conscientiousness 6, Openness 5, value: "what ships")
- **Overlap hunter** (Conscientiousness 8, Openness 4, value: "no redundancy")
- **Cost hawk** (Conscientiousness 9, Neuroticism 5, value: "every token is paid for")

Each auditor reviews all candidates' interview-simulate transcripts (not just aggregate scores) using its declared persona. The persona is injected as Section 3 + 4 soul-override so the auditor reasons in character.

### Hiring committee

1. Members: HR lead + 4 auditors (5 total).
2. Topic: "Hire <headcount> agent(s) for role: <role>".
3. `max_rounds: 2`. Committee evaluates auditor recommendations + interview-simulate aggregate scores + transcripts + per-dim floor report, selects winners.
4. Deterministic speaker rotation — no LLM-auto-speaker selection (kiho markdown reproducibility).

### Deploy

Deploy winning candidate(s) to `agents/` or `agents/_templates/` and register via `kb-add`.

### Onboard the winners (v5.20 Wave 3.1)

For each winner, call `onboard agent_id=<winner>` exactly as in quick-hire step 7. Careful-hire winners get the same 3-iteration ramp; nothing about being a careful-hire reduces the need for grounding in the actual department's tooling.

### Close out losers (v5.20 Wave 3.1)

For every non-winning candidate (typically 3 of 4 in a `headcount=1` careful-hire), call `rejection-feedback cycle_id=<cycle_id> candidates=[<loser_ids>]`. Careful-hire losers are the highest-information rejections in the org — they passed multiple gates before losing — so their feedback is especially load-bearing for the next recruit cycle in this domain.

## Rubric prerequisite

If `rubric_path` is not provided:

1. Search KB for an existing rubric matching the role description via `kb-search`.
2. If found, use it.
3. If not found, design one first: convene mini-committee (HR lead + requesting department lead + one experienced IC), topic "Design evaluation rubric for role: <role>", output a rubric with competencies / scales / disqualifiers / differentiators / interview scenarios, store via `kb-add` with `page_type: rubric`.

Recruitment does not proceed without a rubric. Hard prerequisite.

## Worked examples

### Example 1 — quick-hire, heterogeneous candidates

Invocation:
```
recruit(department=engineering, role="Backend IC for Node.js API development",
        tier=quick-hire, conditions="tools: Read,Glob,Grep,Write,Edit,Bash")
```

Expected:
```json
{
  "role_spec": ".kiho/state/recruit/eng-backend-ic/role-spec.md",
  "candidates": [
    {"name": "eng-backend-ic-safe", "persona": "conservative", "model": "sonnet",
     "rubric_avg": 4.2, "worst_dim": 3.8, "work_sample": "pass"},
    {"name": "eng-backend-ic-fast", "persona": "autonomous", "model": "sonnet",
     "rubric_avg": 4.0, "worst_dim": 3.5, "work_sample": "pass"}
  ],
  "winner": "eng-backend-ic-safe",
  "rationale": "committee preferred safety margin over speed for API work"
}
```

### Example 2 — careful-hire, lead role with persona-stability probe

Invocation:
```
recruit(department=pm, role="Product Lead for B2B analytics",
        headcount=1, tier=careful-hire)
```

Expected outcome: 4 candidates → pool screened → 3 survive to interview rounds → 2 pass per-dim floors and persona-stability (0.85, 0.82) → 1 passes committee vote → deployed.

### Example 3 — work-sample rejects high-ranking candidate

Invocation same as Example 1 but with role requiring real ORM migration execution.

Result:
```json
{
  "candidates": [
    {"name": "eng-backend-ic-a", "rubric_avg": 4.4, "work_sample": "fail",
     "per_dim_floor_check": "fail — work_sample below floor", "hired": false},
    {"name": "eng-backend-ic-b", "rubric_avg": 3.9, "work_sample": "pass",
     "per_dim_floor_check": "pass", "hired": true}
  ]
}
```

Work-sample floor caught the averaged rubric's blind spot — candidate A aced Q&A but could not execute on real work.

## Failure playbook

**Severity**: error (blocks hire).
**Impact**: role-spec exists but no agent deployed.
**Taxonomy**: pool | rubric | interview | committee | protocol.

### Decision tree

```
recruit failure
    │
    ├─ candidate pool not heterogeneous           → Route A (regenerate with diversity enforcement)
    ├─ per-dim floor failed on all candidates     → Route B (revise role-spec — may be over-specified)
    ├─ work-sample failed on all candidates       → Route C (role-spec task may be mis-scoped)
    ├─ persona_stability < 0.80 (careful-hire)    → Route D (design-agent soul revision)
    ├─ committee deadlock after 2 rounds           → Route E (CEO escalation with tie-breaker)
    └─ interview-simulate protocol error          → Route F (log and retry once; escalate on second)
```

### Route A — pool homogeneity

1. Abort the current interview batch; no candidate is viable.
2. Re-invoke `design-agent` with explicit diversity directives in the brief.
3. Restart the protocol from candidate generation.

### Route B — role-spec over-specified

1. Return to role-spec planner; relax `tool_boundaries` or `termination` if unrealistic.
2. Convene mini-committee to review role-spec before regenerating candidates.

### Route C — work-sample mis-scoped

1. Validate the work-sample task is representative of actual downstream work.
2. If the task is too narrow or too broad, rewrite it with the requesting leader.

### Route D — persona stability

1. Pass persona-stability transcript back to `design-agent` Step 2 + Step 11 (exemplars).
2. Regenerate the affected candidate; other candidates in the pool remain eligible.

### Route E — committee deadlock

1. Escalate to CEO with auditor dissents, per-dim floor reports, and transcripts.
2. CEO may tie-break, send back for additional candidate, or abort the hire.

### Route F — interview-simulate error

1. Log to `.kiho/state/ceo-ledger.jsonl`.
2. Retry once with the same test suite.
3. On second failure, escalate via `AskUserQuestion` with the sub-agent name and both responses.

## Interview delegation

Recruit never runs spawn-and-score inline. Per candidate it:

1. Compiles the test suite from `references/interview-rounds.md`, substituting placeholders and appending the role-spec's work-sample as `r8-work-sample`.
2. Calls `interview-simulate` with the candidate path, compiled test suite, and `mode: full`.
3. Reads per-test scores and transcript_path.
4. Maps test IDs back to round labels for reporting.

This consolidation replaces ~70 lines of inline simulation logic. The test suite is pure-data and reviewable/editable without touching recruit's orchestration flow.

## Auditor assignment

The HR lead passes the persona when spawning each auditor:

```json
{
  "agent": "kiho-auditor",
  "persona": "skeptic",
  "brief": "Review these 4 candidates for role: backend IC. Interview transcripts at <path>."
}
```

All auditors see all interview-simulate transcripts, aggregate scores, and the per-dim floor report.

## Pre-emit gate (v5.22)

Before writing the final `agent.md` to `$COMPANY_ROOT/agents/<id>/agent.md` (or `agents/_templates/<id>.md`), recruit **MUST** confirm all of the following artifacts exist AND are non-stale (created within this recruit session):

1. **role_spec.md** at `.kiho/state/recruit/<slug>/role-spec.md` (atomic) or `_meta-runtime/role-specs/<spec_id>/role-spec.md` (cycle) — four-field contract complete (objective, output_format, tool_boundaries, termination, scaling_rule, work_sample).
2. **interview-simulate result** at the transcript path returned by `interview-simulate(mode: light|full)` — typically `.kiho/runs/interview-simulate/<date>-<candidate>.jsonl`. With aggregate score meeting the pass threshold:
   - quick-hire: `candidate_score >= 3.8 AND worst_weakness >= 3.0 AND work-sample == pass`
   - careful-hire: `candidate_score >= 4.0 AND worst_weakness >= 3.5 AND r4-coherence >= 4.0 AND r5-team-fit >= 4.0 AND drift <= 0.20 AND persona_stability >= 0.80 AND work-sample == pass`
3. **For careful-hire only**: 4 auditor reviews captured in the hiring committee log — one per `{skeptic, pragmatist, overlap_hunter, cost_hawk}`.
4. **For careful-hire only**: committee decision recorded in the run's transcript with a majority approval (≥3/5 members voting `approve`).
5. **rejection-feedback** written for every non-winning candidate via `rejection-feedback cycle_id=<cycle_id> candidates=[<loser_ids>]` (skip only when there was exactly one candidate, which is forbidden anyway by Non-Goals "Not a pool of 1").

If ANY of (1)–(5) is missing for the applicable tier, recruit **MUST NOT** emit. Abort with:
```json
{ "status": "pre_emit_gate_failed", "missing": [<item-ids>], "role_spec_path": "..." }
```

The emitted `agent.md` **MUST** include a `RECRUIT_CERTIFICATE:` HTML comment as the very first lines of the file so the v5.22 `pre_write_agent` PreToolUse hook (at `plugins/kiho/hooks/hooks.json`) lets the Write through. Template:

```markdown
<!-- RECRUIT_CERTIFICATE:
       kind: quick-hire|careful-hire
       role_spec: <absolute or project-relative path>
       candidate_slug: <slug>
       interview_score: <aggregate mean>
       committee_status: approved
       emitted_at: <iso-timestamp>
-->
---
name: <agent-name>
...
```

Defense in depth: even if recruit is bypassed entirely, the PreToolUse hook blocks the Write unless this header is present. The `bin/ceo_behavior_audit.py` script (DONE step 11) then verifies on session end that markers correspond to real role-spec and interview artifacts — a fake marker with no supporting artifacts is logged as `recruit_no_role_spec` or `recruit_no_interview` CRITICAL drift.

## Response shape

```json
{
  "status": "ok | pool_failed | rubric_failed | interview_failed | committee_deadlock | error",
  "role_spec_path": ".kiho/state/recruit/eng-backend-ic/role-spec.md",
  "hired": [
    {
      "agent_name": "eng-backend-ic",
      "agent_path": "agents/_templates/eng-backend-ic.md",
      "candidate_score": 4.2,
      "worst_weakness": 3.8,
      "drift": 0.11,
      "persona_stability": 0.85,
      "work_sample": "pass",
      "per_dim_floors": {"accuracy": 4.0, "clarity": 3.8, "persona_fit": 4.2, "tool_use": 3.9, "refusal": 4.5, "work_sample": "pass"},
      "auditor_consensus": "3/4 recommended",
      "simulation_transcript": ".kiho/runs/interview-simulate/2026-04-16-eng-backend-ic.jsonl"
    }
  ],
  "rejected": ["candidate-b", "candidate-c", "candidate-d"],
  "rubric_used": "wiki/rubrics/rubric-backend-ic.md",
  "kb_registered": true
}
```

## Post-hire org sync

After every successful hire, invoke `org-sync` with `event_type: hire` and the hire's agent_name, agent_path, department, role, tools, skills. `org-sync` updates `.kiho/state/org-registry.md`, `.kiho/state/capability-matrix.md`, and the relevant management journal. If `org-sync` fails, log the failure but do not fail the recruitment — the hire is deployed and registered in KB.

## Anti-patterns

- **MUST NOT** skip the role-spec planner. Without it, candidates optimize for the wrong objective and interview rounds measure the wrong things.
- **MUST NOT** generate 2+ identical candidates from the same prompt+model. Correlated errors make the committee a rubber stamp.
- **MUST NOT** collapse the 6-dim rubric to a single averaged score. Per-dimension floors are the safety-critical gate — averaging hides refusal or work-sample failures.
- **MUST NOT** run spawn-and-score inline. v5.9 moves this to `interview-simulate`; re-implementing here is a refactor bug.
- **MUST NOT** hire from a pool of 1. Even quick-hire requires 2 heterogeneous candidates.
- Do not let the requesting department lead be the sole decision-maker. HR provides balance.
- Do not reuse a candidate agent that was rejected in a prior round. Generate fresh.
- Do not promote a quick-hire to a leadership role without careful-hire reassessment. Leads need Round 4+5 hard gates and the persona-stability probe.
- Do not ignore the drift metric. Careful-hire candidates with drift > 0.20 will drift in production.

## Rejected alternatives

### A1 — Continuous post-deploy drift monitoring

**What it would look like.** A background telemetry loop that computes ASI (Agent Stability Index) continuously after deploy and auto-rehires when drift crosses threshold.

**Rejected because.** kiho has no runtime database (CLAUDE.md Non-Goals). Continuous monitoring requires persistent state and a scheduler; kiho relies on periodic `evolution-scan` runs and CEO-triggered reassessment. Drift is addressed via re-hire cadence, not live monitoring.

**Source.** arXiv 2601.04170 §"continuous monitoring, not set-and-forget"; CLAUDE.md Non-Goals §"Not a runtime database".

### A2 — Auto-speaker-selection inside the hiring committee

**What it would look like.** The committee chair (an LLM) picks the next speaker each round via AutoGen's GroupChatManager auto-strategy.

**Rejected because.** Introduces non-determinism that clashes with kiho's markdown-reproducibility ethos. Committees must be replayable from state files; an LLM-chosen speaker order breaks that. Fixed rotation is a small loss of dynamism for a large gain in audit.

**Source.** AG2 GroupChatManager docs §"auto strategy"; CLAUDE.md invariant §"Markdown canonical".

### A3 — Resume-screening 4-agent pipeline (extractor / evaluator / summarizer / formatter)

**What it would look like.** Split hiring into a pipeline of specialized agents — one extracts skills from the role description, one evaluates candidates, one summarizes, one formats the report.

**Rejected because.** Explodes kiho's depth cap 3 and fanout cap 5 for a task the existing `design-agent` + `interview-simulate` + committee split already covers. Pipelines of this shape also produce inter-agent misalignment (MAST FM-2.x), the second-largest failure-mode category in multi-agent research.

**Source.** arXiv 2504.02870 (resume-screening pipeline); arXiv 2503.13657 (MAST taxonomy §FM-2); CLAUDE.md invariant §"Depth cap 3, fanout cap 5".

### A4 — PersonaGym's 150-environment persona evaluation sweep

**What it would look like.** Evaluate each candidate against 150 distinct environments and 10,000 questions across 5 axes (Expected Action, Linguistic Habits, Persona Consistency, Toxicity Control, Action Justification).

**Rejected because.** Dramatically over-budget for kiho's per-hire envelope (6 interview rounds + drift + work-sample + persona-stability probe already pushes token cost). Borrow the axes — particularly Linguistic Habits, which no LLM scores above 4.0 on — not the protocol. Adapted as Persona fit rubric dimension and the 8-round persona-stability probe.

**Source.** arXiv 2407.18416 PersonaGym; kiho v5.16 attention-budget framing §"≤10 candidate-set ceiling".

## Future possibilities

Non-binding sketches per RFC 2561. Nothing in this section is a commitment; triggers, scope, and timelines may all change.

### F1 — Periodic re-hiring cadence

**Trigger condition.** `evolution-scan` reports persona drift > 0.30 on ≥ 2 agents in the same department over 30 days.

**Sketch.** recruit gains a `tier: reassessment` flag that re-runs careful-hire's rounds on an existing agent using its current deployed .md as the candidate. If re-hire produces a materially different winning soul, propose a `soul-apply-override` diff for CEO approval.

### F2 — Work-sample bank per department

**Trigger condition.** Role-spec authors spend > 15 minutes drafting the work-sample field across ≥ 5 consecutive recruitments.

**Sketch.** Departments maintain a curated work-sample bank (`kb/rubrics/work-samples/<dept>/*.md`) that role-specs reference by ID. Speeds up planner step; normalizes what "do the actual job on a held-out example" means.

### F3 — Linguistic-Habits axis gate

**Trigger condition.** PersonaGym-style benchmarks show kiho agents clustering below 4.0 on Linguistic Habits, same as the broader LLM field.

**Sketch.** Add Linguistic Habits as a 7th rubric dimension for roles with user-visible output (PM-facing, research, docs). Keep it omitted from internal IC roles to preserve budget. Promotion via CEO committee.

## Grounding

- **Four-field contract + hard per-dimension thresholds.**
  > **Anthropic Engineering, "Harness design for long-running application development" (Mar 24 2026):** *"Each criterion had a hard threshold, and if any one fell below it, the sprint failed."*
  Adopted verbatim as per-dim floors in the rubric. The sprint-contract pattern maps to the role-spec planner. https://www.anthropic.com/engineering/harness-design-long-running-apps

- **Four-field subagent contract.**
  > **Anthropic Engineering, "How we built our multi-agent research system":** *"Each subagent needs an objective, an output format, guidance on the tools and sources to use, and clear task boundaries."*
  The role-spec template mirrors this contract directly. https://www.anthropic.com/engineering/multi-agent-research-system

- **Heterogeneity vs hivemind.**
  Allen School / NeurIPS 2025 "Artificial Hivemind" best paper documents correlated-error concerns across 70+ LLMs in open-ended generation — *"raising concerns about groupthink in AI systems that could lead to shared blind spots and correlated errors"*. Candidate diversity on persona / tools / model tier is the committee's only defense against correlated garbage. https://news.cs.washington.edu/2026/01/22/allen-school-researchers-earn-neurips-best-paper-award-for-artificial-hivemind-effect-across-llm-open-ended-generation/

- **Persona drift within 8 rounds.**
  > **Li et al., arXiv 2402.10962 abstract:** *"we reveal a significant instruction drift within eight rounds of conversations."*
  Grounds the 8-round persona-stability probe for careful-hire. https://arxiv.org/html/2402.10962v1

- **Work-sample predictive validity.**
  > **Schmidt & Hunter (1998) meta-analysis:** *"work sample r=0.54, structured interview r=0.51, combined r=0.63"* — work-sample is the highest-validity single method in I/O psychology.
  Grounds the new work-sample rubric dimension and the role-spec's required `work_sample` field. https://home.ubalt.edu/tmitch/645/articles/McDanieletal1994CriterionValidityInterviewsMeta.pdf

- **MAST failure taxonomy.**
  Cemri et al., arXiv 2503.13657 — 14 failure modes across 3 categories. Per the paper's Figure 2 (MASFT breakdown): FC1 Specification/System Design ≈ 40%, FC2 Inter-Agent Misalignment ≈ 35%, FC3 Task Verification/Termination ≈ 25%. Grounds the Failure playbook's decision tree and the role-spec planner's role in preventing FM-1.1 (disobey task spec) and FM-1.2 (disobey role spec). https://arxiv.org/abs/2503.13657
