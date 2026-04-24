---
name: consolidate-company-kb
description: Company-scope KB consolidation. Scans `$COMPANY_ROOT/company/wiki/**` for clusters (semantic via `bin/embedding_util.py`, TF-IDF fallback), proposes synthesis pages, AND dedupes entries whose pair-wise text similarity is ≥ 0.80 via `kb-manager op=kb-update` (merge into the higher-confidence canonical). Invoked by CEO DONE step 10b when `days_since_last_company_kb_consolidation >= settings.kb_consolidation.company_kb_cadence_days` (default 30) OR `turns_since_last >= settings.kb_consolidation.company_kb_cadence_turns` (default 20). READ-only by itself — dedup merges + synthesis writes flow through kb-manager so KB_MANAGER_CERTIFICATE hook stays honored. Respects `settings.promote.dry_run_before_write`.
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: draft
  kiho:
    capability: read
    topic_tags: [curation, lifecycle, scope-boundary]
    data_classes: ["kb-wiki-articles", "cross-project-lessons"]
    storage_fit:
      reads: ["$COMPANY_ROOT/company/wiki/**", "$COMPANY_ROOT/settings.md"]
      writes: []
---
# consolidate-company-kb

Periodic company-KB consolidation. Two jobs:

1. **Synthesis clustering** — same as `consolidate-project-kb` but at
   company scope, drafting `synthesis/<topic>.md` from 2+ related entries.
2. **Duplicate merging** — pair-wise similarity ≥ 0.80 across all company
   wiki entries triggers a `kb-update` merge proposal (keep the
   higher-confidence or earlier page as canonical; deprecate the loser with
   `superseded_by:`).

All writes route through `kb-manager` (the KB_MANAGER_CERTIFICATE hook gate
enforces that).

## When to use

Invoke from:

- CEO DONE step 10b cadence gate (days OR cross-project turns)
- Ad-hoc request: "deduplicate company kb"

Do NOT invoke:

- On an empty company wiki
- Mid-LOOP; consolidation runs at DONE

## BCP 14

MUST / MUST NOT / SHOULD — per RFC 2119 + RFC 8174.

## Inputs

```
company_root: <path>
synthesis_threshold: <float 0.60..0.85>      # default 0.70 (cluster seed)
dedupe_threshold: <float 0.75..0.95>         # default 0.80 (merge trigger)
min_cluster_size: <int>                       # default 2
max_synthesis_proposals: <int>                # default 5
max_dedupe_proposals: <int>                   # default 10
dry_run: <bool>                               # default true
```

## Procedure

### Phase 1 — Gather candidates

1. Enumerate files under `$COMPANY_ROOT/company/wiki/` recursively,
   including `entities/`, `concepts/`, `principles/`, `rubrics/`,
   `synthesis/`.
2. Skip `lifecycle: deprecated` pages.

### Phase 2 — Synthesis clustering

Same as `consolidate-project-kb` Phase 2 + 3 but at company scope.
Produces `synthesis_proposals`.

### Phase 3 — Pair-wise dedupe scan

Using `bin/embedding_util.py`:

1. For each ordered pair `(A, B)` where `A.path < B.path` lexicographically
   (avoids double counting), compute `text_similarity(A.body, B.body)`.
2. If `sim >= dedupe_threshold`:
   - Pick the canonical: higher `confidence` frontmatter wins; tie →
     earlier `created_at` wins; tie → longer body wins.
   - The loser becomes `superseded_by: <canonical_path>`.
   - Emit a `dedupe_proposal` with fields: `canonical_path`, `loser_path`,
     `sim_score`, `rationale`, `merged_tags`.

### Phase 4 — Route through kb-manager

For each proposal (synthesis OR dedupe):

- **dry_run == true**: return in response; caller surfaces via
  `AskUserQuestion` with Approve / Skip / Edit options.
- **dry_run == false**: invoke kb-manager directly:
  - synthesis → `op=kb-add` with `page_type=synthesis`
  - dedupe → `op=kb-update` on the loser with `lifecycle=deprecated` and
    `superseded_by=<canonical_path>`, plus `op=kb-update` on canonical to
    merge tag unions.

### Phase 5 — Update consolidation ledger

Append rows to `$COMPANY_ROOT/company/consolidation-ledger.jsonl` (create
if missing):

```json
{"ts": "<iso>", "action": "company_kb_synth_proposed|company_kb_dedupe_proposed|applied|skipped",
 "members": [...], "sim_score": <float|null>, "decision_by": "<user|auto>"}
```

## Response shape

```json
{
  "status": "ok | error",
  "backend": "sentence-transformers | sklearn-tfidf | stdlib-tfidf",
  "synthesis_proposals": [...],
  "dedupe_proposals": [
    {
      "canonical_path": "...",
      "loser_path": "...",
      "sim_score": 0.87,
      "rationale": "canonical has higher confidence (0.92 vs 0.78)"
    }
  ],
  "applied": <int>,
  "review_required": <int>,
  "next_cadence_ts": "<iso>"
}
```

## Anti-patterns

- MUST NOT auto-deprecate a page without surfacing to user when
  `dry_run_before_write == true`. Company-scope retirements are
  user-visible.
- MUST NOT merge pages where the winner has lower confidence — confidence
  is the tie-breaker, not a tie-maker.
- MUST NOT include `synthesis/` outputs in the dedupe scan during the same
  invocation; they need a second turn to settle.
- Do NOT re-cluster within the same call. One pass per invocation.

## Grounding

v6 plan §3.8 — "Company KB consolidation: same clustering as project; plus
dedupe pair-wise ≥ 0.80 via kb-manager kb-update."
