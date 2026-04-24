---
name: okr-individual-dispatch
description: HR-dispatched, agent-experience-driven, multi-party-reviewed individual Objective drafting (v6.2+). The load-bearing skill of the v6.2 OKR auto-flow — this is the skill that makes OKRs an organic part of the org rather than a ceremony the user performs. Flow: OKR-master detects cascade-individual need → memos HR-lead → HR-lead filters qualifying agents by capability-matrix + agent-score → spawns each as sub-agent with an experience-using brief (the agent reads its own memory/lessons/todos/observations before drafting) → collects structured drafts → convenes a lightweight 1-round review committee per draft (dept-lead + HR-lead + OKR-master, optional user for high-risk) → approve (dept-lead emits DEPT_LEAD_OKR_CERTIFICATE → okr-set level=individual) / revise (memo agent with feedback, ≤3 iterations) / reject (rejection-feedback memo + no O this period). Use when OKR-master receives `OPERATION: dispatch-individual`, when a dept O has just been committee-approved, or when the onboard skill completes a new hire's Nth iteration. Read `references/agent-brief.md` for the brief template + `references/review-committee.md` for the committee protocol.
argument-hint: "period=<YYYY-QN> dept_o_scope=[<dept-o-id>,...] [max_per_dept=<int>]"
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: active
  kiho:
    capability: orchestrate
    topic_tags: [governance, coordination, hiring]
    data_classes: ["okrs-period-md", "memo-inbox", "capability-matrix"]
    storage_fit:
      reads:
        - "<project>/.kiho/state/okrs/**"
        - "<project>/.kiho/state/org-registry.md"
        - "<project>/.kiho/state/capability-matrix.md"
        - "<project>/.kiho/state/agent-score-<period>.jsonl"
        - "$COMPANY_ROOT/agents/*/memory/**"
      writes:
        - "<project>/.kiho/state/okrs/<period>/O-*-individual-*.md"  # via okr-set
        - "<project>/.kiho/state/inbox/*.jsonl"                      # via memo-send
        - "<project>/.kiho/committees/<id>/transcript.md"            # via committee
---
# okr-individual-dispatch

The skill that closes the "full-auto org" loop for OKRs. It dispatches real agents to draft real Objectives based on their real experience, then reviews those drafts with a real committee, then emits the resulting OKR through the same approval chain any other individual O would use.

**Three load-bearing properties, taken from the user's direct instruction:**

1. **HR dispatches.** Not the CEO, not OKR-master. HR-lead is the workforce orchestrator — filtering, spawning, collecting.
2. **Agent uses its experience.** The brief literally requires the agent to `memory-query` its own lessons / todos / observations before drafting, and the draft's rationale must cite memory refs.
3. **Multi-party review.** Lightweight committee of dept-lead + HR-lead + OKR-master, with an optional user seat when the draft is flagged high-risk.

## When to use

- `kiho-okr-master` receives `OPERATION: dispatch-individual` from CEO INITIALIZE step 17.5 (after the scanner emits `cascade-individual` for a dept-O).
- `okr-period.toml` phase `individual-cascade` invokes this as its entry skill.
- `skills/core/hr/onboard/SKILL.md` invokes this directly when `[okr.auto_set] individual_on_onboard = true` and the new agent has passed `onboard_threshold_iter` iterations — dispatching a single-agent case (one draft, one review, one emit).

Do NOT invoke:

- To set a company O or dept O — different chains, different skills.
- For an agent who already has an active individual O this period — the scanner's cascade-individual action filters those out.
- Per-turn without a scanner trigger — this is a fanout-5 operation; invoking it speculatively burns attention budget.

## Inputs

```
PAYLOAD:
  period:             <YYYY-QN or YYYY-HN or custom slug>       # required
  dept_o_scope:       [<dept-o-id>, ...]                          # required; list of aligned parents to dispatch under
  max_per_dept:       <int>                                       # optional; default from [okr.auto_set] individual_max_per_dept
  single_agent:       <agent-id>                                  # optional; onboard-triggered single-dispatch path
  filter_min_capability_score:  <int>                             # optional; default 3 (capability-matrix 1-5 scale)
  filter_min_agent_score:       <float>                           # optional; default 0.70
  allow_user_escalation:        <bool>                            # optional; default true (high-risk → AskUserQuestion)
```

## Procedure

The flow has five stages. Each is atomic and logged.

### Stage 1 — HR-lead filters candidate agents

For each `dept_o_scope[i]`:

1. Read `<project>/.kiho/state/org-registry.md` → all agents in the dept.
2. Read `<project>/.kiho/state/capability-matrix.md` → keep agents with proficiency ≥ `filter_min_capability_score` in any skill listed in the dept-O's `required_skills` or topic-tag-aligned to the dept-O.
3. **(v6.2.1+ gap I fix) Read agent-score with cross-project fallback**:
   - First check `<project>/.kiho/state/agent-score-<period>.jsonl` (this-project score).
   - If absent OR agent missing from this-project scores, ALSO check `$COMPANY_ROOT/company/state/agent-score-<period>.jsonl` (company-wide rollup — produced by `bin/kiho_telemetry_rollup.py --company-root` in DONE step 10). This covers kiho-* agents who span multiple projects but happen to have done most work elsewhere.
   - If BOTH absent OR agent missing from both → treat as "no score yet" (new hire or company-wide telemetry not yet rolled up) and include in candidate pool with `score_basis: new_hire`.
   - Keep agents with `score ≥ filter_min_agent_score` OR `score_basis == new_hire`. Reject agents with score < threshold who have a score from either tier (prevents "project A has no score for agent-X but company-wide score is 0.4" from sneaking them in).
4. Exclude agents with an active individual O for this period already (check BOTH `<project>/.kiho/state/okrs/` and `$COMPANY_ROOT/company/state/okrs/` — v6.2.1 OKR files may live in either tier per the scanner's gap-E fix).
5. Cap to `max_per_dept` (take the highest-scoring first; tie-break on capability-matrix sum).

Log `okr_dispatch_filter_complete, dept_o: <id>, candidates: <list>, excluded: <list-with-reason>, score_source_per_candidate: {agent: "project|company|new_hire"}`.

If `single_agent` was provided (onboard path), skip the filter and use that agent directly.

### Stage 2 — Spawn each candidate with the experience-using brief

For each filtered candidate agent, spawn as sub-agent (via `Agent` tool) with:

- `subagent_type`: the agent's canonical type (from `agents/<id>.md` name field)
- `prompt`: the brief template from `references/agent-brief.md`, parameterized with the target dept-O and period

The brief requires the agent (before drafting) to invoke `memory-query` for its own last 5 lessons, pending todos, and recent high-importance observations; then to draft a structured JSON with `{objective, kr[], rationale_from_lessons}` where `rationale_from_lessons` MUST cite at least one memory/lesson by ref.

Log `okr_dispatch_spawn, agent: <id>, dept_o: <parent>`.

### Stage 3 — Collect drafts

Each sub-agent returns its structured draft (or an abort). HR-lead validates:

- `objective` present and one-sentence
- `kr[]` count in [3, 5], weights sum ≤ 100, each KR has description + weight + direction
- `rationale_from_lessons` cites ≥ 1 memory ref (regex: `memory/lessons.md#.+` or similar)
- at least one KR is declared `derivable_from_cycle_events` (so `okr-checkin` can auto-update it in PR 3)

Drafts failing validation → send `memo-send` back to the agent with specific feedback, up to 3 iterations. On third failure, log `okr_dispatch_draft_invalid` and move that agent to rejected bucket.

### Stage 4 — Convene lightweight review committee per draft

For each validated draft, convene a lightweight committee per `references/review-committee.md`:

- Convener: HR-lead
- Members (quorum 3): dept-lead (of the agent's department) + HR-lead + OKR-master
- Optional 4th member: user (via CEO `AskUserQuestion` escalation) when the draft is flagged high-risk:
  - agent has < 30 onboarded iterations, OR
  - agent has no prior closed OKR, OR
  - agent's cycle-outcome score < 0.70, OR
  - draft KR count is 5 (maximum) — reviewer may want user perspective on ambition
- Rounds: 1 (lightweight variant per `references/committee-rules.md` §Lightweight committee)
- Phases: `research` (read draft + memory refs) → `choose` (approve | revise | reject)

Committee clerk writes `<project>/.kiho/committees/okr-indiv-<agent>-<period>/transcript.md` in standard format.

### Stage 5 — Dispatch the committee outcome

**Approve** (unanimous, confidence ≥ 0.90):

1. Dept-lead emits `DEPT_LEAD_OKR_CERTIFICATE` as the committee's closing act. Certificate body:
   ```
   DEPT_LEAD_OKR_CERTIFICATE:
     chain_id: okr-individual
     stages_complete: proposal-draft, dept-lead-review
     agent: <agent-id>
     dept_o_aligns_to: <parent-o-id>
     committee_id: <committee-id>
     emitted_at: <iso>
   ```
2. HR-lead invokes `okr-set` with:
   - `level: individual`
   - `owner: <agent-id>`
   - `aligns_to: <parent-o-id>`
   - `kr`: from the approved draft
   - `certificate`: the DEPT_LEAD_OKR_CERTIFICATE body
3. The `okr-set` skill's pre-emit gate verifies certificate; on pass, writes the Tier-1 file. PreToolUse hook (pre_write_chain_gate.py) additionally verifies the certificate marker in content.
4. Log `okr_individual_emitted, agent: <id>, o_id: <new-id>`.

**Revise** (non-unanimous but no outright rejection):

1. Committee produces feedback bullets.
2. `memo-send` to agent (severity: action) with feedback.
3. Agent has one more draft iteration (max 3 total per HR-dispatch). If already at 3, force to reject.
4. Log `okr_individual_revise_requested, agent: <id>, iteration: <n>`.

**Reject** (unanimous reject, OR 3 drafts exhausted):

1. Invoke `skills/core/hr/rejection-feedback` to compose a structured rejection memo.
2. `memo-send` to agent (severity: info) with the structured feedback.
3. Log `okr_individual_rejected, agent: <id>, reason: <one-line>`.
4. No individual O for this agent this period; their contribution measured by dept-O rollup alone.

## Response shape

```
## Receipt <REQUEST_ID>
OPERATION: okr-individual-dispatch
STATUS: ok | partial | error
PERIOD: <period>
DEPT_O_SCOPE: [<list>]
AGENTS_DISPATCHED: <int>
DRAFTS_APPROVED: <int>
DRAFTS_REVISED: <int>
DRAFTS_REJECTED: <int>
INDIVIDUAL_OS_EMITTED: [<new-o-id>, ...]
USER_ESCALATIONS: [<agent-id-with-reason>, ...]
LEDGER_REF: jsonl://state/ceo-ledger.jsonl#seq=<n>
```

`partial` is returned when some drafts were rejected / revised mid-fanout; the receipt still enumerates what emitted.

## Invariants

- **HR is the dispatcher.** HR-lead spawns the candidate agents, collects drafts, and orchestrates review. OKR-master is a committee MEMBER (not convener); CEO is the escalation target for user seat only.
- **Experience is load-bearing.** A draft without memory/lesson citation is auto-rejected at stage 3 — not by the committee, but by HR-lead's validation. The agent MUST actually read its own memory; sycophancy drafts are caught structurally.
- **Multi-party means 3-4 members always.** Never 2 (not enough perspective), never 5+ (outside committee-rules bounds). Convener + 2 members = 3; + optional user = 4.
- **Approval chain honored.** The `okr-individual` chain in approval-chains.toml is the gate. DEPT_LEAD_OKR_CERTIFICATE is emitted by dept-lead ONLY, never by HR or OKR-master. This is what prevents HR from hiring into an O without dept-domain blessing.
- **Fanout bounded.** `max_per_dept` enforces fanout ≤ 5 per spawn batch; committees may interleave across /kiho turns if fanout would otherwise exceed depth-cap discipline.
- **User escalation bubbles to CEO.** When user seat triggers, OKR-master drafts the AskUserQuestion but CEO invokes it — the "only CEO calls AskUserQuestion" invariant stays.

## Non-Goals

- **Not a replacement for recruit.** This skill dispatches EXISTING agents to draft their own Os. Recruiting new agents for OKR-specific skills is still the recruit skill's job.
- **Not a performance appraisal.** The committee reviews the DRAFT's fit, not the agent's past. That's `performance-review` and `agent-cycle-score`'s domain.
- **Not a multi-O-per-agent emitter.** One individual O per agent per period. If an agent already has an active individual O, this skill skips them.
- **Not synchronous.** Across a large org, drafts arrive over multiple /kiho turns. HR-lead tracks pending drafts via a scratch file; committee doesn't block on pending drafts.

## Anti-patterns

- Spawning every agent in the org. Always filter — capability-matrix + agent-score do real work here. A 20-agent org typically produces ~8 qualifying candidates under defaults.
- Letting the draft skip memory-query. The agent-brief template is explicit; enforcement is structural (validation at stage 3).
- Making the committee unanimous+0.95 instead of unanimous+0.90. Lightweight variant uses the standard 0.90 threshold; raising it produces unnecessary user escalations.
- Emitting the certificate from HR-lead or OKR-master. Hard invariant: dept-lead emits. HR's job is orchestration; dept-lead's job is judgment on domain fit.

## Grounding

- `references/agent-brief.md` (sibling ref) — the experience-using brief template, parameterized at stage 2.
- `references/review-committee.md` (sibling ref) — the lightweight 1-round committee spec.
- `agents/kiho-hr-lead.md` — the HR-lead agent that runs this skill.
- `agents/kiho-okr-master.md` — committee member (not convener).
- `skills/core/okr/okr-set/SKILL.md` — the atomic primitive invoked at stage 5 approve.
- `skills/core/hr/rejection-feedback/SKILL.md` — invoked at stage 5 reject.
- `skills/core/communication/memo-send/SKILL.md` — dispatch + feedback primitive.
- `skills/core/memory/memory-query/SKILL.md` — what the sub-agent uses during drafting.
- `references/committee-rules.md` §Lightweight committee — the format the review follows.
- `references/approval-chains.toml` — the `okr-individual` chain enforced at emit.
- `references/okr-guide.md` — user-facing narrative of this flow.
