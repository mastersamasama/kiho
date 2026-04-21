---
name: kb-promote
description: Use this skill when an agent believes a project-tier KB page is portable enough to belong in the company-tier KB. Sanitizes project-specific references (file paths, proper nouns, code snippets tied to this repo), then copies the sanitized page to the company tier and annotates the project page with a promotion callout. Never moves — always copies. Only kb-manager should load this skill.
argument-hint: "project_page_path=<path> justification=<text>"
metadata:
  trust-tier: T2
  kiho:
    capability: update
    topic_tags: [curation, lifecycle]
    data_classes: ["kb-wiki-articles", "cross-project-lessons"]
---
# kb-promote

Copy a sanitized project-tier page to the company tier. Promotion is explicit and never automatic.

## Inputs

```
PAYLOAD:
  project_page_path: <relative path from .kiho/kb/>
  justification: <why this should be portable>
  target_type: entity | concept | principle | ... (optional — default: same as source)
  rename_to: <new page id> (optional — kb-promote auto-sanitizes names)
  author_agent: <agent-id>
REQUEST_ID: <uuid>
```

## Procedure

1. **Read the project page.** If missing, return `status: error`.
2. **Run sanitization checks:**
   - Scan `content` for project-specific file paths (`src/`, `C:/`, `D:/`, `./apps/`, etc.)
   - Scan for proper nouns bound to this project (kb-manager maintains a "project-bound names" allowlist — e.g., the project's own service names, customer names, internal module names)
   - Scan for `[[wikilinks]]` that reference project-specific entities with no company-tier equivalent
3. **If sanitization fails**, return `status: error` with `sanitization_failures: [...]`. The caller (or committee) must decide whether to rewrite the page for portability or abandon the promotion.
4. **Draft the sanitized copy** in `drafts/<REQUEST_ID>/`:
   - Remove or generalize any project-specific paths (`src/auth/service.ts` → "the authentication service")
   - Remove or generalize proper nouns (`BigCorp` → "the enterprise customer")
   - Rewrite project-specific wikilinks to company-tier equivalents where possible, or drop them
   - Generate a new page ID for the company tier (`company_<type>-<slug>`)
   - Add frontmatter:
     ```yaml
     promoted_from: <project_slug>/<project_page_path>
     promoted_at: <iso>
     promoted_by: <author_agent>
     confidence: <inherited from source page, or 0.85 if source was higher>
     provenance: [{kind: 'promotion', ref: '<project_page_path>'}]
     ```
5. **Call `kb-add`** on the company tier with the sanitized content. The sanitized page goes through the full kb-add decision tree at the company tier (may trigger conflicts or dedupe against existing company pages).
6. **Annotate the project page** by adding a callout at the top:
   ```markdown
   > [!info] PROMOTED_TO: company_<type>-<slug>
   > This page was promoted to the company tier on <iso>. See `<company-tier-path>`.
   ```
7. **Append `cross-project.md`** (company tier only) with the provenance:
   ```markdown
   ## company_<type>-<slug>
   - promoted_from: <project_slug>/<project_page_path>
   - promoted_at: <iso>
   - justification: <text>
   ```
8. **Append `log.md`** on BOTH tiers with the promotion event.
9. **Return the receipt.**

## Sanitization rules

Hard rejects (return `sanitization_failures`):
- Any absolute path matching `^[A-Z]:/` or `^/(home|Users|tmp)`
- Any file path with a slash followed by lowercase code-like segments (`src/`, `apps/`, `packages/`)
- Any string in the project-bound names allowlist
- Any `[[wikilink]]` whose target is a project-tier entity without a company-tier equivalent

Soft flags (warn but allow):
- Generic framework mentions (Next.js, React, Postgres) — these are portable
- Standard protocol names (OAuth, JWT, HTTPS) — portable
- Open-source tool names (git, docker, kubectl) — portable

## Response shapes

**Success:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: promote
STATUS: ok
PROJECT_PAGE: <project_page_path> (annotated with PROMOTED_TO callout)
COMPANY_PAGE: wiki/<type>/company_<slug>.md (new)
SANITIZATION_CHANGES:
  - removed: "src/auth/service.ts" → "the authentication service"
  - removed: "BigCorp" → "the enterprise customer"
  - dropped wikilink: [[acme-auth]] (no company-tier equivalent)
CROSS_PROJECT_UPDATED: true
```

**Sanitization failure:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: promote
STATUS: error
SANITIZATION_FAILURES:
  - line 12: absolute path "C:/Users/wky/project/foo.ts"
  - line 18: project-bound name "BigCorp Payment Gateway"
  - line 24: wikilink [[acme-auth]] has no company-tier equivalent
NOTE: Revise the project page for portability, then retry.
```

**Conflict at company tier:**
```markdown
## Receipt <REQUEST_ID>
OPERATION: promote
STATUS: conflict
SANITIZED_CONTENT_STAGED: drafts/<REQUEST_ID>/company_<slug>.md
COMPANY_TIER_CONFLICT:
  existing_page: <path>
  conflict_type: contradicts | subsumed | restates
QUESTION_OPENED: wiki/questions/Q-<slug>.md (on company tier)
```

## Anti-patterns

- Never move the project page. Always copy.
- Never sanitize silently. Every change must be listed in SANITIZATION_CHANGES so the caller can verify.
- Never promote a page with `confidence < 0.80`. Low-confidence project facts should mature before crossing tiers.
- Never promote a `memo` or a `question/` page. Only durable content is portable.
- Never promote without a justification. An agent that can't explain why a fact is portable probably shouldn't be promoting it.
