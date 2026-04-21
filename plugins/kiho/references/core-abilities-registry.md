# Core abilities registry (kiho v5.21+)

- Version: 1.0 (2026-04-19)
- Status: canonical — closed 7-verb set; templates MUST declare `core_ability` from this list
- Companion: `references/cycle-architecture.md`, `references/capability-taxonomy.md` (sibling closed vocabulary for skills)

> Key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** per BCP 14 (RFC 2119, RFC 8174).

## Purpose

Cycle templates declare each phase's `core_ability` as one of the 7 verbs below. Cycle-runner validates that the phase's `entry_skill` is listed under that ability. This enforces composition discipline: a phase that says it researches MUST invoke a skill registered under `research`, not `decide` or `build`.

The 7-verb set is **closed**. Adding a new verb requires CEO-committee vote (same regime as `references/capability-taxonomy.md` and `references/topic-vocabulary.md`).

Adding a new atomic skill under an existing ability is a normal skill-author commit; no vote needed.

## Sibling relationship with `capability-taxonomy.md`

`core_ability` (this file, 7 verbs) classifies **what a cycle phase exercises**. `metadata.kiho.capability` (`references/capability-taxonomy.md`, 8 verbs) classifies **what a single skill does**. A phase's `entry_skill` **MAY** carry any capability verb compatible with the phase's core-ability:

| core_ability (phase verb) | compatible skill capability (metadata.kiho.capability) |
|---|---|
| `research` | `read`, `evaluate` |
| `decide` | `decide` |
| `build` | `create`, `update` |
| `validate` | `evaluate` |
| `deploy` | `orchestrate`, `update` |
| `monitor` | `read`, `evaluate` |
| `communicate` | `communicate` |

Notes:
- `decide` and `communicate` appear in both vocabularies with matching semantics — a `decide` phase calls a `decide` skill; a `communicate` phase calls a `communicate` skill.
- `orchestrate` exists only in `capability-taxonomy.md`. Orchestration skills compose other skills; they surface at the cycle layer under `deploy` (when the composition ships external state) or are used outside any cycle (atomic invocation).
- `research` and `monitor` both accept `read` + `evaluate` because both are evidence-gathering activities; cycle-runner disambiguates them by phase position, not skill capability.
- Cycle-runner refuses to open a cycle whose phase declares a `core_ability` that does not list the phase's `entry_skill` in the atomic-skills section below. The capability column is advisory: a skill registered here but carrying an incompatible capability verb is a skill-authoring bug, not a cycle-runner error.

## The 7 verbs

### `research`

**Definition.** Acquire information that did not exist in the agent's working context. Either from external sources or from internal knowledge that needs to be surfaced.

**Atomic skills:**
- `skills/core/knowledge/research/SKILL.md` — 5-step cascade (KB → web → deepwiki → clone → ask-user)
- `skills/core/knowledge/research-deep/SKILL.md` — BFS over doc tree with novelty exhaust
- `agents/kiho-kb-manager.md` op=`kb-search` — KB query (sole KB gateway)
- `agents/kiho-kb-manager.md` op=`kb-ingest-raw` — ingest source material into raw/

**Typical phase shapes:** discovery, scope-research, landscape-scan, competitor-survey, capability-gap-research, doc-exhaust.

---

### `decide`

**Definition.** Choose between options, with audit trail. The chosen option becomes a load-bearing decision that downstream phases consume.

**Atomic skills:**
- `skills/core/planning/committee/SKILL.md` — multi-round structured deliberation
- `skills/core/planning/decision-audit/SKILL.md` — re-eval past decisions
- `__ceo_ask_user__` — SPECIAL pseudo-skill: cycle-runner returns `escalate_to_user` payload; CEO is the sole agent that calls AskUserQuestion

**Typical phase shapes:** tool-choice, scope-confirmation, user-confirm, reversal-review, severity-classification.

---

### `build`

**Definition.** Produce a new artifact: code, agent definition, KB page, skill draft, scaffold, ramp-up plan.

