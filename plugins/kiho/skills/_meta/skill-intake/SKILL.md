---
name: skill-intake
description: Use this skill as the single pre-intake step before skill-create when authoring a new skill from user intent. Merges the former skill-architect intent-reading and skill-spec validation into one pass that produces a single validated intake artifact — proposed fields, per-field rationale, siblings scanned for overlap, critic review if warranted, typed-parameter validation, and dry-run preview. User confirmation gate Step E is non-bypassable; every field must be accepted, overridden, or rejected by the user before the artifact hands off to skill-create. Replaces the pre-v5.20 three-step intake (architect → spec → create) with two steps (intake → create), removing the seam between proposer and validator that confused authors.
argument-hint: "intent=<natural-language>"
metadata:
  trust-tier: T3
  kiho:
    capability: evaluate
    topic_tags: [lifecycle, governance]
    data_classes: ["skill-skeletons", "skill-definitions"]
---
# skill-intake

The single pre-intake step for authoring a new kiho skill from user intent. Produces one validated intake artifact that `skill-create` consumes directly. Collapses the pre-v5.20 three-step pipeline (`skill-architect` → `skill-spec` → `skill-create`) into two steps (`skill-intake` → `skill-create`), removing the seam between proposer and validator that confused authors about which entry point to use.

> **v5.21 cycle-aware.** This skill is the `intake` phase entry in `references/cycle-templates/skill-evolution.toml`. When run from cycle-runner, the cycle's `index.toml` carries `params.skill_target` and `params.mode`; this skill's intake_artifact_ref + spec_ready write back into `index.intake.*`. The User-confirmation Step E (per-field accept/override/reject) remains non-bypassable in either invocation path — cycle-runner relays the gate through `__ceo_ask_user__` semantics if needed. Atomic invocation remains supported.

Before v5.20: Step 0 (architect, intent → proposed spec) and Step 1 (spec, validate declared spec + dry-run) lived in separate skills. Architect already self-validated at its own Step E; spec already accepted a free-form `--from-intent` mode as of 2026-04-17. Two skills, one conceptual pass, two indirections. v5.20 fuses them: one call, one artifact on disk, one handoff.

## When to use

Invoke `skill-intake` when:

- A user writes "I want a new skill that does X" — intent text comes in free-form, spec comes out validated.
- `bin/skill_factory.py --from-intent "<text>"` is being driven in either single-skill or batch mode.
- A `skill-derive` invocation needs an intake artifact for the new child before inheritance is resolved.
- A committee-reviewed regeneration needs a fresh validated spec; `skill-improve` reads the intake ref and carries it forward.

Do **NOT** invoke when:

- The user is editing an existing on-disk skill and wants pattern-audit only — use `pattern_compliance_audit.py`.
- The skill artifact exists and you want behavioral verification — use `skill-verify` (Phase 2).
- You want body-content generation — that is `skill-create`'s job; intake stops at the validated spec.
- You want to deprecate or fold an existing skill — use `skill-deprecate`.

## Inputs

```
intent:           <free-form natural language, 20 ≤ len ≤ 8000 chars>
constraints:      <optional dict>
  capability:     <optional; one of the 8 verbs from references/capability-taxonomy.md>
  domain:         <optional; one of the 9 parent_domain values>
  data_classes:   <optional; list of row slugs from references/data-storage-matrix.md>
parent_for_derive: <optional; skill_id when intake is part of skill-derive>
always_critic:    <bool, default false; force the Step D critic even at high confidence>
allow_exception:  <bool, default false; permit parity-exception layout>
```

Constraints narrow the proposal space before signal extraction fires. `parent_for_derive` carries inheritance context so the intake artifact can record which fields were borrowed vs proposed fresh.

## Six sub-steps (internal)

The six sub-steps run in order. A-B-C-F are deterministic; D is a conditional LLM pass; E is a non-bypassable user gate.

### A. Signals — extract capability/domain/layout hints from intent

Tokenize intent text; match against the hand-curated signal taxonomy in `references/signal-taxonomy.md` (copied forward from the former `skill-spec/references/`). Emit `signals.json` with `capability_scores`, `scripts_signal`, `references_signal`, `topic_scores`, `domain_match`. Deterministic, <100ms, no LLM.

