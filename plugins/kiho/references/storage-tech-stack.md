# Storage tech stack — per-category decisions

- Version: 1.0 (2026-04-18)
- Status: canonical decision record
- Companion to: `references/storage-architecture.md` (three-tier invariants) + `references/data-storage-matrix.md` (per-data-class matrix, Phase 2)
- Vote log: `_meta-runtime/phase1-committee-minutes.md`

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.

## Non-Goals

- **Not a replacement for `storage-architecture.md`.** Tier invariants (T1-MUST-*, T2-MUST-*, T3-MUST-*, XT-*) remain load-bearing. This file names specific technologies committee-approved to satisfy those invariants per data-class category.
- **Not a fixed immutable stack.** Each decision carries a confidence score and revisit triggers. New tech stacks replace old ones via committee vote + `storage-architecture.md` cross-reference update.
- **Not an author opinion document.** Every entry traces to Phase 1 committee minutes with vote margin + rationale + rejection reasons.

## How this file is used

Skill authors cite this file when declaring `metadata.kiho.data_classes:` frontmatter (once Phase 2 matrix ships). Choosing a storage technology NOT listed here requires proposing a category addition via CEO-committee vote. Losers in each category must not be re-proposed without new evidence addressing the rejection reasons recorded here.

---

<!-- v5.19.5 cross-refs (propagated by Tier E plan):
     - §6 revisit-trigger #1 is now instrumented at
       <plugin-root>/.kiho/state/tier3/semantic-embedding-triggers.jsonl
       (written by skills/_meta/skill-find/scripts/facet_walk.py on ceiling hit).
       bin/catalog_walk_audit.py reports rolling-30d hit count via
       check_embedding_trigger(); warn ≥5/30d, error ≥15/30d. -->

## 1. Small typed config

**Winner**: **TOML** (Python 3.11+ stdlib `tomllib` for reads; `tomli-w` 5 KB pure-Python or hand-templating for rare writes)

**Use cases**:
- `skills/core/harness/kiho/config.toml` — **MIGRATED v5.19.3** (from `config.yaml`) via `bin/yaml_to_toml.py` as the Tier-C proof migration; hand-touched comment placement post-conversion.
- `skills/core/planning/interview-simulate/assets/canonical-rubric.toml` — **MIGRATED v5.19.5** (from `canonical-rubric.yaml`) as the Tier-E second-config-migration proof; hand-written due to multi-level nesting beyond `yaml_to_toml.py` narrow schema; legacy `.yaml` retained one cycle as safety net (delete in v5.19.6).
- recruit role-specs (committee-deferred to author discretion: TOML OR markdown+TOML-frontmatter)
- soul-overrides (frontmatter+prose stays valid; if purely structured, TOML)

**Rationale**: Stdlib since 3.11 eliminates PyYAML hidden dependency. Strong typing prevents "yes"→bool and "1.0"→string surprises. TOML's table syntax fits flat-scalar and moderate-nesting configs cleanly. Comment support preserves authoring intent (lost in JSON).

**Rejected**:
- **YAML**: not stdlib (PyYAML is third-party, >1 MB install); type ambiguity breaks round-trip.
- **JSON**: no comment support; verbose for hand-editing; authors already complain.
- **SQLite**: binary format blocks committee diff review; wrong abstraction level for <50-entry files.

**Migration discipline**: lazy — new configs use TOML; existing YAML migrates when author touches the file (any `skill-improve` pass that changes the schema migrates it). No mass sweep.

**Confidence**: 0.88. **Revisit trigger**: if tomllib spec changes incompatibly (unlikely) or write-path ergonomics degrade.

---

## 2. Append-only event stream

**Winner**: **Keep JSONL** as canonical; **DuckDB over JSONL** as optional read-side aggregation overlay (fallback to Python loop when DuckDB absent)

**Use cases** (all 5 kept as JSONL):
- `<project>/.kiho/state/skill-invocations.jsonl`
- `<project>/.kiho/state/agent-performance.jsonl`
- `<project>/.kiho/state/ceo-ledger.jsonl`
- `<project>/.kiho/state/gate-observations.jsonl`
- `<project>/.kiho/state/cross-agent-learnings.jsonl`