**Atomic skills:**
- `skills/_meta/skill-create/SKILL.md` — produce SKILL.md from intake artifact
- `skills/_meta/skill-derive/SKILL.md` — fork an existing skill into a variant
- `skills/core/hr/design-agent/SKILL.md` — 12-step agent designer
- `skills/core/hr/onboard/SKILL.md` — ramp-up plan + mentor pairing
- `skills/core/hr/recruit/SKILL.md` — full recruit pipeline
- `skills/core/hr/rejection-feedback/SKILL.md` — close-out memos
- `skills/core/ops/incident-open/SKILL.md` — incident.md authoring
- `skills/core/ops/postmortem/SKILL.md` — postmortem.md with blameless linter
- `skills/core/ceremony/retrospective/SKILL.md` — retrospective.md authoring
- `skills/core/ceremony/shift-handoff/SKILL.md` — structured continuity output
- `skills/core/harness/kiho-init/SKILL.md` — KB bootstrap orchestrator
- `skills/_meta/skill-intake/SKILL.md` — pre-factory intake artifact
- `skills/_meta/skill-factory/SKILL.md` — 10-step skill SOP orchestrator
- `skills/_meta/skill-learn/SKILL.md` — three sub-ops (capture / extract / synthesize); finalize skeleton from research-deep
- `agents/kiho-kb-manager.md` op=`kb-add` — author new KB page through drafts

**Typical phase shapes:** synthesis, scaffold, draft, ramp, codify, open, capture.

---

### `validate`

**Definition.** Apply a deterministic check to an artifact. Returns pass/fail (often with detail). Never mutates the artifact.

**Atomic skills:**
- `skills/_meta/skill-critic/SKILL.md` — 8-axis deterministic rubric
- `skills/core/planning/interview-simulate/SKILL.md` — candidate scoring
- `skills/_meta/soul-validate/SKILL.md` — agent soul schema check
- `agents/kiho-kb-manager.md` op=`kb-lint` — KB consistency check
- `skills/core/ops/postmortem/SKILL.md` blameless linter — root-cause fields validation

**Typical phase shapes:** critic-rerun, lint-pass, score-candidates, validate-spec, blameless-check.

---

### `deploy`

**Definition.** Move an artifact from staging to production. Persisted, visible to other agents, registered in indexes.

**Atomic skills:**
- `skills/_meta/skill-improve/SKILL.md` — apply FIX patch + version bump
- `skills/core/hr/agent-promote/SKILL.md` — IC↔lead role change
- `agents/kiho-kb-manager.md` op=`kb-promote` — KB drafts → wiki atomic move
- `agents/kiho-kb-manager.md` op=`kb-update` — apply KB patch
- `skills/_meta/soul-apply-override/SKILL.md` — apply soul-override into base soul
- `skills/_meta/skill-deprecate/SKILL.md` — retire a skill with consumer migration trail
- `skills/_meta/skill-sunset-announce/SKILL.md` — broadcast deprecation
- `skills/_meta/skill-derive/SKILL.md` — fork an existing skill into a variant (also build)

**Typical phase shapes:** register, promote, ship, atomic-move, version-bump, retire.

---

### `monitor`

**Definition.** Observe state over time and surface signals (drift, failure clusters, low adoption, performance trends). Read-mostly; may emit alerts but doesn't mutate the observed.

**Atomic skills:**
- `skills/core/lifecycle/skill-adoption-check/SKILL.md` — 30/60/90-day adoption review
- `skills/core/hr/performance-review/SKILL.md` — quarterly IC scoring
- `skills/_meta/evolution-scan/SKILL.md` — skill drift / capability gap audit
- `skills/memory/memory-reflect/SKILL.md` — agent drift detection
- `bin/kiho_telemetry_rollup.py` — per-skill rolling stats (invoked from CEO DONE)
- `skills/core/values/values-alignment-audit/SKILL.md` — quarterly value drift detection
- `skills/core/planning/decision-audit/SKILL.md` — past-decision re-eval (also decide)
- `skills/core/planning/capacity-planner/SKILL.md` — agent booking ratio
- `skills/core/hr/performance-review/SKILL.md` — quarterly IC scoring
- `skills/_meta/skill-adoption-check/SKILL.md` — alias for skill-adoption-check (also tracked under build for the agenda-write side)

**Typical phase shapes:** adoption-monitor, perf-snapshot, drift-scan, health-rollup, values-audit.

