---
name: retrospective
description: Use this skill when the CEO should reflect on a completed turn or incident cluster and surface systemic improvements. Fires when a turn exceeds an iteration threshold, when a blocker chain was non-trivial, when a user-accept rejection happened, or when a sev1 postmortem completes. Produces a Tier-1 markdown artifact with sections for what went well, what hurt, systemic observations, and actions with owners and due iterations. Actions mirror into the actions JSONL for follow-up. Reads prior standup-log entries, agent-performance JSONL, ceo-ledger, and any related postmortem as pre-read. Not for re-litigating already-decided items — retrospective focuses on patterns, not individual decisions.
argument-hint: "turn_id=<id> scope=<turn|sprint|incident>"
metadata:
  trust-tier: T2
  kiho:
    capability: evaluate
    topic_tags: [reflection, lifecycle]
    data_classes: [observations, lessons]
---
# retrospective

A retrospective is a **ceremony**, not a debate. Its job is to promote the signal buried in a week of standups into a durable Tier-1 artifact and a small set of actionable follow-ups. Five minutes of committee attention should yield a retrospective; longer means the scope was wrong.

> **v5.21 cycle-aware.** Retrospective is invoked atomically (most cases — periodic hygiene pass) AND fired as a hook from `incident-lifecycle.toml` when sev1 cycle reaches `closed-success`. The retrospective.md artifact is the canonical record; cycle templates that trigger retrospective do so via `lifecycle_hooks.on_close_success` (best-effort) rather than as a phase entry. Atomic invocation is the recommended path.

## Why a ceremony

Standups are abundant and lossy; postmortems are rare and heavy. The retrospective sits in between: it asks one question — *what patterns should we keep or change?* — and writes the answer where future committees will find it. Without a ceremony, teams accumulate standups and memos until nobody re-reads them. With one, every N iterations the organization distills its own experience.

## Inputs

```
PAYLOAD:
  turn_id: <id>               # required — e.g., "turn-142"
  scope: turn | sprint | incident   # required
  participants: [<agent_id>, ...]   # default: all agents active in scope
  metrics_ref: <jsonl-ref>    # optional — agent-performance window to pre-read
  incident_id: <id>           # required iff scope == incident
  time_window: { start: <iso>, end: <iso> }   # optional, default: scope bounds
```

Scope picks the time window and the framing:
- `turn` — a single Ralph turn that exceeded iteration threshold or had a notable event.
- `sprint` — a named block of turns (rare; used when the CEO runs a multi-turn initiative).
- `incident` — retrospective paired with a sev1 postmortem; `incident_id` required.

## Procedure

### 1. Gather

Pull the pre-read bundle without interpreting it yet:

- **Dashboard (v5.23+)** — invoke `python ${CLAUDE_PLUGIN_ROOT}/bin/dashboard.py --project <project> --period per-cycle --cycle-id <id>` (or `--period quarterly --quarter YYYY-QN` at quarter close) BEFORE anything else. If the dashboard file `<project>/.kiho/state/dashboards/<label>.md` is absent or stale (older than the latest cycle-events.jsonl entry), the script regenerates it. Read the resulting markdown into context — it anchors the retrospective narrative in concrete numbers. Per decision `dashboard-analytics-2026-04-23`.
- `memory-query` for each participant over `time_window`, filtered to observations with importance >= 8.
- `storage-broker` op=`query` on `state/standups/<YYYY-WW>` for every week touched by the window, filtered to `participants`.
- `storage-broker` op=`read` on the ceo-ledger rows for the turn(s) in scope.
- If `scope == incident`, fetch the postmortem artifact via its ref.
- If `metrics_ref` provided, read the agent-performance window.

Hard budget: 90 seconds for gather. If a query is slow, shrink the window rather than block. Dashboard regeneration is typically <2s on any project size.

### 2. Synthesize

Assemble five sections. Each is a bulleted list of one-line items with evidence refs — not essays.

- **went_well** — patterns that produced value. Every bullet cites at least one standup or ledger ref.
- **hurt** — patterns that cost time or trust. Blameless: describe the situation, not the agent.
- **process_friction** — (v5.23+) each participant's one-sentence answer to: *"What in this period's process blocked or slowed you? Answer 'nothing' if nothing did."* One bullet per participant; non-optional. If the `nothing`-to-`specific` ratio drops below 50%, emit a `values-flag` with topic `process-friction` so the next `values-alignment-audit` picks it up. Replaces ad-hoc pulse surveys — see `references/committee-rules.md` §Lightweight committee for the related lightweight-poll pattern.
- **systemic** — observations that generalize beyond this scope. A systemic observation names a recurring shape (e.g., "blockers around credential rotation appear every 3rd sprint") not a one-off.
- **actions** — concrete follow-ups. Each action has `owner`, `due_iteration`, and `success_criterion`.

The blameless linter is shared with postmortem: it flags any bullet naming an agent in a hurt, process_friction, or systemic context without a situational frame. Rewrite flagged bullets before proceeding to step 3.

### 3. Persist the retrospective artifact

Call `storage-broker` op=`put`:

```
OPERATION: put
PAYLOAD:
  namespace: state/retros
  kind: retrospective
  access_pattern: read-mostly
  durability: project
  human_legible: true
  body: |
    # Retrospective — <turn_id> (<scope>)

    **Window:** <start> → <end>
    **Participants:** <list>
    **Related:** <incident_id? metrics_ref? ledger refs>

    ## What went well
    - ...

    ## What hurt
    - ...

    ## Process friction (one bullet per participant; 'nothing' is valid)
    - **<participant>** — <one sentence>
    ...

    ## Systemic observations
    - ...

    ## Actions
    - owner: <agent_id>
      due_iteration: <id>
      success_criterion: <one line>
      description: <one line>
```

Storage-broker selects Tier-1 markdown because `human_legible: true` and `access_pattern: read-mostly`. The returned ref is of the form `md://state/retros/<turn_id>.md`.

### 4. Persist actions

For each action in the Actions section, call `storage-broker` op=`put`:

```
OPERATION: put
PAYLOAD:
  namespace: state/actions
  kind: generic
  access_pattern: append-only
  durability: project
  human_legible: false
  body:
    source_retro_ref: <md://...>
    owner: <agent_id>
    due_iteration: <id>
    status: open
    success_criterion: <line>
    description: <line>
    opened_at: <iso>
```

Actions are tracked separately from retrospectives so `committee-agenda` can query open actions by owner or topic without parsing markdown.

### 5. Notify CEO

Send a single memo to `ceo-01`:

```
memo-send to=ceo-01 severity=fyi
  subject: "Retrospective for <turn_id>: <N> actions opened"
  body: <retro ref + bulleted action list with owners>
```

One memo per retrospective. Do not spam.

### 6. Distribute lessons to participating agents (v5.20 Wave 2.1)

For every Systemic observation that the retrospective surfaced, call `memory-write` once per `participants` agent_id with:

```
agent_id: <participant>
type: lesson
importance: 7                     # systemic findings outrank one-off observations
subject: "<systemic observation headline>"
body: |
  Source: <md://state/retros/<turn_id>.md>
  Pattern: <one-line description>
  Recommended response: <action ID + summary>
refs: [<retro_ref>, <action_refs...>]
```

This is the load-bearing change in Wave 2.1: previously a retrospective wrote a markdown artifact that no agent ever read again. Now each participating agent's lessons.md grows with the systemic patterns the org has surfaced, so future delegation briefs (CEO INITIALIZE step 9 injects last-5 lessons) carry that wisdom forward. Failure to write a lesson is best-effort — log `memory_write_skipped: <agent_id>: <reason>` and continue; the markdown retro is still the source of truth.

## Threshold triggers

The CEO decides when to run a retrospective. These are the documented triggers:

- **Iteration threshold.** A turn that ran > 12 iterations.
- **Blocker chain.** Three or more standup blockers on the same topic within a week.
- **User-accept rejection.** Any user rejection on a skill-factory or CEO escalation.
- **Sev1 postmortem.** Every sev1 postmortem pairs with a scope=incident retrospective.
- **Scheduled.** Every 4th Friday regardless of triggers, as a hygiene pass.

The CEO may also run a retrospective on demand. This skill does not enforce triggers; it just writes the artifact when called.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: retrospective
STATUS: ok | error
TURN_ID: <id>
SCOPE: turn | sprint | incident
RETRO_REF: md://state/retros/<turn_id>.md
ACTION_REFS:
  - jsonl://state/actions#L<n> (owner=<agent_id>, due=<iter>)
PARTICIPANTS: [<agent_id>, ...]
BLAMELESS_LINT: passed | rewrites=<n>
MEMO_REF: memo://inbox/ceo-01/<id>
NOTES: <optional>
```

## Invariants

- **Blameless.** Hurt and systemic sections never name an individual agent as the cause. The linter is strict; a retro that fails the linter is rewritten, not posted.
- **Evidence-bound.** Every bullet in went_well and hurt carries at least one ref to a standup, ledger row, or memo. Patterns with no evidence belong in soul reflection, not here.
- **Short.** A retrospective is a distillation, not a transcript. If the draft exceeds ~150 lines, the scope is too wide — split it.
- **Read-mostly.** Once posted, a retrospective is not edited. Corrections live in the next retrospective.

## Non-Goals

- **Not a planning ceremony.** `plan.md` owns forward work. Actions from a retrospective flow into plan.md via the CEO, not from this skill directly.
- **Not an all-hands.** No live synchronous meeting; retrospective is an artifact the CEO produces after reading the pre-read.
- **Not a decision log.** The CEO ledger records decisions; the retrospective records patterns.
- **Not a re-litigation tool.** If an item was already decided by a committee, it does not reopen here — systemic observations may note its cost but may not overturn it.

## Grounding

- `references/storage-architecture.md` — Tier-1 vs Tier-2 selection rules used in steps 3 and 4.
- `references/react-storage-doctrine.md` — why storage-broker owns the tier pick.
- `skills/core/ceremony/standup-log/SKILL.md` — the upstream source of raw observations.
- `skills/core/memory/memory-query/SKILL.md` — used in step 1 to gather archival observations.
- `skills/core/storage/storage-broker/SKILL.md` — the put / query / read ops used throughout.
- `skills/core/inspection/postmortem/SKILL.md` — paired ceremony for scope=incident.
- `references/committee-rules.md` — blameless linter rules shared with postmortem.
