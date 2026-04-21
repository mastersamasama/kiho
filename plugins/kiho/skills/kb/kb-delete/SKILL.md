---
name: kb-delete
description: Use this skill when kb-manager needs to remove a wiki page. Defaults to soft-delete (set valid_until, drop from active indexes, keep file readable). Hard-delete requires explicit caller approval and should almost never be used — history preservation is the default. Only kb-manager should load this skill.
argument-hint: "tier=<t> page_path=<path> reason=<text>"
metadata:
  trust-tier: T2
  kiho:
    capability: delete
    topic_tags: [curation, lifecycle]
    data_classes: ["kb-wiki-articles"]
---
# kb-delete

Remove a wiki page from active use. Default: soft-delete (preserves file + history). Hard-delete only on explicit CEO + user approval.

## Inputs

```
TIER: project | company
PAYLOAD:
  page_path: <relative path>
  reason: <one-line explanation>
  hard_delete: <bool, default false>
  superseded_by: <new-page-id, optional — if this delete is part of a supersede chain>
  author_agent: <agent-id>
REQUEST_ID: <uuid>
```

## Soft-delete procedure (default)

1. **Read the existing page.** If missing, return `status: noop` with `already_absent`.
2. **Stage update in `drafts/<REQUEST_ID>/<page_path>`:**
   - Set frontmatter `valid_until: <now>`
   - Set `status: deprecated`
   - If `superseded_by` was provided, set it in frontmatter
   - Leave body unchanged
3. **Remove from active indexes** in drafts/:
   - `index.md` — remove from "currently valid" listings
   - `timeline.md` — remove
   - `by-confidence.md` — remove
   - `by-owner.md` — remove
   - `tags.md` — remove from each tag's list
   - `skill-solutions.md` — if this page had skill pointers, move them to "deprecated" section
   - `open-questions.md` — if page_type was `question`, remove
4. **Preserve in history indexes:**
   - `log.md` — append delete event (see below)
   - `backlinks.md` — leave existing back-edges (so callers can see "this is why X references a deprecated page")
5. **Scan back-linkers.** For every page that references this one, stage an update adding a note: `> [!note] This page references [[<deleted-page>]] which was deprecated on <iso>.` (The note is advisory; we don't automatically rewrite back-linker content.)
6. **Atomic move** drafts into place.
7. **Append `log.md`:**
   ```markdown
   ## [<iso>] delete | by=kiho-kb-manager | req=<REQUEST_ID>
   Page: <page_path>
   Mode: soft
   Reason: <reason>
   Superseded_by: <id-or-null>
   ```
8. **Return the receipt.**

## Hard-delete procedure (requires explicit approval)

Hard-delete physically removes the file and all references. Only allowed when:

- `hard_delete: true` in payload
- Caller has CEO + user pre-approval (CEO verifies user answered "yes" in AskUserQuestion)
- The page was created in error (typo in title, duplicate accidentally created)

Procedure:
1. Stage deletion via `Bash rm` of the file in drafts/ (actually: unlink the file entirely, not just soft-delete).
2. Remove from ALL indexes including backlinks and log.md history references to it.
3. Atomic move.
4. Append `log.md` with `Mode: hard, Reason: <reason>, Approved_by: <user>`.

Do NOT hard-delete without explicit `hard_delete: true`. If the caller forgot to set it, default to soft-delete and include a note: `"soft-deleted. Pass hard_delete=true to physically remove."`

## Response shapes

**Soft-delete success:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: delete
STATUS: ok
MODE: soft
TOUCHED_FILES:
  - <page_path> (edit — valid_until set, status: deprecated)
  - index.md (edit)
  - ... active indexes
  - log.md (append)
```

**Already absent:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: delete
STATUS: noop
REASON: page_not_found
```

**Hard-delete success:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: delete
STATUS: ok
MODE: hard
TOUCHED_FILES:
  - <page_path> (deleted)
  - ... all references cleaned
  - log.md (append)
```

## Anti-patterns

- Default to soft-delete. Hard-delete is for error correction only.
- Never hard-delete without the `hard_delete: true` flag and explicit CEO+user approval.
- Never delete a page that has back-linkers without at minimum noting the references as deprecated.
- Never delete `raw/` files. Raw is append-only.
- Never delete `knowledge-base.md`, `rules.md`, `memos.md`, or any index file. These are structural.
