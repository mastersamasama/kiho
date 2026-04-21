# Cycle architecture (kiho v5.21+)

- Version: 1.0 (2026-04-19; v5.21 introduces single-orchestrator kernel)
- Status: canonical — every kiho lifecycle MUST be modeled as a cycle template after v5.21
- Companion: `references/core-abilities-registry.md` (closed verb set), `skills/_meta/cycle-runner/references/template-dsl.md` (DSL spec), `skills/_meta/cycle-runner/references/orchestrator-protocol.md` (execution model)

> Key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** per BCP 14 (RFC 2119, RFC 8174).

## Why

Pre-v5.21 lifecycles (recruit, incident, kb-bootstrap, skill-evolution, decision-cycle, value-alignment) were loose compositions of skills. CEO orchestrated by manually chaining skill A → skill B → skill C with state spread across `plan.md`, `ceo-ledger.jsonl`, `state/incidents/`, `state/recruit/`, `committees/<id>/`, `state/actions/`, etc. This produced four chronic problems:

1. **No SSoT per lifecycle.** The state of "open incident #042" lived in three files; the state of "talent-acquisition-2026-04-19" in five.
2. **CEO mental load ∝ lifecycle count.** Each new lifecycle added more if-else branches in `kiho-ceo.md` LOOP step c.
3. **Evolution required code edits.** Adding a new lifecycle (e.g., onboarding) required edits to recruit, ceremony, agents, ceo, and references all at once.
4. **Cross-session resume / replay / cancel / budget were each implemented per-lifecycle.** kiho-init had budget; recruit didn't; incident-open had implicit budget via timeout; talent-acquisition had nothing.

v5.21 solves this with a **single declarative kernel**: one orchestrator (`cycle-runner`), one DSL (`cycle templates`), one per-cycle SSoT (`index.toml`), one master view (`INDEX.md`). The orchestrator does not know any lifecycle by name — it knows phases, transitions, success conditions, and budgets. Adding a new lifecycle means writing a new template; orchestrator code does not change.

## Non-Goals

- **Not a runtime DAG database.** Templates are sequence + conditional branch + budget; not Turing-complete; no loops, no recursion, no function calls in success conditions. kiho non-goal preserved.
- **Not a workflow editor UI.** Templates are TOML in git; reviewable via PR.
- **Not auto-template-generation.** New templates go through CEO-committee review; the user prompt does not auto-spawn templates.
- **Not a replacement for atomic skills.** All skills (`committee`, `research-deep`, `recruit`, `incident-open`, `postmortem`, `onboard`, ...) remain atomic and callable. Cycle-runner is a wrapper that composes them into a state machine.
- **Not a parallel executor.** Sequential phase execution per cycle; cross-cycle parallelism via CEO's existing fanout cap (5).
- **Not a daemon.** Cycle-runner runs synchronously per `advance` invocation. No background workers, no scheduler, no MCP server.
- **Not a multi-tenant kernel.** One CEO, one project; cycles are project-scoped (or company-scoped for HR/talent).

## Architecture (5 layers)

```
┌──────────────────────────────────────────────────────────────┐
│ 1. User                                                       │
└───────────────┬──────────────────────────────────────────────┘
                │ /kiho <op> <args>
                ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. kiho-ceo (Ralph loop)                                      │
│    INITIALIZE: read cycles/INDEX.md → snapshot org state      │
│    LOOP: pick cycle item → cycle-runner advance → verify      │
│    DONE: regenerate INDEX.md + cycle-events rollup            │
└───────────────┬──────────────────────────────────────────────┘
                │ cycle-runner advance cycle_id=<id>
                ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. cycle-runner (skills/_meta/cycle-runner)                   │
│    - Reads cycles/<id>/index.toml + template                  │
│    - Resolves current phase                                   │
│    - Validates entry_skill is registered under declared verb  │
│    - Invokes entry_skill (Bash/Agent/special CEO escalation)  │
│    - Validates success_condition; transitions phase           │
│    - Writes index.toml; appends handoffs.jsonl                │
│    - Emits cycle-events.jsonl row                             │
│    - Returns escalate_to_user when phase = __ceo_ask_user__   │
└───────────────┬──────────────────────────────────────────────┘
                │ entry_skill = ...
                ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. Core abilities (7 verbs) — the kiho kernel API             │
│    research / decide / build / validate / deploy /            │
│    monitor / communicate                                      │
└───────────────┬──────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. Atomic skills (existing kiho catalog)                      │
└──────────────────────────────────────────────────────────────┘
```

