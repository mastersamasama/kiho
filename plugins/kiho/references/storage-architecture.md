# Storage Architecture (three-tier)

Normative spec for how kiho places data on disk. Replaces the former "markdown canonical" invariant wording in `CLAUDE.md` (which was narrower than practice — kiho already used JSONL, YAML, JSON, and plain-text sidecars for non-canonical processing before this doc was written).

The spec teaches agents **when** to reach for each tier. Tool-use is not free; a ReAct-style invocation of sqlite or an embedding cache should beat re-reading Tier 1 markdown before it is chosen. This doc names the axes of that trade-off.

## Practical matrix

The tier invariants below are abstract. For concrete per-data-class decisions — which tier each artifact lives in, what format, what path, what gatekeeper, what eviction — see `references/data-storage-matrix.md`. Per-category technology choices (TOML vs YAML, sqlite vs ripgrep, JSONL vs DuckDB, etc.) live in `references/storage-tech-stack.md` with vote records at `_meta-runtime/phase1-committee-minutes.md`. This file defines the rules; those files instantiate them.

## Non-Goals

kiho is defined as much by what its storage layer refuses to be as by what it is:

- **Not a distributed database.** No remote replication, no consensus, no leader election. A single `/kiho` turn has one agent-writer at the top.
- **Not multi-user ACID.** Single-CEO-per-turn assumption holds. No per-user transactions, no concurrent writer isolation.
- **Not a vector index owned by kiho.** Tier 3 may use embeddings per task on the agent's judgment. kiho ships no embedding daemon, loads no model at startup, maintains no global vector store.
- **Not a long-running daemon.** Tier 3 storage lifespan is bounded by the invoking `/kiho` turn unless an explicit promotion path moves it to Tier 2 or Tier 1.
- **Not a schema registry.** Tier 2 formats are chosen per task from the taxonomy below. No central schema catalog, no schema evolution protocol.
- **Not a replacement for kb-manager.** KB writes still funnel through `agents/kiho-kb-manager.md`. The tier model is orthogonal to the KB-gateway invariant.
- **Not a memory store the user hand-edits.** Tier 2 and Tier 3 surfaces are machine-written. Users edit Tier 1 (agents, skills, references) — and even there, most mutations flow through skills like `skill-create`, `skill-improve`, and `design-agent`.

## Key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 + RFC 8174) when, and only when, they appear in all capitals, as shown here.

## Background

Three independent observations converged on this spec:

1. The original "markdown canonical" invariant was narrower than actual practice. kiho already shipped `skill-invocations.jsonl`, `agent-performance.jsonl`, `config.yaml`, `.skill_id` sidecars, and JSON event files. The invariant's wording implied kiho was "markdown-only"; readers mistook this to mean no JSON at all was allowed.
2. Agents were increasingly asking whether a sqlite FTS index for semantic skill search or a small embedding cache for persona-drift scoring would violate the invariant. The honest answer is "it depends on lifespan and determinism", not a blanket ban. A decision tree beats a prohibition.
3. Karpathy's March 2026 autoresearch writing + the MemGPT / Letta line of agentic-memory research both converge on the same pattern: hot working memory managed by the agent via tool calls, with explicit eviction. kiho already has a three-tier memory frame (core / working / archival) in `references/soul-architecture.md`; this doc extends that frame to non-memory state.

## The three tiers at a glance

| Tier | Name | Examples | Lifespan | Source of truth? |
|---|---|---|---|---|
| 1 | Canonical state | `agents/*.md`, `skills/**/SKILL.md`, `references/*.md`, `CATALOG.md` | Indefinite, git-tracked | **Yes** |
| 2 | Processing artifacts | JSONL telemetry, YAML config, JSON events, `.skill_id` sidecars | Indefinite but regenerable | No — derivable from Tier 1 + observations |
| 3 | Agentic memory | sqlite FTS, embedding cache, session-scoped scratch | Turn-scoped unless promoted | No — ephemeral by default |

### Tier 1 — Canonical state

Git-tracked, human-reviewable plain text **for committee-reviewable artifacts** (souls, SKILL.md, references, KB wiki, decision records, postmortems, retrospectives). Every committee decision, every soul mutation, every skill revision lands here. Source of truth for the artifacts it covers — not for everything in the repo. Tier 2 artifacts that are primary append-only observations (telemetry, factory verdicts) are NOT regenerable from Tier 1; they are primary records protected by append-only discipline. Tier 2 artifacts that are derived (rollups, indexes, rendered views) **MUST** be regenerable from Tier 1 + Tier 2 observations. When a Tier 1 file disappears, the system is broken; when a Tier 2 or Tier 3 artifact disappears, the system recovers (possibly with telemetry loss). See `references/react-storage-doctrine.md` for the per-invocation decision tree agents use to pick the tier.

