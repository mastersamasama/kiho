# Company knowledge base — {{user_name}}

This file describes the **company-tier** knowledge base. It lives at `{{company_root}}/company/` and follows you across every project that uses kiho. It is the user-global counterpart to each project's project-tier KB.

This file is read by kb-manager and every agent before interacting with the company KB.

## 1. Scope

The company KB captures **portable knowledge** — facts, patterns, principles, and rubrics that apply across projects and don't depend on any single codebase's layout. Examples:

- Retry recipes that work regardless of language
- Style preferences the user consistently holds
- HR interview rubrics that have been committee-approved and used successfully
- Tool configurations the user always applies (editor prefs, shell aliases documented as facts, etc.)
- Cross-project retros and meta-observations

**Never** put anything in the company KB that mentions a specific file path in a specific repo, a project-specific module name, or a proper noun bound to one project. Those stay in the project KB. kb-manager enforces this through `kb-lint` check #7 (raw leakage) and check #10 (rules) — and during `kb-promote`, kb-manager sanitizes project entries before copying them here.

## 2. Page type catalog

| Type | Directory | Use when |
|---|---|---|
| **Entity** | `wiki/entities/` | A cross-project thing: a tool (git, docker), a framework (Next.js), a customer (BigCorp if you consult for them), a language |
| **Concept** | `wiki/concepts/` | A reusable idea: `retry-with-jitter`, `idempotency-keys`, `clean-architecture`, `feature-flag-rollout` |
| **Principle** | `wiki/principles/` | User's durable taste rules: `no-abstraction-before-duplication`, `test-outputs-not-implementations`, `boring-technology-first` |
| **Rubric** | `wiki/rubrics/` | HR interview rubrics approved by committee for reuse across projects: `eng-frontend-ic.md`, `pm-senior.md` |
| **Synthesis** | `wiki/synthesis/` | Cross-project analyses: `q1-retro-across-projects`, `which-ORMs-work`, `typescript-error-patterns` |

## 3. Write protocol

Same as the project tier: **only `kiho-kb-manager` writes `wiki/`.** Requests go through the same sub-skills (`kb-add`, `kb-update`, `kb-delete`, `kb-ingest-raw`) with `TIER: company` in the payload.

Writes to the company tier are more conservative than to project tier: kb-manager double-checks for project-specific leakage, cross-project conflicts, and rubric versioning before accepting. A write that would introduce a file path or a project-specific proper noun is rejected with a structured error.

## 4. Read protocol

Any agent can read `wiki/` directly. Curated cross-tier searches (e.g., "what do we know about retry patterns, either in this project or across projects?") go through `kb-search` with `scope: both`, which asks kb-manager to merge project and company results with source annotations.

## 5. Wikilinks

Wikilinks are relative to **this tier's** `wiki/`. Cross-tier links use a prefix:

```markdown
Locally we do [[billing-webhook]]; the general pattern is [[company:idempotency-keys]].
```

kb-manager resolves `company:` as a link to the company-tier `wiki/entities/idempotency-keys.md` etc. Most pages should NOT reference the other tier directly; prefer pure company-tier prose for portability.

## 6. Promotion rule (project → company)

A project-tier page may be promoted to company tier when:

1. No wikilinks inside the page reference project-specific entities with unresolvable external context.
2. No file paths from any repo appear in the body.
3. No proper nouns tied to one project appear in the body.
4. The page has `confidence >= 0.80`.
5. An agent (usually CEO or a dept leader) or a committee explicitly requests promotion via `kb-promote`.

kb-manager runs the sanitization pass before copying, and may reject the request with specific line-by-line feedback. The project-tier page stays in place with a `> PROMOTED_TO: <company-path>` callout. The company-tier copy records the origin project in `provenance[]`.

`cross-project.md` at this tier's root tracks every promoted page and its origin project for traceability.

## 7. Index set

Same 12 indexes as project tier PLUS:

| Index | Purpose |
|---|---|
| `cross-project.md` | Traceability: which company pages came from which projects, with promotion timestamps |

## 8. Skill linkage

Same as project tier. `skill-solutions.md` at this tier's root aggregates skill → problem mappings for company-level skills. Company skills in `$COMPANY_ROOT/skills/` are the most broadly reusable; project skills in any `.kiho/skills/` are narrower.

## 9. Immutability

- `raw/` is append-only.
- `rubrics/` pages are versioned: never edit in place. A new rubric version creates a new page `eng-frontend-ic-v2.md` and marks the old version `status: deprecated`. Old rubrics stay readable for audit.
- Principles are rarely revised; revision requires explicit user approval (committee can propose, user must ack).

## 10. What this tier is NOT

- Not a secondary project KB — it is cross-project ground truth.
- Not a backup — if you have one project's facts here, they shouldn't be here.
- Not a scratch area — memos.md is the scratch area; this file describes durable schema.
- Not auto-synchronized — nothing pulls automatically from project tiers except explicit `kb-promote` calls.
