# OKRs in kiho — a user-facing guide

The OKR framework lands in kiho v6.1 (per committee decision `okr-framework-2026-04-23` under `_proposals/v5.23-oa-integration/01-committee-okr/`). OKRs give kiho the one thing it was always missing: a **durable goal hierarchy** that agents can align their day-to-day cycles against. This guide explains when to set OKRs, how they help, and how kiho itself gets better when they're in use.

## The 30-second version

- An **Objective (O)** is one sentence: what you want to be true by a deadline.
- **Key Results (KRs)** are 3–5 weighted measurables per Objective, 0.0–1.0 scored.
- OKRs live in `<project>/.kiho/state/okrs/<period>/O-*.md` — Tier-1 markdown, one file per Objective.
- Three levels — **company** (you set, as the employer), **department** (dept-lead committee sets), **individual** (agent proposes, dept-lead approves).
- You invoke `/kiho` to set, check in on, and close OKRs.

## When OKRs happen (v6.2+ — mostly auto)

**You (the employer) only directly set COMPANY OKRs. Everything else auto-flows.** Department OKRs are produced by dept-lead committees. Individual OKRs are HR-dispatched, agent-drafted-from-experience, and multi-party-reviewed. Check-ins happen on cycle close. Closes happen at period end.

The automatic triggers:

| Event | What happens | Who acts | Your involvement |
|---|---|---|---|
| Start of each quarter (within first 30 days) | `bin/okr_scanner.py` at CEO INITIALIZE detects no company O for current period → OKR-master drafts 2-3 candidates from your plan.md + last retrospective + dashboard → CEO bubbles via `AskUserQuestion` | OKR-master drafts, CEO bubbles | **You accept / edit / dismiss** |
| Company O set, no dept O yet | OKR-master memos each dept-lead → dept-lead convenes OKR committee → committee closes → auto `okr-set level=department` with `DEPT_COMMITTEE_OKR_CERTIFICATE` | dept-leads + committees | none |
| Dept O set, no individual Os yet | OKR-master memos HR-lead → HR-lead dispatches qualifying agents with experience-using brief → agents draft Os citing their memory → lightweight committee (dept-lead + HR + OKR-master) reviews → approve / revise / reject | HR-lead + agents + review committee | none (optional user seat for high-risk drafts) |
| Plan.md task added | `kiho-plan` does keyword match → auto-tags `aligns_to_okr` to relevant individual or dept O | kiho-plan | none |
| Cycle closes success | cycle-runner `on_close_success` hook → `okr-checkin` with derived score (conservative formula: `0.05 × weight/100` per aligned KR) | cycle-runner | none |
| Active O with no checkin > 30 days | CEO INITIALIZE memo owner (severity=action) | CEO | none |
| Period ends (today > period.end) | Batch `okr-close` all active Os, leaf-first | OKR-master | none |
| Parent O closed with aggregate < 0.3 | Cascade: children go `status: deferred` (per `[okr] cascade_rule`) | OKR-master | none |

### Your direct invocations (optional — auto-flow covers these, but you can always override)

- `/kiho set a company OKR ...` — proactive company O without waiting for the quarter-start nudge
- `/kiho okr-checkin O-<id> ...` — manual override of auto-checkin, e.g., narrative context
- `/kiho close out 2026-Q2 OKRs` — early close before period end
- `/kiho show my OKRs` — walks the alignment tree via OKR-master

### When you should NOT reach for OKRs

