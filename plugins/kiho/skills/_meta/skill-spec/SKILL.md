---
name: skill-spec
description: Typed-parameter resolver and dry-run preview for kiho skill authoring. Two modes. (a) --validate takes a declared skill_spec (name, parent_domain, capability, topic_tags, scripts_required, references_required, parity_layout, batch_id), rejects unknown keys or closed-set violations, and emits a tree-diff preview before any file write. (b) --from-intent takes free-form user intent text and proposes a complete validated skill_spec via deterministic signal extraction + decision tree + sibling pattern observation + optional LLM critic, with per-field rationales for user confirmation. Single source of truth for "what is a well-formed skill-create or skill-improve invocation". Used as Step 0+1 of the skill-factory pipeline. Triggers on "validate this skill spec", "dry-run skill creation", "preview what skill-create would produce", "propose a spec for this intent", "architect this intent", "what should my new skill look like", or when invoked as a sub-step of skill-factory.
metadata:
  trust-tier: T3
  version: 2.0.0
  lifecycle: deprecated
  kiho:
    capability: evaluate
    topic_tags: [authoring, validation]
    data_classes: ["skill-definitions", "skill-skeletons"]
    supersedes: [skill-architect]
    deprecated: true
    deprecated-at: 2026-04-19
    superseded-by: skill-intake
---

> **v5.20 deprecation notice.** Both the intent-proposer mode (`--from-intent`) and the schema-validator mode (`--validate`) have folded into `skill-intake` (sk-053), the single pre-intake skill for skill authoring. Removing the `skill-architect → skill-spec → skill-create` seam that previously confused authors. This skill remains for one release to support in-flight invocations; new authors should route through `skill-intake`.

# skill-spec

Typed-parameter resolver + dry-run previewer + intent-driven spec proposer. The factory's Steps 0 and 1 — every `skill-create` / `skill-improve` / `skill-derive` invocation **MUST** resolve to a validated `skill_spec` struct before any file write. Without this, malformed invocations or underspecified intents slip through the pipeline and surface as defects only after artifacts ship.

Two modes:

- **`--validate`** — takes a declared `skill_spec`, rejects unknown keys and closed-set violations, emits a tree-diff preview. Factory Step 1.
- **`--from-intent`** — takes free-form intent text, proposes a complete `skill_spec` via 6 sub-steps (extract signals → propose spec → observe siblings → optional LLM critic → user confirmation → validate), emits per-field rationales. Factory Step 0 (absorbed from the former `skill-architect`, deprecated 2026-04-17).

Modeled on Backstage Software Templates' `parameters:` JSONSchema + `dry-run` mode, plus Anthropic skill-creator's iterative optimizer pattern for the intent mode.

## When to use

Invoke in `--validate` mode when:

- The user asks "what would skill-create produce for this input?" — preview before commit
- A factory orchestrator is processing a batch and needs Step 1 resolution
- A skill author wants to validate an in-progress brief against the canonical parameter schema
- A reviewer wants the tree-diff of a planned regeneration before approving

Invoke in `--from-intent` mode when:

- A new skill is being authored from intent text and the user wants structural defaults proposed
- The user writes "I want a skill that does X" — the spec is derived, not declared
- The factory is processing a `--from-intent` batch — this skill runs as Step 0 per skill
- A `skill-improve` invocation needs structural suggestions (e.g., "should I add scripts/?")

Do **NOT** invoke when:

- The skill is already on disk and you want behavioral verification — use `skill-verify` (Phase 2)
- You want pattern-compliance audit on existing artifacts — use `pattern_compliance_audit.py`
- You want body content generation — `skill-create` does that at Step 4; this skill produces the spec only
- You want to mutate an existing skill's body — use `skill-improve`

## Non-Goals

