---
name: experience-pool
description: Unified experience retrieval and registration across skills, reflections, and failure cases, operating as a VIEW over per-agent memory rather than a separate store. Supports add_skill, add_reflection, add_failure_case, search, update_performance, and promote (project→company) operations. Use when any agent needs to find similar prior work before starting a task, when skill-learn needs to register a new draft, or when memory-reflect wants to record a high-signal reflection that others might benefit from. Triggers on "check experience pool", "search past skills", "find similar failures", "retrieve reflections", "promote experience".
metadata:
  trust-tier: T2
  kiho:
    capability: read
    topic_tags: [learning, retrieval]
    data_classes: ["cross-project-lessons", "lessons"]
---
# experience-pool

The shared experience layer — a thin index over per-agent memory that lets any agent discover what others have already tried, learned, or failed at. Source of truth stays per-agent; the pool is a lookup table.

> **v5.20 migration note.** For cross-namespace lookups (memory + KB + cross-agent-learnings + ceo-ledger + committee transcripts in one call), callers SHOULD use the unified read path `memory-query` (sk-058) rather than composing multiple experience-pool + kb-search + memory-read invocations. The experience-pool retains its narrow role as the per-agent memory index; `memory-query` dispatches to it for experience-shaped queries. This removes the denormalized-cache-pretending-to-be-a-view pattern called out in the ReAct doctrine.

