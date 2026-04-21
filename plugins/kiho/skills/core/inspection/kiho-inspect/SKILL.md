---
name: kiho-inspect
description: Developer debug and inspection tool for the kiho system. Provides sub-commands to inspect the organization state — org chart, open/closed committees, current plan, KB statistics (page count, index status, lint summary), and cached research. Use when debugging kiho behavior, when the user wants visibility into internal state, or when the CEO needs a system health check. Triggers on "kiho inspect", "show org chart", "list committees", "show plan", "kb stats", "what research do we have", "kiho status", "system health".
metadata:
  trust-tier: T2
  kiho:
    capability: read
    topic_tags: [observability]
    data_classes: ["org-registry", "capability-matrix", "agent-performance"]
---
# kiho-inspect

A read-only inspection tool for kiho's internal state. All sub-commands are non-destructive — they read and report but never modify.

> **kb-manager bypass is sanctioned only here.** CLAUDE.md's "kb-manager is the sole KB gateway" invariant applies to **authoritative committee or delegation work** — readings that inform decisions, citations, or writes. `kiho-inspect kb` and `kiho-inspect research` deliberately read `.kiho/kb/` raw disk state so operators can diagnose drift, staleness, or kb-manager failure itself. These sub-commands return **raw counts and file paths, not synthesized answers**; any agent that needs an authoritative KB read for a decision MUST route through `kb-manager` (`kb-search` sub-skill). Do not copy this bypass pattern into any other skill.

