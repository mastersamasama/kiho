---
name: kiho
description: Single entry point for kiho's multi-agent orchestration harness. Trigger this whenever the user types /kiho (with or without flags — /kiho feature, --bugfix, --refactor, --vibe, --debate, --resume, kb-init, evolve), says "kiho …" or "have kiho …" in natural language, or passes a PRD file path expecting it to be ingested. Also trigger when the user asks for multi-agent orchestration, cross-team planning, committee debate, agent recruitment, knowledge-base bootstrap, or skill evolution — even without saying "kiho" explicitly. The skill loads a CEO persona in the main conversation, parses the mode, and runs a Ralph-style autonomous loop that delegates to departments, committees, and vendored skills until the plan is empty, the iteration budget is exhausted, or a user answer is required.
argument-hint: "<mode-or-description-or-prd-path>"
metadata:
  trust-tier: T3
  version: 2.2.0
  lifecycle: active
  kiho:
    capability: orchestrate
    topic_tags: [orchestration]
    data_classes: ["kiho-config", "ceo-ledger", "continuity", "plan"]
---

# kiho — single entry

`/kiho` activates a **main-conversation CEO agent** that orchestrates departments (PM, Engineering, HR, plus others recruited on demand), runs committees for non-trivial decisions, maintains a project + company knowledge base, and evolves skills over time. The CEO is the only agent authorized to call `AskUserQuestion`; every sub-agent returns structured output and the CEO decides when to escalate.

This skill does not do the requested work itself. It loads the persona, parses the mode, and hands off to the CEO's Ralph loop. If you are tempted to skip that handoff and "just answer," read `references/rejected-alternatives.md` §A1 first.

## When to invoke

Invoke when any of the following holds:

- User types `/kiho <anything>` — with or without mode flags
- User says "kiho …" or "have kiho …" in plain text
- User passes a PRD file path expecting kiho to ingest it
- User asks for multi-agent orchestration, cross-team planning, committee debate, agent recruitment, KB bootstrap, or skill evolution

Do **not** invoke when:

- A spawned sub-agent returns structured output — that routes back to the CEO, not through this skill again
- The user asks an unrelated single-file question — answer directly without loading the harness

## Non-goals

These define the skill by what it refuses to do:

- **Not an inline worker.** This skill never executes the requested task itself. Doing so would bypass committees, RACI, and KB updates — every kiho value proposition assumes delegation.
- **Not a sub-agent entry point.** Only the main conversation invokes `/kiho`. A sub-agent that re-invokes this skill creates a loop and breaks the depth cap.
- **Not a multi-entry harness.** `/kiho` is the sole public surface. Mode-specific commands (`/kiho-feature`, `/kiho-bugfix`) are explicitly rejected (see `references/rejected-alternatives.md` §A2).
- **Not a zero-interaction system.** The CEO pauses and calls `AskUserQuestion` when uncertain. The Ralph loop runs until it needs a human, not until every possible path is exhausted.
- **Not a standalone research tool.** Research is a delegated operation routed through the `research` skill's cascade (KB → web → deepwiki → clone → ask-user). Direct web fetches from this skill are prohibited.
- **Not a session manager.** Cross-session resumption happens via `/kiho --resume <spec-name>` reading `.kiho/state/` — there is no in-memory session store.

## Startup sequence (hot path)

Run these four steps in order before any delegation. Each step carries its reason so you can judge edge cases instead of following blindly.

