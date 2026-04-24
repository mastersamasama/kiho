---
name: okr-close-period
description: Batch-close all active Objectives for a period with cascade semantics (v6.2+). Invoked by `kiho-okr-master` when the scanner emits `period-close` or `cascade-close` action, or by the `okr-period.toml` cycle template's `close` phase. Walks the OKR alignment tree leaf-first (individual → dept → company) so parent aggregates reflect children's final scores. Applies the `[okr] cascade_rule` (default: `deferred`) when a parent closes with aggregate < 0.3 — all downstream active Os are flipped to `status: deferred` with narrative citing the parent's close. Preserves each OKR's certificate marker on the whole-file rewrite. Memos each affected owner on close. Use when `today > period.end` for any period with active Os, or when a company O is manually closed mid-period with cascade implications.
argument-hint: "period=<YYYY-QN> [cascade_rule=deferred|archive] [dry_run=<bool>]"
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
        - "<project>/.kiho/state/okrs/**"
        - "<project>/.kiho/config.toml"
      writes:
        - "<project>/.kiho/state/okrs/<period>/O-*.md"          # via okr-close
        - "<project>/.kiho/state/okrs/<period>/_closed/O-*.md"  # archive move
---
# okr-close-period

Batch + cascade close orchestrator for an OKR period. Reads the tree; invokes `okr-close` (the atomic primitive) leaf-first; applies cascade rule.

## When to use

- CEO INITIALIZE step 17.5 routes a `period-close` scanner action to OKR-master, who delegates here.
- `okr-period.toml` phase `close` invokes this as its entry skill.
- A company O is manually closed mid-period and `[okr] cascade_rule` implies downstream cleanup.

Do NOT invoke:

- Before period end (unless manual-mid-period-close is the explicit case). The scanner is conservative — only emits `period-close` when `today ≥ period.end`.
- On a period that has no active Os (trivial no-op; scanner won't emit).
- To close a single O — use `okr-close` directly.

## Inputs

```
PAYLOAD:
  period:          <YYYY-QN or YYYY-HN or custom slug>    # required
  cascade_rule:    deferred | archive                     # optional; default from [okr] cascade_rule
  dry_run:         <bool>                                 # optional; compute without writing
  trigger_o_id:    <O-id>                                 # optional; for cascade-close path from single parent close
```

## Procedure

### 1. Enumerate active Os in the period

Read `<project>/.kiho/state/okrs/<period>/O-*.md` (excluding `_closed/` subdir). Filter `status == active`.

### 2. Topologically sort leaf-first

Use the `aligns_to` frontmatter field to build the tree:

```
level 3: individual Os  ← leaves
level 2: department Os
level 1: company Os     ← roots
```

Close in order 3 → 2 → 1. This guarantees a company O's close aggregate can (in a future enhancement) incorporate its closed dept Os' aggregates; for v6.2 PR 3 the aggregate is still computed only from the O's own KRs, but ordering is established for v6.3+ aggregate-rollup.

### 3. Per-OKR close

For each O in leaf-first order, invoke `okr-close` (sk-082) with:

```
o_id: <current>
closed_by: kiho-okr-master
narrative: "Period auto-close at <today>. Aggregate is weighted mean of final KR scores (stretch KRs capped at 0.7 per okr-close semantics)."
archive: true
```

Capture returned `aggregate_score`. Log `okr_period_auto_close, o_id, aggregate`.

### 4. Apply cascade for children of trigger O (if cascade-close path)

If `trigger_o_id` is set, additionally walk the subtree rooted at `trigger_o_id` and apply the cascade rule to children that are still `status: active` AFTER step 3:

- **`cascade_rule = "deferred"`** (default): invoke `okr-close` for each child with `narrative: "Cascade from parent <trigger_o_id> close (aggregate <X>). Defer preserves option value; revisit next period."` and manually flip `status: deferred` in the file (rewriting via okr-close which treats deferred as a valid close outcome). Memo each child's owner with the cascade context.
- **`cascade_rule = "archive"`**: same narrative but `status: closed` with 0.0 aggregate credit for unscored KRs. Children go straight to `_closed/`.

### 5. Memo fanout

For each closed O (via either close-leaf-first or cascade):

- `memo-send to=<owner> severity=fyi` with `subject: "OKR closed: <o_id>, aggregate <X>"` + body citing the close reason (period-end or cascade).
- For cascade-defer, also memo the owner "Option: carry over to next period, or close as deferred — address in next retrospective."

Batch to `@all` using the v5.23 wildcard `memo-send` extension if > 10 memos would otherwise fire; single `broadcast announcement` via `.kiho/state/announcements/` with a summary table.

### 6. Ledger + cycle-events trail

Emit to `<project>/.kiho/state/ceo-ledger.jsonl`:

```
{"ts": "<iso>", "action": "okr_period_auto_close_complete",
 "payload": {"period": "<period>", "closed_count": <n>, "cascade_defer_count": <m>,
             "cascade_archive_count": <k>, "triggered_by": "scanner|manual|cascade"}}
```

## Dry-run mode

When `dry_run: true`:

- All of steps 1-4 execute in simulation (no writes, no memos).
- Response shape includes the FULL close plan: which Os would close, in what order, with what estimated aggregates, what cascade actions would apply.
- Useful for the "today > period.end, but user wants to review before batch-close" path. CEO can bubble the dry-run plan via `AskUserQuestion` before invoking non-dry.

## Response shape

```
## Receipt <REQUEST_ID>
OPERATION: okr-close-period
STATUS: ok | partial | error | dry_run
PERIOD: <period>
CASCADE_RULE: <value>
CLOSED_COUNT: <int>
CLOSED_O_IDS: [<list>]
CASCADE_DEFER_COUNT: <int>
CASCADE_ARCHIVE_COUNT: <int>
CASCADE_O_IDS: [<list>]
MEMO_COUNT: <int>
AGGREGATES_BY_LEVEL:
  individual: {mean: <f>, min: <f>, max: <f>, count: <n>}
  department: {...}
  company:    {...}
LEDGER_REF: jsonl://state/ceo-ledger.jsonl#seq=<n>
```

`partial` = some closes failed (e.g., file permission); close what's closeable and report which were skipped.

## Invariants

- **Leaf-first.** Individual Os close before dept Os close before company Os. Guarantees scoring order.
- **Preserve certificates.** Each close is a whole-file rewrite via `okr-close` which preserves the original emit-time certificate marker at the bottom of the file.
- **Atomic per-OKR.** If any single close fails, the period-level invocation returns `partial` with the failed O's error — does NOT roll back successful closes (those are already ledger-written). User / OKR-master decides the follow-up.
- **No self-close of the master.** OKR-master closes others' Os; it doesn't own any OKR itself (by role definition in `agents/kiho-okr-master.md`).
- **Cascade is config-gated.** If `[okr] cascade_rule` is `none` or unrecognized, default to `deferred` and log `action: cascade_rule_fallback, requested: <value>, applied: deferred`.

## Non-Goals

- **Not a period-rollover.** Closing 2026-Q2 does NOT open 2026-Q3 Os. The scanner's `propose-company` action at the next /kiho turn handles the new period.
- **Not an aggregate-rollup-to-parent engine.** Each O's aggregate is still computed only from its own KRs. Parent Os incorporating children's final scores is v6.3+ enhancement.
- **Not a retractor.** Closed Os stay closed. A mistaken close is corrected via the next period's new O + retrospective narrative, never by reopening.

## Anti-patterns

- Batch-closing without leaf-first ordering. If a company O closes before its dept children, and the cascade rule kicks in as `archive`, you've lost data about child performance.
- Skipping memo-send fanout. The memo IS the notification mechanism; silent closes surprise owners at the next retrospective.
- Using cascade `archive` as default. `deferred` is the safer choice — preserves option value for the next period. Only use `archive` when the parent is an incident-remediation O that clearly terminates with the parent.

## Grounding

- `skills/core/okr/okr-close/SKILL.md` — the atomic primitive this skill loops over.
- `bin/okr_scanner.py` — source of the `period-close` and `cascade-close` trigger actions.
- `agents/kiho-okr-master.md` — the invoker; also a committee member on any Os being closed (though that committee ran at emit time, not close time).
- `references/cycle-templates/okr-period.toml` phase `close` — cycle-runner invocation path.
- `skills/core/communication/memo-send/SKILL.md` — memo dispatch.
- `references/okr-guide.md` — user-facing narrative of the period-end flow.
- `_proposals/v6.2-okr-auto-flow/` (authored at v6.2.0 release) — the full architecture lineage.