If any constraint was supplied under `constraints:`, the corresponding signal is pinned before scoring so the proposer cannot drift away from a user-stated decision.

### B. Propose — draft skill_spec with per-field rationale

Apply the decision tree in `references/intent-to-structure-rules.md`. Emit `proposal-v0.json`: full `skill_spec` fields (name, parent_domain, capability, topic_tags, description_seed, scripts_required, references_required, parity_layout, data_classes) plus a `rationales` dict keyed by field name and a per-field `confidence` score. Deterministic, <50ms.

Name proposal uses domain prefix + verb-noun shape; collisions against existing `skills/**/SKILL.md` block the proposal and surface a `skill-improve` suggestion inline.

### C. Siblings — scan for overlap with existing skills

Call `skill-find` in reverse-lookup mode with the proposed capability + topic_tags + domain. Call `kb-search` (via `kiho-kb-manager`) for prior reference docs naming the same concept. Compute `sibling_overlap`: count of siblings whose capability+topic_tag set overlaps ≥ 60%, plus a `divergence_score` against the modal layout for the proposed `parent_domain`.

Siblings with overlap ≥ 60% surface as **candidate merges** — the Step E confirmation renders them to the user and offers "author as improvement to `<sibling>` instead". This is the primary defect catch the old architect→spec path missed: overlap was only visible at Step 1's name-collision check, too late to propose a merge.

### D. Critic — conditional one-shot committee

Fires only if any of:

- `proposal-v0.confidence.overall < 0.85`
- `sibling_overlap.divergence_score > 0.30`
- `sibling_overlap.candidate_merges` non-empty
- `always_critic: true`
- any ambiguous capability (top-two verbs within 0.05)

Skip otherwise. When fired, spawn a one-shot critic committee (`committee` skill, 1 round, 1 critic agent) with inputs `(intent, signals, proposal-v0, sibling_evidence)`. Critic returns `proposal-v1` with confirm/override per field and rationale. Disagreements between deterministic proposal and critic are **surfaced side-by-side** at Step E — never silently reconciled.

Critic is a single sub-agent, not a full deliberation; the CEO-committee vote path is reserved for vocabulary and trust-tier changes.

### E. User confirmation — non-bypassable

CEO renders the proposed spec as a markdown table with columns `field | proposed | rationale | confidence | critic_override?`. The user must, for **every** field, choose one of:

- **accept** — confirmed as proposed
- **override** — user supplies replacement value; recompute any dependent field (layout follows scripts+references; name follows domain+verb)
- **reject** — restart the intake with refined intent

No field defaults to accept. Confidence=1.0 does not short-circuit: trust-tier doctrine requires an explicit user touch per field. Five or more overrides trigger the Route-M prompt "restart intake with refined intent?" inherited from the former architect playbook.

Per-field overrides that change `parent_domain` or `scripts_required` loop back to re-run Step C only for that field's domain; other rationales carry forward unchanged.

### F. Validate — schema check + dry-run + emit artifact

Run the typed-parameter schema check from `references/parameter-schema.md` against the confirmed spec. Routes A-F (schema / vocabulary / layout / name-collision / description-seed-length) are inherited unchanged from the former `skill-spec --validate`. Emit the tree-diff dry-run preview of the would-be SKILL.md skeleton.

Persist the intake artifact via `storage-broker` at `<project>/.kiho/state/intake/<slug>.md` with `kind=generic, human_legible=true, tier=1`. The artifact is the **handoff object**; `skill-create` reads it directly and does not re-derive or re-validate.

## Intake artifact

Stored at `<project>/.kiho/state/intake/<slug>.md` as Tier-1 markdown (committee-reviewable post-hoc). Structure:

