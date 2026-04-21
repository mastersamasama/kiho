# Research cascade protocol

Full specification of kiho's five-step research cascade. Loaded by the `research` skill and by any agent that needs to understand cascade semantics in depth.

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.

## Non-Goals

- **Not a web scraper.** The cascade consults KB first, then trusted sources, then open web. Bulk scraping and unauthorized crawling are out of scope — `robots.txt` compliance is enforced via `robots_check.py`.
- **Not a replacement for `research-deep`.** The cascade is a single-pass retrieval protocol; `research-deep` does BFS traversal of a doc tree. Use the cascade for known questions; use research-deep for cold-start domain discovery.
- **Not a substitute for primary sources.** The cascade returns synthesized answers with citations, but the caller **MUST** verify primary sources for any decision that would be hard to reverse.

## Contents
- [Overview](#overview)
- [Step sequence and thresholds](#step-sequence-and-thresholds)
- [Source authority rubric](#source-authority-rubric)
- [Deepwiki repo matching](#deepwiki-repo-matching)
- [Clone safety rules](#clone-safety-rules)
- [Caching policy](#caching-policy)
- [Escalation formatting](#escalation-formatting)
- [Common failure modes](#common-failure-modes)

## Overview

kiho agents never search ad-hoc. Every external-information need goes through the `research` skill, which enforces this five-step cascade:

```
1. KB      → free         → confidence ≥ 0.80 short-circuits
2. WEB     → cheap        → confidence ≥ 0.80 short-circuits
3. DEEPWIKI→ medium       → confidence ≥ 0.80 short-circuits
4. CLONE   → slow, gated  → confidence ≥ 0.80 short-circuits
5. ESCALATE→ expensive    → return a user-question to CEO
```

The cascade is cost-ascending and confidence-descending. Stop at the first step that clears 0.80 on both "addresses the query" and "sources are authoritative". Never skip steps.

## Step sequence and thresholds

| Step | Source | Threshold | Typical latency | Cost driver |
|---|---|---|---|---|
| 1 | KB (via kb-search) | 0.80 | seconds | tokens only |
| 2 | Web (via WebSearch + WebFetch) | 0.80, AND ≥ 2 authoritative sources that agree | 5–30 seconds | web fetch tokens |
| 3 | Deepwiki MCP | 0.80 | 10–60 seconds | MCP roundtrip + tokens |
| 4 | Clone-as-reference | 0.80 | 30 sec – 5 min | disk + bash + tokens |
| 5 | Escalate | (n/a) | minutes of user attention | user interruption |

### Step 1 — KB

Call:
```
Agent(subagent_type="kiho-kb-manager",
      prompt="TIER: both\nOPERATION: search\nPAYLOAD:\n  query: <Q>\n  max_results: 10\n  require_confidence: 0.80")
```

Interpret the receipt:
- If `CONFIDENCE >= 0.80` AND `ANSWER` directly addresses the query → **STOP**, return with `cascade_step_used: kb`.
- If `CONFIDENCE < 0.80` but relevant pages were found → keep them as partial context for subsequent steps.
- If `STALE_OR_MISSING: true` → proceed to step 2.

### Step 2 — Web

Issue `WebSearch` with the query or a refined form. Apply the [source authority rubric](#source-authority-rubric) to filter results. Need ≥ 2 independent high-confidence sources that agree.

Pull specific pages with `WebFetch` to verify details. Prefer authoritative URLs over SEO-optimized listings.

- **2+ high-confidence sources agree** → synthesize, confidence = 0.85, return with `cascade_step_used: web`.
- **1 high-confidence source** → confidence caps at 0.70, add `single_source: true` flag, proceed to step 3.
- **No high-confidence sources** → proceed to step 3.

### Step 3 — Deepwiki MCP

If the query maps cleanly to a GitHub repository name (see [Deepwiki repo matching](#deepwiki-repo-matching)):

```
mcp__deepwiki__ask_question(
  repoName="<owner/repo>",
  question="<Q>"
)
```

Deepwiki typically returns confidence 0.85+ for indexed repos. If the answer concretely addresses the query → **STOP**, return with `cascade_step_used: deepwiki`.

For structural exploration (no specific question yet):

```
mcp__deepwiki__read_wiki_structure(repoName="<owner/repo>")
```

Then follow up with `ask_question` on the most relevant section.

### Step 4 — Clone-as-reference

Only if steps 1–3 all fell short AND the clone gates pass (see [Clone safety rules](#clone-safety-rules)).

```bash
TMPDIR=$(mktemp -d)
git clone --depth 1 --single-branch <repo-url> "$TMPDIR" 2>&1 | tail -5
du -sh "$TMPDIR"  # verify <50MB
```

Use `Read`/`Glob`/`Grep` inside `$TMPDIR` to find the answer. When done:

```bash
rm -rf "$TMPDIR"
```

If the answer was found → return with `cascade_step_used: clone`.

### Step 5 — Escalate

If the cascade produced no confident answer (typically CONFIDENCE < 0.80 across all steps), return `status: escalate_to_user`. Format per [Escalation formatting](#escalation-formatting).

## Source authority rubric

### High-confidence sources (authoritative)

- **Official documentation**: `claude.com/docs`, `platform.claude.com/docs`, `code.claude.com/docs`, `nodejs.org`, `rust-lang.org`, `postgresql.org`, `react.dev`, etc.
- **Standards bodies**: RFC (ietf.org), W3C, Unicode Consortium, ECMA, ISO
- **Engineering blogs from respected orgs**: Anthropic, Stripe, Fly.io, Uber, Netflix, Discord engineering
- **Academic papers**: arxiv.org, acm.org, ieee.org, nature.com
- **GitHub READMEs from ≥ 1000-star repos** of respected organizations
- **Specification documents**: OpenAPI, JSON Schema, etc.

### Medium-confidence sources (useful but cite with caveats)

- Well-known tech blogs with clear authorship (Simon Willison, Julia Evans, etc.)
- Vendor-published how-tos (AWS docs, GCP docs, Azure docs — vendor-biased but generally accurate)
- Wiki pages on reputable platforms (MDN, Wikipedia for non-controversial topics)

### Low-confidence sources (never cite as authoritative)

- Reddit, Hacker News threads
- Stack Overflow answers older than 2 years
- Random Medium articles without clear authorship
- AI-generated content (including other LLMs' output)
- Personal blogs without subject-matter credentials

If the web step only surfaces low-confidence sources, do not claim high confidence. Proceed to step 3 or escalate.

## Deepwiki repo matching

Deepwiki is powerful but only helps when the query maps to a known repo. Heuristics:

| Query pattern | Repo to try |
|---|---|
| "how does `<named project>` work?" | `<common-org>/<named-project>` (try anthropics/, huggingface/, microsoft/, etc.) |
| "what is `<library>`'s API for X?" | the library's canonical repo |
| "Claude Code plugin structure" | `anthropics/claude-code` |
| "how to author a skill" | `anthropics/skills` |
| "OpenSpace skill evolution" | `HKUDS/OpenSpace` |
| "revfactory harness" | `revfactory/harness` |
| "Karpathy autoresearch" | `karpathy/autoresearch` |

If you're not sure which repo, do NOT guess wildly. Either search the web first for "<query> github" to find the canonical repo URL, or skip deepwiki and go to step 4.

Deepwiki can also do structural browsing:
```
mcp__deepwiki__read_wiki_structure(repoName="owner/repo")
```
Returns a table of contents. Pick the most relevant section, then `ask_question`.

## Clone safety rules

**Gate 1: Size check.** Before cloning, either:
- Do a web search for "<repo> size" or "<repo> bytes", or
- Clone with `--depth 1` and immediately `du -sh` to verify ≤ 50 MB. If over, `rm -rf` and abort.

**Gate 2: Provenance check.** Repo must be clearly attributed:
- Known organization (anthropics, huggingface, nvidia, google, etc.)
- ≥ 100 stars
- License file present
- Not obviously suspicious (no cryptomining, no typosquatting a known repo)

**Gate 3: Ephemeral clone.** Always clone to `$(mktemp -d)`. Never persist.

**Gate 4: Cleanup on exit.** `rm -rf` the clone before returning. Even on error paths.

**Gate 5: No network-heavy operations.** No `npm install`, `pip install`, `cargo build`. Just Read/Grep/Glob on the cloned files.

## Caching policy

**Always cache** research outputs to `<project>/.kiho/state/research/<iso>-<slug>.md`:

```markdown
---
query: <verbatim>
status: <ok|escalate_to_user>
confidence: <0..1>
cascade_step_used: <step>
cached_at: <iso>
author_agent: <agent-id>
ttl_days: 90        # research findings auto-expire
---

# Research result
<answer>

## Sources
- [1] <url-or-path>
- [2] ...

## Cascade trace
- Step 1 (KB): <hit|miss>
- Step 2 (web): <hit|miss>
- ...
```

**Promote to KB** when:
- `cache_to_kb: true` was set in the request
- Final confidence ≥ 0.85
- The finding is durable (not version-specific, not time-sensitive, not "as of 2026")

Call `kiho-kb-manager` op=`add` with `page_type: concept` (or `entity`, as appropriate) and the research result as content.

**Do NOT promote**:
- Time-sensitive facts ("latest version", "current pricing", "this quarter")
- Low-confidence answers (< 0.85)
- Project-specific findings that shouldn't travel (cache to project tier, not company)

## Escalation formatting

When the cascade fails, return a structured escalation to the CEO:

```markdown
## Receipt <REQUEST_ID>
STATUS: escalate_to_user
QUERY: <verbatim>
CONFIDENCE: <final confidence, usually < 0.80>
CASCADE_STEPS_TRIED: [kb, web, deepwiki, clone]
REASON_CASCADE_FAILED: |
  <one-paragraph explanation: missing sources, conflicting sources, out-of-date info, or specific gap>

USER_QUESTION: |
  <exact question the user needs to answer — CEO will pass this verbatim to AskUserQuestion>

CANDIDATE_ANSWERS:
  - option 1: <derivable candidate with rationale>
  - option 2: <derivable candidate with rationale>

PARTIAL_CONTEXT: |
  <what the cascade did find, even if low confidence — gives the user a starting point>

RECOMMENDATION: |
  <kiho-researcher's best guess, explicitly labeled as low-confidence>
```

CEO receives this, may bundle with other pending escalations, and calls `AskUserQuestion` with structured options.

## Common failure modes

**Agent bypasses the cascade.** Agent uses WebSearch directly instead of invoking the `research` skill. **Fix**: enforced via prompt-level instruction in every agent frontmatter that mentions research. If an agent still bypasses, it's a bug in that agent's prompt — report for correction.

**Cascade stops too early.** Agent accepts a 0.75 KB result without checking step 2. **Fix**: threshold is 0.80, not "close enough". Agents must not cheat.

**Cascade stops too late.** Agent runs all 4 steps when step 1 gave a 0.85 answer. **Fix**: short-circuit semantics are mandatory. Running all steps when step 1 clears the threshold is wasted tokens.

**Fabricated citations.** Agent cites a URL that wasn't actually fetched. **Fix**: every citation must trace to an actual WebFetch call in the agent's tool trace. kb-lint catches this retroactively via rule enforcement.

**Single-source web acceptance.** Agent accepts one source as 0.80 confident. **Fix**: the rubric requires 2 independent high-confidence sources that agree. One source caps at 0.70.

**Runaway clones.** Agent clones a 500MB repo. **Fix**: the size gate must fire before reading. If the agent fails to run `du -sh`, the clone step counts as failed and proceeds to escalate.

**Stale cache reuse.** Agent reuses a research cache entry from 6 months ago. **Fix**: `ttl_days: 90` in cached entries; entries older than the TTL are ignored. The `research` skill checks the TTL on every cache lookup.

## Source attribution

User's explicit requirement: "for research, first find kb, if kb no, web search with high confidence result, can use deepwiki mcp, clone the repo directly as reference as well, then if cannot conclude to a answer, ask user question."

This protocol document codifies that sequence.
