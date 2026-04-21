---
name: kiho
description: Use this skill whenever the user invokes /kiho or asks kiho to do anything. Single entry point that parses mode flags, loads the CEO persona, spawns departments, runs the Ralph autonomous loop, delegates tasks, coordinates committees, integrates decisions into the KB, and evolves skills over time. Dispatches across all modes — /kiho feature, /kiho --bugfix, /kiho --refactor, /kiho --vibe, /kiho --debate, /kiho --resume, /kiho kb-init, /kiho evolve — plus implicit mode detection when the user passes a PRD file path or a plain description. Also triggers when the user says "kiho" or "have kiho" followed by any task (e.g., "have kiho build the auth flow"). If the user asks for multi-agent orchestration, cross-team planning, PRD ingestion, committee debate, agent recruitment, knowledge-base bootstrap, or skill evolution, invoke this skill.
argument-hint: "<mode-or-description-or-prd-path>"
metadata:
  trust-tier: T3
  version: 2.1.0
  lifecycle: active
  kiho:
    capability: orchestrate
    topic_tags: [orchestration]
    data_classes: ["kiho-config", "ceo-ledger", "continuity", "plan"]
---
# kiho

Single entry point for kiho. Loads the CEO persona, parses mode, runs the Ralph loop until the work is finished or a user answer is required. Do not perform the requested work inline — route everything through the CEO.

## When to use

Invoke this skill when any of the following is true:

- The user types `/kiho <anything>` — with or without mode flags
- The user says "kiho …" or "have kiho …" in plain text
- The user passes a PRD file path expecting kiho to ingest it
- The user asks for multi-agent orchestration, cross-team planning, committee debate, agent recruitment, KB bootstrap, or skill evolution

Do NOT invoke this skill when:

- A spawned sub-agent returns structured output — that routes back to the CEO, not through this skill
- The user asks a single-file edit question unrelated to orchestration — answer directly

## Non-Goals

kiho the entry-point skill is defined as much by what it refuses to do as by what it does.

