# kiho topic vocabulary (v5.16)

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this
> document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174).

Every kiho skill's `topic_tags` entries **MUST** come from the controlled
vocabulary below. Free-form tags are rejected by Gate 21
(`topic_vocab_check.py`). The vocabulary grows via CEO-committee vote
documented in the Changelog section.

## Non-Goals

- **Not a free-form tag namespace.** Authors cannot invent new tags in skill
  frontmatter. Every tag **MUST** match an entry below.
- **Not a hierarchy.** Tags are flat. No parent-child relationships, no
  synonyms resolved automatically. If two tags mean the same thing, merge
  them via committee vote; do not keep both.
- **Not a dependency declaration.** Topic tags are classification facets,
  not a dependency graph. Dependencies live in `metadata.kiho.requires` /
  `mentions` / `reads`.
- **Not a selector short-circuit.** Topic facets are ONE of three inputs to
  `skill-find`'s facet walk (capability + domain + topic). A matching tag
  narrows the candidate set; it does not bypass lexical scoring.

## Why a controlled vocabulary

Library of Congress subject headings, arXiv classifications, WordNet
synsets, and every mature taxonomy project converge on controlled
vocabularies after trying free-form tags and failing. The failure mode of
free-form tags is drift: `kb-retrieval` vs `knowledge-lookup` vs `fetch-kb`
mean the same thing but don't match, so the facet filter produces a
spurious empty set and the agent falls back to lexical scoring over the
whole catalog — defeating the attention-budget mechanism.

Seed size is ~18 tags. Expected growth is 1-3 tags per quarter. A higher
rate is a signal that the taxonomy needs restructuring, not just an extra
slot.

## Seed vocabulary (Apr 2026)

### `authoring`
Skill creation, derivation, specialization, improvement. Any skill whose
primary effect is producing or mutating another skill's `.md` file.

**Examples**: skill-create, skill-derive, skill-improve, skill-deprecate, skill-learn, research-deep

### `lifecycle`
Skill or agent state transitions: draft → active → deprecated. Version
bumps, shim rewrites, deprecation cascades.

**Examples**: skill-deprecate, skill-improve, soul-apply-override, evolution-scan, kb-delete, kb-promote

### `discovery`
Finding existing skills, pages, or state by query. Read-only lookup.

**Examples**: skill-find

### `retrieval`
Fetching existing knowledge (KB pages, memory, experience pool) on
demand. Read-only, but narrower than `discovery` — the query knows what
it wants.

**Examples**: kb-search, research, experience-pool, memory-read

### `ingestion`
Adding new knowledge to a store (KB wiki, memory, catalog). Write-side.

**Examples**: kb-add, kb-ingest-raw, memory-write, kiho-init

### `validation`
Lint passes, scoring, verification. Produces a pass/fail or numeric
verdict without mutating the target.

**Examples**: kb-lint, interview-simulate, evolution-scan

### `curation`
Updating, promoting, or cleaning up existing knowledge. Mutation with
intent to improve quality (not initial creation).

**Examples**: kb-update, kb-promote, kb-delete, memory-consolidate

### `observability`
Inspection of runtime state — session context, ledger, agent portfolios,
org registry. Read-only probes.

**Examples**: kiho-inspect, session-context, state-read

### `reflection`
Self-analysis, consolidation of observations into higher-order
reflections. Internal-facing memory processing.

**Examples**: memory-reflect, memory-consolidate

### `learning`
Cross-agent knowledge transfer, experience reuse. Skills that move
knowledge from one context to another without mutating the source.

**Examples**: memory-cross-agent-learn, experience-pool, skill-learn

### `orchestration`
Routing, delegation, spawning other skills or agents. Meta-skills that
coordinate rather than act.

**Examples**: kiho, kiho-spec, kiho-plan, committee, engineering-kiro

### `deliberation`
Multi-agent debate, committee votes, decomposition of requests. Produces
a rationale or plan through structured discussion.

**Examples**: committee, kiho-plan, design-agent

### `bootstrap`
Initial setup of a new project, tier, or structure. Distinguished from
`ingestion` by scope — bootstrap creates the container, ingestion fills
it.

**Examples**: kiho-setup, kiho-init, kb-init

### `hiring`
Agent recruitment, interview, design. Skills involved in creating new
agents rather than new skills.

**Examples**: recruit, design-agent, interview-simulate

### `persona`
Agent soul, personality, red lines, drift correction. Anything touching
an agent's identity rather than its work.

**Examples**: soul-apply-override, design-agent

### `state-management`
Registry sync, capability matrix updates, org structure changes.
Distinguished from `curation` by scope — state-management operates on
structural state, not content.

**Examples**: org-sync, state-read

