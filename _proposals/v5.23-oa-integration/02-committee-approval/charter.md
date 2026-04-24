# Charter — multi-stage approval committee

## Committee identity

- **committee_id:** `approval-chains-2026-04-23`
- **topic:** "How should kiho represent multi-stage conditional approvals without displacing committee deliberation?"
- **chartered_at:** 2026-04-23T14:30:00Z
- **reversibility:** reversible (additive protocol; can be abandoned)
- **knowledge_update:** true

## Members (quorum 4 of 5)

- **@kiho-hr-lead** — owns recruit-chain sign-offs (HR + auditors + CEO), a natural approval-chain analog
- **@kiho-eng-lead** — owns high-risk skill-create approvals (eng-lead → auditor → CEO), the second natural analog
- **@kiho-auditor-cost-hawk** — challenges adding infrastructure where existing committee covers
- **@kiho-auditor-pragmatist** — balances rigor against implementation cost
- **@kiho-clerk** — member here (not clerk of this committee) because the protocol interacts with transcript emission; separate clerk assigned

Clerk: auto-assigned per `kiho-clerk` (a second clerk instance). Not a member, does not vote.

## Input context

- User question: DingTalk approvals route expense/leave/procurement through sequential stages with amount-based conditional branches (>$5K → finance manager). kiho today has only `AskUserQuestion` (single gate to the user) and `committee` (deliberative, not sequential).
- Gap score from `00-gap-analysis.md` §matrix row 2: **HIGH** — no agent-level sequential approval chain, no conditional routing
- WebSearch evidence (2026-04-23): DingTalk compresses 3-day approval chains to 4 hours using form templates + conditional routing + auto-reminders

## Questions the committee MUST answer

| # | Question | Why it matters |
|---|---|---|
| Q1 | **Is this a new skill portfolio or a committee extension?** A sequential flavor of `committee` vs a `core/approval/` portfolio (e.g., `approval-request`, `approval-route`, `approval-escalate`, `approval-close`) | Determines whether deliberation + sign-off merge or stay separate |
| Q2 | **Conditional routing declaration** — TOML in a new approval-chain DSL? Inline in skill frontmatter? A referenced `chains.toml`? | Machine-parseable is required; the choice affects author ergonomics |
| Q3 | **Interaction with `AskUserQuestion` at the final stage** — is the user always the last approver, or can an all-agent chain close without user touch for pre-approved routines? | Must respect CLAUDE.md invariant: only CEO calls `AskUserQuestion` |
| Q4 | **Audit trail** — new ledger action types (e.g., `approval_requested`, `approval_granted`, `approval_denied`, `approval_escalated`)? Separate JSONL (e.g., `approvals.jsonl`) vs piggy-back on ledger? | CEO self-audit must cover approval drift |
| Q5 | **v5.22 hook composition** — does an approval-skill emission require a certificate marker analogous to `RECRUIT_CERTIFICATE:` / `KB_MANAGER_CERTIFICATE:`? | Preserves the generator/evaluator discipline that landed in v5.22 |
| Q6 | **Existing analogs** — can the recruit cycle's hiring-committee + HR-lead sign-off be re-expressed under the new approval chain to prove the protocol handles a known workload? | Worked example is the acceptance test |
| Q7 | **Escalation semantics when a stage denies** — does the request die, reroute, or bubble to CEO? How does this compose with committee escalation table? | Prevents approval-chain becoming a new parallel escalation path |

## Success criteria

Unanimous position describing:

- **Decision on Q1** (skill portfolio vs committee extension). If new skill portfolio: proposed skill IDs + capabilities.
- **Worked example** — at least one existing workload (recruit hiring-committee OR skill-factory high-risk path) fully expressed in the proposed chain DSL.
- **Audit surface** — specific new ledger action types OR explicit statement that existing `delegate`/`committee_convened`/`escalate_to_user` cover it.
- **Hook posture** — certificate pattern OR no-hook-needed with reasoning.
- **Non-duplication proof** — explicit argument for why this does not overlap with committee (e.g., "committee converges, approval chain gates; different phase of the decision lifecycle").

Close rule: unanimous + no unresolved challenges + aggregate confidence ≥ 0.90, ≤ 3 rounds.

## Constraints + references

- `plugins/kiho/references/committee-rules.md` — the committee this new protocol must coexist with; all format / round-limit / confidence rules apply to THIS committee too.
- CLAUDE.md invariant: **Only CEO in main conversation calls `AskUserQuestion`**. An approval chain that ends in "user approves" MUST route the last stage through the CEO's escalation bubble-up, NOT let a sub-agent invoke `AskUserQuestion` directly.
- `plugins/kiho/skills/core/hr/recruit/SKILL.md` §Pre-emit gate (v5.22) — the recruit certificate pattern is a proven in-the-wild approval chain; new design should match or improve on it.
- `plugins/kiho/bin/ceo_behavior_audit.py` — new action types must be either added to `KNOWN_SUBAGENTS` / audit checks or explicitly flagged as "audit-exempt" with reasoning.
- `plugins/kiho/references/capability-taxonomy.md` — if new skills, capabilities MUST come from the 8-verb set (likely `decide` or `orchestrate`).

## Out of scope (explicit)

- **No finance/expense domain specifics.** kiho agents have no budget-to-approve; the "approval chain" is about code review, risk-gated skill creation, recruit sign-off, etc. Amount-based routing becomes risk-tier-based or sensitivity-based.
- **No replacement of committee.** Committee remains the deliberative convergence primitive. Approval chains are for sequential binary sign-offs on a converged decision.
- **No automatic escalation to external tools.** No Slack pings, no email, no DingTalk pushes. All approval state stays inside kiho state.

## Escalation triggers

- If the committee cannot distinguish "approval chain" from "committee with sequential roles" — ASK_USER (likely the correct clarifying question: "do you want sequential binary sign-offs or gated deliberative convergence?").
- If the worked example (recruit chain or factory high-risk path) can't be re-expressed under any proposed chain DSL in round 2, recommend "no new protocol; improve existing certificate pattern" as a valid close position.
