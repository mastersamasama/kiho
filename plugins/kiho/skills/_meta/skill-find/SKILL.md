---
name: skill-find
description: Runtime skill discovery that searches available skills across all tiers using faceted retrieval. Parses the query into capability verb + domain + topic tag facets, walks the CATALOG.md routing block to produce a pre-filtered candidate set (hard ceiling 10), then applies lexical scoring inside the filtered set. Falls back to flat lexical scoring when no facets are inferrable. Use when an agent needs to find the right skill for a task, when the CEO routes a request to a skill, or when any agent says "find a skill for", "is there a skill that", "which skill handles". Also used by the skill engine to check for duplicates before creating new skills.
metadata:
  trust-tier: T3
  kiho:
    capability: read
    topic_tags: [discovery]
    data_classes: ["skill-catalog-index", "skill-definitions"]
---
# skill-find

Discovers and ranks skills by relevance to a query via v5.16 **faceted retrieval**: capability verb + domain + topic tag facets prune the candidate set before lexical scoring runs. At scale (>100 skills), this two-stage retrieval is the only mechanism that keeps the agent's attention budget bounded — flat lexical scoring over the whole catalog degrades past |S|=30 per arXiv 2601.04748 §5.2.

## Contents
- [Inputs](#inputs)
- [Facet walk procedure (v5.16 primary path)](#facet-walk-procedure-v516-primary-path)
- [Lexical fallback (when facets are unresolvable)](#lexical-fallback-when-facets-are-unresolvable)
- [Response shape](#response-shape)
- [Anti-patterns](#anti-patterns)

## Inputs

```
query: <natural language description of what the skill should do>
tiers: [plugin, project, company]  (default: all three)
lifecycle_filter: draft | active | deprecated | all  (default: active)
limit: <max results, default 3>
hard_ceiling: <max candidate-set size before lexical scoring, default 10>
```

## Facet walk procedure (v5.16 primary path)

The canonical implementation is `scripts/facet_walk.py`. Invoke it via `Bash`:

```bash
python skills/_meta/skill-find/scripts/facet_walk.py \
    --query "<natural-language query>" \
    --limit 3
```

The script performs a deterministic 5-step walk:

1. **Tokenize the query** and remove stop words (same STOP_WORDS set as `catalog_fit.py`).
2. **Infer the capability facet** by matching query verbs against the closed verb set in `kiho-plugin/references/capability-taxonomy.md`. First match wins. Maps ~50 synonyms (`create/draft/generate/author`, `find/search/lookup`, `update/improve/fix/patch`, etc.) to the 8 canonical verbs.
3. **Infer the domain facet** by keyword overlap with each domain's `routing-description` in `skills/CATALOG.md`'s routing block. Winner **MUST** beat runner-up by ≥2× to resolve; ambiguous queries leave the domain facet unset.
4. **Infer the topic-tag facet(s)** by checking if any query token matches an entry in `kiho-plugin/references/topic-vocabulary.md`. Exact token match only (no stemming).
5. **Walk the candidate set**: start with all ACTIVE skills; intersect by each resolved facet; stop when the set size ≤ `hard_ceiling` (default 10).

If the candidate set after filtering is ≤10, apply lexical scoring within the set and return the top `limit`. If it's >10 and `--gate-mode` is set, emit `status: underspecified` with `narrowing_hints` pointing at the missing facets and exit 1. In interactive mode (no `--gate-mode`), return the top lexical-scored results anyway with a `candidate_count: <n>` warning.

## Lexical fallback (when facets are unresolvable)

When the query has no matchable capability verb, no domain keyword overlap, and no topic tag, the facet walker falls back to the v5.12 lexical scoring procedure:

```
query_words = tokenize(lowercase(query))
desc_words = tokenize(lowercase(description))
name_words = tokenize(lowercase(name))

word_overlap = |query_words ∩ (desc_words ∪ name_words)| / |query_words|
desc_length_bonus = min(len(description) / 500, 0.1)
score = word_overlap + desc_length_bonus
```

Lexical fallback runs over the full catalog, which is the pre-v5.16 behavior. Post-v5.16, this is expected to be rare by design — most queries should land at least one facet.

### Tiebreaking

When two skills have the same score:
1. Prefer `active` over `draft`
2. Prefer plugin-tier over project-tier over company-tier
3. Prefer higher `use_count` (if tracked in frontmatter)

## Response shape

```markdown
## Skill search results

**Query:** "handle PDF extraction"
**Results:** 3 skills found

| Rank | Score | Tier | Domain | ID | Name | Lifecycle | Description (truncated) |
|---|---|---|---|---|---|---|---|
| 1 | 0.85 | plugin | engineering | sk-015 | processing-pdfs | active | Extracts text and tables from PDF files... |
| 2 | 0.42 | project | core | — | doc-parser | active | Parses document formats including PDF, DOCX... |
| 3 | 0.30 | plugin | kb | sk-008 | kb-ingest-raw | active | Ingests raw files into the KB raw/ directory... |
```

When no skills match (all scores < 0.1), return:
```markdown
## Skill search results

**Query:** "handle PDF extraction"
**Results:** 0 skills found

No matching skills. Consider using `skills/skill-capture/` to create one from a successful session, or `skills/skill-derive/` to specialize an existing skill.
```

## Anti-patterns

- Never return deprecated skills unless explicitly requested via `lifecycle_filter: deprecated`.
- Never read the full SKILL.md body during search. Frontmatter only — the body loads on invocation, not discovery.
- Never modify any skill during a find operation. This is read-only.
- Never score by body content. Discovery operates purely on name + description (the metadata tier of progressive disclosure).