- **Not a generator.** Validates inputs and previews outputs; `skill-create` does the generation.
- **Not autonomous.** `--from-intent` proposes; user confirms at Step E. Even confidence=1.0 proposals require explicit user accept.
- **Not a frontmatter validator.** Gate 1 + `pattern_compliance_audit.py` validate artifact frontmatter; this skill validates the *invocation*, not the *artifact*.
- **Not a runtime executor.** Dry-run emits a markdown tree-diff; no file writes. Actual write path is `skill-create` + `skill-factory`.
- **Not a free-form NLU.** The parameter schema is strict — unknown keys rejected, not silently dropped. Intent mode uses a hand-curated signal taxonomy, not open-ended LLM parsing.
- **Not a CATALOG mutator.** Previews new CATALOG entry shape; `bin/catalog_gen.py` does the post-write regen.
- **Not a multi-skill orchestrator.** One spec at a time. Batches are `bin/skill_factory.py --batch`'s concern.
- **Not a vocabulary expander.** Cannot extend the closed 8-verb capability set or 18-tag topic vocabulary. Vocabulary additions go through CEO-committee vote.
- **Not embedding-based.** Intent-mode signal matching is hand-curated keyword vocab + simple stemming. No vector similarity, no model dependency.

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are interpreted per BCP 14 (RFC 2119, RFC 8174).

## Mode — `--validate` (factory Step 1)

### Parameter schema

Every `skill-create` / `skill-improve` / `skill-derive` invocation **MUST** resolve to:

```yaml
skill_spec:
  name:               <kebab-case, ≤ 64 chars, lowercase, no "anthropic"/"claude">
  parent_domain:      _meta | core/harness | core/hr | core/inspection | core/knowledge | core/planning | kb | memory | engineering
  capability:         create | read | update | delete | evaluate | orchestrate | communicate | decide
  topic_tags:         [<one-or-more from references/topic-vocabulary.md>]
  description_seed:   <string, ≥ 200 chars, ≤ 1024 chars; first paragraph of intended description>
  scripts_required:   [<list of script filenames the skill will ship>]
  references_required: [<list of reference markdown filenames>]
  parity_layout:      standard | meta-with-scripts | meta-with-refs | meta-with-both | parity-exception
  parity_exception:   <one-line rationale>  # required iff parity_layout == parity-exception
  batch_id:           <optional UUID; set by orchestrator when running in batch mode>
  on_failure:         jidoka-stop | escalate | rollback   # default: jidoka-stop
```

Full JSONSchema-style validation rules in `references/parameter-schema.md`. Invocation: `python scripts/dry_run.py --spec <yaml-file>`.

### Failure playbook — validate

**Severity**: error (blocks downstream). **Taxonomy**: schema | vocabulary | layout | conflict.

```
spec resolution failure
    ├─ unknown frontmatter key                  → Route A (reject; surface key list)
    ├─ capability not in closed 8-verb set      → Route B (reject; suggest closest verb)
    ├─ topic_tag not in controlled vocabulary   → Route C (reject; suggest closest tag)
    ├─ parity_layout != standard, no exception  → Route D (reject; require parity_exception rationale)
    ├─ name collision with existing skill       → Route E (reject; suggest skill-improve instead)
    └─ description_seed length out of bounds    → Route F (reject with min/max bounds)
```

**Route A**: parse input YAML in strict mode. Exit 1 with `status: schema_violation` + valid keys list.
**Route B**: check against `references/capability-taxonomy.md` (8 verbs). Suggest closest via Levenshtein. Exit 1 with `status: capability_invalid`.
**Route C**: check against `references/topic-vocabulary.md` (18 tags). Suggest closest per invalid tag. Exit 1 with `status: topic_vocab_violation`.
**Route D**: diff against canonical for `parent_domain` in `skill-structural-gate/references/canonical-layouts.md`. Exit 1 with `status: parity_violation` unless `parity_exception:` rationale present.
**Route E**: walk `skills/**/SKILL.md` for name collision. Suggest `skill-improve` on existing. Exit 1 with `status: name_collision`.
**Route F**: enforce 200 ≤ len(description_seed) ≤ 1024. Exit 1 with `status: description_seed_length` + bounds.

## Mode — `--from-intent` (factory Step 0)

### 6-substep architecture

```
Step A — extract_signals.py    (deterministic; <100ms)
   tokenize intent → match signal taxonomy
   output: signals.json with capability_scores, scripts_signal, references_signal, topic_scores, domain_match
   │
   ▼
Step B — propose_spec.py        (deterministic; <50ms)
   apply decision tree from signal-taxonomy.md
   output: proposal-v0.json with full spec + per-field rationales + confidence
   │
   ▼
Step C — observe_siblings.py    (deterministic; <500ms)
   walk catalog; compute modal layout / capability for proposed parent_domain
   output: sibling-evidence.json with divergence_score
   │
   ▼
Step D — critic.md subagent     (LLM; conditional; ~5-15s)
   fires only if proposal.confidence < 0.85 OR sibling.divergence > 0.30 OR --always-critic
   reads (intent + signals + proposal-v0 + sibling-evidence)
   output: proposal-v1.json with confirm/override per field + rationales
   │
   ▼
Step E — user confirmation       (main conversation only)
   render markdown table with proposed values + rationales + confidence per field
   user: accept all | per-field override | reject + restart
   on per-field override, re-run Step C only for the overridden field's domain
   output: confirmed-spec.yaml
   │
   ▼
Step F — handoff to --validate
   pass confirmed-spec.yaml → scripts/dry_run.py
   skill-spec validates and emits tree-diff preview
   factory pipeline continues at Step 1 (same skill in --validate mode)
```