**Rationale**: Low-frequency writes (per-invocation / per-task / per-phase / per-gate / per-lesson) don't justify migration away from JSONL. Append semantics map directly to `open(p, 'a')`. Crash safety via atomic `write+fsync+rename` is stdlib-available. Committee diff-review on JSONL is trivially human-readable. The one pain point — aggregate reads in `org_sync` — is solved by DuckDB's `read_json()` zero-copy overlay without touching the write path.

**Rejected**:
- **SQLite append-only table**: stdlib but binary; breaks diff review; write locking contradicts Ralph statelessness.
- **Parquet**: batch-optimized write pattern; ~6× slower per-record append than JSON; complex rolling compaction for incremental appends.
- **DuckDB as write target**: DuckDB's value is on reads, not writes; misses the point.

**DuckDB integration** (optional):
- Scripts check `duckdb` import; on ImportError, fall back to Python loop.
- `bin/org_sync.py` should offer both paths; hot path is still the Python loop until DuckDB adoption is broad.
- No skill MAY require DuckDB as a hard dep until a committee vote promotes it from optional to required.

**Confidence**: 0.85. **Revisit trigger**: aggregate read latency (capability-matrix rebuild) ≥ 500ms on a project with <1M telemetry rows.

---

## 3. Relational live registry (capability-matrix et al.)

**Winner**: **Markdown Tier-1 canonical** + **in-memory Python dict Tier-3** (session-scope eviction, build from .md or JSONL replay)

**Use cases**:
- `<project>/.kiho/state/capability-matrix.md` (proficiency table; rebuilt by `bin/org_sync.py`)
- `<project>/.kiho/state/org-registry.md` (agents/departments/teams table)
- `<project>/.kiho/state/management-journals/<leader-id>.md` (narrative-heavy; table sections inside)

**Rationale**: Committee-reviewable .md is load-bearing for all three. RACI lookups during CEO delegation are solved by a single in-memory dict built once per `/kiho` turn. No sqlite, no dual-write, no binary artifact. In-memory dict is T3 with session-scope eviction; rebuild is 10-20 ms from .md or JSONL replay.

**Rejected**:
- **SQLite / DuckDB**: binary blocks diff review; dual-write introduces divergence risk; query latency gain is unnecessary at current cardinality (14 agents × 8 domains = 112 cells).
- **Parquet**: append-every-60s pattern is wrong fit; no diff-review.

**Pattern** (for in-memory dict):
```python
# CEO INITIALIZE, once per /kiho turn
capability_matrix = build_from_md(".kiho/state/capability-matrix.md")
# OR: capability_matrix = replay_from_jsonl([...])
# session-scope dict; GC'd at turn end
```

**Implication for v5.19 Phase 4**: capability-matrix is **no longer a pilot candidate**. It needs no migration — the existing .md stays canonical; the in-memory dict is a best-practice pattern scripts already use ad-hoc.

**Confidence**: 0.92. **Revisit trigger**: agents > 100 or per-turn RACI query count > 1000.

---

## 4. Committee records

**Winner**: **JSONL-per-committee (T2)** + **sqlite cross-committee index (T2, lazy)** with **transcript.md (T1) as regenerability source**

**Use cases**:
- Per-committee rounds, per-member positions, per-round challenges, aggregate-confidence trajectory, dissent
- Final decisions (≥0.90 confidence) still promoted to `<project>/.kiho/kb/wiki/decisions/<id>.md` via kb-manager gateway — unchanged

**Storage layout**:
```
<project>/.kiho/committees/<committee-id>/
  transcript.md       (T1 — live committee prose; source of truth)
  records.jsonl       (T2 — parsed structured rounds; regenerated from transcript)
<project>/.kiho/state/committee-index.sqlite  (T2 — lazy cross-committee aggregation for pattern queries)
```

**Regeneration recipe**: `kiho_clerk extract-rounds <transcript.md> → <records.jsonl>` (deterministic parser; to be implemented as part of pilot if chosen). Sqlite index rebuilt by scanning all `committees/*/records.jsonl`.

**Rationale**: Mid-round dissent, per-member positions, resolved challenges are currently lost. JSONL-per-committee captures them structured while transcript.md preserves the human narrative. Sqlite index is lazy — built only when a cross-committee pattern query fires. kb-manager gateway preserved for final decisions.

