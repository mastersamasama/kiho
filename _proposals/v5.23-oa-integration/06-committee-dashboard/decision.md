# Decision — analytics dashboard (committee dashboard-analytics-2026-04-23)

## Status

Accepted by unanimous close at aggregate confidence 0.91, 1 round.

## Context

Lark/DingTalk/Feishu dashboards show per-period rollups of activity: tasks shipped, approvals closed, incidents + MTTR, hiring events, engagement. kiho has telemetry (`cycle-events.jsonl`, `agent-performance.jsonl`, `factory-verdicts.jsonl`, `skill-invocations.jsonl`, committee closes) and regenerated indexes (`cycles/INDEX.md`, `org-registry.md`) but no synthesized period-rollup view. The committee established that the gap is the period rollup, not the data collection.

## Decision

**Regenerable Tier-2 dashboard via `bin/dashboard.py`. Zero new skills.**

### 1. New Python helper `bin/dashboard.py`

Stdlib-only. Reads existing JSONL + committee transcripts + cycle handoffs. Emits markdown. Invocation:

```bash
python bin/dashboard.py --period per-cycle --cycle-id <id> --out .kiho/state/dashboards/<cycle-id>.md
python bin/dashboard.py --period quarterly --quarter 2026-Q2 --out .kiho/state/dashboards/2026-Q2.md
```

Idempotent — re-running on same inputs produces byte-identical output (like `kiho_clerk extract-rounds`).

### 2. Seven metrics, each with named consumer

| # | Metric | Source | Consumer | Notes |
|---|---|---|---|---|
| 1 | `cycles_closed / cycles_opened` | cycle-events.jsonl | retrospective | velocity signal |
| 2 | `incidents_opened`, `mean_mttr_seconds` | cycle-events.jsonl (incident-lifecycle entries) | retrospective | reliability signal |
| 3 | `agents_hired`, `agents_rejected`, `hire_rate` | ledger `recruit_*` entries + rejection-feedback | HR ceremony / retrospective | hiring throughput |
| 4 | `committees_convened`, `unanimous_close_rate`, `mean_rounds_used` | committee transcript close blocks | retrospective + skill-evolution | deliberation health |
| 5 | `factory_pass_rate`, `factory_reject_rate` | factory-verdicts.jsonl | skill-evolution committee | generator quality |
| 6 | `kb_pages_added_rate`, `kb_stale_count` | ledger `kb_add` entries + kb-lint output | kb-lint health check (rate view) | growth signal |
| 7 | `top_5_agent_scores`, `bottom_5_agent_scores` | agent-score-<period>.jsonl (committee 05 output) | agent-promote committee | promotion targeting |

Each metric's addition was gated by the cost-hawk's "named consumer" test during round 1 choose. No decorative metrics.

### 3. Output shape

```markdown
# Dashboard — 2026-Q2 (cycle-id: cyc-web3-quant-engine-007)

Generated: 2026-06-30T23:59:59Z
Source: bin/dashboard.py --period quarterly --quarter 2026-Q2

## Velocity
- cycles_closed: 23
- cycles_opened: 21
- ratio: 0.913 (slight backlog reduction)

## Reliability
- incidents_opened: 2
- mean_mttr_seconds: 1847  (~31 min)

## Hiring
- agents_hired: 3
- agents_rejected: 7
- hire_rate: 0.30

## Committees
- convened: 41
- unanimous_close_rate: 0.87
- mean_rounds_used: 1.6

## Factory
- factory_pass_rate: 0.78
- factory_reject_rate: 0.22

## KB
- pages_added_rate_per_week: 4.2
- stale_count: 6

## Agent scores (top 5)
1. kiho-eng-lead : 0.91
2. kiho-kb-manager : 0.88
3. kiho-pm-lead : 0.85
4. kiho-hr-lead : 0.82
5. kiho-researcher : 0.79

## Agent scores (bottom 5)
- (intentionally omitted if all ≥ 0.70)
```

Minimalist prose — no ASCII charts, no emojis. The markdown is a data artifact, not a presentation artifact.

### 4. Cadence

- **Per-cycle**: `bin/dashboard.py --period per-cycle --cycle-id <id>` invoked at cycle close, by retrospective ceremony.
- **Quarterly**: `bin/dashboard.py --period quarterly --quarter YYYY-QN` invoked at the end of quarter, either by a manual user `/kiho` turn or a scheduled `/loop`.

NOT per-turn. NOT daily. Over-emission is what distinguishes "dashboard" from "noise."

### 5. Data-storage-matrix row

| Slug | Tier | Format | Path | Gatekeeper | Regenerable |
|---|---|---|---|---|---|
| dashboard-period-md | T2 | markdown (generated) | `.kiho/state/dashboards/<period>.md` | bin/dashboard.py | yes, from all source JSONL streams |

Storage-fit follow-up committee for row addition (v5.19 doctrine).

### 6. Retrospective ceremony integration

`skills/core/ceremony/retrospective/SKILL.md` §Procedure: first step after context-load is `Read .kiho/state/dashboards/<current-cycle>.md` (invoking `bin/dashboard.py` first if file missing or stale). Retro narrative opens by referencing the quantitative preface; specific values anchor the conversation.

## Consequences

### Positive

- Period rollup gap closed with minimal infrastructure.
- Regenerable T2 avoids KB gateway + kb-manager ceremony for dashboard updates.
- Each metric has a named consumer — no decoration.
- Reuses existing telemetry; zero new data sources introduced.
- Composable with committee 05 output (agent-score) — natural synergy.
- Retrospective ceremony gains quantitative anchor without becoming presentation-heavy.

### Negative

- `bin/dashboard.py` becomes a maintenance surface — adding a metric means editing the script + adding a consumer argument, so additions have visible cost.
- Dependency on committee 05's `agent-score-<period>.jsonl` — if committee 05 is not adopted in v5.23, metric 7 drops out or gets a stub.
- Idempotency requires deterministic input ordering; the script must sort JSONL entries before consuming (minor implementation detail).

## Alternatives considered and rejected

- **T1 synthesized via kb-manager** — rejected; kb-manager would add narrative flair that doesn't justify the gateway overhead for a data artifact. Retrospective already produces the narrative.
- **New `dashboard-generate` skill** — rejected as new surface when an org-sync-style script covers the workload.
- **Daily / weekly cadence** — rejected as firing without a natural ceremony anchor; would become noise.
- **Per-agent dashboards** — rejected; aggregation at org level; per-agent detail already lives in `capability-matrix`, soul, `agent-score-<period>.jsonl`.
- **External dashboard / web UI** (Grafana, custom HTML) — rejected per charter out-of-scope.

## Scope estimate

- 1 new Python script (~300 lines with unit tests)
- 1 data-storage-matrix row (Storage-fit follow-up)
- 1 SKILL.md edit (`retrospective` — dashboard-load step)
- 0 new skills, 0 new agent.md changes, 0 hook changes
- Estimated implementation: ~6 hours

## Dependencies

- Existing telemetry streams (shipped).
- Committee 05 (agent-score) output for metric 7 (soft dependency — metric 7 is optional if committee 05 is not adopted in v5.23).
- Storage-fit follow-up committee.

## Next concrete step

Implementation plan authorizes: `bin/dashboard.py` scaffolding + unit tests + 3 synthetic-fixture scenarios (empty period, normal period, outlier period), retrospective SKILL.md edit, data-storage-matrix row via Storage-fit committee. First real dashboard is per-cycle rollup at next cycle close; first quarterly is 2026-Q2 end.
