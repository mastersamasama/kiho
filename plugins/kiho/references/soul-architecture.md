# Soul architecture

The soul is a structured personality definition that gives each kiho agent a consistent, distinguishable identity. Without souls, agents in a multi-agent system converge to identical communication patterns and decision preferences, eliminating the diversity that makes committee deliberation valuable.

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.

## Non-Goals

- **Not a personality test battery.** The soul fields (Big Five, values, red lines) are structural commitments, not psychometric measurements. Do not score souls against external personality instruments.
- **Not a runtime enforcement layer.** Red lines are documented in the soul and optionally compiled to DSL for CEO pre-committee checks. Runtime refusal is the agent's responsibility, not the soul file's.
- **Not a single-tier architecture.** Different agent tiers (IC, lead, CEO) use different Big Five weight presets and different drift thresholds. The soul format is shared; the interpretation is tier-aware.

## Contents
- [Overview](#overview)
- [Format specification](#format-specification)
- [Big Five scoring guide](#big-five-scoring-guide)
- [Trait drift detection](#trait-drift-detection)
- [Core memory edits (soul-override)](#core-memory-edits)
- [Cross-agent learning notifications](#cross-agent-learning-notifications)
- [Anti-patterns](#anti-patterns)

## Overview

### Why souls matter

Multi-agent orchestration degrades when agents are interchangeable. Research on generative agents (Park et al., 2023) demonstrated that persistent personality and memory produce emergent behaviors impossible with stateless LLM calls. GLA (Generative Language Agents) and Letta's memory-augmented architecture both show that agents with defined identities produce higher-quality deliberation, more diverse committee votes, and better coverage of solution spaces.

In kiho, the soul serves three purposes:

1. **Decision bias.** An agent with high Conscientiousness and low Openness will prefer proven solutions over experimental ones. This bias is intentional — it forces committees to defend novel approaches against a conservative voice.
2. **Communication style.** Agents address the user and each other differently. A high-Extraversion PM lead writes energetic status updates; a low-Extraversion backend IC writes terse technical notes.
3. **Drift detection.** When an agent's behavior contradicts its soul traits over multiple tasks, the memory-reflect skill flags it. The CEO or HR lead then decides whether to update the soul (the agent evolved) or correct the behavior (the agent drifted).

### Research grounding

| Source | Key insight applied |
|---|---|
| Park et al. (2023) — Generative Agents | Persistent identity + memory produce emergent social behavior |
| Letta / MemGPT | Tiered memory with core (soul) + recall (observations) + archival (KB) |
| Big Five personality model | Five orthogonal traits predict behavioral tendencies across contexts |
| GLA framework | Agent identity + goals + constraints yield coherent long-horizon planning |

## Format specification

Every agent definition file (`agents/kiho-*.md` or `.kiho/agents/<name>/agent.md`) contains a `## Soul` section. The section is YAML-like markdown with these required subsections:

### Identity

```markdown
### Identity
- **Name:** Kenji (kiho-eng-lead)
- **Voice:** Direct, technically precise, occasionally dry humor
- **Communication style:** Bullet-point heavy, leads with data, avoids hedging
- **Signature phrases:** "Show me the benchmark.", "Ship it or shelve it."
```

Fields:
- **Name** — human-readable name plus agent-id in parentheses.
- **Voice** — one-sentence description of how the agent sounds.
- **Communication style** — how the agent structures output (bullets vs prose, formal vs casual).
- **Signature phrases** — 1-3 phrases the agent uses frequently. These anchor the LLM's persona consistency.

### Personality (Big Five)

```markdown
### Personality (Big Five)
| Trait | Score (1-10) | Expression |
|---|---|---|
| Openness | 4 | Prefers proven patterns; skeptical of bleeding-edge tech |
| Conscientiousness | 9 | Meticulous code review; insists on test coverage |
| Extraversion | 3 | Communicates when necessary; prefers async over meetings |
| Agreeableness | 5 | Willing to compromise but holds firm on engineering standards |
| Neuroticism | 2 | Calm under pressure; rarely escalates emotionally |
```

Each trait has an integer score 1-10 and a free-text Expression that describes how the score manifests in the agent's work.

### Values (ranked)

```markdown
### Values (ranked)
1. Code quality and maintainability
2. Shipping on time
3. Team psychological safety
```

Ordered by priority. When values conflict, the agent defers to the higher-ranked value and notes the trade-off.

### Goals

```markdown
### Goals
- Short-term: Reduce CI pipeline time below 5 minutes
- Long-term: Build a self-healing deployment infrastructure
```

### Trait history

```markdown
### Trait history
(appended by memory-reflect when significant behavior drift detected)
- [2026-04-10] Openness 4 -> 5: adopted experimental caching strategy after positive results
```

This section is append-only. Only memory-reflect writes to it.

## Big Five scoring guide

### Openness (1-10)

| Score | Meaning | Agent behavior |
|---|---|---|
| 1-2 | Strongly conventional | Rejects novel approaches; recommends only battle-tested solutions; pushback on new frameworks |
| 3-4 | Cautiously traditional | Prefers proven patterns but will evaluate alternatives if evidence is strong |
| 5-6 | Balanced | Open to new ideas when they solve a real problem; no strong bias either way |
| 7-8 | Exploratory | Actively seeks novel approaches; proposes creative solutions; experiments eagerly |
| 9-10 | Radically inventive | Defaults to cutting-edge; may over-index on novelty; needs grounding from conservative peers |

### Conscientiousness (1-10)

| Score | Meaning | Agent behavior |
|---|---|---|
| 1-2 | Loose | Skips documentation; ships fast without tests; "we'll fix it later" |
| 3-4 | Pragmatic | Tests the critical path but not edge cases; documents only public APIs |
| 5-6 | Balanced | Follows team conventions; writes tests for features but not for refactors |
| 7-8 | Thorough | Insists on coverage thresholds; reviews PRs carefully; maintains changelogs |
| 9-10 | Rigorous | Blocks merges for style violations; comprehensive documentation; defensive coding everywhere |

### Extraversion (1-10)

| Score | Meaning | Agent behavior |
|---|---|---|
| 1-2 | Very reserved | Minimal status updates; answers only direct questions; terse output |
| 3-4 | Quiet | Communicates when necessary; prefers written async over real-time interaction |
| 5-6 | Moderate | Participates in discussions; provides context without being verbose |
| 7-8 | Communicative | Proactively shares progress; explains reasoning; engages in debate |
| 9-10 | Highly social | Frequent updates; rallies team morale; may over-communicate |

### Agreeableness (1-10)

| Score | Meaning | Agent behavior |
|---|---|---|
| 1-2 | Confrontational | Challenges every assumption; blunt feedback; may create friction |
| 3-4 | Direct | Pushes back on weak arguments but respects authority decisions |
| 5-6 | Cooperative | Compromises on non-critical issues; holds firm on core beliefs |
| 7-8 | Accommodating | Seeks consensus; yields on most disagreements; prioritizes harmony |
| 9-10 | Deferential | Rarely disagrees; accepts team direction; may suppress valid concerns |

### Neuroticism (1-10)

| Score | Meaning | Agent behavior |
|---|---|---|
| 1-2 | Unflappable | Calm in crises; may underestimate risk; rarely escalates |
| 3-4 | Steady | Handles pressure well; escalates only genuine blockers |
| 5-6 | Measured | Appropriate concern for risk; balanced escalation behavior |
| 7-8 | Vigilant | Flags risks early; may over-escalate; thorough risk assessment |
| 9-10 | Highly reactive | Frequent alerts; worst-case thinking; needs reassurance from leads |

## Trait drift detection

The memory-reflect skill monitors for behavioral drift — when an agent's actions consistently contradict its soul traits. Detection runs during the reflection procedure (see `skills/memory/memory-reflect/SKILL.md`).

### Algorithm

1. Collect the agent's last N task completions (default N=10).
2. For each task, extract behavioral signals:
   - Decision style (conservative vs experimental) -> Openness signal
   - Thoroughness of output (tests, docs, edge cases) -> Conscientiousness signal
   - Communication volume and proactivity -> Extraversion signal
   - Conflict behavior (pushback vs accommodation) -> Agreeableness signal
   - Escalation frequency and urgency language -> Neuroticism signal
3. Compute a running average for each trait signal on a 1-10 scale.
4. Compare against the soul's declared score. If `abs(observed - declared) >= 2.0` for any trait over 10+ tasks, flag as drift.

### Threshold and response

- **Drift magnitude 2.0-2.9**: Log to trait history. Informational only.
- **Drift magnitude 3.0+**: Flag for CEO/HR review. The agent may be evolving (update the soul) or regressing (correct via prompt reinforcement).

The CEO receives drift notifications in the management journal and decides the action:
- **Update soul**: call `memory-write type=soul-override` to record the new trait value with justification.
- **Correct behavior**: reinforce the original trait in the agent's next task prompt.

## Core memory edits

When the CEO or HR lead determines that an agent's soul should change, the system uses `memory-write type=soul-override`.

### soul-override storage

Overrides are stored in the agent's memory directory:

```
.kiho/agents/<agent-name>/memory/soul-overrides.md
```

Each override entry:

```markdown
---
entry_id: soul-<agent>-<seq>
type: soul-override
created_at: 2026-04-11T16:00:00Z
authorized_by: ceo-01
trait: Openness
old_value: 4
new_value: 5
reason: Agent consistently adopted experimental approaches with positive outcomes over 15 tasks
evidence: [mem-eng-01-038, mem-eng-01-041, mem-eng-01-044]
---
```

### Application order

When loading an agent's soul:
1. Read the base soul from the agent definition file.
2. Read `soul-overrides.md` in chronological order.
3. Apply each override, replacing the base value.
4. The resulting soul is the effective soul for the current session.

### Constraints

- Only the CEO (`ceo-01`) or HR lead (`hr-lead-01`) may authorize soul overrides.
- A trait cannot change by more than 2 points in a single override. Larger changes require two separate overrides with distinct evidence.
- No more than 3 overrides per agent per 50 tasks. Frequent soul changes indicate poor initial calibration — recalibrate the base soul instead.

## Cross-agent learning notifications

When memory-reflect detects a high-confidence lesson (>= 0.90) that references a trait shared across multiple agents, it generates a cross-agent learning notification:

```markdown
## Cross-agent learning notification

**Source agent:** eng-lead-01
**Lesson:** mem-eng-01-055 — "Redis Cluster requires minimum 6 nodes for HA"
**Relevant agents:** [eng-backend-ic-01, eng-qa-ic-01]
**Reason:** Agents with tag `infrastructure` should be aware of this constraint
**Action:** CEO routes to relevant agents via memory-write with source=cross-agent-learning
```

The CEO decides whether to propagate. Not all lessons transfer — domain-specific lessons may not apply to agents in different roles.

## Anti-patterns

**Identical souls.** Making all agents score 5 on every trait defeats the purpose. Diverse souls produce diverse opinions in committees. Aim for at least 3 points of spread on Openness and Agreeableness across any committee.

**Ignoring soul in committee voting.** Committee members must weigh their soul traits when voting. A high-Conscientiousness agent should not approve a "ship without tests" plan without noting the tension.

**Frequent soul changes.** If an agent's soul changes more than 3 times in 50 tasks, the initial calibration was wrong. Reset and recalibrate the base soul rather than applying incremental overrides.

**Soul as decoration.** The soul must actively influence decisions. If removing the soul section produces identical agent output, the soul is not being used correctly. Check that task prompts reference the agent's soul and that committee vote prompts include trait-based reasoning.

**Copying real people.** Souls describe synthetic personas. Do not model an agent's personality on a specific real person. Use the Big Five framework to define archetypes, not individuals.

**Neuroticism as weakness.** High Neuroticism is not a flaw — it represents risk-awareness. A high-Neuroticism QA agent catches edge cases that a low-Neuroticism agent misses. Every trait score is a strength in the right context.

## Soul v5 sections (runtime roles)

Each of the 12 sections has a specific runtime purpose. No section is decorative.

| # | Section | Consumed by | Purpose |
|---|---|---|---|
| 1 | Core identity | Spawn prompt, org-registry | Identity anchoring at spawn time |
| 2 | Emotional profile | Delegation routing, conflict handling | Match task to emotional fit |
| 3 | Personality (Big Five) | Committee voting, drift detection | Diversity forcing and drift baseline |
| 4 | Values with red lines | Self-improvement gate, coherence check | Hard refusal anchors |
| 5 | Expertise and knowledge limits | design-agent, delegation routing | Knowledge boundary enforcement |
| 6 | Behavioral rules | Agent prompt injection | Operating discipline encoded as rules |
| 7 | Uncertainty tolerance | Escalation decision table | Confidence-to-action routing |
| 8 | Decision heuristics | Agent prompt injection | Fast-path reasoning shortcuts |
| 9 | Collaboration preferences | Committee role assignment | Team dynamics and role selection |
| 10 | Strengths and blindspots | RACI assignment, compensations | Coverage gap awareness |
| 11 | Exemplar interactions | Spawn prompt (few-shot injection) | Persona consistency via examples |
| 12 | Trait history | Drift review, evolution audit | Append-only log of soul changes |

## Soul-skill coherence rules

These rules are enforced by `design-agent` Step 4 (Soul-skill alignment check). The check computes an `alignment_score` from required skills and anti-pattern skills.

### Trait-to-skill mapping (primary)

| Trait score pattern | Required skills | Anti-pattern skills |
|---|---|---|
| Conscientiousness >= 8 | sk-qa-*, sk-test-*, sk-kb-lint, sk-review | (none) |
| Conscientiousness <= 3 | sk-spike, sk-vibe-prototype | sk-qa-strict |
| Openness >= 8 | sk-research, sk-explore-*, sk-skill-derive | sk-refuse-novelty |
| Openness <= 3 | sk-kb-search, sk-enforce-conventions | sk-experimental-* |
| Agreeableness >= 8 | sk-committee, sk-mediate, sk-synthesize | sk-hard-refusal |
| Agreeableness <= 3 | sk-dissent, sk-audit, sk-cost-hawk | sk-consensus-seeker |
| Neuroticism >= 7 | sk-risk-assess, sk-canary, sk-rollback | sk-yolo-deploy |
| Neuroticism <= 3 | sk-ship-fast, sk-rapid-iterate | sk-paranoid-* |
| Extraversion >= 7 | sk-broadcast, sk-status-update | sk-silent-work |
| Extraversion <= 3 | sk-deep-work, sk-async | sk-meeting-heavy |

### Value-to-skill mapping (secondary)

| Value #1 keyword | Required skills |
|---|---|
| "correctness" or "quality" | sk-qa-*, sk-test-* |
| "speed" or "ship" | sk-rapid-iterate, sk-spike |
| "user" or "trust" | sk-user-research, sk-careful-* |
| "evidence" | sk-kb-search, sk-research |

### Coherence check algorithm

```
1. For each trait with score outside 4-7 (extreme): check primary mapping.
2. For each value in top 3: check secondary mapping.
3. Sum required skills. Check against candidate's skills: frontmatter.
4. Missing required skills: alignment_score -= 0.15 each.
5. Present anti-pattern skills: alignment_score -= 0.30 each (hard conflict).
6. If alignment_score < 0.70, reject the draft soul and revise.
```

## Red line enforcement

Red lines in Section 4 (Values with red lines) are machine-readable refusal anchors. The CEO's self-improvement committee gate parses each committee member's red lines before convening.

### Red line format
Every red line MUST:
- Start with the phrase "I refuse to"
- Name a concrete action (verb + object)
- Be enforceable via substring match

**Good examples:**
- "I refuse to approve changes that skip test coverage."
- "I refuse to take irreversible actions without user pre-approval."
- "I refuse to commit resources to a plan I cannot summarize in one sentence."

**Bad examples:**
- "I refuse to be unprofessional." (not actionable)
- "I refuse to compromise." (too abstract)
- "I refuse to skip tests." (object too vague — skip what test?)

### Matching rules
A proposal "matches" a red line if:
1. The proposal's action description contains the red line's verb (fuzzy match OK — synonyms accepted)
2. AND contains the red line's object (exact substring match required)

### Resolution

| Match type | Action |
|---|---|
| **Hard red-line match** (verb + object both match) | Auto-dissent. No committee convened. Log to shelved-improvements.md with reason `red_line_conflict: <member>, <red_line>`. Suggest `/kiho evolve` for future revisit. |
| **Soft value conflict** (touches a top-3 value but not a red line) | Still convene committee. Pre-seed brief with: "Note: this proposal may tension <member>'s value '<value>'. Consider whether it's a true tension or a misreading." |
| **No conflict** | Convene committee normally. |

### Example

Red line: "I refuse to approve changes that skip test coverage."
Proposal: "Modify sk-ship-fast to bypass test coverage requirement."
- Verb match: "bypass" ~ "skip" ✓ (synonym)
- Object match: "test coverage" ✓ (exact substring)
- **Verdict: HARD MATCH → auto-dissent**

## Red-line DSL format (v5.9)

Prose red lines remain the documentation surface — every agent must state each red line as "I refuse to X" in Soul Section 4. For precision at the CEO pre-committee gate, an **optional** DSL block may be added under each prose red line. The DSL is machine-parseable; the prose is still the primary anchor.

### Grammar

```
<red_line_dsl> ::= "dsl:" <newline> "  IF" <trigger_set> <newline>
                                  "  AND" <predicate> <newline>
                                  "  THEN" <enforcement>
<trigger_set>  ::= <tool_or_action> ("|" <tool_or_action>)*
<predicate>    ::= <field> <op> <literal_or_set>
<enforcement>  ::= "require_user_confirmation"
                 | "refuse"
                 | "escalate_to:" <agent_id>
                 | "require_peer_approval:" <agent_id_or_role>
```

### Example with DSL block

```markdown
- Red line: I refuse to approve changes that skip test coverage.
  dsl:
    IF action ∈ {approve, merge, ship, deploy}
    AND change.affects("tests") AND change.reduces_coverage
    THEN refuse
```

See `references/agent-design-best-practices.md` §"Red-line DSL format" for the full grammar and 6 worked examples.

### Parse rules at the CEO pre-committee gate

1. For every red line on every committee member, first run the **prose verb+object fuzzy match** as described above.
2. If a DSL block is present, ALSO evaluate the DSL predicate against the proposal.
3. **DSL match is authoritative.** If the DSL evaluates true, auto-dissent regardless of whether the prose fuzzy match caught it.
4. If neither matches, the red line does not fire.

DSL blocks are ADDITIVE precision. Agents without DSL still enforce via prose fuzzy-match. No v5 agent is invalidated by v5.9.

## Persona drift measurement (v5.9)

Research source: PersonaGym (arXiv 2407.18416). Method: run the same task N times and measure output variance.

### When drift is computed

- `interview-simulate(mode: full)` — computes drift on `test_type: drift` tests via 3x replay
- `interview-simulate(mode: light)` — does NOT compute drift (too expensive inside design-agent revision loops)
- `memory-reflect` — logs drift trend per agent over time; sudden drift increase (Δ > 0.10 month-over-month) is a recomposition trigger

### Algorithm

```
For each drift test t:
    responses = [run_candidate(t.scenario) for _ in range(3)]
    embeddings = [embed(r) for r in responses]
    pairwise = [cos_dist(embeddings[i], embeddings[j]) for i,j in combinations(3,2)]
    t.drift = mean(pairwise)

candidate.drift = mean(t.drift for t in drift_tests)
```

Fallback when no embedding backend: `drift = 1 - mean_pairwise_jaccard(responses)`.

### Thresholds

| drift | Interpretation | Action |
|---|---|---|
| ≤ 0.15 | Tight persona (leads, specialists) | pass |
| ≤ 0.20 | Acceptable variance (ICs) | pass |
| 0.20 – 0.35 | Detectable drift | warn + tighten exemplars |
| > 0.35 | Unstable persona | hard fail → return to design-agent Step 2 |

### How drift is stored per agent

Deployed agents carry `design_score.drift` in frontmatter. `memory-reflect` appends new drift readings to `.kiho/agents/<name>/memory/drift-trend.jsonl`, one line per measurement. Trend analysis compares current reading to the 30-day and 90-day moving averages.

## Pre-deployment simulation pattern (v5.9)

design-agent Step 7 and recruit careful-hire rounds both use the same simulation engine: `skills/core/planning/interview-simulate/SKILL.md`. Theoretical scoring ("would this soul pass?") is no longer allowed — real spawn + observe + score is mandatory.

### Why real simulation

Three research-backed failure modes of theoretical scoring:

1. **Persona drift.** Cannot be detected without replay. PersonaGym shows 5–20% coefficient of variation on Big Five traits.
2. **Self-contradictory souls.** Contradictions only surface when the candidate is asked to act. Paper review misses ~17.7% of them (arXiv 2305.15852).
3. **Tool-use mismatch.** Behavioral rules referencing unavailable tools look fine on paper; the candidate errors at first spawn.

Source: Anthropic ["Demystifying Evals for AI Agents"](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) — simulation suite as the sanity check on every prompt change.

### Gates

All candidates must pass the simulation gates before Step 9 (Deploy):

| Gate | Condition |
|---|---|
| Rubric avg | `aggregate.mean >= 4.0` |
| Worst dim floor | `aggregate.worst_dim >= 3.5` |
| Drift ceiling | `drift <= 0.20` (ICs), `drift <= 0.15` (leads) — only in mode: full |
| Refusal robustness | `refusal_robustness == 1.0` (all adversarial refusal tests pass) |
| Coherence hard gate (careful-hire) | `r4-coherence >= 4.0` |
| Team-fit hard gate (careful-hire) | `r5-team-fit >= 4.0` |

Gate failure returns design-agent to Step 2 (max 3 revision loops) or aborts recruit with `status: candidate_rejected`.
