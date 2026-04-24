---
committee_id: okr-framework-2026-04-23
topic: "How should kiho support company-level OKRs (Objectives + Key Results)?"
chartered_at: 2026-04-23T14:00:00Z
members:
  - "@kiho-pm-lead"
  - "@kiho-eng-lead"
  - "@kiho-hr-lead"
  - "@kiho-auditor-skeptic"
  - "@kiho-researcher"
quorum: 4
---

## Round 1

### research

- **@kiho-researcher** (confidence: 0.88) — Lark OKR primary mechanics: O (1-5 per owner), KRs (3-5 per O, each weighted 0-100 summing to ≤100), alignment tree (O_child references O_parent by id), quarterly cycle with two mid-cycle check-ins at weeks 4 + 8, scoring 0.0-1.0 per KR, aggregated via weighted mean.
  > The alignment tree is not an org chart — it's a goal-chart: a department O aligns upward to a company O, and downward to individual Os. This is distinct from RACI.
- **@kiho-pm-lead** (confidence: 0.85) — kiho's `plan.md` is a flat RACI task list, not a hierarchy. Cycle-runner templates have phase-level structure but no cross-cycle goal hierarchy. Gap is real: no mechanism today lets an individual IC task cite a company-level goal it serves.
- **@kiho-eng-lead** (confidence: 0.82) — Three feasible storage shapes: (a) extend `plan.md` with an `## OKRs` section; (b) new `.kiho/state/okrs/` directory with one markdown file per O; (c) new cycle-template `okr-quarterly` where the cycle's phases are the check-ins. Each has tradeoffs.
- **@kiho-hr-lead** (confidence: 0.80) — Current `performance-review` has no goal-reference. If OKRs land, reviews should cite which KRs the agent contributed to. That's a promotion criteria extension, not an OKR-framework blocker.
- **@kiho-auditor-skeptic** (confidence: 0.75) — The user motivation cited "agent make OKR" — that's drift-prone. Agents proposing their own goals under a vague company O will goal-hack. Need strong gate: company Os are user-set, department Os are committee-set, individual Os are proposed by agent + blessed by dept-lead.

### suggest

- **@kiho-pm-lead** (confidence: 0.85) — Shape (c): new cycle template `okr-quarterly`. Each company O becomes a cycle instance. KRs are cycle outputs tracked in index.toml. Check-ins are cycle phases. Close = cycle close = OKR score.
- **@kiho-eng-lead** (confidence: 0.82) — Disagree. Cycle-runner is for *work that terminates*; an OKR is a *goal that guides terminating work*. Overloading cycle-runner breaks its semantic. Propose shape (b): `.kiho/state/okrs/<period>/<o-id>.md` Tier-1 with a small portfolio of skills (`okr-set`, `okr-checkin`, `okr-close`, `okr-align`, `okr-report`). The cycle-runner remains separate; cycles *cite* OKRs they serve via frontmatter.

### challenge

- **@kiho-auditor-skeptic** (confidence: 0.78) — Challenge on shape (b): five new skills is a large skill-portfolio addition. Each must pass the factory + critic. Counter-proposal: just (a) — add `## OKRs` section to `plan.md`, document the alignment-tree notation as markdown convention, no new skills. Reviewers already read `plan.md` every turn; attention budget is free.
  > Concrete: `plan.md` gets `## Company Objectives (2026-Q2)` + `## Department Objectives` + `## Individual Objectives` subsections. OKR id like `O-2026Q2-company-01`, KRs nested under each O with `<!-- weight: 30 -->` HTML-comment annotations. Alignment: each child O has `aligns_to: O-2026Q2-company-01`.
- **@kiho-researcher** (confidence: 0.80) — Counter-challenge on shape (a): `plan.md` is already the longest Tier-1 file most projects have. Adding 10-20 OKR objectives × 3-5 KRs each balloons it to where scanning becomes painful. The Karpathy-wiki rationale (one concept per file for targeted compilation) applies here too. Shape (b) respects the wiki discipline.
- **@kiho-pm-lead** (confidence: 0.82) — Challenge on shape (c) I proposed: eng-lead is right that cycle semantics differ. Withdrawing (c). Leaning toward (b) with skeptic's scope check — start with 3 skills not 5.

### choose