**Rejected**:
- **Append to ceo-ledger.jsonl**: mixes committee state into CEO orchestration stream; muddies both narratives.
- **Markdown-per-round hybrid**: merge conflicts when parallel rounds exist; cross-committee queries require grep.
- **SQLite-only (no JSONL)**: transaction recovery complex; committee records should be audit-traceable as text streams.

**Schema (sqlite index, lazy)**:
```sql
CREATE TABLE committee_records (
  id INTEGER PRIMARY KEY,
  committee_id TEXT NOT NULL,
  round INTEGER NOT NULL,
  phase TEXT NOT NULL,  -- suggest|challenge|research|choose|...
  timestamp TEXT NOT NULL,
  agent_id TEXT,
  position TEXT,
  confidence REAL,
  aggregate_confidence REAL,
  status TEXT   -- open|closed|deadlocked
);
CREATE INDEX idx_committee_round ON committee_records(committee_id, round);
```

**Confidence**: 0.88. **Revisit trigger**: if transcript-parser determinism breaks on 3+ committees, re-evaluate committee-records-first (bypassing transcript as source).

---

## 5. Full-text search over narrative

**Winner**: **SQLite FTS5 Tier-3 per-turn** (primary) + **ripgrep on-demand** (fallback for ≤20-file corpora or literal-token searches)

**Use cases**:
- `skills/_meta/skill-create/scripts/similarity_scan.py` (Gate 17)
- `skills/_meta/skill-find/scripts/facet_walk.py`
- kb-search queries over `<project>/.kiho/kb/wiki/**/*.md` and `$COMPANY_ROOT/company/wiki/`
- experience-pool queries (when materialized)

**Rationale**: SQLite FTS5 is stdlib; 50ms rebuild for 44 docs; <20ms BM25 query. Deterministic with k1=1.2, b=0.75 pinned. ripgrep fallback is fast for small corpora where the index build dominates.

**Rejected**:
- **Whoosh**: original repo unmaintained; 2-3× slower than FTS5 on medium corpora.
- **Tantivy**: adds external Rust binary dep; index format breaks across major versions; overkill at 44-skill scale.
- **In-memory inverted index**: 180+ lines of custom BM25 logic vs FTS5's declarative queries; harder to test.

**Pattern**:
```python
# Tier-3 session-scope helper
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
    conn = sqlite3.connect(f.name)
    conn.execute("CREATE VIRTUAL TABLE skills USING fts5(name, description)")
    # index 44 SKILL.md files
    # query via MATCH + bm25(skills)
# delete at turn end
```

**Gate 17 interaction**: Jaccard remains the Gate 17 formalism (ground truth). FTS5 is a pre-filter that narrows the candidate set before Jaccard scoring. Determinism preserved.

**Confidence**: 0.92. **Revisit trigger**: catalog > 200 skills; FTS5 per-turn rebuild > 300ms.

---

## 6. Semantic similarity — DEFERRED

**Winner**: **Do nothing today.** No persistent semantic similarity store, no embedding daemon, no model pre-load. Revisit when one of these revisit triggers fires:

1. An agent reports hitting the 10-candidate ceiling in `facet_walk.py` even after narrowing hints, on a real task. **Instrumented v5.19.5:** `skills/_meta/skill-find/scripts/facet_walk.py` appends one JSONL line per ceiling hit to `<plugin-root>/.kiho/state/tier3/semantic-embedding-triggers.jsonl`; `bin/catalog_walk_audit.py check_embedding_trigger()` rolls that up over the last 30 days. Warn at ≥5 hits/30d, error at ≥15 hits/30d. Error-level firing twice in a quarter = committee re-opens this §.
2. A concrete use-case requests cross-session semantic memory retrieval (MemGPT/Letta-style) with justification beyond "would be nice."
3. Catalog grows to ≥100 skills AND mean-pairwise Jaccard climbs above 0.03 (early congestion signal). `bin/catalog_walk_audit.py` check `confusability` already reports rolling Jaccard; baseline Apr 2026 is 0.0146.

**If forced by one of the triggers**: **sqlite-vec** + pinned lightweight embedding model (e.g., EmbeddingGemma 308M or Model2Vec compressed variants). Model version declared in the Tier-3 cache header. Per-task cache; TTL session-scope.

