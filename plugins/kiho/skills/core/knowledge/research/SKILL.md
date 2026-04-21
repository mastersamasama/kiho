---
name: research
description: Use this skill whenever any kiho agent needs external information that is not guaranteed to be in the knowledge base. Enforces a strict five-step cascade — knowledge base, then web search (high-confidence sources only), then deepwiki MCP, then clone-as-reference for small GitHub repos, then escalate to user. Each step has a confidence threshold of 0.80 to short-circuit. Returns a structured cited answer or an escalation request. Also use when the CEO is classifying an unfamiliar request or when kb-manager needs authoritative sources to resolve a contradiction.
argument-hint: "query=<text> scope=<project|company|both>"
metadata:
  trust-tier: T2
  kiho:
    capability: read
    topic_tags: [research, retrieval]
    data_classes: ["research-cache", "kb-wiki-articles"]
---
# research

Enforces kiho's five-step research cascade. The only way agents are allowed to gather external context.

> **v5.21 cycle-aware.** This skill is invoked atomically (single-question lookups) AND as the `discovery` / `scope-research` phase entry in cycle templates (`talent-acquisition`, `kb-bootstrap`, `research-discovery`). When run from cycle-runner, the cycle's `index.toml` carries the search context; this skill's outputs (tools_landscape_ref, candidates) write back into the phase's declared `output_to_index_path`.

## Why a cascade

Costs ascend (KB is free, web is cheap, deepwiki is medium, cloning is slow, asking the user is expensive in user attention). Confidence descends after the first truly authoritative step. By always trying cheaper steps first and short-circuiting at 0.80 confidence, you spend the minimum necessary to answer a question.

## Inputs

```
PAYLOAD:
  query: <free-text question>
  scope: project | company | both (default: both)
  context: <why this matters — one sentence>
  max_steps: 1..5 (default 5)
  budget_min: <minutes, default 10>
  cache_to_kb: <bool, default true if final confidence >= 0.85>
```

## The cascade

Execute in strict order. Each step has a confidence threshold of **0.80** — stop when met, go to next when not.

### Step 1 — KB

Invoke `kiho-kb-manager` with op=`search`:

```
TIER: <scope-mapped>
OPERATION: search
PAYLOAD:
  query: <QUERY>
  max_results: 10
  require_confidence: 0.80
```

If kb-manager returns `CONFIDENCE >= 0.80` AND the answer directly addresses the query, **stop**. Return with `cascade_step_used: kb`.

If the return is below 0.80 but has relevant context, keep the partial answer and pages as "prior context" for the next step.

### Step 1.5 — Trusted source registry (v5.10)

Before hitting the open web, consult the **trusted-source registry** to see if the org already knows a good starting URL for this topic. The registry is an entity-typed subset of the KB under `entities/trusted-sources/`; see `references/trusted-source-registry.md` for the schema.

```
kiho-kb-manager op=search
PAYLOAD:
  query: <topic keywords from QUERY>
  page_type: entity
  entity_type: trusted-source
  filters:
    topic_tags_any: [<extracted from QUERY>]
    trust_level_in: [official, community]
  max_results: 5
  sort_by: [trust_level DESC, success_count DESC]
```

- **If one or more matches return with `trust_level: official` or `community`**: fetch each URL via `WebFetch` directly. Do not run `WebSearch` — the registry hit bypasses it. Apply the normal "2 independent high-confidence sources" rule to the fetched content. If the fetched content meets confidence >= 0.80, return with `cascade_step_used: trusted_source` and add the used source name(s) to the response's `trusted_sources_used` field.
- **If no match**: proceed to Step 2 (Web search) as normal.
- **Registry update on every run**: after Step 2 or later cascade steps find a high-confidence answer, call `kb-add` (or `kb-update` if the URL already has a registry entry) to record the winning URL in the trusted-source registry. Default `trust_level: unverified, added_by: research, use_count: 1, success_count: 1`. See `references/trusted-source-registry.md` §"Auto-population" for the full update protocol.

**Why Step 1.5 matters:** the first time you research "Playwright visual regression," you blind-search. The second time, Step 1.5 hits `playwright-dev` directly and skips the web-search shuffle. Over a project's lifetime this is a large time and token saving, and it concentrates confidence on sources the org has already validated.

### Step 2 — Web search

