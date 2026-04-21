# Company KB rules — {{user_name}}

Durable rules for how the company-tier knowledge base is used. kb-manager reads this before every write to the company tier. `kb-lint` check #10 enforces these across all existing company pages.

These rules are more conservative than project-tier rules because content here is supposed to be portable across every project.

## Must-follow (enforced on every write)

1. **No project-specific file paths.** A page that contains `src/`, `/apps/`, `C:/`, `D:/`, or similar path fragments is rejected. Paths are checked with regex during kb-add.
2. **No project-specific proper nouns.** Service names unique to one repo, customer names tied to one engagement, database names from one project — all rejected. kb-manager maintains a "project-bound names" allowlist learned from promotion events.
3. **Every `rubrics/` page must have a `version` frontmatter field** and must have been approved by a committee (reference in `provenance[]` with `kind: committee_decision`).
4. **Every `principles/` page must have `user_approved: true`** set. Principles reflect the user's taste; kiho cannot invent principles without explicit approval.
5. **Entity pages are generic.** A company-tier entity page for `postgres` describes postgres in general, not "our postgres cluster". Anything that starts "our ..." is project-tier.
6. **Concept pages apply to at least 2 hypothetical projects.** If kb-manager can only imagine this concept applying to the originating project, it belongs in the project tier instead. (This is a heuristic kb-manager applies during promotion.)
7. **Confidence >= 0.80 for all ACTIVE pages.** Uncertain content should live in project tier until validated across at least one more project; then it can be promoted.
8. **No time-sensitive content.** Phrases like "this quarter", "after Aug 2026", "the current version of X" are rejected. Use `valid_from` / `valid_until` frontmatter for anything time-bound.

## Conventions (strongly recommended)

- Kebab-case filenames.
- Tags use broad categories (`retry`, `testing`, `review`) not project terms.
- Source citations link to vendor docs, well-known blogs, academic papers, or cloned-repo references — not project commits or committee transcripts from one project (those are the PROVENANCE of the promotion, kept in the project tier).

## Rubric versioning

Rubrics follow strict semver:
- PATCH: typo / clarification.
- MINOR: added dimension with backwards-compatible scoring.
- MAJOR: weights changed or dimensions removed. A MAJOR bump creates a new file `<name>-v<N>.md` and the old one flips to `status: deprecated` but is kept.

Any MAJOR bump requires a fresh committee approval.

## Principles are special

Principles are NEVER created by an agent unprompted. A principle enters company KB only when:

1. The user has explicitly told CEO "this is how I work" in a committee decision, AND
2. The user has ack'd the principle page content before it lands, AND
3. The principle has `user_approved: true` in frontmatter with a timestamp and a reference to the user's exact words in a ceo-ledger entry.

kb-manager enforces this at `kb-add` time: principle additions without `user_approved: true` are rejected.

## Amendment process

To change a rule in this file, convene a committee at the company-tier scope. The committee must produce a decision page in `wiki/synthesis/` (or `wiki/decisions/` if you add that type to company tier). On close, the Clerk invokes `kb-update` on this file with the new rule. Changes should be committed to git if `$COMPANY_ROOT` is under git control (recommended).
