---
name: okr-set
description: Create a new OKR (Objective + 3-5 Key Results) at company, department, or individual level. Enforces a RACI pre-emit gate that refuses to write the Tier-1 markdown file until the appropriate approval stage has produced its certificate (USER_OKR_CERTIFICATE for company, DEPT_COMMITTEE_OKR_CERTIFICATE for department, DEPT_LEAD_OKR_CERTIFICATE for individual). Validates KR count (3-5), weights (sum ≤ 100), alignment (non-company levels must cite an existing parent O). Writes one markdown file per Objective under `<project>/.kiho/state/okrs/<period>/O-<period>-<level>-<slug>-<n>.md`. Use this skill when the user invokes /kiho with OKR-setting intent ("set an OKR", "I want an objective for Q2", "have engineering set a goal"), when a department lead convenes a committee and the closed decision mandates a new O, or when an agent proposes an individual O and the dept-lead approves. See references/okr-guide.md for the user-facing primer. Does NOT run automatic cadence — invocation is always explicit.
argument-hint: "level=company|department|individual title=<text> period=<YYYY-QN> [aligns_to=<O-id>] [owner=<agent-id>]"
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: active
  kiho:
    capability: create
    topic_tags: [governance, planning, lifecycle]
    data_classes: ["okrs-period-md"]
    storage_fit:
      reads:
        - "<project>/.kiho/state/okrs/<period>/"
        - "<project>/.kiho/committees/<id>/decision.md"
        - "<project>/.kiho/state/org-registry.md"
      writes:
        - "<project>/.kiho/state/okrs/<period>/O-<period>-<level>-<slug>-<n>.md"
---
# okr-set

Creates a new Objective + its Key Results as a Tier-1 markdown file. The skill refuses to emit without the appropriate certificate for the chosen level — it is the **generator side** of the generator/evaluator separation kiho uses for every write-sensitive surface.

Companion: `okr-checkin` (mid-period updates), `okr-close` (period-end aggregation). User-facing guide: `references/okr-guide.md`.

## When to use

Invoke this skill when:

- User invokes `/kiho` with OKR-setting intent. The CEO classifies intent and routes here.
- A department lead's committee closes with a recommendation to formalize a new department Objective (the committee decision page at `decisions/<dept>-okr-<period>.md` is the prerequisite artifact).
- An agent proposes an individual Objective and the dept-lead has approved via the `okr-individual` approval chain (dept-lead emits the `DEPT_LEAD_OKR_CERTIFICATE` marker first; this skill consumes it).

Do **not** invoke:

- To record a single task or a plan.md item — that's `kiho-plan`'s domain. OKRs are directional, not granular.
- To adjust weights or scores on an existing Objective — use `okr-checkin`.
- To close out an Objective at period end — use `okr-close`.
- For automatic "set an OKR every N turns" cadence. There is no such cadence. Invocation is explicit.

## Inputs

```
PAYLOAD:
  level:              company | department | individual   # required
  title:              <one-sentence Objective>            # required
  period:             <YYYY-QN | YYYY-HN | YYYY-<slug>>   # required
  owner:              <agent-id or "user">                # required; user-owner is company-only
  aligns_to:          <parent O id>                       # required for department + individual
  kr:                 list of 3-5 KR records              # required
  slug:               <kebab-case hint>                   # optional, derived from title if omitted
  dept:               <department name>                   # required for level=department
  certificate:        <raw certificate body>              # required — one of the three markers per level
```

Each KR record:

```
  kr:
    - id:            <stable slug, unique within Objective>
      description:   <measurable statement>
      weight:        <0-100 integer>
      target:        <numeric or descriptive>
      direction:     up | down | binary
      stretch:       <bool; optional; default false>
```

## Procedure

### 1. Validate shape

- `level ∈ {company, department, individual}` — else reject.
- `period` matches the pattern `\d{4}-(Q[1-4]|H[1-2]|[a-z0-9-]+)` — else reject.
- `len(kr)` in [3, 5] — else reject with `status: kr_count_out_of_range`.
- `sum(kr[].weight) ≤ 100` — else reject (normalization at scoring time, but weights must not exceed 100 at emit).
- Each KR has a unique `id` within the Objective.
- `level ∈ {department, individual}` → `aligns_to` MUST be present AND MUST reference an existing O file in the same or earlier period (skill reads `.kiho/state/okrs/**/O-*.md` to confirm).

