---
name: unified-search
description: Single entry-point retrieval across project KB, company KB, skill library, and external plugin skills. Used by CEO INITIALIZE step 7 (KB seed check — richer than kb-search alone), design-agent Phase 2 (skill resolution + external reference), recruit Phase 2 (author vs reference decision), and kb-manager on demand. Inputs `{query, scope, filter?, limit?}` where `scope ∈ [project|company|skills|external|all]`. Output is ranked hits with `{source, snippet, link, score, meta}`. Ranking blends embedding similarity (if available) with performance (reuse_count × skill-performance × freshness) × scope_bonus; falls back to pure TF-IDF when embeddings are unavailable. Wraps `bin/embedding_util.py` and consumes `external-skills-catalog.json` from skill-discover. Respects `settings.external_skills.allow_references` (false → skip external scope).
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: draft
  kiho:
    capability: read
    topic_tags: [discovery, retrieval]
    data_classes: ["kb-wiki-articles", "skill-definitions"]
    storage_fit:
      reads: ["<project>/.kiho/kb/wiki/**", "$COMPANY_ROOT/company/wiki/**", "$COMPANY_ROOT/skills/**", "$COMPANY_ROOT/external-skills-catalog.json", "$COMPANY_ROOT/settings.md", "$COMPANY_ROOT/company/skill-performance.jsonl"]
      writes: []
---
# unified-search

One search primitive that every kiho role can call. Retrieves from four corpora in parallel and returns a single ranked list. Replaces ad-hoc `Grep` / `kb-search` / `skill-find` invocations where callers previously had to merge results themselves.

## When to use

Invoke from:

- CEO INITIALIZE step 7 (KB seed check) — `scope: all`, small `limit`
- design-agent Phase 2 skill resolution — `scope: [skills, external]`
- recruit Phase 2 author vs reference decision — `scope: [skills, external]`
- kb-manager on ad-hoc lookups — `scope: [project, company]`
- any skill needing cross-corpus retrieval instead of raw `Grep`

Do NOT invoke:

- For a known exact path read — `Read` is cheaper
- When only project KB is needed AND a fresh `kb-search` already happened this turn — cache re-use via the CEO's session context suffices

## BCP 14

MUST / MUST NOT / SHOULD — per RFC 2119 + RFC 8174.

## Inputs

```
query: <string>                       # free-text search query
scope: <list>                         # ∈ [project, company, skills, external, all]
filter: <optional dict>               # {tags: [...], capability: <verb>, min_confidence: <float>}
limit: <int>                          # default 10; max 50
min_score: <float>                    # default 0.20 — floor on result inclusion
embedding_backend: <auto|sbert|tfidf> # default auto — follows bin/embedding_util.py tier
```

`scope: all` expands to `[project, company, skills, external]` with equal weight before `scope_bonus` re-weighting.

## Output

```json
{
  "status": "ok | partial | error",
  "backend": "sentence-transformers | sklearn-tfidf | stdlib-tfidf",
  "query": "<echo>",
  "hits": [
    {
      "source": "project | company | skills | external",
      "snippet": "<first 240 chars of matching context>",
      "link": "<abs path or skill_id>",
      "score": 0.87,
      "meta": {
        "title": "...",
        "tags": [...],
        "confidence": 0.92,
        "invocations": 12,
        "last_invoked": "..."
      }
    }
  ],
  "scope_tallies": {"project": 4, "company": 2, "skills": 1, "external": 0},
  "next_refresh_hint": "run skill-discover to refresh external cache"
}
```

## Procedure

### Phase 1 — Resolve scope

1. Read `settings.external_skills.allow_references`. If `false` AND `scope` includes `external` → drop `external`, log a filter event.
2. If `scope = all`, expand to the four primary scopes.
3. Cap `limit` at 50.

### Phase 2 — Gather corpora

For each active scope, collect candidate documents:

| Scope | Corpus |
|---|---|
| `project` | `<project>/.kiho/kb/wiki/**/*.md` + `<project>/.kiho/kb/knowledge-base.md` |
| `company` | `$COMPANY_ROOT/company/wiki/**/*.md` + `$COMPANY_ROOT/company/knowledge-base.md` |
| `skills` | `$COMPANY_ROOT/skills/*/SKILL.md` — skill frontmatter + body |
| `external` | Each row of `$COMPANY_ROOT/external-skills-catalog.json` as a document (description + name) |

### Phase 3 — Score each candidate

For each document `d`:

1. **Semantic similarity** via `bin/embedding_util.py::text_similarity(query, d.text)` — returns `[0, 1]`
2. **Performance bonus** (skills scope only): consult `$COMPANY_ROOT/company/skill-performance.jsonl` — multiplier
   ```
   perf_multiplier = 1 + 0.5 × success_rate × freshness
   ```
   where `freshness = max(0, 1 - days_since_last_invoked / 90)`.
3. **Reuse bonus** (project/company scopes): consult `<project>/.kiho/state/reuse-ledger.jsonl` for the file's cumulative reuse count:
   ```
   reuse_multiplier = 1 + min(0.3, reuse_count × 0.05)
   ```
4. **Scope bonus** — small additive weight so same-scope hits cluster when query intent is scope-specific:
   ```
   scope_bonus = {project: 0.05, company: 0.03, skills: 0.05, external: 0.02}[scope]
   ```
5. **Final score**:
   ```
   final = sim × perf_multiplier × reuse_multiplier + scope_bonus
   ```

### Phase 4 — Filter + rank

1. Drop any hit below `min_score`.
2. Apply `filter` if provided:
   - `tags` — intersect with document frontmatter tags
   - `capability` — only matches for skills scope
   - `min_confidence` — drop project/company hits below threshold
3. Sort by `final` desc; slice to `limit`.

### Phase 5 — Build snippets

For each retained hit:

1. Locate the window around the best-matching sentence (naive: 240 chars surrounding the highest-IDF query-term occurrence).
2. Normalize whitespace.
3. Attach `source`, `link`, `score`, `meta`.

## Fallback chain

1. `sentence-transformers` available → use it for similarity
2. `sklearn` + `numpy` → TF-IDF + cosine
3. Neither → pure-Python TF-IDF via `bin/embedding_util.py`
4. All fail → return `{status: "error", hits: []}` with `error: "no search backend available"`

Fallback is automatic; the caller sees the same shape regardless.

## Anti-patterns

- MUST NOT write to any of the scanned corpora. `unified-search` is strictly READ-only; all writes flow through `kb-manager` / `skill-improve`.
- MUST NOT fetch external URLs. The `external` scope consumes the CACHED catalog only; refreshing it is `skill-discover`'s job.
- MUST NOT exceed `limit: 50`. Above that callers should paginate or narrow the query.
- Do NOT return raw full-text of results — always snippets. Full content is one `Read` call away from the caller.

## Grounding

v6 plan §3.11 — "Single entry point for CEO/design-agent/recruit/kb-manager searches across project KB, company KB, skill library, external plugins. Ranking: embedding × settings-weighted blend × scope_bonus. Fallback: pure TF-IDF."
