# ReAct storage doctrine

Version: 1.0 (2026-04-19; v5.20)
Status: canonical — supersedes ad-hoc "markdown-first" assumptions in pre-v5.20 skills
Companions: `storage-architecture.md` (tier invariants), `data-storage-matrix.md` (per-data-class rows), `storage-tech-stack.md` (per-category tech picks)

This reference names the **ReAct decision** a kiho agent runs before every persistent write. Storage tier is no longer a static skill-authoring choice; it is an **agent-side judgement** made per invocation through the `storage-broker` skill, whose backing library is `bin/kiho_storage.py`.

## Background

Pre-v5.20 convention: each skill authored its own storage choice at commit time via `metadata.kiho.data_classes:` frontmatter pointing at a matrix row. That convention stays — data-storage-matrix.md remains authoritative for well-known data classes — but it was narrower than the `/kiho` working pattern. Agents in practice often need to decide storage per invocation: an agent writing a one-shot research cache for a short-lived task has different needs than the same agent writing a cross-session lesson.

Three converging observations drove this doctrine:

1. `CLAUDE.md` v5.19 already declares "Markdown is not the default; the data shape chooses the tier." The implementation lagged: ~18 skills wrote Tier-1 md unconditionally, zero used Tier-3, and each domain reinvented frontmatter.
2. Karpathy's agentic-memory writing + the MemGPT / Letta line both converge on the same pattern: hot working memory managed by the agent via tool calls, with explicit eviction. kiho's three-tier frame already mirrors core / working / archival memory; this doctrine wires a **tool** (the broker) for the agent to reach it.
3. Skills that hardcoded markdown shipped a recurring smell: committee reviewers got walls of prose for what was really append-only telemetry; processing artifacts leaked into git diffs. Once storage is arbitrated, reviewability and queryability stop fighting each other.

## Principle

kiho does not dictate storage. The agent knows the task; the broker picks the tool. Storage tier is arbitrated per call via `storage-broker`, not baked into each skill. Committee-reviewable artifacts remain markdown, always; everything else is a ReAct choice.

## The decision tree

> **When to use this 4-question form vs the 7-question declarative matrix.** This doctrine's 4-Q tree is the **runtime agent-side distillation** — walk it silently before every `storage-broker` call. For static classification ("which tier does this *kind* of artifact belong in?" — soul vs telemetry vs eviction-scoped cache), consult the 7-Q tree in `references/storage-architecture.md §Decision tree`, which enumerates the authoritative mapping and carries 8 worked examples. The two are consistent: any 4-Q outcome reached at runtime matches the 7-Q static classification for that data class.

Run this before every persistent write. Stop at the first YES. The `storage-broker` skill encodes exactly this tree; callers supply the signals, the broker resolves the tier.

1. **Is this committee-reviewable?**
   Kinds: `soul`, `skill-md`, `kb-article`, `decision`, `brief`, `announcement`, `incident`, `postmortem`, `retrospective`, `values-flag`, `committee-transcript`.
   → **md**. Forced by `kiho_frontmatter.validate`; the broker refuses any other tier for these kinds.

2. **Does it die with this turn?**
   Signals: `durability=session` or `access_pattern=ephemeral`.
   → **mem** (in-process dict). Zero cost, zero durability. Use for multi-step reasoning scratch, inter-iteration passing, intra-turn caches.

3. **Is it query-heavy, or large (>1000 rows expected)?**
   Signals: `access_pattern=query-heavy` or `size_hint > 1000`.
   → **sqlite** with FTS5, built lazily from the jsonl spool on first query. The sqlite file is derived; the jsonl is authoritative. Deletion recovers correctness, possibly slower.

4. **None of the above?**
   → **jsonl** (append-only). The default. Cheap writes, O(n) scan, works for any kiho-sized workload until row-count forces a promotion.

## Questions the agent asks itself

Not a ceremony — four questions, walked silently before a put():

- **Will a human review this in the next turn?** → md.
- **Does it outlive this turn?** → not mem.
- **Do I need to filter, sort, or full-text-search it later?** → sqlite is likely.
- **Is the source already canonical elsewhere?** → don't write; cite.

## Cost model

