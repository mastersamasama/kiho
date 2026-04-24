# 00 — OA ←→ kiho capability gap analysis

## Scope

Evaluate every capability that Lark/Feishu, DingTalk, Notion, Workday, Monday, Asana, Linear, and Slack/Teams provide as a named product surface, and map each to kiho's equivalent (if any). For each gap where OA is objectively superior, decide whether to open a committee.

Sources:

- **Lark OKR** — `larksuite.com/product/okr` (create/align/track/analyze weighted OKRs, quarterly reviews, profile visibility, alignment tree)
- **Lark CLI** — `github.com/larksuite/cli` (200+ commands, 20+ AI Agent Skills across Messenger/Docs/Base/Sheets/Calendar/Mail/Tasks/Meetings — strongest architectural parallel to kiho)
- **DingTalk approvals** — `dingtalk-global.com` (multi-stage routing, amount-based conditional branches, automatic reminders, 3-day → 4-hour cycle-time compression)
- **Feishu Miaoji** — auto-transcription + action-item extraction
- **Lark Base** — spreadsheet-database with kanban/gantt/calendar/gallery views
- **Retrieved via WebSearch 2026-04-23**

## Gap matrix

| # | OA capability | kiho's today | Gap severity | Committee? |
|---|---|---|---|---|
| 1 | **OKR framework** — quarterly O→KR tree, weighted KRs, alignment up/down, mid-cycle check-ins, scoring, profile visibility | `plan.md` has RACI tasks; cycle-runner budgets are per-cycle, not company-wide | **HIGH** — no company-level goal hierarchy, no O→KR→task linkage, no scoring semantics | **YES** (01) |
| 2 | **Multi-stage conditional approval** — form → dept lead → finance → CEO with amount-threshold branches, auto-reminders, audit trail | `AskUserQuestion` is the single gate (only CEO calls it, only the human user answers); committees deliberate but don't route sequentially | **HIGH** — no agent-level sequential approval chain, no conditional routing by amount/risk/domain | **YES** (02) |
| 3 | **Company-wide broadcast + pinned announcements** — publish once, every employee sees it, pinning + expiry, optional acknowledgement tracking | `memo-send` is strictly peer-to-peer; no broadcast fan-out; no pinning semantics | **MEDIUM** — new skill plausible; overlap with shift-handoff to watch | **YES** (03) |
| 4 | **Pulse surveys / peer-feedback polls** — 1-question lightweight non-blocking signal from all or a capability-filtered subset | Committee vote is heavyweight + blocking; values-flag is single-person raising; no lightweight aggregate | **MEDIUM** — may be overlap with committee once scoped; committee may close with "not needed" | **YES** (04) |
| 5 | **360 performance review** — multi-peer + self + manager signals, rating aggregation, calibration | `performance-review` skill is single-reviewer (usually perf-reviewer agent) | **MEDIUM** — LLM-agent peer signal quality is open question; committee will decide whether to extend or reject | **YES** (05) |
| 6 | **Analytics dashboard** — period rollup of velocity (tasks/cycles closed), hiring (agents onboarded, rejected), incidents (count, MTTR), KB growth, cycle outcomes | `cycle-events.jsonl` + `cycles/INDEX.md` are raw telemetry; no synthesized period report; retrospective ceremony is narrative not quantitative | **MEDIUM** — clear extension point; regenerable T2 via deterministic script is natural | **YES** (06) |
| 7 | Action-item extraction from committee transcripts auto-pushed to assignees' `todos.md` | Transcripts contain decisions but don't auto-push | LOW-MED | **defer** — small clerk extension, doesn't warrant standalone committee |
| 8 | Smart Meeting Notes auto-transcribe | Committee transcripts are already the structured record; clerk produces them | N/A | **defer** — committees don't have a separate "meeting audio" surface |
| 9 | Lark Base multi-view database (kanban/gantt/calendar/gallery from same table) | Markdown + regenerated indexes (tags, backlinks, timeline, stale, questions, graph, by-confidence) already produce multi-view slicing | LOW | **defer** — markdown+indexes cover this |
| 10 | Calendar / time-zone scheduling | Cycle-runner has iter + wall-clock budgets; `/loop` can pace; but no calendar surface | N/A | **defer** — LLM agents don't have timezones; Ralph loop + budgets already cover cadence |
| 11 | LMS / training-completion tracking | `skill-learn` builds skill mastery; capability-matrix 1-5 scale tracks proficiency | LOW | **defer** — capability-matrix is the certification track |
| 12 | Integration marketplace (push-side publishing to Jira/Linear/GitHub) | `integration-audit` + `integration-register` track MCP/CLI *pull*; no push semantics | LOW | **defer** — out of scope for an orchestration harness |

