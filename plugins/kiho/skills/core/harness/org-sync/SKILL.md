---
name: org-sync
description: Synchronizes the live org registry and capability matrix after workforce changes. Single writer for .kiho/state/org-registry.md and capability-matrix.md — no other skill or agent modifies these files directly. Triggers after agent hire, fire, reorg, team creation, team merge, or team split events. Reads the current registry, applies the structural change, recomputes affected capability matrix entries from performance data, and appends a Change Log entry. Use when the recruit skill completes a hire, when the CEO removes an agent, when departments restructure, or when teams are created/merged/split. Also triggers on "sync org", "update org registry", "refresh capability matrix", or "recompute proficiency".
metadata:
  trust-tier: T3
  version: 2.0.0
  lifecycle: active
  kiho:
    capability: update
    topic_tags: [state-management]
    data_classes: ["org-registry", "capability-matrix", "agent-performance"]
---
# org-sync

Applies workforce events to the org registry and recomputes the capability matrix. This skill is the **single writer** for `.kiho/state/org-registry.md` and `.kiho/state/capability-matrix.md` — no other skill or agent modifies these files directly. The single-writer discipline mirrors kiho's existing kb-manager-is-sole-KB-gateway invariant (see CLAUDE.md) and prevents change-log drift.

## When to use

Invoke this skill when:

- The `recruit` skill completes a hire (`event_type: hire`) and needs the new agent reflected in the registry
- The CEO decides to remove an agent (`event_type: fire`) after persistent underperformance or policy violation
- A department restructures — roles shift, agents move between departments, leads are promoted (`event_type: reorg`)
- A new team is created inside a department (`event_type: team_create`)
- Teams consolidate (`event_type: team_merge`) or split (`event_type: team_split`)
- The periodic CEO recomposition check determines capability matrix proficiency needs a full refresh (re-invoke without an event, which triggers recomputation-only mode)

Do NOT invoke this skill when:

- A skill rather than an agent is being created — `recruit` handles agents; skills route through `skill-create`, `skill-derive`, or `skill-improve`
- An agent's soul needs editing — `soul-apply-override` owns the soul mutation (and calls org-sync only for the agent_count refresh at its propagation step 10)
- A one-off task needs assignment without changing the workforce — delegate through the CEO's ledger, not through org-sync

## Non-Goals

org-sync is defined as much by what it refuses to do as by what it does.

- **Not a policy engine.** org-sync applies fire / reorg / restructure decisions; it does not *decide* to fire or reorg. Those decisions live with the CEO + HR lead (fire) or CEO + department leads (reorg). org-sync is mechanical.
- **Not a task reassigner.** When an agent is fired, their in-flight tasks in `plan.md` need reassignment. org-sync flags this in the response `warnings[]` but does not rewrite `plan.md` — that is the CEO's responsibility.
- **Not a runtime database.** Both `org-registry.md` and `capability-matrix.md` are markdown on disk. No SQLite, no Postgres, no vector store (CLAUDE.md Non-Goal). Any derived cache is regenerable from these files plus JSONL telemetry.
- **Not an event bus.** org-sync is called once per event — there is no queue, no consumer list, no retry-with-backoff. Callers (recruit, design-agent, soul-apply-override, CEO) invoke synchronously and receive the structured response.
- **Not a multi-project federator.** One project's `.kiho/state/` per invocation. Cross-project org federation is an F3 future possibility, not today's scope.
- **Not the Change Log sole auditor.** org-sync writes Change Log entries, but independent auditors (e.g., `kiho-auditor` in careful-hire recruitment, or `kb-lint`) read the log to detect anomalies. org-sync produces the audit trail; it does not interpret it.

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.

## Inputs

```
event_type:    hire | fire | reorg | team_create | team_merge | team_split
event_payload: <structured data for the event — see below>
project_root:  <path to project root, default: current working directory>
```

## Event types and payloads

### hire

```json
{
  "agent_id": "eng-backend-ic-02",
  "agent_definition": "agents/eng-backend-ic-02.md",
  "department": "eng",
  "team": "backend",
  "role": "Backend IC",
  "hired_by": "hr-lead-01",
  "approved_by": "ceo-01"
}
```

### fire

