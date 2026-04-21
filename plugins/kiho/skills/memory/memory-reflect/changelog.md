# memory-reflect changelog

## v1.1.0 — 2026-04-19

- **FIX:** outdated-content — CEO-pathway drift producer flipped from md append to broker-backed jsonl
- **Evidence:** v5.20 coordinated pending-queue migration. CEO drift entries previously appended to `.kiho/agents/ceo-01/memory/soul-overrides.md`; now route through `storage-broker` (sk-040) into the jsonl namespace that `soul-apply-override` drains.
- **Diff:** 3 lines — version/lifecycle frontmatter + data_classes addition + line 249 CEO drift-write body.
- **Coordinated with:** `memory-consolidate` (IC producer) + `soul-apply-override` (consumer) + `agents/kiho-ceo.md` trait-drift audit reader.
- **Scope note:** IC pathway lives in `memory-consolidate` (not this skill); this FIX only rewires the CEO-specific drift-write path.
