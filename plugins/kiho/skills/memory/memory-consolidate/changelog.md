# memory-consolidate changelog

## v1.1.0 — 2026-04-19

- **FIX:** outdated-content — drift-entry producer flipped from md append to broker-backed jsonl via `storage-broker` (sk-040)
- **Evidence:** v5.20 coordinated pending-queue migration. The pre-v5.20 md append at `agents/<id>/memory/soul-overrides.md` drifted tier (machine-written working memory should be jsonl, not Tier-1 md).
- **Diff:** 3 lines — version/lifecycle/data_classes frontmatter, Step 4 body (broker.put call), drift-entry format updated from markdown to JSON payload.
- **Coordinated with:** `soul-apply-override` (consumer) + `memory-reflect` (CEO producer) + `agents/kiho-ceo.md` trait-drift audit reader.
- **Consumer review:** `python bin/kiho_rdeps.py memory-consolidate` — non-blocking (memory is a per-agent skill with no hard_requires).