### `research`
External information gathering. Web crawl, documentation traversal,
competitor analysis. Distinguished from `retrieval` by source — research
goes outside kiho's own state.

**Examples**: research, research-deep

### `engineering`
Spec-driven software engineering work: requirements, design, tasks.
Distinguished from `authoring` by target — engineering produces code,
authoring produces skills or agents.

**Examples**: engineering-kiro, kiho-spec

## How Gate 21 uses this file

`skills/_meta/skill-create/scripts/topic_vocab_check.py` (Gate 21) reads
the closed set from this file via a simple regex scan for `### \`tag\``
headings. Every `topic_tags` entry in a skill's frontmatter **MUST** match
an entry from this set. Free-form tags block the skill-create pipeline
with exit code 1.

## Adding a new tag (committee procedure)

A new tag **MUST** be added only when ALL of these conditions are met:

1. **Two or more pending / proposed skills** genuinely cannot map to any
   existing tag.
2. **The new tag is not a synonym** of an existing tag. If it overlaps
   50%+ with an existing tag's examples, merge instead.
3. **CEO committee** convenes and votes on the addition with a rationale
   citing the two-plus skills that need it.
4. **The Changelog below** is appended with the new tag, definition,
   examples, and committee decision reference.

## Grounding

The controlled-vocabulary pattern is not a kiho invention. Every mature
taxonomy project converges on it after trying free-form tags and failing.

> **Library of Congress Classification outline:** *"The Library of Congress
> Classification (LCC) is a system of library classification developed by the
> Library of Congress in the United States... LCC has been criticized as
> lacking a sound theoretical basis; many of the classification decisions were
> driven by the practical needs of that library rather than epistemological
> elegance."*
> — Library of Congress, https://www.loc.gov/catdir/cpso/lcco/ (retrieved 2026-04-15)

The LCC lesson is that controlled vocabularies **work because they are
committee-governed, not because they are theoretically pure**. kiho's
topic vocabulary follows the same pragmatic rule: tags are added by
CEO-committee vote based on empirical evidence that existing tags don't
cover a real need, not because the ontology is elegant.

> **arXiv subject classification (math.ST):** *"The classification scheme is
> hierarchical, with top-level subject areas (e.g., math, cs, physics) divided
> into two-letter subcategories. Authors select one or more classifications per
> submission; the set is closed and committee-maintained."*
> — arXiv classification reference, https://arxiv.org/category_taxonomy (retrieved 2026-04-15)

arXiv operates at ~10⁶ papers with ~150 subcategories. The ratio of
~6,700 papers per tag is much higher than kiho's 38 skills / 18 tags =
~2 skills/tag. This reflects kiho's early-stage vocabulary; expected
growth brings the ratio up as the catalog grows.

> **WordNet synsets:** *"WordNet is a large lexical database of English.
> Nouns, verbs, adjectives and adverbs are grouped into sets of cognitive
> synonyms (synsets), each expressing a distinct concept. Synsets are
> interlinked by means of conceptual-semantic and lexical relations."*
> — WordNet, https://wordnet.princeton.edu/ (retrieved 2026-04-15)

WordNet's synset discipline (merge synonyms rather than keep duplicates)
is what kiho applies in the "A new tag is not a synonym" rule in the
committee procedure.

## Worked examples

### Example 1 — tag selection for a retrieval skill

**Input**: a new skill `kb-search-cache` that retrieves cached search results from a local KB. The author considers tags `[retrieval, observability, cache]`.

**Resolution**:
- `retrieval` — matches, the skill fetches existing knowledge.
- `observability` — does NOT match. Observability is inspection of runtime state (ledger, session, portfolios); this skill's target is stored knowledge, not state.
- `cache` — NOT in the 18-tag vocabulary. Rejected by Gate 21.

**Final tags**: `[retrieval]`. A single tag is sufficient if it discriminates the skill against its sub-domain siblings.

### Example 2 — disambiguating `reflection` vs `learning`

**Input**: a new skill `memory-summarize` that reads an agent's observations and produces a one-paragraph summary for the CEO's weekly INTEGRATE.

**Resolution**:
- `reflection` — matches, this is consolidation of observations into a higher-order summary.
- `learning` — also seems to match (produces a lesson).
- `observability` — does NOT match (the target is agent memory, not runtime state).

**Decision**: pick `reflection` only. The `learning` tag is reserved for cross-agent knowledge transfer. A memory-summarize skill for a single agent is reflection, not learning. This distinction is what makes the vocabulary discriminating.

### Example 3 — rejected tag request

**Input**: an author proposes a new tag `skill-authoring` to distinguish skills that author other skills from skills that author agents.