Format: markdown with YAML frontmatter. No other file formats qualify as Tier 1.

### Tier 2 — Processing artifacts

Any format the task needs — JSONL for append-only telemetry, JSON for structured events, YAML for typed config, plain text for sidecars, TOML if a library requires it, sqlite for a regenerable index. Machine-written, not hand-edited. Each artifact **MUST** declare its regeneration recipe (header comment or sibling README). Artifacts **MAY** be git-committed (config, `.skill_id` sidecars) or gitignored (telemetry, indexes).

Format: chosen per task. There is no central schema registry; each skill owns the format of its own Tier 2 outputs.

### Tier 3 — Agentic memory (on-demand)

Zero pre-declared storage. The agent reads its task, evaluates whether a ReAct-style tool call to external storage beats re-reading Tier 1 and Tier 2 artifacts, and creates storage for the duration of the task if yes. Patterns include sqlite FTS for structured queries across many markdown files, embedding caches for semantic similarity that Jaccard can't capture, or scratch files for multi-step reasoning traces.

Every Tier 3 write **MUST** carry an eviction plan stated up front (TTL, importance decay, or session scope). Every Tier 3 read **MUST** be idempotent-safe — re-running the task with an empty Tier 3 **MUST** produce an equally correct result (possibly slower).

Format: agent chooses. The agent **SHOULD** prefer formats that a later Tier 2 promotion can ingest without transformation.

## Decision tree

> **Two trees, one answer.** The 7-question tree below is the **declarative static** classification for known data kinds (use it when authoring a new skill or data class). The 4-question runtime distillation in `references/react-storage-doctrine.md §The decision tree` is what an agent silently walks before every `storage-broker` put(); both must arrive at the same tier for a given data class, and `kiho_frontmatter.validate` enforces the invariant for committee-reviewable kinds.

**Flow**: given an operation, walk the questions top-down. First YES wins.

1. **Is this a committee decision, a soul mutation, or a skill/agent/reference definition?** → Tier 1.
2. **Is this high-frequency append-only observation data (invocation counts, event traces, performance samples)?** → Tier 2, JSONL.
3. **Is this typed configuration that humans read and scripts load (harness config, canonical rubric)?** → Tier 2, YAML.
4. **Is this a stable machine-assigned identifier (skill IDs, hash sidecars)?** → Tier 2, plain-text sidecar.
5. **Is this ephemeral event data consumed and deleted within a session?** → Tier 2, JSON files.
6. **Would an agent benefit from a structured query or semantic cache for one task and then discard it?** → Tier 3, agent's choice of medium.
7. **None of the above?** → stop and ask the user or CEO before inventing a new surface.

### 8 concrete worked examples

| # | Operation | Tier | Medium | Reason | Regenerable from |
|---|---|---|---|---|---|
| 1 | Hire a new agent | T1 | `agents/<name>.md` | Canonical identity; committee-reviewed soul | — (source) |
| 2 | Record a skill invocation count | T2 | `.kiho/state/skill-invocations.jsonl` (append) | High-frequency, append-only, never edited | New observations (lossy telemetry) |
| 3 | Store harness config (depth cap, fanout cap) | T2 | `skills/core/harness/kiho/config.toml` (migrated from YAML v5.19.3) | Keyed lookup by humans and scripts, typed values | CLAUDE.md invariants + committee record |
| 4 | Give each skill a stable identity | T2 | `.skill_id` sidecar | Needed by scripts but not a spec humans author | `uuidgen` on first observation; frozen once written |
| 5 | Emit an ephemeral harness event | T2 | `.oki-team/events/pending/<ts>_<hash>.json` | Short-lived, consumed and deleted | — (ephemeral by design; loss acceptable) |
| 6 | Find semantically-similar skills across a 44-skill catalog | T3 | agent picks: Jaccard scan, sqlite FTS5, or embedding cache | Agent weighs corpus size, session budget, reuse | Tier 1 SKILL.md files |
| 7 | Remember "user prefers terse committee output" across 40+ turns | T3 | Agent-managed working memory | MemGPT-style hot context; CEO committee may promote to T1 (agent soul) | Prior turns in operations.jsonl |
| 8 | Track which agent worked which task for a weekly retro | T2 | `.kiho/state/agent-performance.jsonl` | Append-only, structured | Replay from `.oki-team/interactions/operations.jsonl` |

