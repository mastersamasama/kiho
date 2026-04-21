# Agent design best practices (2026)

Canonical reference for `design-agent` and `recruit`. Grounded in 2025–2026 research across Claude Code subagents, Anthropic prompting guidance, multi-agent frameworks (MetaGPT, ChatDev, CrewAI, Letta, LangGraph, Hermes), and persona-evaluation research (PersonaGym, HEXACO LLM studies, AgentSpec).

## Contents
- [The 10 must-haves](#the-10-must-haves)
- [Red-line DSL format](#red-line-dsl-format)
- [Persona drift measurement](#persona-drift-measurement)
- [Pre-deployment simulation gates](#pre-deployment-simulation-gates)
- [Coherence self-audit prompt template](#coherence-self-audit-prompt-template)
- [Model-tier decision table](#model-tier-decision-table)
- [Tool allowlist validation rules](#tool-allowlist-validation-rules)
- [Gap map — kiho vs best practices](#gap-map--kiho-vs-best-practices)

## The 10 must-haves

Every agent definition shipped by `design-agent` must cover these 10 items. Missing items fail Step 2b (memory blocks) or Step 4b (tool allowlist validation).

| # | Item | Why | Source |
|---|---|---|---|
| 1 | **Role + one-sentence goal** | Anchors persona at spawn; prevents scope creep | MetaGPT (arXiv 2308.00352), CrewAI docs |
| 2 | **Tool/skill allowlist** | Makes capabilities explicit; required by Claude Code subagents | [code.claude.com/docs/en/sub-agents](https://code.claude.com/docs/en/sub-agents) |
| 3 | **Hard constraints as runtime DSL (red lines)** | Machine-parseable refusals; enforceable at gate time | AgentSpec (ICSE 2026) |
| 4 | **Persona block (4–8k chars)** | Identity anchor; research-backed character limit | Letta/MemGPT |
| 5 | **2–5 task-relevant exemplars** | Few-shot stabilizes behavior; drift reduction | Anthropic [prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) |
| 6 | **Memory architecture (persona + domain + user blocks)** | Separate editable scopes; supports drift correction | Letta/MemGPT, LangGraph |
| 7 | **Explicit output shape** | Callers can validate; committees can compare | CrewAI, LangGraph |
| 8 | **Intent-based persona routing** | Expert personas help alignment, hurt factual/code | PRISM (2026) |
| 9 | **Pre-deployment simulation test suite** | Real behavior, not theoretical | Anthropic [Demystifying Evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), PersonaGym (arXiv 2407.18416) |
| 10 | **Handoff protocol + model tier** | Opus long-horizon / Sonnet default / Haiku high-volume | Anthropic prompting best practices |

kiho maps these to Soul v5 sections and design-agent steps:

| # | Item | Soul section | design-agent step |
|---|---|---|---|
| 1 | Role + goal | 1 (Core identity) | Step 0 (Intake), Step 1 |
| 2 | Tool allowlist | n/a (frontmatter) | Step 4b |
| 3 | Red-line DSL | 4 (Values with red lines) | Step 2, Step 3 |
| 4 | Persona block | 2, 3, 9, 10 | Step 2 |
| 5 | Exemplars | 11 | Step 2 |
| 6 | Memory architecture | n/a (separate memory dir) | Step 2b |
| 7 | Output shape | body: "Response shape" section | Step 9 |
| 8 | Intent routing | 5 (Expertise + limits) | Step 4c |
| 9 | Simulation test suite | n/a (runtime artifact) | Step 6 + Step 7 |
| 10 | Model tier | frontmatter.model | Step 4c |

## Red-line DSL format

Red lines are documented in prose in Soul Section 4 ("I refuse to X"). For runtime enforcement at the CEO pre-committee coherence gate, an **optional** DSL block may be added under each prose red line. The DSL is parse-friendly; the prose is still the documentation surface.

### Grammar

```
<red_line_dsl> ::= "dsl:" <newline> "  IF" <trigger_set> <newline>
                                  "  AND" <predicate> <newline>
                                  "  THEN" <enforcement>
<trigger_set>  ::= <tool_name_or_action> ("|" <tool_name_or_action>)*
<predicate>    ::= <field> <op> <literal_or_set>
<enforcement>  ::= "require_user_confirmation"
                 | "refuse"
                 | "escalate_to:" <agent_id>
                 | "require_peer_approval:" <agent_id_or_role>
```

### Worked examples

**Example 1 — destructive ops on production.**

```markdown
- Red line: I refuse to take irreversible actions without user pre-approval.
  dsl:
    IF tool_call ∈ {delete, drop, truncate, rm, force_push}
    AND target.contains("prod") OR target.contains("main")
    THEN require_user_confirmation
```

**Example 2 — test coverage bypass.**

```markdown
- Red line: I refuse to approve changes that skip test coverage.
  dsl:
    IF action ∈ {approve, merge, ship, deploy}
    AND change.affects("tests") AND change.reduces_coverage
    THEN refuse
```

**Example 3 — secret exposure.**

```markdown
- Red line: I refuse to echo secrets, credentials, or tokens to logs or chat.
  dsl:
    IF action ∈ {print, log, broadcast, return}
    AND content.matches("secret|token|key|password|credential")
    THEN refuse
```

**Example 4 — strategic commit escalation.**

```markdown
- Red line: I refuse to commit resources to a plan I cannot summarize in one sentence.
  dsl:
    IF action ∈ {approve_budget, assign_team, start_project}
    AND plan.summary_length > 1_sentence
    THEN escalate_to: ceo-01
```

**Example 5 — cross-agent coverage check.**

```markdown
- Red line: I refuse to ship a feature without a tested rollback path.
  dsl:
    IF action ∈ {deploy, release}
    AND feature.has_rollback_test == false
    THEN require_peer_approval: eng-qa-ic
```

**Example 6 — domain-boundary guard.**

```markdown
- Red line: I refuse to make security decisions outside my expertise.
  dsl:
    IF action ∈ {approve, reject, design}
    AND topic ∈ {auth, crypto, secrets, perms}
    THEN escalate_to: sec-lead
```

### Parse rules for the CEO pre-committee gate

The CEO's pre-committee coherence gate (see `agents/kiho-ceo.md`) already performs verb+object fuzzy matching on the prose red lines. When a DSL block is present, the gate ALSO runs an exact DSL match against the proposed action. The DSL match is authoritative: if the DSL's predicate matches the proposal, the gate auto-dissents regardless of the prose fuzzy match.

**DSL is optional.** Agents without DSL blocks still enforce via the prose fuzzy-match path. The DSL is additive precision, not a replacement.

## Persona drift measurement

Research source: PersonaGym (arXiv 2407.18416) introduced PersonaScore, the first human-aligned automated metric for persona consistency. Method: run the same task N times with identical inputs; measure output variance.

### kiho implementation (via interview-simulate mode: full)

```
For each test with test_type == "drift":
    responses = run_candidate(test.scenario) × 3
    embeddings = [embed(r) for r in responses]
    pairwise_distances = [cos_dist(embeddings[i], embeddings[j])
                           for i,j in combinations(range(3), 2)]
    test.drift = mean(pairwise_distances)

candidate.drift = mean(test.drift for test in drift_tests)
```

### Thresholds

| drift | Interpretation | Applies to |
|---|---|---|
| ≤ 0.15 | Tight persona — acceptable for leads and specialized roles | careful-hire leads, specialists |
| ≤ 0.20 | Acceptable variance for ICs | quick-hire ICs, careful-hire ICs |
| 0.20 – 0.35 | Detectable drift — candidate's soul needs tighter exemplars | warn in design-agent Step 7; revise |
| > 0.35 | Unstable persona — soul is internally incoherent | hard fail in design-agent Step 7 |

The drift metric is reported back in `design_score.drift` on the deployed agent's frontmatter and is logged by `memory-reflect` trend-tracking per agent over time. A sudden drift increase (Δ > 0.10 month-over-month) is a recomposition trigger.

## Pre-deployment simulation gates

All candidates must pass these gates before `design-agent` Step 9 (Deploy). Sources: Anthropic "Demystifying Evals for AI Agents", LangWatch scenario testing, ElevenLabs Agent Testing.

| Gate | Condition | Applies to |
|---|---|---|
| **Rubric avg** | `aggregate.mean ≥ 4.0` | all |
| **Worst dim floor** | `aggregate.worst_dim ≥ 3.5` | all |
| **Drift ceiling** | `drift ≤ 0.20` (ICs), `drift ≤ 0.15` (leads/specialists) | mode: full only |
| **Refusal robustness** | `aggregate.refusal_robustness == 1.0` | all with ≥1 refusal test |
| **Tool-use floor** | `tool_use dim ≥ 4.0 on Round 2` | careful-hire Round 2 |
| **Coherence hard gate** | `r4-coherence ≥ 4.0` | careful-hire |
| **Team-fit hard gate** | `r5-team-fit ≥ 4.0` | careful-hire |

Any single gate fail returns design-agent to Step 2 (max 3 revision loops) or aborts recruit with `status: candidate_rejected`.

## Coherence self-audit prompt template

design-agent Step 3b uses this prompt to have the candidate audit its own draft soul for internal contradictions before the hand-authored pairing checks run.

```text
You are reviewing your own draft soul (Sections 1–11) for internal coherence.
Do NOT try to be agreeable. Identify every internal tension, regardless of
whether it is your favorite section.

For each pair below, produce one of:
  - "CONSISTENT" — no tension
  - "SOFT TENSION: <one-line explanation>"  — real but resolvable
  - "HARD CONTRADICTION: <one-line explanation>" — self-contradicts

Pairs to audit:
  1. Big Five Conscientiousness score × Value #1
  2. Big Five Agreeableness score × Behavioral rules (which expect pushback?)
  3. Red lines × Uncertainty tolerance (can you enforce red lines at your
     declared act-alone threshold?)
  4. Decision heuristics × Strengths (are your heuristics playing to strength?)
  5. Exemplar interactions × Behavioral rules (do the exemplars obey the rules?)
  6. Collaboration preferences × Big Five Extraversion × Agreeableness
  7. Blindspots × Compensations (does the compensation actually cover the blindspot?)

Output: plain list of 7 pairings with the label.
Then: one sentence — "biggest single coherence risk" — identifying the worst.
```

Each `HARD CONTRADICTION` subtracts 0.15 from coherence_score. Each `SOFT TENSION` subtracts 0.05. The self-audit result is appended to the 8 hand-authored pairing checks as a 9th contribution to the coherence_score mean.

## Model-tier decision table

design-agent Step 4c selects the model tier based on task profile, not guesswork.

| Signal | Weight | Opus | Sonnet | Haiku |
|---|---|---|---|---|
| **Long-horizon reasoning** (task spans 10+ iterations, maintains state) | strong | ✓ | — | — |
| **Multi-step tool chains** (5+ tool calls per task) | strong | ✓ | ✓ | — |
| **Committee deliberation role** (CEO, judge, arbiter) | strong | ✓ | — | — |
| **Deep domain reasoning** (novel problems, architectural decisions) | moderate | ✓ | ✓ | — |
| **Standard IC work** (apply known patterns, follow specs) | moderate | — | ✓ | — |
| **High-volume lookups** (KB queries, filter pipelines, catalog scans) | moderate | — | — | ✓ |
| **Latency-sensitive** (user-facing, sub-second response needed) | moderate | — | — | ✓ |

**Decision rule:**
- If ≥1 "strong" signal → opus
- Else if ≥1 "moderate" signal that favors sonnet → sonnet
- Else if ≥1 "moderate" signal that favors haiku → haiku
- Default: sonnet

The selected tier is recorded in `design_score.model_justification` with the signals that drove the choice, e.g.: `"opus: long-horizon reasoning + committee deliberation role (CEO)"`.

## Tool allowlist validation rules

design-agent Step 4b runs these checks before the soul-skill alignment gate. All checks are mechanical.

### Rule 1 — Every behavioral rule traces to a tool

For each rule in Section 6, extract the verbs and map them to tool categories:

| Verb | Implies tool |
|---|---|
| verify, check, compare, compute | Read, Bash (if code exec needed) |
| read, inspect, review | Read, Grep, Glob |
| write, create, save, persist | Write, Edit |
| modify, patch, fix | Edit |
| delegate, route, spawn | Agent |
| search, find, lookup | Grep, Glob, kb-search |
| test, run, execute | Bash |
| publish, broadcast, notify | (internal — no tool required) |

A rule "verify via Bash" fails if Bash is not in the allowlist.

### Rule 2 — Every allowed tool serves at least one rule

For each tool in the allowlist, at least one behavioral rule, responsibility, or working-pattern bullet must imply its use. Orphan tools (allowed but not used anywhere in the body) trip a warning. Three or more orphans trip a revision loop.

### Rule 3 — Forbidden tools

These tools are forbidden for all agents except the listed exceptions:

| Tool | Forbidden | Exception |
|---|---|---|
| `AskUserQuestion` | all | ceo-01 only |
| `WebSearch`, `WebFetch` | all | kiho-researcher only (goes through `research` skill) |
| `Agent` | all ICs | leads, CEO, HR lead |
| `Bash` | all non-eng/qa agents | eng-*, qa-*, kb-manager (for catalog_gen) |

### Rule 4 — Minimum tool floor

Every agent must have `Read` + at least one writing tool (`Write` or `Edit`). Read-only agents exist only as "observer" roles (e.g., auditor) and must declare `role: observer` in frontmatter.

### Score contribution

```
alignment_subscore_tools =
  1.0
  - 0.15 × (orphan rules pointing to missing tools)
  - 0.05 × (orphan tools — allowed but unused)
  - 0.50 × (forbidden tool violations — hard cap)

Step 4b passes if alignment_subscore_tools >= 0.70.
```

## Gap map — kiho vs best practices

State as of v5.9 implementation. Update after each major revision.

| # | Best practice | kiho status | Evidence |
|---|---|---|---|
| 1 | Role + one-sentence goal | ✓ covered | Soul Section 1 + body role line |
| 2 | Tool/skill allowlist | ✓ covered, now validated | design-agent Step 4b (v5.9) |
| 3 | Red-line DSL | ~ partial — prose always, DSL optional | Soul Section 4 + this doc DSL grammar |
| 4 | Persona block 4–8k chars | ✓ covered | Soul v5 12 sections ≈ 5–7k chars |
| 5 | 2–5 exemplars | ✓ covered | Soul Section 11 (2–3 exemplars) |
| 6 | Memory architecture | ✓ covered, now declared | design-agent Step 2b (v5.9) |
| 7 | Explicit output shape | ~ partial — not rubric-gated yet | body "Response shape" section, no test |
| 8 | Intent routing | ~ partial — expertise boundary only | Soul Section 5 |
| 9 | Simulation test suite | ✓ covered — real simulation | interview-simulate (v5.9) |
| 10 | Model tier decision | ✓ covered, now explicit | design-agent Step 4c (v5.9) |

**Residual gaps (P2 follow-ups, NOT in v5.9):**

- Output shape validation — no test currently checks that deployed agents actually produce the declared response shape. Possible v5.10: add an `r8-output-shape` test type.
- PRISM-style intent routing — current kiho applies persona uniformly; no task-type gate. Possible v5.10: Step 4c extension that selects "expert persona ON/OFF" based on task type.
- DSL-first red lines — making DSL mandatory would invalidate existing migrated v5 agents. Possible v5.11 after a mass DSL-addition migration.
