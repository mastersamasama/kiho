# RACI assignment protocol

RACI annotations clarify who does what for each task in `plan.md`. Every delegated task carries a RACI line immediately below it.

## Format

```markdown
- [ ] <task description>
  RACI: R=<agent-id> | A=<agent-id> | C=<agent-id> | I=<agent-id>
```

Multiple agents in a role are comma-separated:

```markdown
- [ ] Design the database schema
  RACI: R=eng-backend-ic-01 | A=eng-lead-01 | C=eng-backend-ic-02,pm-lead-01 | I=ceo-01
```

The RACI line is indented 2 spaces under its task. Do not place RACI on the same line as the checkbox.

## Assignment rules

### Responsible (R)

The agent performing the work. Selection criteria:

1. Query the capability matrix for the task's skill domain.
2. Select the agent with the highest proficiency score (>= 2 required).
3. If multiple agents tie, prefer the one with fewer active tasks (check plan.md for unchecked items assigned to them).
4. If no agent has proficiency >= 2, the task requires a hire or must be assigned to a lead as a stretch task.

One and only one R per task. Never leave R empty.

### Accountable (A)

The agent who approves the work. Assignment rule:

- A is always R's direct reporting lead.
- If R is a department lead, A is the CEO.
- If R is the CEO, A is also the CEO (self-accountable).

One and only one A per task.

### Consulted (C)

Agents providing input before or during the task. Assignment rules:

- Include agents from other departments whose domain overlaps with the task.
- Include agents with relevant memory entries (high-confidence lessons) about the task domain.
- C is optional. Omit if the task is self-contained.
- Do not include R's direct lead as C (that is A's role).

Zero or more C agents per task.

### Informed (I)

Agents who receive status updates after the task completes. Assignment rules:

- Always include the CEO unless the CEO is already R or A.
- Include agents blocked by this task's completion.
- I is passive — no action required from informed agents.

One or more I agents per task.

## Validation rules

Before finalizing a plan with RACI annotations, validate:

1. **R must exist.** The agent-id must appear in `org-registry.md` with status `active`.
2. **A must be R's lead.** Cross-reference org-registry.md to confirm the reporting relationship.
3. **No agent in more than 2 roles per task.** An agent can be R+A (when a lead does their own work) but not R+C+I.
4. **R proficiency >= 2.** Check capability-matrix.md. Tasks assigned to agents below proficiency 2 must have an explicit `stretch_assignment: true` note.
5. **No orphaned tasks.** Every task with a checkbox in plan.md must have a RACI line.

## Examples

### Implementation task

```markdown
- [ ] Build the REST API for user registration
  RACI: R=eng-backend-ic-01 | A=eng-lead-01 | C=pm-lead-01 | I=ceo-01
```

R is the backend IC with highest API proficiency. A is their engineering lead. C is the PM lead (owns the user stories). I is the CEO.

### Design review task

```markdown
- [ ] Review and approve the database schema design
  RACI: R=eng-lead-01 | A=ceo-01 | C=eng-backend-ic-01,eng-backend-ic-02 | I=pm-lead-01
```

R is the engineering lead (design authority). A is the CEO (approves architecture decisions). C is the backend ICs who will implement against the schema. I is the PM lead (needs to know the data model).

### Recruitment task

```markdown
- [ ] Hire a DevOps IC for the engineering department
  RACI: R=hr-lead-01 | A=ceo-01 | C=eng-lead-01 | I=pm-lead-01
```

R is HR (owns the hiring process). A is the CEO (approves headcount). C is the engineering lead (defines requirements). I is the PM lead (affected by timeline).