```json
{
  "agent_id": "eng-backend-ic-02",
  "department": "eng",
  "reason": "Persistent underperformance (success_rate < 0.40 over 20 tasks)",
  "fired_by": "ceo-01",
  "reassign_tasks_to": "eng-backend-ic-01"
}
```

### reorg

```json
{
  "changes": [
    {"action": "move", "agent_id": "eng-frontend-ic-01", "from_dept": "eng", "to_dept": "design"},
    {"action": "promote", "agent_id": "eng-backend-ic-01", "new_role": "Backend Team Lead"}
  ],
  "authorized_by": "ceo-01",
  "rationale": "Creating dedicated design department for v2 launch"
}
```

### team_create

```json
{
  "department": "eng",
  "team_name": "DevOps",
  "initial_members": ["eng-devops-ic-01"],
  "created_by": "eng-lead-01"
}
```

### team_merge

```json
{
  "department": "eng",
  "source_teams": ["backend", "api"],
  "target_team": "backend",
  "merged_by": "eng-lead-01"
}
```

### team_split

```json
{
  "department": "eng",
  "source_team": "backend",
  "new_teams": {
    "backend-core": ["eng-backend-ic-01"],
    "backend-infra": ["eng-backend-ic-02", "eng-devops-ic-01"]
  },
  "split_by": "eng-lead-01"
}
```

## Sync procedure

### Read current state

Read `.kiho/state/org-registry.md` and `.kiho/state/capability-matrix.md`. If either file does not exist, create it from the template (`templates/org-registry.template.md` or `templates/capability-matrix.template.md`).

### Apply the event

Based on `event_type`:

**hire:**
1. Add the agent to the specified department and team in org-registry.md.
2. Add a row to capability-matrix.md with all proficiency scores set to 1 (new agent, no track record).
3. Increment `agent_count` in frontmatter.

**fire:**
1. Remove the agent from org-registry.md.
2. Remove the agent's row from capability-matrix.md.
3. Decrement `agent_count` in frontmatter.
4. If `reassign_tasks_to` is set, note the reassignment in the Change Log.

**reorg:**
1. Apply each change in the `changes` array sequentially.
2. For `move`: remove from source department/team, add to target.
3. For `promote`: update the agent's role; if promoted to lead, update the department's lead field.

**team_create:**
1. Add the team section under the specified department.
2. List initial members.

**team_merge:**
1. Combine member lists from source teams into the target team.
2. Remove the dissolved source team sections (keep the target).

**team_split:**
1. Remove the source team section.
2. Create new team sections with their respective member lists.

### Update frontmatter

Set `last_modified` to the current ISO timestamp. Recount agents for `agent_count`.

### Append Change Log entry

Add a row to the Change Log table (format below).

### Recompute capability matrix

For affected agents (hired, fired, moved), recompute proficiency scores (see below).

### Write files

Write the updated `org-registry.md` and `capability-matrix.md` back to `.kiho/state/`.

## Capability matrix recomputation

Proficiency is computed per agent per skill domain. The formula:

```
proficiency = floor(1 + 4 * min(success_rate * log2(tasks + 1) / 5, 1.0))
```

Data sources:
- `.kiho/state/agent-performance.jsonl` — one JSON object per line: `{"agent_id": "...", "skill_domain": "...", "success": true, "timestamp": "..."}`
- `.kiho/state/skill-invocations.jsonl` — one JSON object per line: `{"agent_id": "...", "skill_name": "...", "success": true, "timestamp": "..."}`

Recomputation steps:

1. Read both JSONL files.
2. For each agent in the current org, group entries by skill domain.
3. Compute `success_rate` and `tasks` per domain.
4. Apply the formula.
5. Update the agent's row in capability-matrix.md.

For newly hired agents with no performance data, all proficiency scores default to 1.

The Python utility `bin/org_sync.py` performs this computation and can be invoked as a fallback when in-skill computation is impractical (e.g., hundreds of JSONL entries, full catalog recompute).

## Change Log entry format

```markdown
| 2026-04-11T14:00:00Z | hire | eng-backend-ic-02 added to Engineering/Backend; approved by ceo-01 |
```

Format: `| <ISO timestamp> | <event_type> | <freeform details> |`

Details **SHOULD** include the affected agent(s), the structural change, and who authorized the change.

## Worked examples

### Example 1 — quick-hire cascade (the common case)

