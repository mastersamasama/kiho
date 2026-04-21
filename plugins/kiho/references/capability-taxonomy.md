# kiho capability taxonomy (v5.16)

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this
> document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174).

Every kiho skill **MUST** declare exactly one `metadata.kiho.capability` verb from
the closed 8-element set below. The set is **closed** — additions require a
CEO-committee vote documented in the Changelog section at the bottom of this file.

> **Sibling vocabulary.** This 8-verb capability set classifies **what a single skill does**. `references/core-abilities-registry.md` carries a sibling 7-verb `core_ability` set classifying **what a cycle phase exercises**. A phase's `entry_skill` **MAY** carry any capability compatible with the phase's core-ability — see the mapping table in `core-abilities-registry.md §Sibling relationship`. `decide` and `communicate` appear in both vocabularies with matching semantics; `orchestrate` exists only here (surfaces under cycle-layer `deploy` or atomic invocation).

## Non-Goals

- **Not a free-form tag system.** Authors cannot invent new verbs in a skill's
  frontmatter. The taxonomy is committee-governed.
- **Not a dependency graph.** Capability is what a skill *does*, not what it
  requires. Dependencies live in `metadata.kiho.requires` / `mentions` / `reads`.
- **Not a runtime selector.** The capability facet is one of three inputs to
  `skill-find`'s facet walk; it does not bypass the lexical scoring step.
- **Not a permission model.** A skill declaring `capability: delete` is not
  automatically granted delete permissions on state. Permissions stay at the
  agent + tool-allowlist level.
- **Not immutable.** The closed set can grow, but every addition is audit-logged
  in the Changelog below.

## Why a closed set

