---
name: postmortem
description: Use this skill to close an open incident with a blameless root-cause analysis. Required whenever an incident opened by incident-open has been mitigated and the Ralph loop has resumed normal flow. Produces a Tier-1 markdown postmortem with timeline, root cause, contributing factors, corrective actions, and sign-off. The postmortem is blameless-by-construction — the root_cause field must describe a system or process failure, not an agent identity; the skill rejects writes where root_cause contains agent-identity tokens. Corrective actions are mirrored into the actions jsonl for follow-up tracking. For sev1 incidents the skill also triggers a retrospective; for sev2 the retrospective is optional; for sev3 postmortem is optional too (status closed without one).
argument-hint: "incident_id=<id> root_cause=<text>"
metadata:
  trust-tier: T2
  kiho:
    capability: evaluate
    topic_tags: [safety, reflection]
    data_classes: [lessons]
---
# postmortem

Closes an open incident with a blameless root-cause analysis. Every sev1 incident must pass through this skill; sev2 should; sev3 may. Blameless discipline is not a politeness norm — it is a design constraint that keeps the incident record useful across committee review and future agent training. A postmortem that names an agent as the cause teaches the system nothing reproducible; a postmortem that names a missing check, a racy protocol, or a misaligned contract teaches a fix.

> **v5.21 cycle-aware.** This skill is invoked as the `postmortem` phase entry in `references/cycle-templates/incident-lifecycle.toml`. When run from cycle-runner, the cycle's `index.toml` carries the lifecycle position (incident_id, severity, affected_agents); this skill produces the canonical `postmortem.md` artifact and writes its ref + corrective_actions_count back into `index.postmortem.*`. The blameless linter still applies regardless of invocation path. Atomic invocation (outside any cycle) remains supported for ad-hoc historical postmortems.

## Why blameless

Kiho agents are procedurally generated, tuned by souls, and replaced when they drift. Blaming "agent research-07" for a bad citation is exactly as useful as blaming "yesterday's weather" — the entity that failed will not be the entity that runs tomorrow. Systemic lessons outlive individual agents; individual blame does not. The linter in this skill enforces that property mechanically so authors cannot accidentally write a blame-shaped postmortem under deadline pressure.

## Inputs

```
PAYLOAD:
  incident_id: <id returned by incident-open>
  timeline: [{iter: <n>, event: <one-line>}, ...]
  root_cause: <free text describing the system or process failure>
  contributing_factors: [<free text>, ...]
  corrective_actions: [
    {description: <text>, owner: <agent-id-or-role>, due_iteration: <n>},
    ...
  ]
  blameless: true   # must be true; gate for the linter
  signoff: <agent-id of the reviewer, usually ceo-01 or a dept-lead>
```

## Blameless linter

Runs before the broker write. Non-bypassable.

### Tokens it rejects

1. Any agent-id string from the live org registry (`state/org-registry.md`). Load the registry at linter start; match case-insensitively against both the id (e.g., `research-07`) and the display name (`Research 7`).
2. The role-filler patterns `agent <name>`, `<name> agent`, `the <name>`, where `<name>` is an org-registry entry.
3. Blame verbs when attached to an agent-id token: `failed to`, `forgot to`, `was careless`, `ignored`, `should have`, within ±40 characters of an agent-id match.

### Fields it scans

- `root_cause` (mandatory scan)
- Every entry in `contributing_factors` (mandatory scan)
- `timeline[].event` (scan only; blame-shaped timeline entries are warned but not rejected, because timelines must record what actually happened)

### On match

Return `status: policy_violation` with:

```
reason: "root_cause or contributing_factors references an agent identity; rewrite as a system or process failure description."
offending_field: root_cause | contributing_factors[<i>]
offending_token: <matched string>
example_rewrite: |
  Before: "research-07 failed to verify the citation because it was careless."
  After:  "The research cascade's step-2 confidence threshold was not enforced at
          the web-fetch boundary, so a single low-quality source advanced to
          synthesis. No guardrail existed between WebSearch and the citation
          pass."
```

The caller must revise and re-invoke. There is no override flag.

### On clean pass

Emit a `blameless: true, linter_version: <v>` tag in the postmortem frontmatter so reviewers know the linter ran.

## Procedure

### Step 1 — Load the incident record

Call `storage-broker` op=`get` namespace=`state/incidents` id=`<incident_id>`. If the record is missing or already `status: closed`, abort with `status: invalid_state` — postmortems can only close open incidents, and an incident-id typo must not silently create an orphan.

Capture the record's `severity` field; it drives step 3 and step 6.

### Step 2 — Run the blameless linter

As specified above. On `policy_violation`, stop; do not touch the broker. On clean pass, continue.

### Step 3 — Write the postmortem

For `severity in {sev1, sev2}`, always write. For sev3, write only if `corrective_actions` is non-empty (otherwise skip to step 5 and close without a postmortem file).

Call `storage-broker` op=`put`:

```
NAMESPACE: state/postmortems
KIND: postmortem
HUMAN_LEGIBLE: true
ID: pm-<incident_id>
BODY: |
  # Postmortem for <incident_id>

  - **Incident severity:** <sev1|sev2|sev3>
  - **Closed:** <iso>
  - **Signoff:** <signoff>
  - **Blameless linter:** pass (v<n>)

  ## Timeline
  <rendered timeline, one iter per line>

  ## Root cause
  <root_cause verbatim>

  ## Contributing factors
  <bulleted contributing_factors>

  ## Corrective actions
  <rendered actions with owner and due_iteration>

  ## Links
  - Incident: <broker ref from step 1>
```

