# Org tracking protocol

The live org registry and capability matrix track the current state of kiho's agent workforce — who exists, what they can do, and how well they perform. These files are the source of truth for delegation decisions, recruitment triggers, and recomposition.

> **v5.20 dual-format plan (deferred).** The authoritative source of truth for these structures is slated to flip from markdown-first to JSONL-first: `state/org/org-registry.jsonl` + `state/org/capability-matrix.jsonl` become the canonical write surface, and the existing `.kiho/state/org-registry.md` + `.kiho/state/capability-matrix.md` become regenerable views rendered by `bin/org_sync.py --render`. RACI queries (currently grep over md) would then dispatch via `storage-broker` against JSONL. The change is documented here but the org_sync.py refactor has NOT yet landed in v5.20; the md files remain authoritative. Re-audit when RACI query latency becomes material (capability-matrix rows exceed ~500 or per-delegation scan time exceeds 100 ms).

## Contents
- [org-registry.md format](#org-registrymd-format)
- [When org-registry updates](#when-org-registry-updates)
- [Capability matrix format](#capability-matrix-format)
- [Proficiency formula](#proficiency-formula)
- [Management journal format](#management-journal-format)
- [Auto-recomposition trigger](#auto-recomposition-trigger)
- [RACI annotation overview](#raci-annotation-overview)

## org-registry.md format

Location: `.kiho/state/org-registry.md`

The file uses YAML frontmatter for machine-readable metadata followed by markdown sections for human-readable structure.

```yaml
---
project_slug: my-saas-app
agent_count: 7
last_modified: 2026-04-11T14:00:00Z
schema_version: 1
---
```

### Markdown sections

```markdown
# Org Registry — {{project_slug}}

## CEO
- **Agent:** ceo-01
- **Definition:** agents/kiho-ceo.md
- **Status:** active

## Departments

### Product Management
- **Lead:** pm-lead-01 (agents/kiho-pm-lead.md)
- **Status:** active
- **Direct reports:**
  - pm-ic-01 — product analyst (active)

### Engineering
- **Lead:** eng-lead-01 (agents/kiho-eng-lead.md)
- **Status:** active
- **Teams:**
  - **Backend** — eng-backend-ic-01, eng-backend-ic-02
  - **Frontend** — eng-frontend-ic-01
- **Direct reports:** (none — all ICs are in teams)

### Human Resources
- **Lead:** hr-lead-01 (agents/kiho-hr-lead.md)
- **Status:** active
- **Direct reports:**
  - hr-ic-01 — recruiter (active)

## Shared Services
- **kb-manager:** kb-manager-01 (agents/kiho-kb-manager.md) — active
- **researcher:** researcher-01 (agents/kiho-researcher.md) — active

## Change Log
| Timestamp | Event | Details |
|---|---|---|
| 2026-04-11T14:00:00Z | hire | eng-backend-ic-02 added to Engineering/Backend |
| 2026-04-10T09:00:00Z | team_create | Backend team created under Engineering |
| 2026-04-09T10:00:00Z | bootstrap | Initial org created with 3 departments |
```

### Section rules

- **CEO** is always a single entry. Never plural.
- **Departments** contain a lead, optional teams, and optional direct reports. Teams contain only ICs.
- **Shared Services** lists agents that serve all departments (kb-manager, researcher, auditor, clerk).
- **Change Log** is append-only, newest first. Each row has ISO timestamp, event type, and freeform details.

## When org-registry updates

The org-sync skill (`skills/core/harness/org-sync/SKILL.md`) updates org-registry.md after these events:

| Event | Trigger | Registry change |
|---|---|---|
| `hire` | recruit skill completes, CEO approves | Add agent to department/team; increment agent_count |
| `fire` | CEO or HR lead removes an agent | Remove agent; decrement agent_count; mark tasks for reassignment |
| `reorg` | CEO restructures departments | Move agents between departments/teams; update leads |
| `team_create` | Department lead creates a sub-team | Add team section under department |
| `team_merge` | Department lead consolidates teams | Merge member lists; remove dissolved team section |
| `team_split` | Department lead divides a team | Create new team sections; redistribute members |

Every event also:
1. Appends a Change Log row.
2. Updates the `last_modified` and `agent_count` frontmatter fields.
3. Triggers a capability matrix recomputation for affected agents.

## Capability matrix format

Location: `.kiho/state/capability-matrix.md`

The capability matrix maps agents to skill domains with proficiency scores.

```yaml
---
project_slug: my-saas-app
last_recomputed: 2026-04-11T14:30:00Z
schema_version: 1
---
```

```markdown
# Capability Matrix

| Agent | TypeScript | Python | React | DevOps | Testing | Research | Writing |
|---|---|---|---|---|---|---|---|
| eng-lead-01 | 4 | 3 | 3 | 4 | 4 | 2 | 3 |
| eng-backend-ic-01 | 5 | 4 | 1 | 3 | 4 | 1 | 1 |
| eng-frontend-ic-01 | 5 | 1 | 5 | 1 | 3 | 1 | 2 |
| pm-lead-01 | 1 | 1 | 1 | 1 | 1 | 4 | 5 |
```

Proficiency scores range from 1 (no demonstrated ability) to 5 (expert with high success rate).

## Proficiency formula

Proficiency is computed from task completion data:

```
proficiency = floor(1 + 4 * min(success_rate * log2(tasks + 1) / 5, 1.0))
```

Where:
- `success_rate` = number of successful task completions / total task attempts in the skill domain
- `tasks` = total task attempts in the skill domain
- `log2(tasks + 1) / 5` is a volume scaling factor — an agent needs ~31 tasks (`log2(32) = 5`) at 100% success to reach proficiency 5

**Examples:**

| success_rate | tasks | log2(tasks+1)/5 | raw | proficiency |
|---|---|---|---|---|
| 1.00 | 1 | 0.20 | 1.80 | 1 |
| 1.00 | 7 | 0.60 | 3.40 | 3 |
| 1.00 | 31 | 1.00 | 5.00 | 5 |
| 0.80 | 15 | 0.80 | 3.56 | 3 |
| 0.50 | 31 | 1.00 | 3.00 | 3 |
| 0.50 | 7 | 0.60 | 2.20 | 2 |

Data sources:
- `.kiho/state/agent-performance.jsonl` — one JSON line per completed task with `agent_id`, `skill_domain`, `success` (boolean), `timestamp`
- `.kiho/state/skill-invocations.jsonl` — one JSON line per skill invocation with `agent_id`, `skill_name`, `success`, `timestamp`

## Management journal format

Location: `.kiho/state/management-journals/<leader-agent-id>.md`

Each department leader and the CEO maintain a management journal for tracking delegation decisions, strategy experiments, and team performance.

```yaml
---
agent_id: eng-lead-01
role: Engineering Lead
last_updated: 2026-04-11T15:00:00Z
---
```

### Delegation decisions

```markdown
## Delegation decisions

| Date | Task | Assigned to | Rationale | Outcome |
|---|---|---|---|---|
| 2026-04-11 | Implement auth flow | eng-backend-ic-01 | Highest TypeScript proficiency (5) | success |
| 2026-04-10 | Set up CI pipeline | eng-backend-ic-02 | DevOps proficiency (3), growth opportunity | pending |
```

### Strategy experiments

```markdown
## Strategy experiments

| Date | Hypothesis | Experiment | Result | Decision |
|---|---|---|---|---|
| 2026-04-09 | Pair programming reduces bugs | Paired eng-backend-ic-01 + eng-frontend-ic-01 on API integration | Bug rate dropped 40% | Continue pairing for cross-stack tasks |
```

### OKR progress

```markdown
## OKR progress

| Objective | Key result | Current | Target | Status |
|---|---|---|---|---|
| Ship v1 by April 30 | Core features complete | 7/10 | 10/10 | on-track |
| Ship v1 by April 30 | Test coverage > 80% | 72% | 80% | at-risk |
```

### Team performance summary

```markdown
## Team performance summary

| Agent | Tasks completed | Success rate | Avg time | Trend |
|---|---|---|---|---|
| eng-backend-ic-01 | 12 | 0.92 | 14 min | improving |
| eng-frontend-ic-01 | 8 | 0.88 | 18 min | stable |
```

## Auto-recomposition trigger

Every 10 completed tasks, the CEO performs a recomposition check:

1. Read the capability matrix and management journal.
2. Identify agents with success rates below 0.60 over the last 10 tasks.
3. Identify skill domains with no agent above proficiency 2.
4. If underperformance or skill gaps are found:
   - Consider reassigning tasks to better-suited agents.
   - Consider hiring a new IC via the recruit skill.
   - Consider team restructuring via org-sync with `event_type=reorg`.
5. Log the recomposition decision in the CEO's management journal under Strategy experiments.

The CEO does not auto-fire underperforming agents. Firing requires explicit justification and HR lead involvement.

## RACI annotation overview

Tasks in `plan.md` can carry RACI annotations to clarify responsibility. The full specification is in `references/raci-assignment-protocol.md`. In summary:

- **R** (Responsible) — the agent doing the work. Selected from the capability matrix.
- **A** (Accountable) — the agent who approves/reviews. Always R's reporting lead.
- **C** (Consulted) — cross-department agents providing input.
- **I** (Informed) — the CEO or other stakeholders who receive status updates.

RACI annotations appear on the line below each task in `plan.md`:

```markdown
- [ ] Implement user authentication
  RACI: R=eng-backend-ic-01 | A=eng-lead-01 | C=pm-lead-01 | I=ceo-01
```