Kubernetes API verbs (`get/list/watch/create/update/patch/delete`) are the
canonical precedent. HTTP REST has 4-5 verbs. SQL DML has 4. More verbs hurt
discrimination (the selector can't reliably classify); fewer verbs hurt
selectivity (too many distinct operations merge into one bucket). Eight is the
empirical sweet spot across those precedents.

At |S|=1000 skills, filtering on a single capability verb prunes the candidate
set by ~5× on average (1000 → ~200) before any lexical scoring runs. That
prune is the difference between a selectable facet walk and an unselectable
flat search.

## The eight verbs

### `create`
Produces a new artifact or piece of state that did not exist before.

- **Examples**: skill-create, skill-derive, kiho-init, kb-init, recruit, research, research-deep, memory-write, kb-add, kb-ingest-raw
- **Test**: Does running this skill result in a new file, row, or entity on disk / in state? Yes → `create`.
- **Not-examples**: A skill that reads a file and returns a summary is `read`, not `create`, even if it produces an output document.

### `read`
Retrieves existing state without mutation. Side-effect-free queries.

- **Examples**: skill-find, session-context, state-read, kb-search, memory-read, experience-pool (retrieval mode), kiho-inspect
- **Test**: If you ran this skill twice back-to-back, would the second run see any changes made by the first? No → `read`.
- **Not-examples**: A skill that reads state and writes a log entry is `update` (the log is mutation), not `read`.

### `update`
Modifies existing state. Distinct from `create` because the target must already exist.

- **Examples**: skill-improve, kb-update, kb-promote, memory-consolidate, org-sync, soul-apply-override
- **Test**: Does this skill operate on an artifact that must exist before the skill runs? Yes + mutation → `update`.
- **Not-examples**: skill-deprecate mutates state (body rewrite + frontmatter flag flip) but its primary effect is removal from the active selection set — so `delete`, not `update`.

### `delete`
Removes or retires state. Includes soft-deletes and deprecation shims.

- **Examples**: skill-deprecate, kb-delete
- **Test**: Does this skill's primary effect make something no longer selectable / no longer authoritative? Yes → `delete`.
- **Not-examples**: kb-lint flags stale references but does not remove them — that's `evaluate`, not `delete`.

### `evaluate`
Judges, scores, or validates existing artifacts. Produces a verdict, not a mutation.

- **Examples**: kb-lint, interview-simulate, evolution-scan
- **Test**: Does the skill produce a pass/fail or a numeric score as its primary output? Yes → `evaluate`.
- **Not-examples**: A skill that scores AND rewrites based on the score is `update` (the rewrite is the primary effect) — unless it can run in a score-only mode, in which case split into two sub-operations.

### `orchestrate`
Coordinates other skills or agents. A meta-skill whose body is mostly delegation.

- **Examples**: kiho, kiho-plan, kiho-spec, kiho-setup, committee
- **Test**: Does this skill's body primarily spawn or route to OTHER skills / agents rather than do work itself? Yes → `orchestrate`.
- **Not-examples**: skill-create calls Python scripts for each gate but the primary effect is producing a new skill — `create`, not `orchestrate`.

### `communicate`
Escalates, notifies, or produces external output to users / other systems.

- **Examples**: (reserved — no strong fit in the current catalog; candidates are future escalation / notification skills)
- **Test**: Does this skill's primary effect reach a human or an external system rather than modify local state? Yes → `communicate`.
- **Not-examples**: research-deep crawls external docs but its primary effect is building a local skeleton — `create`, not `communicate`.

### `decide`
Committee-gated decision-making. Produces an authoritative decision record.

- **Examples**: (reserved — committee is more `orchestrate` than `decide` because its primary effect is routing votes, not producing a verdict file)
- **Test**: Does the skill produce a decision record that downstream skills consult as authoritative? Yes → `decide`.
- **Not-examples**: interview-simulate produces a score but not a decision — `evaluate`.

## Multi-capability skills

If a skill genuinely performs multiple capabilities (e.g., skill-improve both reads consumers via `kiho_rdeps.py` AND updates the target skill body), classify by **primary effect**:

- What is this skill's *reason for existing*?
- Which side-effect would users describe first if asked "what does this skill do"?

If two capabilities are equally primary, the skill is probably doing too much and **SHOULD** be split into sub-operations (like `skill-learn op=capture` / `op=extract` / `op=synthesize`) each with its own capability verb.

## How Gate 20 uses this file

`skills/_meta/skill-create/scripts/capability_check.py` (Gate 20) reads the closed set from this file via a simple regex scan for `### \`verb\`` headings. New skills **MUST** declare exactly one verb from this set in their frontmatter `metadata.kiho.capability` field. Missing or out-of-set verbs block the skill-create pipeline with exit code 1.

## Adding a new verb (committee procedure)

The set is closed by design. A new verb **MUST** be added only when ALL of these conditions are met:

1. **Three or more pending / proposed skills** genuinely cannot map to any existing verb by primary effect.
2. **CEO committee** convenes and votes on the addition with a rationale citing the three skills.
3. **The Changelog below** is appended with the new verb, definition, examples, test, and the committee decision reference.
4. **Existing skills** are NOT retroactively re-classified to the new verb unless their primary effect genuinely matches the new definition better than their current verb.

Expected frequency: <1 addition per quarter. A higher rate is a signal that the taxonomy needs restructuring, not just an extra slot.

## Grounding

The closed-set design is not a kiho invention — it mirrors Kubernetes API verbs, the canonical precedent for "many things, cheap selection".

> **Kubernetes Authorization Overview:** *"Determining whether a request is allowed or denied. Determine the requested verb. Kubernetes uses common HTTP verbs (GET, POST, PUT, DELETE) to authorize API requests. These correspond to Kubernetes verbs: get, list, watch, create, update, patch, delete, deletecollection."*
> — Kubernetes documentation, https://kubernetes.io/docs/reference/access-authn-authz/authorization/ §"Review your request attributes" (retrieved 2026-04-15)

kiho's 8 verbs adapt this pattern:
- `create`, `read`, `update`, `delete` — the four CRUD operations shared with SQL DML and HTTP REST.
- `evaluate` — distinct from read because it produces a verdict, not just a retrieval (K8s has no equivalent; the closest is a subjectaccessreview).
- `orchestrate` — distinct from create because it coordinates rather than produces (no K8s equivalent; agent-skill ecosystems need it).
- `communicate` — distinct from read because it reaches outside local state (closest K8s analog is events/eventsink).
- `decide` — reserved for committee-gated decision records (no K8s equivalent; kiho-specific).

The 8-verb cardinality is the empirical sweet spot across three precedent systems:

| System | Verb count | Source |
|---|---|---|
| HTTP REST | 4-5 (GET, POST, PUT, PATCH, DELETE) | RFC 7231 / RFC 9110 |
| SQL DML | 4 (SELECT, INSERT, UPDATE, DELETE) | ISO/IEC 9075 |
| Kubernetes API | 8 (get, list, watch, create, update, patch, delete, deletecollection) | kubernetes.io |

More verbs hurt discrimination (the author/classifier cannot reliably bucket); fewer verbs hurt selectivity (too many distinct operations merge). kiho's 8 is compatible with the K8s cardinality while staying readable.

## Worked examples

### Example 1 — `create` vs `update` on skill-learn

**Input**: skill-learn takes three sub-operations (`capture`, `extract`, `synthesize`). Should the overall skill be `create` or `update`?

**Resolution**: `create`. All three sub-operations result in a new artifact (a new skill, a new reflection entry, a new KB page). The skill does not mutate existing state; the operations are additive.

**Frontmatter**:
```yaml
metadata:
  kiho:
    capability: create
    topic_tags: [authoring, learning]
```

**Anti-example**: if skill-learn had a sub-operation that mutated an existing skill's description based on session behavior, that sub-operation would be `update`, and the skill would be "doing too much" — a candidate for splitting into two skills.

### Example 2 — `evaluate` vs `update` on kb-lint

**Input**: kb-lint runs 12 checks on a wiki tier and produces a verdict report. It does NOT fix any issues automatically.

**Resolution**: `evaluate`. The primary effect is the verdict, not any mutation. If kb-lint grew an auto-fix mode, that mode would be a separate sub-operation with `capability: update`.

**Frontmatter**:
```yaml
metadata:
  kiho:
    capability: evaluate
    topic_tags: [validation]
```

### Example 3 — `orchestrate` on committee

**Input**: committee runs 5-phase rounds (research, suggest, combine, challenge, choose) with a unanimous close rule. It spawns member sub-agents and tallies their outputs. It does NOT produce a decision record on its own — the close-rule logic emits the verdict.

**Resolution**: `orchestrate`. The primary effect is coordinating multi-agent deliberation. The verdict is a side effect of the routing, not the primary artifact.

**Frontmatter**:
```yaml
metadata:
  kiho:
    capability: orchestrate
    topic_tags: [deliberation, orchestration]
```

**Anti-example**: a future `kiho-vote` skill that takes a proposal and a member list and emits a single decision record (no routing, no phases) would be `decide`, not `orchestrate`. `decide` is currently unused but reserved for this pattern.

## Rejected alternatives

This section records design choices that could have gone differently. MADR 4.0 format: "What it would look like" → "Rejected because" → "Source".

### A1 — 20-verb ontology

**What it would look like.** Instead of 8 closed verbs, an open-ish set of ~20 fine-grained verbs: `author`, `edit`, `review`, `publish`, `retract`, `lint`, `audit`, `transform`, `filter`, `aggregate`, `summarize`, `explain`, `suggest`, `recommend`, `approve`, `reject`, `dispatch`, `notify`, `escalate`, `archive`.

**Rejected because.**
- **Discrimination collapse.** Authors cannot reliably bucket between `author` vs `edit` vs `publish` vs `transform` for a skill that produces a new artifact. Classification variance across authors defeats the facet's selection power.
- **Kubernetes precedent.** K8s converged on 7 verbs across 15 years of API evolution. SQL DML has 4. HTTP REST has 4-5. More verbs have never improved usability in mature taxonomies.
- **Maintenance burden.** A 20-verb set would require per-verb documentation, per-verb worked examples, and per-verb migration rules. The 8-verb set fits in one reference file.

**Source:** Kubernetes API reference (https://kubernetes.io/docs/reference/access-authn-authz/authorization/), SQL:2016 DML spec, RFC 9110 §9.3 (HTTP method definitions).

### A2 — Hierarchical capability taxonomy

**What it would look like.** A tree: `create.skill`, `create.agent`, `create.kb-page`, `update.skill.body`, `update.skill.metadata`, etc. Every skill declares a dot-path instead of a flat verb.

**Rejected because.**
- **Parse overhead.** Every facet-walk gate would need a dot-path parser. The flat regex-matchable set is simpler and faster.
- **Premature hierarchy.** At 38 skills, a two-level taxonomy would put 4-8 leaves under each verb — no discrimination gain over the flat set.
- **Library of Congress precedent.** LCC is hierarchical (Classification → Subclass → Topic), but it has 21 top-level classes and ~500 subclasses for a corpus of millions. Hierarchy pays off at 10³+ entities, not 10¹-10² entities. kiho's catalog is nowhere near that scale.

**Source:** arXiv 2603.02176 §2.1.1 (AgentSkillOS merges single-child categories, validating that shallow taxonomies are preferred at agent-skill scale). Library of Congress Classification (https://www.loc.gov/catdir/cpso/lcco/).

### A3 — Automated capability inference from skill body

**What it would look like.** Gate 20 reads the skill's description + body and infers the capability verb via keyword heuristics or LLM judge. Authors don't declare the field; the pipeline assigns it.

**Rejected because.**
- **Declarative semantics.** The capability field is a commitment by the author about the skill's primary effect. Inferring it would make the field non-authoritative — two runs against slightly different text could produce different verbs.
- **Classification drift.** An LLM judge running on the skill's description would classify `kb-ingest-raw` as `read` (it reads a source document) instead of `create` (the primary effect is producing wiki pages). Authorial intent is load-bearing.
- **Gate determinism.** v5.16 Non-Goal: "No LLM judge at any gate." Only Gate 11 (transcript review) uses a judge.

**Source:** kiho v5.16 plan Non-Goal list. Anthropic "Demystifying Evals" Jan 2026 §step 7 (deterministic gates should stay deterministic).

## Future possibilities (non-binding)

> **Non-binding note (Rust RFC 2561 convention):** *"Having something written down in this section is not a reason to accept the current or a future RFC; such notes should be in the section on motivation or rationale in this or subsequent specs."* The items below are hints for the author who eventually picks each one up. They do not commit kiho to any behavior.

### F1 — Verb-to-tool-allowlist mapping

**Sketch.** Tie each capability verb to a default tool allowlist. `capability: read` implies the skill's `allowed-tools` defaults to `[Read, Glob, Grep]`; `capability: delete` implies `[Read, Edit, Bash(git rm)]` with explicit opt-in for anything broader. Gate 6 would cross-check that a skill's declared tools match its capability verb.

**Not a commitment.** Requires telemetry on whether the mismatch pattern exists (do authors declare `read` and then call `Write`?). If empirical rate is <5%, don't ship F1.

### F2 — Per-verb telemetry rollups

**Sketch.** `skill-invocations.jsonl` already logs per-skill invocations. Add a rollup by `metadata.kiho.capability` to `.kiho/state/capability-usage.md`: weekly counts per verb, outlier detection (e.g., `delete` invocations spiking). Feeds the CEO's weekly INTEGRATE review.

**Not a commitment.** kb-manager already runs `catalog_walk_audit.py` weekly; this would be a companion metric.

### F3 — Sub-capability annotations for multi-op skills

**Sketch.** For skills with sub-operations (like `skill-learn op=capture|extract|synthesize`), allow optional `metadata.kiho.sub_capabilities: {capture: create, extract: update, synthesize: create}`. Gate 20 validates each sub-verb against the closed set. Lets facet walk resolve `skill-learn` for queries that match any sub-op.

**Not a commitment.** Currently skill-learn is classified as `create` (primary effect); the sub-op gap has not caused discovery failures in v5.16.

## Changelog

| Date | Verb | Action | Rationale | Committee ref |
|---|---|---|---|---|
| 2026-04-15 | (all 8) | Initial seed | v5.16 Stage B migration | `plans/bright-toasting-diffie.md` v5.16 execution commitment |
