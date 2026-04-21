---
name: kb-add
description: Use this skill when kb-manager needs to add a new page to the wiki (entities/concepts/decisions/conventions/synthesis/questions/principles/rubrics). Runs the full conflict/duplicate/deprecation decision tree before writing. Detects contradictions with existing pages and opens questions/ pages when ambiguity requires human resolution. Updates all affected indexes and the skill-solutions.md back-references. Only kb-manager should load this skill.
argument-hint: "tier=<t> page_type=<t> title=<text> content=<md>"
metadata:
  trust-tier: T2
  kiho:
    capability: create
    topic_tags: [ingestion]
    data_classes: ["kb-wiki-articles"]
---
# kb-add

The centerpiece of kiho's knowledge-base write path. Runs a strict decision tree before any write: duplicate detection, contradiction detection, deprecation detection, rule enforcement. Only after all checks pass does the new page land in `wiki/`.

## Contents
- [Inputs](#inputs)
- [Procedure](#procedure)
- [Decision tree](#decision-tree)
- [Rule enforcement](#rule-enforcement)
- [Affected-page propagation](#affected-page-propagation)
- [Response shapes](#response-shapes)

## Inputs

```
TIER: project | company
PAYLOAD:
  page_type: entity | concept | decision | convention | synthesis | question | principle | rubric
  title: <string>
  content: <full markdown body>
  tags: [kebab-case strings]
  sources: [<url-or-path>]
  confidence: <0..1>
  provenance: [{kind, ref}]
  affected_entities: [<entity-name>]    # hints from caller
  affected_concepts: [<concept-name>]   # hints from caller
  skill_solutions: [<skill-id>]         # if this page is being added to register a skill
  author_agent: <agent-id>
REQUEST_ID: <uuid>
```

All fields except `title`, `content`, `page_type` are optional; kb-manager fills in defaults.

## Procedure

1. **Read `rules.md`** for the tier. Validate the incoming payload against every rule (see [Rule enforcement](#rule-enforcement)).
2. **Search for duplicates** — dedupe check against existing pages of the same type (see [Decision tree](#decision-tree)).
3. **Generate a page ID** from the title: `<type>-<slug>` for most types, `ADR-NNNN-<slug>` for decisions (auto-increment N based on highest existing ADR number).
4. **Draft the new page** in `drafts/<REQUEST_ID>/wiki/<type>/<id>.md` with full frontmatter:
   ```yaml
   ---
   id: <page-id>
   type: <page_type>
   title: <title>
   tags: <tags>
   author_agent: <author_agent>
   created_at: <iso>
   updated_at: <iso>
   valid_from: <iso>
   valid_until: null
   last_verified: <iso>
   confidence: <confidence>
   status: active
   provenance: <provenance>
   skill_solutions: <skill_solutions>
   superseded_by: null
   supersedes: null
   ---
   ```
5. **Walk affected pages** — for every entity/concept in `affected_entities` + `affected_concepts`, stage an update in `drafts/<REQUEST_ID>/wiki/<type>/<affected>.md` that adds a wikilink back to the new page.
6. **Rebuild affected indexes** in `drafts/<REQUEST_ID>/`:
   - `index.md` — add new entry to the right section
   - `tags.md` — add new page to each of its tags' page lists
   - `backlinks.md` — add new reverse edges for every wikilink the new page contains
   - `timeline.md` — insert new page sorted by `updated_at`
   - `by-confidence.md` — insert sorted by `confidence` asc
   - `by-owner.md` — append under `author_agent` group
   - `skill-solutions.md` — if `skill_solutions` is non-empty, add entries under each affected entity/concept section
   - `open-questions.md` — if page_type is `question`, add to the list
7. **Run dry-lint** — call the `kb-lint` sub-skill on the union of `drafts/` + existing `wiki/`. If lint fails, abort with `status: error`.
8. **Atomic move** — move every file in `drafts/<REQUEST_ID>/` to its target in `wiki/` and the tier root (for indexes). Use `Bash mv` where possible.
9. **Append `log.md`** with a receipt entry:
   ```markdown
   ## [<iso>] add | by=kiho-kb-manager | req=<REQUEST_ID>
   Type: <page_type>
   ID: <page-id>
   Touched: [<list of affected pages>]
   Contradictions: [<list>]
   ```
10. **Return the receipt.**

## Decision tree

Run BEFORE drafting the new page:

```
1. Fuzzy match incoming (title + top 3 tags) against existing pages in
   <tier>/wiki/<page_type>/. Use a lexical score (word overlap + title similarity).

2. For each match with score > 0.85:
     a. Load the existing page.
     b. Compare content semantically (LLM-based: is incoming a superset?
        subset? contradiction? unrelated restatement?).

     RESULT paths:
       - SUBSUMED: existing covers everything incoming says → NOOP, log "subsumed", return status: noop
       - SUPERSET: incoming covers existing plus more → switch to kb-update on the existing page (call kb-update sub-skill); do NOT create a new page
       - CONTRADICTS: incoming claims the opposite of existing → CONFLICT path
       - RESTATES: same claim, different words → NOOP with a note in log.md
       - UNRELATED: false positive from fuzzy match → continue to next match

3. CONFLICT path:
     a. Stage a contradiction callout on both pages in drafts/:
        > [!warning] CONTRADICTS [[other-page]]
        > (one-line summary of disagreement)
     b. Create a new questions/Q-<slug>.md page in drafts/ listing both claims,
        their provenance, and "awaiting resolution".
     c. Do NOT create the incoming page. Return status: conflict with
        CONTRADICTION_RAISED set to the question page path.

4. DEPRECATION path (triggered by explicit deprecation signal in payload —
   e.g., content says "X has been replaced by Y", or caller sets deprecate_target):
     a. Set existing page's valid_until = now in drafts/
     b. Set existing page's superseded_by = <new-id>
     c. Remove existing from active index entries in drafts/
     d. Continue to create the incoming page as new
     e. Add DEPRECATIONS field to the receipt

5. If no match > 0.85 after all: CREATE — proceed with the draft as a new page.
```

## Rule enforcement

Before any write, enforce every rule in `rules.md`:

**Project tier rules** (must-follow):
1. Decisions must cite ≥1 source from `raw/` — if `provenance` is empty for `page_type=decision`, reject.
2. Entity pages must have `status` in frontmatter — kb-add sets it to `active` automatically.
3. Concept pages must define exactly one idea — if the content has multiple distinct definitions, reject with `rule_violation: concepts-must-be-single`.
4. Conventions conflicting with company KB must be marked `local_override: true` — if kb-search against company tier finds a contradicting convention and payload doesn't set `local_override`, reject.
5. Questions must reference ≥2 pages they relate to — parse `content` for `[[wikilinks]]`; if fewer than 2 found for `page_type=question`, reject.
6. Pages with `confidence < 0.60` must link to a questions/ page — if `confidence < 0.60` and no `uncertainty_link` in frontmatter, either auto-create a questions/ page or reject with rule_violation.
7. Titles must be < 80 chars — if longer, reject.
8. Page IDs follow pattern `<type>-<slug>` or `ADR-NNNN-<slug>` — kb-add generates these; no user override.

**Company tier rules** (stricter):
1. No project-specific file paths — regex-scan `content` for `src/`, `/apps/`, `C:/`, `D:/`. If found, reject.
2. No project-specific proper nouns — match against kb-manager's "project-bound names" allowlist. If found, reject with rule_violation: proper-noun-leak.
3. Rubric pages require committee-approved provenance.
4. Principle pages require `user_approved: true` — if missing, reject with rule_violation: principle-needs-user-approval.
5. Entity pages are generic — content starting with "our X" is rejected.
6. Confidence ≥ 0.80 for new ACTIVE pages — if lower, either downgrade to DRAFT or reject.

On any rule violation, return immediately with:
```
status: error
error_message: rule <N> in rules.md violated: <specific detail>
error_location: kb-add rule enforcement
```

## Affected-page propagation

When the new page mentions other entities/concepts (via `affected_*` hints or parsed wikilinks in `content`), kb-add updates every affected page:

- Add a short "see also" bullet pointing to the new page
- Update the affected page's `updated_at` to now
- If the affected page has `skill_solutions` and the new page is a skill registration, add the skill-id to `skill_solutions`
- Stage the update in `drafts/<REQUEST_ID>/` alongside the new page

This is how a single ingest "touches 10-15 pages" per the Karpathy wiki protocol.

## Response shapes

**Success (CREATE):**
```markdown
## Receipt <REQUEST_ID>
OPERATION: add
TIER: <tier>
STATUS: ok
TOUCHED_FILES:
  - wiki/<type>/<id>.md (new)
  - wiki/entities/<affected-1>.md (edit)
  - wiki/concepts/<affected-2>.md (edit)
  - index.md (edit)
  - tags.md (edit)
  - backlinks.md (edit)
  - timeline.md (edit)
  - by-confidence.md (edit)
  - by-owner.md (edit)
  - skill-solutions.md (edit)
  - log.md (append)
NEW_QUESTIONS: []
DEPRECATIONS: []
CONTRADICTION_RAISED: null
CONFIDENCE: <confidence>
```

**NOOP (subsumed):**
```markdown
## Receipt <REQUEST_ID>
OPERATION: add
STATUS: noop
REASON: subsumed_by_<existing-page-id>
```

**CONFLICT:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: add
STATUS: conflict
CONTRADICTION_RAISED: wiki/questions/Q-<slug>.md
TOUCHED_FILES:
  - wiki/<type>/<existing-page>.md (edit — CONTRADICTS callout)
  - wiki/questions/Q-<slug>.md (new)
  - open-questions.md (edit)
  - log.md (append)
NOTE: Incoming page NOT created. Resolve the question first, then retry.
```

**DEPRECATE + CREATE:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: add
STATUS: ok
DEPRECATIONS: [wiki/<type>/<old-page>.md]
TOUCHED_FILES:
  - wiki/<type>/<new-page>.md (new)
  - wiki/<type>/<old-page>.md (edit — valid_until set)
  - ... indexes
  - log.md (append)
```

## Anti-patterns

- Never skip the decision tree. Even if the caller says "this is definitely new", run the dedupe check.
- Never write directly to `wiki/`. Always stage in `drafts/` first.
- Never mutate the incoming payload. If rule enforcement needs changes, reject and ask the caller to fix.
- Never create a page with empty `sources` unless `page_type` is `synthesis` or `memo`. Everything else needs provenance.
- Never silently resolve a contradiction. Opening a questions/ page is the only correct move.