## Contents
- [Operations](#operations)
- [Storage layout](#storage-layout)
- [Index schema](#index-schema)
- [Search operation](#search-operation)
- [Performance metrics](#performance-metrics)
- [Promotion procedure](#promotion-procedure)
- [Archive policy](#archive-policy)
- [Response shape](#response-shape)
- [Anti-patterns](#anti-patterns)

## Operations

| op | Purpose |
|---|---|
| `add_skill` | Register a new skill (DRAFT or ACTIVE) in the pool index |
| `add_reflection` | Add a memory-reflect output to the pool for peer visibility |
| `add_failure_case` | Record a failed attempt with root cause and corrective action |
| `search` | Tag-first + keyword fallback lookup across the pool |
| `update_performance` | Bump success/tokens/rating/use_count for an existing entry |
| `promote` | Move a project-tier entry up to company-tier via kb-promote sanitization |
| `render-company-pool` | Synthesize `$COMPANY_ROOT/company/wiki/experience-pool.md` from promoted lessons (v5.19.5+) |

## Storage layout

The pool is a **VIEW**, not a store. The source of truth remains in per-agent memory (`.kiho/agents/<id>/memory/*.md`) and per-skill directories (`skills/<domain>/<skill>/`).

- **Project-tier index:** `.kiho/state/experience-pool/index.jsonl`
- **Company-tier index:** `$COMPANY_ROOT/experience-pool/index.jsonl`
- **Archive root:** `.kiho/state/experience-pool/archive/<YYYY-MM>.jsonl` (and same under company root)

Every index entry is a pointer (`source_path` + `ref_id`) plus denormalized metadata for search. Reading an entry fetches the pointed-to source file lazily.

## Index schema

```json
{
  "entry_id": "ep-2026-04-14-0007",
  "type": "skill | reflection | failure_case",
  "owner_agent": "eng-lead-01",
  "source_path": "skills/_meta/skill-learn/SKILL.md",
  "ref_id": "sk-learn",
  "tags": ["meta", "learning", "dedup"],
  "summary": "Merged skill-capture and skill-extract into a unified learning skill.",
  "created_at": "2026-04-14T08:30:00Z",
  "performance": {
    "success_rate": 0.0,
    "avg_tokens": 0,
    "user_rating": null,
    "use_count": 0
  },
  "status": "active | draft | archived"
}
```

## Search operation

1. **Tag-first pass.** Intersect the query tags with each entry's tags. Rank by overlap count, then by `performance.success_rate`, then by `use_count`.
2. **Keyword fallback.** If tag pass yields < 3 results, run a case-insensitive substring match over `summary`. Merge results, deduping by `entry_id`.
3. **Filter by tier.** Project-tier search defaults to project index; pass `include_company: true` to union with company index.
4. **Dedup on creation.** Before appending a new entry, the skill checks for an existing entry matching `(type, ref_id)`. Exact match → skip. Same tags + > 0.85 summary cosine similarity → return `status: duplicate`.

## Performance metrics

`update_performance` is the only op that mutates existing entries. Input:

```
entry_id: <entry>
delta_success: +1 | 0 | -1   # pass/neutral/fail
tokens_used: <int>
user_rating: <null | 1-5>
```

Procedure:
1. Fetch entry, update `use_count += 1`.
2. Recompute `success_rate` as running average.
3. Recompute `avg_tokens` as running average of `tokens_used`.
4. If `user_rating` provided, overwrite prior rating.
5. Append an audit line to `.kiho/state/experience-pool/performance-log.jsonl` for traceability.

## Promotion procedure

The `promote` op moves a high-value project entry into the company index:

1. Verify eligibility: `use_count >= 5`, `success_rate >= 0.80`, entry is not a failure case.
2. Call `kb-promote` to sanitize the underlying source (strip project-specific paths, variable names).
3. Write a new entry to the company index with `source_path` rewritten to the sanitized location.
4. Mark the project entry as `status: promoted` (retained for local reference) and add `promoted_to: <company_entry_id>`.

## Render-company-pool procedure (v5.19.5+)

The `render-company-pool` op emits the synthesized markdown index that closes
the `experience-pool-cross-project` data-class row in `references/data-storage-matrix.md`
§10. It reads sanitized lessons (the kb-promote output at
`$COMPANY_ROOT/company/wiki/cross-project-lessons/*.md`), deduplicates, and writes
one aggregated view to `$COMPANY_ROOT/company/wiki/experience-pool.md`.

Procedure:

1. **Invoke the helper.** Run `python ${CLAUDE_PLUGIN_ROOT}/bin/experience_pool_render.py --company-root $COMPANY_ROOT`. The helper is deterministic, stdlib-only, and carries the dedup + render logic. Use `--dry-run` to preview; omit it to write the output file.
2. **Interpret the helper report.** On success the helper prints one JSON line: `{status: ok, out, chars, topics, lessons_scanned, lessons_after_dedup, dedup_dropped}`. On `status: no_lessons` the `cross-project-lessons/` directory is missing or empty — nothing to render, no-op.
3. **Submit via kb-manager.** After the helper writes the file, call `kb-manager op=update path=experience-pool.md tier=company`. kb-manager runs the standard drafts/ atomicity pipeline + lint + log append. Do NOT edit `experience-pool.md` by hand; the helper is the sole writer, and re-running it will stomp hand-edits.
4. **Rebuild affected indexes.** kb-manager's post-write protocol rebuilds `index.md`, `backlinks.md`, `tags.md`, `cross-project.md`, etc. automatically. The new `experience-pool.md` is cross-project-scoped so it will land under `cross-project.md`; `kb_lint_cross_project.py` parity checker verifies this post-rebuild.

Determinism and dedup:

- Dedup uses char-3-gram Jaccard similarity (threshold 0.85, matching `kb-promote` sanitization). Two lessons with the same summary but different wordings will be deduped; two on genuinely different points stay separate.
- Sort order within a topic: confidence desc, then updated_at desc, then slug asc.
- Output is idempotent: re-running over unchanged inputs produces byte-identical output modulo the `generated_at:` frontmatter timestamp.

## Archive policy

- Entries with `created_at` older than 90 days AND `use_count == 0` → move to `archive/<YYYY-MM>.jsonl`.
- Entries of type `failure_case` are never auto-archived (they remain as warnings regardless of age).
- Archived entries are excluded from default search but returned when the caller passes `include_archived: true`.

## Response shape

```json
{
  "status": "ok | duplicate | error",
  "op": "search",
  "entry_id": "ep-2026-04-14-0007",
  "results": [
    {"entry_id": "ep-...", "ref_id": "sk-learn", "score": 0.88, "source_path": "skills/_meta/skill-learn/SKILL.md"}
  ],
  "result_count": 3,
  "tier": "project",
  "promotion": {"promoted_to": null}
}
```

## Anti-patterns

- **Copying content into the index.** The index is metadata only. Ballooning entries into full skill bodies turns the pool into a slow second store.
- **Unbounded growth.** Enforce the 90-day archive rule; an unbounded index kills search latency.
- **Cold keyword search.** Always run the tag pass first. Jumping straight to substring matching is slow and imprecise.
- **Silent metric updates.** Every `update_performance` must append an audit line. No invisible mutations.
- **Skipping dedup on creation.** Duplicate entries fragment the signal and waste ranking budget.
- **Cross-tier leakage.** Never write a company entry from project scope without going through `promote` (which gates on `kb-promote` sanitization).
