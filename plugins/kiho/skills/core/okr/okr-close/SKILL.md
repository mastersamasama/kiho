---
name: okr-close
description: Close an active Objective at period end. Computes the aggregate score as a weighted mean of KR current_scores, with stretch KRs capped at 0.7 to prevent double-counting. Marks the Objective status=closed, writes the final aggregate + closed_at + optional narrative, rewrites the file preserving the certificate marker, then optionally archives the file to .kiho/state/okrs/<period>/_closed/. Refuses to close an Objective whose status is already closed or deferred. Use this skill at the end of a quarter when wrapping up OKRs, after a postmortem cycle completes an incident-remediation Objective, or when a mid-period Objective has naturally concluded. Invocation is always explicit — there is no time-based auto-close.
argument-hint: "o_id=<id> [archive=<bool>] [narrative=<text>]"
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: active
  kiho:
    capability: update
    topic_tags: [governance, planning, lifecycle]
    data_classes: ["okrs-period-md"]
    storage_fit:
      reads:
        - "<project>/.kiho/state/okrs/<period>/O-*.md"
      writes:
        - "<project>/.kiho/state/okrs/<period>/O-*.md"
        - "<project>/.kiho/state/okrs/<period>/_closed/O-*.md (on archive=true)"
---
# okr-close

End-of-period aggregation. Reads the Objective's KRs, computes the weighted-mean aggregate, writes the close block, and (optionally) moves the file into the period's `_closed/` archive. After close, the Objective is frozen — `okr-checkin` refuses to touch it.

## When to use

- Period end (quarter close): iterate through every `status: active` Objective in `.kiho/state/okrs/<period>/` and close them. Typically bundled into a retrospective invocation.
- Mid-period wrap-up when the underlying initiative has naturally concluded (e.g., an incident-remediation Objective whose incident has been resolved and verified).
- User invokes `/kiho close the 2026-Q2 OKRs` after the quarter end.

Do **not** invoke:

- Before the period actually ends (premature closure = ignoring remaining work).
- To retract a mistaken Objective. Mistaken Os are closed normally with a narrative explaining the mistake; the next period's retrospective references the lesson.
- To transition to a new period. Closing Q2 does not open Q3 — that's `okr-set` in the new period.

## Inputs

```
PAYLOAD:
  o_id:               <O id>                             # required
  archive:            <bool>                             # optional; default true
  narrative:          <multi-line markdown>              # optional; one-paragraph retrospective on the O
  closed_by:          <agent-id or "user">               # required
  ts:                 <iso>                              # optional; defaults to now()
  override_scores:    list                               # optional; last-minute corrections per KR
    - kr_id:          <stable slug>
      final_score:    <float in [0.0, 1.0]>
      note:           <text>
```

## Procedure

### 1. Load + validate

- Read the Objective file. Refuse on missing → `status: o_not_found`.
- Refuse on `status != active` → `status: o_already_closed` (closed/deferred are frozen).

### 2. Apply any override_scores

For each override, locate the KR, update `current_score` AND append a history entry with `by: <closed_by>`, `note: "<note or 'final adjustment at close'>"`.

### 3. Compute the aggregate

```
For each KR in the Objective:
  effective_score = current_score
  if KR.stretch == true AND effective_score > 0.7:
    effective_score = 0.7            # stretch cap prevents double-counting
  weighted = effective_score * (weight / 100)

aggregate = sum(weighted) * (100 / weights_sum)
aggregate = round(aggregate, 4)
```

The `(100 / weights_sum)` normalization scales the result back to [0, 1] when the KR weights don't sum to exactly 100 (allowed: `weights_sum ≤ 100` at emit). An aggregate of 1.0 means every KR fully met; 0.0 means no progress on any KR.

### 4. Write the close block

Append or replace a `## Close` block in the file:

```markdown
## Close

- closed_at: <iso>
- closed_by: <agent-id>
- rounds_of_checkins: <int>       # count of history entries across all KRs
- weights_sum_at_emit: <int>      # from frontmatter
- aggregate_score: <float>
- per_kr:
  - <kr_id>: <effective_score> (weight <int>, stretch <bool>)
  - ...
- narrative: |
    <optional narrative paragraph>
```

Frontmatter update: `status: closed`, `closed_at: <iso>`, `aggregate_score: <f>`.

Rewrite the full file — certificate marker preserved verbatim.

### 5. Archive (optional, default true)

