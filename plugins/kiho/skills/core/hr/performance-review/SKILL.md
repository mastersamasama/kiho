---
name: performance-review
description: Use this skill when CEO + dept lead need to formally rate an IC on accuracy / reliability / collaboration / growth / safety based on agent-performance.jsonl telemetry, and feed the verdict into agent-promote. Distinct from one-on-one (1:1 is coaching; performance-review is measurement). Runs quarterly per IC by default; can be triggered ad-hoc when an IC is up for promotion or demotion. Triggers on "performance review for <agent>", "rate <agent>", "promotion review", or auto-fires when an agent's task count crosses 50 since the last review. Reads agent-performance.jsonl + skill-invocations.jsonl + recent retrospective + recent 1:1 observations from the lead's memory; writes a structured rating sheet to state/perf-reviews/<agent>-<quarter>.md and a memory observation to both the IC and the lead.
metadata:
  trust-tier: T2
  kiho:
    capability: evaluate
    topic_tags: [reflection, lifecycle]
    data_classes: [agent-performance, skill-invocations, observations]
---
# performance-review

Quarterly measurement, not coaching. The 1:1 ceremony is the coaching channel; performance-review is the formal record that feeds promotion/demotion/recomposition decisions. Run sparingly (quarterly) but deliberately — every rating goes into the audit trail and is consumed by agent-promote.

> **v5.21 cycle-aware.** This skill is the `adoption-monitor` phase entry in `references/cycle-templates/talent-acquisition.toml` (90-day post-onboard check) AND can be invoked atomically for ad-hoc reviews. When run from cycle-runner, the cycle's `index.toml` carries `index.recruit.winner`; this skill writes the perf-review ref + recommendation back into `index.adoption.*` for the cycle's success_condition. Atomic invocation remains the primary path for routine quarterly cadence.

## When to use

- Quarterly cadence per IC (auto-trigger: every 50 completed tasks per agent since last review)
- Pre-`agent-promote` evaluation (CEO needs the structured rating to justify the move)
- Cross-dept transfer prep (receiving dept lead reads the most recent perf-review)

Do **NOT** invoke when:

- The IC has < 10 completed tasks in the review window — no statistical signal
- A 1:1 would suffice (coaching/feedback) — use `one-on-one` instead
- An incident just happened — wait until the postmortem closes; perf-review during fresh incident heat is biased

## Inputs

```
ic_id: <agent-id>                   # required
window: quarter | semester | year   # default quarter
include_recommendations: <bool>     # default true
reviewers: { ceo: ceo-01, lead: <dept-lead-id> }   # optional; defaults derived from org-registry
```

## Procedure

1. **Resolve the review window.** Default `quarter` = last 90 days. Window must span ≥ 10 completed tasks for `ic_id` in `agent-performance.jsonl`; if not, return `status: deferred reason=insufficient_signal_<count>_tasks`.

2. **Pull telemetry.** Read from `<project>/.kiho/state/`:
   - `agent-performance.jsonl` rows where `agent_id == ic_id` AND `ts ∈ window` → success rate, avg confidence, avg duration
   - `skill-invocations.jsonl` rows where `agent_id == ic_id` AND `ts ∈ window` → skill diversity, failure clusters
   - Last 5 retrospectives in window → mentions of `ic_id` (positive, neutral, negative)
   - Lead's memory `observations.md` last entries with `ic_id` in subject → coaching observations

3. **Score 5 axes (0–5 scale, integer).** Each axis MUST cite ≥ 1 evidence pointer (jsonl row range or memory ref):
   | Axis | Definition | Evidence source |
   |---|---|---|
   | accuracy | success rate × avg confidence | agent-performance.jsonl |
   | reliability | task completion w/o blocker chain ratio | skill-invocations.jsonl |
   | collaboration | help-wanted claim rate, dept-sync responsiveness | help-wanted/<cycle>.jsonl + dept-digests |
   | growth | new skills exercised, capability-matrix proficiency delta | capability-matrix.md diffs |
   | safety | incident count where IC was contributing factor | incidents/index + postmortems |

