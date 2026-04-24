---
name: onboard
description: Use this skill the moment a new agent ships from the recruit pipeline. Wraps the new IC in a 3-iteration ramp-up — pairs them with a department mentor, hands them a curated toy task, schedules a first-90-day brief, and logs an onboarding-note to their memory. Without onboarding, fresh agents jump straight from hire-day into production work, which the v5.20 retro showed costs ~1 turn of mentor unblocking per skill the new agent doesn't yet understand. Triggers on "onboard <agent>", "ramp up <new-agent>", or auto-fires from recruit's `op=hire` success path. Reads agent-md, capability-matrix, and hires the IC into a paired task with their mentor for the first 3 iterations.
metadata:
  trust-tier: T2
  kiho:
    capability: create
    topic_tags: [coordination, lifecycle]
    data_classes: [agent-md, capability-matrix, todos]
---
# onboard

The 3-iteration ramp-up that bridges hire-day to first independent task. Recruit ships a competent persona; onboard makes that persona productive *here*. Both are required; hiring without onboarding teaches the org that fresh agents fail their first task by design.

> **v5.21 cycle-aware.** This skill is the `onboard` phase entry in `references/cycle-templates/talent-acquisition.toml` AND `references/cycle-templates/onboarding-cycle.toml` (planned). When run from cycle-runner, the cycle's `index.toml` already carries `index.recruit.winner`; this skill writes `onboarding_note_ref` and `status` back into `index.onboard.*`. Atomic invocation remains supported for transfer-onboarding (existing agent moving departments).

## When to use

- Auto-fires after `recruit op=hire` returns `status: ok` with the new agent's path
- Manually: `/kiho onboard <agent_id>` after a transferred agent joins a new department
- After `agent-promote` moves an IC to lead — re-onboard the lead into their new responsibilities

Do **NOT** invoke when:

- The agent has run ≥ 5 successful tasks in this department already (already onboarded)
- The user is in the middle of a feature flow that needs the new agent immediately — escalate the scope conflict to CEO instead

## Inputs

```
agent_id: <new-agent-id>          # required
mentor_id: <existing-agent-id>    # optional; defaults to dept-lead-of(agent_id)
toy_task: <one-line description>  # optional; defaults to a department-curated task
ramp_iterations: <int>            # default 3; min 2, max 5
first_90_day_brief: <bool>        # default true
```

## Procedure

1. **Resolve mentor.** If not provided, look up `agent_id`'s dept lead from `.kiho/state/org-registry.md`. If the new agent IS the lead, the mentor is the CEO.

2. **Pick a toy task.** If not provided, query `state/onboarding-tasks/<dept>/` for a curated task list. The toy task MUST be:
   - Reversible (no production writes, no irreversible KB changes)
   - Bounded (1 iteration, ≤ 30 minutes)
   - Touched by ≥ 2 of the agent's portfolio skills (so they exercise their tools)
   - Not on the critical path for any open user request

3. **Pair execution for `ramp_iterations` iterations.** For each ramp iteration:
   - Spawn the new agent and the mentor on the same brief; the mentor's role is `pair_observer`, not `co-implementer`
   - The new agent leads; the mentor reviews after each tool call and at iteration end
   - Mentor records observations in their *own* memory (type=observation, subject=`"Pairing with <agent_id> @ ramp-iter-<N>"`)
   - If the new agent fails the same step twice, the mentor takes over and demonstrates; new agent retries on the next iteration

4. **Write the onboarding-note to the new agent's memory.** Call `memory-write`:
   ```
   agent_id: <agent_id>
   memory_type: onboarding-note
   confidence: 0.85
   tags: [onboarding, <dept>]
   source: "onboard@<iso-ts>"
   content: |
     Mentor: <mentor_id>
     Toy task: <one-line>
     Ramp iterations: <N>
     Mentor observations: <count>
     First independent task scheduled for: iteration <N+1>
     Skills exercised: <comma list from portfolio>
   ```

5. **Generate the first-90-day brief.** If `first_90_day_brief: true`, write `state/onboarding/<agent_id>-90day-brief.md` with:
   - 3 month-1 milestones (each = 1-3 task completions in the dept)
   - 2 month-2 stretch goals (cross-dept collaboration)
   - 1 month-3 review checkpoint (run `performance-review` skill — Wave 3.3)
   - Each milestone has a `due_iteration` field for tracking via `state/actions`