Upstream invocation (from `recruit`):
```json
{
  "event_type": "hire",
  "event_payload": {
    "agent_id": "eng-backend-ic-02",
    "agent_definition": "agents/eng-backend-ic-02.md",
    "department": "eng",
    "team": "backend",
    "role": "Backend IC",
    "hired_by": "hr-lead-01",
    "approved_by": "ceo-01"
  }
}
```

Expected response:
```json
{
  "status": "ok",
  "event_type": "hire",
  "changes_applied": [
    "Added eng-backend-ic-02 to Engineering/Backend",
    "Capability matrix row added with default proficiency 1",
    "agent_count updated: 7 -> 8"
  ],
  "files_modified": [
    ".kiho/state/org-registry.md",
    ".kiho/state/capability-matrix.md"
  ],
  "warnings": []
}
```

Change Log row appended:
```
| 2026-04-16T09:24:31Z | hire | eng-backend-ic-02 added to Engineering/Backend; approved by ceo-01 |
```

### Example 2 — reorg with multi-change authorization

Invocation:
```json
{
  "event_type": "reorg",
  "event_payload": {
    "changes": [
      {"action": "move",    "agent_id": "eng-frontend-ic-01", "from_dept": "eng", "to_dept": "design"},
      {"action": "promote", "agent_id": "eng-backend-ic-01",  "new_role": "Backend Team Lead"}
    ],
    "authorized_by": "ceo-01",
    "rationale": "Creating dedicated design department for v2 launch"
  }
}
```

Expected response: `status: ok`, `changes_applied` lists both the move and the promotion; `warnings` empty unless the move would leave Engineering without a lead (in which case Route 3 in the Failure playbook fires).

### Example 3 — team_split with capability-matrix side effects

Invocation:
```json
{
  "event_type": "team_split",
  "event_payload": {
    "department": "eng",
    "source_team": "backend",
    "new_teams": {
      "backend-core":  ["eng-backend-ic-01"],
      "backend-infra": ["eng-backend-ic-02", "eng-devops-ic-01"]
    },
    "split_by": "eng-lead-01"
  }
}
```

Expected: org-registry team sections updated; capability-matrix unchanged (same agents, same skills — split is a structural relabel). Change Log shows `team_split: backend → backend-core + backend-infra`.

## Failure playbook

**Severity:** error (blocks state update).
**Impact:** registry and matrix left in pre-event state; calling skill (recruit / design-agent / soul-apply-override) does not see success.
**Taxonomy:** filesystem | invariant | telemetry | protocol.

### Decision tree

```
sync failure
    │
    ├─ .kiho/state/ dir missing                   → Route A (create from templates, retry)
    ├─ frontmatter parse fails                    → Route B (abort, CEO manually repairs)
    ├─ depth-cap or fanout-cap would be breached  → Route C (emit warning, abort event)
    ├─ department left with no lead post-reorg    → Route D (require explicit lead in payload)
    ├─ JSONL entry malformed during recompute     → Route E (skip line with warning; continue)
    └─ reassign_tasks_to target does not exist    → Route F (warn and queue for CEO)
```

### Route A — missing state directory

1. Read `templates/org-registry.template.md` and `templates/capability-matrix.template.md`.
2. Write fresh copies to `.kiho/state/org-registry.md` and `.kiho/state/capability-matrix.md` with `agent_count: 0`.
3. Retry the event from the top of the Sync procedure.

### Route B — frontmatter parse failure

1. Abort with `status: registry_corrupt`.
2. Emit the offending line number + unparseable content in the response.
3. **MUST NOT** auto-repair — that path corrupts the audit trail. CEO inspects and manually repairs.

### Route C — depth or fanout cap breach

1. Check against CLAUDE.md invariant: depth cap 3 (CEO → Dept → Team/IC), fanout cap 5.
2. If the event would push a team past 5 members or push organization depth past 3, emit `warnings: ["fanout_cap_exceeded" | "depth_cap_exceeded"]`.
3. Abort the event with `status: cap_exceeded`. The requesting skill (recruit) should split the team first.

### Route D — department without a lead

1. Post-reorg validation: every department **MUST** have exactly one lead field populated.
2. If the reorg empties a lead slot and the payload does not assign a replacement, abort with `status: department_without_lead`.
3. Upstream caller re-invokes with an explicit `promote` change pointing to the new lead.

### Route E — JSONL corruption during recompute

