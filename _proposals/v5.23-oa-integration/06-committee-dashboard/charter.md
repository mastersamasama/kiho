# Charter — analytics dashboard committee

## Committee identity

- **committee_id:** `dashboard-analytics-2026-04-23`
- **topic:** "What should a kiho period-rollup dashboard contain, and where should it live?"
- **chartered_at:** 2026-04-23T16:30:00Z
- **reversibility:** reversible
- **knowledge_update:** true

## Members (quorum 4 of 5)

- **@kiho-kb-manager** — any synthesized period page is KB-adjacent; gateway concern
- **@kiho-comms** — dashboards feed into shift-handoff + retrospective ceremonies
- **@kiho-perf-reviewer** — agent-performance.jsonl is one of the main data sources
- **@kiho-eng-lead** — telemetry shape + deterministic rollup script authoring
- **@kiho-auditor-cost-hawk** — challenges every metric that doesn't earn its place

Clerk: auto-assigned. Not a member.

## Input context

- User gap: Lark/DingTalk show per-period activity rollups (tasks shipped, approvals closed, incidents MTTR). kiho has raw telemetry (`cycle-events.jsonl`, `agent-performance.jsonl`, `factory-verdicts.jsonl`, `skill-invocations.jsonl`) + `cycles/INDEX.md` but no synthesized dashboard.
- Gap score from `00-gap-analysis.md` §matrix row 6: **MEDIUM** — clear extension point; regenerable T2 via deterministic script is natural.
- Precedent: `cycles/INDEX.md` is already regenerated at CEO DONE-11 via deterministic scan; this extends the same pattern.

## Questions the committee MUST answer

| # | Question | Why it matters |
|---|---|---|
| Q1 | **Regenerable T2 vs synthesized T1** — is the dashboard a deterministic rollup (Tier-2, regenerable from JSONL telemetry) or a kb-manager-written synthesis page (Tier-1)? | Determines hook posture + gatekeeper |
| Q2 | **Period granularity** — daily / weekly / per-cycle / per-quarter? One granularity or multiple concurrent? | Monthly + quarterly is a natural pair; daily may be noise |
| Q3 | **Metric list** — which metrics are load-bearing (change behavior) vs decorative (nice to see, no action)? Cost-hawk must veto any metric with no downstream consumer | The auditor's primary concern |
| Q4 | **Integration with retrospective ceremony** — dashboard feeds retro; retro references dashboard; single direction or both? | Must not create circular state |
| Q5 | **Skill shape** — a new `dashboard-generate` skill invoked by ceremony? Extension of org-sync? Standalone script called from ceremony? | Affects skill count vs script/ceremony blending |
| Q6 | **Emission trigger** — on every cycle close? On shift-handoff? Explicit user invocation only? CEO DONE step? | Must not burn turn budget writing dashboards nobody will read |

## Success criteria

Unanimous position covering:

- A specific **tier decision** (T2 regenerable vs T1 synthesized) with reasoning rooted in `storage-architecture.md`.
- A **metric list** with each metric defended by its downstream consumer (retrospective? skill-deprecate? agent-promote?).
- A **skill shape** decision — new `dashboard-generate` skill OR a referenced script emitted by an existing skill/ceremony.
- A **period granularity** decision with cadence.
- A **verification path** — how does a reader of the dashboard file confirm the numbers are not stale?

Close rule: unanimous + no unresolved challenges + aggregate confidence ≥ 0.90, ≤ 3 rounds.

## Constraints + references

- `plugins/kiho/references/storage-architecture.md` + `data-storage-matrix.md` + `react-storage-doctrine.md` — tier selection.
- `plugins/kiho/skills/core/harness/org-sync/SKILL.md` — existing regenerable T2 pattern (org-registry.md).
- `plugins/kiho/skills/_meta/cycle-runner/SKILL.md` — cycles/INDEX.md is regenerated at CEO DONE; same pattern.
- `plugins/kiho/agents/kiho-ceo.md` §DONE step 11 — where existing regeneration happens.
- `plugins/kiho/skills/core/ceremony/retrospective/SKILL.md` — the natural consumer.
- Existing telemetry sources: `cycle-events.jsonl`, `agent-performance.jsonl`, `factory-verdicts.jsonl`, `skill-invocations.jsonl` — the dashboard reads these; no new telemetry introduced.

## Out of scope (explicit)

- **No external dashboard / web UI.** kiho is markdown-canonical. Grafana-style live dashboards are explicitly non-goal.
- **No real-time updates.** Dashboard is regenerated on demand or at ceremony boundaries. No watch mode.
- **No per-agent dashboards.** Aggregation is at org level; per-agent detail lives in soul + capability-matrix.
- **No metric additions requiring new telemetry sources.** Committee must fit existing JSONL streams. New telemetry = separate Storage-fit committee.

## Escalation triggers

- Cost-hawk vetoes enough metrics that no viable dashboard remains → close with "existing cycles/INDEX.md + org-registry.md are sufficient; no new synthesis" as a valid unanimous outcome.
- T1 vs T2 split that can't resolve → ASK_USER with concrete preview of both shapes.