6. **Open mentor's coaching todo.** Call `memory-write` to the *mentor*:
   ```
   agent_id: <mentor_id>
   memory_type: todo
   confidence: 1.0
   source: "onboard@<iso-ts>"
   content: |
     Coach <agent_id> through onboarding milestones; review at iteration <N+30>.
     90-day brief: state/onboarding/<agent_id>-90day-brief.md
   ```

7. **Notify the dept lead.** `memo-send to=<dept-lead> severity=fyi` with the onboarding summary. The lead is `informed`, not action-required — the mentor is the action owner.

8. **Schedule individual-OKR proposal (v6.2+).** If `[okr.auto_set] individual_on_onboard == true` in config (default: true), enqueue a deferred action that fires when this agent reaches `[okr.auto_set] onboard_threshold_iter` iterations (default: 30). Implementation: write a todo into the mentor's memory with kind=lesson-followup and body `"At iteration <N+threshold>, memo HR-lead to dispatch individual-O drafting for <agent_id>. See skills/core/okr/okr-individual-dispatch/SKILL.md."`. The mentor's next `memory-reflect` surfaces this as a trigger; HR-lead then invokes `okr-individual-dispatch single_agent=<agent_id>` which runs the single-agent variant of the dispatch flow. On dispatch, the new agent gets its first brief to draft an individual O based on the experience it's accumulated over those N iterations.

   Skip this step if:
   - `[okr] auto_trigger_enabled == false` (master switch off)
   - `[okr.auto_set] individual_on_onboard == false` (feature disabled)
   - The dept has no active dept-O for the current period (no parent to align to; OKR-master's cascade-dept sweep will fire on its own cadence)

   Log `action: okr_individual_schedule_onboard, agent: <id>, fires_at_iteration: <N+threshold>`. This is a schedule, not a direct invocation — v6.2 runs the actual dispatch when the agent has memory to cite.

9. **Return refs.** Response shape below.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: onboard
STATUS: ok | error
AGENT_ID: <id>
MENTOR_ID: <id>
RAMP_ITERATIONS: <N>
ONBOARDING_NOTE_REF: mem://<agent>/onboarding-notes#L<n>
NINETY_DAY_BRIEF_REF: md://state/onboarding/<agent>-90day-brief.md
MENTOR_TODO_REF: mem://<mentor>/todos#L<n>
NEXT_ACTION: "Run first independent task at iteration <N+1>"
```

## Invariants

- **Never skip the toy task.** Even for an experienced persona transferring into a new dept, the toy task validates the agent has *this* dept's tooling.
- **Mentor is observer, not co-implementer.** If the mentor does the work, the new agent learns nothing. Pair-programming, not pair-doing.
- **Onboarding-note is sacred for 180 days.** memory-prune respects the per-type retention; do not manually delete it.
- **First-90-day brief is a contract.** If the agent doesn't hit milestone 1 by iteration N+30, escalate to dept lead, not silent failure.

## Non-Goals

- Not a training corpus loader. We don't fine-tune the persona; we exercise it.
- Not a probationary period. The agent is a full member of the org from hire-day; onboarding is scaffolding, not vetting.
- Not a substitute for `recruit`. If the new agent is a poor persona match, fix it in the next recruit cycle, not via 8 weeks of remedial onboarding.

## Anti-patterns

- Never auto-promote the toy task to a real production task. Even if the new agent crushes it, the toy task ships nothing.
- Never run more than 5 ramp iterations. If the agent isn't productive after 5, the persona is wrong; trigger `agent-promote` for reassignment or `recruit` for replacement.
- Never assign two new agents to the same mentor in the same turn. Mentors have bounded capacity; capacity-planner (Wave 3.4) enforces this.

## Grounding

- `skills/core/hr/recruit/SKILL.md` — the upstream skill that hands a new agent to onboard.
- `references/raci-assignment-protocol.md` — mentor-as-Consulted role pattern.
- `references/soul-architecture.md` — onboarding does not change the agent's soul (would require `soul-apply-override`).
- `agents/kiho-ceo.md` INITIALIZE step 9 — the lessons-injection path that benefits from onboarding-notes appearing in the new agent's memory.
