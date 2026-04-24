---
name: okr-checkin
description: Update Key Result progress on an existing active Objective during the period. Reads the OKR file, updates one or more KRs with new scores (0.0-1.0), appends a history entry per KR with timestamp + note + updater, rewrites the full file preserving the certificate marker intact. Refuses to modify a closed Objective. Refuses to change weights, KR identities, aligns_to, or the certificate — those are emit-time decisions. Invocation is always explicit — there is no automatic cadence. Use when an agent wants to update their individual OKR progress, when a dept-lead is rolling up department OKR status mid-period, or when the user asks "how are we doing on the 2026-Q2 ship Objective".
argument-hint: "o_id=<id> kr_updates=[{kr_id, progress_score, note}]"
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: active
  kiho:
    capability: update
    topic_tags: [governance, planning]
    data_classes: ["okrs-period-md"]
    storage_fit:
      reads:
        - "<project>/.kiho/state/okrs/<period>/O-*.md"
      writes:
        - "<project>/.kiho/state/okrs/<period>/O-*.md"
---
# okr-checkin

Per-KR progress update on an active Objective. The skill is intentionally narrow: it mutates scores + appends history and nothing else. Identity, weights, alignment, and the approval certificate are all immutable after emit.

## When to use

- An agent wants to update their individual OKR progress after shipping a cycle.
- A dept-lead is rolling up mid-period department OKR status before a committee.
- The user asks "how are we tracking on Q2 Objective X" — the CEO may invoke this if the scores are stale enough that a fresh data point belongs in the history.

Do **not** invoke:

- To mark an Objective closed — use `okr-close`.
- To change a KR's description, target, or weight — those are emit-time decisions. If the KR as written has become unmeasurable, close the O and set a new one.
- To change `aligns_to` — same reason.
- To auto-update on every /kiho turn — that's cadence noise. Check in when the underlying reality changed.

## Inputs

```
PAYLOAD:
  o_id:               <O id>                             # required
  kr_updates:         list                               # required; 1-5 entries
    - kr_id:          <stable slug>                      # required, must exist in target O
      progress_score: <float in [0.0, 1.0]>              # required
      note:           <one-sentence evidence/context>    # required; "no change" allowed for no-op checkin
      stretch_cap:    <bool>                             # optional; default derived from KR frontmatter
  updater:            <agent-id or "user">               # required
  ts:                 <iso>                              # optional; defaults to now()
```

## Procedure

### 1. Load + validate

- Read `<project>/.kiho/state/okrs/<period>/<o_id>.md`. Resolve period by scanning all period dirs — O ids are unique across periods.
- Refuse if file missing → `status: o_not_found`.
- Refuse if frontmatter `status != active` → `status: o_already_closed` (closed Os are frozen).
- Refuse if any `kr_updates[].kr_id` is not a declared KR on this O → `status: unknown_kr`.
- Validate all `progress_score` values in `[0.0, 1.0]` (inclusive).

### 2. Apply updates

For each `kr_updates[i]`:

- Locate the `### <kr_id>` block.
- Update `current_score: <new score>`.
- Append a history entry:
  ```
  - ts: <ts>
    score: <new>
    by: <updater>
    note: "<note>"
  ```

### 3. Rewrite the file

Whole-file Write. The certificate marker lives in an HTML comment at the bottom of the file (emitted by `okr-set`) — preserve it verbatim. The PreToolUse hook checks the marker at every Write, including this one.

**Why whole-file rewrite, not Edit?** Markdown under the `## Key Results / ### kr_id` tree has variable formatting. Edit's string-match rule becomes fragile across repeated checkins; full Write is simpler and deterministic. The file is ≤ 200 lines in every realistic case.

### 4. Ledger entry

```
{"ts": "<iso>", "action": "okr_checkin",
 "payload": {"o_id": "<id>", "kr_updates": [{"kr_id": "...", "score": <f>}, ...],
             "updater": "<id>"}}
```

### 5. Optional values-flag if regression detected