---

### `communicate`

**Definition.** Move information between agents (or between agent and user via CEO). Asynchronous (memos), aggregated (digests), or broadcast (help-wanted).

**Atomic skills:**
- `skills/core/communication/memo-send/SKILL.md` — point-to-point message
- `skills/core/communication/memo-inbox-read/SKILL.md` — recipient-side triage
- `skills/core/communication/help-wanted/SKILL.md` — capability-filtered broadcast
- `skills/core/ceremony/dept-sync/SKILL.md` (if shipped) — dept-lead aggregation pulse
- `skills/core/ceremony/shift-handoff/SKILL.md` — end-of-session structured handoff
- `skills/core/hr/rejection-feedback/SKILL.md` — structured close-out memos

**Typical phase shapes:** notify, broadcast, escalate, digest, handoff, feedback.

---

## Special pseudo-skills

These are NOT real skills under `skills/`. They are sentinel strings the orchestrator recognizes:

| Sentinel | Verb | Behavior |
|---|---|---|
| `__ceo_ask_user__` | `decide` | Cycle-runner returns `escalate_to_user` payload. CEO calls AskUserQuestion. User response is written back to cycle's `index.toml` via `cycle-runner advance` second call. |
| `__no_op__` | any | Phase succeeds immediately. Used in templates as a placeholder during development; production templates SHOULD NOT use this. |
| `__hook_only__` | any | Phase has no entry skill; `lifecycle_hooks` handle the work. Used for pure transition phases (e.g., "wait for user_confirm field to be true"). |

## How templates declare ability

```toml
[[phases]]
id = "decision"
core_ability = "decide"            # MUST be one of the 7 verbs above
entry_skill = "committee"          # MUST be registered under "decide"
```

If a template declares `core_ability = "decide"` and `entry_skill = "research-deep"`, cycle-runner refuses to open the cycle and emits a validation error.

## How adoption check enforces this

`bin/cycle_runner.py validate-template --path <X>.toml` runs at template authoring time AND at every `op=open`. It checks:

1. Each phase's `entry_skill` is in the registry under the declared `core_ability`
2. All phases' `on_success`/`on_failure` targets refer to existing phases or one of the closed terminal states (`closed-success`, `closed-failure`, `blocked`)
3. The phase graph is a DAG (no cycles in transitions)
4. `lifecycle_hooks` only invoke verbs from the closed hook set
5. `success_condition` parses successfully (restricted DSL)

Validation failure → cycle does not open → CEO sees a clear error message, not a half-baked cycle.

## Adding a new verb (governance)

If a future kiho lifecycle truly needs a verb that doesn't fit the 7 (e.g., a hypothetical `negotiate` verb for multi-party contract negotiation):

1. Author a CEO-committee proposal at `_meta-runtime/proposals/new-verb-<name>.md`
2. Proposal MUST cite ≥2 existing or planned templates that would benefit
3. Proposal MUST list which atomic skills implement the verb (typically requires drafting at least one)
4. Committee runs standard 3-round deliberation
5. On unanimous close, registry gets a new row + this file bumps version

This is the same regime as adding a verb to `references/capability-taxonomy.md`. The 7-verb set is intentionally small and load-bearing.

## Why exactly 7

These verbs cover every operation an organization performs against its environment:

- **research**: I need to know
- **decide**: I need to choose
- **build**: I need to make
- **validate**: I need to check
- **deploy**: I need to ship
- **monitor**: I need to watch
- **communicate**: I need to tell

Most organizational lifecycles compose these in different orders. A hire is research → decide → build → validate → deploy → monitor → communicate. An incident is monitor → research → decide → build (corrective action) → deploy → communicate. A skill evolution is monitor → validate → build → validate → deploy.

If a future lifecycle genuinely needs an 8th verb, the bar is high: show that no existing verb captures it, that ≥2 templates need it, and that ≥1 atomic skill is ready to implement it.

## Versioning

This file is versioned at the top. Bumps:
- Adding a new atomic skill under an existing verb → no version bump (just append the row)
- Adding a new verb → minor bump (1.x → 1.x+1)
- Removing a verb → major bump (1.x → 2.0); requires CEO-committee + 30-day deprecation window for any template that uses it