```markdown
# Intake — <slug>

intake_id:    in-<8char>
created:      <ISO8601>
intent_text:  |
  <verbatim, redacted of any PII>

## proposed_spec
name:                <kebab-case>
parent_domain:       <one of 9>
capability:          <one of 8 verbs>
topic_tags:          [<one-or-more from 18>]
description_seed:    <200-1024 chars>
scripts_required:    [...]
references_required: [...]
parity_layout:       <one of 5>
data_classes:        [...]

## rationale
capability:          "top score 1.00 via [synchronize, recompute, update]"
scripts_required:    "signals score 0.70; evidence [arithmetic: recompute, scale: jsonl]"
parity_layout:       "derived from scripts=true + references=false → meta-with-scripts"
name:                "domain-prefix 'core/harness' + verb-noun 'org-sync'"
<one rationale entry per non-empty field>

## sibling_overlap
n_siblings_scanned:  <int>
modal_layout:        <one of 5>
divergence_score:    <float 0..1>
candidate_merges:    [<list of sibling skill_ids with overlap ≥ 60%>]

## critic_review          # present iff Step D fired
fired_because:       <"low_confidence" | "high_divergence" | "merge_candidates" | "always_critic" | "capability_ambiguous">
confirms:            [<field names>]
overrides:           {field: {from: ..., to: ..., reason: ...}}

## user_decisions
<field>:             {decision: accept | override | reject, replacement?: <value>, note?: <text>}
<one entry per field, no field may be absent>

## validation_errors
# empty list when Step F passed; otherwise Route A-F codes
```

Artifact is immutable after emission. Re-intake on the same intent produces a new artifact with a new `intake_id`; diff between artifacts is the audit trail.

## Procedure (concrete tool-use map)

1. **Step A.** Invoke `research` only if the intent mentions a third-party concept the KB does not cover (signal taxonomy is text-local; research cascade guards against stale assumptions, not signal gaps).
2. **Step B.** Pure in-process proposal; no tool calls.
3. **Step C.** Call `skill-find` with reverse-lookup parameters; call `kb-search` through `kiho-kb-manager` for concept hits in `company/wiki/`. Do not read KB paths directly.
4. **Step D.** When triggered, spawn the `skill-intake-critic` sub-agent via `committee` skill with `rounds=1, members=1, confidence_floor=0.90`. Pass proposal-v0 + sibling evidence as structured input. Return path only; no user interaction from within the committee.
5. **Step E.** Call `AskUserQuestion` from the CEO main conversation. Sub-agents **MUST NOT** call this tool; they return `escalate_to_user` structured output instead. One question block per intake is preferred; render the full field table in a single prompt.
6. **Step F.** Call `storage-broker` with `kind=generic, human_legible=true, tier=1, path=<project>/.kiho/state/intake/<slug>.md`. Emit `status: intake_ready, artifact_path: <...>`.

All six steps complete within a single CEO turn. If Step E blocks on the user, the turn suspends and resumes on user reply per Ralph-loop discipline.

## Hand-off to skill-create

`skill-create` is invoked with a single input:

```
intake_ref: <project>/.kiho/state/intake/<slug>.md
```

`skill-create` reads the artifact, honors the confirmed spec verbatim, and runs its own Steps 2-10 (graph → parity → generate → critic → optimize → verify → citation → cousin-prompt → stale-path). It **MUST NOT** re-propose fields, **MUST NOT** re-validate the schema, and **MUST NOT** call `skill-architect` or `skill-spec` — those skills are deprecated post-v5.20 and folded into `skill-intake`.

If `skill-create`'s own critic (Step 5) surfaces a structural concern, the remedy is to re-run `skill-intake` with refined intent; `skill-create` does not modify the intake artifact in place.

## Response shapes

### Success

```json
{
  "status": "intake_ready",
  "intake_id": "in-8f3c2d1a",
  "artifact_path": ".kiho/state/intake/org-sync.md",
  "spec": {
    "name": "org-sync",
    "parent_domain": "core/harness",
    "capability": "update",
    "topic_tags": ["state-management"],
    "parity_layout": "meta-with-scripts"
  },
  "critic_fired": true,
  "user_overrides_count": 1,
  "next_skill": "skill-create",
  "next_input": {"intake_ref": ".kiho/state/intake/org-sync.md"}
}
```

### User reject or restart

```json
{
  "status": "intake_rejected",
  "intake_id": "in-8f3c2d1a",
  "reason": "user_requested_restart",
  "overrides_count": 6,
  "suggestion": "re-invoke skill-intake with refined intent text"
}
```

### Validation failure

```json
{
  "status": "validation_error",
  "intake_id": "in-8f3c2d1a",
  "route": "name_collision",
  "errors": ["name 'committee' collides with sk-042"],
  "suggestion": "invoke skill-improve --target skills/core/planning/committee/SKILL.md"
}
```