**Rationale for deferral**: v5.15 H1/Q2 findings explicitly rejected persistent embedding indexes (daemon requirement, model-version drift, dependency bloat). v5.16 chose faceted retrieval (capability + domain + topic_tags) and catalog-audit reports mean-pairwise Jaccard 0.015 — zero congestion today. No agent report has triggered a ceiling-violation in gate mode. Deferral is a concrete rule with auditable triggers, not an open loop.

**Rejected as immediate winners**:
- **LanceDB**: 50MB wheel; designed for long-lived indexes (contradicts "on-demand per task"); multimodal is overkill.
- **faiss-cpu**: AVX2/AVX512 binary incompatibility across CI environments breaks reproducibility (v5.15 hard requirement).
- **numpy + cosine**: O(n²) pairwise; doesn't scale past 50 vectors; no dependency gain over Jaccard.
- **sqlite-vec (as immediate winner)**: valid tech, but deferred because no concrete use-case blocks today.

**Confidence in deferral**: 0.85. **Revisit triggers above are the only paths to re-vote.**

---

## 7. Session scratch — no unified doctrine

**Winner**: **Each script decides.** No centralized `SessionScratch` wrapper required. T3-MUST-1 (eviction declared) and T3-MUST-2 (idempotent-safe reads) remain hard invariants.

**Pattern reference**: `references/t3-scratch-patterns.md` (to be authored in Phase 2 if a pattern doc is warranted; may be absorbed into `data-storage-matrix.md` instead).

**Suggested choices per use-case** (non-normative):
- **Small in-turn cache**: Python dict in module scope; no persistence.
- **Multi-script cross-invocation scratch (same turn)**: `tempfile.TemporaryDirectory` + JSON files per key.
- **Structured queries on intermediate data**: `sqlite3.connect(":memory:")`.
- **Crash-debuggable intermediate state**: `tempfile` + sqlite file with explicit `unlink()` cleanup.

**Rejected (as unified mandates)**:
- **Single `SessionScratch(tempfile + JSON)` helper**: boilerplate for 90% of scripts that just need dicts.
- **sqlite :memory: as mandate**: over-specifies for simple JSON-blob cases; adds schema overhead.

**Rationale**: No concrete use-case drives unification today. Decentralized discipline + T3 invariants are sufficient. If a pattern emerges naturally, codify it later via `skill-improve` on the affected scripts.

**Confidence**: 0.72. Lower than peers because "no unified pattern" is a conservative choice when data is thin. **Revisit trigger**: ≥3 scripts implement substantially similar tempfile+JSON scratch patterns within a quarter; at that point, factor into a helper.

---

## 8. Derived index over skill-catalog metadata

**Winner**: **SQLite FTS5 Tier-3 session-scope** at `<project>/.kiho/state/tier3/skill-catalog-<turn-id>.sqlite`, built at CEO INITIALIZE by `bin/skill_catalog_index.py` (to be implemented in Phase 4).

**Use cases**:
- `skills/_meta/skill-create/scripts/*.py` (32 scripts re-parsing 44 SKILL.md per invocation)
- `skills/_meta/skill-find/scripts/facet_walk.py`
- `bin/kiho_rdeps.py` forward-edge traversal
- Gate 17, Gate 19-24 checks during skill-factory batches

**Rationale**: 32-script re-parse at 44 skills = ~6.4s aggregate per full factory run; at 200 skills projected = ~29s. Sqlite-FTS5 index built once per turn (~50 ms) + <5 ms per query eliminates this. Session-scope eviction preserves the "compute fresh each turn" Ralph discipline while sharing one parse across 32 consumers.

**Schema** (see `_meta-runtime/phase1-committee-minutes.md` §Category 8 for full schema sketch):
```sql
CREATE TABLE skills (id TEXT PRIMARY KEY, name TEXT, domain TEXT, sub_domain TEXT,
  description TEXT, capability TEXT, requires TEXT, mentions TEXT,
  topic_tags TEXT, version TEXT, solves TEXT, path TEXT, disk_mtime INTEGER);
CREATE VIRTUAL TABLE skills_fts USING fts5(name, description, capability, topic_tags,
  content='skills', content_rowid='id');
CREATE TABLE catalog_parent_of (domain TEXT, child_id TEXT, PRIMARY KEY(domain, child_id));
```

**Eviction**: session-scope (deleted at CEO turn end). Staleness detection: compare disk mtime per skill vs recorded; rebuild on any mismatch.

