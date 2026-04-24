---
name: cycle-runner
description: Use this skill as the single orchestrator for every kiho lifecycle (talent-acquisition, incident-handling, skill-evolution, kb-bootstrap, decision-cycle, value-alignment, research-discovery). Cycle-runner reads a declarative TOML template from references/cycle-templates/, instantiates a per-cycle index.toml as the single source of truth, advances one phase per Ralph iter by invoking the phase's entry skill via the 7 core abilities (research/decide/build/validate/deploy/monitor/communicate), validates success conditions against a restricted DSL (no Turing-completeness), enforces budgets (iters/pages/wall-clock), emits handoffs.jsonl audit trail, and returns escalate_to_user when a phase requires the CEO to call AskUserQuestion. Triggers on "open cycle", "advance cycle", "cycle status", "cycle-runner", "/kiho cycle", or auto-fires from CEO INITIALIZE when an in-flight cycle's index.toml shows phase ready to advance. Replaces the v5.20 pattern of CEO manually chaining skill A → skill B → skill C with state spread across plan.md / ledger / receipts / committees / actions.
metadata:
  trust-tier: T3
  version: 1.0.0
  lifecycle: active
  kiho:
    capability: orchestrate
    topic_tags: [orchestration, lifecycle]
    data_classes: [cycle-index, cycle-master-index, cycle-templates, cycle-events, cycle-handoffs]
---
# cycle-runner

The kiho kernel. Every lifecycle in kiho v5.21+ runs through this single orchestrator. Cycle-runner does not know any specific lifecycle by name — it reads a TOML template, parses the phase graph, and advances one phase per Ralph iter by composing atomic skills via the closed 7-verb core ability registry.

> **Architectural foundation.** See `references/cycle-architecture.md` for the full design rationale, the 5-layer architecture, and the migration story from v5.20's loose-composition pattern. See `references/core-abilities-registry.md` for the 7-verb set. See `skills/_meta/cycle-runner/references/template-dsl.md` for the TOML schema. See `skills/_meta/cycle-runner/references/orchestrator-protocol.md` for the per-advance execution model.

