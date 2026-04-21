# Karpathy LLM-wiki protocol — offline excerpt

Distilled from Andrej Karpathy's llm-wiki gist. Governs kiho's knowledge-base structure and maintenance. Cited offline so kb-manager has this doctrine available without network access.

## Contents
- [The core insight](#the-core-insight)
- [Three-layer architecture](#three-layer-architecture)
- [Standard files](#standard-files)
- [Page types](#page-types)
- [The ingest flow](#the-ingest-flow)
- [The query flow](#the-query-flow)
- [The lint flow](#the-lint-flow)
- [Cross-references](#cross-references)
- [Anti-patterns](#anti-patterns)
- [kiho-specific adaptations](#kiho-specific-adaptations)

## The core insight

> "The LLM is not a query engine — it's a wiki editor."

Traditional RAG retrieves from raw documents at query time. Every query re-discovers the same connections. The LLM wiki pattern flips this: the LLM *compiles* raw sources into a persistent, interlinked markdown collection. Queries hit the compiled wiki, not the raw sources. The wiki grows richer with each source and each question.

> "The tedious part of maintaining a knowledge base is not the reading — it's the bookkeeping." — Karpathy

The LLM handles bookkeeping (summarizing, cross-referencing, filing) so the human can focus on direction and emphasis.

## Three-layer architecture

```
raw/           # immutable source documents
wiki/          # LLM-generated markdown
knowledge-base.md  # schema + operations guide (kiho renames from Karpathy's CLAUDE.md)
```

**Raw layer.** Immutable. Never edited by the LLM. Source documents, papers, pasted content, committee transcripts, web snapshots. The LLM reads from here; never writes here except by append.

**Wiki layer.** LLM-owned markdown. Summaries, entity pages, concept pages, decision pages, cross-references, synthesis. The LLM writes and maintains everything here.

**Schema layer.** A single file (Karpathy calls it `CLAUDE.md`; kiho calls it `knowledge-base.md` to avoid plugin-root collision) that specifies how the wiki is structured, what the conventions are, how to ingest, how to query, how to lint.

## Standard files

Every kiho KB tier has these files at the root:

- `knowledge-base.md` — schema + operations (Karpathy's equivalent of `CLAUDE.md`)
- `rules.md` — kiho addition: durable enforceable rules
- `memos.md` — kiho addition: short-lived scratch area
- `index.md` — content catalog: every wiki page with one-line summary
- `log.md` — append-only chronological activity log

kiho adds 7 more derived indexes (tags, backlinks, timeline, stale, open-questions, graph, by-confidence, by-owner, skill-solutions) because its scale and multi-agent context benefit from query-shaped retrieval.

## Page types

Karpathy's suggestions, extended for kiho:

| Directory | Contents |
|---|---|
| `wiki/entities/` | People, organizations, services, tools, libraries, files, modules, vendors |
| `wiki/concepts/` | Ideas: patterns, glossary, invariants, principles |
| `wiki/sources/` | Per-source summaries (one per raw/ document; kiho largely subsumes this into entities/concepts) |
| `wiki/synthesis/` | Integrated analyses tying multiple pages together |
| `wiki/decisions/` | kiho addition: ADRs from committees |
| `wiki/conventions/` | kiho addition: project-specific rules |
| `wiki/questions/` | kiho addition: durable open questions |

One page per thing. Never mix multiple entities in one file.

## The ingest flow

When a new raw source arrives:

1. **Read the source.** LLM reads the raw file, identifies key takeaways, names, concepts, claims.
2. **Write the summary page.** Create `wiki/<type>/<slug>.md` with a concise summary, metadata, citations back to the raw source.
3. **Update affected pages.** Scan `index.md` for entities and concepts the new source touches. Read each affected page. Append a short addition referencing the new source.
4. **Update `index.md`.** Add the new summary page; refresh backlink counts on affected pages.
5. **Append `log.md`.** One entry: `## [<iso>] ingest | source="<path>" | touched=[...]`.

**A single source may touch 10-15 pages.** This is expected. The LLM's job is to spread the new information across every page that benefits from knowing about it.

## The query flow

When the LLM (or another agent via kb-manager) queries the wiki:

1. **Read `index.md` first.** Find candidate pages by type and tag.
2. **Drill into candidate pages.** Read full content of top-5 candidates.
3. **Synthesize an answer.** Combine what's on the candidate pages. Cite each claim with `[[page-name]]` or `[^source]` footnotes.
4. **File valuable answers back.** If the synthesized answer is durable (non-trivial, likely to be asked again), create a new `synthesis/<slug>.md` page summarizing the answer. This is how the wiki compounds.

Queries hit the compiled wiki. They do NOT re-read raw sources (except through page references).

## The lint flow

Periodically (kiho runs this at end of every ingest + start of every evolve):

1. **Orphan check.** Pages with zero incoming backlinks from index.md or other pages.
2. **Broken-link check.** `[[name]]` references that resolve to nothing.
3. **Stale-claim check.** Pages whose last verification is > threshold AND that are referenced by recent content.
4. **Contradiction check.** Two pages making opposing claims without a `CONTRADICTS:` callout.
5. **Missing type-page check.** A concept referenced 3+ times with no dedicated page.
6. **Index drift check.** Pages that exist but aren't in `index.md`, or index entries pointing at deleted pages.
7. **Raw leakage check.** Wiki pages citing `raw/` via wikilinks (should cite by prose, not by link).

Mechanical findings are fixed directly by the LLM. Judgment findings become open `questions/` pages.

## Cross-references

**Wikilinks** connect pages: `[[billing-webhook]]` resolves to `wiki/entities/billing-webhook.md`.

**Backlinks** are maintained in `backlinks.md` — for each page, the list of pages that link to it. kiho's kb-manager rebuilds this on every write.

**Key distinction from RAG**: cross-references are pre-computed at ingest time, not discovered at query time. This is Vannevar Bush's Memex idea (1945) applied to LLM-authored knowledge.

> "The connections between documents are as valuable as the documents themselves."

## Anti-patterns

Karpathy's explicit warnings:

- **Don't let the LLM write the wiki blindly.** "You're in charge of sourcing, exploration, and asking the right questions. The LLM does all the grunt work." Human oversight guides emphasis.
- **Don't treat the wiki as immutable.** The LLM continuously updates pages. Contradictions must be flagged, not silently overwritten.
- **Don't rely on embedding-based RAG alone.** "The index file works surprisingly well at moderate scale ... and avoids the need for embedding-based RAG infrastructure."
- **Don't attempt manual maintenance at scale.** "If humans must maintain cross-references, the system will be abandoned. Automate or fail."
- **Don't use Obsidian's plugin ecosystem as a crutch.** The point is plain-text markdown. Fancy tools add lock-in.
- **Don't assume the pattern is prescriptive.** "Everything mentioned above is optional and modular — pick what's useful, ignore what isn't."

## kiho-specific adaptations

kiho adopts the Karpathy pattern with these modifications:

**1. Renamed the schema file.** Karpathy calls it `CLAUDE.md`. kiho uses `knowledge-base.md` to avoid collision with Claude Code's plugin-level `CLAUDE.md` convention.

**2. Added `rules.md` and `memos.md`.** kiho separates durable enforceable rules from the schema doc, and adds a short-lived scratch area for operational TODOs.

**3. Sole-gateway writer.** kiho's `kiho-kb-manager` agent is the only agent that writes `wiki/`. Other agents submit requests through `kb-add`/`kb-update`/etc. Karpathy's gist assumes one user + one LLM; kiho has many agents, so one gateway enforces consistency.

**4. Rich multi-index set.** Karpathy has `index.md` + `log.md`. kiho adds 9 more derived indexes (tags, backlinks, timeline, stale, open-questions, graph, by-confidence, by-owner, skill-solutions) for query-shape diversity.

**5. Skill linkage.** kiho's `skill-solutions.md` index maps KB entries to skills that solve their problems. Karpathy's gist has no skill concept; kiho adds the linkage so newly-spawned skills are discoverable from the KB.

**6. Two tiers.** Project tier (in `.kiho/kb/`) + company tier (in `$COMPANY_ROOT/company/`). Karpathy's gist is single-tier.

## Source attribution

Karpathy, Andrej — https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Offline excerpt maintained in kiho-plugin for KB-manager reference.