## Pros / cons per tier

### Tier 1 — Canonical state

- **Gain**: git history, diff review, human-editable, one-shot agent load, committee traceability.
- **Lose**: poor write throughput, no typed queries, merge conflicts on hot files, grep-only retrieval.

### Tier 2 — Processing artifacts

- **Gain**: pick-the-format freedom, high write rate, parseable by deterministic scripts, composes well with Tier 1.
- **Lose**: invisible to humans in review, must carry a regeneration recipe (or it is secretly Tier 1), easy to let drift from Tier 1 if not disciplined.

### Tier 3 — Agentic memory

- **Gain**: scales to corpus sizes markdown can't, agent decides cost/benefit per task, zero upfront infrastructure commitment, handles semantic operations markdown can't.
- **Lose**: non-determinism across sessions, requires eviction discipline, cache drift versus Tier 1, hides cost from `/kiho` turn budget.

## Guardrails — BCP 14 normative rules

Grouped by tier.

### Tier 1

- **T1-MUST-1**: Tier 1 files **MUST** be git-committable plain text (markdown, with YAML frontmatter allowed).
- **T1-MUST-2**: Writes to `<project>/.kiho/kb/wiki/` or `$COMPANY_ROOT/company/wiki/` **MUST** route through `kiho-kb-manager`. The tier model does not relax the kb-manager gateway invariant.
- **T1-MUST-NOT-1**: Tier 1 files **MUST NOT** be machine-generated without a committee-approved generator (`org-sync` writing `.kiho/state/org-registry.md` is allowed because committee-approved; ad-hoc agent scribbles are not).

### Tier 2

- **T2-MUST-1**: Tier 2 artifacts **MUST** be regenerable from Tier 1 + observations. If deleted, the system recovers correctness (possibly with information loss on telemetry).
- **T2-MUST-2**: Every Tier 2 artifact **MUST** declare its regeneration recipe — either as a header comment in the file itself, or in a sibling README or producing-script docstring.
- **T2-MUST-NOT-1**: Tier 2 artifacts **MUST NOT** be treated as source of truth by any committee decision.

### Tier 3

- **T3-MUST-1**: Tier 3 storage **MUST** have an eviction policy stated before the first write — TTL, importance decay, or session scope.
- **T3-MUST-2**: Tier 3 reads **MUST** be idempotent-safe: re-running the task with empty Tier 3 **MUST** produce an equally correct result (possibly slower).
- **T3-MUST-NOT-1**: Tier 3 **MUST NOT** be used to bypass kb-manager for KB content, and **MUST NOT** be used to write to `agents/*.md` or `skills/**/SKILL.md` directly.

### Cross-tier

- **XT-MUST-1**: Promotion T3 → T2 → T1 **MUST** follow the standard kiho committee path — CEO vote for Tier 1, scripted gate for Tier 2.
- **XT-SHOULD-1**: Agents **SHOULD** prefer the lowest tier that satisfies the task. Tier 3 is not a cheap default; its non-determinism costs audit clarity.

## Current-state inventory (2026-04-17)

Every state surface kiho currently writes, mapped to a tier:

**Tier 1 (canonical)**
- `agents/*.md` — 14 agent definitions with Soul sections
- `skills/**/SKILL.md` — 44 skill definitions
- `references/*.md` — 23 canonical specs (capability-taxonomy, topic-vocabulary, soul-architecture, committee-rules, …)
- `templates/*.md` — skill and eval templates
- `skills/CATALOG.md` — with embedded YAML routing-block; the block is machine-regenerated but committee-approved
- `.kiho/state/org-registry.md` — written by `org-sync` (committee-approved generator)
- `.kiho/state/capability-matrix.md` — written by `org-sync`
- `.kiho/agents/<name>/memory/*.md` — archival memory notes