1. When parsing `agent-performance.jsonl` or `skill-invocations.jsonl`, skip any line that fails `json.loads`.
2. Emit `warnings: ["skipped_line_<N>_in_<file>"]` per skipped line.
3. Continue the recompute — partial data is acceptable; corruption of one line does not block the whole sync.

### Route F — reassignment target missing

1. If `fire` payload's `reassign_tasks_to` points to an agent not in the registry, abort with `status: reassign_target_not_found`.
2. Emit in `warnings[]` so the CEO sees it.
3. Caller re-invokes fire with a valid reassignment target OR accepts `reassign_tasks_to: null` and manually handles in `plan.md`.

## Response shape

```json
{
  "status": "ok | registry_corrupt | cap_exceeded | department_without_lead | reassign_target_not_found | error",
  "event_type": "hire",
  "changes_applied": [
    "Added eng-backend-ic-02 to Engineering/Backend",
    "Capability matrix row added with default proficiency 1",
    "agent_count updated: 7 -> 8"
  ],
  "files_modified": [
    ".kiho/state/org-registry.md",
    ".kiho/state/capability-matrix.md"
  ],
  "warnings": []
}
```

Warnings are emitted for:
- Firing an agent with active tasks (tasks **MUST** be reassigned)
- Reorg that leaves a department with no lead
- Team merge that produces a team exceeding the fanout cap (5 members)
- Hire that exceeds the depth cap (3 levels)
- JSONL entries skipped during recompute (Route E)

## Anti-patterns

- **MUST NOT** modify `org-registry.md` or `capability-matrix.md` outside of org-sync. All mutations flow through this skill to maintain Change Log integrity.
- **MUST NOT** skip the Change Log. Every event **MUST** produce a Change Log entry. The log is the audit trail for every organizational decision.
- **MUST NOT** auto-fire. org-sync applies fire events but does not initiate them. Only the CEO, with HR lead involvement, decides to fire.
- **MUST NOT** orphan tasks. When an agent is fired, their unchecked tasks in `plan.md` require reassignment. org-sync flags this in the response; the CEO handles the plan rewrite.
- Do not recompute the entire matrix on every event. Only recompute affected agents. A hire adds one row; a fire removes one. Full recomputation runs on the periodic 10-task CEO recomposition check, not on every event.
- Do not ignore the fanout cap. After team_merge or hire, verify no team exceeds 5 members. If it would, emit a warning and abort — the lead should split the team.

## Rejected alternatives

### A1 — SQLite index for the capability matrix

**What it would look like.** Replace `capability-matrix.md` with a SQLite database; org-sync reads/writes via SQL.

**Rejected because.** CLAUDE.md explicitly rejects runtime databases: *"All kiho state is markdown or JSON on disk. Any sqlite index is a regenerable optimization, never a source of truth. No Postgres, no vector store, no DAG scheduler database."* Markdown is the canonical format so humans and kb-manager can read the matrix without a tool. A SQLite index can still exist as a *derived* cache rebuilt from the markdown — it must not be the source of truth.

**Source.** CLAUDE.md §Non-Goals "Not a runtime database"; same §"Markdown canonical" invariant that kb-manager depends on.

### A2 — Auto-fire policy engine based on underperformance thresholds

**What it would look like.** org-sync watches `agent-performance.jsonl` in the background; when an agent's 20-task rolling success_rate drops below 0.40, it auto-emits a `fire` event.

**Rejected because.** CLAUDE.md §"CEO-only user interaction" restricts autonomous destructive actions. Firing an agent is a *social decision* that needs HR lead involvement + CEO approval + rationale that the Change Log can audit. An automated threshold would blind-side department leads and produce Change Log entries with no human reasoning attached — defeating the audit trail's purpose. org-sync stays mechanical; the policy lives upstream.

**Source.** CLAUDE.md §Invariants "CEO-only user interaction"; Anti-patterns §"Auto-firing".

### A3 — Kubernetes-style controller loop

**What it would look like.** org-sync becomes a long-running process that watches `.kiho/state/` for changes and reconciles the registry against a declarative desired-state YAML.

**Rejected because.** CLAUDE.md §"Not a container orchestrator": *"'Department' and 'team' are metaphors for agent hierarchy, not processes. No Docker, no Kubernetes, no deployment manifests."* The controller pattern is genuinely useful at scale but introduces a runtime daemon, a reconciliation queue, and watch-loop state — none of which fit kiho's synchronous-markdown model. The mechanical-per-event design covers every known workflow at current catalog scale.

