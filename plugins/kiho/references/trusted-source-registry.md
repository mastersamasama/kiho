# Trusted source registry

A persistent index of external sources the kiho org has found useful. Lives in the **company-tier KB** so it follows the user across projects. Every agent that needs to research something consults the registry first — the goal is that repeat research on the same topic never starts from blind web search.

## Contents
- [Why a registry](#why-a-registry)
- [Storage](#storage)
- [Schema](#schema)
- [Trust levels](#trust-levels)
- [Source types](#source-types)
- [Auto-population](#auto-population)
- [Trust promotion and demotion](#trust-promotion-and-demotion)
- [Seed entries](#seed-entries)
- [Query patterns](#query-patterns)
- [Security rules](#security-rules)
- [Anti-patterns](#anti-patterns)

## Why a registry

Every research cascade that ends with a successful fetch produces one durable artifact: the URL that worked. kiho previously discarded this — each new research call started from blind `WebSearch`. The registry captures the URL, tags it with topic and trust metadata, and makes it the first port of call on the next research run.

Concrete wins:
- `research-deep` on "React Server Components" hits `react.dev/reference/rsc` in step 1, not step 3.
- Tool discovery (ossinsight, deepwiki, awesome-* lists) becomes a named capability, not tribal knowledge.
- Auth-gated sources record their auth method, so the next visit can reuse the credential handshake without re-asking.
- Bad sources (outdated, SEO-farmed, retracted) get demoted and skipped on future runs.

## Storage

Trusted sources are **KB entity pages** under the `trusted-sources/` subdirectory of the company-tier wiki:

```
$COMPANY_ROOT/company/wiki/entities/trusted-sources/
├── playwright-dev.md
├── react-dev.md
├── storybook-official.md
├── deepwiki.md
├── ossinsight.md
├── npm-registry.md
└── ...
```

All writes go through `kb-manager` (`kb-add`, `kb-update`, `kb-delete`). All reads go through `kb-search` with `page_type: entity` and a tag filter like `tag: trusted-source`. Never read or write the directory directly.

**Why company-tier and not project-tier:** sources are portable across projects. A good doc on Playwright visual regression is equally useful for a frontend-qa hire in project A and project B. Project-tier trusted sources are allowed but rare — use them only when the source is genuinely project-specific (a private API, an internal wiki).

## Schema

Every entry is a KB entity page with this frontmatter and body shape. See `templates/kb-trusted-source.template.md` for the canonical template.

```markdown
---
kind: entity
entity_type: trusted-source
name: playwright-dev
display_name: Playwright (official)
url: https://playwright.dev/
url_patterns:
  - "https://playwright.dev/**"
  - "https://github.com/microsoft/playwright/**"
source_type: api-docs          # see Source types below
trust_level: official          # see Trust levels below
auth_required: false
auth_method: none              # none | public-cookie | oauth | basic | api-key
topic_tags: [playwright, testing, e2e, browser-automation, visual-regression]
covers_tools:
  - mcp__playwright__*
last_verified: 2026-04-14
use_count: 0
success_count: 0
failure_count: 0
promoted_from: seed
added_by: kiho-setup
robots_txt_checked: 2026-04-14
---

# Playwright (official)

Microsoft-maintained browser automation library covering Chromium, Firefox, and WebKit. Authoritative for anything tagged `playwright`, `e2e`, `visual-regression` (when combined with `test-snapshots`), and `browser-automation`.

## When to use
- Any research on browser automation, UI testing, or e2e test frameworks
- As a seed URL for `research-deep` when drafting frontend QA skills
- As a tool-discovery target when `mcp__playwright__*` appears in a gap

## Known strengths
- Complete API reference with examples
- Official test-snapshots guide covers visual regression baselines
- Active maintainers; docs are kept current

## Known limitations
- Very long — `research-deep` should use page/novelty budgets
- Some pages require JS to render fully; prefer the `/docs` tree over marketing pages
```

## Trust levels

| Level | Meaning | Who can promote | Research weight |
|---|---|---|---|
| `official` | First-party docs, standards bodies, authoritative primary sources | CEO only (manual) | +0.10 confidence in research cascade |
| `community` | Well-known community resources (awesome-* lists, deepwiki, ossinsight, popular blogs with identifiable authorship) | Auto after 3 successful uses OR CEO | +0.05 confidence |
| `unverified` | New entry, not yet validated | Default for auto-registered sources | baseline confidence |
| `demoted` | Was higher tier but failed on recent use (stale, wrong, retracted) | Auto after 2 failed uses | -0.10 confidence, deprioritize |
| `blocked` | Known bad (malware, AI-generated slop, retracted) | CEO only | never used |

Trust level affects two things:
1. **Ranking** in research cascade Step 1.5 — higher trust served first.
2. **Confidence bonus/penalty** applied to the research output when the source is cited.

## Source types

| `source_type` | Purpose | Example entries |
|---|---|---|
| `api-docs` | First-party API/framework documentation | playwright.dev, react.dev, docs.anthropic.com |
| `best-practices` | Official or semi-official best-practice guides | web.dev, owasp.org, testing-library.com/docs |
| `tool-discovery` | Sites that help find tools, libraries, MCPs | ossinsight.io, awesome-* GitHub repos, mcp.so |
| `repo-intelligence` | Deep-docs layers over GitHub repos | deepwiki.com |
| `package-registry` | Package indexes (for discovery + metadata) | npmjs.com, pypi.org, crates.io |
| `standards-body` | RFCs, specs, official standards | w3.org, ietf.org, unicode.org, iso.org |
| `academic` | Papers + preprints | arxiv.org, acm.org, openreview.net |
| `community-ref` | Community-maintained reference (not official) | mdn-web-docs, wikipedia-tech |
| `vendor-docs` | Third-party vendor docs | stripe.com/docs, vercel.com/docs |
| `examples` | Code examples / example galleries | github.com/vercel/next.js/tree/canary/examples |

A single entry can have one primary `source_type` and additional `topic_tags` for secondary coverage.

## Auto-population

Trusted sources are populated automatically by the research cascade:

1. Every time `research` or `research-deep` finishes with a winning URL and confidence ≥ 0.80, it calls `kb-search` for `trusted-sources` matching the URL host + path pattern.
2. If no match, call `kb-add` with:
   - `entity_type: trusted-source`
   - `trust_level: unverified`
   - `url_patterns`: the URL and its parent directory
   - `topic_tags`: derived from the research query
   - `added_by`: the calling agent
3. On every successful reuse of an existing entry, call `kb-update` to increment `use_count` and `success_count`. `last_verified` gets bumped.
4. On every failed reuse (fetch returns 404, content stale, contradicts newer high-confidence source), call `kb-update` to increment `failure_count`.

**Rule:** the research cascade never skips the registry write. Missing this step means the next run starts from blind search.

## Trust promotion and demotion

Automatic trust transitions:

| From | To | Trigger |
|---|---|---|
| `unverified` | `community` | `success_count >= 3` AND `failure_count == 0` |
| `community` | `demoted` | `failure_count >= 2` in the last 10 uses |
| `demoted` | `unverified` | manual CEO re-check + `last_verified` refreshed |
| `unverified` | `demoted` | `failure_count >= 2` in first 5 uses |

**Manual transitions only:**
- `unverified | community` → `official` — requires CEO approval. Official status is for primary sources only.
- any → `blocked` — requires CEO approval. Blocked sources stay out of the cascade permanently.
- `demoted` → `community` — requires CEO approval after re-verification.

**No auto-promotion to `official` ever.** Official is a judgment call; only the CEO may apply it.

## Seed entries

kiho ships with a baseline set. These are created by `kiho-setup` on first run (idempotent — already-present entries are skipped).

| Name | URL | Source type | Trust | Primary topics |
|---|---|---|---|---|
| `playwright-dev` | https://playwright.dev/ | api-docs | official | browser-automation, e2e, visual-regression |
| `react-dev` | https://react.dev/ | api-docs | official | react, components, hooks |
| `storybook-official` | https://storybook.js.org/docs | api-docs | official | component-dev, visual-testing, design-system |
| `mdn` | https://developer.mozilla.org/ | community-ref | official | web-platform, browser-apis, html, css, js |
| `anthropic-docs` | https://docs.anthropic.com/ | api-docs | official | claude, mcp, prompt-engineering |
| `claude-code-docs` | https://code.claude.com/docs/en/ | api-docs | official | claude-code, subagents, skills, plugins |
| `deepwiki` | https://deepwiki.com/ | repo-intelligence | community | github-repos, ai-generated-docs |
| `ossinsight` | https://ossinsight.io/ | tool-discovery | community | popularity-metrics, trending-repos, tool-discovery |
| `awesome-mcp` | https://github.com/modelcontextprotocol/servers | tool-discovery | community | mcp-servers, discovery |
| `mcp-registry` | https://github.com/modelcontextprotocol/registry | tool-discovery | community | mcp-servers, registry |
| `npm-registry` | https://www.npmjs.com/ | package-registry | community | js-packages, metadata |
| `pypi` | https://pypi.org/ | package-registry | community | python-packages, metadata |
| `crates-io` | https://crates.io/ | package-registry | community | rust-crates, metadata |
| `arxiv-cs` | https://arxiv.org/list/cs/ | academic | official | research-papers, cs |
| `owasp` | https://owasp.org/ | best-practices | official | security, web-vulnerabilities, llm-top-10 |
| `web-dev` | https://web.dev/ | best-practices | official | web-performance, accessibility, pwa |

Seed entries are the **only** entries written outside the normal `research → auto-register` flow.

## Query patterns

When any agent needs to research a topic, it queries the registry FIRST:

```
kb-search(
  query: "<topic keywords>",
  page_type: entity,
  entity_type: trusted-source,
  filters: {
    topic_tags_any: ["playwright", "visual-regression"],
    trust_level_in: [official, community]
  },
  max_results: 5,
  sort_by: [trust_level DESC, success_count DESC]
)
```

The cascade uses the returned URLs as **seed URLs** for `research-deep`, not final answers. The sources are known-good launchpads; the content still needs to be fetched and validated.

### Tool-discovery query shape

When `design-agent` hits a tool/MCP gap, it runs a specialized query:

```
kb-search(
  query: "tool-discovery <gap-keyword>",
  page_type: entity,
  entity_type: trusted-source,
  filters: { source_type: tool-discovery }
)
```

This surfaces sites that help find tools (ossinsight, awesome lists, mcp-registry) rather than content about tools.

## Security rules

1. **Never trust auto-registered sources with `official` status.** Auto-populate goes in as `unverified` or `community`. Official is manual.
2. **Always verify robots.txt** before using a URL as a seed for deep research. Record `robots_txt_checked: <iso-date>` in the entry. Re-check quarterly.
3. **Never store credentials in the registry.** `auth_method` records the TYPE (oauth, basic, cookie), never the value. Credentials go through OS keychain via the `auth-helper` primitive.
4. **Auto-demote on contradiction.** If a newer high-confidence source contradicts a registered source, increment `failure_count`. Two contradictions → demoted.
5. **Block AI-generated slop.** If a source has no clear human authorship AND content has telltale LLM generation markers, block on discovery.
6. **No auto-install from tool-discovery sources.** tool-discovery sources help *find* tools; installing them is always a separate CEO-gated decision.

## Anti-patterns

- **Querying the registry but not updating it.** Every successful research call must register or update. Skipping this rots the registry.
- **Auto-promoting to `official`.** Never. Official status is earned by CEO review, not usage count.
- **Writing to `$COMPANY_ROOT/company/wiki/entities/trusted-sources/` directly.** Always go through `kb-manager`. Direct writes break the index.
- **Storing content in the registry entry.** The entry is metadata (URL, trust, tags). Actual content lives in `.kiho/state/research/<iso>-<slug>.md` or in KB concept/synthesis pages.
- **Blanket blocking a whole domain.** Be surgical. Block specific paths, not `github.com` as a whole.
- **Skipping robots.txt check.** Some sources explicitly disallow automated fetching. Honor it.
