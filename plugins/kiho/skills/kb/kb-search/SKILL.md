---
name: kb-search
description: Use this skill when any agent needs to query the knowledge base and receive a synthesized, cited answer. Runs a multi-index retrieval cascade (index → tags → backlinks → candidate pages → synthesis) and returns a markdown answer with inline citations, a confidence score, and the list of pages consulted. Scopes are project, company, or both. Only kb-manager should load this skill — callers invoke it via the kb-manager agent.
argument-hint: "query=<text> scope=<project|company|both>"
metadata:
  trust-tier: T2
  kiho:
    capability: read
    topic_tags: [retrieval]
    data_classes: ["kb-wiki-articles"]
---
# kb-search

Multi-index synthesized search. The default path for any agent that needs a cited answer from the KB.

## Why synthesized, not raw?

A raw Read of `wiki/entities/auth-service.md` gives you one page. A kb-search call on `"how does auth work"` reads the right indexes, loads the 3-5 most relevant pages, synthesizes an answer that spans them, and cites each claim. The synthesis is what makes the KB useful under multi-agent workloads — every agent gets a coherent, current picture without re-deriving it.

## Inputs

```
PAYLOAD:
  query: <natural language or specific identifier>
  scope: project | company | both
  max_results: <int, default 10>
  include_stale: <bool, default false>
  require_confidence: <0..1, default 0.70>
  hint_types: [entity, concept, decision, ...] (optional — narrow the search)
  hint_tags: [<tag>] (optional — narrow by tag)
REQUEST_ID: <uuid>
```

## Retrieval cascade

Execute in order. Combine results.

### Stage 1 — Read the index

Read `index.md` for the target tier(s). Use `Grep` on the indexes:
- If query contains a known entity name → check `index.md` entities section
- If query contains a tag-like word → check `tags.md`
- If query is "who owns X" → check `by-owner.md`
- If query is "what are we uncertain about" → check `by-confidence.md` (bottom of ascending list)
- If query is "recent changes" → check `timeline.md`
- If query is "open questions" → check `open-questions.md`

For `scope: both`, read both tiers' index.md files. Merge candidate lists with tier annotation.

### Stage 2 — Shortlist candidates

From index hits, build a ranked shortlist of candidate pages. Ranking:
- Exact title match: +1.0
- Tag match on a top-3 tag: +0.7 per match
- Wikilink target match: +0.5
- Recent updated_at: +0.3 (scaled by recency)
- Matching hint_types: +0.2
- Stale (if not `include_stale`): -0.5

Keep top `max_results * 2` candidates.

### Stage 3 — Expand via backlinks

For the top-5 candidates, read `backlinks.md` to find pages that reference them. Add those as second-tier candidates (lower weight but still considered). This is the key to multi-hop retrieval without a graph database.

### Stage 4 — Load candidate pages

Read the top-`max_results` candidate pages in full. Note frontmatter fields (confidence, updated_at, valid_until, skill_solutions).

### Stage 5 — Synthesize an answer

Produce a markdown answer that:
- Directly answers the query in ≤ 3 paragraphs
- Cites each claim with `[[page-name]]` or `[^N]` footnotes pointing at loaded pages
- Notes any contradictions observed between loaded pages
- Notes any loaded page with `confidence < require_confidence` as "low-confidence source"
- Notes any loaded page with `valid_until != null` as "this page is deprecated"
- Lists the `skill_solutions` referenced by any loaded page (surfaces relevant skills for free)

### Stage 6 — Compute confidence

Answer confidence = weighted average of loaded page confidences, weighted by rank × relevance.

If answer confidence < `require_confidence`, do NOT fabricate — return `status: ok` but with `CONFIDENCE: <actual>` and a `stale_or_missing: true` flag so the caller knows to escalate to research cascade.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: search
STATUS: ok
SCOPE: <scope>
CONFIDENCE: <0..1>
ANSWER: |
  <synthesized markdown with inline citations>

  Example:
  The billing webhook uses idempotency keys per [[billing-webhook]]. The
  policy of exponential backoff with jitter is in [[retry-backoff-cap]] and
  was decided by committee [[ADR-0007-queue-backend]].

  For implementations, see these skills:
  - sk_idempotency_middleware_v2 (linked from [[idempotency-keys]])
  - sk_retry_jitter_v3 (linked from [[retry-backoff-cap]])

PAGES_CONSULTED:
  - wiki/entities/billing-webhook.md (confidence 0.92, updated 2026-04-09)
  - wiki/concepts/idempotency-keys.md (confidence 0.95, updated 2026-03-28)
  - wiki/concepts/retry-backoff-cap.md (confidence 0.88, updated 2026-04-02)
  - wiki/decisions/ADR-0007-queue-backend.md (confidence 0.94, updated 2026-02-11)
SKILL_SOLUTIONS_FOUND:
  - sk_idempotency_middleware_v2
  - sk_retry_jitter_v3
STALE_WARNING: null
CONTRADICTIONS_OBSERVED: []
```

**Empty / low confidence:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: search
STATUS: ok
CONFIDENCE: 0.35
ANSWER: |
  KB has no confident answer for this query. Closest match is
  [[rate-limit-policy]] which is loosely related but does not directly
  address <query>.
PAGES_CONSULTED:
  - wiki/concepts/rate-limit-policy.md (confidence 0.7, low-relevance)
STALE_OR_MISSING: true
SUGGESTION: run the research skill to gather external context
```

**Scope: both, with cross-tier results:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: search
STATUS: ok
ANSWER: |
  This project implements [[project:billing-webhook]] following the general
  pattern documented in [[company:idempotency-keys]]. The company-level
  convention is strict; this project follows it without local overrides.
PAGES_CONSULTED:
  - <project>/.kiho/kb/wiki/entities/billing-webhook.md
  - $COMPANY_ROOT/company/wiki/concepts/idempotency-keys.md
```

## Anti-patterns

- Do not skip the index stage. Jumping straight to page reads without the index makes the search O(N) on every page.
- Do not fabricate citations. Every cited claim must point at an actually-loaded page.
- Do not hide contradictions. If two loaded pages disagree, surface it explicitly.
- Do not return more than `max_results` pages in PAGES_CONSULTED. If you loaded more for internal reasoning, still cap the reported list.
- Do not synthesize on < 0.70 confidence material. Return with `stale_or_missing: true` and let the caller decide.
- Do not skip `skill-solutions.md`. Linked skills are one of the primary values kb-search provides to its caller.
