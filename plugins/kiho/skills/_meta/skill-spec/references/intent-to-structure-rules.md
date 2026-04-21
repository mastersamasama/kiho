# intent-to-structure rules — worked examples and escalation paths

How `skill-architect` maps free-form user intent to structural choices. Companion to `signal-taxonomy.md` (the closed signal vocabulary) — this file is the *narrative* explanation with worked cases, escalation paths, and the override-semantics for Step E user confirmation.

> Key words **MUST**, **MUST NOT**, **SHOULD**, **MAY** per BCP 14 (RFC 2119, RFC 8174).

## Non-Goals

- **Not the canonical signal source.** That is `signal-taxonomy.md`. This file references the taxonomy; vocabulary changes happen there, not here.
- **Not exhaustive.** Worked examples cover the common kiho intent shapes; edge cases escalate via the failure playbook to the LLM critic and ultimately user.
- **Not a body-content generator.** Architect produces the spec; body comes from `skill-create` Step 4 of the factory SOP.

## The 9-field spec architect produces

Every architect run produces a complete `skill_spec` struct with these 9 fields:

| Field | Source | Determinism |
|---|---|---|
| `name` | derived from intent's primary verb + noun | deterministic |
| `parent_domain` | top match in domain-keyword scan | deterministic |
| `capability` | top match in 8-verb scan | deterministic |
| `topic_tags` | top 1-2 matches in 18-tag scan | deterministic |
| `description_seed` | first 200-1024 chars of intent | deterministic |
| `scripts_required` | derived from arithmetic + scale + side-effect signals | deterministic |
| `references_required` | derived from narrative + reference-data signals | deterministic |
| `parity_layout` | joint of scripts + references | deterministic |
| `parity_exception` | absent unless none-of-the-above signals trigger escalation | rare |

Each field carries a `rationale` (one-line evidence) and contributes to overall `confidence`.

## Worked examples — by canonical pattern

### Pattern 1: arithmetic-over-data → meta-with-scripts

**Intent shape**: "Compute / recompute / aggregate X from data files. Apply formula Y. Update target."

**Examples from kiho catalog**:
- org-sync: "Synchronizes... recomputes proficiency entries from JSONL performance data" → `meta-with-scripts` + `scripts_required: [recompute_proficiency.py]`
- catalog_walk_audit: "Weekly catalog health audit: orphans, stale DRAFTs, confusability" → `meta-with-scripts` + `scripts_required: [audit.py]` (lives in bin/ as cross-skill, but layout pattern matches)
- pattern_compliance_audit: "Deterministic P1-P9 pattern-compliance scorer" → `meta-with-scripts` (lives in skill-create's scripts/, but pattern matches)

**Architect's signal pattern**: arithmetic verb (recompute / aggregate / score) + scale word (JSONL / batch / all entries) + side-effect verb (append / write).

**Decision**: `parity_layout: meta-with-scripts`. Scripts named after primary verb (e.g., `recompute.py`, `audit.py`).

### Pattern 2: procedural-explanation → meta-with-refs

**Intent shape**: "Run an N-step procedure. First X, then Y, finally Z. See <reference> for full spec."

**Examples**:
- recruit: "6 interview rounds via interview-simulate, role-spec planner, mini-committee" → `meta-with-refs` + `references_required: [interview-rounds.md, smoke-test.md, quality-scorecard.md]`
- design-agent: "12-step pipeline drafts a v5 soul, validates tool allowlist, runs interview-simulate" → `meta-with-refs` + `references_required: [capability-gap-resolution.md, output-format.md]`

**Architect's signal pattern**: multi-step marker (numbered phases / first-then-finally) + reference-data marker (rubric / template / schema) + narrative-explanation marker (rationale / trade-offs).

**Decision**: `parity_layout: meta-with-refs`. References named after primary nouns (e.g., `interview-rounds.md`).

### Pattern 3: heavy meta-skill → meta-with-both

**Intent shape**: "Validate X via Y formula AND surface narrative procedure for Z."

**Examples**:
- skill-create: 24 validation gates (scripts) + 11 reference docs (narrative) → `meta-with-both`
- skill-spec: typed-parameter validator (script) + parameter schema reference (narrative) → `meta-with-both`
- skill-architect: 3 deterministic scripts + signal taxonomy + intent-to-structure rules → `meta-with-both`

**Architect's signal pattern**: arithmetic + multi-step + narrative-explanation simultaneously.

**Decision**: `parity_layout: meta-with-both`. Multiple scripts and references.

### Pattern 4: dispatcher / router → standard

**Intent shape**: "Dispatch X to Y. Route based on Z. Return result."

**Examples**:
- kiho-spec, kiho-setup, kiho-init: thin orchestrators that delegate via `Agent` tool, no compute → `standard`
- skill-find: faceted retrieval that wraps facet_walk.py (script lives in scripts/ but pattern is dispatcher) → `parity-exception` (single-purpose retrieval)
- committee: deliberation harness, no arithmetic → `standard`

**Architect's signal pattern**: weak-or-no scripts signals + weak-or-no references signals + verbs are orchestrate / dispatch / route.

**Decision**: `parity_layout: standard`. SKILL.md only.

### Pattern 5: parity-exception case (escalation)

**Intent shape**: doesn't fit any of the 4 above patterns; structural novelty.

**Examples**:
- engineering-kiro: ships a nested `kiro/` directory (legacy first-skill copy)
- skill-find: single-purpose retrieval, no narrative reference, has scripts but doesn't match any other layout

**Architect's signal pattern**: all signal scores < 0.30 OR contradiction (e.g., scripts true + references true but layout shouldn't be `meta-with-both` because actually a special case).

