# Company KB memos — {{user_name}}

Short-lived scratch for the company knowledge base. Cross-project TODOs, flagged concerns, reminders for the kb-manager at the company level.

Format: checkbox list with `[date] · <who> · <note>`. Resolved items older than 30 days are pruned by `kb-lint`.

## Open

(none yet)

## Resolved (last 30 days)

(none)

## Examples of what belongs here

- `- [ ] 2026-04-12 · kb-manager: review whether the retry-backoff-cap concept should be split into per-language variants`
- `- [ ] 2026-04-10 · user: add a principle for "no feature flags for unborn features" after our discussion yesterday`
- `- [ ] 2026-04-09 · kb-manager: audit rubrics/ for MAJOR version drift; the pm-senior rubric hasn't been used in any recruit cycle in 4 months`

## What does NOT belong here

- Durable facts — those go in `wiki/`
- Project-specific notes — those go in the project's own `.kiho/kb/memos.md`
- User principles — those go in `wiki/principles/` after user approval
- Open cross-tier questions — those open as `questions/` pages in the appropriate tier

Keep this file lean. If it grows past ~50 lines, run `kb-lint` to prune or flip-and-archive resolved items.
