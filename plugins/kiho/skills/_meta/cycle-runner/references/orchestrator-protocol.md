# Orchestrator protocol (cycle-runner per-advance execution model)

- Version: 1.0 (2026-04-19)
- Status: canonical — `bin/cycle_runner.py` MUST implement this protocol verbatim
- Companion: `template-dsl.md` (template grammar), `cycle-architecture.md` (system context)

> Key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** per BCP 14 (RFC 2119, RFC 8174).

## Atomicity

Every `op=advance` invocation is a single transaction. Either it succeeds entirely (phase advanced or stayed; index.toml + handoffs.jsonl + cycle-events.jsonl updated consistently) or it fails entirely (no writes, error returned).

`index.toml` writes use atomic-replace (write to temp, fsync, rename). `handoffs.jsonl` and `cycle-events.jsonl` are append-only and crash-safe.

## Per-advance execution sequence

```
1. LOAD
   - Read state/cycles/<cycle_id>/index.toml
   - Read references/cycle-templates/<template_id>.toml at the version pinned in index.meta.template_version
   - If either is missing: return {status: error, reason: missing_state_or_template}

2. PRE-CHECK
   - If index.meta.status in {paused, closed-success, closed-failure, cancelled}: return {status: noop, reason: status_<X>}
   - If any budget exhausted (iters_used >= iters_max etc.): mark blocked, fire on_close_failure, return
   - If index.meta.phase in {closed-success, closed-failure, blocked, cancelled}: return {status: noop, reason: terminal}

3. RESOLVE PHASE
   - phase = template.phases[id == index.meta.phase]
   - If phase not found: status = blocked, blocker = phase_id_unknown, return

4. RESOLVE ENTRY
   - If phase.entry_skill == "__ceo_ask_user__":
     - If user_input not provided in advance() call:
       - Render question + options from entry_args_template against {index, params}
       - Append handoff: {action: escalate_to_user, phase}
       - Return {escalate_to_user: {question, options, phase}, transitioned: false}
     - Else (user_input present):
       - Write user_input fields into index per phase.output_to_index_path
       - Skip to step 6 (success_condition evaluation)
   - If phase.entry_skill == "__no_op__":
     - Skip to step 6 (success_condition evaluates against current index)
   - If phase.entry_skill == "__hook_only__":
     - Skip to step 6 (rely on prior phase hooks having populated needed state)
   - Else (real atomic skill):
     - Validate entry_skill is registered under phase.core_ability in core-abilities-registry.md
       - If not registered: status = blocked, blocker = ability_skill_mismatch, return
     - Render entry_args_template against {index, params}; parse as JSON or TOML

5. INVOKE
   - Three invocation modes (orchestrator picks based on skill metadata):
     a. SUBPROCESS — for skills shipping a Python script under skills/<X>/scripts/, invoke via subprocess with rendered args as JSON on stdin or as CLI flags
     b. AGENT — for skills that require a sub-agent (committee, recruit, deep work), spawn via Agent tool with subagent_type = phase.required_role
     c. INLINE — for fast atomic skills (memory-write, kb-search), the orchestrator MAY invoke directly in-process if a Python helper exists; otherwise falls back to AGENT mode
   - Capture skill output as a JSON-parseable dict
   - On invocation timeout (per-skill default 5 min, configurable in template's [budget]): blocker = entry_skill_timeout, return
   - On invocation crash: blocker = entry_skill_crashed:<exit_code>, return

6. WRITE OUTPUT TO INDEX
   - Determine output target: phase.output_to_index_path (e.g., "discovery")
   - Validate skill output fields against template.index_schema[output_path]
     - Type mismatch / unknown field: blocker = output_schema_violation, return
   - Atomic-write merged index.toml

7. EVALUATE SUCCESS_CONDITION
   - Parse phase.success_condition under restricted DSL
   - Evaluate against {index, params} (post-write)
   - Result is bool

8. TRANSITION
   - If success_condition is true:
     - new_phase = phase.on_success
     - If new_phase in terminal states: handle close (fire on_close_*); update index.meta.status
     - index.meta.phase = new_phase, index.meta.phase_entered_at = now()
     - Reset phase_iters counter
   - If false AND phase_iters_in_current < phase.budget_iters:
     - phase_iters_in_current++
     - index.meta.phase unchanged
   - If false AND phase_iters_in_current >= phase.budget_iters:
     - new_phase = phase.on_failure (default: "blocked")
     - index.meta.status = "blocked" if new_phase == "blocked" else "in_progress"
     - blocker_reason = "phase_<id>_could_not_satisfy"

9. UPDATE BUDGET
   - index.budget.iters_used++
   - index.budget.wall_clock_min_used = (now - index.meta.opened_at) in minutes
   - If phase declares output_pages: index.budget.pages_used += output_pages

10. APPEND AUDIT TRAIL
    - handoffs.jsonl: {ts, cycle_id, from: phase_before, to: phase_after, transitioned, reason, emitted_by: "cycle-runner"}
    - cycle-events.jsonl: {ts, cycle_id, template_id, phase_after, transitioned, escalation, blocker_reason, budget}

11. FIRE TRANSITION HOOKS (if any)
    - If new_phase in terminal states: fire on_close_success or on_close_failure
    - Hook execution order preserved per template
    - Hook failures: log to cycle-events.jsonl with action=hook_failed; continue (do NOT abort)

12. RETURN
    - JSON shape per cycle-runner SKILL.md "Response shape"
```