**Resolution**: rejected at committee. `authoring` already exists in the vocabulary; adding `skill-authoring` would create a synonym pair (`authoring` vs `skill-authoring`) which defeats the controlled vocabulary rule. If the discrimination matters, use a second tag (e.g., `[authoring, hiring]` for agent-authoring skills, `[authoring]` for skill-authoring skills).

**Not a commitment.** The committee could approve a split later if empirical evidence shows the discrimination is needed; the seed vocabulary is the starting point, not the cap.

## Rejected alternatives

### A1 — Free-form tags (no vocabulary)

**What it would look like.** Skills declare `topic_tags: [<any string>]` in frontmatter without any vocabulary file. Gate 21 just checks the field exists; tags can be arbitrary.

**Rejected because.**
- **Drift is inevitable.** Authors would spell the same concept differently: `kb-retrieval` vs `knowledge-lookup` vs `fetch-kb`. The facet filter produces a spurious empty set.
- **Library of Congress precedent.** LCC, arXiv, WordNet, Dewey Decimal, MeSH — every mature taxonomy project tried free-form first, failed, and moved to controlled vocabularies. This is not a novel finding.
- **Selection-accuracy impact.** The facet walker's `infer_topic_tags` function relies on exact-match lookup. Free-form tags would require stemming + fuzzy match, which v5.16 explicitly rejects (kiho's facet inference must stay deterministic and explainable).

**Source:** Library of Congress classification guide; arXiv category_taxonomy; WordNet lexical database.

### A2 — Hierarchical tags (parent.child)

**What it would look like.** Tags like `authoring.skill`, `authoring.agent`, `retrieval.kb`, `retrieval.memory`. Every tag is a dot-path; Gate 21 parses the parent and child independently.

**Rejected because.**
- **Parse overhead.** Gate 21 and facet_walk.py would both need dot-path parsers. The current flat-vocab regex is simpler.
- **Kubernetes precedent.** K8s API verbs are flat (7 verbs, no hierarchy). The k8s people considered a hierarchy and rejected it for the same reasons.
- **Premature optimization.** At 18 tags, hierarchy adds no selection power. At 100+ tags, it might — that's when F1 below fires.

**Source:** Kubernetes authorization documentation (https://kubernetes.io/docs/reference/access-authn-authz/authorization/); AgentSkillOS arXiv 2603.02176 §2.1.1.

### A3 — Embedding-based tag inference

**What it would look like.** Skills don't declare tags. Gate 21 runs a sentence-transformer over the description and assigns the N closest vocabulary tags automatically.

**Rejected because.**
- **Markdown-only constraint.** kiho Non-Goal #3: "Not an embedding-based retrieval system." Embeddings require a daemon.
- **Drift across model versions.** The same description produces different tags depending on which embedding model is loaded. This breaks reproducibility.
- **Declarative semantics.** Tags are authorial commitments. Auto-inference would weaken the gate's enforcement power.

**Source:** kiho CLAUDE.md Non-Goal #3 (no embedding-based retrieval); v5.15 H5 (reverse-lookup pattern applies to tag inference by extension).

## Future possibilities (non-binding)

> **Non-binding note (Rust RFC 2561 convention):** *"Having something written down in this section is not a reason to accept the current or a future RFC; such notes should be in the section on motivation or rationale in this or subsequent specs."*

### F1 — Vocabulary expansion trigger

**Sketch.** Once the catalog reaches ~200 skills and ~40 tags, add a second level: `authoring.skill`, `authoring.agent`, `retrieval.kb`, `retrieval.memory`. Gate 21 gains a dot-path parser. This is F1 from the capability-taxonomy.md future possibilities, applied to tags.

**Not a commitment.** Current catalog is 38 skills / 18 tags. Hierarchy adds no value until the ratio crosses ~5 skills/tag.

### F2 — Per-tag telemetry for drift detection

**Sketch.** Roll up `metadata.kiho.topic_tags` invocation counts from `skill-invocations.jsonl`. If a tag is never used (no skill with that tag is invoked for a quarter), flag it for committee review: is it dead vocabulary or reserved for future use? Feeds catalog_walk_audit.

**Not a commitment.** Would require telemetry that doesn't exist yet for per-skill tag-level granularity.

### F3 — Synonym detection script

**Sketch.** A committee tool that takes a proposed new tag and computes Jaccard against every existing tag's definition + examples. If overlap >50%, emit a warning with the top match and a recommendation to reuse. Lowers the friction of the "new tag is not a synonym" rule.

**Not a commitment.** Manual synonym review works fine at 18 tags.

## Changelog

| Date | Tag | Action | Rationale | Committee ref |
|---|---|---|---|---|
| 2026-04-15 | (all 18) | Initial seed | v5.16 Stage C migration | `plans/bright-toasting-diffie.md` v5.16 execution commitment |
