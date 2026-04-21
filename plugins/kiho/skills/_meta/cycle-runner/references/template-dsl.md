# Cycle template DSL specification (kiho v5.21+)

- Version: 1.0 (2026-04-19)
- Status: canonical — every `references/cycle-templates/*.toml` MUST conform
- Companion: `cycle-architecture.md`, `core-abilities-registry.md`, `orchestrator-protocol.md`

> Key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** per BCP 14 (RFC 2119, RFC 8174).

## File location

```
references/cycle-templates/<template_id>.toml
```

Template ID matches the filename (without `.toml` extension). Template IDs MUST be kebab-case, ≤40 chars, match `[a-z][a-z0-9-]*`.

## Top-level sections

A valid template has exactly these top-level tables:

```toml
[meta]              # required
[parameters]        # required (may be empty)
[index_schema]      # required
[[phases]]          # required, ≥2 phases
[budget]            # required
[lifecycle_hooks]   # optional (default: empty)
```

Unknown top-level keys cause validation failure.

## `[meta]` — template identity

```toml
[meta]
template_id = "talent-acquisition"        # MUST match filename
version = "1.0.0"                          # semver
description = "..."                        # one-line; ≤200 chars
core_abilities_used = ["research", "decide", "build", "deploy", "monitor"]
                                           # subset of the 7-verb set; for documentation only
inherits_from = ""                         # reserved; v5.21 MUST be empty string
ceo_visible = true                         # whether INDEX.md shows this cycle (default true)
```

Field rules:
- `version` MUST be valid semver
- `core_abilities_used` MUST be a subset of `references/core-abilities-registry.md`
- `inherits_from` MUST be empty in v5.21 (template inheritance reserved for future)

## `[parameters]` — open-time inputs

```toml
[parameters]
required = ["domain", "requestor"]                       # array of param names
optional = { tier = "string", budget_iters_override = "int" }
                                                         # map of name → type
```

Type literals: `string | int | bool | list[string] | list[int]`.

`op=open` validates inputs against this schema. Missing required → fail. Wrong type → fail. Extra params → warning only.

Params are accessible inside templates via `{params.<name>}` interpolation.

## `[index_schema]` — per-cycle index structure

Declares the shape of the per-cycle `index.toml`'s phase-specific tables. Cycle-runner validates writes against this schema.

```toml
[index_schema]
discovery = { tools_landscape_ref = "string", candidates = "list[string]" }
decision = { committee_id = "string", recommended_tool = "string", user_confirmed = "bool" }
research = { skeleton_ref = "string", pages_crawled = "int", status = "enum[in_progress,exhausted,budget_hit]" }
recruit = { cycle_id = "string", winner = "string|null" }
onboard = { status = "enum[not_started,in_progress,complete]" }
```

The orchestrator initializes each declared table to type-default values when a new cycle opens (string → empty, int → 0, bool → false, list → empty, enum → first value, `string|null` → null).