**Decision**: `parity_layout: parity-exception`. **REQUIRES** `parity_exception:` rationale at Step E user confirmation. Logged to `_meta-runtime/parity-exceptions.md`.

## Escalation paths

When architect cannot decide a field, the failure playbook routes:

| Condition | Failure route | User-facing prompt |
|---|---|---|
| All signal scores < 0.30 | Route B | "I cannot propose defaults from this intent. Please provide:" + 9-field manual prompt |
| Capability tie within 0.05 | Route C | "Two capabilities tied: `[verb1, verb2]`. Which fits your intent?" |
| 0 topic tags above threshold | Route D | "No topic tags matched strongly. Top 3 candidates: `[tag1, tag2, tag3]`. Pick 1-2." |
| Sibling divergence > 0.30 | Route F (critic fires) | "Proposal diverges from sibling consensus. Critic recommends: `<value>` because `<rationale>`. Sibling modal is `<modal>` because `<consensus>`. Accept critic's choice or override?" |
| User overrides ≥ 5 fields | Route G | "You overrode 5+ fields. Restart Step 0 with refined intent? (Saves time vs override-by-override.)" |

## Override semantics at Step E

User can:

- **`accept all`** — flow to Step 1 with the proposal as-is
- **Per-field override** — replace one field; re-run Step C only for that field's domain (cheap)
- **Multi-field override** — replace several fields; re-run Step C for each
- **`reject; restart`** — discard proposal; reprompt for refined intent

Override telemetry logged to `_meta-runtime/architect-overrides.jsonl`:
```json
{"timestamp": "2026-04-16T12:00:00Z", "intent_hash": "abc123", "field": "topic_tags",
 "proposed": ["state-management", "hiring"], "overridden_to": ["state-management"],
 "rationale": "user dropped hiring false-positive"}
```

If a signal's recommendations are overridden in > 30% of cases over 20 invocations, that signal weight is flagged for CEO-committee review (NOT auto-tuned).

## Common mistakes the critic catches

These are the categories the critic (Step D) is specifically tuned to catch:

1. **Tautological name** — `synchronize-sync`, `find-find`, `audit-audit`. Critic proposes a noun-led name like `org-sync`, `skill-find`, `lifecycle-audit`.
2. **False-positive topic tag from consumer mention** — intent like "use when X completes" picks up X's tags. Critic drops the tag with rationale "X is a consumer, not the actor".
3. **Layout-domain mismatch** — proposal is `meta-with-scripts` but domain modal is `standard` AND no arithmetic justification. Critic proposes `standard` with rationale "no arithmetic verbs in intent; sibling consensus 80%".
4. **Wrong capability for state-mutating intent** — proposal is `evaluate` but intent has "modify / write / sync" — critic overrides to `update`.
5. **Underspecified topic_tags** — proposal has 0 tags but intent clearly maps to one of the 18 controlled tags. Critic suggests the closest match.

## How to request architect from the orchestrator

Three ways to invoke the factory's Step 0:

```bash
# Single skill from intent text
bin/skill_factory.py --regen-from-intent "Synchronize org registry after workforce changes" --domain core/harness

# Batch from a markdown file (one intent per line)
bin/skill_factory.py --batch-from-intent batch-spec.md

# Skip architect (provide explicit spec)
bin/skill_factory.py --batch _meta-runtime/declared-spec.yaml
```

When `--batch-from-intent` is used, architect runs Step 0 for each line; user sees a single batch-report with N proposals to review at the end (single CEO checkpoint per batch, per the v5.17 reduction).

## Source references

- `signal-taxonomy.md` — the closed signal vocabulary
- v5.18 plan §"Architecture — 6-substep architect pipeline"
- v5.17 research findings §"7 missing pieces #1" — the gap architect closes
- Anthropic skill-creator iterative description optimizer pattern
- Cognition Labs Devin autofix — single-checkpoint reduction principle