## Contents
- [When to use](#when-to-use)
- [Operations](#operations)
- [Inputs per op](#inputs-per-op)
- [Cycle lifecycle](#cycle-lifecycle)
- [Phase resolution](#phase-resolution)
- [Special entry skills](#special-entry-skills)
- [Budget enforcement](#budget-enforcement)
- [Lifecycle hooks](#lifecycle-hooks)
- [Failure playbook](#failure-playbook)
- [Response shape](#response-shape)
- [Anti-patterns](#anti-patterns)
- [Grounding](#grounding)

## When to use

Invoke cycle-runner when:

- A user wants to start any kiho lifecycle (recruit / incident / kb-bootstrap / skill-evolution / decision / value-alignment / research-discovery)
- CEO INITIALIZE detects an open cycle in `cycles/INDEX.md` that needs an `advance`
- CEO needs to inspect (`status`), pause/resume, cancel, or replay a cycle
- A new template lands in `references/cycle-templates/` and needs validation before first use

Do **NOT** invoke when:

- A skill needs to run as a one-shot atomic call (no state machine) — call the skill directly
- A user request maps to none of the existing templates AND no template is appropriate to author — handle ad-hoc and consider whether a template is warranted afterward
- The current Ralph iter has already advanced 5 cycles (fanout cap) — defer remaining cycles to next iter

## Operations

| Op | Purpose |
|---|---|
| `open` | Instantiate a new cycle from a template; validate parameters; create index.toml; fire `on_open` hooks; first phase becomes current |
| `advance` | Run one phase forward: invoke entry_skill, capture output into index, validate success_condition, transition phase, write handoffs.jsonl row |
| `status` | Read-only: return current phase, budget remaining, blockers, last handoff |
| `pause` | Set status=paused; future `advance` returns no-op until `resume` |
| `resume` | Flip paused → in_progress |
| `cancel` | Set status=cancelled, fire `on_close_failure` hooks, append final handoff row |
| `replay` | Read handoffs.jsonl + cycle-events.jsonl; render human-readable timeline (delegated to `bin/cycle_replay.py`) |
| `validate-template` | Static-check a template TOML before first use; verify DSL grammar, ability mappings, DAG transitions |

## Inputs per op

```
op: open
  template_id: <string>           required; from references/cycle-templates/
  params: <json|toml object>       required; validated against template's [parameters]
  cycle_id: <string>               optional; auto-generated if omitted

op: advance
  cycle_id: <string>               required
  user_input: <json>               optional; supplied when CEO is responding to a __ceo_ask_user__ phase

op: status
  cycle_id: <string>               required
  format: human | json             default: human

op: pause | resume | cancel
  cycle_id: <string>               required
  reason: <string>                 optional but recommended

op: replay
  cycle_id: <string>               required
  detail: brief | full             default: brief

op: validate-template
  path: <path>                     required; absolute or relative to plugin root
```

## Cycle lifecycle

```
open
  ├─ Load template from references/cycle-templates/<template_id>.toml
  ├─ Validate params against template's [parameters]
  ├─ Generate cycle_id: <template_id-prefix>-<iso-date>-<short-uuid>
  ├─ Create state/cycles/<cycle_id>/{index.toml, handoffs.jsonl}
  ├─ Initialize index.toml: meta + budget + params + empty phase data
  ├─ Set phase = first phase in template
  ├─ Fire on_open hooks (memory-write to ceo, etc.)
  ├─ Append handoffs.jsonl: {action: opened, template_version}
  └─ Append cycle-events.jsonl: {action: opened, cycle_id, template_id}

advance (per CEO Ralph iter)
  ├─ Read index.toml + template (using pinned template_version)
  ├─ Resolve current phase
  ├─ If phase entry_skill is __ceo_ask_user__:
  │   - Render question from entry_args_template
  │   - If user_input was passed in: write to index, evaluate success
  │   - Else: return {escalate_to_user: {question, options}}, no transition
  ├─ Else (normal entry_skill):
  │   - Render entry_args_template against {index, params}
  │   - Validate entry_skill is registered under phase.core_ability
  │   - Invoke entry_skill (Bash for scripts; Agent for subagents; direct for fast atomic skills)
  │   - Parse skill output
  │   - Write designated fields back into index.toml (per phase.output_to_index_path)
  ├─ Evaluate success_condition (restricted DSL)
  │   - True: transition phase = on_success target; phase_iters reset
  │   - False & phase_iters < phase.budget_iters: stay; phase_iters++
  │   - False & phase_iters >= phase.budget_iters: phase = "blocked"; record blocker_reason
  ├─ Update budget.iters_used, budget.wall_clock_min_used
  ├─ If new phase is closed-success or closed-failure: fire on_close_* hooks
  ├─ Append handoffs.jsonl row + cycle-events.jsonl row
  └─ Return JSON: {phase_after, transitioned, escalation, blocker_reason, budget}

close (any final state)
  ├─ status = closed-success | closed-failure | cancelled
  ├─ on_close_* hooks fire
  ├─ Final handoff + cycle-event row
  ├─ index.toml's [meta] phase = terminal_state
  └─ INDEX.md regenerated at next CEO DONE step 11
```

## Phase resolution

A phase resolution lookup uses the template's pinned version:

1. `template = load_template(meta.template_id, version=meta.template_version)`
2. `phase = next(p for p in template.phases if p.id == meta.phase)`
3. If `phase` not found → cycle is corrupt; status=blocked + escalate

Phase iteration count tracks how many times we tried to satisfy `success_condition` for the current phase. Resets on transition. Bounded by `phase.budget_iters` (default 5).

## Special entry skills

The orchestrator recognizes three sentinel `entry_skill` strings:

| Sentinel | Behavior |
|---|---|
| `__ceo_ask_user__` | Returns `escalate_to_user` payload. CEO calls AskUserQuestion. Next `advance` invocation MUST include `user_input` to drive the success_condition. |
| `__no_op__` | Always succeeds immediately. Templates SHOULD NOT use this in production; useful for development scaffolding. |
| `__hook_only__` | Phase does no work itself; relies on `lifecycle_hooks` triggered by transitions. Phase auto-succeeds when transitions evaluate. |

All other `entry_skill` values MUST be a registered atomic skill ID under the phase's declared `core_ability` (per `references/core-abilities-registry.md`).

## Budget enforcement

Each cycle has three independent budgets in `index.toml [budget]`:

- `iters_max` — total phase advances; default 30, max 100
- `pages_max` — for cycles that crawl docs (research-discovery, kb-bootstrap, talent-acquisition); default 50, max 500
- `wall_clock_min_max` — total elapsed minutes since open; default 60, max 180

When ANY budget is hit:
- `status` becomes `blocked` with `blocker_reason: budget_<which>_exhausted`
- `on_close_failure` hooks fire if the template treats budget exhaustion as failure (default yes)
- CEO sees blocker in next INDEX.md regeneration

To extend a budget, CEO opens a fresh cycle with `parameters.budget_iters_override` (template MUST declare it as an optional param). Or cancels and reopens with a different template.

## Lifecycle hooks

Templates declare hooks that fire on phase transitions:

- `on_open` — fired when cycle opens (after index.toml created)
- `on_close_success` — fired when cycle reaches a phase that transitions to `closed-success`
- `on_close_failure` — fired on `closed-failure`, `cancelled`, or budget exhaustion
- `on_pause` / `on_resume` — fired on op=pause/resume

Hooks are restricted to a closed verb set:

| Hook verb | Format |
|---|---|
| `memory-write` | `memory-write type=<X> agent_id=<Y> content='<template-string>'` |
| `kb-add` | `kb-add page_type=<X> ref=<template-string>` |
| `memo-send` | `memo-send to=<X> severity=<Y> subject='<template-string>'` |
| `incident-open` | `incident-open severity=<X> trigger_event='<template-string>'` |
| `standup-log` | `standup-log agent_id=<X> did=<...>` |
| `okr-checkin` (v6.2+) | `okr-checkin auto_from_cycle=true` — resolves the cycle's `aligns_to_okr` field from index.toml, derives KR score delta via `bin/okr_derive_score.py`, invokes `okr-checkin` atomic. No-op when `aligns_to_okr` is absent. Gated on `[okr] auto_checkin_from_cycle`. |

Templates referencing other verbs in hooks fail validation. To add a hook verb, run a CEO-committee vote (rare). The `okr-checkin` verb was added in v6.2 via user direct override of committee-01's no-auto-cadence decision (see `_proposals/v6.2-okr-auto-flow/`).

Template strings inside hooks may interpolate `{cycle_id}`, `{template_id}`, `{index.<path>}`, `{params.<name>}`.

### Cycle `aligns_to_okr` field (v6.2+)

Any cycle template's `index_schema` MAY declare an optional `aligns_to_okr: "string"` field at the top level. When set on an individual cycle's index.toml, the `okr-checkin` hook auto-updates the referenced Objective's aligned KR(s) on cycle close.

Resolution order for inheriting this value (cycle-open populates it automatically if empty):

1. Explicit `--aligns-to-okr <o-id>` on cycle-runner op=open.
2. Trigger plan.md task's frontmatter `aligns_to_okr: <o-id>`.
3. Owner agent's active individual O for current period (from scanner cache).
4. Owner agent's dept O for current period.
5. If none resolved, leave empty and log `action: okr_link_unresolved, cycle_id: <id>` (not an error).

This field is the single source of OKR→cycle linkage; `okr-checkin` reads only this field to know which KR(s) to update.

## Failure playbook

```
phase advance fails
  │
  ├─ entry_skill not found             → status=blocked, blocker=skill_not_found:<id>
  ├─ entry_skill output unparseable    → status=blocked, blocker=output_parse_failed
  ├─ success_condition parse error     → status=blocked, blocker=success_condition_invalid
  ├─ success_condition false N times   → status=blocked, blocker=phase_<id>_could_not_satisfy
  ├─ budget exhausted (any)            → status=blocked, blocker=budget_<which>_exhausted
  ├─ on_*_hooks fail                   → log warning, do NOT block (hooks are best-effort)
  └─ template validation fails at open → cycle never opens; clear error returned to caller
```

A blocked cycle's next `advance` is a no-op. CEO must `cancel` (and optionally reopen with adjusted params) or address the blocker manually before the cycle can resume.

## Response shape

```json
{
  "status": "ok | blocked | error",
  "op": "advance",
  "cycle_id": "ta-2026-04-19-crypto-trader",
  "phase_before": "discovery",
  "phase_after": "decision",
  "transitioned": true,
  "iter_in_phase": 1,
  "budget": {
    "iters_used": 8,
    "iters_max": 30,
    "pages_used": 23,
    "pages_max": 50,
    "wall_clock_min_used": 14,
    "wall_clock_min_max": 60
  },
  "escalate_to_user": null,
  "blocker_reason": null,
  "handoff_ref": "jsonl://cycles/ta-2026-04-19-crypto-trader/handoffs#L17",
  "next_action": "Pick this cycle for advance again next iter (or CEO escalation if applicable)"
}
```

When `escalate_to_user` is set:

```json
{
  "status": "ok",
  "op": "advance",
  "cycle_id": "ta-2026-04-19-crypto-trader",
  "phase_before": "user-confirm",
  "phase_after": "user-confirm",
  "transitioned": false,
  "escalate_to_user": {
    "question": "Committee recommends ccxt as the trading SDK. Confirm or override?",
    "options": [
      {"label": "Confirm ccxt", "value": "confirm"},
      {"label": "Override with another SDK", "value": "override"}
    ],
    "phase": "user-confirm"
  },
  "next_action": "CEO calls AskUserQuestion; on response, re-invoke cycle-runner advance with user_input"
}
```

## Anti-patterns

- **Never write to `index.toml` from outside cycle-runner.** Other agents/skills may READ it but never WRITE. The orchestrator owns mutations to preserve handoffs trail integrity.
- **Never invoke an atomic skill that the phase's core_ability does not register.** This is enforced; trying it returns `error: ability_skill_mismatch`.
- **Never embed Turing-complete logic in `success_condition`.** No function calls, no loops, no recursion. If a template needs richer logic, it needs more phases.
- **Never bypass `__ceo_ask_user__` to call AskUserQuestion from within an atomic skill invoked by cycle-runner.** CEO-only invariant is preserved; cycle-runner is the bridge.
- **Never edit a running template.** Edits to `cycle-templates/<X>.toml` only affect cycles opened after the edit. In-flight cycles use their pinned version.
- **Never delete `cycles/<id>/` while status is in_progress.** Use `cancel` first.
- **Never silently skip a hook failure.** Hooks are best-effort, but failures MUST be logged to `cycle-events.jsonl` so they surface in monitoring.

## Non-Goals

- **Not a parallel executor.** Single phase per advance; cross-cycle parallelism is CEO's job (existing fanout cap).
- **Not a workflow editor.** Templates are TOML in git; reviewed via PR.
- **Not a daemon.** Synchronous per `advance` invocation; no background workers.
- **Not a replacement for atomic skills.** Skills remain atomic and callable.
- **Not a runtime DAG database.** DSL is restricted; no general-purpose graph execution.
- **Not multi-tenant.** One CEO, one project; cycles are project-scoped (with company-scoped variants for HR/talent).

## Grounding

- `references/cycle-architecture.md` — master design and migration story
- `references/core-abilities-registry.md` — closed 7-verb set
- `skills/_meta/cycle-runner/references/template-dsl.md` — TOML DSL spec
- `skills/_meta/cycle-runner/references/orchestrator-protocol.md` — per-advance execution model
- `references/data-storage-matrix.md` rows `cycle-index`, `cycle-master-index`, `cycle-templates`, `cycle-events`, `cycle-handoffs`
- `agents/kiho-ceo.md` INITIALIZE step 18, LOOP step c, DONE step 11 — CEO integration points
- `bin/cycle_runner.py` — orchestrator implementation
- `bin/cycle_index_gen.py` — master INDEX.md regenerator
- `bin/cycle_replay.py` — timeline reconstruction