## Deferred invocation (`delegate_to_skill`)

Step 5 (INVOKE) above describes three nominal modes (SUBPROCESS / AGENT / INLINE). In practice, `bin/cycle_runner.py` is a pure-Python subprocess and **cannot spawn `Agent`-tool sub-agents itself** (the `Agent` tool is a Claude Code construct unavailable from a Python child process). For any phase whose `entry_skill` is a real atomic skill (not `__ceo_ask_user__`, `__no_op__`, or `__hook_only__`), the orchestrator therefore **returns BEFORE invoking** — emitting a structured "to-invoke" payload that the CEO loop translates into an `Agent` spawn.

This deferred-invocation pattern is part of the canonical protocol. Behaviorally:

1. After step 4 (RESOLVE ENTRY) successfully validates the entry_skill, instead of executing step 5 (INVOKE) inline, the orchestrator appends `{action: "delegate_skill", phase, entry_skill}` to `handoffs.jsonl` and returns the response below.
2. CEO spawns the named skill via `Agent` (subagent_type = `required_role` if set), captures its structured return JSON, then re-invokes `cycle_runner advance --cycle-id <id> --user-input <captured-json>`.
3. On the re-invoke, the orchestrator resumes at step 6 (WRITE OUTPUT TO INDEX), folding `user_input` into `index.<output_to_index_path>`, then proceeds normally through 7-12.

Response shape (terminal phase NOT yet reached, no transition has fired):

```json
{
  "status": "ok",
  "op": "advance",
  "cycle_id": "...",
  "phase_before": "<phase_id>",
  "phase_after": "<phase_id>",
  "transitioned": false,
  "delegate_to_skill": {
    "kind": "skill_invocation_required",
    "phase": "<phase_id>",
    "entry_skill": "<sk-id or agent:op>",
    "rendered_args": "<TOML/JSON args block>",
    "core_ability": "<verb>",
    "required_role": "<agent_id|null>"
  },
  "blocker_reason": null,
  "budget": { "iters_used": ..., "iters_max": ..., ... },
  "next_action": "CEO spawns the skill; re-invoke advance with --user-input carrying skill output"
}
```

**`hooks_fired` is OMITTED from this response** — no transition has occurred yet, so no transition hooks have fired. CEO consumers MUST treat `hooks_fired` as optional and only process it when present (terminal-transition responses on success/failure paths). The same rule applies to `escalate_to_user` responses returned at step 4.

Implementation reference: `bin/cycle_runner.py` lines ~770-796 emit this payload; the inline comment there is the authoritative rationale.

