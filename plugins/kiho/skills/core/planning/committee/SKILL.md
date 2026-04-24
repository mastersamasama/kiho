---
name: committee
description: Convenes a structured multi-agent committee to deliberate on a question and reach consensus. Runs five-phase rounds (research, suggest, combine, challenge, choose) with a unanimous + no-unresolved-challenges close rule. Max 3 rounds before CEO escalation. Use when a decision needs multiple perspectives — spec stage reviews, architecture choices, hiring rubrics, contradictions, or any question where confidence from a single agent is insufficient. Triggers on "convene committee", "get multiple opinions", "debate this", or when CEO delegates a committee-debate item.
argument-hint: "topic=<question> members=[<agent-ids>] scope=<project|company> reversibility=<tag>"
metadata:
  trust-tier: T2
  kiho:
    capability: orchestrate
    topic_tags: [deliberation, orchestration]
    data_classes: ["committee-transcript", "committee-records-jsonl", "reflections"]
---
# committee

The committee protocol orchestrates structured multi-agent deliberation. Each committee runs in rounds of five phases. The protocol enforces convergence through combination, adversarial challenge, and unanimous close rules.

> **v5.21 cycle-aware.** Committee is invoked atomically (ad-hoc deliberation) AND as the `decision` phase entry in cycle templates (`talent-acquisition`, `decision-cycle`, `value-alignment`, `incident-lifecycle` triage variants). When run from cycle-runner, the cycle's `index.toml` provides the charter context; committee outputs (committee_id, recommended_tool / decision content) write back into the phase's `output_to_index_path`. Committee's own per-deliberation directory at `.kiho/committees/<committee-id>/` remains the authoritative artifact for the deliberation; the cycle index is the lifecycle position.