**Reconstruction recipe**: walk `skills/**/SKILL.md`, parse frontmatter, insert. Deterministic, ~50 ms at 44 skills.

**Rejected**:
- **Keep current (re-parse)**: doesn't scale past 100 skills; 32× re-parse burden compounds.
- **JSON hash-cache**: hash-check cost (~100 ms) negates cache benefit at per-turn granularity; no FTS queries.
- **In-memory per script**: zero cross-script benefit; 32 scripts each discover independently.

**Distinction from `kiho_rdeps`**: `kiho_rdeps` computes REVERSE edges from forward graph (inherently cache-hostile; pnpm/cargo rationale applies). This index caches FORWARD edges (frontmatter parsing), which is cache-friendly. Both patterns coexist.

**Confidence**: 0.85 today; 0.92 after CEO turn-termination cleanup hook is verified in Phase 4 pilot.

**Phase 4 pilot**: **This is the primary pilot candidate** — first-ever Tier-3 shipping artifact, isolated from CEO Ralph loop, measurable latency gain.

---

## 9. Cross-project lesson rollup

**Winner**: **kb-manager wiki promotion** to `$COMPANY_ROOT/company/wiki/cross-project-lessons/<slug>.md`, one markdown page per canonicalized lesson.

**Promotion flow**:
1. CEO DONE step 5 identifies eligible lessons: `confidence ≥ 0.80` AND (learned across ≥1 prior project OR committee-approved).
2. Calls `kb-promote` with the project-tier lesson as source.
3. kb-manager sanitizes: strips absolute paths, project-bound names (allowlist), internal tool names. Rewrites possessives ("our X" → "X"). Preserves generic frameworks + open-source tools.
4. Staged in `$COMPANY_ROOT/company/drafts/<REQUEST_ID>/` → lint → atomic move to `cross-project-lessons/<slug>.md`.
5. Dedup: if cosine-similarity ≥0.85 with existing page, merge via `kb-update` — increment `republished_count`, append source project to `source_projects` frontmatter.

**Schema (frontmatter)**:
```yaml
---
title: <canonical-lesson-title>
slug: <lesson-slug>
confidence: <0.0-1.0>
republished_count: 1
source_projects: [<project-slug-1>]
promotion_history:
  - {project: <slug>, ts: <iso>, confidence: <f>}
tags: [...]
---
<lesson body — narrative, no project-specific paths>
```

**Rationale**: Reuses existing kb-manager gateway (single-writer invariant preserved). Fits Karpathy wiki protocol (one page per thing). Committee-reviewable at promotion time via `log.md` entries. Searchable via kb-search facet + tag indexes; no new Tier-3 required.

**Rejected**:
- **Per-agent `lessons-published.jsonl`**: couples CEO loop state; no kb-search discoverability; violates single-gateway invariant.
- **Company `experience-pool.sqlite`**: adds Tier-3 for a rare-write / rare-read scenario; no human reviewability at promotion time.
- **Single markdown concat file**: unscalable; no backlinks; violates Karpathy one-page-per-thing.

**Sanitization rules** (seed list; evolves via kb-manager rules.md committee):
- Hardblock: absolute paths (`/home`, `/Users`, `C:\`), project-bound names, wikilinks to project-only entities without company equivalents.
- Softflag: generic frameworks, open-source tools, standard patterns.
- Rewrite: possessives, file paths → service names, config-var names → role-names.

**Cosine dedup**: ephemeral embedding at promotion time only (not persistent). Falls under Category 6 deferral exception — per-write, not per-read, no daemon.

**Integration**:
- `experience-pool` skill op=`promote` calls `kb-promote` as first step.
- kb-lint adds `project_bound_name_check` warning.

**Confidence**: 0.88. **Revisit trigger**: if cosine 0.85 threshold over- or under-merges in first 10 promotions; if sanitization rule evolution becomes constant churn.

---

## Decision revisit protocol

- Each category has explicit revisit triggers. When a trigger fires, a CEO-committee vote re-opens the category.
- Adding a new storage technology not listed here requires a category-expansion vote + this file's edit.
- Deprecating a chosen technology requires a vote + migration plan for existing skills that cited it.
- Vote records live at `_meta-runtime/storage-committee-*.md`.
