---
name: capacity-planner
description: Use this skill before delegating new work to confirm the assigned agent isn't already overcommitted. Reads all open handoff-accept receipts in the current turn, sums per-agent eta_iterations, and computes a booking ratio. If any agent's booking exceeds 100% of the turn's iteration budget, raises a blocker memo to CEO before the new delegation lands. Triggers on "check capacity", "is <agent> available", "capacity check", or auto-fires from CEO LOOP step b (PLAN THIS ITEM) when the proposed RACI Responsible was already assigned to ≥ 2 prior items this turn. Closes the gap where CEO assigns 200% to one agent and discovers the conflict only when the agent's iterations dry up mid-loop.
metadata:
  trust-tier: T2
  kiho:
    capability: evaluate
    topic_tags: [coordination, lifecycle]
    data_classes: [agent-performance]
---
# capacity-planner

The "is the assignee actually free?" pre-flight check. handoff-accept logs ETAs but nobody sums them per agent; capacity-planner is that sum, plus the policy "warn on > 100% booking, block on > 150%".

## When to use

- CEO LOOP step b (PLAN THIS ITEM) auto-trigger when the proposed Responsible already has ≥ 2 open handoffs this turn
- Manually before a high-stakes delegation: "is eng-backend-01 actually available for this?"
- Pre-pair-request: confirm both candidates have spare capacity before opening a pair scratchpad

Do **NOT** invoke when:

- The turn just started (no prior handoffs to sum) — capacity is trivially 0%
- The work is irreversible-and-urgent — the user accepted the urgency, capacity is secondary
- The agent is the only qualifier per capability-matrix — overbooking is the lesser evil vs unassigned work

## Inputs

```
agent_id: <id> | "all"            # required; "all" returns the dept-wide booking summary
turn_id: <id>                     # default current turn from CEO ledger
budget_iterations: <int>          # default from completion.md hard limits
warn_threshold_pct: <int>         # default 100
block_threshold_pct: <int>        # default 150
```

## Procedure

1. **Resolve turn budget.** Read `<project>/.kiho/state/completion.md` for the current turn's `hard_limits.max_iterations`. If absent, default 12.

2. **Enumerate open handoffs for the agent(s).** Read `<project>/.kiho/state/receipts/<turn_id>/*.jsonl` (handoff-accept receipts). Filter to:
   - `accepted: true`
   - `status: in_progress | not_yet_started`
   - `agent_id` matches input (or all if `"all"`)

3. **Sum eta_iterations per agent.**
   ```
   booked = sum(receipt.eta_iterations for receipt in open_handoffs)
   booking_pct = (booked / budget_iterations) * 100
   ```

4. **Classify per agent:**
   - `under-booked` (< warn): green
   - `at-capacity` (warn ≤ booking_pct < block): yellow; flag in summary
   - `over-booked` (≥ block): red; raise blocker memo

5. **For each over-booked agent, raise a blocker memo to CEO.** Body:
   ```
   subject: "Capacity breach: <agent_id> booked at <pct>%"
   body: |
     Budget: <budget_iterations> iterations
     Booked: <booked> iterations across <count> handoffs
     Open handoffs:
       - <handoff_id>: <eta> iters (brief: <brief_path>)
     Recommendation: re-assign one of the open handoffs OR extend budget OR defer the new delegation.
   ```
   The CEO MUST resolve before adding new work to this agent.

6. **Write the capacity report.** Call `storage-broker` op=`put`:
   ```
   namespace: state/capacity-checks/<check_id>
   kind: capacity-check
   access_pattern: read-mostly
   durability: project
   human_legible: true
   body: { check_id, ts, turn_id, budget_iterations, per_agent: [{agent_id, booked, pct, status, open_handoffs}] }
   ```

7. **Return per-agent summary.** Response shape below.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: capacity-planner
STATUS: ok | warning | blocker-raised | error
TURN_ID: <id>
BUDGET_ITERATIONS: <int>
PER_AGENT:
  - agent_id: <id>
    booked_iterations: <int>
    booking_pct: <int>
    status: <under-booked | at-capacity | over-booked>
    open_handoffs_count: <int>
BLOCKERS_RAISED: <count>
REPORT_REF: md://state/capacity-checks/<id>.md
```

## Invariants

- **Budget is a hard limit, not a target.** Booking 80% is healthy; 100% leaves zero margin for surprise; 150% is a process bug.
- **One memo per over-booked agent per turn.** Don't spam the CEO inbox; one blocker captures the situation.
- **Capacity is per-turn, not per-day.** Each turn is its own iteration budget; carry-over is via plan.md, not capacity rollover.
- **Read-only for handoff-accept records.** capacity-planner never modifies receipts; if a receipt is wrong, it's the issuing agent's job to update.

## Non-Goals

- Not a scheduler. Doesn't sequence work; just counts commitments.
- Not a calendar. No wall-clock awareness; iterations are the only currency.
- Not for cross-turn capacity. If an agent will be overbooked next turn, that's CEO planning, not capacity-planner.
- Not for human capacity. ICs are agents; their "capacity" is iteration budget within this turn.

## Anti-patterns

- Never silence an over-booked blocker. Even if the user is impatient, surface the conflict so the CEO chooses what to drop.
- Never add new handoffs while a blocker is open for the same agent. CEO MUST resolve the existing capacity issue first.
- Never sum eta_iterations across agents. Capacity is per-agent; aggregating hides the actual conflict.
- Never run capacity-planner before INITIALIZE finishes. The receipts directory may not exist yet.

## Grounding

- `skills/core/communication/handoff-accept/SKILL.md` — the source of eta_iterations data.
- `agents/kiho-ceo.md` LOOP step b — the canonical invocation point pre-DELEGATE.
- `references/data-storage-matrix.md` — receipts directory storage (turn-scope T2).
- `skills/core/ceremony/department-sync/SKILL.md` — sibling skill that surfaces capacity issues at the dept-level pulse.