## Invariants

- **Step E is non-bypassable.** Every field requires an explicit user decision. Confidence=1.0 proposals do not short-circuit. A sub-agent **MUST NOT** accept on the user's behalf.
- **Intake artifact is Tier-1 markdown.** Committee can audit any past intake post-hoc. No sqlite, no JSONL, no scratch-only state. Storage tier chosen per `references/storage-architecture.md` — human-legible governance artifact.
- **Single-pass.** One intake call produces one artifact. Re-running intake produces a new artifact; previous artifacts are immutable.
- **CEO-only AskUserQuestion.** Step E renders through the CEO persona in main conversation. Critic sub-agent returns structured output.
- **Closed vocabularies enforced.** Proposed capability must be one of 8 verbs; topic_tags from the 18-tag vocabulary; data_classes from the storage matrix row slugs. No silent extension.
- **Skill-create consumes intake directly.** No re-derivation, no re-validation, no fallback to `skill-architect` or `skill-spec`.

## Non-Goals

- **Not the generator.** `skill-create` owns body, scripts, and references generation. Intake stops at the validated spec plus dry-run preview.
- **Not a skill-improve.** Intake is for new skills (and for `skill-derive` children). Editing an existing skill is `skill-improve`'s concern, which reads the intake artifact but does not call intake itself on the target.
- **Not a deprecation path.** Marking a skill deprecated, folding skills, or recording supersession is `skill-deprecate` + evolution-history; intake has no role there.
- **Not a vocabulary expander.** The closed 8-verb capability set and 18-tag topic vocabulary are frozen at intake time; additions go through CEO-committee vote.
- **Not a runtime dependency resolver.** Intake records `metadata.kiho.requires` if the user supplies it; does not verify targets resolve.
- **Not a free-form NLU.** Schema is strict; unknown keys are rejected, not silently coerced.

## Migration note

`skill-architect` (sk-037 at `skills/_meta/skill-architect/`) and `skill-spec` (sk-036 at `skills/_meta/skill-spec/`) remain on disk for one release (v5.20 → v5.21) for backcompat. Their bodies will be marked `lifecycle: deprecated` + `superseded-by: skill-intake` in a follow-up change; their scripts remain callable so any tooling pinned to the old paths does not break mid-release.

**New skill authoring MUST route through `skill-intake`.** `bin/skill_factory.py --from-intent` will dispatch to `skill-intake` internally from v5.20 onward; the CLI flag is unchanged. An `evolution-history` row records the merge, both predecessor skill_ids, the rationale ("seam removal between proposer and validator confused authors"), and the v5.20 milestone.

Tooling that directly imported `skills/_meta/skill-architect/scripts/` or `skills/_meta/skill-spec/scripts/` should update imports to `skills/_meta/skill-intake/scripts/` once the new scripts land; until then, the old paths continue to function.

## Grounding

- **`skill-create`** (`skills/_meta/skill-create/SKILL.md`) — downstream consumer of the intake artifact; Steps 2-10 of the factory.
- **`skill-find`** (`skills/_meta/skill-find/SKILL.md`) — sibling scan and reverse-lookup at Step C.
- **`research`** (cascade protocol at `references/research-cascade-protocol.md`) — KB → web → deepwiki → clone → ask-user; Step A optional pre-scan for third-party concepts.
- **`committee`** (`skills/core/planning/committee/SKILL.md`) — one-shot critic spawn at Step D; `rounds=1, members=1, confidence_floor=0.90`.
- **`storage-broker`** (`skills/core/harness/storage-broker/SKILL.md`) — emits the Tier-1 markdown intake artifact at Step F.
- **`kiho-kb-manager`** (`agents/kiho-kb-manager.md`) — sole gateway for `kb-search` at Step C.
- **Capability taxonomy** (`references/capability-taxonomy.md`) — closed 8-verb set enforced at Step F.
- **Topic vocabulary** (`references/topic-vocabulary.md`) — closed 18-tag set enforced at Step F.
- **Storage architecture** (`references/storage-architecture.md`) — Tier-1 rationale for the intake artifact.
- **Soul architecture** (`references/soul-architecture.md`) — intake does not mutate soul; trust-tier doctrine requires explicit user accept at Step E.