Six gaps (1–6) qualify for committees. Seven gaps (7–12) are logged and deferred to the v5.23 roadmap backlog, to be revisited in a later cycle if user value emerges.

## Scoring rubric (used for the "Worth committee?" column)

A gap gets a committee when ALL four hold:

1. **Product-level named surface in OA.** The capability is a top-menu item in at least two OA suites (not a niche feature).
2. **No direct kiho equivalent.** If kiho has a skill or convention that already covers it, committee is not needed (even if the UX differs).
3. **Non-trivial design decision.** The implementation direction is not obvious — multiple plausible approaches exist and the choice matters.
4. **User value is plausible.** Solving the gap would plausibly make kiho more useful in practice, not just closer to a checklist.

Gaps 7 and 9–11 fail condition 2. Gap 8 fails condition 2 (transcripts already structured). Gap 10 fails condition 4 (timezones are not an agent concept). Gap 12 fails condition 4 (push-side integrations fight the harness model).

## kiho's existing OA-like strengths (preserve, do not replace)

The gap matrix would read as one-sided if it only catalogued OA's wins. kiho has architectural features with no OA analog:

- **Karpathy KB compilation** — OA wikis are static (Notion, Confluence); kiho's KB continuously recompiles into synthesis pages and maintains 6 derived indexes (tags, backlinks, timeline, stale, questions, graph, by-confidence). Gap 9 (Lark Base views) is already covered by this mechanism.
- **Cycle-runner TOML DSL** — OA BPA builders are GUI-driven. kiho's cycle-runner already executes declarative lifecycle templates (7 production templates). Any proposal that requires a new lifecycle should extend this, not build parallel infrastructure.
- **Committee with unanimous close + unresolved-challenge tracking + 3-round cap** — OA "approvals" are sequential sign-offs. kiho committees are deliberative convergence with explicit dissent tracking. The approval committee (02) will decide whether to add a *sequential* flavor without displacing the deliberative one.
- **Soul architecture** — OA has no concept of agent evolution over time. Soul drift via `memory-reflect` → `soul-overrides.md` has no OA counterpart; propose-and-review of agent personality changes is novel.
- **Skill-factory 10-step pipeline** — OA integration marketplaces are 1-shot installs. kiho's skill-factory is a generator with poka-yoke gates (critic, parity, stale-path, citation). New v5.23 skills produced by any committee MUST go through the factory.
- **v5.22 runtime gates (PreToolUse hooks)** — OA audit logs are after-the-fact. kiho blocks the write at the tool-call boundary. Every new storage surface introduced by v5.23 committees MUST carry the hook-analogue if it holds committee-reviewable state.

## Committees opened

1. `01-committee-okr/` — OKR framework
2. `02-committee-approval/` — multi-stage conditional approval
3. `03-committee-broadcast/` — company-wide announcements
4. `04-committee-pulse/` — lightweight pulse surveys
5. `05-committee-360review/` — multi-peer performance review
6. `06-committee-dashboard/` — period-rollup analytics

Each committee operates under `TIER: careful` per this /kiho turn's tier declaration. Full unanimous close at ≥ 0.90 required; escalation to the CEO (and ultimately to user) when the committee cannot converge.
