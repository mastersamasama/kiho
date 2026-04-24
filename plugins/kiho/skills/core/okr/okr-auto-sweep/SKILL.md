---
name: okr-auto-sweep
description: Deterministic OKR auto-sweep invoked from CEO INITIALIZE step 17.5 and the `okr-period.toml` cycle template's sweep/period-execute phases. Reads `<project>/.kiho/state/okrs/` via `bin/okr_scanner.py`, classifies state against the current date and `[okr]` config, and emits a structured JSON action list for the CEO / OKR-master to dispatch. Never mutates OKR state — this is the read-only half of the auto-flow. Emits one of six action kinds: propose-company, cascade-dept, cascade-individual, stale-memo, period-close, cascade-close. Use this skill when the CEO needs to know "what OKR auto-actions are pending" or when `kiho-okr-master` is invoked with `OPERATION: sweep`. Turn-boundary default; consume_subset allows filtering when a specific phase only cares about a subset of actions.
argument-hint: "period=<YYYY-QN> [today=<YYYY-MM-DD>] [consume_subset=[...]]"
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: active
  kiho:
    capability: evaluate
    topic_tags: [governance, planning, lifecycle]
    data_classes: ["okrs-period-md"]
    storage_fit:
      reads:
        - "<project>/.kiho/state/okrs/**"
        - "<project>/.kiho/config.toml"
        - "${CLAUDE_PLUGIN_ROOT}/templates/config.default.toml"
      writes: []
---
# okr-auto-sweep

Read-only OKR state inspector. Runs deterministically — same inputs produce same actions. Reserves all mutation decisions to the dispatcher (CEO, OKR-master, or the cycle-runner hook consumer).

## When to use

- CEO INITIALIZE step 17.5 — every /kiho turn, CEO invokes this via `bin/okr_scanner.py` to populate the turn's auto-action agenda.
- `okr-period.toml` phase `sweep` — once per OKR-period cycle open.
- `okr-period.toml` phase `period-execute` — each turn while the period is active; consume_subset filters to stale-memo + period-close only.
- `kiho-okr-master` with `OPERATION: sweep` — any sub-agent needing to check OKR state.

Do NOT invoke:

- From agent.md writes (wrong surface — recruit chain).
- From KB writes (wrong surface — kb-manager chain).
- As a user-facing /kiho command (use `/kiho show my okrs` which routes through okr-master reading the scanner output).

## Inputs

```
PAYLOAD:
  op:                sweep   (only supported operation)
  period:            <YYYY-QN or YYYY-HN or custom slug>   # required
  today:             <YYYY-MM-DD>                           # optional; defaults to system date
  consume_subset:    ["propose-company", ...]               # optional; filter actions by kind
  project_root:      <path>                                 # optional; defaults to cwd
```

## Procedure

### 1. Resolve scanner invocation

Construct the Bash command:

```bash
python ${CLAUDE_PLUGIN_ROOT}/bin/okr_scanner.py \
    --project <project_root> \
    [--today <today>] \
    --json
```

Capture stdout JSON. Exit code 2 or 3 → return status=error with the scanner's stderr.

### 2. Parse + filter

Scanner emits `{"today": "YYYY-MM-DD", "actions": [{kind, payload, reason}, ...]}`. If `consume_subset` is provided, filter `actions[]` to `kind ∈ consume_subset` only.

### 3. Tier per-kind priority

Order actions by priority so the dispatcher gets high-urgency items first:

| Priority | Kind | Why |
|---|---|---|
| 1 | `period-close` | Period boundary already crossed — closing is overdue |
| 2 | `cascade-close` | Parent already closed — children are orphaned |
| 3 | `propose-company` | Period active with no direction set |
| 4 | `stale-memo` | Drift signal — owner may have forgotten |
| 5 | `cascade-dept` | Structural gap under a set company O |
| 6 | `cascade-individual` | Populating the leaf layer under set dept Os |

### 4. Return structured receipt

```markdown
## Receipt <REQUEST_ID>
OPERATION: okr-auto-sweep
STATUS: ok | error
SCANNER_TODAY: <YYYY-MM-DD>
ACTIONS_COUNT: <n>
ACTIONS:
  - priority: 1
    kind: <kind>
    payload: {...}
    reason: <scanner reason>
  - ...
```

The dispatcher (CEO / OKR-master / cycle-runner) iterates ACTIONS in order and takes the appropriate next action per each. This skill does NOT dispatch — that's the consumer's job.

### 5. Ledger trail

Log a single entry per sweep invocation:

```
{"ts": "<iso>", "action": "okr_sweep_complete",
 "payload": {"period": "<period>", "scanner_today": "<today>",
             "actions_count": <n>, "kinds": [...]}}
```

If zero actions, still log `okr_sweep_clean` to prove the sweep ran (avoids the silent-skip drift that v5.22 INITIALIZE step 7/14 audit was built to catch).

## Response shape

```
## Receipt <REQUEST_ID>
OPERATION: okr-auto-sweep
STATUS: ok | error
SCANNER_TODAY: <YYYY-MM-DD>
ACTIONS_COUNT: <n>
ACTIONS: [...]
LEDGER_REF: jsonl://state/ceo-ledger.jsonl#seq=<n>
NOTES: <optional>
```

## Invariants

- **Read-only.** Never writes to `<project>/.kiho/state/okrs/` or any OKR file. Ledger write is allowed (it's not OKR state).
- **Deterministic.** Given same filesystem state + same `today`, returns identical actions. The scanner enforces this (no randomness, no ordering dependence on file mtimes beyond what the spec requires).
- **No silent skip.** Even zero actions produces a ledger entry (`okr_sweep_clean`). Skipping without a ledger trail is drift.
- **Config-respected.** `[okr] auto_trigger_enabled = false` in config makes the scanner return zero actions — but the ledger entry still fires, with `reason: master_switch_off`. This preserves auditability of opt-out.
- **No dispatch.** The scanner's output is a proposal. Converting proposal to action is the consumer's responsibility. This skill does not spawn sub-agents, does not send memos, does not call okr-set/checkin/close.

## Non-Goals

- **Not a dispatcher.** See Invariants.
- **Not a decision-maker.** The scanner identifies "what state needs attention"; OKR-master or CEO decides what to do about it.
- **Not a history viewer.** For "what happened" queries, read `state/ceo-ledger.jsonl` or the dashboard.
- **Not a cross-period analyzer.** Focuses on the current period plus any active-but-overdue prior period. Long-horizon analysis belongs to retrospective.

## Anti-patterns

- Running this skill multiple times per /kiho turn. Once per turn at INITIALIZE is sufficient; each run produces a new ledger entry. Spam generates audit noise.
- Consuming the full action list when only a subset matters (e.g., cycle-runner hook needing only stale-memo). Use `consume_subset` — filtering at emit is cheaper than filtering at consumer.
- Ignoring the priority ordering. If the dispatcher acts on `cascade-individual` before `period-close`, it'll dispatch drafting work for a period that's already over.

## Grounding

- `bin/okr_scanner.py` — the deterministic scanner this skill wraps.
- `agents/kiho-okr-master.md` — the primary consumer.
- `agents/kiho-ceo.md` INITIALIZE step 17.5 — the primary invocation point.
- `references/cycle-templates/okr-period.toml` — phase-level invocation points.
- `references/okr-guide.md` — user-facing explanation of what the sweep does in practice.
- `skills/core/okr/okr-set/` + `okr-checkin/` + `okr-close/` — the atomic primitives this skill does NOT call (the dispatcher calls them).
