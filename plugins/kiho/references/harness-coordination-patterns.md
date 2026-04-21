# Harness coordination patterns — offline reference

Offline excerpt of the six coordination patterns from revfactory/harness, adapted for kiho's multi-agent orchestration. The CEO selects a pattern at the PLAN THIS ITEM step of each Ralph loop iteration.

## Contents
- [Pattern catalog](#pattern-catalog)
- [Pipeline](#pipeline)
- [Fan-out / Fan-in](#fan-out--fan-in)
- [Expert Pool](#expert-pool)
- [Producer-Reviewer](#producer-reviewer)
- [Supervisor](#supervisor)
- [Hierarchical Delegation](#hierarchical-delegation)
- [Selection guide](#selection-guide)

## Pattern catalog

| Pattern | Shape | Agents | Use when |
|---|---|---|---|
| Pipeline | A → B → C | 2-5 sequential | Each stage depends on the prior stage's output |
| Fan-out/Fan-in | A → [B,C,D] → E | 1 coordinator + 2-5 workers | Independent subtasks that combine into one result |
| Expert Pool | Router → best-fit expert | 1 router + N experts | Ambiguous request needs the right specialist |
| Producer-Reviewer | A ↔ B (loop) | 2 (producer + reviewer) | Quality requires iterative feedback |
| Supervisor | S → [dynamic] | 1 supervisor + N workers | Plan evolves as work proceeds |
| Hierarchical Delegation | A → B → C (recursive) | 2-3 levels | Large goal broken into subgoals at each level |

## Pipeline

**Shape:** Sequential stages where each stage's output is the next stage's input.

```
Stage 1 (requirements) → Stage 2 (design) → Stage 3 (tasks)
```

**When to use:**
- The work has natural sequential dependencies
- Each stage adds value that the next stage needs
- Parallelization is not possible because later work depends on earlier decisions

**kiho application:** The kiro spec ritual (requirements → design → tasks) is a pipeline. Each stage gates the next. The CEO does not run stages in parallel because design depends on approved requirements.

**Implementation:**
1. CEO creates a brief for stage 1 and delegates
2. Stage 1 agent returns result; CEO verifies
3. CEO creates a brief for stage 2, including stage 1 output as context
4. Repeat until all stages complete

**Pitfall:** Pipelines are slow because they serialize everything. Only use when dependencies genuinely require it. If two stages can work independently, prefer Fan-out/Fan-in.

## Fan-out / Fan-in

**Shape:** One coordinator splits work into independent subtasks, workers execute in parallel (conceptually), coordinator merges results.

```
CEO → [Researcher A, Researcher B, Researcher C] → CEO merges
```

**When to use:**
- Multiple independent subtasks contribute to one deliverable
- Each subtask can be completed without knowing the others' results
- Results need to be merged, deduplicated, or synthesized

**kiho application:** Research across multiple sources (KB, web, deepwiki). Multi-file analysis where each file is independent. Cross-department review where each department evaluates independently.

**Implementation:**
1. CEO writes N briefs, one per subtask
2. Spawns N subagents (respecting fanout cap of 5)
3. Collects all results
4. Merges/synthesizes into a single deliverable
5. If results conflict, convene a committee to resolve

**Pitfall:** Merging is the hard part. Plan the merge strategy before fanning out. If merge requires judgment (not just concatenation), consider a committee for the merge step.

## Expert Pool

**Shape:** A router analyzes the request and delegates to the best-fit expert.

```
CEO analyzes → routes to PM-lead (product question)
CEO analyzes → routes to Eng-lead (technical question)
CEO analyzes → routes to HR-lead (staffing question)
```

**When to use:**
- The request is ambiguous about which domain it falls into
- Multiple experts exist but only one is needed
- Routing logic can be expressed as a decision tree

**kiho application:** When the user's /kiho request is not clearly a spec, research, or committee task, the CEO acts as the router, analyzing the request and routing to the appropriate department.

**Implementation:**
1. CEO reads the request and classifies it
2. Selects the best-fit department leader or skill
3. Delegates with a brief
4. If the expert returns "wrong expert" (the task is outside their domain), re-route

**Pitfall:** Do not over-route. If the request clearly fits one domain, delegate directly without a routing analysis step.

## Producer-Reviewer

**Shape:** One agent produces output, another reviews it, producer revises based on feedback, loop until quality threshold met.

```
IC produces → QA reviews → IC revises → QA re-reviews → accept
```

**When to use:**
- Output quality is critical and hard to achieve in one shot
- A separate perspective (reviewer) catches issues the producer misses
- Iteration is expected (not a sign of failure)

**kiho application:** Any spec stage with QA review. Code implementation where the engineering lead reviews the IC's work. Requirements where the PM lead reviews the PM IC's stories.

**Implementation:**
1. Producer agent creates the deliverable
2. Reviewer agent evaluates against criteria
3. If reviewer approves: done
4. If reviewer flags issues: producer receives feedback and revises
5. Maximum 3 revision cycles; if still not approved, escalate to the department lead

**Pitfall:** Cap the revision cycles. Infinite loops between producer and reviewer waste budget. After 3 cycles, the issue is likely a specification problem, not an execution problem.

## Supervisor

**Shape:** One supervisor agent dynamically assigns tasks to workers based on evolving state.

```
Supervisor reads state → assigns Task A to Worker 1
Worker 1 completes → Supervisor reads new state → assigns Task B to Worker 2
(tasks are not predetermined — supervisor decides based on current state)
```

**When to use:**
- The work plan evolves as you learn more
- Tasks cannot all be identified upfront
- Dynamic task assignment based on intermediate results

**kiho application:** PRD-driven work where the plan evolves as the CEO learns more about the codebase and requirements. The CEO acts as the supervisor, reading plan.md after each iteration and deciding the next task.

**Implementation:** This is the CEO's Ralph loop itself — EXAMINE, PLAN, DELEGATE, VERIFY, INTEGRATE, UPDATE is a supervisor pattern.

**Pitfall:** Supervisors must avoid micromanagement. Delegate whole tasks, not individual steps. If you find yourself issuing one-line instructions to workers, the tasks are too granular.

## Hierarchical Delegation

**Shape:** Each level breaks its goal into subgoals and delegates to the next level.

```
CEO → Eng-lead (build auth feature)
  Eng-lead → Frontend-IC (build login UI)
  Eng-lead → Backend-IC (build auth API)
  Eng-lead → QA-IC (write auth tests)
```

**When to use:**
- The goal is too large for one agent
- Natural decomposition exists at each level
- Subgoals are relatively independent within each level

**kiho application:** Large features where the CEO delegates to a department lead, who decomposes into IC-level tasks. This is the standard kiho delegation pattern for feature work.

**Implementation:**
1. CEO writes a brief for the department lead
2. Department lead decomposes into IC-level tasks
3. Department lead spawns ICs with task-specific briefs
4. Department lead collects IC results and merges
5. Department lead returns merged result to CEO

**Pitfall:** Respect the depth cap (CEO → Lead → IC = 3 levels max). Never go deeper. If an IC needs to delegate, the task decomposition was wrong — restructure at the lead level.

## Selection guide

At the CEO's PLAN THIS ITEM step, select the pattern:

| Situation | Pattern |
|---|---|
| Work has sequential dependencies (stage N needs stage N-1 output) | Pipeline |
| Multiple independent research/analysis tasks | Fan-out/Fan-in |
| Request is ambiguous about which department handles it | Expert Pool |
| Output requires iteration and feedback | Producer-Reviewer |
| Work plan is dynamic and evolves | Supervisor |
| Large goal decomposes into department-level subgoals | Hierarchical Delegation |
| Decision needs multiple perspectives with consensus | Committee (not a harness pattern — use the committee skill) |

Record the chosen pattern in the brief so the delegated agent understands the coordination shape.