Call `WebSearch` with the query (or a refined version that includes the query's key terms).

**High-confidence source filter.** Accept results only from:
- Official documentation sites (claude.com/docs, github.com/<official-org>, nodejs.org, rust-lang.org, postgresql.org, etc.)
- Standards bodies (RFC, W3C, Unicode)
- Well-known engineering blogs (Fly.io, Stripe engineering, Anthropic engineering, etc.)
- Academic papers (arxiv.org, acm.org, ieee.org)
- GitHub READMEs of repos with > 1000 stars from respected orgs

**Rejected sources**: random blog posts, Medium articles without clear authorship, SEO-farmed content, forum posts (Reddit, Hacker News, Stack Overflow older than 2 years), AI-generated content.

Require at least **2 independent** high-confidence sources that agree. If you can only find 1, confidence caps at 0.70 and you continue to step 3.

Use `WebFetch` to pull specific pages for detail. Prefer authoritative URLs.

If confidence ≥ 0.80, **stop**. Return with `cascade_step_used: web`.

### Step 3 — Deepwiki MCP

If the query maps to a named GitHub repository (e.g., "how does Voyager's skill library work" → `MineDojo/Voyager`; "what is OpenSpace's skill engine" → `HKUDS/OpenSpace`), call deepwiki:

```
mcp__deepwiki__ask_question(
  repoName="<owner/repo>",
  question="<query>"
)
```

Or for structure browsing:

```
mcp__deepwiki__read_wiki_structure(repoName="<owner/repo>")
```

Deepwiki is authoritative for indexed repos. Confidence is typically 0.85+ when it returns a concrete answer.

If confidence ≥ 0.80, **stop**. Return with `cascade_step_used: deepwiki`.

### Step 4 — Clone-as-reference

Only if prior steps failed AND:
- The repo is clearly identified (not a guess)
- The repo is ≤ 50 MB (check with `git ls-remote` or a shallow fetch size estimate)
- The repo is clearly relevant (not a hail mary)

Procedure:

```bash
TMPDIR=$(mktemp -d)
git clone --depth 1 <repo-url> "$TMPDIR"
du -sh "$TMPDIR"  # verify < 50MB
# Use Glob/Grep/Read on $TMPDIR to find the answer
rm -rf "$TMPDIR"
```

**Hard rules:**
- Never clone > 50 MB. Check size before cloning.
- Never persist the clone beyond this research call.
- Never clone private repos.
- Never clone without `--depth 1`.

If confidence ≥ 0.80, **stop**. Return with `cascade_step_used: clone`.

### Step 5 — Escalate to user

If the cascade produced no confident answer, return `status: escalate_to_user` with:

```
- exact question the user needs to answer
- what the cascade already found (even if low confidence)
- why the cascade failed (missing sources, conflicting sources, out-of-date info)
- 2-3 candidate answers the user could pick from (if derivable)
```

The CEO receives this, may bundle with other pending questions, and calls `AskUserQuestion`.

## Trusted-source registry update protocol

Every cascade run that succeeds with confidence >= 0.80 MUST update the trusted-source registry. This is not optional — the registry is what makes Step 1.5 useful on the next run.

**On success:**

1. Determine the primary URL that produced the winning answer (the top-cited source in the response).
2. Query the registry: `kb-search` for an entity with `url_patterns` matching the primary URL's host + path prefix.
3. **If a match exists:**
   - Call `kb-update` to increment `use_count` and `success_count`.
   - Update `last_verified` to today.
   - If `success_count >= 3 AND failure_count == 0 AND trust_level == unverified`, auto-promote to `trust_level: community`.
4. **If no match exists:**
   - Call `kb-add` with `page_type: entity, entity_type: trusted-source, trust_level: unverified, added_by: research, source_type: <inferred from URL>`.
   - Derive `topic_tags` from the query keywords.
   - Set `use_count: 1, success_count: 1, last_verified: today`.
5. **Never auto-promote to `official`.** Official status is manual and CEO-only.

**On failure** (content stale, contradicted by newer high-confidence source, 404):

1. Query the registry for a match on the failed URL.
2. If match exists, call `kb-update` to increment `failure_count`.
3. If `failure_count >= 2` in the last 10 uses AND `trust_level: community`, auto-demote to `trust_level: demoted`.

See `references/trusted-source-registry.md` for the full schema, trust transitions, and security rules.

## Caching

- Every run writes its raw output to `<project>/.kiho/state/research/<iso>-<slug>.md`:
  ```markdown
  ---
  query: <verbatim>
  status: <ok|escalate_to_user>
  confidence: <0..1>
  cascade_step_used: <step>
  cached_at: <iso>
  ---
  # Research result
  <answer>

  ## Sources
  - [1] <url-or-kb-path>
  - [2] ...
  ```

- If `cache_to_kb: true` AND confidence ≥ 0.85 AND the finding is durable (not time-sensitive — no "as of Q2 2026" phrases), call `kiho-kb-manager` op=`add` to promote the finding into the KB. Future `kb-search` calls will hit the KB directly without re-running the cascade.

- Time-sensitive findings (vendor pricing, current software version, news) stay only in `.kiho/state/research/` and are not promoted.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: research
STATUS: ok | escalate_to_user | error
QUERY: <verbatim>
CONFIDENCE: <0..1>
CASCADE_STEP_USED: kb | trusted_source | web | deepwiki | clone | escalate
ANSWER: |
  <synthesized markdown with inline citations>
CITATIONS:
  - [1] <url-or-path>
  - [2] ...
TRUSTED_SOURCES_USED:
  - <trusted-source entity name if any was the winning source>
TRUSTED_SOURCES_REGISTERED:
  - <trusted-source entity name if this run added or updated one>
RAW_CACHE_PATH: <project>/.kiho/state/research/<iso>-<slug>.md
PROMOTED_TO_KB: <company-or-project-page-path | null>
NOTES: <optional: stale-source warning, single-source warning, etc.>
```

**Escalation:**

```markdown
## Receipt <REQUEST_ID>
OPERATION: research
STATUS: escalate_to_user
QUERY: <verbatim>
CONFIDENCE: 0.4
CASCADE_STEPS_TRIED: [kb, web, deepwiki, clone]
USER_QUESTION: |
  <exact question — the CEO will pass this to AskUserQuestion>
CANDIDATE_ANSWERS:
  - option 1: <text>
  - option 2: <text>
PARTIAL_CONTEXT: |
  <what the cascade found, even if low confidence>
REASON_CASCADE_FAILED: <one-line>
```

## Anti-patterns

- Never skip a step. If the CEO passes `max_steps: 3`, short-circuit at step 3 — but never jump from step 1 directly to step 5.
- Never fabricate citations. Every cited fact must trace to a real, loaded source.
- Never accept a single low-quality source (forum post, random blog) as high confidence.
- Never clone a repo > 50 MB or persist clones beyond the current call.
- Never cache time-sensitive findings to the KB.
- Never return "I don't know" without completing the cascade and escalating.
- Never escalate to the user on every question. 0.80 is a threshold, not a minimum. If step 1 returns 0.82, stop; don't keep looking for 0.99.
