# Skill authoring standards for kiho

This file is loaded by every skill-creating skill (`skill-create`, `skill-learn`, `skill-derive`, `design-agent` Step 4d) and by the CEO before writing any project-level skill. Pulled from Anthropic's official best-practices guide with kiho-specific additions. **Updated v5.11 (2026)** — incorporates the 2026 SKILL.md open standard, OWASP Agentic Skills Top 10, and the expanded optional frontmatter spec. **v5.16 adds** the hierarchical walk-catalog + closed 8-verb capability taxonomy + controlled topic vocabulary architecture; token-budget framing is demoted and attention-budget framing (Gate 22 candidate-set ceiling) takes over.

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals. Lowercase "must", "should", "do not" remain informal prose guidance.

## Non-Goals

skill-authoring-standards is defined as much by what it refuses to prescribe as by what it does. These are things that could reasonably be in scope but are explicitly not:

- **Not a runtime enforcement spec.** The rules below are enforced at skill-create time via the 24-gate pipeline. This file describes the rules; the gate scripts enforce them. Runtime (post-registration) behavior is not governed here.
- **Not an LLM prompt-engineering guide.** This is a structural specification for SKILL.md files and their validation. Prompt crafting for skill bodies (tone, voice, format) is left to the author.
- **Not a replacement for CLAUDE.md invariants.** CLAUDE.md declares kiho architectural invariants (depth cap 3, fanout cap 5, single entry point, CEO-only user interaction, three-tier storage per `references/storage-architecture.md`). This file incorporates them by reference but does not restate them.
- **Not a token-budget-driven system.** v5.16 reframes discoverability around attention budget (Gate 22: candidate-set after facet filtering ≤10). Gate 3 body-length check is demoted to `warn`. Gates 15 and 16 remain as platform-constraint checks, not organization mechanisms.
- **Not a single-tier standard.** kiho has four lifecycle states (draft / active / deprecated / retired). This file describes the rules for each; it does not mandate a single set of rules for all states.

