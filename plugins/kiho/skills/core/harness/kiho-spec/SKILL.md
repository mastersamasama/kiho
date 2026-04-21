---
name: kiho-spec
description: Harness-enriched kiro spec runner that orchestrates the three-stage spec ritual (requirements, design, tasks) with committee-backed deliberation at each stage. For each stage, convenes a committee with relevant departments (PM+Research for requirements, PM+Eng+Research for design, Eng+QA for tasks), merges contributions into kiro-template-based documents, presents to the user for gate approval, and calls kb-add on completion. Use when the CEO delegates a feature, bugfix, or refactor plan item that needs spec-driven development. Triggers on spec generation, stage-gate work, or committee-enriched kiro flows.
metadata:
  trust-tier: T3
  kiho:
    capability: orchestrate
    topic_tags: [orchestration, engineering]
    data_classes: ["plan", "completion"]
---
# kiho-spec

The spec runner enriches kiro's three-stage spec ritual with multi-department committees. Each stage produces a kiro-format document, vetted by a committee of relevant specialists, and gated by user approval before advancing.

## Contents
- [Overview](#overview)
- [Stage pipeline](#stage-pipeline)
- [Requirements stage](#requirements-stage)
- [Design stage](#design-stage)
- [Tasks stage](#tasks-stage)
- [Gate protocol](#gate-protocol)
- [KB integration](#kb-integration)
- [Response shape](#response-shape)

## Overview

The CEO delegates a plan item to kiho-spec with a brief containing the goal, context, constraints, and mode (feature/bugfix/refactor). kiho-spec runs the kiro three-stage pipeline, enriching each stage with a committee.

The mechanical kiro template filling is handled by `skills/engineering-kiro/`. kiho-spec wraps it with:
1. Committee deliberation per stage (multiple perspectives)
2. User gate approval per stage (preserved kiro discipline)
3. KB integration per stage (decisions captured immediately)

## Stage pipeline

```
Requirements ──[user gate]──> Design ──[user gate]──> Tasks ──[user gate]──> Done
     |                           |                        |
  PM + Research              PM + Eng + Research       Eng + QA
  committee                  committee                 committee
```

Each stage:
1. Read the brief and any prior stage output
2. Convene a committee with the relevant departments
3. Merge committee output into the kiro template
4. Present the filled template to the user via CEO (return `escalate_to_user` with the document)
5. On user approval, call `kb-add` with the stage output
6. Advance to the next stage

If the user rejects a stage, return to the committee with the user's feedback injected.

## Requirements stage

**Committee members:** PM lead, researcher (and optionally a domain-expert IC)

**Input:** CEO brief with goal, user context, constraints

**Procedure:**
1. Invoke `skills/research/` with the brief topic — gather KB context, external research
2. Convene a committee with topic: "Define requirements for: <goal>"
3. Committee members research user needs, suggest requirement sets, combine, challenge completeness/feasibility, choose final requirements
4. Merge the winning position into `skills/engineering-kiro/kiro/templates/requirements.template.md`
5. Fill template fields: functional requirements, non-functional requirements, user stories, acceptance criteria, out-of-scope items
6. Return `escalate_to_user` with the filled requirements document for gate approval

**Output:** `<project>/.kiho/specs/<slug>/requirements.md`

## Design stage

**Committee members:** PM lead, engineering lead, researcher

**Input:** Approved requirements from stage 1

**Procedure:**
1. Read the approved requirements document
2. Invoke `skills/research/` with architecture/design questions surfaced by requirements
3. Convene a committee with topic: "Design solution for: <goal> given these requirements"
4. Committee deliberates on architecture, data models, API contracts, component breakdown, technology choices
5. Merge into `skills/engineering-kiro/kiro/templates/design.template.md`
6. Fill template fields: architecture overview, data flow, API contracts, component responsibilities, technology decisions, trade-offs
7. Return `escalate_to_user` with the filled design document

**Output:** `<project>/.kiho/specs/<slug>/design.md`

## Tasks stage

**Committee members:** Engineering lead, QA IC (recruited via HR if not available)

**Input:** Approved requirements + design from stages 1-2

**Procedure:**
1. Read approved requirements and design documents
2. Convene a committee with topic: "Break down implementation tasks for: <goal>"
3. Committee deliberates on task granularity, ordering, dependencies, test coverage, edge cases
4. Merge into `skills/engineering-kiro/kiro/templates/tasks.template.md`
5. Fill template fields: ordered task list with descriptions, acceptance criteria per task, test requirements, dependency graph
6. Return `escalate_to_user` with the filled tasks document

**Output:** `<project>/.kiho/specs/<slug>/tasks.md`

## Gate protocol

Each stage gate is a user approval checkpoint. The CEO is the only agent authorized to present gates to the user (via `AskUserQuestion`). kiho-spec returns structured output to the CEO:

```json
{
  "status": "gate_pending",
  "stage": "requirements",
  "document_path": ".kiho/specs/auth-sso/requirements.md",
  "summary": "3 functional requirements, 2 non-functional, 5 user stories defined",
  "confidence": 0.91,
  "escalate_to_user": {
    "question": "Please review the requirements document for the SSO feature.",
    "document": "<full document content>",
    "options": ["approve", "reject with feedback"]
  }
}
```

On user approval: advance to the next stage.
On user rejection: the CEO passes feedback back to kiho-spec, which reconvenes the committee with the feedback injected.

## KB integration

After each stage gate is approved:

1. Call `kb-add` with `page_type: decision` for any architectural/technology decisions made during the stage
2. Call `kb-add` with `page_type: entity` for any new entities discovered (APIs, services, data models)
3. Call `kb-add` with `page_type: concept` for any design patterns or approaches chosen

This ensures that stage 2 benefits from stage 1's KB entries (mid-loop integration).

## Response shape

Final response after all three stages complete:

```json
{
  "status": "complete",
  "confidence": 0.93,
  "output_path": ".kiho/specs/<slug>/",
  "summary": "Spec complete: 3 requirements, design with 4 components, 12 implementation tasks",
  "spec_paths": {
    "requirements": ".kiho/specs/<slug>/requirements.md",
    "design": ".kiho/specs/<slug>/design.md",
    "tasks": ".kiho/specs/<slug>/tasks.md"
  },
  "contradictions_flagged": [],
  "new_questions": [],
  "skills_spawned": [],
  "escalate_to_user": null
}
```

## Anti-patterns

- Never skip a committee for any stage. Even if the brief seems simple, the committee forces multi-perspective review.
- Never advance past a gate without user approval. The gate ritual is sacred.
- Never run all three stages before presenting anything to the user. Present each stage individually.
- Never let kiho-spec call `AskUserQuestion` directly. Return `escalate_to_user` to the CEO.