- **md writes**: O(1) per file, diffable, committee-friendly. Lose: grep-only retrieval, merge conflicts on hot files.
- **jsonl append**: O(1) per row, schema-tagged by frontmatter helper, streamable. Lose: O(n) scan for reads.
- **sqlite FTS5**: cold-open ≈ 50–200 ms on first query (lazy rebuild), then keyed/FTS queries are cheap. Lose: binary file, re-built when the spool changes, invalidated by every append.
- **mem**: zero cost, zero durability. Lose everything on process exit.

Rule of thumb: **md iff a human reads it; jsonl iff append-then-scan; sqlite iff scan-cost dominates; mem iff it dies with the turn.**

## Invariants

Cross-reference with `storage-architecture.md` §Guardrails. The ReAct broker respects the same rules; it does not weaken them.

- **Reviewable-kind guardrail.** `kiho_frontmatter.validate(meta, kind)` rejects any non-md tier for the 11 reviewable kinds. The storage-broker checks before writing. Caller cannot override.
- **Source-of-truth discipline.** Tier-1 md remains canonical for committee-reviewed artifacts. Tier-2 jsonl is regenerable or primary-observation; if primary (telemetry), it cannot be re-derived and must be protected (append-only, no hand-edit). Tier-3 sqlite is always derived from Tier-2 and may be deleted freely.
- **No long-running server.** `kiho_storage.py` opens and closes sqlite connections per call. No daemon, no background indexer, no PostToolUse hook. Lazy FTS is built on demand.
- **Eviction is explicit.** Every Tier-3 write carries an eviction policy (session-scope, TTL, or keep_last). `evict()` is the only destructive op; md is NOT evicted by broker — md retention is governed by kb-manager / skill-deprecate / committee.
- **User-accept non-bypassable.** Broker writes at `scope=project` or `scope=company` require a prior user-accept turn. Enforced by CEO at the `/kiho` loop boundary, not inside the broker (the broker is amoral; the CEO polices scope).
- **Depth/fanout caps unchanged.** Broker writes are file I/O, not agent spawns. They never count against depth-3 / fanout-5.

## Anti-patterns

- **Writing md "just in case."** If no human reviews it within the session, it doesn't need to be md. Use jsonl.
- **Pre-building indices.** Sqlite is lazy. Don't build at plugin load; don't rebuild on every write; let the first query pay the cost.
- **Denormalized jsonl caches pretending to be views.** If you keep a separate jsonl mirror to "speed things up," you own dedup. Prefer: make the source itself queryable (jsonl) and let sqlite build on demand.
- **Grep-based read paths outside `memory-query`.** Use the unified read path (`memory-query` skill) for cross-namespace lookups; it calls the broker with the right signals.
- **Inventing a new data class without a matrix row.** If the write doesn't fit any row in `data-storage-matrix.md`, that's a signal to pause and ask the CEO / user, not an invitation to create ad-hoc paths.

## API surface (summary)

The broker exposes four calls via `skills/core/storage/storage-broker/SKILL.md`, backed by `bin/kiho_storage.py`:

```
put(namespace, key, payload, *, access_pattern, durability, size_hint,
    query_keys, human_legible, kind, scope, owner, body) -> Ref
get(ref | (namespace, key)) -> {meta, payload, body} | None
query(namespace, *, where, fts, order_by, limit) -> [rows]
evict(namespace, *, older_than_days, keep_last) -> n_removed
```

`Ref = {tier, namespace, key, path, row_id, etag}` — callers persist the Ref in their own records to cite later, rather than raw paths.

## Migration contract

- **Existing skills** (`data_classes:` frontmatter pointing to matrix rows) keep working without change. The doctrine is additive.
- **New skills** authored after v5.20 SHOULD delegate persistent writes to the broker unless a matrix row names a specific path (e.g. `agent-performance.jsonl` lives at a fixed location and is written via `session-context` / telemetry hooks, not the broker).
- **Lazy migration**: existing skills that touch via `skill-improve` pick up broker use as part of the improvement. No bulk rewrite. `bin/kiho_fm_doctor.py` tracks drift.

## Changelog

| Date | Version | Change |
|---|---|---|
| 2026-04-19 | 1.0 | Initial ReAct storage doctrine. Formalizes the per-call tier-selection pattern encoded in `storage-broker` + `bin/kiho_storage.py`. Cross-references storage-architecture.md §Decision tree (whose 7-question tree applies to data-class design; this 4-question tree applies to per-invocation agent judgement). |