**Tier 2 (processing)**
- `skills/**/.skill_id` — plain-text sidecars
- `skills/core/harness/kiho/config.toml` — harness config (migrated from YAML v5.19.3)
- `.kiho/state/skill-invocations.jsonl` — telemetry
- `.kiho/state/agent-performance.jsonl` — telemetry
- `.kiho/state/gate-observations.jsonl` — telemetry
- `.kiho/state/cross-agent-learnings.jsonl` — cross-agent learning queue
- `.oki-team/events/pending/*.json` — ephemeral event snapshots
- `.oki-team/interactions/operations.jsonl` — append-only op log
- `.oki-team/payloads/*` — agent response payloads
- `skills/core/planning/interview-simulate/assets/canonical-rubric.toml` — committee-approved config asset (migrated from `.yaml` in v5.19.5)

**Tier 3 (agentic memory — on-demand)**
- `<project>/.kiho/state/tier3/skill-catalog-<turn-id>.sqlite` — **first shipping Tier-3 artifact** (v5.19 Phase 4 pilot). Session-scope sqlite + FTS5 index over `skills/**/SKILL.md` frontmatter; built by `bin/skill_catalog_index.py` at CEO INITIALIZE; deleted at turn end. Serves 32 scripts under `skills/_meta/skill-create/scripts/` + `skill-find` + `kiho_rdeps` without re-parsing. See `references/data-storage-matrix.md` §8.
- capability-matrix in-memory dict (T3, session-scope) — built from `.kiho/state/capability-matrix.md` or JSONL replay per turn; no disk footprint. Documented pattern, not a committee-approved generator. See `references/data-storage-matrix.md` §3.
- Semantic embedding cache — **deferred** with explicit revisit triggers; see `references/storage-tech-stack.md` §6.

**SQLite usage**: 1 session-scope file (Phase 4 pilot). No persistent sqlite files.

## Migration impact

- `CLAUDE.md` line 31 ("Markdown canonical") is replaced by "Three-tier storage — see `references/storage-architecture.md`."
- CLAUDE.md Non-Goals "Not a runtime database" and "Not an embedding-based retrieval system" are softened — they become Tier 3 on-demand options with guardrails. The "No Postgres, no vector store" wording stays (those would be Tier 1/2 infrastructure, not on-demand).
- `skills/_meta/skill-create/scripts/similarity_scan.py` (Jaccard on shingles) is no longer the only permitted similarity primitive. It becomes one implementation of a Tier-3 capability. sqlite FTS or embedding scan are equally legal provided guardrails hold.
- `skills/core/planning/interview-simulate/scripts/score_drift.py` — its existing sentence-transformers path (previously framed as fallback to Jaccard) is fully sanctioned as a Tier-3 choice.
- `skills/_meta/skill-find/scripts/facet_walk.py` — similarly one Tier-3 implementation. Agents may construct a sqlite FTS view on demand.

**What does not change**: kb-manager as sole KB gateway; depth-3 / fanout-5 caps; single-CEO `AskUserQuestion`; session-context skill replacing PostToolUse hooks; Ralph discipline.

## Integration points

- **`CLAUDE.md`** — rewrite line 31 invariant, soften lines 9 and 11 Non-Goals, add one-line reference to this file.
- **`references/soul-architecture.md`** — cross-reference Tier 1 / core-memory mapping (soul lives in Tier 1).
- **`references/karpathy-autoresearch-loop.md`** — cross-reference Tier 3 keep-or-discard discipline.
- **`references/ralph-loop-philosophy.md`** — single-`/kiho`-turn bounds Tier 3 lifespan by default.
- **`references/deep-research-protocol.md`** — Tier 3 scratch indexes permitted during research-deep.
- **`agents/kiho-kb-manager.md`** — Tier 1 wiki-gateway role made explicit.
- **`agents/kiho-ceo.md`** — authorized to promote T3 → T1 via committee.
- **`references/pattern-compliance-baseline.md`** — future addition: "Storage declaration" pattern where every SKILL.md that reads or writes state **SHOULD** declare the tier in its Outputs or Non-Goals section.

## Changelog

| Date | Version | Change |
|---|---|---|
| 2026-04-17 | 1.0 | Initial three-tier spec. Replaces the former "markdown canonical" invariant in `CLAUDE.md`. Documented current-state inventory with 0 Tier-3 artifacts and an opening for sqlite FTS / embedding caches under guardrails. |
| 2026-04-18 | 1.1 | v5.19 Phase 2. Added §"Practical matrix" cross-reference to `data-storage-matrix.md` + `storage-tech-stack.md`. Updated Tier-3 inventory to list the skill-catalog-sqlite pilot + capability-matrix in-memory dict pattern + semantic-embedding deferral. Invariants T1/T2/T3 MUST rules unchanged. |