**Layer 4 (core abilities) is the API the kernel exports.** Templates declare which verb each phase exercises; the verb maps (via `core-abilities-registry.md`) to one or more atomic skills. The orchestrator never invokes a skill that is not registered under a declared ability — this enforces composition discipline.

## Invariants

- **Single orchestrator.** Only `cycle-runner` advances cycles; no other skill writes to `cycles/<id>/index.toml`.
- **Templates are pinned.** Cycles record `template_version` at open; orchestrator always uses that version even if the template has since been updated. New cycles use the latest version.
- **Per-cycle SSoT is `index.toml`.** Other writes (incident.md, decision.md, committee transcripts, candidate transcripts) are authoritative for the artifact they produce, but the cycle's lifecycle position lives only in `index.toml`.
- **Org-wide INDEX.md is regenerable.** Never hand-edit; it is rebuilt at CEO DONE step 11 from `cycles/*/index.toml`.
- **Handoffs are append-only.** Every phase transition + every escalation appends one JSONL row to `cycles/<id>/handoffs.jsonl`. Replay (`cycle_replay.py`) reconstructs timeline from this stream.
- **DSL is non-Turing-complete.** Success conditions are restricted expressions; transitions form a directed acyclic graph; orchestrator validates this on `open`.
- **CEO-only AskUserQuestion preserved.** Cycle-runner returns `escalate_to_user` payload when phase entry is `__ceo_ask_user__`; CEO is the sole agent that calls AskUserQuestion. **Sequencing is synchronous within one CEO LOOP iteration**: cycle-runner returns the payload → CEO immediately calls `AskUserQuestion` (per `agents/kiho-ceo.md` LOOP.d.VERIFY) → CEO writes the user response into the cycle's index via a follow-up `cycle-runner advance --user-input <json>` call within the same iteration. A second LOOP iteration is NOT required to deliver the user's answer back into the cycle.
- **Atomic skills remain atomic.** Every skill that becomes a cycle phase is still callable directly. Cycle-runner is composition, not replacement.
- **Hooks have a closed verb set.** `lifecycle_hooks` may invoke only: `memory-write`, `kb-add`, `memo-send`, `incident-open`, `standup-log`. Adding new hook verbs requires CEO-committee vote.

## Lifecycle of a cycle

```
USER REQUEST
    │
    ▼
CEO INITIALIZE step 18
    Reads cycles/INDEX.md → no matching open cycle
    OR: cycle-runner open --template-id <X> --params <Y>
    │
    ▼
INDEX.toml created at cycles/<new-id>/
    [meta] phase = first_phase, status = in_progress
    [params] = validated against template parameters
    on_open hooks fire (memo-send, memory-write to ceo)
    Handoffs.jsonl: {action: opened}
    Cycle-events.jsonl: {action: opened, template_id, version}
    │
    ▼
EACH CEO TURN (Ralph iter):
    │
    ├─ CEO LOOP step c picks cycle from plan.md
    │
    ├─ cycle-runner advance --cycle-id <id>
    │   1. Read index.toml + template
    │   2. Resolve current phase
    │   3. Render entry_args_template with current index data
    │   4. Invoke entry_skill (sub-agent / Bash / special CEO ask)
    │      - On __ceo_ask_user__: return escalate_to_user, stop
    │   5. Read sub-skill output, write back into index.toml
    │      (per phase's output_to_index_path declaration)
    │   6. Evaluate success_condition
    │      - True: transition to on_success phase
    │      - False & retries < N: stay in phase, increment phase iters
    │      - False & retries == N: phase = blocked
    │   7. Append handoffs.jsonl row + cycle-events.jsonl
    │   8. Update budget.iters_used
    │   9. Return JSON: {phase_after, transitioned, escalation, blocker, budget}
    │
    ├─ CEO VERIFY: integrate result into plan.md
    │
    └─ Loop until DONE
    │
    ▼
CYCLE END (any of):
    - Final phase reached + on_success leads to "closed-success"
    - Budget exhausted → status = closed-failure
    - Cancelled by CEO/user → status = cancelled
    - on_close_* hooks fire
    - Handoffs.jsonl: {action: closed, reason}
    - Cycle-events.jsonl: {action: closed, outcome}
    - INDEX.md regenerated at next DONE
```

## Migration strategy

Existing skills (`incident-open`, `recruit`, `kiho-init`, `skill-factory`, etc.) are **wrapped, not replaced**. Two invocation paths coexist:

- **Atomic path (legacy + ad-hoc):** user/CEO calls the skill directly. Skill works as before. State lives wherever it lived before. No cycle index.
- **Cycle path (default for new lifecycles):** CEO calls `cycle-runner open --template-id <X>`. Cycle-runner spawns the skill at the right phase, captures output into `index.toml`, manages transitions. The skill itself doesn't know it's running in a cycle (the wrapper handles state translation).