### Inputs (intent mode)

```
intent:           <free-form text, 20 ≤ len ≤ 8000 chars>
always_critic:    <bool, default false; force Step D critic>
allow_exception:  <bool, default false; permit parity-exception layout>
```

### Failure playbook — intent

**Severity**: warn (architect-style — escalate to user, never silently override).

```
intent-mode failure
    ├─ Step A: intent < 20 chars                       → Route G (reject; reprompt for richer intent)
    ├─ Step A: all signal scores < 0.30                → Route H (escalate; flag every field user_input_needed)
    ├─ Step B: capability tie within 0.05              → Route I (flag; surface candidates)
    ├─ Step B: 0 topic tags above threshold 0.4        → Route J (flag; surface top-3)
    ├─ Step C: insufficient siblings (< 2 in domain)   → Route K (skip Step C; confidence -0.1)
    ├─ Step D: critic disagrees with deterministic     → Route L (surface BOTH rationales at Step E)
    └─ Step E: user overrides ≥ 5 fields               → Route M (re-prompt: "restart Step 0 with refined intent?")
```

**Route G**: reject with `status: intent_too_short`. Surface 20-char minimum + examples.
**Route H**: render proposal as "I cannot propose defaults; please provide:" + 9 spec fields with examples.
**Route I**: Step E surfaces top 2-3 candidate verbs with evidence.
**Route J**: Step E surfaces top 3 candidate tags with scores.
**Route K**: skip sibling observation (domain too new). Confidence drops 0.1. Continue to Step D.
**Route L**: Step E renders two columns (deterministic vs critic) with both rationales. Disagreement logged to `_meta-runtime/architect-overrides.jsonl`.
**Route M**: after 5 per-field overrides, prompt for refined intent + optional restart.

## Worked examples

### Example 1 — valid --validate for a new `_meta` skill

Input `skill_spec.yaml`:
```yaml
skill_spec:
  name: skill-watch
  parent_domain: _meta
  capability: orchestrate
  topic_tags: [observability, lifecycle]
  description_seed: "Telemetry-driven regeneration trigger. Aggregates failed eval signals, parity drift, and broken inbound deps into a ranked queue and presents the CEO with a single batch decision per session."
  scripts_required: [queue_watch.py]
  references_required: [signal-sources.md]
  parity_layout: meta-with-both
  on_failure: jidoka-stop
```

Invocation: `python scripts/dry_run.py --spec skill_spec.yaml`

Expected tree-diff:
```
NEW skills/_meta/skill-watch/
├── SKILL.md                    (estimated 240 lines, 7/7 patterns target)
├── scripts/
│   └── queue_watch.py          (estimated 180 lines, 0/1/2/3 exit codes)
└── references/
    └── signal-sources.md       (estimated 120 lines, ≥6/9 patterns target)

Catalog impact:
  + sk-NNN | skill-watch | _meta/skill-watch/
```

Result: `status: ok, dry_run: true` — no files written.

### Example 2 — name collision rejection

Input: `name: kiho` (already exists at sk-001). Expected: exit 1, `status: name_collision`, suggestion: "use `skill-improve --target skills/core/harness/kiho/SKILL.md`".

### Example 3 — --from-intent gap-closing case (org-sync)

Intent: "Synchronizes the live org registry and capability matrix after workforce changes. Recomputes affected proficiency entries from JSONL performance data and appends a Change Log entry. Use when recruit completes a hire or when departments restructure."

