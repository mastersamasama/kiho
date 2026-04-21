# Project knowledge base — {{project_name}}

This file describes the project knowledge base for **{{project_name}}**. It is read by kb-manager and every agent before interacting with the KB.

It is NOT the place to put facts — those live in `wiki/`. This is the **schema and operations doc** for how the KB works in this project.

## 1. Scope

This KB captures knowledge **specific to this codebase**: services, modules, APIs, vendors, decisions made by committees, conventions that apply only here, and open questions that haven't been resolved yet.

For knowledge that applies across projects (reusable patterns, user principles, approved rubrics, portable skills), see the **company KB** at the path configured in `kiho-plugin/skills/core/harness/kiho/config.toml` under `company_root`.

**Never mix tiers.** A file path in this codebase, a module name, a project-specific vendor integration — all of that stays project-tier. Anything that mentions `src/`, `<this-repo>/`, or a proper noun tied to this project does not travel.

## 2. Page type catalog

Every file under `wiki/` belongs to exactly one of these types. The type is determined by the directory the file lives in.

| Type | Directory | Use when |
|---|---|---|
| **Entity** | `wiki/entities/` | Describing a concrete thing with an identity: a service, a module, a file, an API, a vendor, a person, a customer |
| **Concept** | `wiki/concepts/` | Describing a reusable idea, pattern, invariant, or glossary term that appears across multiple entities |
| **Decision** | `wiki/decisions/` | An ADR page. One per committee-approved architectural call. Committee outputs land here via the Clerk pipeline |
| **Convention** | `wiki/conventions/` | A project-specific rule of the road: naming, layout, test placement, review protocol |
| **Synthesis** | `wiki/synthesis/` | A cross-cutting analysis that ties multiple entities/concepts/decisions into a narrative: roadmaps, retros, tech radar entries |
| **Question** | `wiki/questions/` | A durable open question. Opened by ingest when a gap or contradiction is detected. Closed by linking to a `decisions/` page that resolves it |

## 3. Write protocol

**Only the `kiho-kb-manager` agent may write to `wiki/`.** No other agent — not CEO, not committee members, not engineering-kiro — writes directly. Writes happen exclusively through kb-manager's sub-skills:

- `kb-add` — create a new page (runs conflict/dedup/deprecation detection first)
- `kb-update` — mutate an existing page atomically via `drafts/`
- `kb-delete` — soft-delete (set `valid_until`; never hard-delete without explicit CEO+user approval)
- `kb-ingest-raw` — process a raw source into wiki updates (Karpathy ingest: one source touches 10-15 files)

To request a write, an agent spawns `kiho-kb-manager` via the Agent tool with a structured request:

```
TIER: project
OPERATION: add
PAYLOAD:
  page_type: decision
  title: ...
  content: ...
  tags: [...]
  sources: [...]
  confidence: 0.92
  affected_entities: [...]
  affected_concepts: [...]
REQUEST_ID: <uuid>
```

kb-manager returns a structured receipt listing every touched file.

**Before any write, kb-manager reads `rules.md`.** Any rule violation causes kb-manager to reject the write with a structured error; the requesting agent must revise and retry, or escalate to CEO.

## 4. Read protocol

Two paths:

- **Fast direct reads** — any agent may Read or Grep files in `wiki/` directly for speed. This is allowed for simple lookups. Indexes (`index.md`, `tags.md`, etc.) are designed to make this fast.
- **Curated search** — for cross-referenced, synthesized, or confidence-scored answers, invoke `kb-search` via kb-manager. It reads the index cascade, loads candidate pages, and returns a cited markdown answer with linked skills (via `skill-solutions.md`).

When in doubt, prefer `kb-search`. It surfaces contradictions, freshness, and linked skills that direct reads miss.

## 5. Wikilinks and backlinks

Cross-references use Obsidian-style wikilinks:

```markdown
The [[billing-webhook]] service handles Stripe inbound events and must follow
the [[idempotency-keys]] convention.
```