The skill SKILL.md gets a `cycle-aware` note at the top documenting this duality. The skill author does not need to change anything else.

For lifecycles where the cycle path is the **only** sanctioned path going forward (talent-acquisition, kb-bootstrap), the skill SKILL.md adds a "Recommended invocation" pointing to cycle-runner; direct atomic invocation stays available as escape hatch.

## Evolution model

**Adding a new lifecycle:**
1. Author a new `references/cycle-templates/<name>.toml`
2. Validate via `python bin/cycle_runner.py validate-template --path <name>.toml`
3. Submit to CEO-committee review (template counts as a "skill artifact"; goes through skill-intake → factory → critic gate using the same SOP)
4. On approval, commit. Cycle-runner picks it up at next invocation.

**Adding a new core ability:**
1. Add a row to `references/core-abilities-registry.md`
2. Open a CEO-committee vote (same regime as adding a verb to capability-taxonomy.md)
3. On approval, templates may declare `core_ability: <new-verb>`

**Adding an atomic skill under an existing ability:**
1. Build the skill via normal skill-create / skill-factory pipeline
2. Append it to the ability's row in `core-abilities-registry.md`
3. No vote required (the ability's contract is unchanged)

**Modifying a phase in an existing template:**
1. Edit the template; bump `version`
2. In-flight cycles continue under their pinned old version
3. New cycles use the new version
4. Old version stays in git history; can be re-pinned if rollback needed

This is why kiho can evolve without re-architecting: lifecycle complexity is data, ability vocabulary is a closed verb set, orchestrator code is bounded and stable.

## Storage map

| Artifact | Tier | Path | matrix row |
|---|---|---|---|
| cycle template | T1 | `references/cycle-templates/*.toml` | `cycle-templates` |
| per-cycle index | T1 | `<project>/.kiho/state/cycles/<id>/index.toml` | `cycle-index` |
| master cycle index | T1 (regenerable) | `<project>/.kiho/state/cycles/INDEX.md` | `cycle-master-index` |
| handoffs (per cycle) | T2 | `<project>/.kiho/state/cycles/<id>/handoffs.jsonl` | `cycle-handoffs` |
| cycle events (org-wide) | T2 | `_meta-runtime/cycle-events.jsonl` | `cycle-events` |
| phase artifacts | per-skill | (whatever the atomic skill writes) | (existing rows) |

## CEO loop integration

See `agents/kiho-ceo.md` INITIALIZE step 18 (read INDEX.md), LOOP step c (route cycle items via cycle-runner), DONE step 11 (regenerate INDEX.md). The CEO's role becomes **cross-cycle coordination** — picking which cycle to advance this iter, escalating to user when cycle-runner returns `escalate_to_user`, deciding to cancel a chronically blocked cycle. Within-cycle logic is the template's job.

## Observability

- **Per-cycle replay:** `python bin/cycle_replay.py --cycle-id <id>` reads `handoffs.jsonl` + `index.toml` and renders a human-readable timeline (phase transitions, durations, blockers, escalations, hooks fired)
- **Cross-cycle health:** `_meta-runtime/cycle-events.jsonl` aggregated by `bin/kiho_telemetry_rollup.py` (extended in v5.21 to include cycle metrics)
- **Live snapshot:** `cycles/INDEX.md` always reflects current state (regenerated each turn)
- **Audit trail:** every state change is append-only (handoffs.jsonl + cycle-events.jsonl); index.toml mutations are atomic writes

## What this enables long-term

- **One-line new lifecycles**: `references/cycle-templates/<X>.toml` is the only file needed to add a new flow
- **Replay & debugging**: any cycle can be reconstructed from handoffs.jsonl
- **Cross-cycle reasoning**: CEO can answer "what's happening across the org?" by reading one INDEX.md
- **Budget enforcement**: every cycle has bounded iters / pages / wall-clock; no runaway lifecycles
- **Pause/resume across sessions**: cycle state is on disk; new session reads INDEX.md and resumes
- **Cancellable**: explicit cancel writes final state, hooks fire, audit trail preserved
- **Versioned**: template evolution does not break in-flight cycles

## What this does NOT change

- Atomic skills work as before
- CEO Ralph loop discipline unchanged
- Storage tier doctrine unchanged
- Memory architecture unchanged
- Committee rules unchanged
- KB manager remains sole KB gateway
- Storage-broker remains the storage front-door
- Depth/fanout caps unchanged