**Source.** CLAUDE.md Non-Goals §"Not a container orchestrator"; kiho v4 synchronous-call design.

### A4 — Event sourcing with full replay log

**What it would look like.** Instead of mutating `org-registry.md` directly, org-sync appends every event to a `.kiho/state/org-events.jsonl` append-only log and derives the registry on demand via replay.

**Rejected because.** Martin Fowler's classic Event Sourcing write-up identifies the pattern's trade-off: *"you must be able to reconstruct the application state at any point in the past."* kiho never needs this — the Change Log inside `org-registry.md` is a human-readable "why did this change happen" audit, not a replay-forward mechanism. A parallel events log would double-write state and double the surface for drift between the log and the rendered registry. The current append-Change-Log-row pattern is a lighter version of event-sourcing's audit benefit without the replay overhead.

**Source.** Martin Fowler, "Event Sourcing" (2005) — https://martinfowler.com/eaaDev/EventSourcing.html; kiho v4 synchronous-write design.

## Future possibilities

Non-binding sketches per RFC 2561. Nothing in this section is a commitment; triggers, scope, and timelines may all change.

### F1 — Event-sourced replay for debugging

**Trigger condition.** ≥3 reported incidents where "the Change Log says X happened but the registry state doesn't match" — a silent drift bug.

**Sketch.** Add `bin/org_sync_replay.py` that reads the Change Log table back into structured events and re-applies them to a fresh registry, then diffs against the current registry. Drift is reported for manual repair. This is event-sourcing *as a debugger*, not *as a source of truth* — addresses the failure mode without the A4 downsides.

### F2 — `--dry-run` mode

**Trigger condition.** HR lead reports "I hired 3 candidates and 1 had a payload typo that corrupted the registry; I want to preview changes before they commit."

**Sketch.** `event_payload.dry_run: true` flag causes org-sync to compute and return `changes_applied[]` + `warnings[]` without writing to disk. Caller reviews the planned diff and re-invokes without the flag to commit. Zero state mutation in dry-run mode.

### F3 — Cross-project org federation

**Trigger condition.** The same agent (e.g., a shared `kb-manager`) needs to appear in multiple project registries, and keeping them in sync manually creates divergence.

**Sketch.** A `$COMPANY_ROOT/org-registry.md` shared index; project registries reference federated agents by ID. org-sync gains a federated-mode that reads both the project and company registries. Depends on `$COMPANY_ROOT` being populated (see `kiho-setup`).

## Grounding

- **Single-writer discipline.**
  > **CLAUDE.md §Invariants:** *"kb-manager is the sole KB gateway. All KB reads and writes go through the kiho-kb-manager sub-agent."*
  org-sync applies the same discipline to org-registry + capability-matrix: one writer, mechanical per-event, Change Log as audit trail. Direct analogue, not a copy.

- **Markdown-canonical state (grounds rejection of A1 SQLite index).**
  > **CLAUDE.md §Non-Goals:** *"Not a runtime database. All kiho state is markdown or JSON on disk. Any sqlite index is a regenerable optimization, never a source of truth."*
  Drives the choice of `.md` files with frontmatter over any DB-backed schema.

- **Not-a-container-orchestrator (grounds rejection of A3 controller loop).**
  > **CLAUDE.md §Non-Goals:** *"Not a container orchestrator. 'Department' and 'team' are metaphors for agent hierarchy, not processes."*
  Keeps org-sync synchronous and per-event rather than a watch-reconcile daemon.

- **Event sourcing trade-off (grounds rejection of A4 full replay log).**
  Martin Fowler, *Event Sourcing* (2005) — the canonical reference that the benefit (full replayability) comes paired with doubled-write complexity. kiho's Change Log captures the audit benefit without the double-write. https://martinfowler.com/eaaDev/EventSourcing.html

- **CEO-only destructive action (grounds rejection of A2 auto-fire).**
  > **CLAUDE.md §Invariants:** *"CEO-only user interaction. Only the CEO agent running in the main conversation may call AskUserQuestion."*
  Firing is a destructive social decision that **MUST** have human authorization; org-sync applies but does not decide.