### 2. Resolve prerequisite per level (skill-internal pre-emit gate)

This is the **load-bearing RACI enforcement**. The skill does not write until the prerequisite is satisfied. The PreToolUse hook is a second-layer defense but must not be the first.

| Level | Prerequisite | Missing → |
|---|---|---|
| `company` | CEO has routed an `AskUserQuestion` and the user accepted; `certificate` contains a `USER_OKR_CERTIFICATE:` block with `accepted_by: user` and `accepted_at: <iso>` | return `status: pre_emit_gate_needs_user` — CEO re-routes through AskUserQuestion |
| `department` | A closed committee decision page at `<project>/.kiho/committees/<committee-id>/decision.md` exists with `outcome: unanimous` and mentions this O in the `decision` field; `certificate` contains `DEPT_COMMITTEE_OKR_CERTIFICATE:` block referencing the committee_id | return `status: pre_emit_gate_committee_required` |
| `individual` | Dept-lead for `owner`'s department has emitted `DEPT_LEAD_OKR_CERTIFICATE:` block referencing the proposing agent + aligns_to | return `status: pre_emit_gate_dept_lead_required` |

If the prerequisite check fails, do not Write. Return the status envelope so the CEO / dept-lead / agent can correct.

### 3. Derive identifiers

- `o_id = O-<period>-<level-slug>-<n>` where:
  - `level-slug` is `company` / `dept-<dept>` / `individual-<agent-id>`
  - `n` is the next integer not already used in `<project>/.kiho/state/okrs/<period>/`
- `slug` defaults to first 3 meaningful words of `title`, lowercased, hyphenated.

### 4. Emit the Objective file

Write `<project>/.kiho/state/okrs/<period>/<o_id>.md` with frontmatter:

```yaml
---
o_id: <o_id>
okr_level: company | department | individual
period: <period>
owner: <owner>
aligns_to: <parent O id or null>
status: active
slug: <slug>
created_at: <iso>
weights_sum: <int>
# Embedded certificate block required by PreToolUse hook
# (format: HTML comment at end of file — see § Certificate block)
---
# <title>

## Key Results

### <kr[0].id>

- description: <text>
- weight: <int>
- target: <target>
- direction: <up | down | binary>
- stretch: <bool>
- current_score: 0.0
- history: []

### <kr[1].id>
...
```

Append the certificate block as an HTML comment at the bottom, verbatim. The hook (`pre_write_chain_gate.py`) matches the certificate_marker per `references/approval-chains.toml`; the write passes when the marker string is present in content.

### 5. Ledger entry

Emit to `<project>/.kiho/state/ceo-ledger.jsonl`:

```
{"ts": "<iso>", "action": "okr_set",
 "payload": {"o_id": "<o_id>", "level": "<level>", "period": "<period>",
             "owner": "<owner>", "aligns_to": "<parent or null>",
             "kr_count": <n>, "weights_sum": <int>}}
```

### 6. Mirror into plan.md (optional, company + department levels)

For `level ∈ {company, department}`, append a one-line reference to `<project>/.kiho/state/plan.md` under `## Active Objectives (<period>)`:

```
- [<o_id>] <title> — owner: <owner> (aligns: <parent or self>)
```

This is a surface convenience so retrospectives and standups see the Objective in the same scan as tasks. Individual Os stay out of plan.md to avoid clutter.

## Response shape

```
## Receipt <REQUEST_ID>
OPERATION: okr-set
STATUS: ok | pre_emit_gate_needs_user | pre_emit_gate_committee_required | pre_emit_gate_dept_lead_required | invalid_input
O_ID: <id or null>
PATH: <project-relative path or null>
LEDGER_REF: jsonl://state/ceo-ledger.jsonl#seq=<n>
PLAN_UPDATED: <bool>
NOTES: <optional>
```