Phase output writes that violate the schema cause `blocker = output_parse_failed` (the phase doesn't transition).

## `[[phases]]` — the state machine

Phases form a directed acyclic graph. The orchestrator validates DAG-ness at `op=open` (cycle in transitions → reject).

```toml
[[phases]]
id = "discovery"                              # MUST be kebab-case, unique within template
core_ability = "research"                     # MUST be in core-abilities-registry
entry_skill = "research"                      # MUST be registered under that ability OR a sentinel
entry_args_template = """                     # multi-line TOML interpolation template
op = "kb-search"
query = "{params.domain} tools landscape"
"""
output_to_index_path = "discovery"            # which [index_schema] table the skill output writes to
success_condition = "len(index.discovery.candidates) >= 2"
                                              # restricted-DSL boolean expression
on_success = "decision"                       # next phase id OR "closed-success"
on_failure = "blocked"                        # next phase id OR "blocked" (default) OR "closed-failure"
budget_iters = 5                              # max retries within this phase before blocked
required_role = "kiho-researcher"             # subagent_type for Agent tool spawning (optional)
output_pages = 0                              # if this phase consumes pages, declare here (default 0)
```

Phase id rules:
- Unique within the template
- MUST NOT be `closed-success`, `closed-failure`, `blocked`, `cancelled`, `paused` (terminal states are reserved)
- MUST appear in some other phase's `on_success` or `on_failure` chain (no orphan phases)

Phase ordering:
- The first phase in `[[phases]]` is the entry phase (cycle starts there at open)
- `on_success` and `on_failure` define the graph; cycle-runner traverses by id

## Restricted success condition DSL

The `success_condition` field uses a deliberately restricted boolean expression language. Supported:

| Construct | Examples |
|---|---|
| Field access | `index.discovery.candidates_count`, `params.domain`, `index.budget.iters_used` |
| Comparison | `==`, `!=`, `<`, `<=`, `>`, `>=` |
| Boolean | `and`, `or`, `not` |
| Built-ins | `len(<list>)`, `is_null(<field>)`, `is_set(<field>)` |
| Literals | strings (single or double quotes), ints, floats, `true`, `false`, `null` |
| Grouping | `(...)` |

Forbidden (will fail validation):
- Function definitions
- Loops, comprehensions
- Arbitrary function calls (only the 3 built-ins are allowed)
- Lambdas
- Attribute access on anything except `index.*` and `params.*`
- Imports
- Side effects (assignments)

Examples:

```
len(index.discovery.candidates) >= 2
index.decision.user_confirmed == true
index.research.status == "exhausted" or index.research.pages_crawled >= 50
not is_null(index.recruit.winner)
(index.budget.iters_used >= 20) and (len(index.recruit.candidates) == 0)
```

## `[budget]` — cycle-wide limits

```toml
[budget]
max_iters = 30                                # total advance() invocations; max 100
max_wall_clock_min = 60                       # since open(); max 180
max_pages = 50                                # for crawl-heavy cycles; max 500
escalate_on_blocked_iters = 3                 # blocked-state advance attempts before escalation memo
```

Hard caps (enforced by cycle-runner; templates cannot exceed):
- `max_iters` ≤ 100
- `max_wall_clock_min` ≤ 180
- `max_pages` ≤ 500

When budget is hit, `status` becomes `blocked` with `blocker_reason: budget_<which>_exhausted`. CEO can `cancel` and reopen with `params.budget_iters_override` (template MUST declare it as optional param).

## `[lifecycle_hooks]` — auto-fire on transitions

Closed verb set: `memory-write`, `kb-add`, `memo-send`, `incident-open`, `standup-log`. Adding a verb requires CEO-committee vote.

Hooks are arrays of strings; each string is a single skill invocation with template-interpolated arguments.

```toml
[lifecycle_hooks]
on_open = [
  "memory-write type=todo agent_id=ceo-01 importance=5 content='Cycle {cycle_id} ({meta.template_id}) opened by {params.requestor}'"
]
on_close_success = [
  "memory-write type=lesson agent_id=ceo-01 importance=8 content='Cycle {cycle_id} succeeded; pattern: <template-specific>'",
  "kb-add page_type=cycle-completion ref={cycle_id}"
]
on_close_failure = [
  "incident-open severity=sev2 trigger_event='cycle {cycle_id} reached failure terminal state'"
]
on_pause = []
on_resume = []
```

Hook execution:
- Synchronous; orchestrator waits for each hook to complete before next
- Best-effort: failures logged to `cycle-events.jsonl` but do NOT block cycle transition
- Order within an array is preserved
- Template interpolation: `{cycle_id}`, `{meta.<X>}`, `{index.<X>.<Y>}`, `{params.<X>}`

## Reserved terminal phase IDs

Templates MUST NOT define phases with these IDs (they are orchestrator-managed terminal states):

- `closed-success` — reached normal completion via on_success chain
- `closed-failure` — explicit failure from a phase's on_failure chain
- `blocked` — couldn't satisfy success_condition or budget exhausted
- `cancelled` — operator invoked `op=cancel`
- `paused` — operator invoked `op=pause` (advance is no-op until resume)

`on_success` / `on_failure` may target these terminal IDs; the cycle then enters that state and fires the matching `on_close_*` hook.

## Validation invariants (enforced at `op=open` and `validate-template`)

1. **Schema:** all required top-level tables present; no unknown keys
2. **Versioning:** `meta.version` is valid semver
3. **Ability mapping:** every phase's `entry_skill` is registered under its `core_ability` in `core-abilities-registry.md` (or is a sentinel)
4. **Sentinel rules:** `__ceo_ask_user__` only allowed under `core_ability = "decide"`; `__no_op__` and `__hook_only__` allowed under any ability
5. **DAG:** phase transition graph has no cycles; `entry phase → ... → terminal state` is reachable
6. **No orphans:** every non-entry phase appears in some other phase's `on_success` or `on_failure`
7. **DSL parse:** every `success_condition` parses cleanly under the restricted DSL
8. **Schema field references:** `success_condition` and `entry_args_template` only reference fields declared in `[index_schema]` or `[parameters]`
9. **Budget caps:** `max_iters` ≤ 100, `max_wall_clock_min` ≤ 180, `max_pages` ≤ 500
10. **Hook verbs:** `lifecycle_hooks` only invoke verbs from the closed set
11. **Template ID match:** `meta.template_id` matches the filename
12. **Reserved ids:** no phase id collides with reserved terminal states

## Worked example

See `references/cycle-templates/incident-lifecycle.toml` for the simplest production template (3 phases, no escalation), and `references/cycle-templates/talent-acquisition.toml` for the most complex (8 phases, includes `__ceo_ask_user__`).

## Authoring workflow

1. Draft `<template_id>.toml` per this spec
2. Run `python bin/cycle_runner.py validate-template --path references/cycle-templates/<template_id>.toml`
3. If validation fails, fix and rerun
4. If new ability mappings or hook verbs needed, run CEO-committee vote first (separate process)
5. Submit through skill-intake → factory → critic gate (templates are treated as a "skill artifact" for review purposes)
6. On committee approval, commit; cycle-runner picks up automatically at next invocation

## Versioning rules

- Patch bump (1.0.0 → 1.0.1): typo, doc-only change in description, hook arg interpolation tweak
- Minor bump (1.0.x → 1.1.0): add new phase, add new optional param, add new hook
- Major bump (1.x.x → 2.0.0): remove a phase, change a phase's id, change `[index_schema]` in a backward-incompatible way

In-flight cycles always use their pinned `template_version`. New cycles open under the latest version.