- **@kiho-pm-lead** (confidence: 0.80) — Shape (b) with reduced scope: 3 new skills (`okr-set`, `okr-checkin`, `okr-close`). Alignment + reporting deferred to v5.24 if demand emerges. Storage `.kiho/state/okrs/<period>/<o-id>.md` T1.
- **@kiho-eng-lead** (confidence: 0.80) — Shape (b) with reduced scope: 3 new skills. Agreed.
- **@kiho-hr-lead** (confidence: 0.75) — Shape (b) with reduced scope: 3 new skills. Agreed; performance-review citation of KRs is v5.24 follow-up.
- **@kiho-auditor-skeptic** (confidence: 0.68) — Shape (b) with reduced scope: 3 new skills. Still concerned about agent-proposed individual Os; want RACI constraint baked into `okr-set`.
- **@kiho-researcher** (confidence: 0.78) — Shape (b) with reduced scope: 3 new skills. Agreed.

Unanimous position on shape (b) + 3 skills, but aggregate = mean(0.80, 0.80, 0.75, 0.68, 0.78) = **0.762** < 0.90. Challenge of "RACI for individual O proposal" is unresolved. NOT closed. Round 2.

## Round 2

### research

- **@kiho-auditor-skeptic** (confidence: 0.82) — Drafted the RACI constraint: `okr-set` frontmatter MUST carry `okr_level: company | department | individual`; `okr_level: company` requires user-set (CEO escalation via AskUserQuestion); `department` requires a committee decision page as prerequisite; `individual` requires dept-lead sign-off (natural approval-chain analog — ties into committee 02's output).
  > This means `okr-set` cannot execute unless the prerequisite artifact exists. Same poka-yoke pattern as the v5.22 recruit pre-emit gate.
- **@kiho-pm-lead** (confidence: 0.85) — The RACI constraint addresses the goal-hacking concern. Adding: individual Os also need `aligns_to: <department-O-id>` mandatory — you cannot propose an orphan individual O.

### suggest

- **@kiho-auditor-skeptic** (confidence: 0.88) — Adopt the RACI constraint as a pre-emit gate on `okr-set`, analogous to `recruit`'s pre-emit gate. No new hook needed (the pre-emit gate is a skill-internal check, not a PreToolUse hook).

### challenge

- **@kiho-eng-lead** (confidence: 0.85) — Minor challenge: the individual-O pre-emit gate needs a "dept-lead sign-off" artifact. What shape? If we reuse the v5.22 recruit certificate pattern, individual O files need a `DEPT_LEAD_OKR_CERTIFICATE:` marker. Committee 02 (approval) is designing a general chain DSL; this is one instance of it. Recommend: this committee specifies the REQUIREMENT, committee 02 specifies the MECHANISM.
  > Resolved: this committee's decision records "individual-O creation requires dept-lead approval; mechanism deferred to committee 02's output; interim stub is a manually-inserted certificate line". No blocker.

### choose

- **@kiho-pm-lead** (confidence: 0.92) — Shape (b) + 3 skills + RACI pre-emit gate + mechanism deferred to committee 02.
- **@kiho-eng-lead** (confidence: 0.92) — Shape (b) + 3 skills + RACI pre-emit gate + mechanism deferred to committee 02.
- **@kiho-hr-lead** (confidence: 0.90) — Shape (b) + 3 skills + RACI pre-emit gate + mechanism deferred to committee 02.
- **@kiho-auditor-skeptic** (confidence: 0.90) — Shape (b) + 3 skills + RACI pre-emit gate + mechanism deferred to committee 02.
- **@kiho-researcher** (confidence: 0.90) — Shape (b) + 3 skills + RACI pre-emit gate + mechanism deferred to committee 02.

Aggregate = mean(0.92, 0.92, 0.90, 0.90, 0.90) = **0.908** ≥ 0.90. Unanimous. Challenge from round 1 resolved. **CLOSE.**

## Close

- outcome: unanimous
- final_confidence: 0.91
- rounds_used: 2
- decision: "Introduce OKR framework as new `core/okr/` skill portfolio with 3 skills (okr-set, okr-checkin, okr-close), Tier-1 markdown at `.kiho/state/okrs/<period>/<o-id>.md`, RACI-enforced pre-emit gate on okr-set mirroring the v5.22 recruit certificate pattern, approval-chain mechanism deferred to committee 02."