- Links are relative to `wiki/` regardless of which sub-directory the linking page lives in.
- Target names are file basenames without extension. kb-manager resolves `[[billing-webhook]]` to `wiki/entities/billing-webhook.md` via the index.
- Backlinks are auto-maintained in `backlinks.md` (rebuilt on every write by kb-manager).
- If a wikilink resolves to nothing, `kb-lint` flags it as broken and kb-manager opens a `questions/` page OR a stub `entities/` page depending on context.

## 6. Contradiction rule

**Never silently overwrite a fact.** When a new write contradicts an existing page:

1. kb-manager flags the contradiction in both pages with a callout:
   ```markdown
   > [!warning] CONTRADICTS [[other-page]]
   > (one-line summary of the disagreement)
   ```
2. kb-manager opens a `questions/Q-<slug>.md` page listing both claims with evidence.
3. The requesting agent's receipt has `CONTRADICTION_RAISED: <question-path>`.
4. CEO sees the flag and may convene a resolution committee (not kb-manager's job to decide).
5. Neither original page is modified by the contradiction event itself — both stay readable.

Deprecation is different: if the new content says "X is no longer true because Y supersedes it", kb-manager sets the old page's `valid_until = now`, adds `superseded_by: <new-id>`, writes the new page, and drops the old from active indexes (still readable, just hidden from default search).

## 7. Index set (12 files)

All index files at the KB root are **derived** from `wiki/` frontmatter. kb-manager rebuilds them after every write. Never hand-edit.

| Index | Purpose |
|---|---|
| `index.md` | Master catalog: every page grouped by type, most-recently-updated first per group |
| `log.md` | Chronological append-only activity log (`## [iso] operation \| by=agent`) |
| `tags.md` | Tag cloud: tag → page list |
| `backlinks.md` | Reverse graph: page → pages that link to it, with anchor snippets |
| `timeline.md` | All pages sorted desc by `updated_at` |
| `stale.md` | Pages with `last_verified > 90d` that are referenced by recent content |
| `open-questions.md` | Flat list of `questions/` pages still open |
| `graph.md` | Adjacency listing for topology traversal |
| `by-confidence.md` | Pages sorted ascending by confidence (surfaces uncertain claims) |
| `by-owner.md` | Pages grouped by `author_agent` |
| `skill-solutions.md` | Problem/entity/concept → skills that solve it (the skill-linkage index) |

The company tier has all of these PLUS `cross-project.md` tracking which company entries originated from which projects.

## 8. Skill linkage

Every entity/concept/question page can carry a `skill_solutions` frontmatter field listing skill IDs that help solve problems described on that page:

```yaml
---
id: ent-billing-webhook
skill_solutions: [sk_stripe_webhook_validator_v1, sk_idempotency_middleware_v2]
---
```

`skill-solutions.md` at the KB root aggregates these links by entity, concept, and open question for fast agent lookup. When a new skill is spawned (FIX/DERIVED/CAPTURED), the spawning skill MUST immediately call `kb-add` to register the new skill and update the relevant pages' `skill_solutions` fields. This is the mechanism that makes newly-created skills discoverable company-wide in the same session they're born.

## 9. Immutability

- **`raw/` is append-only.** kb-manager never edits files under `raw/`. Raw sources (committee transcripts, pasted docs, research notes) are ground truth and must survive unchanged.
- `wiki/` pages are editable (by kb-manager) but never lose history — old versions live in the git commit log or in `drafts/` after atomic moves.
- `index.md` and other derived indexes are fully regenerable; if deleted, kb-manager rebuilds them on the next operation.

## 10. When the KB looks empty

On a fresh project the KB only has this file, `rules.md`, `memos.md`, and empty indexes. That's fine. The `/kiho kb-init` skill (called by the CEO on the first real task or explicitly via `/kiho kb-init`) seeds the KB by recruiting a research team, reading the project's PRD or codebase, and ingesting initial entities/concepts/conventions. From that point forward, every committee decision and every session's discoveries flow into the KB through kb-manager.

## 11. When the company tier matters

Project-tier knowledge belongs here. But when a lesson is portable — when the same insight would apply on a totally different codebase — any agent may request promotion via `kb-promote`. kb-manager sanitizes the page (strips repo paths, proper nouns) and copies it to the company tier. The original stays here with a `> PROMOTED_TO: <company-path>` callout.

Promotion is explicit, not automatic. CEO or any dept leader may request it.