If `archive == true`, move the file to `<project>/.kiho/state/okrs/<period>/_closed/<o_id>.md`. The `_closed/` subdirectory is not scanned by `okr-checkin` or by the dashboard's "active Objectives" list; the file stays committee-reviewable and grep-able.

Archive does NOT delete — git history preserves everything; `_closed/` is a scan-time convenience.

### 6. Ledger entry

```
{"ts": "<iso>", "action": "okr_close",
 "payload": {"o_id": "<id>", "aggregate_score": <f>, "archived": <bool>,
             "closed_by": "<id>", "kr_count": <n>}}
```

### 7. Remove from plan.md active list (company + department levels only)

If the closed Objective was mirrored into `plan.md ## Active Objectives` (step 6 of `okr-set` for company + department levels), remove its line from that section. Individual Os are not mirrored, so this step is a no-op for them.

## Response shape

```
## Receipt <REQUEST_ID>
OPERATION: okr-close
STATUS: ok | o_not_found | o_already_closed | invalid_override
O_ID: <id>
AGGREGATE_SCORE: <float in [0.0, 1.0]>
PER_KR_SCORES: {kr_id: score, ...}
ARCHIVED: <bool>
PLAN_UPDATED: <bool>
LEDGER_REF: jsonl://state/ceo-ledger.jsonl#seq=<n>
```

## Invariants

- **Idempotent re-close.** Calling `okr-close` on an already-closed O is a no-op with `status: o_already_closed`, never a silent re-write. Corrections post-close live in the next period's retrospective or a new O.
- **Stretch cap at 0.7.** A stretch KR scoring 0.95 contributes `0.7 × weight` to the aggregate. Stretch is aspirational at emit; it cannot retroactively inflate the close.
- **Aggregate in [0.0, 1.0].** The normalization divides by `weights_sum / 100` so partial-weight Objectives (weights_sum < 100) still produce aggregates that are comparable across Objectives.
- **Frozen on close.** After close, `okr-checkin` refuses. `okr-set` with the same o_id refuses (O ids are unique within a project).
- **Certificate preserved.** The emit-time certificate marker stays. Close adds content; it never strips the marker.

## Non-Goals

- **Not a period-rollover tool.** Closing 2026-Q2 does not create 2026-Q3 Objectives. Those go through `okr-set` fresh, with company-level ones requiring user accept again.
- **Not a performance review.** The aggregate is a number. Interpretation (who drove it, who didn't, what to change) happens in retrospective, `agent-promote`, and dashboard rollups — not here.
- **Not a rollup across Objectives.** Closing each O produces its own aggregate. Rollup to department / company level is a dashboard concern, not a close-time concern.

## Anti-patterns

- Closing every active O mechanically at the last day of the quarter regardless of whether the work actually concluded. Some Os carry over narrative-wise (e.g., "reduce tech debt" is a multi-quarter arc); they close with 0.5 and a narrative, and next period's new O carries the next phase.
- Using `override_scores` to inflate an Objective that clearly didn't land. The history entries are append-only; the override is visible. Sycophancy here is visible drift.
- Deleting closed files instead of archiving. Delete → lose diff-ability. Archive keeps them in git history AND under `_closed/` for directory scans.

## Grounding

- `skills/core/okr/okr-set/SKILL.md` — sibling skill that created the Objective.
- `skills/core/okr/okr-checkin/SKILL.md` — sibling skill that fed the KR current_scores this close aggregates.
- `references/okr-guide.md` — user-facing primer.
- `skills/core/ceremony/retrospective/SKILL.md` — the natural next step after close; retrospective pulls closed aggregates into its narrative.
- `bin/dashboard.py` — regenerates the period dashboard with closed-Objective aggregates on next invocation.
- `_proposals/v5.23-oa-integration/01-committee-okr/decision.md` — the decision record.

## Worked example

At the end of 2026-Q2, user invokes `/kiho close out all active 2026-Q2 OKRs`. CEO enumerates active Objectives in `<project>/.kiho/state/okrs/2026-Q2/` (excluding `_closed/` subdir) → 3 Objectives found. For each, `okr-close` is invoked in sequence. The company-level O `O-2026Q2-company-01` ships-v5.23 has KR aggregates 0.9 / 0.8 / 0.6 with weights 40 / 40 / 20 → aggregate = `(0.9×40 + 0.8×40 + 0.6×20) / 100 = 0.80`. File is closed, archived, ledger row written, plan.md line removed. Next dashboard regen shows `O-2026Q2-company-01: 0.800 (closed)` in the top-5 list.