`kind=postmortem` is on the reviewable-forced-to-md list; Tier-1 markdown is mandatory.

### Step 4 — Mirror corrective actions

For each entry in `corrective_actions`, call `storage-broker` op=`put`:

```
NAMESPACE: state/actions
KIND: generic
BODY_FORMAT: jsonl-append
PAYLOAD:
  action_id: <auto>
  incident_id: <id>
  postmortem_ref: <ref from step 3>
  description: <text>
  owner: <agent-id-or-role>
  due_iteration: <n>
  status: open
  created_at: <iso>
```

The actions log is Tier-2, regenerable from the Tier-1 postmortems. It exists so `ops-dashboard` can surface overdue corrective actions without parsing prose.

### Step 5 — Close the incident

Call `kiho-kb-manager` op=`update` on the original incident record:

```
fields:
  status: closed
  closed_at: <iso>
  postmortem_ref: <pm ref or null for sev3-without-pm>
  timeline_append:
    - <iso> — closed by postmortem
```

Also append a `status: closed` row to `state/incidents/index`. Status mutation never goes through `storage-broker` directly — it always flows through kb-manager to preserve the audit chain.

### Step 6 — Notify CEO for sev1

For `severity == sev1`, call `memo-send`:

```
to: ceo-01
severity: action
subject: "Postmortem complete for <incident_id>; retrospective required"
body: |
  Postmortem: <pm ref>
  Root cause: <first 200 chars>
  Corrective actions: <count>; next due at iteration <min due_iteration>
  Retrospective: required (sev1); recommended follow-up within 5 iterations.
```

For sev2, the retrospective is optional — no memo. For sev3, nothing.

### Step 7 — Distribute lesson to affected agents (v5.20 Wave 2.1)

For every agent in the incident's `affected_agents` list, call `memory-write`:

```
agent_id: <affected>
type: lesson
importance: 9                       # incidents are the highest-signal lesson source
subject: "Postmortem <incident_id>: <root_cause first 80 chars>"
body: |
  Severity: <sev1|sev2|sev3>
  Root cause: <root_cause first 200 chars>
  Contributing factors: <count>; key factor: <first factor headline>
  Corrective actions due by iteration: <min due_iteration>
  What to do differently: <one-line preventive note distilled from corrective_actions>
refs: [<pm_ref>, <incident_ref>]
```

Incidents are the most expensive learning the organization buys; the lesson MUST land in every affected agent's memory so that future delegation briefs (CEO INITIALIZE step 9 injects last-5 lessons) carry the prevention forward. Failure to write a lesson is best-effort — log `memory_write_skipped: <agent_id>: <reason>` in the postmortem ref's metadata and continue. Sev3 still writes lessons, even though no CEO memo was sent.

## Response shapes

```markdown
## Receipt <REQUEST_ID>
OPERATION: postmortem
STATUS: ok | policy_violation | invalid_state
INCIDENT_ID: <id>
POSTMORTEM_REF: <broker ref or null>
ACTIONS_WRITTEN: <count>
INCIDENT_CLOSED: true
RETROSPECTIVE_REQUIRED: true | false
NOTES: <optional>
```

On `policy_violation`, include `offending_field`, `offending_token`, and `example_rewrite` from the linter. On `invalid_state`, include the current status of the referenced incident.

## Invariants

- Blameless linter is non-bypassable. No flag, no override, no severity-based exception. Sev1 incidents especially must not bypass — high-severity is exactly when blame pressure is highest.
- Tier-1 markdown is enforced by the broker. Callers cannot request JSON or Tier-2 downgrade.
- An incident must be `open` to be closed. Double-close attempts return `invalid_state`, preserving the first closure's timeline.
- The corrective-actions mirror is append-only and regenerable from the Tier-1 postmortem. Editing the postmortem body and expecting the actions log to update is not supported; rewrite via kb-manager and re-mirror.
- Postmortem refs are deterministic: `pm-<incident_id>`. There is exactly one postmortem per incident.

## Non-Goals

- Not a replacement for retrospective. Retrospectives cover wider scope — a whole sprint, a skill generation, a capability rollout — and synthesize across multiple incidents plus non-incident signal. This skill closes one incident.
- Not a blame assignment mechanism. The linter exists precisely to reject that use.
- Not a real-time debugger. If the incident is still actively firing, do not open a postmortem; mitigate first, then close.
- Not a metrics dashboard. Counts, MTTR, and trend lines belong to `ops-dashboard`, which reads the index and actions log this skill maintains.

## Grounding

- `skills/core/storage/storage-broker/SKILL.md` — `put` API, reviewable-forced-to-md for `kind=postmortem`, and the `state/actions` namespace.
- `skills/core/ops/incident-open/SKILL.md` — the open-side ceremony, severity definitions, and index schema this skill closes against.
- `skills/core/ops/retrospective/SKILL.md` — the wider-scope ceremony that consumes sev1 postmortems. Read when writing one, cite when closing one.
- `references/react-storage-doctrine.md` — tier rules for incidents, postmortems, and action logs; why status mutation routes through kb-manager.