If any `progress_score` DROPPED by > 0.20 vs the last history entry, emit a `values-flag` with topic `okr-regression`:

```
values-flag severity=info topic=okr-regression
  subject: "KR <kr_id> on <o_id> dropped from <prev> to <new>"
  body: "Updater: <updater>. Note: <note>. Review whether the target or plan needs adjustment."
```

This is **information-producing**, not blocking — the retrospective or next dept-lead committee picks it up. Regression is data; it's not an error.

## Response shape

```
## Receipt <REQUEST_ID>
OPERATION: okr-checkin
STATUS: ok | o_not_found | o_already_closed | unknown_kr | invalid_score
O_ID: <id>
KR_UPDATES_APPLIED: <int>
REGRESSION_FLAGS: <int>
LEDGER_REF: jsonl://state/ceo-ledger.jsonl#seq=<n>
NOTES: <optional>
```

## Invariants

- **Append-only history.** Prior entries in a KR's history are never rewritten. A mistaken checkin is corrected by a follow-up checkin with a clarifying note, never by retracting the bad entry.
- **Certificate preserved.** The original emit-time certificate marker stays at the bottom of the file. Never rewrite or strip it.
- **Immutable identity.** `o_id`, `okr_level`, `period`, `owner`, `aligns_to`, `status: active`, and every KR `id / weight / target / direction / stretch` are invariant through checkins.
- **Score bounds.** `0.0 ≤ progress_score ≤ 1.0`. Stretch KRs allow emit-time aspiration; the `stretch_cap` for aggregation is enforced at `okr-close`, not here.
- **No cadence.** Invocation is explicit. A quarter without checkins is a data point in itself (the dept-lead committee will notice at period close).

## Non-Goals

- **Not a redefinition tool.** Changing what a KR measures = close the O and set a new one.
- **Not a notification surface.** Checkin doesn't memo anyone. The dashboard at `.kiho/state/dashboards/` picks up current scores on its next regen.
- **Not a cycle trigger.** A checkin does NOT open or close a cycle. Cycles and OKRs are separate surfaces that can reference each other (cycles via `aligns_to_okr` in cycle index.toml), not fused.

## Anti-patterns

- Daily / per-turn checkins. You're generating history noise. Check in when the underlying reality moved, typically when a cycle that contributes to the KR closed.
- Rounding optimistically. `progress_score: 0.8` on a KR where the target is 5× away from current is either a misread of the target or a sycophancy reflex. The numbers mean what they mean; discipline is the point.
- Using `note: "updating"` or `"progress"`. The note field is evidence, not a label. "Ref: cycle c-2026-04-20 closed, 3 of 5 hooks landed" is a real note.

## Grounding

- `skills/core/okr/okr-set/SKILL.md` — sibling skill that created the Objective this skill is updating.
- `skills/core/okr/okr-close/SKILL.md` — sibling skill that closes Objectives at period end.
- `references/okr-guide.md` — user-facing primer.
- `references/approval-chains.toml` — certificate preservation invariant.
- `skills/core/values/values-flag/SKILL.md` — the regression flag in step 5 lands here.

## Worked example

Agent `kiho-eng-lead` shipped cycle `c-2026-04-22` which touched approval-chains. Their individual OKR `O-2026Q2-individual-eng-lead-01` has KR `approval-chain-coverage` at weight 30. Last checkin was 0.40; new data says 3 of 5 scenarios shipped → 0.60.

```
/kiho okr-checkin o_id=O-2026Q2-individual-eng-lead-01 kr_updates=[
  {kr_id: approval-chain-coverage, progress_score: 0.60,
   note: "cycle c-2026-04-22 closed, 3 of 5 scenarios shipped"}]
  updater: kiho-eng-lead
```

Skill reads the file, updates current_score, appends history entry, rewrites file preserving the `DEPT_LEAD_OKR_CERTIFICATE:` at the bottom. Emits `okr_checkin` ledger row. No regression flag (score went up). The next dashboard regen shows the new 0.60.
