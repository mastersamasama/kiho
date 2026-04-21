# soul-apply-override changelog

## v1.1.0 — 2026-04-19

- **FIX:** outdated-content + structural — pending queue flipped from Tier-1 md to broker-backed jsonl with `status` field; `-applied.md` archive retired
- **Evidence:** v5.20 ReAct/agentic-memory review flagged the two-file md atomicity dance (pending.md → applied.md move) as non-atomic and the md queue as wrong tier for machine-written working memory. Smell #1 from the critique.
- **Diff:** 4 lines — version bump (1.0.2→1.1.0 minor; structural change), Inputs block note, Step 2 body (broker query + structural rate-limit), Step 9 body (status-field supersedes archive-file).
- **Coordinated with:** `memory-consolidate` (IC producer) + `memory-reflect` (CEO producer) + `agents/kiho-ceo.md` trait-drift audit reader. All four land in same turn.
- **Migration note:** Downstream projects with pre-v5.20 `.kiho/agents/*/memory/soul-overrides.md` must run `kiho_fm_doctor --fix` once before the next soul-apply-override invocation; un-migrated md queues are silently ignored (jsonl wins).

## v1.0.2 — 2026-04-19

- **FIX:** outdated-content — Step 7 trait-history write migrates to `storage-broker` (sk-040) with canonical `kind=evolution` schema
- **Evidence:** v5.20 ReAct/agentic-memory review flagged ad-hoc trait-history schema drifting from `bin/kiho_frontmatter.py KIND_SCHEMAS["evolution"]`. Production `trait-history.jsonl` per agent did not yet exist; this FIX both introduces the canonical write path and unifies soul evolution with skill evolution for `memory-query` retrieval.
- **Diff:** 3 lines — version bump + Step 7 body rewrite. Frontmatter/Step-1/Red-lines/anti-patterns unchanged from v1.0.1.
- **Consumer review:** unchanged from v1.0.1 — non-blocking.

## v1.0.1 — 2026-04-19

- **FIX:** missing-instruction — red-line overrides must cite a resolved `values_flag_ref`
- **Evidence:** v5.20 v5.20 ReAct/agentic-memory review flagged that Step 1 auth check predates the `values-flag` skill (sk-051) introduced v5.20; CEO sign-off alone carries no auditable provenance back to the soul clause challenged.
- **Diff:** 5 lines — frontmatter `version`/`lifecycle` added, Step 1 body extended with values-flag requirement, Red lines merging rule tightened, new anti-pattern entry, no structural reorganization.
- **Consumer review:** `python bin/kiho_rdeps.py soul-apply-override` → 0 hard_requires, 0 soft_mentions, 1 agent_portfolio (kiho-ceo), 1 catalog_entry, 0 wikilinks, 0 kb_backrefs. No blocking downstream impact.
