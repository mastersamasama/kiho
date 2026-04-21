# Deep research protocol

Specification for `research-deep` (sk-rdp) — the exhaustive documentation traversal skill that powers capability-gap skill synthesis. Unlike `research` (single-pass, 5-step cascade, returns one answer), `research-deep` performs a BFS over a documentation site's link graph, reads each page, incrementally updates a SKILL.md skeleton, and terminates when content novelty drops to zero.

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.

## Non-Goals

- **Not a general web crawler.** research-deep targets ONE documentation site at a time, respects `robots.txt` via `robots_check.py`, and terminates on content-novelty saturation. Bulk-scraping multiple sites in parallel is out of scope.
- **Not a replacement for the cascade.** For known questions, use `research` (5-step cascade). research-deep is for cold-start domain exploration where the answer is "build a complete mental model of this doc tree".
- **Not an authenticated-site bypass mechanism.** When research-deep hits an auth wall, it escalates to CEO (`escalate_to_user: auth-needed`) for user-mediated Playwright login. It does NOT attempt credential stuffing, session-cookie scraping, or MFA bypass.

## Contents
- [When to use research-deep vs research](#when-to-use)
- [Inputs](#inputs)
- [State files](#state-files)
- [BFS algorithm](#bfs-algorithm)
- [Skeleton-first incremental build](#skeleton-first-incremental-build)
- [Termination conditions](#termination-conditions)
- [Auth escalation via Playwright MCP](#auth-escalation-via-playwright-mcp)
- [Budgets](#budgets)
- [Security and robots.txt](#security-and-robotstxt)
- [Output](#output)
- [Anti-patterns](#anti-patterns)

## When to use

| Use case | research | research-deep |
|---|---|---|
| Answer a single question | ✓ | — |
| Decide between 2–3 candidate designs | ✓ | — |
| Fetch a best-practice guide | partially | ✓ |
| Synthesize a new skill from a doc tree | — | ✓ |
| Follow inline links and accumulate context | — | ✓ |
| Handle auth-gated docs | — | ✓ |
| Answer quickly (< 2 min) | ✓ | — |
| Exhaustive coverage of a topic domain | — | ✓ |

`research` is a 1-shot cascade that stops at the first confident answer. `research-deep` is a multi-page traversal that builds a whole skill. They are complementary — `research` feeds quick answers; `research-deep` feeds synthesis.

## Inputs

```
topic:           one short phrase — the topic to research
                 (e.g., "Playwright visual regression testing")
seed_urls:       [url, ...] — 1-5 starting points, usually from trusted-source-registry
role_context:    short string — who will use the resulting skill
                 (e.g., "frontend-qa IC doing UI visual regression in CI")
target_skill_id: optional — if resuming an in-progress skeleton, pass the existing ID
budget_pages:    int, default 50
budget_depth:    int, default 3 (max BFS depth from any seed)
budget_min:      int minutes, default 15
novelty_window:  int, default 3 (how many recent pages with zero new concepts trigger term)
auth_mode:       "never" | "ask" | "provided"
                 never = fail on auth-needed
                 ask = escalate to CEO/user for login
                 provided = use credentials already in OS keychain
requestor:       agent-id of caller (usually design-agent)
```

## State files

Every `research-deep` run uses three files with a shared slug derived from `topic`:

### `.kiho/state/research-queue/<slug>.jsonl`

Append-only BFS queue + read log. One JSON object per line.

```jsonc
// Queue entry (pending)
{ "kind": "queue", "url": "https://playwright.dev/docs/test-snapshots", "depth": 0, "source_url": null, "discovered_at": "2026-04-14T..." }

// Read entry (fetched and processed)
{ "kind": "read", "url": "https://playwright.dev/docs/test-snapshots", "depth": 0,
  "read_at": "2026-04-14T...", "status": "ok", "tokens_fetched": 3400,
  "extracted_concepts": ["snapshot-baseline", "update-workflow", "pixel-threshold"],
  "new_concepts_added": 3, "discovered_links": [/* urls */],
  "extraction_summary": "Snapshots are PNG files stored alongside tests. Update via --update-snapshots flag. Threshold tuned via maxDiffPixels." }

// Auth-needed signal
{ "kind": "auth_needed", "url": "https://docs.example.com/private", "detected_at": "2026-04-14T...",
  "auth_method": "cookie-session", "escalated_to_ceo": true }

// Termination marker
{ "kind": "terminate", "reason": "novelty_exhausted" | "budget_pages" | "budget_depth" | "budget_min" | "queue_empty" | "auth_denied",
  "at": "2026-04-14T...", "pages_read": 27, "concepts_captured": 41 }
```

### `.kiho/state/skill-skeletons/<slug>.md`

Living skill skeleton. Overwritten atomically on every update. Follows the template in `templates/skill-skeleton.template.md`.

### `.kiho/state/research/<iso>-<slug>.md`

Final raw dump — the traditional research output shape, for audit compatibility with the `research` skill. Written once at termination.

## BFS algorithm

```
queue = [{url: seed, depth: 0} for seed in seed_urls]
read_set = {}
novelty_streak = 0
pages_read = 0
start_time = now()

# Check robots.txt for each seed's host before starting
for seed in seed_urls:
    if not robots_allows(seed):
        emit queue_log: {"kind": "skip", "url": seed, "reason": "robots_disallow"}
        continue

# Initialize skeleton with overview section only (derived from topic + role_context)
write_skeleton(slug, initial_overview(topic, role_context))

while queue is not empty:
    # Budget checks
    if pages_read >= budget_pages: terminate("budget_pages"); break
    if now() - start_time >= budget_min: terminate("budget_min"); break
    if novelty_streak >= novelty_window: terminate("novelty_exhausted"); break

    # Pop next URL (BFS order: lower depth first, then FIFO)
    entry = queue.pop_lowest_depth()
    url, depth = entry.url, entry.depth

    if url in read_set: continue
    if depth > budget_depth:
        emit queue_log: {"kind": "skip", "url": url, "reason": "depth_cap"}
        continue

    # Fetch
    try:
        content = fetch(url, auth_mode=auth_mode)
    except AuthNeeded as e:
        if auth_mode == "never":
            emit queue_log: {"kind": "skip", "url": url, "reason": "auth_needed_never_mode"}
            continue
        elif auth_mode == "ask":
            escalate_auth(url, e.auth_method)
            # If escalation approved, credential is now in keychain; retry once
            content = fetch(url, auth_mode="provided")
        else:
            content = fetch(url, auth_mode="provided")
    except FetchError as e:
        emit queue_log: {"kind": "fetch_error", "url": url, "error": str(e)}
        continue

    # Extract
    concepts = extract_concepts(content, topic, role_context)
    new_concepts = [c for c in concepts if c not in skeleton.extracted_concepts]
    links = extract_links(content)
    same_topic_links = filter_same_topic(links, topic, url.host)

    # Update skeleton
    skeleton.merge(new_concepts, url)
    write_skeleton(slug, skeleton)  # atomic

    # Log
    emit read_log entry

    # Queue new links (BFS)
    for link in same_topic_links:
        if link not in read_set and link not in queue:
            queue.append({url: link, depth: depth + 1, source_url: url})

    # Update novelty counter
    if len(new_concepts) == 0:
        novelty_streak += 1
    else:
        novelty_streak = 0

    read_set.add(url)
    pages_read += 1

if queue is empty:
    terminate("queue_empty")

# Final consolidation
consolidate_skeleton(slug)
write_final_research_dump(slug)
```

### Filter rules for `filter_same_topic`

- **Same-host by default.** Links outside the seed host are dropped unless:
  - The link target is in the trusted-source-registry with `trust_level in [official, community]` AND overlapping tags
  - The link target is on a known package-registry (npm/pypi/crates) AND the topic involves that ecosystem
- **Skip anchor-only links** (`#section-foo` without a path change).
- **Skip mailto / tel / javascript pseudo-protocols.**
- **Skip localized duplicates** when a canonical language version exists (e.g., `/zh/` and `/ja/` when `/en/` is available).
- **Respect `rel="nofollow"` for trust ranking** — don't skip, but drop the depth bonus.
- **Respect explicit doc-tree boundaries.** On sites that have `/docs/` vs `/blog/` vs `/reference/`, only follow links within the same tree as the seed unless the seed was a landing page.

## Skeleton-first incremental build

The skeleton is the single most important output. It's a living SKILL.md that gets updated on every read. The first read produces an Overview; every subsequent read merges new concepts into the right section.

### Structure (from `templates/skill-skeleton.template.md`)

```markdown
---
slug: sk-playwright-visual-regression
topic: "Playwright visual regression testing"
role_context: "frontend-qa IC doing UI visual regression in CI"
status: in-progress | terminated
pages_read: 12
extracted_concepts:
  - snapshot-baseline
  - update-workflow
  - pixel-threshold
  - ci-integration
last_updated: 2026-04-14T...
---

# <topic>

<!-- Overview written on first read; refined on every subsequent read -->
## Overview
<one-paragraph summary of what this skill does and when to use it>

## When to use
<bullet list of triggers; appended per read>

## Preconditions
<bullet list; appended per read>

## Procedure
<numbered steps; each step tagged with source URL; reorganized on consolidation>

## Configuration
<bullet list of important config knobs; appended per read>

## Pitfalls and gotchas
<bullet list; appended per read>

## Examples
<code blocks; each tagged with source URL>

## Sources
<list of all URLs read, with extraction timestamp>

## Extraction log
<!-- mirrors research-queue/<slug>.jsonl for at-a-glance auditing -->
```

### Update rules

- **Never overwrite a section.** Append to the relevant subsection, preserving prior reads.
- **Cite every bullet** with the source URL it came from. On consolidation, duplicate bullets merge and citations combine.
- **Concept dedup** uses normalized-phrase matching — "snapshot baseline" and "baseline snapshot" are the same concept.
- **On consolidation,** reorder sections into canonical order, dedupe, and tighten phrasing. This is the only time the skeleton is rewritten (not appended).

## Termination conditions

Listed in priority order. First condition to fire wins.

| Condition | Trigger | Termination reason |
|---|---|---|
| **Queue empty** | BFS has drained the queue and visited everything reachable | `queue_empty` — clean exhaustion |
| **Novelty exhausted** | Last `novelty_window` (default 3) consecutive reads produced 0 new concepts | `novelty_exhausted` — content has saturated |
| **Page budget** | `pages_read >= budget_pages` | `budget_pages` — budget cap |
| **Time budget** | `now() - start_time >= budget_min` | `budget_min` — budget cap |
| **Depth budget** | Every remaining queue entry has `depth > budget_depth` | `budget_depth` — depth cap |
| **Auth denied** | User declined auth escalation for a seed that had no auth-free path | `auth_denied` — partial results |

**Preferred exit is `novelty_exhausted`.** It means the doc tree's useful content has been captured and further reading would waste budget. If a run consistently exits on `budget_pages`, the budget is too small for the topic — tune up the budget for that topic in the trusted-source-registry entry.

**Discouraged exit is `budget_min`.** Time-based termination usually means the traversal was spending too much time on slow pages; consider raising budget_min or lowering budget_pages.

## Auth escalation via Playwright MCP

When `fetch()` encounters an auth wall (HTTP 401/403, login redirect, or known auth-gate signals like "Sign in to continue") AND `auth_mode: ask`:

1. Emit `auth_needed` entry to the queue log.
2. Return structured `escalate_to_user` to design-agent (or whatever invoked research-deep):
   ```json
   {
     "status": "escalate_to_user",
     "reason": "auth-needed",
     "url": "https://docs.example.com/private/api",
     "auth_method": "cookie-session",
     "site_name": "docs.example.com",
     "why": "required to read <topic> documentation for <role_context>",
     "alternatives": ["skip this source and use other seeds", "defer research-deep until credential is available"]
   }
   ```
3. design-agent bubbles the escalation to CEO. CEO calls `AskUserQuestion` with options:
   - Approve interactive login (kiho spawns Playwright MCP, opens the URL in a controlled browser, you log in, cookie is captured)
   - Skip this source and continue with remaining seeds
   - Defer the whole research-deep run
4. If user approves interactive login:
   - CEO invokes `mcp__playwright__browser_navigate(url)` to open the auth URL in Playwright
   - User logs in interactively through the Playwright browser window
   - After successful login, CEO captures the session cookie via `mcp__playwright__browser_evaluate(script="document.cookie")`
   - Cookie is stored in **OS keychain** under key `kiho-auth-<host>`, with `expires_at` and `scope: <host>`
   - CEO returns control to research-deep with `auth_mode: provided`
   - research-deep retries the failed fetch using the cookie; on success, BFS resumes
5. **Credentials never land in KB, never land in `.kiho/state/`, never land in the research queue.** OS keychain only. The queue records `auth_method` but not the credential value.
6. **Session expiry handling.** If a cached cookie is expired or rejected, the fetch fails again; research-deep re-emits `auth_needed` and the cycle repeats. No silent retry with expired credentials.
7. **Scope limit.** Captured cookies are scoped to the host that issued them. A cookie for `docs.example.com` cannot be used on `api.example.com` even if they share a parent domain. This is a conservative posture to limit credential blast radius.

## Budgets

Defaults (overridable per invocation):

| Budget | Default | Rationale |
|---|---|---|
| `budget_pages` | 50 | Enough to cover a moderately deep doc tree; prevents runaway |
| `budget_depth` | 3 | Most doc trees have their load-bearing content within 3 clicks of the seed |
| `budget_min` | 15 | Wall-clock cap; forces the skill to be completable in a Ralph loop iteration |
| `novelty_window` | 3 | Three barren pages in a row is a strong saturation signal |
| `timeout_per_fetch` | 30s | Hard per-request cap to bound slow pages |

**Per-topic budget overrides** can be stored in the trusted-source-registry entry for the primary seed. Example: `playwright-dev` might declare `research_deep_budget: { pages: 80, min: 20 }` because the Playwright doc tree is unusually deep. design-agent reads the override before invoking research-deep.

## Security and robots.txt

1. **Always check robots.txt** for each seed's host before fetching any page. If disallowed, skip the seed (emit `skip: robots_disallow`) and continue with other seeds.
2. **Respect `Crawl-delay`** from robots.txt by throttling fetches to the declared interval. Default 1s between fetches to the same host.
3. **User-Agent honesty.** research-deep identifies itself as `kiho-research-deep/0.4 (+https://github.com/wky/kiho)` in the User-Agent header. No cloaking.
4. **No JavaScript execution from fetched content.** Strip `<script>`, `<iframe>`, and event handlers before feeding HTML to the LLM for extraction.
5. **No credential reuse across sites.** Cookies are scoped to the host that issued them (see Auth escalation).
6. **No automatic form-filling on login pages.** The user must interact with the Playwright browser window directly.
7. **Auth-walled sources always carry a trust concern.** Even after successful login, auth-gated pages get flagged `auth_required: true` in the trusted-source-registry and receive no trust bonus.

## Output

On termination, research-deep returns:

```json
{
  "status": "ok | partial | failed",
  "termination_reason": "novelty_exhausted | queue_empty | budget_pages | budget_depth | budget_min | auth_denied",
  "slug": "sk-playwright-visual-regression",
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

Caller (usually design-agent Step 4d) reads `skeleton_path` and hands it to `skill-learn op=synthesize` for finalization.

## Anti-patterns

- **Treating research-deep as a search engine.** It's a doc-tree crawler with synthesis. If you need a single answer, use `research`.
- **Running without seed URLs.** Blind research-deep from a web search is budget-poison. Always start with trusted-source-registry seeds.
- **Ignoring novelty termination.** The whole point of novelty termination is to avoid reading saturated content. If you keep raising `novelty_window`, you're fighting the algorithm — probably the seed is wrong.
- **Auto-retrying on auth-denied.** If the user declined auth, that is the final answer for this turn. Continue with other seeds or terminate.
- **Storing credentials in state files.** Never. OS keychain only.
- **Cloning instead of crawling.** research-deep reads via HTTP, not git clone. Use the `research` skill's clone-as-reference step if you need a whole repo.
- **Skipping robots.txt.** Always check. Violating robots.txt is both unethical and gets your user IP blocked.
- **Appending duplicate bullets to the skeleton.** The concept dedup step is load-bearing; a skeleton with 20 variants of "snapshot baseline" is worse than one clean bullet.
- **Running multiple research-deep invocations on the same slug concurrently.** They will race on the skeleton file and produce garbage. Serialize by slug.