- Single-file bugfix or quick spike (use `/kiho --vibe` or `/kiho --bugfix`).
- A plan.md task that expresses the work fully — plan.md is the execution layer.
- "Objectives" you'd set on an agent's behalf without a real business outcome (that's activity tracking, not OKRs).

## How to disable auto-flow (opt back into v6.1 explicit-only)

Set in `<project>/.kiho/config.toml` or `$COMPANY_ROOT/settings.md`:

```toml
[okr]
auto_trigger_enabled = false        # master switch — reverts to v6.1 explicit-only behavior
```

Or disable individual features:

```toml
[okr.auto_set]
individual_on_onboard = false       # HR-lead won't auto-propose individual Os at onboard
dept_from_committee = false         # OKR-topic committees won't auto-create dept Os

[okr]
auto_checkin_from_cycle = false     # cycle-runner won't auto-checkin on cycle close

[okr.period]
auto_close_on_period_end = false    # period end won't batch-close
```

The atomic primitives (`okr-set`, `okr-checkin`, `okr-close`) remain functional under all configurations — auto-flow is an orchestration layer on top of them.

## The three levels

| Level | Who sets it | Approval mechanism | Example |
|---|---|---|---|
| **Company** | You, the employer | User accepts via `AskUserQuestion` — the skill refuses to emit without a `USER_OKR_CERTIFICATE:` marker | "Ship the v5.23 OA integration with zero regressions to v5.22 hook behavior by 2026-06-30." |
| **Department** | Dept-lead (eng-lead, hr-lead, pm-lead, etc.) via a committee | Requires a closed `decisions/<dept>-okr-<period>.md` committee decision page as prerequisite | "Engineering: reduce mean approval-chain wall-clock from 45s to 20s by 2026-06-30." |
| **Individual** | Agent proposes; dept-lead approves via the `okr-individual` approval chain (v5.23 shipped in approval-chains.toml) | Requires `DEPT_LEAD_OKR_CERTIFICATE:` marker emitted by the dept-lead after review | "@kiho-eng-lead: close 80% of opened cycles within budget in 2026-Q2." |

Every non-company Objective has an `aligns_to: <parent-O-id>` field in its frontmatter. This creates a tree — individual Os align to department Os, which align to company Os. You can read the tree top-down (company vision → departments → agents) or bottom-up (agent tasks → which company Objective does this serve?). That's the entire point of OKRs.

## How OKRs help

### For you (the employer)

- **Alignment**. You write your intent once; agents cite it in every relevant cycle. You stop re-explaining the same priorities across turns.
- **Focus**. Forcing yourself to pick 1–5 Objectives per quarter is a useful exercise. The Os you reject teach you as much as the ones you keep.
- **Measurement**. At quarter close, `okr-close` aggregates KR scores into a 0.0–1.0 number per Objective. You can see what worked without narrative interpretation.
- **Delegation fidelity**. When you set a company O, every dept-lead and agent downstream can draft their own OKRs in service of it without further input from you. You've given them the north star; they execute.

### For the agents

- **RACI clarity**. Individual OKRs are the strongest RACI signal agents get — stronger than plan.md task ownership, stronger than capability-matrix proficiency. An agent with an individual OKR knows, concretely, what "success for me this period" looks like.
- **Self-pacing**. `okr-checkin` is explicit-invocation, not scheduled — agents decide when to update their KR progress. The act of writing a 0.7 when last checkin was 0.4 is meaningful.
- **Promotion targeting**. The v5.23 agent-promote skill now reads `agent-score-<period>.jsonl` (committee 05 decision). High-scoring agents pair their performance narrative with a closed individual OKR showing concrete KR completion, which makes promotion committees much faster.

### For kiho itself

This is where the framework actually pulls its weight. OKRs don't just help users and agents — they make the **system** more coherent:

1. **Cycles can align to OKRs.** `cycle-runner` reads a cycle's `index.toml` at advance time. v6.1+ recognizes an optional `aligns_to_okr: O-<id>` field. When present, the cycle's close event writes an `okr_contribution` breadcrumb into the Objective file's activity log. You get automatic traceability from shipped work to the Objective it served.
2. **Dashboard rollup.** `bin/dashboard.py` already reports velocity + committees + hiring + factory + KB. v6.1 extends metric 7 to cite top/bottom OKR scores when `.kiho/state/okrs/<period>/` has closed files. One `dashboard --period quarterly` invocation gives you a period scorecard that's legible to the humans around you (board members, stakeholders) — not just the agents.
3. **Retrospectives get quantitative.** The v5.23 retrospective already opens by loading the dashboard. With OKRs in place, the retrospective's `systemic` section has concrete anchors — "our velocity was high but OKR closure was 0.4; we were busy in the wrong direction."
4. **Soul drift detection.** An agent who consistently scores 0.2 on their individual KR while invoking many skills successfully is a drift signal (doing work but not the work that mattered). `values-alignment-audit` picks this up as a values-flag-worthy pattern.
5. **Committee escalation clarity.** When a committee escalates a decision to you, the committee packet can reference the relevant company O — the decision is adjudicated against your stated intent, not against an unstated one.

## The three skills

- **`okr-set`** — create a new Objective with its KRs. Enforces the RACI pre-emit gate (user / committee / dept-lead approval per level). Capability: `create`.
- **`okr-checkin`** — update KR progress scores during the period. No special gate; modifying your own Objective. Capability: `update`.
- **`okr-close`** — compute the aggregate score at period end, mark Objective `status: closed`, optionally archive. Capability: `update`.

All three are new in v6.1 per decision `okr-framework-2026-04-23`.

## Example: setting your first company OKR

```
/kiho I want to set a company OKR for 2026-Q2: ship the v5.23 OA integration
with zero regressions to v5.22 hook behavior by 2026-06-30. Key results
should cover (a) approval-chain test coverage, (b) user-satisfaction signal
from retrospectives, (c) adoption — at least 5 cycles should cite the new
aligns_to_okr field.
```

The CEO routes this to `okr-set` with `okr_level: company`. The skill drafts the O + KRs, calls `AskUserQuestion` so you accept (or adjust) the weighting, and on your accept emits `<project>/.kiho/state/okrs/2026-Q2/O-2026Q2-company-01.md` with the `USER_OKR_CERTIFICATE:` marker that lets the PreToolUse hook pass the write. Next retrospective, the new O shows up on the dashboard.

## Invariants you can rely on

- Every OKR file is Tier-1 markdown — committee-reviewable, git-diffable, grep-able.
- Every OKR file has a YAML frontmatter block with `o_id`, `okr_level`, `period`, `owner`, `aligns_to`, `status`.
- `status` transitions are one-way: `draft → active → closed`. No silent revivals.
- Weights across an Objective's KRs sum to ≤ 100 (normalization at aggregation time).
- Stretch KRs (frontmatter `stretch: true`) cap at 0.7 for aggregate purposes — they can't inflate the final score.
- Company-level Objective emission ALWAYS routes through `AskUserQuestion`. A main-thread CEO cannot set a company OKR on your behalf without your explicit accept.
- The per-level approval chains are enforced both by the skill's pre-emit gate AND by the PreToolUse hook (`pre_write_chain_gate.py`) — defense in depth.

## Anti-patterns

- **Don't set more than ~5 company Objectives per quarter.** 3 is the right number for most quarters. 10+ Os means you haven't prioritized.
- **Don't let KRs drift into activity lists.** "Hold five meetings" is not a KR; "reduce mean decision-to-implementation wall-clock by 30%" is.
- **Don't rewrite closed Objectives.** At quarter close, `okr-close` freezes the file. Corrections go into the next period's retrospective.
- **Don't rely on automatic cadence.** There isn't one. Invoking `okr-checkin` is your or the agents' responsibility — the discipline is the point.
- **Don't route broadcast announcements through OKR files.** OKRs are measurable outcomes; announcements (v5.23 broadcast extension) are messages. Different skills, different surfaces.

## Related doctrine

- `references/committee-rules.md` §Special committee types — department OKRs convene here.
- `references/approval-chains.toml` — the three OKR chains (`okr-company`, `okr-department`, `okr-individual`) and their certificate markers.
- `references/data-storage-matrix.md` §7 Session working state — row `okrs-period-md` for the Tier-1 OKR files.
- `references/raci-assignment-protocol.md` — OKR ownership integrates with RACI.
- `skills/core/hr/agent-promote/SKILL.md` §2a — how OKR closure feeds promotion criteria.
- `bin/dashboard.py` — metric 7 surfaces top/bottom OKR scores at period rollup.
- `_proposals/v5.23-oa-integration/01-committee-okr/decision.md` — the committee decision record that grounds all of this.
