---
name: research-deep
description: Exhaustive documentation traversal skill for capability-gap skill synthesis. Performs BFS over a doc site's inline link graph, fetches each page via WebFetch or mcp__deepwiki__read_wiki_contents, extracts concepts, and incrementally updates a living SKILL.md skeleton until content novelty drops to zero or budgets exhaust. Terminates cleanly on queue-empty, novelty-exhausted, page/depth/time budgets, or auth-denied. Escalates auth-walled seeds via Playwright MCP for interactive login; never stores credentials in KB. Used by design-agent Step 4d when a capability gap is researchable (no parent skill in catalog, but trusted-source registry has coverage). Triggers on "deep research", "exhaustive doc crawl", "synthesize skill from docs", "research tree".
metadata:
  trust-tier: T2
  kiho:
    capability: create
    topic_tags: [research, authoring]
    data_classes: ["research-cache", "kb-wiki-articles"]
---
# research-deep

Multi-page documentation crawler with BFS link-graph traversal and skeleton-first incremental skill build. Complementary to `research` (single-pass 5-step cascade) — where `research` answers one question, `research-deep` reads a whole doc tree and produces a SKILL.md skeleton ready for `skill-learn op=synthesize`.

> **v5.21 cycle-aware.** This skill is the `research-deep` phase entry in `references/cycle-templates/talent-acquisition.toml` and `references/cycle-templates/kb-bootstrap.toml`. When run from cycle-runner, the cycle's `index.toml` carries the chosen tool/topic from the upstream `decision` phase; this skill writes pages_crawled / status / skeleton_ref back into `index.research.*` with `output_pages` declared in the template so the cycle's page budget is enforced. Atomic invocation remains supported for ad-hoc deep crawls outside any cycle.