4. **Compute composite.** Weighted average: accuracy 0.30, reliability 0.25, collaboration 0.15, growth 0.15, safety 0.15. Round to 1 decimal.

5. **Draft recommendations** (if `include_recommendations: true`): one of `promote | hold | reposition | demote | exit`. The recommendation is the *reviewers'* judgment, not a hard threshold — composite < 2.5 strongly suggests reposition/demote/exit; > 4.0 strongly suggests promote.

6. **Write the rating sheet.** Call `storage-broker` op=`put`:
   ```
   namespace: state/perf-reviews/<ic_id>
   kind: perf-review
   access_pattern: read-mostly
   durability: project
   human_legible: true
   body: { ic_id, window, ts, axis_scores, composite, evidence_refs,
           reviewers, recommendation, narrative }
   ```

7. **Write memory observations** to both reviewers and the IC:
   - **Lead memory** (type=observation, importance=7): `"Perf-review for <ic_id> Q<n>: composite <score>; recommendation <rec>"`
   - **IC memory** (type=observation, importance=7, written_by=lead): `"Perf-review Q<n>: <axis_summary>; growth focus next quarter: <one_line>"`
   - **CEO ledger** (jsonl row): `{ action: perf_review_complete, ic_id, composite, recommendation }`

8. **Conditional handoff to agent-promote.** If recommendation is `promote | demote | exit | reposition`, append the perf-review ref to `state/promotion-queue.jsonl` for the next agent-promote cycle.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: performance-review
STATUS: ok | deferred | error
IC_ID: <id>
WINDOW: <q-n>
TASKS_IN_WINDOW: <count>
AXIS_SCORES: { accuracy, reliability, collaboration, growth, safety }
COMPOSITE: <0.0-5.0>
RECOMMENDATION: <promote | hold | reposition | demote | exit>
REVIEW_REF: md://state/perf-reviews/<ic>/<ts>.md
HANDOFF_TO_PROMOTE: <bool>
```

## Invariants

- **Two reviewers, both must sign.** CEO + dept lead. Single-reviewer perf-reviews are biased; if dept lead is on leave, CEO + a peer dept lead substitutes.
- **Evidence-based, not impression-based.** Every axis score cites a jsonl row range or memory ref. No vibes.
- **Recommendation ≠ decision.** agent-promote is the deciding skill; perf-review feeds it.
- **No surprise demotion.** If `recommendation: demote | exit`, the IC must have had ≥ 1 prior perf-review with `recommendation: hold` documenting the trend. First-review-demote is a process bug.

## Non-Goals

- Not a 1:1 transcript. Coaching dialogue is logged in 1:1 ceremonies.
- Not a salary discussion (no salaries here, but the analogy: this is rating, not compensation).
- Not a forced-distribution exercise. Multiple ICs may all rate 4.0+; absolute thresholds, not relative ranks.
- Not a moment-in-time judgment. Window is ≥ 90 days; cherry-picking single iterations is forbidden.

## Anti-patterns

- Never run perf-review on yourself (CEO can't perf-review CEO; that's `memory-reflect` territory).
- Never hide the rating sheet from the IC. They get a memory observation pointing to it.
- Never down-weight the safety axis. Even if the other 4 are 5.0, a single sev1 incident as contributing factor caps the recommendation at `hold`.
- Never average reviews from prior windows into the current one. Each perf-review is its own snapshot.

## Grounding

- `references/data-storage-matrix.md` rows `agent-performance` + `skill-invocations` — the canonical telemetry sources.
- `skills/core/hr/agent-promote/SKILL.md` — the deciding skill that consumes this output.
- `skills/core/ceremony/one-on-one/SKILL.md` — the coaching ceremony performance-review explicitly is NOT.
- `agents/kiho-ceo.md` INTEGRATE step (skill-invocations + agent-performance writes) — the upstream telemetry source.