## Invariants

- **Three-level RACI.** Only the user sets company Os (via AskUserQuestion accept). Only committees set department Os (via closed decision page). Only dept-leads sanction individual Os (via approval-chain emission).
- **No silent level upgrade.** A department O cannot be re-classified as company without running the company chain from scratch. Status transitions are one-way at this level.
- **Weights sum ≤ 100.** Enforced at emit; stored verbatim in frontmatter as `weights_sum`.
- **KR count 3-5.** Enforced at emit. Fewer than 3 = insufficient measurement; more than 5 = attention overload.
- **Certificate in content.** The PreToolUse hook blocks any write that lacks the level's certificate marker. The skill emits the marker as part of the file body — NEVER synthesizes a fake marker to pass the gate; the marker is evidence the approval stage actually ran.
- **No auto-close, no auto-cadence.** `okr-set` creates; `okr-checkin` updates; `okr-close` closes. Each is explicit.

## Non-Goals

- **Not a broadcast.** Setting an Objective does not announce it to every agent. Use `memo-send to=@all` with `basis: <o-path>` if you want announcement semantics (v5.23 broadcast extension).
- **Not a plan.md rewrite.** OKRs are the direction layer; `plan.md` stays as the execution layer with RACI tasks. A one-line mirror (step 6) is the only cross-pollination.
- **Not a replacement for `kiho-plan`.** Plan tasks may `aligns_to: <o_id>` in their frontmatter, but the two surfaces remain distinct.
- **Not a scheduler.** No time-based triggers. No automatic quarterly rollover. The user invokes `/kiho` at period start.

## Anti-patterns

- Inventing a certificate marker inline. The marker is evidence of approval, not a sigil. Writing `USER_OKR_CERTIFICATE: accepted: true` without the CEO actually having asked the user is the exact drift class the v5.22 hook system was built to catch.
- Setting more than ~5 company Objectives. The committee decision caps at 5 per period for a reason.
- Using `individual` level to bypass committee for a department-scope Objective. The aligns_to check catches this (an individual O must align to an existing department O; you can't forge a parent).
- Setting KRs that are activity lists ("hold 5 meetings") rather than outcome metrics ("reduce mean decision wall-clock by 30%"). No machine check catches this; the dept-lead / user accepting the draft is the filter.

## Grounding

- `_proposals/v5.23-oa-integration/01-committee-okr/decision.md` — the committee decision that grounds this skill.
- `references/okr-guide.md` — user-facing primer (when to set OKRs, how they help).
- `references/approval-chains.toml` — the three chains (`okr-company`, `okr-department`, `okr-individual`) enforced by `bin/hooks/pre_write_chain_gate.py`.
- `references/data-storage-matrix.md` §7 `okrs-period-md` — storage tier + regeneration + gatekeeper.
- `references/committee-rules.md` — department-level OKR committees follow the standard format.
- `skills/core/hr/agent-promote/SKILL.md` §2a — how closed individual OKRs feed promotion criteria.

## Worked example: setting a company Objective

User: `/kiho set a company OKR for 2026-Q2: ship the v5.23 OA integration with zero regressions to v5.22 hooks by 2026-06-30`.

1. CEO classifies intent → routes to `okr-set` with draft `{level: company, title: "Ship v5.23 OA integration ...", period: "2026-Q2", ...}`.
2. Skill validates shape, sees `level=company`, sees no `USER_OKR_CERTIFICATE:` in the draft → returns `status: pre_emit_gate_needs_user`.
3. CEO calls `AskUserQuestion` with the full draft (title + proposed KRs + weights).
4. User accepts (or edits + accepts).
5. CEO re-invokes `okr-set` with the accepted payload + a `USER_OKR_CERTIFICATE:` block containing `accepted_by: user`, `accepted_at: <iso>`, `conversation_turn: <id>`.
6. Skill validates, writes `<project>/.kiho/state/okrs/2026-Q2/O-2026Q2-company-01.md`, appends to `plan.md` Active Objectives, emits `okr_set` ledger row.
7. PreToolUse hook passes the Write (certificate present, path matches `okr-company` chain).