## Contents
- [Sub-commands](#sub-commands)
- [org — Organization chart](#org)
- [committees — Committee listing](#committees)
- [plan — Current plan](#plan)
- [kb — Knowledge base stats](#kb)
- [research — Cached research](#research)
- [Response shape](#response-shape)

## Sub-commands

| Command | Purpose |
|---|---|
| `org` | Print the current org chart with agents, departments, and hierarchy |
| `committees` | List all open and closed committees with status |
| `plan` | Show the current plan.md contents |
| `kb` | Show KB statistics — page count, index status, lint summary |
| `research` | Show cached research from previous sessions |
| `capability-matrix` | Display the capability matrix with agent proficiencies |
| `performance` | Show per-agent performance summary from tracking data |
| `management-journal <leader-id>` | Display a department leader's management journal |

## org

Read all agent .md files from `agents/` and `agents/_templates/`. Extract frontmatter and build a hierarchy.

Output format:
```markdown
## Organization chart

### CEO
- **kiho-ceo** (opus) — main orchestrator

### Department leads
- **kiho-eng-lead** (sonnet) — engineering
- **kiho-pm-lead** (sonnet) — product
- **kiho-hr-lead** (sonnet) — HR

### Engineering ICs
- **eng-frontend-ic** (sonnet) — template
- **eng-backend-ic** (sonnet) — template
- **eng-qa-ic** (sonnet) — template

### PM ICs
- **pm-ic** (sonnet) — template

### HR ICs
- **hr-ic** (sonnet) — template

### Support
- **kiho-kb-manager** (sonnet) — KB gateway
- **kiho-researcher** (sonnet) — research cascade
- **kiho-clerk** (sonnet) — committee extraction
- **kiho-auditor** (sonnet) — hiring review

**Total agents:** 12 (3 leads, 5 IC templates, 4 support)
```

## committees

Glob `<project>/.kiho/committees/*/index.md`. Read each index.md frontmatter.

Output format:
```markdown
## Committees

### Open
| ID | Topic | Members | Round | Created |
|---|---|---|---|---|
| 2026-04-11-auth | Which auth provider? | eng, pm, researcher | 1/3 | 2026-04-11 |

### Closed (consensus)
| ID | Topic | Decision | Confidence | Rounds |
|---|---|---|---|---|
| 2026-04-10-cache | Caching strategy? | Use Redis | 0.93 | 2 |

### Escalated
| ID | Topic | Reason | Rounds |
|---|---|---|---|
| (none) | | | |
```

## plan

Read `<project>/.kiho/state/plan.md`. Display its contents grouped by status.

Output format:
```markdown
## Current plan

### Pending (3 items)
1. [P0] Implement user login — assigned: eng-lead
2. [P1] Set up CI pipeline — assigned: eng-lead
3. [P2] Write user docs — unassigned

### In progress (1 item)
1. Design auth flow — assigned: eng-lead, round 2

### Completed (5 items)
1. Bootstrap KB — completed 2026-04-10
2. ...

### Blocked (0 items)
(none)
```

If `plan.md` does not exist, report "No active plan. Run /kiho to create one."

## kb

Read the KB structure and compute statistics.

1. Glob `<project>/.kiho/kb/wiki/**/*.md` — count pages by type
2. Read `<project>/.kiho/kb/index.md` — check last updated timestamp
3. Read `<project>/.kiho/kb/log.md` last 5 entries — recent activity
4. Run a quick lint check (if `kb-lint` is available) or count known issues

Output format:
```markdown
## KB statistics

**Tier:** project
**Root:** .kiho/kb/

### Page counts
| Type | Count |
|---|---|
| entities | 12 |
| concepts | 8 |
| decisions | 5 |
| conventions | 3 |
| synthesis | 1 |
| questions | 2 |
| principles | 4 |
| rubrics | 1 |
| **Total** | **36** |

### Index status
- index.md: last updated 2026-04-11T14:00:00Z
- tags.md: 24 unique tags
- backlinks.md: 89 edges
- open-questions.md: 2 unresolved

### Recent activity (last 5)
1. [2026-04-11T14:00:00Z] add — decision: auth-provider
2. [2026-04-11T13:30:00Z] add — entity: firebase
3. ...

### Lint summary
- Warnings: 2 (orphaned pages)
- Errors: 0
```

If the KB does not exist, report "KB not initialized. Run /kiho init to bootstrap."

## research

Glob `<project>/.kiho/research/` and `<project>/.kiho/kb/raw/`. List cached research with metadata.

Output format:
```markdown
## Cached research

### Web research
| Query | Date | Source | Pages |
|---|---|---|---|
| "Firebase Auth pricing" | 2026-04-11 | web | 3 |
| "Auth0 vs Firebase" | 2026-04-11 | web | 5 |

### DeepWiki queries
| Repo | Topic | Date |
|---|---|---|
| auth0/nextjs-auth0 | setup guide | 2026-04-10 |

### Raw ingested files
| File | Type | Ingested |
|---|---|---|
| prd-sso-feature.md | PRD | 2026-04-10 |

**Total cached items:** 4
```

## capability-matrix

Read `<project>/.kiho/state/capability-matrix.md`. Display its contents — the matrix maps skills to agents with proficiency levels.

Output format:
```markdown
## Capability matrix

| Skill | Agent | Proficiency (1-5) | Last used |
|---|---|---|---|
| frontend-react | eng-frontend-ic | 4 | 2026-04-11 |
| backend-node | eng-backend-ic | 5 | 2026-04-12 |
| qa-testing | eng-qa-ic | 3 | 2026-04-10 |

**Coverage gaps:** skills with no agent at proficiency >= 3
- infrastructure-aws (max proficiency: 1)
```

If `capability-matrix.md` does not exist, report "Capability matrix not initialized. Run /kiho setup to scaffold."

## performance

Read `<project>/.kiho/state/agent-performance.jsonl`. Parse all entries and compute per-agent summary statistics.

Each JSONL entry has the shape: `{ "ts": "<iso>", "agent_id": "<name>", "task_id": "<id>", "success": true|false, "confidence": 0.0-1.0, "duration_ms": N }`

Output format:
```markdown
## Agent performance summary

| Agent | Tasks | Success rate | Avg confidence | Last active |
|---|---|---|---|---|
| eng-frontend-ic | 12 | 0.92 | 0.88 | 2026-04-12 |
| eng-backend-ic | 8 | 0.75 | 0.82 | 2026-04-11 |
| pm-ic | 5 | 1.00 | 0.91 | 2026-04-12 |

**Agents below 0.70 success rate:** (flagged for review)
- (none)
```

If `agent-performance.jsonl` does not exist or is empty, report "No performance data yet. Data is recorded by the CEO during Ralph loop iterations."

## management-journal

Read `<project>/.kiho/state/management-journals/<leader-id>.md`. Display the journal contents for the specified department leader.

Usage: `kiho inspect management-journal <leader-id>` (e.g., `kiho inspect management-journal kiho-eng-lead`)

Output: the raw markdown contents of the journal file.

If the journal file does not exist, report "No management journal found for <leader-id>. Journals are created when department leaders record management observations."

## Response shape

All sub-commands return markdown directly to the caller. No structured JSON — this is a human-readable inspection tool.

If invoked without a sub-command, display the sub-command list and ask which one to run.
