---
name: kb-update
description: Use this skill when kb-manager needs to mutate an existing wiki page — correcting a fact, adding new evidence, amending a decision after follow-up, or applying a lint-identified fix. Writes atomically via drafts/ and rebuilds all affected indexes. Preserves history through updated_at timestamps and supersede chains. Only kb-manager should load this skill.
argument-hint: "tier=<t> page_path=<path> patch=<md>"
metadata:
  trust-tier: T2
  kiho:
    capability: update
    topic_tags: [curation]
    data_classes: ["kb-wiki-articles"]
---
# kb-update

Atomic update to an existing wiki page. Used for corrections, enrichments, lint fixes, and post-committee amendments.

## Inputs

```
TIER: project | company
PAYLOAD:
  page_path: <relative path from tier root, e.g., wiki/entities/auth-service.md>
  patch: <markdown describing the change — either a replacement body or a diff>
  patch_mode: replace | append | edit_section | frontmatter_only
  reason: <one-line explanation for log.md>
  new_confidence: <0..1>              # optional, overrides existing
  new_last_verified: <iso>            # optional, defaults to now
  author_agent: <agent-id>
REQUEST_ID: <uuid>
```

## Procedure

1. **Read the existing page** at `<TIER_ROOT>/<page_path>`. If missing, return `status: error` with `error_message: page_not_found`.
2. **Read `rules.md`** and validate that the proposed update doesn't violate any rule (same checks as kb-add).
3. **Stage the update** in `drafts/<REQUEST_ID>/<page_path>`:
   - `replace` — write the new body verbatim, preserve existing frontmatter except for updated fields
   - `append` — add the patch at the end of the existing body
   - `edit_section` — find the section header in the patch and replace just that section
   - `frontmatter_only` — modify only YAML frontmatter fields (no body change)
4. **Update frontmatter fields:**
   - `updated_at: <now>`
   - `last_verified: <new_last_verified or now>`
   - `confidence: <new_confidence if provided>`
   - If the patch substantially changes the page's claims, bump an internal version counter (track in frontmatter as `revision: <N>`).
5. **Check for cascading contradictions.** Parse the updated page's claims. Run a quick kb-search across pages that back-link to this one (via `backlinks.md`). If the update would contradict any back-linker, stage CONTRADICTS callouts and open a questions/ page. Return `status: partial` with `CONTRADICTION_RAISED` set if the contradiction is material.
6. **Update derived indexes** that reference this page:
   - `index.md` — re-sort the page's section by updated_at
   - `timeline.md` — move this page to the top
   - `by-confidence.md` — re-sort if confidence changed
   - `tags.md` — if tags changed, re-index
   - `stale.md` — remove this page if it was listed (updated_at resets stale-ness)
   - `skill-solutions.md` — if `skill_solutions` changed, update mappings
7. **Run dry-lint** on staged drafts + existing wiki. Abort if lint fails.
8. **Atomic move** drafts into place.
9. **Append `log.md`:**
   ```markdown
   ## [<iso>] update | by=kiho-kb-manager | req=<REQUEST_ID>
   Page: <page_path>
   Reason: <reason>
   Mode: <patch_mode>
   ```
10. **Return the receipt.**

## Preserving history

kb-update does NOT destroy the old content. Two mechanisms:

- **Bump `revision` in frontmatter** — lets downstream tooling see that the page has been amended
- **If the change is substantial** (new claim contradicts an old claim the page made), use `kb-delete` to soft-delete the old page and `kb-add` the new version with `supersedes: <old-id>`. This preserves both pages.

The rule of thumb: minor corrections and clarifications are `update`. Material changes to the page's central claim are `delete + add`.

## Response shapes

**Success:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: update
STATUS: ok
TOUCHED_FILES:
  - <page_path> (edit)
  - index.md (edit)
  - timeline.md (edit)
  - ... other affected indexes
  - log.md (append)
```

**Cascading contradiction:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: update
STATUS: partial
TOUCHED_FILES:
  - <page_path> (edit)
  - wiki/entities/<affected-backlinker>.md (edit — CONTRADICTS callout)
  - wiki/questions/Q-<slug>.md (new)
  - ... indexes
CONTRADICTION_RAISED: wiki/questions/Q-<slug>.md
NOTE: Update applied, but back-linking pages now show contradictions.
```

**Error:**
```markdown
## Receipt <REQUEST_ID>
STATUS: error
ERROR_MESSAGE: <specific>
ERROR_LOCATION: kb-update step N
```

## Anti-patterns

- Never update a page's `id` field. IDs are immutable; use kb-delete + kb-add for renames.
- Never update `raw/` files. Raw sources are append-only.
- Never use `replace` mode without reading the existing content first. Blind replacement erases history.
- Never skip the cascading-contradiction check. It's what prevents silent KB drift.