## Error taxonomy

```
status: ok       → advance succeeded; phase_after may equal phase_before (still in phase)
status: blocked  → cycle is blocked; CEO must cancel or address the blocker
status: noop     → cycle is in terminal/paused/cancelled state; no work done
status: error    → orchestrator-level failure (missing files, malformed template, etc.); return early
```

`blocker_reason` enumeration:
- `budget_iters_exhausted`
- `budget_wall_clock_exhausted`
- `budget_pages_exhausted`
- `phase_id_unknown`
- `entry_skill_unknown`
- `ability_skill_mismatch`
- `entry_skill_timeout`
- `entry_skill_crashed:<code>`
- `output_parse_failed`
- `output_schema_violation`
- `success_condition_invalid`
- `phase_<id>_could_not_satisfy`
- `template_not_found_at_pinned_version`

## Concurrency / locking

`index.toml` writes are serialized via OS-level file locking (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows). Cycle-runner acquires an exclusive lock on the cycle directory's `.lock` file before reading; releases after writing.

Concurrent `advance` invocations on the same cycle_id are rejected with `status: error, reason: cycle_locked`.

Concurrent `advance` invocations on DIFFERENT cycles are fine; orchestrator is reentrant (no shared mutable state across cycles).

## Template caching

Templates are loaded fresh at every `advance` (TOML parse is fast; ~1ms per file). No in-memory cache to avoid stale-template bugs across long sessions.

If template caching becomes a perf concern (cycle count > 50 per turn), revisit with a per-process cache keyed by `(template_id, version, mtime)`.

## Restricted DSL evaluator

Implementation in `bin/cycle_runner.py` is a small AST walker that:

1. Parses `success_condition` via Python's `ast.parse(expr, mode='eval')`
2. Walks the AST; rejects any node not in the allow list:
   - `ast.Expression`, `ast.BoolOp` (and/or), `ast.UnaryOp` (not), `ast.Compare`, `ast.Constant`, `ast.Name`, `ast.Attribute`, `ast.Subscript`, `ast.Call` (only for built-ins `len/is_null/is_set`)
3. For allowed `Name`/`Attribute` chains, dereferences against `{index, params}` dict; raises on unknown paths
4. For allowed `Call`, only `len(...)`, `is_null(<expr>)`, `is_set(<expr>)` accepted
5. Returns a Python bool

This is intentionally not Python `eval()` — Turing-completeness is forbidden by design.

## Hook execution sub-protocol

Each hook string is parsed into `{verb, kwargs}`:

```
"memory-write type=lesson agent_id=ceo-01 importance=8 content='...'"
   → verb = "memory-write"
   → kwargs = {type: "lesson", agent_id: "ceo-01", importance: 8, content: "..."}
```

Template interpolation happens before parsing: `{cycle_id}`, `{meta.X}`, `{index.X.Y}`, `{params.X}` are substituted with values from current state.

After parsing, the verb dispatches to its handler:
- `memory-write` → invoke `skills/memory/memory-write/` via subprocess or inline
- `kb-add` → invoke kb-manager op=add via subprocess
- `memo-send` → invoke `skills/core/communication/memo-send/`
- `incident-open` → invoke `skills/core/ops/incident-open/`
- `standup-log` → invoke `skills/core/ceremony/standup-log/`
- `okr-checkin` (v6.2+) → invoke `skills/core/okr/okr-checkin/` with auto-derived score delta. Resolution: read the current cycle's `aligns_to_okr` field in `index.toml`; if present, read `handoffs.jsonl` for phase-owner success count + cycle outcome; pipe through `bin/okr_derive_score.py --cycle-id <id>` to compute conservative per-KR score increments; pass the derived deltas to `okr-checkin`. If `aligns_to_okr` is absent, the hook becomes a no-op with `action: okr_link_unresolved` logged. Gated on `[okr] auto_checkin_from_cycle = true` in config (default: true). Conservative formula avoids over-crediting (each cycle-close success increments aligned KR by `0.05 × weight/100`, capped at 1.0); readers interpret the score via `bin/okr_derive_score.py` docstring.

