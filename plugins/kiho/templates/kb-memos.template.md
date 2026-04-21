# KB memos — {{project_name}}

Living scratch area for short-lived notes, reminders, flagged concerns, and TODOs for the kb-manager or for committees. NOT a permanent store — items are pruned after 30 days of resolution by the `kb-lint` pass.

Format: checkbox list with `[date] · <who> · <note>`. When an item is resolved, flip the box and leave it in place; the next lint sweep moves resolved items older than 30 days to the bottom or deletes them.

## Open

(none yet — CEO and kb-manager will add entries as they go)

## Resolved (last 30 days)

(none)

## Examples of what belongs here

- `- [ ] 2026-04-12 · kb-manager: migrate entity pages to include owner_team field after org.json schema bump`
- `- [ ] 2026-04-11 · ceo: follow up on Q-rate-limit-policy pending external vendor response`
- `- [ ] 2026-04-10 · eng-lead-01: verify the retry-backoff-cap concept page is still accurate after the NATS migration lands`
- `- [x] 2026-04-09 · kb-manager: consolidated duplicate entities auth-service and auth-svc` (will be pruned 30 days after flip)

## What does NOT belong here

- Durable facts — those go in `wiki/`
- Decisions — those go in `wiki/decisions/` via committee
- Agent memory — each agent has its own memory files
- Research cache — those live in `.kiho/state/research/<iso>.md`
- User questions waiting on answer — those stay in CEO's ledger, not here

memos.md is for the KB's own operational TODOs: bookkeeping, cleanup, flagged items. Keep it lean.