## Contents
- [Overview](#overview)
- [Convening a committee](#convening-a-committee)
- [Round structure](#round-structure)
- [Close rule](#close-rule)
- [Escalation](#escalation)
- [Clerk extraction](#clerk-extraction)
- [File layout](#file-layout)
- [Response shape](#response-shape)

## Overview

A committee is a temporary deliberation body. It has:
- A **convening leader** (the agent that requested the committee)
- **Members** (2-5 agents, each with a distinct perspective)
- A **clerk** (neutral extractor — see `agents/kiho-clerk.md`)
- A **topic** (single question, never compound)
- A **scope** (project or company tier)

Committees produce three artifacts: `transcript.md` (full chat log), `decision.md` (MADR-format outcome), and optionally `dissent.md` (minority positions).

## Convening a committee

The convening leader provides:

```yaml
topic: "Which auth provider should we use for the SSO feature?"
members:
  - kiho-eng-lead
  - kiho-pm-lead
  - kiho-researcher
scope: project
reversibility: slow-reversible
max_rounds: 3
knowledge_update: true
```

Create the committee directory at `<project>/.kiho/committees/<date>-<slug>/` using `templates/index.template.md`. Populate `index.md` with frontmatter. Initialize an empty `transcript.md` from `templates/transcript.template.md`.

**Language pre-check (v6 §3.7 propagation).** Before writing the first transcript header, invoke `python ${CLAUDE_PLUGIN_ROOT}/bin/brief_builder.py read-language --settings $COMPANY_ROOT/settings.md` via Bash. If the returned value is non-empty (e.g. `zh-TW`), record it at the top of `index.md` frontmatter as `transcript_language: <value>` and write EVERY subsequent transcript message body in that language (agent name labels and phase tags stay in English for parseability; the content prose and rationale follow the company language). If empty / helper unavailable: default to English (v5 behavior). Log `action: committee_language_set, value: <value|en>`.

## Round structure

Each round has five phases executed sequentially:

1. **Research** — each member reads KB context and gathers evidence
2. **Suggest** — each member posts their position with confidence and reasoning
3. **Combine** — members look for synthesis across positions
4. **Challenge** — members raise objections, edge cases, contradictions
5. **Choose** — each member declares their final position for this round

All messages append to `transcript.md` using the chat format defined in `references/chat-format.md`. Phase-level rules are in `references/round-phases.md`.

Each phase message includes: agent name, phase tag, position, confidence (0.0-1.0), reasoning, sources, and any challenges raised or resolved.

### Private consultation

During any phase, a member may request a private T+1 consultation with a specialist. See `references/consultation.md` for the sub-agent protocol.

## Close rule

A committee closes when ALL of:
1. **Unanimous position** — every member's latest `choose` message names the same option
2. **No unresolved challenges** — every challenge in the transcript has a corresponding `resolved: true` entry
3. **Aggregate confidence >= 0.90** — mean of all members' final confidence values

If the close rule is met after any round's choose phase, the committee closes immediately. Do not start another round.

If the close rule is NOT met after round N:
- Round 1 or 2: start the next round, injecting unresolved challenges and dissent into the research phase context
- Round 3: escalate to CEO with the current transcript and a structured summary

See `references/committee-rules.md` for the full close-rule specification and escalation table.

## Escalation

When max rounds are exhausted without consensus:

```markdown
## Escalation to CEO
status: escalated
rounds_used: 3
winning_position: <position with highest aggregate confidence>
winning_confidence: 0.82
dissent_positions:
  - position: <alternative>
    supporters: [agent-a, agent-b]
    confidence: 0.75
    rationale: <one-line>
unresolved_challenges:
  - <challenge summary 1>
  - <challenge summary 2>
recommendation: <clerk's recommendation based on evidence weight>
```

CEO applies the escalation decision table from `agents/kiho-ceo.md` — typically ASK_USER for irreversible decisions, RECONVENE (once) for reversible ones with strong dissent.

## Clerk extraction

When the committee closes (or escalates), the clerk agent runs the extraction pipeline:

1. Parse `transcript.md` into structured messages
2. Cluster positions and compute aggregate confidence
3. Write `decision.md` using `templates/decision.template.md` (MADR format)
4. Write `dissent.md` using `templates/dissent.template.md` if minority positions exist
5. If `knowledge_update: true`, call `kb-add` with the decision content
6. **Distribute reflections to participants (v5.20 Wave 2.1).** For each committee member, call `memory-write`:
   ```
   agent_id: <participant>
   type: reflection
   importance: 6
   subject: "Committee <committee-id>: <decision headline>"
   body: |
     Outcome: <decision summary>
     Aggregate confidence: <0..1>
     My stance: <converged | dissent>
     What I want to remember: <one-line distilled by clerk from member's positions across rounds>
   refs: [decision.md, dissent.md (if applicable)]
   ```
   The clerk derives "what I want to remember" from each member's own messages (their unique evidence cited, the minority position they considered, the assumptions that turned out wrong). This is the load-bearing change in Wave 2.1: previously committee members closed and forgot — now their reflections.md grows so future committees benefit from past learnings.

The clerk is always a neutral party. If the convening leader has a stake in the outcome, spawn `kiho-clerk` as a separate agent. See `references/clerk-protocol.md` for the full extraction pipeline.

## File layout

```
<project>/.kiho/committees/2026-04-11-auth-provider/
  index.md            # committee metadata (from index.template.md)
  transcript.md       # append-only chat log
  decision.md         # MADR output (clerk writes this)
  dissent.md          # minority report (optional)
  .meta/
    consultations/    # private T+1 consultation records
```

## Response shape

On completion, the committee skill returns to its caller:

```json
{
  "status": "consensus | escalated",
  "confidence": 0.93,
  "decision_path": ".kiho/committees/2026-04-11-auth-provider/decision.md",
  "dissent_path": ".kiho/committees/2026-04-11-auth-provider/dissent.md",
  "rounds_used": 2,
  "output_path": ".kiho/committees/2026-04-11-auth-provider/",
  "summary": "Committee chose Firebase Auth (3/3 unanimous, conf 0.93)",
  "contradictions_flagged": [],
  "new_questions": [],
  "skills_spawned": [],
  "escalate_to_user": null
}
```

## Anti-patterns

- Never run a committee for trivial decisions (single-option, obvious best choice, low impact). Use a committee only when multiple legitimate perspectives exist.
- Never allow a member to skip the challenge phase. Even if positions agree, challenge forces robustness testing.
- Never let the convening leader also serve as clerk when they have a stake in the outcome.
- Never start a new round if the close rule is already met. Check after every choose phase.
- Never compound multiple questions into one committee. Split into separate committees.