## Contents
- [Core principles](#core-principles)
- [Frontmatter rules](#frontmatter-rules)
- [Optional frontmatter fields (2026)](#optional-frontmatter-fields-2026)
- [Description effectiveness rules](#description-effectiveness-rules)
- [Body rules](#body-rules)
- [Progressive disclosure patterns](#progressive-disclosure-patterns)
- [Scripts vs inline code](#scripts-vs-inline-code)
- [Versioning and lifecycle](#versioning-and-lifecycle)
- [Evals schema](#evals-schema)
- [Security (OWASP Agentic Skills Top 10)](#security-owasp-agentic-skills-top-10)
- [The Lethal Trifecta rule](#the-lethal-trifecta-rule)
- [Ten validation gates](#ten-validation-gates)
- [Iterative description improvement](#iterative-description-improvement)
- [v5.14 additions](#v514-additions)
- [v5.15 additions — dependencies and similarity](#v515-additions--dependencies-and-similarity)
- [Anti-patterns](#anti-patterns)
- [Checklist before promoting DRAFT to ACTIVE](#checklist)

## v5.21 additions — cycle-phase-aware skill authoring

After v5.21, lifecycles run through `cycle-runner` (the kiho kernel) using declarative TOML templates in `references/cycle-templates/`. Atomic skills MAY be invoked directly (legacy path) OR as a phase entry inside a cycle template. New and existing skills MUST observe these rules to remain cycle-compatible.

### Cycle-aware note

Every skill that is wired into at least one cycle template (or is intended to be) MUST add a v5.21 cycle-aware note near the top of its body — typically as the second paragraph after the H1. Format:

> **v5.21 cycle-aware.** This skill MAY be invoked atomically OR as the `<phase-id>` phase entry in `references/cycle-templates/<template-id>.toml`. When invoked from cycle-runner, the cycle's `index.toml` is the SSoT for lifecycle position; this skill's local artifact (e.g., `<artifact-name>`) remains the authoritative record for the artifact it produces. Atomic invocation remains supported.

Skills that are NEVER cycle phases (e.g., `memo-send`, `memory-write`, `storage-broker`, `kb-search` — pure atomic infrastructure) need no such note.

### Output contract for cycle phases

A skill invoked as a cycle phase entry MUST return its structured output as a JSON-parseable dict matching the template's `output_to_index_path` schema fields. The cycle-runner writes those fields into `index.<output_path>.<field>` after the skill returns.

If a skill produces side-artifacts (e.g., `committee.md`, `incident.md`), those are still authoritative for their own kind; the JSON output exists to give the cycle-runner the structured fields it needs to evaluate `success_condition`. Common pattern: return `{ <primary_artifact_ref>: "md://...", <count_field>: N, <status_field>: "..." }`.

### Ability registration

The skill MUST be registered under exactly one of the 7 verbs in `references/core-abilities-registry.md`. If a skill spans multiple verbs (e.g., `postmortem` is both build and validate), pick the verb that best matches its primary function and register secondary uses as separate row entries. Templates that declare a phase using the skill MUST set `core_ability` to a verb under which the skill is registered.

Adding a new ability requires a CEO-committee vote. Adding a new skill under an existing ability is a normal authoring commit.

### Template authoring

Every new lifecycle gets a TOML template in `references/cycle-templates/<id>.toml` that conforms to `skills/_meta/cycle-runner/references/template-dsl.md`. Templates go through `python bin/cycle_runner.py validate-template --path <path>` BEFORE PR review. The validator enforces all 12 invariants documented in the DSL spec.

Templates are themselves treated as skill artifacts for committee review purposes — they go through skill-intake → skill-factory → skill-critic gates using the same SOP.

### When the skill writes vs the cycle-runner writes

| Field | Writer | Why |
|---|---|---|
| Skill's primary artifact (e.g., `incident.md`) | The skill | The skill owns its artifact's content and validation rules. |
| `index.<phase>.<field>` (per template's `output_to_index_path`) | cycle-runner, using the skill's returned JSON | Index is the cycle's SSoT; only cycle-runner writes index.toml. |
| `index.meta.phase` / `index.meta.status` | cycle-runner only | Lifecycle position is owned by the kernel. |
| `handoffs.jsonl` | cycle-runner only | Append-only audit trail, single writer. |
| `cycle-events.jsonl` | cycle-runner only | Org-wide telemetry stream, single writer. |
| Skill's own telemetry (e.g., `skill-invocations.jsonl`) | The skill | Per-skill telemetry remains under the skill's control. |

### What changes for existing skills

For Wave 5 migration, existing skills add the cycle-aware note (5 lines) and verify their structured output JSON matches the template's `output_to_index_path` schema. No behavior change required. Skills that don't yet have a JSON output mode can stay invocation-only; the cycle template author will handle the output capture in their phase configuration (using `__hook_only__` if needed).

---

## v5.14 additions

This section consolidates the v5.14 skill-authoring rules. Each item below is grounded in a 2026 primary source cited in `kiho-plugin/references/v5.14-research-findings.md`.

### Evaluator-generator separation (H5)

Gate 11 transcript review is ALWAYS performed by a fresh skeptical evaluator subagent — never the agent that authored the skill, never the agent that ran the scenario. The evaluator's system prompt starts with: *"Uncertainty defaults to FAIL. Praise is affirmative and must be earned."* This prevents the leniency bias documented in Anthropic's Mar 24 2026 harness-design post.

### Non-monotonic iteration (H5)

When `skill-create`'s run_loop produces multiple iterations, the best iteration is NOT necessarily the most recent. Compare each new iteration against the current historical best (via the comparator sub-agent), and if the new iteration loses, preserve the current best unchanged. `run_loop.py --mode summarize` walks every `comparisons/*.json` and reports `non_monotonic_winner: true` when this happens.

### Capability vs regression eval split (H1)

Every skill's eval suite is split into two named buckets:

- `evals/capability/` — iterative, free to mutate, gated on F1 / balanced accuracy, retired on saturation or non-discrimination
- `evals/regression/` — frozen, populated only after first ACTIVE promotion, gated on raw pass rate ≥ 95%, retired only by CEO committee

Detailed semantics in `skills/_meta/skill-create/references/capability-regression-split.md`.

### Isolation manifest (Gate 12)

Every skill declares its filesystem/env-var/network touch points via `scripts/isolation_manifest.py`. The Gate 11 eval harness cleans these before each trial. Skills with side effects must include a `## Security` section documenting the cleanup procedure.

### Grader review (Gate 13)

Every 11-gate run samples 10% of graded transcripts per assertion via `scripts/grader_review.py` and produces a review worksheet for kiho-kb-manager to audit. If >10% of reviewed rows show disagreement with the grader's verdict, the skill routes back to Step 9 — the problem is in the grader, not the skill.

### Claims extraction (Gate 11 evaluator addendum)

The evaluator extracts a `claims[]` array from each transcript with implicit factual / process / quality claims. Factual claims verify against tool outputs; process claims verify against the tool-call log; quality claims are marked `subjective`. **Uncertainty defaults to FAIL.** >50% unverifiable claims on a transcript auto-fail Gate 11 with `status: too_many_unverifiable_claims`. Full protocol in `skills/_meta/skill-create/references/claims-extraction.md`.

### Security: 8-category taxonomy + trust tiers (Gate 9, H4)

Gate 9 now enforces the **Snyk 8-category taxonomy** (prompt injection, malicious code, suspicious downloads, credential handling, hardcoded secrets, third-party content exposure, unverifiable dependencies, direct money access). Every skill carries `metadata.trust-tier: T1|T2|T3|T4` with CEO-only promotion past T2. Script-bearing skills apply the **2.12× rule** (extra eval + extra transcript review + tighter token budget). Substantial content changes trigger **delta-consent** auto-downgrade. **Do not attempt AST-based malicious intent detection** — three independent papers confirm it's infeasible. Detail in `skills/_meta/skill-create/references/security-v5.14.md`.

### Catalog-fit + budget + compaction (Gates 14, 15, 16, H3)

- **Gate 14:** new skill description must overlap its parent catalog domain's `routing-description` by ≥1 substantive keyword (`scripts/catalog_fit.py`).
- **Gate 15:** total ACTIVE description chars ≤ 90% of 1%/8k char budget; per-skill combined `description + when_to_use` ≤ 1,536 chars (`scripts/budget_preflight.py`).
- **Gate 16:** projected post-compaction 25k-token ceiling across concurrently-loaded skills; warn when top-N recent-invocation set exceeds 80% (`scripts/compaction_budget.py`).

### when_to_use field rule

`when_to_use` is a conditionally-required frontmatter field. Required when `description` is below 200 chars; optional otherwise. Combined `description + when_to_use` MUST stay under 1,536 chars regardless.

### intended-roles metadata field (Thread 10)

Every skill declares `metadata.intended-roles: [ceo, dept-lead, ic-eng-backend, ...]` listing which kiho agent roles are expected to invoke it. Used by Gate 14 (catalog-fit sanity check) and by the fragmentation detector that runs on skill promotion. A skill whose description overlaps an existing ACTIVE skill but differs only in `intended-roles` is flagged for CEO review as a potential deduplication target.

### Subagent skill preloading caveat

When a sub-agent's frontmatter has a `skills:` list, Claude Code injects the FULL skill content at sub-agent startup — not lazy-loaded like the main-agent Skill tool. For kiho's depth-2 sub-agents with pre-loaded portfolios, this eats the token budget upfront. Minimize the portfolio in sub-agent frontmatter and rely on just-in-time Skill tool invocation for the rest.

### skills-ref CLI cross-check (Gate 1)

Gate 1 frontmatter validation runs `skills-ref validate ./draft-skill` from `agentskills/agentskills` as a defense-in-depth cross-check against kiho's own `quick_validate.py`. The two validators catch different errors; both must pass.

### Eval-driven skill development (8-step pattern)

Anthropic's Jan 9 2026 "Demystifying Evals for AI Agents" describes an 8-step eval-driven development pattern that skill authors should follow:

1. Start with 20–50 real failures (don't invent edge cases from scratch)
2. Convert manual tests to automated early
3. Write unambiguous specs that can be graded programmatically
4. Balance positive/negative cases at the eval level
5. Build isolated harnesses (Gate 12)
6. Design appropriate graders (deterministic / model-based / human)
7. Review transcripts, not just scores (Gate 11 + claims extraction)
8. Monitor saturation — stop iterating when improvements plateau

This pattern is guidance for skill authors; the 16 validation gates remain the hard pre-ship checks.

### kiho vs Anthropic skill-creator divergences

kiho's skill-create has explicit divergences from `anthropics/skills/skill-creator`:

- kiho has **16 explicit gates**; skill-creator relies on human review
- kiho enforces **OWASP-style security scanning** at Gate 9; skill-creator does not
- kiho has **versioning + lifecycle** tracking; skill-creator skills don't carry version metadata
- kiho requires **CEO committee promotion** from DRAFT to ACTIVE; skill-creator skills go ACTIVE on first save
- **Shared patterns**: train/test split, 1024-char description limit, topic-based bodies, progressive disclosure tiers, one-level-deep references, analyzer/comparator pair (v5.14)

These divergences are intentional. Do not remove them to "align with upstream" — they encode kiho's multi-agent harness requirements that the upstream skill-creator doesn't face.

## v5.16 additions — hierarchical walk-catalog + capability taxonomy + faceted retrieval

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this section are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174).

v5.16 replaces token-budget framing with attention-budget framing. The three primitives and six new gates are grounded in `kiho-plugin/references/v5.16-facet-retrieval.md` and `references/v5.16-research-findings.md`. Full architectural rationale and migration playbook live there; this section is the normative rulebook for skill authors.

### Primitive 1 — Hierarchical walk-catalog (max depth 3)

`skills/CATALOG.md` is a **domain index only** (~50 lines), pointing at per-domain sub-catalogs. Each domain **MUST** split into sub-domains when it exceeds ~10 skills (currently applied to `core`, split into `harness/`, `hr/`, `inspection/`, `knowledge/`, `planning/`). Maximum tree depth is 3: `top-level → domain → sub-domain → skill`.

- Authors **MUST NOT** nest deeper than depth 3.
- Authors **MUST NOT** create ad-hoc top-level domains outside the canonical five (`_meta`, `core`, `kb`, `memory`, `engineering`). New domains require CEO-committee approval documented in the routing block.
- Moving a skill between sub-domains is a directory rename; `.skill_id` sidecars preserve stable identity. Skill IDs **MUST NOT** change on a sub-domain move.

### Primitive 2 — Closed 8-verb capability taxonomy

Every skill **MUST** declare exactly one `metadata.kiho.capability` verb from the closed set in `kiho-plugin/references/capability-taxonomy.md`:

```
create | read | update | delete | evaluate | orchestrate | communicate | decide
```

- Authors **MUST NOT** invent new verbs in frontmatter. Gate 20 rejects out-of-set values.
- Classification **MUST** be by *primary effect*, not secondary operations. Edge cases are escalated to CEO committee for resolution.
- Adding a new verb to the closed set requires a CEO-committee vote with a rationale citing 3+ pending skills that genuinely cannot map to any existing verb.

Grounding: Kubernetes API verbs (7 canonical operations), SQL DML (4), HTTP REST (4-5). 8 is the empirical sweet spot across these precedents.

### Primitive 3 — Controlled topic vocabulary + faceted retrieval

Every skill's `metadata.kiho.topic_tags` entries **MUST** come from `kiho-plugin/references/topic-vocabulary.md`. Seed size at v5.16 is 18 tags; expected growth is 1-3 tags per quarter via CEO-committee vote.

- Authors **MUST NOT** use free-form tags. Gate 21 rejects out-of-vocab values.
- Tags describe what the skill is *about*, not what operation it performs (capability is the operation axis).
- Adding a new tag to the vocabulary requires a CEO-committee vote.

Grounding: Library of Congress subject headings, arXiv classifications, WordNet synsets — every mature taxonomy project converges on controlled vocabularies after free-form tags fail.

`skill-find` uses a deterministic 5-step facet walk via `skills/_meta/skill-find/scripts/facet_walk.py`:

1. Tokenize query (stop-word removal).
2. Infer capability via keyword → verb mapping (deterministic dict).
3. Infer domain by keyword overlap with routing-descriptions; winner must beat runner-up by ≥2×.
4. Infer topic tags by exact-match against the vocabulary.
5. Walk routing block, intersect by applied facets, enforce ≤10 candidate-set ceiling.

If the candidate set exceeds the ceiling, `facet_walk.py` emits `status: underspecified` with narrowing hints. Authors **MUST NOT** bypass the ceiling by loosening facets — the ≤10 cap is the attention budget.

### Gate table (v5.16 additions)

| Gate | Script | Tier | Purpose |
|---|---|---|---|
| 19 Routing sync | `routing_sync.py` | error | Walk-catalog coherence (ghost/orphan/mismatch/deprecated entries) |
| 20 Capability declared | `capability_check.py` | error | Closed 8-verb set enforcement |
| 21 Topic vocabulary | `topic_vocab_check.py` | error | Controlled vocabulary enforcement |
| 22 Candidate-set budget | `candidate_set_budget.py` | error | **Primary attention gate**: worst-case facet-walk candidate set ≤10 |
| 23 Trigger uniqueness | `trigger_uniqueness.py` | error | Pairwise Jaccard on trigger phrases ≥0.70 blocks |
| 24 Agent portfolio density | `agent_density.py` | warn | Per-capability + per-domain density per agent |

**Gate 3 demotion.** Body token budget (was error in v5.14-v5.15.2) is demoted to `warn` in v5.16. Body length is a kiho authoring preference, not a platform constraint. **Gate 22 is the real attention gate.**

**Token gates that stay.** Gates 15 (budget pre-flight) and 16 (compaction budget) remain as platform-constraint checks. Claude Code imposes hard 8k-char and 25k-token ceilings that any skill system must respect; these are orthogonal to the kiho organization mechanism.

### Why attention budget replaces token budget

Token count is a proxy for attention load, but at scale it fails in both directions:

- **False negatives**: a 3k-token skill sitting in a cluster of 12 near-duplicates is unselectable even though it's small.
- **False positives**: a 6k-token skill that cleanly discriminates against every other skill is trivially selectable even though it's large.

The failure mode at |S|>30 is *the agent cannot decide which skill to pick*, not *the context overflowed*. Gate 22 measures candidate-set size after facet filtering — the actual attention load the agent faces when picking a skill. This is the metric that scales to 1000+ skills without drift.

Grounding: arXiv 2601.04748 §5.2 (selection accuracy plateau at |S|≤20, collapse at |S|≥30, ~20% accuracy at |S|=200 on flat catalogs) + §5.3 (semantic confusability dominates skill count — two similar skills hurt more than two extra unrelated skills). Full reference at `kiho-plugin/references/v5.16-research-findings.md`.

### kiho is NOT a token-budget-driven organization system

- **MUST NOT** use body length as the primary selection criterion. Short bodies don't help discoverability if the facets are wrong.
- **MUST NOT** skip facet filtering to save tokens. Lexical scoring over the whole catalog is strictly worse than facet-filtered scoring at any catalog size.
- **MUST NOT** conflate Gate 15/16 (platform constraints) with Gate 22 (attention gate). They measure different things; both apply.

## v5.15 additions — dependencies and similarity

This section consolidates the v5.15 skill-authoring rules. Each item is grounded in a 2026 primary source cited in `kiho-plugin/references/v5.15-research-findings.md`. v5.15 adds three mechanical primitives: a pre-create similarity gate, a forward-only dependency format, and an on-demand reverse-lookup script.

### Gate 17 — novel contribution similarity scan (H3)

Before a draft skill is registered, `skills/_meta/skill-create/scripts/similarity_scan.py` compares its description against every existing skill's description via Jaccard on unigrams + bigrams (after stop-word removal). Thresholds:

- `Jaccard ≥ 0.60` → **block** (exit 1, `status: near_duplicate`). Author is told to run `skill-improve` on the top match instead of creating a new skill.
- `0.30 ≤ Jaccard < 0.60` → **warn** (exit 0, `status: related_review`). Author must acknowledge the overlap in the committee proposal.
- `Jaccard < 0.30` → **pass** (`status: novel`).

A CEO-only `--force-overlap` override exists for legitimate edge cases (two skills that share vocabulary but serve opposite operations — e.g., `skill-improve` and `skill-deprecate`). Forced overrides require a unanimous committee vote and are logged to `skill-invocations.jsonl`.

Gate 17 is the full-catalog complement to Gate 14 (catalog-fit), which only checks parent-domain overlap. The two gates address different failure modes — Gate 14 catches mis-categorization, Gate 17 catches redundancy. Both run; neither replaces the other.

Grounding: arXiv 2601.04748 §5.2, §5.3 (semantic confusability drives the phase transition — two similar skills hurt more than two extra unrelated skills); Nelhage fuzzy-dedup; arXiv 2411.04257 LSHBloom. Full reference at `skills/_meta/skill-create/references/novel-contribution.md`.

### Forward-only dependency declarations (H2)

Five namespaced fields under `metadata.kiho.*` express every dependency kiho tracks:

```yaml
metadata:
  kiho:
    requires: []          # hard deps — skill fails if missing
    mentions: []          # soft refs — body links but doesn't require
    reads: []             # KB page paths this skill reads
    supersedes: []        # skills this one replaces (managed by skill-deprecate)
    deprecated: false     # flipped to true by skill-deprecate
    # superseded-by: sk-NNN  # set by skill-deprecate; omit when active
```

**All declarations are forward-only.** A skill declares what IT needs; nothing declares what depends on IT. The reverse query is computed on demand by `bin/kiho_rdeps.py` — there is no on-disk reverse index. This matches the pattern used by every mature package manager (`pnpm why`, `cargo tree --invert`, `go mod why`, `bazel rdeps`) and by Kubernetes `ownerReferences` — forward edges are authoritative, reverse views are computed, never persisted.

**No top-level `requires:` field.** Under no circumstances may a skill declare `requires:` at the top level of its frontmatter. Claude Code issue #27113 (declarative dependencies) was closed "not planned"; agentskills RFC #252 (signature field) was rejected on the precedent that "structural metadata belongs outside the skill file when possible." kiho follows the same precedent: dependency metadata lives inside `metadata.kiho.*` to stay spec-compliant with agentskills.io and to avoid collisions with future upstream fields. Gate 2 frontmatter validation rejects top-level `requires:` as a spec violation.

### `metadata.kiho.requires` vs `metadata.kiho.mentions` semantics

- **`requires`** is a **contract**. A skill that declares `requires: [sk-013]` cannot execute its procedure if `sk-013` is absent from the catalog. The main-agent harness does not enforce this at invocation time (kiho has no runtime resolver), but `skill-deprecate` does enforce it at **evolution time**: a skill cannot be deprecated while any other skill hard-requires it. This makes dependencies real where it matters — at the point where breaking them would cause silent downstream damage.
- **`mentions`** is an **audit trail**. A skill that declares `mentions: [sk-024]` has a body that links to `sk-024` (e.g., "see also `skill-find`") but does not execute it. `kb-lint` reports stale mentions when a referenced skill is deprecated, but does not block the consumer skill from running.

Authors should default to `mentions` for soft refs and escalate to `requires` only when the dependency is genuinely load-bearing. Over-declaring `requires` creates false deprecation blocks.

### On-demand reverse lookup via `bin/kiho_rdeps.py` (H5)

`kiho_rdeps` is the reverse-query tool. Given a skill target (slug, sk-ID, or path), it walks six forward-edge sources and reports every consumer:

1. `metadata.kiho.requires` across every SKILL.md
2. `metadata.kiho.mentions` across every SKILL.md
3. `skills: [...]` arrays in `agents/*.md` frontmatter
4. `parent_of: [...]` lists in `skills/CATALOG.md` routing block
5. Wiki-style `[[slug]]` mentions in SKILL.md body prose
6. `.kiho/kb/wiki/skill-solutions.md` back-references (best-effort, per-project)

Every invocation walks the tree fresh — there is no cached reverse index. At 37 skills the walk runs in <500ms; at 200 skills still <3s by estimate. If performance becomes a concern, add in-memory per-invocation caching inside the script; do **not** persist to disk. Staleness-vs-complexity is the entire reason every mature package manager refuses to persist reverse indexes.

`skill-improve` Step 0 consults `kiho_rdeps` before proposing a diff, so authors see the downstream impact of their changes before the diff is written. `skill-deprecate` requires the consumer list as a hard pre-check: any consumer under `hard_requires` blocks the deprecation until that consumer is migrated.

### Deprecation shim pattern (H4, H5)

`skill-deprecate` retires a skill by rewriting its body to a one-paragraph "use `<replacement>` instead" redirect. The file stays present; the slug still resolves; consumers that still reference the deprecated name land on a clean migration banner instead of a missing-skill error. This is the **deprecation shim pattern** borrowed from npm `deprecate` and cargo rename conventions.

Required fields on a shim:

- `metadata.lifecycle: deprecated` (canonical top-level flag)
- `metadata.kiho.deprecated: true` (namespaced mirror)
- `metadata.kiho.superseded-by: <slug>` (replacement pointer, required — no empty values)

Both `deprecated` flags must be present and must agree. A mismatch is flagged by `kb-lint` as `inconsistent_deprecation`.

Consumer migration happens lazily via `skill-improve` on each consumer. `kb-lint` tracks migration debt through a `stale_reference` check — any skill that still carries `metadata.kiho.requires: <deprecated-slug>` is flagged. When stale reference count > 5, `kb-lint` exits 1 and forces the CEO committee to address the backlog. **kb-lint does not auto-fix stale references** because migration often requires semantic judgment. Full protocol at `skills/_meta/skill-create/references/deprecation-shim.md` and `skills/_meta/skill-deprecate/SKILL.md`.

### What v5.15 explicitly does NOT add

- **No precomputed reverse-dependency index on disk.** H5. Every mature ecosystem walks forward edges on demand.
- **No embedding-based similarity search.** H1/Q2. Requires a daemon or rebuild step; non-deterministic; non-explainable. MinHash + Jaccard is the 2024-2026 industry standard for markdown-scale dedup.
- **No mechanical "merge two skills" primitive.** H4. Literature confirms merging skills is an open problem. Gate 17 provides mechanical overlap *inputs*; humans write the merged third artifact.
- **No AST parsing of SKILL.md bodies for semantic dep extraction.** arXiv 2604.02837 §4 rejects this category outright. Regex for wiki-link mentions is fine; intent extraction is not.
- **No dependency lockfile.** There is exactly one version of each skill on disk.
- **No auto-rename cascade.** Renaming is a CEO committee decision; tools assist but do not automate.
- **No retroactive `requires:` annotation of existing 37 skills.** `kiho_rdeps` works even when forward declarations are absent by falling back to agent portfolios, CATALOG `parent_of`, and wiki-link scans. Annotation happens lazily.

### kiho vs upstream (v5.15 delta)

- kiho has a **pre-create similarity gate**; upstream `anthropics/skills/skill-creator` does not.
- kiho has **forward-only `metadata.kiho.*` dependency declarations**; upstream has nothing analogous (Claude Code issue #27113 closed "not planned").
- kiho has an **on-demand reverse-query script** (`kiho_rdeps.py`); upstream has no reverse-query tool at all.
- kiho has a **deprecation shim workflow** with consumer review; upstream has no deprecation operation.

These are additive divergences — v5.15 does not break any v5.14 or upstream-compatible behavior. A skill authored under upstream `skill-creator` can still be imported into kiho without rewrites; the `metadata.kiho.*` block is optional.

### Exit-code convention for kiho scripts (v5.15.2)

Every Python script under `kiho-plugin/skills/**/scripts/` and `kiho-plugin/bin/` **MUST** follow the kiho exit-code convention. The convention was audited in Apr 2026 and confirmed to be already followed by every v5.14+ script; v5.15.2 elevates it from de facto practice to a normative requirement.

The key words MUST, MUST NOT, SHOULD, SHOULD NOT in this section are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.

**The four codes:**

| Code | Semantic | When to use |
|---|---|---|
| **0** | success / pass / novel | The script's primary operation completed and the check passed. No output required beyond the normal JSON/stdout payload. |
| **1** | policy violation / block / gate fail | The script's primary operation completed but a policy check failed. The caller can retry after fixing the input. Example: Gate 17 blocks with Jaccard ≥ 0.60. |
| **2** | usage error / bad arguments / missing input | The caller invoked the script incorrectly — missing required argument, unreadable input file, domain not found in CATALOG. The caller has a bug; fix the invocation. |
| **3** | internal error / unexpected exception | The script encountered a state it did not handle: filesystem error, unhandled exception, invariant violation. Report as a kiho bug. |

**Normative rules:**

- Every kiho script MUST return 0 on success.
- Every kiho script MUST return 1 and 1 only when a policy check fails. Bare failures that are not policy violations (e.g., file not writable) are tier 2 or 3, not tier 1.
- Every kiho script MUST return 2 for usage errors, matching Python `argparse` default.
- Every kiho script SHOULD catch unexpected exceptions in `main()` and return 3 rather than letting the exception propagate with an implicit exit 1.
- Every kiho script MUST NOT use exit codes ≥125 (POSIX reserves 125-128 for shell semantics and Docker reserves 125-127 for container lifecycle).
- Every kiho script MUST NOT use exit code 101 (Rust panic).
- New exit codes outside 0/1/2/3 MUST NOT be introduced without CEO-committee authorization. This is a v6.0-scale change that requires auditing every caller script.
- Two sibling kiho scripts MUST NOT assign different semantics to the same exit code.

**Documentation requirement:**

Every kiho script's module docstring MUST include an "Exit codes" section listing the codes it uses with concrete per-script meanings. Scripts that never encounter a tier-3 case (internal error) may omit it and state "not reached" in the docstring.

```python
"""
<script name> — <one-line description>

...

Exit codes:
    0 — <script-specific success>
    1 — <script-specific policy violation, or "not used" if none>
    2 — <script-specific usage error>
    3 — <script-specific internal error, or "not reached">
"""
```

**Rationale:** CI pipelines and `skill-create` shell out to dozens of kiho scripts. A consistent exit-code convention lets the caller use a single dispatch (`case $? in 0)...; 1)...; 2)...; 3)...;`) instead of special-casing every script. Grounding: kiho v5.15.2 research pass Pattern 9 — no external standard is canonical at the "policy violation vs usage error" distinction kiho needs, so kiho prescribes its own 4-code convention compatible with POSIX, Python argparse, and GNU coreutils.

**Audit status (Apr 2026):** all 13 v5.14+ scripts under `skills/_meta/skill-create/scripts/` plus `bin/kiho_rdeps.py` and `bin/catalog_gen.py` verified compliant with 0/1/2/3. `bin/org_sync.py` and `bin/session_context.py` (pre-v5.14) are not yet audited; they will be graduated on touch per the lazy-migration rule in `references/skill-authoring-patterns.md` §"Review checklist".

## Core principles

**Concise is key.** The context window is a shared resource. Only add context Claude doesn't already have. Challenge each sentence: does this justify its token cost? If Claude already knows what a PDF is, don't explain PDFs.

**Set appropriate degrees of freedom.** High freedom (text instructions) when multiple approaches work. Medium freedom (parameterized scripts) when a preferred pattern exists. Low freedom (specific scripts, few parameters) for fragile sequences. Match specificity to task fragility.

**Topic-based body, not step-based narration.** Organize the body as reference material (Overview → Quick start → Common tasks → Anti-patterns), not as a walkthrough (Step 1 → Step 2 → Step 3). Claude reads for reference, not to be shepherded.

**Imperative language.** "Read the file." "Call kb-manager with op=add." Not "You should read" or "I can help you".

## Frontmatter rules

**Two fields are required:**

```yaml
---
name: <skill-name>
description: <one or two sentences combining WHAT and WHEN>
---
```

**`name` rules:**
- Max 64 chars, lowercase, numbers, hyphens only.
- Cannot contain `anthropic` or `claude`.
- Gerund form preferred (`processing-pdfs`, `managing-kb`) but compound nouns accepted for brand names (`kiho-setup`, `kb-manager`).
- Avoid vague names: `helper`, `utils`, `tools`.
- Must match the skill's parent directory name exactly.

**`description` rules** (see also [Description effectiveness rules](#description-effectiveness-rules)):
- Max 1024 chars. Write in **third person** always. Never "I can help" or "You can use this".
- Combine WHAT the skill does AND WHEN to use it in the same paragraph.
- Use specific trigger phrases — include phrases users might literally type.
- Be "pushy" about discoverability: if there's any chance the user's phrasing matches this skill, say so explicitly.
- NEVER put "when to use this skill" inside the body — the body only loads AFTER triggering, so trigger hints there are invisible to the router.

**Gold-standard description:**
```yaml
description: Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting text/tables from PDFs, combining or merging multiple PDFs into one, splitting PDFs apart, rotating pages, adding watermarks, creating new PDFs, filling PDF forms, encrypting/decrypting PDFs, extracting images, and OCR on scanned PDFs to make them searchable. If the user mentions a .pdf file or asks to produce one, use this skill.
```

It names the skill's domain up front, enumerates concrete actions, then lists explicit triggers.

**Not-good description (avoid):**
```yaml
description: Helps with documents
```
```yaml
description: I can help you manage your knowledge base
```

## agentskills.io open standard (2026)

The canonical open standard at `agentskills.io/specification` defines **6 top-level frontmatter fields** — everything else should live under `metadata:` to stay compatible with the standard.

| Canonical field | Required | Purpose |
|---|---|---|
| `name` | yes | Skill identifier, kebab-case, 1–64 chars |
| `description` | yes | Trigger-heavy description, 1–1024 chars |
| `license` | no | SPDX identifier or bundled license reference |
| `compatibility` | no | Environment requirements (1–500 chars) — e.g., "requires Python 3.11+, git, tiktoken" |
| `metadata` | no | Arbitrary key-value extensions — kiho extensions live here |
| `allowed-tools` | no | Space-separated tool-allowlist patterns (experimental) |

**Fields NOT in the standard (do not add as top-level):**
- `cache-control`, `priority`, `deprecated_at`, `required_versions`, `frequency_tier` — none of these are in the agentskills.io spec. If you see them in a kiho skill, they're speculative additions and should be moved under `metadata:` or removed.

**kiho-specific fields under `metadata:`**
- `version` — semver starting at 0.1.0
- `lifecycle` — draft | active | deprecated
- `topic_tags` — list, for capability-gap matching
- `requires` — list of sk-NNN IDs (informational, not runtime-enforced)
- `created_by`, `created_at` — provenance
- `validation_gates_passed` — list of integers (1..11)
- `security_risk_tier` — low | medium | high | trifecta
- `lethal_trifecta_check` — passed | warning | blocked
- `iterative_description_score`, `iterative_description_loops` — Phase 1 results
- `train_accuracy`, `test_accuracy`, `overfitting_warning` — Phase 2 results (v5.13)
- `gate_11_min_mean` — Gate 11 transcript review minimum (v5.13)

Claude Code extends the agentskills.io standard with additional optional top-level fields documented below ("Optional frontmatter fields (2026)"). These are Claude Code-specific and are fine to use at the top level for skills running in that environment.

## Optional frontmatter fields (2026)

The 2026 SKILL.md spec documents these optional fields. Use them deliberately — do not add fields without a concrete reason.

| Field | Type | When to use | Rationale |
|---|---|---|---|
| `version` | semver string | Always set for DRAFT/ACTIVE/DEPRECATED lifecycle tracking | Supports drift detection and regression audit |
| `lifecycle` | `draft \| active \| deprecated` | Always for kiho-created skills | DRAFT → ACTIVE requires CEO committee gate |
| `disable-model-invocation` | bool, default false | Set `true` for workflow skills with side effects that must be user-triggered (e.g., deploy, commit) | Prevents auto-invocation of destructive operations |
| `user-invocable` | bool, default true | Set `false` for knowledge-only skills that Claude should read but users should not invoke via `/` menu | Cleans up the user-visible slash command list |
| `allowed-tools` | space-separated list | When the skill needs scoped tool pre-approval (e.g., `Bash(git add *) Bash(git commit *)`) | Reduces permission friction without granting wildcard access |
| `argument-hint` | string | When the skill takes arguments on invocation (e.g., `[issue-number]`) | Better `/skill-name` autocomplete |
| `model` | model name | When a skill must run on a specific model (rare) | Override session model for this skill only |
| `effort` | `low \| medium \| high \| max` | When the skill's reasoning depth differs from session default | Cost control without losing quality |
| `context` | `fork` | When the skill's body should run in an isolated subagent, not inline | Prevents skill content from polluting main context |
| `agent` | subagent type (`Explore`, `Plan`, etc.) | Only with `context: fork` | Controls which tool set the forked agent gets |
| `paths` | glob pattern(s) | When a skill should activate only for specific file types | Path-aware skill loading — reduces false triggers |
| `shell` | `bash \| powershell` | When the skill uses `` !`cmd` `` inline shell blocks | Cross-platform determinism |
| `hooks` | YAML dict | When the skill needs lifecycle hooks scoped to itself | Event-driven skill behavior |
| `requires` | list of `sk-NNN` IDs | **kiho-specific** — when the skill calls other skills | Composition lineage; informational, not enforced at runtime |
| `topic_tags` | list of strings | **kiho-specific** — for capability-gap matching and trusted-source registry lookups | Cross-cuts the CATALOG and registry |
| `data_classes` | list of row slugs from `references/data-storage-matrix.md` | **kiho-specific** (v5.19+) — required for new skills that read or write state; declares which matrix rows the skill touches | Enables `evolution-scan --audit=storage-fit` drift detection; legacy skills backfill lazily (warn 60d / error 180d) |

**Rule:** only add fields you will actually use. Frontmatter bloat makes the metadata tier expensive.

### `metadata.kiho.data_classes` rule (v5.19)

- **MUST** be a list of row slugs that exist in `references/data-storage-matrix.md` (e.g., `agent-performance`, `skill-catalog-index`, `kb-wiki-articles`).
- **MUST NOT** cite a row whose status is `GAP` or `DEFERRED` — those rows exist as forward placeholders; their storage choice is not yet authorized.
- **SHOULD** be minimal — list only the classes the skill actually reads or writes, not everything it might incidentally pass through.
- New skills (author-touched after 2026-04-18) **MUST** declare this field.
- Legacy skills authored before 2026-04-18 are **grandfathered until 180 days post-v5.19 ship** — `evolution-scan --audit=storage-fit` warns for 60 days, then errors. Backfill happens lazily on the next `skill-improve` that touches the frontmatter.
- Adding a new class requires a matrix PR + CEO-committee vote per `committee-rules.md` §"Storage-fit committee".

## Description effectiveness rules

The description field is the PRIMARY trigger mechanism. Claude reads it from the system prompt to decide whether to invoke the skill. These 8 rules encode what makes a description load-bearing:

1. **Enumeration of concrete actions** — list 5–8 specific things the skill does, not adjectives.
   - ✓ "extracting text, merging PDFs, rotating pages, adding watermarks, filling forms"
   - ✗ "PDF processing"

2. **Explicit trigger phrases** — include phrases users might literally type.
   - ✓ "If the user mentions .pdf, asks to produce one, or says 'extract text from PDF'..."
   - ✗ "When document processing is needed..."

3. **Pushy language** — combat Claude's undertrigger tendency.
   - ✓ "Make sure to use this skill whenever the user mentions dashboards, data viz, or internal metrics, even if they don't explicitly ask for a dashboard."
   - ✗ "Can be useful for creating dashboards."

4. **Third person only** — no first person, no second person.
   - ✓ "Extracts text from PDFs."
   - ✗ "I can help extract text" or "You can extract text"

5. **WHAT + WHEN in one paragraph** — don't split.
   - ✓ "Processes PDFs by extracting text. Use when the user mentions PDFs or document processing."
   - ✗ Domain description + separate `when_to_use` field. (Claude only reads the description field for triggering; other fields are invisible to the router.)

6. **Length** — 50–1024 characters. Too short underspecifies; too long wastes system-prompt budget.

7. **No vague action verbs** — be specific.
   - ✓ "Extract, merge, rotate, fill forms"
   - ✗ "Handle, manage, process, work with"

8. **No meta-commentary** — don't describe what the skill does in the abstract; just state the actions.
   - ✓ "Extract text from PDFs."
   - ✗ "This skill is designed to help you extract text from PDFs by using..."

Run the mental test: if a user types a phrase that should trigger the skill, does the description obviously match?

## Body rules

**Under 500 lines.** If the body grows past 500 lines, split to `references/` files linked from the body. Include a Table of Contents at the top for any body > 100 lines.

**Topic sections, not Step 1/Step 2.** Organize as reference material:

Good structure:
```markdown
# Overview
## Quick start
## Common operations
## Advanced features
## Anti-patterns
```

Bad structure:
```markdown
# Step 1: Read the config
# Step 2: Parse the arguments
# Step 3: Call the downstream
```

Exception: a *workflow* skill with a fixed procedural sequence may use numbered steps, but keep them under 7 steps total and move details to per-step sub-sections or references.

**Use concrete examples, not abstract explanations.** Show code. Show receipts. Show input/output pairs. Every pattern should have one worked example.

**Consistent terminology.** Pick one word per concept and use it throughout. Don't switch between "field", "box", "control", "element".

**No time-sensitive content.** Avoid "as of 2026", "after next quarter", "the latest version". If content is version-specific, put it in an `## Old patterns` section with a `<details>` block.

**Forward slashes only.** `scripts/helper.py`, never `scripts\helper.py`. Even on Windows, cross-platform authoring uses forward slashes.

## Progressive disclosure patterns

Three tiers of context loading:
1. **Metadata** (name + description) — always in system prompt, ~100 tokens per skill.
2. **SKILL.md body** — loaded when skill triggers. **Target < 4000 tokens, warn 4000–5000, reject > 6000, hard limit 8000.** Measured via `skills/_meta/skill-create/scripts/count_tokens.py` (uses tiktoken cl100k_base when available, falls back to word_count × 1.3).
3. **Bundled resources** (`references/`, `scripts/`, `assets/`) — loaded only when explicitly referenced from the body.

**Why tokens, not lines** (v5.13): A 500-line body of prose is ~4000 tokens, but a 500-line body heavy on YAML tables or code blocks can exceed 6000 tokens. Gate 3 measures tokens to catch the dense-content case. Anthropic's Jan 2026 empirical study (referenced in `references/skill-authoring-standards.md` §"Eval-driven skill development") confirms that effective context window is 60–70% of advertised, with retrieval accuracy dropping sharply past ~120K tokens on a 200K model. Keeping individual skill bodies under 5K tokens preserves the budget for other skills and conversation history.

**For frequently-loaded skills** (activated in most sessions), keep the main body under 200 words (~300 tokens) with all detail in references. The metadata + body cost is paid on every session; minimize it.

**Pattern 1: High-level guide + references.** Body gives the quick start; detailed work lives in named reference files.

```markdown
# Processing PDFs

## Quick start
... code example ...

## Advanced
- Form filling: see FORMS.md
- API reference: see REFERENCE.md
```

**Pattern 2: Domain organization.** For multi-domain skills, put each domain in its own reference file.

```
bigquery-skill/
├── SKILL.md            # overview + domain selection
└── references/
    ├── finance.md
    ├── sales.md
    └── product.md
```

**Pattern 3: Conditional details.** Body shows basic usage; links to advanced content only when needed.

**Important**: references are one level deep from SKILL.md. Never nest references inside references. A `references/foo.md` file should not itself point to `references/foo-details.md`.

**Reference files >100 lines need a table of contents at the top.**

## Scripts vs inline code

**Use scripts (`scripts/`) when**:
- The same code would be rewritten repeatedly
- Deterministic execution matters more than explanation
- The operation is fragile and error-prone

**Use inline code when**:
- It's a one-off example illustrating a pattern
- The user will likely customize it
- The surrounding narrative makes it clearer

**Scripts must handle errors explicitly.** Don't punt to Claude:
```python
# Good
def process_file(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        print(f"File {path} not found")
        return ""

# Bad
def process_file(path):
    return open(path).read()  # let Claude figure out failures
```

**No voodoo constants.** Every magic number gets a comment explaining why that value.

## Versioning and lifecycle

Every kiho skill carries two lifecycle-related frontmatter fields:

```yaml
version: 0.1.0
lifecycle: draft
```

**Version rules:**
- Start at `0.1.0` for new DRAFT skills.
- Bump to `0.2.0`, `0.3.0`, ... on `skill-improve` structural changes.
- Bump to `1.0.0` on DRAFT → ACTIVE promotion.
- Bump minor (`1.1.0`) on additive changes after ACTIVE.
- Bump patch (`1.0.1`) on typo/clarification fixes after ACTIVE.
- Never bump past `1.x.x` without a committee-gated review.

**Lifecycle states:**

| State | Meaning | Who can write it | How to advance |
|---|---|---|---|
| `draft` | Newly created; not yet validated by real use | `skill-create`, `skill-learn op=synthesize`, `skill-derive` | Pass `interview-simulate` on a consuming agent + CEO committee approval |
| `active` | Validated; available to all agents | CEO committee gate | `skill-improve` for fixes; `deprecate` for removal |
| `deprecated` | Still loadable but marked for removal | CEO only | `skill-delete` after 60 days of zero use |

**DRAFT skills live at** `.kiho/state/drafts/sk-<slug>/SKILL.md`. On promotion to ACTIVE they move to `skills/<domain>/<slug>/SKILL.md` and are registered in CATALOG.md.

**Deprecated skills** stay in place but their frontmatter adds:
```yaml
lifecycle: deprecated
deprecated_at: 2026-04-15
superseded_by: sk-NNN  # optional pointer to the replacement
removal_target: 2026-06-15
```

## Evals schema

Every kiho skill ships with an eval suite at `.kiho/agents/<consumer>/tests.md` or adjacent to the skill at `<skill-dir>/evals.md`. The eval suite is used by `interview-simulate` for pre-deployment validation and by regression checks after `skill-improve`.

**Minimum eval suite:** 3 test cases. **Recommended:** 5–7.

**Schema (one test per block):**

```yaml
- id: <short-id>                   # e.g., "basic", "edge-empty", "refusal"
  scenario: |
    <user prompt or multi-turn setup that triggers the skill>
  must_invoke_skill: true          # false for "should NOT invoke" negative cases
  expected_behavior: |
    <natural-language description of pass criteria>
  rubric_dimensions: [accuracy, clarity, persona_fit, tool_use, refusal]
  test_type: basic | edge | coherence | tool_use | refusal | drift | refusal_robustness
  rubric_weights:                  # optional per-test weight override
    accuracy: 0.40
```

**Mandatory coverage:** every eval suite must include at least one `basic`, one `edge`, and one `refusal` or negative test (either a red-line trigger or a "should not invoke" case).

Full template in `templates/skill-evals.template.md`.

## Security (OWASP Agentic Skills Top 10)

The 2026 OWASP Agentic Skills Top 10 codifies the risk surface of skill authoring. A kiho skill MUST satisfy these rules before promotion to ACTIVE.

**1. No hardcoded credentials.** Never include API keys, tokens, passwords, or secrets in SKILL.md body, scripts, or references. Reject patterns: `api_key`, `password`, `token`, `AWS_`, `OPENAI_API_`, hex strings longer than 32 chars that look like keys.

**2. Input validation in scripts.** Scripts that accept file paths must validate — no directory traversal (`../`), no absolute paths to system directories. Scripts that run shell commands must sanitize — no `os.system(user_input)`, no `shell=True` with untrusted args.

**3. Least privilege in allowed-tools.** If a skill declares `allowed-tools`, narrow it to specific invocations: `allowed-tools: Bash(git add *) Bash(git commit *)`. Reject wildcards like `Bash(*)`.

**4. No skill duplication.** A skill that just wraps an existing tool (e.g., "call Bash with this command") is supply-chain bloat. Reject skills that are <20 lines of tool pass-through. Enforce naming uniqueness to prevent typosquatting/shadowing.

**5. Fail-closed defaults.** When a script encounters an unknown state, deny/exit rather than proceeding. Dangerous operations require explicit opt-in (`--force`, `--yes`).

**6. Explicit error states.** Scripts MUST write error messages to stderr or logs. Silent failure is an anti-pattern. SKILL.md body MUST document what happens if the skill fails.

**7. Audit trail for external calls.** Scripts that call external APIs must log: endpoint, HTTP method, status code, timestamp. **Never log response bodies** (may contain secrets).

**8. No auto-eval of fetched content.** If a skill fetches external content (via WebFetch or by running a remote script), do NOT pass the content into `eval()`, `exec()`, or `subprocess.run(shell=True)`. Parse as data, not as code.

**9. Reproducibility.** A skill's behavior must be reproducible given the same inputs — no timing-dependent logic, no randomness without seed, no reliance on hidden environment state.

**10. Revocation path.** Every skill has a documented way to be disabled or rolled back. ACTIVE skills can be moved to `deprecated` via CEO. Runtime kill-switch: adding `lifecycle: deprecated` to frontmatter makes the skill ineligible for automatic invocation.

## The Lethal Trifecta rule

From Simon Willison's 2026 analysis of agent security: a skill is **dangerous** when it simultaneously has all three of:

1. **Access to private data** (SSH keys, API tokens, credentials, browser cookies, ~/.config)
2. **Exposure to untrusted content** (user input, email bodies, external web pages, git history from forks)
3. **Ability to communicate externally** (network egress, webhooks, curl, email sending)

A skill with 2 of 3 is elevated-risk. A skill with all 3 is the lethal trifecta and MUST be blocked from DRAFT → ACTIVE promotion without a CEO committee + user approval. `skill-create` enforces this at Gate 9 (Security scan).

Mitigation patterns:
- Break the trifecta by removing one capability. A skill that reads private data should not also have network egress.
- If all three are essential, require user-in-the-loop for every invocation (set `disable-model-invocation: true`).
- Document the risk tier in the skill's frontmatter: `risk_tier: low | medium | high | trifecta`.

## Ten validation gates

Every newly authored skill must pass these 10 gates before registration. `skill-create` implements each as a hard check; `skill-learn op=synthesize` runs the same gates on its output.

| # | Gate | Failure action |
|---|---|---|
| 1 | **Frontmatter syntax** — YAML well-formed, `name` 3–64 chars kebab-case, `description` 50–1024 chars, no reserved words | reject; revise frontmatter |
| 2 | **Description effectiveness** — passes all 8 Description effectiveness rules | iterate via [Iterative description improvement](#iterative-description-improvement) |
| 3 | **Body structure** — under 500 lines, topic-based sections, TOC if >100 lines, every reference one level deep | reject; restructure |
| 4 | **Example presence** — at least one concrete worked example per major operation described in the body | reject; add examples |
| 5 | **Terminology consistency** — same concept word used throughout; no synonym mixing | reject; normalize terms |
| 6 | **Script integrity** — scripts handle errors explicitly, no voodoo constants, `python -m py_compile` passes, cross-platform paths | reject; fix scripts |
| 7 | **No time-sensitive content** — no "as of 2026", "latest version", unless isolated in `## Old patterns` `<details>` block | reject; quarantine |
| 8 | **Dedup check** — no existing skill in CATALOG.md with >0.70 description overlap | abort with `status: duplicate` naming the existing `sk-NNN` |
| 9 | **Security scan** — no secrets, input validation in scripts, least-privilege `allowed-tools`, Lethal Trifecta check | reject; fix or escalate |
| 10 | **Eval suite present** — at least 3 test cases including one `basic`, one `edge`, one `refusal`/negative | reject; generate or request evals |

A skill that passes all 10 gates may still be DRAFT. DRAFT → ACTIVE promotion additionally requires a passing `interview-simulate` run on a consuming agent + CEO committee approval.

## Iterative description improvement

When Gate 2 (Description effectiveness) fails, do NOT manually guess at fixes. Run the iterative improvement loop:

1. **Score the description** against the 8 rules. Each rule is binary (pass/fail). Score = count of passes / 8.
2. If score ≥ 0.85, accept and proceed.
3. Otherwise, list the failed rules with one-line diagnoses (e.g., "Rule 1 failed: no concrete actions enumerated").
4. **Rewrite** the description to address the failed rules specifically. Preserve passing elements.
5. Re-score. If still below threshold, loop (max 3 iterations).
6. If 3 iterations fail, abort with `status: description_irrecoverable` and escalate — the underlying domain may be too vague to be a discrete skill.

Inspired by Anthropic's `improve_description.py` from the official `skill-creator` skill. This loop catches undertrigger at creation time rather than during a real task.

## Anti-patterns

**Too many options.**
```markdown
Bad: Use pypdf, or pdfplumber, or PyMuPDF, or pdf2image...
Good: Use pdfplumber for text. For scanned PDFs needing OCR, switch to pdf2image + pytesseract.
```

**Verbose preamble.** Don't explain what Claude already knows. If Claude is reading your skill, you can assume Claude knows what markdown is, what YAML is, what a function is.

**Meta-narration.** Don't write "You are loading the kiho skill. Your job is to...". Just tell Claude what to do.

**Windows paths.** Always forward slashes.

**Inconsistent terminology.** Pick one word and stick with it.

**Creating auxiliary files in the skill directory.** No README.md, INSTALLATION.md, CHANGELOG.md. The skill directory should contain only SKILL.md, the `.skill_id` sidecar, and its bundled resources (`references/`, `scripts/`, `templates/`, `assets/`, and optionally `evals.md`).

**Skill that just wraps a tool.** If the skill is <20 lines of "call tool X with these args", delete it — this is tool pass-through, not a skill. Skills add domain knowledge, orchestration, or multi-step coordination. A single tool call wrapped in markdown is CATALOG spam.

**Nested references.** `references/foo.md` must not itself point to `references/bar.md`. Progressive disclosure is exactly 2 levels: SKILL.md → references. Deeper nesting means Claude reads partial context and misses the load-bearing detail.

**Secrets anywhere.** Never in the body, never in scripts, never in references, never in evals, never in the git history. OS keychain or environment variables only.

**The Lethal Trifecta without a user-in-the-loop.** A skill that reads private data AND ingests untrusted content AND has network egress must require explicit user approval per invocation. Auto-invocable trifecta skills are rejected at Gate 9.

**Punting errors to Claude.** Scripts must catch and handle; don't let Python exceptions bubble up expecting Claude to debug them.

**Writing in second person.** "You should do X" — no. Use imperative: "Do X."

**Writing in first person.** "I can help with..." — no. Third person only in descriptions; imperative in bodies.

## Checklist

Before promoting any kiho skill from DRAFT to ACTIVE:

**Frontmatter**
- [ ] `name` matches the filename's parent directory
- [ ] `description` is third-person, combines WHAT + WHEN, includes specific trigger phrases
- [ ] `description` is under 1024 characters and over 50 characters
- [ ] No other frontmatter fields besides the ones kiho's skill schema requires

**Body**
- [ ] Under 500 lines
- [ ] Topic-based sections, not "Step 1/Step 2" narration (unless it's a genuine procedural workflow)
- [ ] All references are one level deep from this SKILL.md
- [ ] Every reference file over 100 lines has a table of contents
- [ ] Consistent terminology throughout
- [ ] No time-sensitive content (or quarantined in `## Old patterns`)
- [ ] Forward slashes in all paths
- [ ] At least one concrete example per key operation
- [ ] Imperative language; no second/first person in the body
- [ ] No explanations of things Claude already knows

**Scripts (if any)**
- [ ] Handle errors explicitly
- [ ] No voodoo constants
- [ ] Work on Linux, macOS, and Windows (forward slashes, pathlib.Path)
- [ ] Tested with `python -m py_compile` at minimum

**Discoverability**
- [ ] Run a mental test: if a user types a phrase that should trigger this skill, does the description obviously match?
- [ ] The skill is NOT named with reserved words (`anthropic`, `claude`)
- [ ] The skill name doesn't collide with an existing kiho skill

**Versioning and lifecycle**
- [ ] `version` field present and starts at `0.1.0` for new DRAFT
- [ ] `lifecycle: draft` on initial registration
- [ ] Promotion to `active` requires passing interview-simulate + CEO committee approval
- [ ] Deprecated skills carry `deprecated_at` and `removal_target`

**Evals**
- [ ] At least 3 test cases in `evals.md` or equivalent tests.md
- [ ] Coverage: one `basic`, one `edge`, one `refusal`/negative
- [ ] Each test has scenario + expected_behavior + must_invoke_skill + rubric_dimensions
- [ ] Full template schema from `templates/skill-evals.template.md`

**Security (OWASP Agentic Skills Top 10)**
- [ ] No hardcoded credentials, API keys, or tokens (regex-scanned)
- [ ] Scripts validate external inputs (no directory traversal, no shell injection)
- [ ] `allowed-tools` is narrowly scoped (no wildcards like `Bash(*)`)
- [ ] Skill is not a thin tool wrapper (< 20 lines of pass-through)
- [ ] Explicit error handling in all scripts
- [ ] Audit-trail logging for external API calls (no response-body logging)
- [ ] Lethal Trifecta check: fewer than 3 of {private-data access, untrusted content exposure, network egress}, OR `disable-model-invocation: true`

**Promotion to ACTIVE**
- [ ] Skill has passed its eval suite via `interview-simulate(mode: light)`
- [ ] CEO committee gate approved the promotion
- [ ] `kb-add` has been called to register the skill in the KB
- [ ] `skill-solutions.md` updated with any entities/concepts this skill solves
- [ ] Version bumped to `1.0.0` on promotion

## Iteration workflow

When a skill underperforms:
1. Observe it on a real task (not a test case).
2. Capture the specific struggle — missed trigger, wrong section read, incorrect output shape.
3. Apply a minimal targeted fix — a better description phrase, a tighter example, an anti-pattern.
4. Re-run the real task.
5. Repeat until the struggle is gone.

This is the Claude-A/Claude-B pattern from Anthropic's docs: one Claude authors the skill, another Claude uses it, observations flow back to the author.

## Eval-driven skill development (8 steps)

**Source:** Anthropic's Jan 2026 engineering blog "Demystifying Evals for AI Agents". This pattern is the authoritative guidance for 2026 skill evaluation. It complements the 10 validation gates (which are hard pre-ship checks) by providing a workflow for how to design the evals themselves.

1. **Start with 20–50 real failures.** Don't invent edge cases from scratch. Mine session logs, error reports, and user complaints for actual failure modes. A test case derived from a real failure is worth ten invented edge cases — the real failure proves it matters. For kiho, the `.kiho/state/research/` cache and `agent-performance.jsonl` are your real-failure corpus.

2. **Convert manual tests to automated early.** A manual "does this look right" check that lives in someone's head is not an eval. Write it down as a runnable test with a deterministic or model-based grader. Kiho's `interview-simulate(mode: full)` + canonical-rubric.toml provide the runtime; you provide the schema.

3. **Write unambiguous specs.** Every test's `expected_behavior` must be concrete enough to grade programmatically. "Handles the request correctly" is useless — "Cites behavioral rule #3 verbatim in the first sentence" is specific and gradable.

4. **Balance positive and negative cases.** Every test suite should include tests that should pass AND tests that should NOT pass (or should refuse). For kiho, the v5.13 `triggering_accuracy` test type bakes this in via the 20-prompt 10+10 corpus.

5. **Build isolated harnesses.** Eval runs must not pollute production state. kiho enforces this by routing eval writes to `.kiho/state/drafts/<slug>/` and `.kiho/state/runs/interview-simulate/` which are intentionally outside the active skill catalog and agent registry.

6. **Design appropriate graders.** Use deterministic checks for output shape and tool-call correctness (fast, cheap, reproducible). Use model-based graders for subjective quality (persona_fit, clarity, scope adherence). Use human graders only for gray-area disagreements. Kiho's canonical-rubric.toml uses all three: deterministic for tool_use and refusal, model-based for persona_fit and clarity, human fallback for committee reviews.

7. **Review transcripts, not just scores.** Scores aggregate away behavioral issues. Read a sample of actual transcripts to catch silent error swallowing, wrong-tool-for-right-operation, and scope drift. This is exactly what Gate 11 (transcript review) enforces for skill-create in v5.13.

8. **Monitor saturation.** Stop iterating when improvements plateau. If 3 consecutive rewrite iterations don't move the test accuracy meaningfully, the description or body has hit a local optimum — sharpen the intent or split the skill rather than flogging the rewriter.

## What kiho differs from Anthropic skill-creator

kiho's `skill-create` intentionally diverges from Anthropic's official `skill-creator` in several ways. Documenting the divergences here for auditability.

| Aspect | Anthropic skill-creator | kiho skill-create |
|---|---|---|
| Validation gates | Relies on iterative `improve_description` loop + human review; no explicit gate checklist | 11 explicit hard gates (frontmatter, description, body, examples, terminology, scripts, time-sensitivity, dedup, security, evals, transcript review) |
| Description improvement | `improve_description.py` — train/test split, 5 iterations, blind comparisons | Two-phase: fast binary scorer (score_description.py) → slow iterative rewriter (improve_description.py) modeled on Anthropic's |
| Security enforcement | Minimal — no documented static analysis or secret scanning | OWASP Agentic Skills Top 10 + Lethal Trifecta + secret regex scan + input validation + allowed-tools scope check |
| Versioning / lifecycle | Not baked into skill-creator | DRAFT / ACTIVE / DEPRECATED with version bumps; CEO committee gate for promotion |
| Eval suite minimum | Implicit — `improve_description.py` generates 20 prompts, no explicit eval schema | Explicit 5-test minimum (basic, edge, refusal, triggering_accuracy, transcript_correctness) with YAML schema |
| Composition | No `requires:` declaration | Informational `requires: [sk-NNN]` in metadata; enforcement deferred |
| Transcript review | Recommended in Anthropic 8-step eval blog | Hard gate (Gate 11) — skills can't register without passing it |
| Dedup check | Not enforced | Hard gate — 0.70 CATALOG overlap aborts with `status: duplicate` |
| Frontmatter extensions | Sticks to the 6 agentskills.io canonical fields | Extends via `metadata:` with kiho-specific fields (version, lifecycle, topic_tags, etc.) — open-standard compatible |
| Output artifacts | Just the SKILL.md | SKILL.md + references/ + scripts/ + assets/ + evals.md + transcript-review.md + audit block in frontmatter |

**Why the divergences:** kiho is a multi-agent orchestration system with enterprise simulation — skills are created by subagents on behalf of other subagents, with no human in the loop during normal operation. That shifts the validation burden from human review (Anthropic's model) to programmatic gates (kiho's model). Gate 11 and the 11-gate pipeline exist precisely because there's no human reviewer to catch behavioral issues at ship time.

**What kiho copies verbatim:**
- The train/test split, 60/40 ratio, max-5 iterations, blind comparison from `improve_description.py`
- The 1024-character description limit
- The "review transcripts, not just scores" discipline from the 8-step eval blog
- The topic-based body structure (not step-based narration)
- The progressive disclosure tiers (metadata / body / references)
- The "one level deep" reference rule

**What kiho does NOT copy:**
- Reliance on human review at ship time — kiho's gates are programmatic
- Opt-in skill synthesis — kiho skill-create is invoked automatically by design-agent Step 4d sub-path B
