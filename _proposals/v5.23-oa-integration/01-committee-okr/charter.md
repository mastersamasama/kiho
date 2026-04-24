# Charter — OKR framework committee

## Committee identity

- **committee_id:** `okr-framework-2026-04-23`
- **topic:** "How should kiho support company-level OKRs (Objectives + Key Results)?"
- **chartered_at:** 2026-04-23T14:00:00Z
- **reversibility:** reversible (all T1/T2 additions; no agent terminations)
- **knowledge_update:** true (decision becomes a KB synthesis page)

## Members (quorum 4 of 5)

- **@kiho-pm-lead** — product responsibility for plan.md, priority arbitration; owns how OKRs interact with plan.md tasks and cycle-runner
- **@kiho-eng-lead** — technical feasibility; owns storage format, skill authoring rules
- **@kiho-hr-lead** — performance-review interaction; OKR → individual agent goal cascades
- **@kiho-auditor-skeptic** — challenges "feature because OA has it" reflex
- **@kiho-researcher** — Lark OKR primary source; quarterly-review cadence research

Clerk: auto-assigned per `kiho-clerk`. Not a member, does not vote.

## Input context

- User's stated motivation: "lark can let user setup okr, and we may integrate to ket agent make okr etc"
- Gap score from `00-gap-analysis.md` §matrix row 1: **HIGH** — no company-level goal hierarchy, no O→KR→task linkage, no scoring semantics
- WebSearch evidence (2026-04-23): Lark OKR supports weighted KRs, alignment tree with tagging, quarterly review + periodic check-ins, profile visibility

## Questions the committee MUST answer

| # | Question | Why it matters |
|---|---|---|
| Q1 | **Storage location** — new `core/okr/` skill portfolio vs extension of `plan.md` vs new cycle-template (`okr-quarterly`)? | Decides integration surface and how OKRs compose with existing state |
| Q2 | **O→KR→task alignment tree** — how is it represented in markdown? | Must be Tier-1 canonical (committee-reviewable); must be machine-parseable for the alignment view |
| Q3 | **Check-in cadence** — every Ralph-loop turn? Per-cycle boundary? Explicit `okr-checkin` invocation? | Over-eager = ceremony noise; under-eager = dead goals |
| Q4 | **Scoring mechanics** — 0.0–1.0 per KR with weight × score aggregation? Binary met/unmet? Stretch-goal double-counting? | Determines how OKRs feed dashboards + retros |
| Q5 | **RACI** — who can set O? Who can update KR progress? Who closes the cycle? | Must align with existing RACI protocol |
| Q6 | **Interaction with cycle-runner budgets** — does an OKR become a cycle? Does a cycle roll up to OKR? | Deep integration decision; has downstream implications for cycle-events.jsonl schema |
| Q7 | **Does the OKR framework need a runtime gate (v5.22-analogue)?** | Writes to `okr/` surface must match the kb-manager/recruit pattern |

## Success criteria

Committee closes successfully when it produces a unanimous position (all 5 members agree on exact string after normalization), no unresolved challenges remain, aggregate confidence ≥ 0.90, within 3 rounds. The closing position must cover:

- A concrete storage decision (one of: new `core/okr/` skill portfolio | `plan.md` extension | new cycle template | some combination). Reasoning must cite `references/data-storage-matrix.md` or motivate a new row addition (which would require a separate Storage-fit committee follow-up).
- A proposed skill list: 3–5 new skill IDs with one-line purposes (e.g., `okr-set`, `okr-checkin`, `okr-align`, `okr-close`, `okr-report`).
- A decision on the cycle-template question (whether `okr-quarterly` is a new template under `references/cycle-templates/`).
- A runtime-gate posture (hook needed? certificate marker? or committee-reviewable without hook?).

If unanimous close fails within 3 rounds, the CEO applies the escalation decision table (`committee-rules.md` §Escalation) — this is a reversible decision without strong dissent unless one member rates dissent > 0.80, so the default is **PROCEED** with winner ≥ 0.80, else **ASK_USER**.

## Constraints + references the committee must honor

- `plugins/kiho/references/committee-rules.md` — full normative spec (close rule, 3-round cap, confidence aggregation, transcript format). **Binding.**
- `plugins/kiho/references/storage-architecture.md` + `data-storage-matrix.md` + `storage-tech-stack.md` — tier selection; any new data class requires a matrix-row addition (flagged as follow-up Storage-fit committee, not blocker for this committee).
- `plugins/kiho/references/capability-taxonomy.md` — new skills' `metadata.kiho.capability` MUST be one of the 8 verbs (`create | read | update | delete | evaluate | orchestrate | communicate | decide`).
- `plugins/kiho/references/topic-vocabulary.md` — new skills' `topic_tags` from closed 18-tag set.
- `plugins/kiho/references/cycle-architecture.md` — if a new cycle template is proposed.
- `plugins/kiho/skills/CATALOG.md` — proposed additions must slot into the routing structure.
- `plugins/kiho/references/raci-assignment-protocol.md` — OKR RACI must fit the existing protocol.
- `plugins/kiho/references/skill-authoring-standards.md` + `skill-authoring-patterns.md` (≥ 6/9 patterns) — any skill proposal must be author-able under the standard.

## Out of scope (explicit)

- **No implementation.** Committee produces a design document; skills are authored in a subsequent v5.23 implementation plan.
- **No integration with external OKR products** (Lark OKR API, Weekdone, Lattice). kiho stays self-contained markdown-canonical; external OKR systems are pull-side only via `kiho-researcher`.
- **No per-agent private OKRs that bypass the KB gateway.** All committee-reviewable OKR state (at minimum company O and department Os) is Tier-1 markdown; agent-private tactical notes remain in Tier-3 agentic memory.
- **No "AI OKR autocomplete."** User specifies objectives; committee considers whether agents MAY draft KR candidates under that O, but MUST NOT auto-commit them.

## Escalation triggers (mid-deliberation)

- Any member raises a values-flag (`values-flag` skill) on OKR pressure producing Goodhart-law KR gaming → pause, resolve via `values-alignment-audit` before resuming.
- Storage decision collides with existing data-storage-matrix row → defer that sub-question to a Storage-fit committee, continue closing on remaining questions with annotated dependency.
- Research-deep is needed for Lark OKR mechanics depth → CEO-level decision to budget one `research-deep` invocation (≤ 20 minutes wall-clock, ≤ 40 pages); researcher reports findings into round N+1 research phase.