- **Not an inline worker.** This skill never executes the requested task itself — it parses a mode, loads the CEO, and delegates. Attempting to do the work inline bypasses committees, RACI, and KB updates.
- **Not a sub-agent entry point.** Only the main conversation invokes `/kiho`. Spawned sub-agents must return structured output to the CEO, never re-invoke this skill.
- **Not a multi-entry harness.** `/kiho` is the sole public surface. Mode-specific slash commands (`/kiho-feature`, `/kiho-bugfix`) are explicitly rejected (see [A2](#a2--multiple-top-level-slash-commands-per-mode)).
- **Not a zero-interaction system.** The CEO pauses and calls `AskUserQuestion` when uncertain. The Ralph loop runs until it needs a human, not until every possible path is exhausted.
- **Not a standalone research tool.** Research is one of many delegated operations — the CEO calls the `research` skill via cascade. Direct web fetches from this skill are prohibited.
- **Not a session manager.** Resumption across sessions happens via `/kiho --resume <spec-name>` reading `.kiho/state/` — there is no in-memory session store.

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals. Lowercase "must", "should", "do not" remain informal prose.

## Overview

`/kiho` activates a main-conversation CEO agent that orchestrates departments (PM, Engineering, HR, plus others recruited on demand), runs committees for non-trivial decisions, maintains a project + company knowledge base, and evolves skills over time. The CEO is the only agent authorized to call `AskUserQuestion`. All sub-agents return structured outputs to the CEO.

## Agent assignments by mode

Each mode recruits a canonical delegation shape. Depth cap 3 (CEO → Dept → Team/IC) and fanout cap 5 apply to every row.

| Mode | Primary delegation | Supporting | Recruited on demand |
|---|---|---|---|
| feature / feature-from-prd | CEO → PM → Engineering | kb-manager (INTEGRATE) | design-agent (researchable gap), committee (non-trivial decisions) |
| bugfix | CEO → Engineering | kb-manager | — |
| refactor | CEO → Engineering | kb-manager | — |
| vibe | CEO → IC | — | — |
| debate | CEO → committee | kb-manager (INTEGRATE) | — |
| evolve | CEO → kb-manager | — | design-agent, skill-derive |
| kb-init | CEO → kb-manager | Engineering (code-base scan) | — |
| resume | (reloads prior delegation from `.kiho/state/<spec>/`) | kb-manager | — |

## Startup sequence

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/core/harness/kiho/config.toml` (migrated from YAML in v5.19.3).
   - If `company_root` is empty, invoke the `kiho-setup` skill first.
   - Otherwise export `$COMPANY_ROOT` from the value.
2. Read `${CLAUDE_PLUGIN_ROOT}/agents/kiho-ceo.md`. From this point the main agent follows its instructions verbatim.
3. Parse `$ARGUMENTS` into `(mode, payload)` — see [Mode parsing](#mode-parsing).
4. Run the CEO's Ralph loop — see `agents/kiho-ceo.md`.

> `$CLAUDE_PLUGIN_ROOT` is set by Claude Code to the plugin install path (e.g., `C:\Users\wky\.claude\kiho-plugin`). `$COMPANY_ROOT` is sourced from `config.toml` and is first populated by `kiho-setup` on a fresh install.

The main agent **MUST NOT** skip step 2. Loading `kiho-ceo.md` is what switches the main conversation into CEO persona; without it, the loop runs without role discipline.

## Mode parsing

| Input | Mode | Payload |
|---|---|---|
| `--bugfix <text>` | bugfix | text |
| `--refactor <text>` | refactor | text |
| `--vibe <text>` | vibe | text |
| `--debate <topic>` | debate | topic |
| `--resume <name>` | resume | spec name |
| `feature <text>` | feature | text |
| `kb-init` or `kb-init <path>` | kb-init | optional PRD path |
| `evolve` or `evolve <skill>` | evolve | optional skill name; accepts `--audit=<lens>` to run a deterministic read-only audit instead of the normal evolution loop (lens values: `storage-fit` — verifies `metadata.kiho.data_classes:` against `references/data-storage-matrix.md`; see `skills/_meta/evolution-scan/references/storage-audit-lens.md`) |
| Path to an existing file | feature-from-prd | absolute path |
| Anything else | unclassified | raw string |

For `unclassified`, the CEO reads `.kiho/state/plan.md` (if present) + last 10 session-context entries, then classifies internally. If still unclear, the CEO calls `AskUserQuestion`.

## Failure playbook

**Severity:** error (blocks `/kiho` turn from completing).
**Impact:** prevents the CEO from running the Ralph loop — user cannot use kiho until resolved.
**Taxonomy:** config | transient | resource | protocol.

Failures during startup or the Ralph loop MUST route through the decision tree below rather than raising raw errors to the user.

### Decision tree

```
startup / loop failure
    │
    ├─ config.toml missing                      → Route A (invoke kiho-setup)
    ├─ config.toml present, company_root empty  → Route A (populate company_root)
    ├─ agents/kiho-ceo.md missing               → Route B (abort, user reinstalls plugin)
    ├─ $ARGUMENTS empty                         → Route C (AskUserQuestion — mode or description)
    ├─ mode=unclassified AND plan.md empty      → Route C (cannot infer intent)
    ├─ max_ralph_iterations exceeded            → Route D (partial summary, end turn, wait for --resume)
    ├─ stuck_timeout_min elapsed no progress    → Route D (emit ASK_USER, end turn)
    └─ sub-agent returned malformed output      → Route E (log, retry once, escalate)
```

### Route A — config or company_root missing

1. Log `startup_failure: config.toml` or `company_root_empty` to `.kiho/state/ceo-ledger.jsonl`.
2. Invoke the `kiho-setup` skill (it handles file creation + company_root prompt).
3. Retry step 1 of Startup sequence.

### Route B — CEO persona missing

1. Abort with `status: ceo_persona_missing`.
2. Return an error pointing to `agents/kiho-ceo.md`.
3. User reinstalls the plugin; there is no automated recovery.

### Route C — ambiguous invocation

1. CEO calls `AskUserQuestion` with options: pick a mode or supply a description.
2. End the turn after the question is posed.
3. Next `/kiho` invocation with the user's answer dispatches normally.

### Route D — loop budget exceeded

1. Write current plan state + iteration count + last completed step to `.kiho/state/<spec-name>/partial.md`.
2. Emit structured summary with `status: max_iterations` or `status: user_question`.
3. End turn.
4. User resumes via `/kiho --resume <spec-name>`.

### Route E — sub-agent protocol violation

1. Log the malformed response (full body) to `.kiho/state/ceo-ledger.jsonl`.
2. Retry the sub-agent call **once** with a prompt-level reminder of the expected schema.
3. On second failure, escalate via `AskUserQuestion` with the sub-agent name and the last two responses attached.

Routes A-E are the only exits from failure. Silent retry is **MUST NOT** behavior — every retry is recorded in the CEO ledger.

## Worked examples

### Example 1 — implicit feature mode from a plain description

Invocation:
```
/kiho build a dark-mode toggle for the settings page
```

Expected routing (CEO's internal classification):
```json
{
  "mode": "feature",
  "payload": "build a dark-mode toggle for the settings page",
  "next_action": "load CEO persona, create spec, delegate to Engineering"
}
```

### Example 2 — PRD file path

Invocation:
```
/kiho C:/projects/acme/PRDs/onboarding-v2.md
```

Expected routing:
```json
{
  "mode": "feature-from-prd",
  "payload": "C:/projects/acme/PRDs/onboarding-v2.md",
  "next_action": "read PRD, classify subsystems, spawn PM then Engineering cascade"
}
```

### Example 3 — vibe mode skips spec creation

Invocation:
```
/kiho --vibe fix typo in README
```

Expected routing:
```json
{
  "mode": "vibe",
  "payload": "fix typo in README",
  "next_action": "skip spec, delegate directly to an IC"
}
```

### Example 4 — resume a paused spec

Invocation:
```
/kiho --resume dark-mode-toggle
```

Expected routing:
```json
{
  "mode": "resume",
  "payload": "dark-mode-toggle",
  "next_action": "read .kiho/state/dark-mode-toggle/partial.md, rehydrate Ralph loop state, continue from last checkpoint"
}
```

## Response shape

When a `/kiho` turn ends, the main agent returns a structured summary. IDE extensions, `/kiho --resume`, and downstream tooling consume this shape to know what changed and what remains.

```json
{
  "status": "complete | user_question | max_iterations | error",
  "mode": "feature | bugfix | refactor | vibe | debate | resume | kb-init | evolve | feature-from-prd | unclassified",
  "spec_name": "<slug or null>",
  "iterations_run": 7,
  "plan_summary": "3 tasks done, 1 pending user decision",
  "kb_updates": 2,
  "agents_spawned": ["pm", "engineering", "kb-manager"],
  "committees_convened": 0,
  "escalations": [{"type": "user_question", "prompt": "..."}],
  "next_action": "User reviews KB changes; re-invoke /kiho --resume <spec-name> to continue"
}
```

The `status` field drives downstream behavior:

- `complete` — plan empty, completion criteria met. No follow-up needed.
- `user_question` — `AskUserQuestion` was called mid-loop. Turn ended after the question was posed; user's next message resumes the loop.
- `max_iterations` — Ralph loop hit `max_ralph_iterations`. Partial summary in `.kiho/state/`; resume via `/kiho --resume <spec-name>`.
- `error` — unrecoverable failure. Route via the failure playbook above.

## Loop discipline

The CEO runs inside a single main-agent turn. It **MUST NOT** stop until one of:

- The `plan.md` Pending list is empty AND `completion.md` criteria are met
- A user answer is required (CEO calls `AskUserQuestion`)
- `max_ralph_iterations` from `config.toml` is exceeded

Each Ralph iteration includes a mid-loop `INTEGRATE` step that calls `kb-add` via `kiho-kb-manager` when decisions are made with confidence ≥ 0.90. The KB stays current throughout the session.

## Invariants

- **MUST** delegate every request; **MUST NOT** do the work inline. Vibe mode still routes through the CEO — the CEO skips spec creation and delegates directly to an IC.
- **MUST** route KB writes through `kiho-kb-manager` via the `kb-add` / `kb-update` / `kb-delete` sub-skills. **MUST NOT** write to `.kiho/kb/wiki/` directly.
- **MUST** respect depth cap 3 (CEO → Dept → Team/IC) and fanout cap 5. **MUST NOT** spawn deeper or wider.
- **MUST** use the research cascade (KB → web → deepwiki → clone → ask user) via the `research` skill. **MUST NOT** bypass to raw WebFetch.
- **MUST** end the turn with a structured summary (see [Response shape](#response-shape)) when the loop exits.

## Anti-patterns

- **MUST NOT invoke `/kiho` from a sub-agent.** Sub-agents return structured output to the CEO; re-invoking `/kiho` from inside a sub-agent creates a loop and bypasses the depth cap. All escalations route back to the main-conversation CEO via `escalate_to_user` bubble-up.
- **MUST NOT bypass the research cascade with raw WebFetch.** The `research` skill is the only authorized external-fetch path (KB → web → deepwiki → clone → ask-user). Direct WebFetch here or from agents corrupts KB consistency and skips trusted-source registry promotion.
- **MUST NOT create new entry-point slash commands** (`/kiho-feature`, `/kiho-bugfix`, …). Single entry point is a budget constraint (skill-create Gate 15: Claude Code's 1%/8k-char cap would exceed at 8+ top-level commands) and a UX constraint (one command to remember). Mode flags are the extension mechanism.
- **MUST NOT use vibe mode for complex features.** Vibe skips spec creation and committee review. Reserve it for single-file tasks < 1 hour (typo fixes, small edits). Use feature mode for anything requiring design.
- Do not write directly to `.kiho/kb/wiki/`. Every KB write goes through `kiho-kb-manager` via `kb-add` / `kb-update` / `kb-delete` sub-skills (see Invariants).

## Rejected alternatives

### A1 — Inline execution instead of delegation

**What it would look like.** `/kiho` directly runs the requested task in the main conversation without loading the CEO persona or spawning sub-agents.

**Rejected because.** Collapses the whole multi-agent harness into a single-agent loop. Loses RACI, committee debate, KB updates, and persona separation. Every kiho value proposition (soul, capability matrix, self-improvement) assumes delegation. Defeats the plugin's purpose.

**Source.** CLAUDE.md Invariants §"Delegate every request"; v4 CEO persona design.

### A2 — Multiple top-level slash commands per mode

**What it would look like.** `/kiho-feature`, `/kiho-bugfix`, `/kiho-vibe`, etc. — one command per mode instead of a single `/kiho` with flags.

**Rejected because.** Expanded discovery surface: users must remember 8+ commands. Claude Code's 1%/8k-char skill budget pays the description cost 8 times. The v5.14 `budget_preflight.py` (Gate 15) would flag this as budget-exceeded within two additions. (This budget applies across every skill in the plugin. See `skill-create/SKILL.md` Gate 15 for the per-skill 1,536-char cap and aggregate ceiling.) CLAUDE.md invariant "Single entry point" is explicit.

**Source.** CLAUDE.md §"Invariants" — "`/kiho` is the only skill users should need to remember"; Claude Code skills docs §"description budget".

### A3 — Automatic mode detection with no CLI flags

**What it would look like.** Always parse raw text and guess the mode via heuristics or a classifier call.

**Rejected because.** Ambiguous inputs ("fix the auth bug" — bugfix or vibe?) lose deterministic control. Users need a way to force a mode when the classifier guesses wrong. The current design uses flags as the deterministic path and falls back to classification only for `unclassified` input — a superset of "always classify" that preserves user agency.

**Source.** Mode parsing table design; kiho-ceo.md INITIALIZE step 3.

### A4 — Running the CEO loop in a sub-agent instead of the main conversation

**What it would look like.** `/kiho` spawns a sub-agent that carries the CEO persona and runs the Ralph loop there; the main conversation only proxies.

**Rejected because.** Only the main conversation can call `AskUserQuestion`. Putting the CEO in a sub-agent means every user question needs a bubble-up protocol, doubling latency and adding a failure mode (malformed escalations). The main-conversation CEO is a direct consequence of Claude Code's tool-scoping rules.

**Source.** Claude Code docs §"AskUserQuestion is main-conversation-only"; CLAUDE.md §"CEO-only user interaction".

## Future possibilities

Non-binding sketches per RFC 2561. Nothing in this section is a commitment; triggers, scope, and timelines may all change.

### F1 — Streaming CEO progress updates

**Trigger condition.** Median `/kiho feature` turn duration exceeds 10 minutes across a sliding 30-turn window (measured via `session-context` telemetry).

**Sketch.** Emit streaming status updates from CEO at phase transitions (plan drafted, committee convened, agent spawned, integration complete). Users see progress without the turn returning. Requires Claude Code streaming API support for skills.

### F2 — Cross-session resumption beyond `--resume <spec>`

**Trigger condition.** ≥ 3 user reports of "/kiho lost my context after I closed the session".

**Sketch.** Persist CEO working memory to `.kiho/state/ceo-resume/<turn-id>.json` at every INTEGRATE checkpoint. `/kiho --continue` rehydrates the most recent turn regardless of whether a spec was active. Current `--resume` only handles named specs.

### F3 — First-class mode discovery via `/kiho --list-modes`

**Trigger condition.** New user reports "I didn't know mode X existed" OR the mode table grows past 12 entries.

**Sketch.** `/kiho --list-modes` returns a structured list with each mode's purpose, arguments, and a one-line worked example. Replaces the current mode table in this SKILL.md body with a runtime-queryable surface.

## Grounding

- **Single-entry CLI pattern.**
  > **Kubernetes kubectl Command structure:** *"kubectl uses the syntax `kubectl [command] [TYPE] [NAME] [flags]`... Commands describe the operation you want to perform."*
  One binary, many subcommands. Validated at multi-million-skill scale. https://kubernetes.io/docs/reference/kubectl/

- **Ralph-style autonomous loop.**
  > **Geoffrey Litt, "Ralph: an AI-first autonomous loop for LLM agents" (2025):** *"iterate until done, user-blocked, or budget-exhausted."*
  The CEO's loop discipline follows this verbatim. https://geoffreylitt.com/ralph

- **CEO-only user interaction.**
  > **Claude Code docs §AskUserQuestion scoping:** *"AskUserQuestion is only available in the main conversation; sub-agents cannot invoke it."*
  kiho's CEO-only invariant is a direct consequence of tool-scoping, not a style choice.

- **Delegate-over-inline pattern.**
  > **Anthropic Engineering, "Harness design for long-running application development" (Mar 24 2026) §Generator/evaluator separation:** *"When we asked agents to evaluate work they had produced, they tend to respond by confidently praising the work … Tuning a standalone evaluator to be skeptical turns out to be far more tractable."*
  kiho delegates every request; the CEO never does the work inline. https://www.anthropic.com/engineering/harness-design-long-running-apps

- **Depth cap 3 + fanout cap 5.**
  Empirical ceilings on Claude Code sub-agent usefulness — deeper stacks lose coherence, wider fanouts exceed attention budget. Grounded in kiho v4 design + Claude Code `--max-subagents` documentation.