Expected pipeline:
- **Step A**: capability `update` score 1.0; scripts_recommended true (0.70 — arithmetic + scale + side_effect); references_recommended false; domain `core/harness`; tags `[state-management, hiring]`.
- **Step B**: layout `meta-with-scripts`, scripts_required `[recompute.py]`, name `org-sync`.
- **Step C**: 5 core/harness siblings, modal `standard` (0.80) — divergence 1.0.
- **Step D** fires: critic confirms `meta-with-scripts` (arithmetic verbs justify scripts).
- **Step E**: user reviews; accepts or drops `hiring` false-positive tag.

Result: spec proposed correctly from intent alone. User does not have to ask "no need any script?" — architect-mode already answered with rationale.

### Example 4 — --from-intent standard layout (committee)

Intent: "Runs a kiho committee deliberation with N agents and M rounds. Each round members vote and present rationale. Unanimous close ends; tie escalates to CEO."

Expected:
- Step A: capability `decide` or `orchestrate`; scripts_recommended false; references_recommended false; domain `core/planning`; tags `[deliberation]`.
- Step B: `standard` layout, empty scripts and references.
- Step C: core/planning siblings 3, modal `standard`. No divergence.
- Step E: high confidence (~0.85), user accepts.

## Response shapes

### --validate response
```json
{
  "status": "ok | schema_violation | capability_invalid | topic_vocab_violation | parity_violation | name_collision | description_seed_length",
  "dry_run": true,
  "spec_resolved": {
    "name": "skill-watch",
    "parent_domain": "_meta",
    "capability": "orchestrate",
    "topic_tags": ["observability", "lifecycle"],
    "scripts_required": ["queue_watch.py"],
    "references_required": ["signal-sources.md"],
    "parity_layout": "meta-with-both"
  },
  "tree_diff": "NEW skills/_meta/skill-watch/\n├── SKILL.md ...",
  "catalog_impact": "+ sk-NNN | skill-watch | _meta/skill-watch/",
  "errors": [],
  "warnings": []
}
```

### --from-intent response
```json
{
  "status": "proposed | needs_user_input | intent_too_short | error",
  "intent_text": "...",
  "spec": {
    "name": "org-sync",
    "parent_domain": "core/harness",
    "capability": "update",
    "topic_tags": ["state-management"],
    "description_seed": "Synchronizes the live org registry...",
    "scripts_required": ["recompute.py"],
    "references_required": [],
    "parity_layout": "meta-with-scripts"
  },
  "rationales": {
    "capability": "top score 1.00 via ['synchronize', 'recompute', 'update']",
    "scripts_required": "signals score 0.70 (recommended); evidence: ['arithmetic: recompute', 'scale: jsonl']",
    "parity_layout": "derived from scripts=true + references=false → meta-with-scripts"
  },
  "confidence": {"capability": 1.0, "layout": 0.70, "overall": 0.85},
  "sibling_evidence": {
    "n_siblings": 5,
    "modal_layout": "standard",
    "divergence_score": 1.0
  },
  "critic_notes": "...",
  "flags": {"needs_critic": true, "capability_alternates": []},
  "next_step": "user_confirmation"
}
```

## Anti-patterns

- **MUST NOT** skip `--validate` on a skill-improve. The spec validates update intent, not just creation.
- **MUST NOT** silent-pass unknown frontmatter keys. Strict mode is the whole point.
- **MUST NOT** auto-extend `references/topic-vocabulary.md` or `references/capability-taxonomy.md`. Vocabulary changes require CEO-committee vote.
- **MUST NOT** ship an unconfirmed `--from-intent` proposal. Step E is non-bypassable.
- **MUST NOT** invoke either mode from inside a sub-agent. Main conversation or a single-level Task subagent only; deeper sub-agents return structured output to the parent.
- Do not treat low-confidence intent proposals as failures. Low confidence fires the critic + surfaces uncertainty to the user.
- Do not log raw intent text to telemetry without redaction. Log hashes + signal vectors only.
- Do not treat dry-run output as authoritative line counts. Estimates vary by ±20%.

## Rejected alternatives

### A1 — Free-form NLU intake (no strict schema)

Accept any natural-language brief; skill-create infers internally. Rejected: pre-v5.17 kiho did this and got 4 regen passes with silent defects. Backstage's JSONSchema `parameters:` pattern is the correct shape.

### A2 — JSON Schema as a separate file

Ship `skill-spec.schema.json` + `jsonschema` PyPI dep. Rejected: CLAUDE.md Non-Goal "Not a runtime database" implies no extra deps; schema lives in YAML+prose at `references/parameter-schema.md`.