Hook failures (non-zero exit, exception, timeout):
1. Append to cycle-events.jsonl: `{action: "hook_failed", verb, kwargs, error}`
2. Continue with next hook (do NOT abort cycle transition)
3. On 3+ consecutive hook failures within a cycle, escalate via memo to ceo-01

## Replay protocol (`bin/cycle_replay.py`)

`replay --cycle-id <id>` reads `handoffs.jsonl` + `index.toml` + `cycle-events.jsonl` and renders:

```
Cycle: ta-2026-04-19-crypto-trader
Template: talent-acquisition v1.0.0
Opened: 2026-04-19T10:00:00Z by user
Status: in_progress @ phase research-deep (iter 7/30)

Timeline:
  [0:00] opened (params: domain=crypto-trading, tier=careful-hire)
  [0:01] discovery phase entered
  [0:03] discovery → decision (candidates=3)
  [0:08] decision → user-confirm (recommended=ccxt)
  [0:08] escalate_to_user
  [0:15] user_input received: confirm
  [0:15] user-confirm → research-deep
  [0:18] research-deep iter 1 (4 pages)
  ...
  [1:14] research-deep iter 7 (3 pages, novelty_remaining=3)

Hooks fired: 4 (1 on_open, 3 on_phase_transition)
Hook failures: 0
Budget: 7/30 iters, 23/50 pages, 14/60 wall-clock-min
```

Useful for debugging stuck cycles or auditing past lifecycles.

## Validation protocol (`op=validate-template`)

Independent code path that parses a template TOML and runs the 12 validation invariants from `template-dsl.md` §"Validation invariants". Returns:

```json
{
  "status": "valid | invalid",
  "template_id": "...",
  "version": "...",
  "errors": [
    {"rule": "ability_mapping", "phase_id": "decision", "detail": "entry_skill 'committee' not registered under 'research'"}
  ],
  "warnings": [
    {"rule": "extra_param", "name": "max_pages_override"}
  ]
}
```

Authors run this before submitting a template for committee review.

## Performance characteristics

- `op=open`: < 50ms (TOML parse + index init + on_open hooks)
- `op=advance` minus skill invocation: < 100ms (load + DSL eval + writes)
- Total `advance` time dominated by entry_skill execution
- `op=status`: < 10ms (read-only)
- `op=replay`: < 500ms for cycles with < 100 handoff rows

If `advance` non-skill overhead exceeds 200ms, profile and revisit. The orchestrator is supposed to be transparent overhead; the work happens in atomic skills.

## Telemetry contract

Every `advance` MUST append exactly one row to `_meta-runtime/cycle-events.jsonl`:

```json
{
  "ts": "2026-04-19T10:14:23Z",
  "cycle_id": "ta-2026-04-19-crypto-trader",
  "template_id": "talent-acquisition",
  "template_version": "1.0.0",
  "op": "advance",
  "phase_before": "discovery",
  "phase_after": "decision",
  "transitioned": true,
  "iter_in_phase": 1,
  "blocker_reason": null,
  "escalation": null,
  "budget": {"iters_used": 8, "iters_max": 30, ...},
  "duration_ms": 142
}
```

`bin/kiho_telemetry_rollup.py` (Wave 1.3) is extended in v5.21 to read this stream alongside `skill-invocations.jsonl`, producing per-template health stats.

## Backwards compatibility

`bin/cycle_runner.py` MUST refuse to operate on a cycle whose `index.meta.template_version` is greater than the latest version of the named template on disk. If this happens (e.g., user rolled back the template), CEO sees a clear error and chooses cancel-or-pin.

`bin/cycle_runner.py` MAY operate on a cycle whose pinned version is OLDER than the latest, by loading the historical version from git history (or by keeping versioned template copies under `references/cycle-templates/.history/`). Implementation deferred to v5.22 — for v5.21 we assume no template removals during a cycle's lifetime.
