---
name: kb-ingest-raw
description: Use this skill when kb-manager needs to process a raw source document into wiki updates following the Karpathy llm-wiki ingest protocol. A single raw source (committee transcript, pasted doc, research output, imported playbook) typically touches 10-15 wiki pages — a new summary page plus additions to affected entities, concepts, and decisions. The raw file itself stays append-only under raw/; this skill only produces wiki updates that cite back to raw. Only kb-manager should load this skill.
argument-hint: "tier=<t> raw_path=<path>"
metadata:
  trust-tier: T2
  kiho:
    capability: create
    topic_tags: [ingestion]
    data_classes: ["kb-wiki-articles", "kb-drafts"]
---
# kb-ingest-raw

Process a raw source into wiki updates via the Karpathy ingest flow. Appends nothing to raw (raw is the source of truth); only writes wiki/ and indexes.

## Inputs

```
PAYLOAD:
  raw_path: <path under raw/ — must already exist>
  page_type_hint: <type for the primary summary page>
  affected_entities: [<entity-name>]     # hints
  affected_concepts: [<concept-name>]    # hints
  author_agent: <agent-id>
REQUEST_ID: <uuid>
```

## Procedure (Karpathy ingest flow)

### 1. Read the raw source

Read the file at `<raw_path>` in full. It may be a committee transcript (markdown with agent messages), a pasted doc (free-form markdown), an imported playbook (structured reference), or research output from the `research` skill.

### 2. Extract structure

Identify in the raw content:
- **Key entities mentioned** — services, libraries, vendors, people
- **Key concepts discussed** — patterns, principles, invariants
- **Claims made** — factual statements that could become wiki content
- **Decisions taken** — if the raw is a committee transcript, extract the decision
- **Questions raised** — if the raw contains unresolved debate

### 3. Draft the primary summary page

Create a summary page in `drafts/<REQUEST_ID>/wiki/<page_type_hint>/<slug>.md`:
- Title: distilled from the raw source's main topic
- Body: 3-5 paragraph summary of the source's key claims
- Frontmatter: `confidence`, `tags`, `provenance: [{kind: 'raw_source', ref: '<raw_path>'}]`, `author_agent`
- Citations: every claim in the body cites back to the raw source by prose (NOT via wikilink — raw leakage rule)

### 4. Walk affected pages

For each entity in `affected_entities` (plus any additional entities detected in step 2):
- Read the existing entity page (if any) via `<TIER_ROOT>/wiki/entities/<name>.md`
- If missing: create a new stub entity page in drafts/ with `stub: true` frontmatter and a short definition drawn from the raw source
- If existing: stage an append to the page: a short paragraph referencing the new summary page and any new claims the raw adds about this entity

For each concept in `affected_concepts` (plus detected): same procedure.

For any decisions detected (if raw is a committee transcript): create an ADR page in `drafts/<REQUEST_ID>/wiki/decisions/ADR-NNNN-<slug>.md`. Use the Clerk decision extraction format.

For any open questions detected: create a `wiki/questions/Q-<slug>.md` with the unresolved question and `status: open`.

**A single ingest typically touches 10-15 pages** — the summary plus 5-10 affected entity/concept pages plus 0-2 decisions plus 0-3 questions.

### 5. Update derived indexes

In drafts/<REQUEST_ID>/, rebuild affected entries in:
- `index.md` — add all new pages
- `tags.md` — add new pages under each tag
- `backlinks.md` — rebuild all new wikilink reverse edges
- `timeline.md` — add all new pages at the top
- `by-confidence.md` — insert sorted
- `by-owner.md` — append under `author_agent` group
- `open-questions.md` — add any new question pages
- `skill-solutions.md` — if the raw referenced any existing skills, add linkage entries

### 6. Run dry-lint

Call kb-lint on the union of drafts/ + existing wiki/. If the lint finds contradictions (very common on ingest), either:
- Auto-resolve by opening questions/ pages (if the contradiction is structural)
- Or abort with `status: partial` and leave the drafts/ in place for the caller to resolve

### 7. Atomic move

Move all drafts into wiki/ and index files.

### 8. Append log.md

```markdown
## [<iso>] ingest-raw | by=kiho-kb-manager | req=<REQUEST_ID>
Source: <raw_path>
Summary: <primary page path>
Touched: [<list of all affected wiki pages>]
New questions: [<list>]
Contradictions flagged: [<list>]
```

### 9. Return receipt

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: ingest-raw
TIER: <tier>
STATUS: ok | partial
RAW_SOURCE: <raw_path>
PRIMARY_PAGE: wiki/<type>/<slug>.md (new)
TOUCHED_FILES:
  - wiki/<type>/<slug>.md (new — summary)
  - wiki/entities/<affected-1>.md (edit)
  - wiki/entities/<affected-2>.md (edit)
  - wiki/concepts/<affected-3>.md (edit)
  - wiki/decisions/ADR-NNNN-<decision-slug>.md (new)
  - wiki/questions/Q-<open-q>.md (new)
  - index.md (edit)
  - tags.md (edit)
  - backlinks.md (edit)
  - timeline.md (edit)
  - by-confidence.md (edit)
  - by-owner.md (edit)
  - open-questions.md (edit)
  - log.md (append)
NEW_QUESTIONS: [<q-page-paths>]
CONTRADICTIONS_FLAGGED: []
PAGES_AFFECTED_COUNT: 12
```

## Karpathy ingest principles (invariants)

- **One source touches many pages.** If your ingest only produces 1-2 pages, you missed affected entities/concepts. Re-scan.
- **Cite raw by prose, never by wikilink.** `(see raw/sources/postmortem.md)` NOT `[[raw:sources/postmortem]]`.
- **Never edit raw/.** Raw is append-only. If you need to correct a raw source, add a new raw file with the correction and let the wiki pages reference both.
- **Preserve conflicts.** If the raw source contradicts existing wiki content, don't silently pick a side. Open a question.
- **Don't fabricate affected pages.** If you're not sure whether an entity is mentioned, don't invent the link. Leave it for the next ingest that actually touches that entity.

## Anti-patterns

- Don't call kb-ingest-raw on content that's already in `wiki/`. That's what kb-update is for.
- Don't ingest the same raw file twice. kb-lint will catch duplicate ingests via index drift, but the better practice is for the caller to check before calling.
- Don't skip the dry-lint step. Multi-file ingests are where lint most often catches issues.
- Don't write to raw/ through this skill. Raw ingestion (adding to raw/) happens outside kb-manager — the caller places the file there before invoking kb-ingest-raw.