### A3 — Validate at write time, not at intake

Skip dry-run; let `skill-create` discover violations during its gates. Rejected: defeats prevention-vs-inspection (Shingo). Caught at intake = zero artifacts; caught at gate 6 = half-completed skill on disk.

### A4 — Inline schema in every `_meta` SKILL.md

Rejected: DRY — schema shared across skill-create + skill-improve + skill-derive. Single source at `references/parameter-schema.md`.

### A5 — Pure LLM intent → spec (no deterministic steps)

Skip Steps A-C; just ask Claude. Rejected: non-deterministic, hard to audit. Deterministic-first handles ~70% reproducibly; LLM critic fires only at low confidence.

### A6 — Embedding-based intent matching against existing descriptions

Rejected: CLAUDE.md "Not a pre-loaded embedding index". Hand-curated signal taxonomy is deterministic + explainable + zero PyPI dep. Similar descriptions don't necessarily imply similar structure.

### A7 — Auto-confirm intent proposal at high confidence

Skip Step E if confidence > 0.95. Rejected: trust-tier doctrine requires explicit user accept even at confidence=1.0.

### A8 — Keep skill-architect as a separate skill

Rejected (2026-04-17 slim-and-consolidate): architect is Step 0 intent→spec; skill-spec is Step 1 spec-validate. The boundary was thin; architect already self-validated at Step E. Merging removes the "two places for spec logic" authoring drift.

## Future possibilities

Non-binding sketches per RFC 2561.

### F1 — Auto-completion for description_seed

**Trigger**: ≥ 5 reports of "I had to revise description_seed 3+ times before Gate 2 passed".
**Sketch**: `--validate` invokes `score_description.py` at intake; returns suggested rewrites without rejecting.

### F2 — Schema versioning + migration

**Trigger**: parameter schema change breaks existing batch-spec files.
**Sketch**: `schema_version: 1.x` in the spec; auto-migrate older versions.

### F3 — Architect handles skill-improve

**Trigger**: ≥ 5 reports of "I want architect suggestions when I run skill-improve".
**Sketch**: `--from-intent --mode improve --target <skill>`. Reads existing spec + telemetry, proposes incremental revisions.

### F4 — Multi-language intent input

**Trigger**: non-English intents from international authors.
**Sketch**: LLM translation pre-step before Step A. Signal taxonomy stays English-only.

### F5 — IDE-style streaming proposal

**Trigger**: authors prefer interactive proposal-as-you-type.
**Sketch**: Step A on every keystroke; surfaces signal scores live. Steps B-E run on confirm.

## Grounding

- **Typed-parameter scaffold pattern.**
  > **Backstage Software Templates §Writing Templates**: *"parameters takes the same structure as a JSONSchema, with some extensions for customizing the look and feel."*
  Adopted as the strict YAML schema; kiho's markdown-centric constraint replaces JSONSchema with YAML+prose validated by hand-coded Python. https://backstage.io/docs/features/software-templates/writing-templates

- **Dry-run-before-write discipline.**
  > **Backstage `dry-run` mode docs**: *"Dry-run mode previews the full filesystem result before any step executes."*
  Adopted: tree-diff in markdown before commit.

- **Iterative description optimizer (intent mode).**
  > **Anthropic `skill-creator/scripts/run_loop.py`**: *"--max-iterations 5 with 20 trigger-eval queries, 60/40 train/test split, best-by-test-score selection."*
  Adopted as the model for the deterministic-then-critic loop in `--from-intent`. https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md

- **Mistake-prevention vs defect-inspection.**
  > **Shingo Institute on mistake-proofing**: *"Mistakes are inevitable, but defects (mistakes that reach the customer) are preventable through poka-yoke."*
  Grounds strict-mode rejection + intent-mode user confirmation. https://shingo.org/mistake-proofing-mistakes/

- **GEPA Pareto-frontier (intent mode Step C).**
  > **GEPA paper (Agrawal et al. 2025)**: *"maintains a Pareto frontier of candidate prompts to avoid local optima."*
  Sibling observation follows the same logic: don't force a single canonical; observe per-domain modal patterns. https://arxiv.org/abs/2507.19457

- **Single source of truth.**
  > **CLAUDE.md §Invariants**: *"kb-manager is the sole KB gateway."*
  Same applied to parameter schema: skill-spec is the sole resolver; skill-create / skill-improve / skill-derive consume it.