## Contents
- [When to use](#when-to-use)
- [Inputs](#inputs)
- [Tools used](#tools-used)
- [Procedure](#procedure)
- [Link filtering](#link-filtering)
- [Concept extraction](#concept-extraction)
- [Skeleton updates](#skeleton-updates)
- [Novelty termination](#novelty-termination)
- [Auth escalation](#auth-escalation)
- [State files](#state-files)
- [Response shape](#response-shape)
- [Anti-patterns](#anti-patterns)

## When to use

| Scenario | Use this skill |
|---|---|
| design-agent Step 4d hit a "researchable" gap and has trusted-source seeds | ✓ |
| A committee needs exhaustive coverage of a topic, not just a single answer | ✓ |
| kb-manager is bootstrapping the company KB for a new technology | ✓ |
| You need to *answer a question* with high confidence | use `research` instead |
| You need competitive analysis across many sources | use `research` instead (multi-source cascade is what it does) |
| You need real-time info (pricing, versions, news) | use `research` instead |
| The topic has no trusted-source-registry coverage | **do not run**; classify as Unfillable |

`research-deep` is **not** a search engine. It requires seed URLs and follows links; it does not start from a web search.

## Inputs

```
topic:            one short phrase — "Playwright visual regression testing"
seed_urls:        [url, ...]  1..5 starting points (usually from trusted-source-registry)
role_context:     short string describing who will use the resulting skill
target_skill_id:  optional — resume an in-progress skeleton
budget_pages:     default 50
budget_depth:     default 3
budget_min:       default 15 (wall-clock minutes)
novelty_window:   default 3
auth_mode:        never | ask | provided   (default: ask)
requestor:        agent-id of caller (usually design-agent)
```

Full budget semantics + filter rules in `references/deep-research-protocol.md`.

## Tools used

- **`WebFetch`** — primary content fetcher for HTTP(S) URLs. Returns markdown-converted text.
- **`mcp__deepwiki__read_wiki_contents`** + **`mcp__deepwiki__ask_question`** — when seed URL maps to a deepwiki repo, prefer deepwiki over raw GitHub (denser signal, AI-curated structure).
- **`mcp__playwright__browser_navigate`** + **`mcp__playwright__browser_evaluate`** — auth escalation path only (never for content fetching — research-deep extracts from static markdown, not rendered HTML).
- **`Read`** / **`Write`** — state file management (queue log, skeleton, research dumps).
- **`kb-search`** via kb-manager — trusted-source-registry lookups (for discovering per-topic budget overrides and auth mode).
- **`kb-add`** / **`kb-update`** via kb-manager — register successful URLs in trusted-source-registry; increment counters.

## Procedure

Follow the full BFS algorithm in `references/deep-research-protocol.md` §"BFS algorithm". High-level:

1. **Validate** — check `seed_urls` is non-empty, check `budget_*` values in range, derive `slug` from `topic`, check for an existing in-progress skeleton for that slug (abort if one exists and `target_skill_id` wasn't passed → avoid race).
2. **Check robots.txt** for each seed host. Skip seeds whose host disallows the path.
3. **Initialize** — write initial skeleton using `templates/skill-skeleton.template.md` with overview drafted from `topic` + `role_context`. Open `.kiho/state/research-queue/<slug>.jsonl` for append.
4. **BFS loop** — per `references/deep-research-protocol.md`. On each iteration:
   - Check budgets (pages, time, novelty, depth) — terminate if any tripped.
   - Pop lowest-depth URL from queue.
   - **Check robots.txt compliance** via `scripts/robots_check.py` (deterministic, deny-on-disallow):
     ```bash
     python skills/core/knowledge/research-deep/scripts/robots_check.py <url>
     ```
     If disallowed, emit `skip: robots_disallow` to the queue log and continue.
   - Fetch via WebFetch (or deepwiki if URL matches a known deepwiki repo).
   - On 401/403 or login-redirect, trigger auth escalation (see [Auth escalation](#auth-escalation)).
   - Extract concepts + links.
   - Merge new concepts into skeleton (append to appropriate section, tag with source URL).
   - Atomically write skeleton.
   - Append read entry to queue log.
   - Enqueue new links (BFS) after filtering.
   - Update novelty counter.
5. **Register source** — for every seed URL that was successfully used as a research anchor, call `kb-search` for an existing trusted-source entry. If missing, `kb-add` a new one with `trust_level: unverified, added_by: research-deep`. If present, `kb-update` incrementing `use_count` and `success_count`.
6. **Terminate** — write termination marker to queue log. Reason codes in §"Novelty termination" and `references/deep-research-protocol.md`.
7. **Consolidate** — reorganize the skeleton into canonical section order, dedupe bullets, merge citations, tighten phrasing. This is the only time the skeleton is rewritten instead of appended.
8. **Final dump** — write a traditional `.kiho/state/research/<iso>-<slug>.md` for audit compatibility with the `research` skill.
9. **Return** the structured response (see §"Response shape"). The caller (usually design-agent Step 4d) hands the `skeleton_path` to `skill-learn op=synthesize`.

## Link filtering

See `references/deep-research-protocol.md` §"Filter rules for `filter_same_topic`" for the canonical rules. Summary:

- Same-host by default; cross-host only if the target is registered in trusted-source-registry with overlapping tags OR is a package-registry for the relevant ecosystem
- Skip anchor-only, mailto/tel/javascript, localized duplicates
- Honor `rel="nofollow"` by dropping the depth bonus (do not skip)
- Respect doc-tree boundaries (`/docs/` vs `/blog/` vs `/reference/`)

## Concept extraction

For each fetched page, extract concepts using the following prompt schema (internal to the skill):

```
Given the page content and the research topic "{{topic}}" + role context "{{role_context}}",
produce:

1. A list of NEW concepts this page introduces relative to already-known concepts.
   Each concept is a short noun phrase (2-5 words). Normalize to lowercase-hyphenated
   form for dedup.
2. For each new concept, one sentence of context describing it.
3. Structural slots (When-to-use / Preconditions / Procedure / Configuration / Pitfalls /
   Examples) that this page populates, with a one-line bullet per slot.
4. A list of inline links in the page, each with link text + destination URL.

Ignore:
- Navigation chrome, headers, footers, cookie banners
- Marketing pages (unless the seed WAS a marketing page — then extract the call-to-action doc links)
- JavaScript-rendered content that didn't come through in the markdown conversion
```

The new-concept list is what drives novelty termination — a page that returns 0 new concepts increments the novelty streak.

## Skeleton updates

On every read:
- Append (never overwrite) new bullets under the appropriate section heading
- Tag every bullet with `[<source_url>]` prefix
- Merge duplicate concepts using normalized-phrase matching
- Update frontmatter: `pages_read`, `extracted_concepts`, `last_updated`
- Atomic write (write to temp file, rename)

On consolidation (final pass):
- Reorder sections into canonical order: Overview → When-to-use → Preconditions → Procedure → Configuration → Pitfalls → Examples → Sources
- Dedupe bullets by concept similarity
- Merge citations from multiple URLs into single bullets where appropriate
- Tighten prose — remove the `[<url>]` prefixes from individual bullets and move citations to a compact `Sources` section with per-concept cross-references
- Update status frontmatter to `terminated`

## Novelty termination

The most important exit condition. Default `novelty_window: 3` — if 3 consecutive reads produce 0 new concepts, terminate with `reason: novelty_exhausted`.

**Why novelty over page count.** A well-written doc tree reaches content saturation well before a 50-page budget. Stopping on saturation saves budget and avoids low-signal bullets polluting the skeleton. Budget-based termination is a safety net; novelty termination is the preferred exit.

**Tuning guidance.** If a topic consistently terminates on `budget_pages` without hitting novelty exhaustion, the budget is too small for that topic — record an override in the trusted-source-registry entry for the primary seed:

```yaml
research_deep_budget:
  pages: 80
  min: 20
  novelty_window: 4
```

design-agent reads the override before invoking research-deep. This lets well-known deep-doc topics (Playwright, React, Kubernetes) get more runway without raising the global default.

## Auth escalation

When a fetch returns HTTP 401/403 or detects a login redirect, AND `auth_mode: ask`:

1. Emit `auth_needed` entry to the queue log.
2. Return `status: escalate_to_user, reason: auth-needed` with the URL, the detected auth method, the site name, and a why-statement that includes `role_context`.
3. design-agent bubbles to CEO. CEO calls `AskUserQuestion` with three options: interactive login / skip this source / defer research-deep.
4. **If user approves interactive login:**
   - CEO invokes `mcp__playwright__browser_navigate(url: <auth URL>)`
   - Playwright opens a controlled browser window
   - User logs in interactively through the Playwright window
   - After login succeeds, CEO invokes `mcp__playwright__browser_evaluate(script: "document.cookie")` to capture the session cookie
   - Cookie is stored in **OS keychain** under key `kiho-auth-<host>` with `expires_at` and `scope: <host>`
   - research-deep resumes with `auth_mode: provided` and retries the failed fetch
5. **Credentials never land in KB, never in state files, never in research queue log.** OS keychain only.
6. **Cookie scope is strict:** a cookie for `docs.example.com` cannot be reused on `api.example.com` or any sibling subdomain.
7. **Session expiry:** if a cached cookie is rejected on a later fetch, re-escalate. Do not silently retry with stale credentials.

Full auth escalation spec in `references/deep-research-protocol.md` §"Auth escalation via Playwright MCP".

## State files

- **`.kiho/state/research-queue/<slug>.jsonl`** — append-only BFS queue + read log. Schema in `references/deep-research-protocol.md`.
- **`.kiho/state/skill-skeletons/<slug>.md`** — living skeleton, atomically overwritten each iteration. Follows `templates/skill-skeleton.template.md`.
- **`.kiho/state/research/<iso>-<slug>.md`** — final consolidated dump (written once at termination).
- **`.kiho/state/skill-skeletons/_archive/<slug>-<iso>.md`** — on successful synthesize, the skeleton moves here for lineage.

## Response shape

```json
{
  "status": "ok | partial | failed",
  "termination_reason": "novelty_exhausted | queue_empty | budget_pages | budget_depth | budget_min | auth_denied",
  "slug": "sk-playwright-visual-regression",
  "topic": "Playwright visual regression testing",
  "skeleton_path": ".kiho/state/skill-skeletons/sk-playwright-visual-regression.md",
  "queue_log_path": ".kiho/state/research-queue/sk-playwright-visual-regression.jsonl",
  "final_dump_path": ".kiho/state/research/2026-04-14T16-03-playwright-visual-regression.md",
  "pages_read": 27,
  "pages_skipped": 4,
  "concepts_captured": 41,
  "sources_registered": ["playwright-dev", "storybook-official"],
  "auth_escalations": 0,
  "wall_ms": 600000,
  "consolidated": true
}
```

On escalation:

```json
{
  "status": "escalate_to_user",
  "reason": "auth-needed",
  "url": "https://docs.example.com/private/api",
  "auth_method": "cookie-session",
  "site_name": "docs.example.com",
  "why": "required to read Playwright visual regression documentation for frontend-qa IC",
  "alternatives": ["skip this source and use other seeds", "defer research-deep until credential available"],
  "partial_skeleton_path": ".kiho/state/skill-skeletons/sk-playwright-visual-regression.md",
  "pages_read_so_far": 12
}
```

## Anti-patterns

- **Calling research-deep with zero seed URLs.** It's a crawler, not a search engine. Query the trusted-source-registry first; if empty, classify the gap as Unfillable and skip research-deep.
- **Running multiple invocations on the same slug concurrently.** They will race on the skeleton file. Serialize by slug — if a skeleton already exists in-progress, either wait or pass `target_skill_id` to resume.
- **Setting `auth_mode: never` for sources that are clearly auth-walled.** Just classify the gap as Unfillable in design-agent instead; don't waste budget hitting 401s.
- **Raising `novelty_window` to avoid termination.** If you're fighting the novelty counter, either the seeds are wrong or the topic is too broad. Revisit the seeds and the topic scope.
- **Storing captured cookies anywhere but OS keychain.** Never in KB. Never in state files. Never in the queue log. OS keychain only.
- **Skipping robots.txt.** Always check. Violating is both unethical and often gets the user's IP blocked.
- **Treating deepwiki results as equivalent to primary docs.** Deepwiki is great for structure but AI-curated. Prefer primary docs as seeds when both exist.
- **Consolidating before termination.** The consolidation step reorganizes and dedupes — running it mid-crawl corrupts the append-only discipline and you lose citations. Consolidate exactly once, at termination.
- **Persisting the skeleton in its in-progress form.** After synthesize runs, the in-progress skeleton should move to `_archive/` so the next run for the same slug is a clean start.