1. **Read `${CLAUDE_PLUGIN_ROOT}/skills/core/harness/kiho/config.toml`.** This file holds thresholds (iteration caps, committee budgets), company_root, and migration flags. If `company_root` is empty, invoke the `kiho-setup` skill first and restart this sequence — kiho cannot operate without a company root. Otherwise export `$COMPANY_ROOT` from the value.
2. **Read `${CLAUDE_PLUGIN_ROOT}/agents/kiho-ceo.md`.** This is the step that switches the main agent into CEO persona, including its pre-loaded skill portfolio and the Ralph loop definition. **Skipping this step is the single most load-bearing MUST NOT in this file** — without the CEO loaded, the loop runs without role discipline, no one owns `AskUserQuestion`, and delegation targets are unresolved.
3. **Parse `$ARGUMENTS` into `(mode, payload)`.** Use the table in [Mode parsing](#mode-parsing). The parser is deterministic — flag-prefixed inputs bind to a mode directly; bare text becomes `unclassified` and the CEO classifies it internally using `.kiho/state/plan.md` + recent session context.
4. **Run the CEO's Ralph loop.** The loop body, escalation table, and 18-step INITIALIZE live in `agents/kiho-ceo.md`. Exit conditions are in [Loop discipline](#loop-discipline) below.

`${CLAUDE_PLUGIN_ROOT}` is set by Claude Code to the plugin install path. `$COMPANY_ROOT` is sourced from `config.toml` and is first populated by `kiho-setup` on a fresh install.

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
| `evolve` or `evolve <skill>` | evolve | optional skill name; accepts `--audit=<lens>` for a deterministic read-only audit (lens values: `storage-fit` — verifies `metadata.kiho.data_classes:` against `references/data-storage-matrix.md`; see `skills/_meta/evolution-scan/references/storage-audit-lens.md`) |
| Path to an existing file | feature-from-prd | absolute path |
| `--tier=<minimal\|normal\|careful>` | (modifier on any mode) | sets discipline level; logged as `action: tier_declared, value: <tier>` before any delegation |
| Anything else | unclassified | raw string |

For `unclassified`, the CEO reads `.kiho/state/plan.md` (if present) + last 10 session-context entries, then classifies internally. If still unclear, the CEO calls `AskUserQuestion` (Route C below).

See `references/worked-examples.md` for the four canonical dispatch shapes: implicit feature from plain description, PRD path, vibe, and resume.

## Tier discipline (v5.22)

`--tier` is a modifier, not a mode — it attaches to any of the modes above and controls how strictly the CEO enforces v5.22 invariants. Defaults to `normal` when unspecified. The CEO declares the tier as the first visible line of its response (`TIER: <value>`) and writes `action: tier_declared` as the first ledger entry of the turn, before any delegation.

| Tier | Recruit | Research cascade | Committees | KB writes | User-visible marker |
|---|---|---|---|---|---|
| `minimal` | shortcut allowed (logged `recruit_shortcut_taken`) | main-thread OK for any scope | skippable | direct Write allowed (logged `kb_direct_taken`; PreToolUse hook still fires — bypass requires both tier=minimal and content certificate) | ⚠️ MINIMAL TIER — ceremonies skipped |
| `normal` (default) | quick-hire required for new agents | `kiho:kiho-researcher` preferred; main-thread research OK for <30s sanity checks | mini-committee for non-trivial decisions | via `kiho-kb-manager` only | (none) |
| `careful` | careful-hire only | `kiho:kiho-researcher` mandatory; main-thread research aborts the turn with a drift flag | full committee with 4 auditors for every spec decision | strictly via `kiho-kb-manager`; no inline edits even with certificate | 🔒 CAREFUL TIER |

**Choosing a tier:**

- **minimal** — throwaway spike, single-file edit, time-boxed exploration, prototype where you explicitly accept drift and want to tag it rather than hide it.
- **normal** — day-to-day feature / bugfix / refactor work. Use this unless you have a reason not to.
- **careful** — lead/senior hiring, security-sensitive decisions, production-bound spec, compliance-relevant changes. The full machinery runs and any shortcut is a hard drift flag.

The declared tier does NOT relax the v5.22 PreToolUse hooks (those still fire on every Write/Edit regardless of tier). It DOES change what the CEO treats as a policy violation in its own loop and what `bin/ceo_behavior_audit.py` considers drift.

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

## Failure playbook

Failures during startup or the Ralph loop must route through the decision below rather than raising raw errors to the user. Silent retry is forbidden — every retry is recorded in the CEO ledger at `.kiho/state/ceo-ledger.jsonl`.

**Severity:** error (blocks the `/kiho` turn from completing). **Taxonomy:** config | transient | resource | protocol.

| Trigger | Route | Action |
|---|---|---|
| `config.toml` missing, OR present with empty `company_root` | **A — setup** | Log the failure, invoke `kiho-setup`, retry from startup step 1 |
| `agents/kiho-ceo.md` missing | **B — reinstall** | Abort with `status: ceo_persona_missing`; user reinstalls the plugin (no automated recovery) |
| `$ARGUMENTS` empty, OR mode=`unclassified` with empty `plan.md` | **C — ask user** | CEO calls `AskUserQuestion` with mode/description options, ends the turn; the user's reply dispatches on the next invocation |
| `max_ralph_iterations` exceeded, OR `stuck_timeout_min` elapsed with no progress | **D — checkpoint** | Write plan + iteration count + last step to `.kiho/state/<spec>/partial.md`, emit structured summary with `status: max_iterations` or `status: user_question`, end turn; user resumes via `/kiho --resume <spec>` |
| Sub-agent returned malformed output | **E — retry-then-escalate** | Log full malformed body; retry the sub-agent **once** with a schema reminder; on second failure, escalate via `AskUserQuestion` attaching both responses |

Routes A–E are the only exits from failure.

## Loop discipline

The CEO runs inside a single main-agent turn. It must not stop until one of:

- `plan.md` Pending list is empty **AND** `completion.md` criteria are met → `status: complete`
- A user answer is required — CEO calls `AskUserQuestion` → `status: user_question`
- `max_ralph_iterations` from `config.toml` is exceeded → `status: max_iterations`, checkpoint via Route D

Each Ralph iteration runs a mid-loop `INTEGRATE` step that routes decisions with confidence ≥ 0.90 through `kiho-kb-manager` via `kb-add`. The KB stays current throughout the session.

## Invariants

The following are load-bearing MUSTs. Each has a reason attached so you can distinguish a legitimate exception from drift.

- **Delegate every request.** Inline execution bypasses RACI, committees, and KB updates — the core value proposition. Vibe mode still routes through the CEO; it just skips spec creation and delegates directly to an IC.
- **Route every KB write through `kiho-kb-manager`.** Direct writes to `.kiho/kb/wiki/` corrupt the Karpathy-wiki invariants (root files, tier indexes) because the kb-manager is the only component that runs the post-write lint/promote pipeline.
- **[v6.4] Route content via the 3-lane classifier.** Every confidence ≥0.90 decision (or B/D/E/F trigger fire) MUST classify into ONE of: **Lane A** (state — `state_decision` ledger entry), **Lane B** (KB — `kb_add` via kb-manager), **Lane C** (memory — `memory_write` to `agents/<name>/memory/lessons.md` for skill-shaped, or `~/.claude/projects/<cwd>/memory/feedback_*.md` for user-facing feedback). Do NOT bypass with direct kb-add — kb-manager will refuse Lane-B-failing entries with `status: rejected, suggested_lane`. Audit script v6.4+ flags state-shaped content that landed in KB anyway. KB capture is multi-trigger (six scenarios A-F); B/D bypass the ≥0.90 confidence gate. See `agents/kiho-ceo.md` §INTEGRATE + `references/content-routing.md` for the full decision tree.
- **Respect depth cap 3 (CEO → Dept → Team/IC) and fanout cap 5.** These are empirical ceilings — deeper stacks lose coherence, wider fanouts exceed attention budget. See `references/grounding.md` §"Depth cap 3 + fanout cap 5".
- **Use the research cascade** (KB → web → deepwiki → clone → ask-user) via the `research` skill. Direct `WebFetch` skips trusted-source registry promotion and corrupts KB consistency.
- **End the turn with a structured summary** (shape below) when the loop exits. Downstream tooling (`/kiho --resume`, IDE extensions, telemetry rollup) consumes the envelope to know what changed.

### Anti-patterns specific to this entry skill

- **Do not invoke `/kiho` from a sub-agent.** Escalations route back to the main-conversation CEO via `escalate_to_user` bubble-up, not by re-entering the skill.
- **Do not create new entry-point slash commands.** The 1%/8k-char skill-description budget is paid once; adding `/kiho-feature`, `/kiho-bugfix`, etc. blows that ceiling by the second addition (see `references/rejected-alternatives.md` §A2).
- **Do not use vibe mode for complex features.** Vibe skips spec creation and committee review. Reserve it for single-file tasks under an hour.
- **Do not soft-stop the Ralph loop.** Mid-iteration prompts like 「要我繼續嗎」 / "shall I proceed" / "want me to start Turn N" violate the loop discipline. If the plan has pending items, the CEO MUST pick the next one and DELEGATE; if it needs a decision, MUST call `AskUserQuestion`; if done, MUST emit `status: complete`. The audit at `bin/ceo_behavior_audit.py` flags this as `soft_stop_drift` — projects on v6.5.1+ get the check on every DONE step.
- **Do not soft-stop via `next_action` field.** Phrases like `"next_action": "下個 /kiho 接 Turn 2"` are structural soft-stops disguised as JSON. They violate the same rule as natural-language `"要我繼續嗎"` prompts. Caught by `bin/ceo_behavior_audit.py check_soft_stop_drift` Signal 3 as MAJOR (CRITICAL when plan.md Pending is non-empty).

## Response shape

When a `/kiho` turn ends, the main agent returns a structured summary. `/kiho --resume`, telemetry rollup, and IDE extensions all consume this shape.

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

- `complete` — plan empty, completion criteria met; no follow-up needed
- `user_question` — `AskUserQuestion` was called mid-loop; the user's next message resumes the loop
- `max_iterations` — Ralph loop hit its budget; partial summary in `.kiho/state/`; resume via `/kiho --resume <spec-name>`
- `error` — unrecoverable failure routed through the failure playbook

## Deep references

These files are not on the hot path. Read them when the situation calls for it.

- `references/worked-examples.md` — canonical dispatch envelopes for implicit feature, PRD path, vibe, and resume. Read when the mode-parsing table leaves a shape ambiguous.
- `references/rejected-alternatives.md` — A1–A5, the designs that were evaluated and rejected (inline execution, mode-per-command, flagless auto-classification, CEO-in-subagent, two-file split harness). Read before proposing a redesign.
- `references/grounding.md` — the five source citations underwriting the design (kubectl single-entry, Ralph loop discipline, main-conversation-only AskUserQuestion, generator/evaluator separation, empirical depth/fanout caps). Read when defending a rule in committee.

The Ralph loop itself, the INITIALIZE checklist, the DONE checklist, and the escalation decision table all live in `agents/kiho-ceo.md` — that file is loaded at startup step 2, so those details do not need to be reproduced here.
