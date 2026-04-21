---
name: values-alignment-audit
description: Use this skill quarterly to detect value drift by aggregating all values-flag entries from the past 90 days and grouping by value tag. If one value (e.g., transparency_vs_speed) accumulates >= 6 flags or shows a 30%+ spike vs the prior quarter, surfaces a "value drift signal" to CEO + relevant dept leads. Triggers on "values audit", "are we still aligned", "check value drift", or auto-fires once per quarter from CEO INITIALIZE. Without this skill, values-flag becomes write-only — incidents get logged but no one ever notices the patterns. Outputs a structured drift report with options: (a) reaffirm value, (b) re-rank values, (c) draft an explicit trade-off rule for the value-pair.
metadata:
  trust-tier: T2
  kiho:
    capability: evaluate
    topic_tags: [reflection, state-management]
    data_classes: [observations]
---
# values-alignment-audit

Values are silent until they conflict. values-flag is the per-incident logger; this skill is the per-quarter aggregator that turns the log into a question the org can answer.

> **v5.21 cycle-aware.** This skill is the `audit` phase entry in `references/cycle-templates/value-alignment.toml` (quarterly cycle, opens every 90 days). When run from cycle-runner, the cycle's `index.toml` is initially empty; this skill writes audit_id / values_flagged / drift_detected back into `index.audit.*`. The cycle's downstream `decide` phase opens a committee if drift_detected; otherwise short-circuits to closed-success. Atomic invocation remains supported for ad-hoc audits.

## When to use

- Quarterly cadence (every 90 days; CEO INITIALIZE auto-trigger)
- After a sev1 incident whose postmortem cites "value tension" as a contributing factor
- Pre-charter-revision: before changing the org's stated values, audit the actual recent friction

Do **NOT** invoke when:

- Fewer than 5 values-flag entries in the audit window — no statistical signal
- A user has asked about a specific recent decision — that's `decision-audit`, not values-audit
- The current turn is mid-feature — values audit is reflection, not in-band

## Inputs

```
window_days: <int>                # default 90
threshold_count: <int>            # default 6 (per-value)
threshold_spike_pct: <int>        # default 30 (vs prior window)
include_dept_breakdown: <bool>    # default true
```

## Procedure

1. **Collect values-flag entries.** Walk `state/values-flags/*.{md,jsonl}` from the last `window_days`. Extract `{ts, value_tag, severity, context_ref, agent_id}`. Also collect prior window for delta computation.

2. **Aggregate per value_tag.**
   - count_current
   - count_prior
   - spike_pct = ((current - prior) / max(prior, 1)) * 100
   - severity_distribution
   - top contributing dept (from agent_id → org-registry lookup)

3. **Identify drift signals.** A value_tag is flagged if EITHER:
   - count_current >= threshold_count, OR
   - spike_pct >= threshold_spike_pct AND count_current >= 3

4. **For each flagged value, draft an options block:**
   - **(a) Reaffirm the value.** Recommended when the recent flags resolved correctly via the existing rule; the spike was situational.
   - **(b) Re-rank values.** Recommended when the value frequently loses to another value in the same tension-pair; suggests a stable rebalance.
   - **(c) Draft an explicit trade-off rule.** Recommended when most flags are "we paused unsure"; a documented rule removes future ambiguity.

5. **Write the drift report.** Call `storage-broker` op=`put`:
   ```
   namespace: state/values-audits/<audit_id>
   kind: values-audit
   access_pattern: read-mostly
   durability: project
   human_legible: true
   body: { audit_id, ts, window_days, per_value: [{tag, count_current, count_prior,
           spike_pct, severity_distribution, top_dept, options}],
           reaffirmed_count, re_ranked_count, new_rules_drafted }
   ```

6. **Notify CEO + dept leads** named in `top_dept`. One `memo-send severity=fyi` per recipient with the drift report ref.

7. **Memory reflections** to dept leads (type=reflection, importance=6): "Value <tag> shows drift in your dept; recommended option <a/b/c>".

8. **Conditional escalation.** If any flagged value's `options` answer is `(b) re-rank`, the CEO MUST schedule a values committee within 7 days; this skill writes the committee proposal to `state/proposals/values-rerank-<audit_id>.md` for the CEO's next turn.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: values-alignment-audit
STATUS: ok | error
AUDIT_ID: <id>
WINDOW_DAYS: <int>
TOTAL_FLAGS: <count>
VALUES_FLAGGED: <count>
PER_VALUE_SUMMARY:
  - tag: <value>
    count: <N>
    spike_pct: <int>
    recommended_option: <a|b|c>
RE_RANK_PROPOSALS: <count>   # any (b)? requires CEO follow-up committee
AUDIT_REF: md://state/values-audits/<id>.md
```

## Invariants

- **Aggregate, don't re-litigate.** Each individual flag is settled at flag-time; this audit is about *patterns*.
- **Three options, no others.** Reaffirm / re-rank / draft-rule. If something else is needed, that's a charter-level conversation, not this skill.
- **Re-rank requires committee.** No CEO unilateral action on stated values.
- **No agent-blame.** Drift reports cite contributing dept (for accountability) but never single agents (values flags are systemic signals).

## Non-Goals

- Not a flag-creation tool. `values-flag` opens individual flags; this skill only reads them.
- Not a sentiment analyzer. The audit is structural (counts, spikes), not interpretive.
- Not a substitute for one-on-ones. Coaching individual agents about value-aligned behavior happens in 1:1.
- Not for cross-org comparison. Single-project scope; cross-project values-rollup is out of scope.

## Anti-patterns

- Never rank values in option (b) without a committee. Drafting the proposal is fine; deciding is not.
- Never set threshold_count below 3. Below that, you're amplifying noise.
- Never run the audit during a sev1. Wait for the incident to close + postmortem to land; otherwise the audit is dominated by acute, not chronic, signals.
- Never write to values-flag from this skill. One-way read.

## Grounding

- `skills/core/values/values-flag/SKILL.md` — the upstream per-incident flag logger.
- `references/committee-rules.md` — the committee process used for re-rank decisions.
- `references/data-storage-matrix.md` — values-flags storage (currently grandfathered; matrix row to be added if drift becomes structural).
