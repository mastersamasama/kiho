---
name: incident-open
description: Use this skill the moment kiho detects a failure that warrants durable tracking — a sub-agent erroring twice on the same task, a user-accept gate rejection that invalidates prior work, any observed invariant violation like depth-cap breach or AskUserQuestion outside the CEO, or a sev1 bug report from the user. Writes a Tier-1 markdown incident file with severity triage, the trigger event, affected agents and tasks, and a pointer to follow-up work. Also emits a blocker memo to CEO so the Ralph loop routes around the failure. This skill opens the incident record; the paired postmortem skill closes it with a blameless write-up. Auto-fires from error-recovery paths; agents should invoke it explicitly whenever they suspect an invariant-breaking event rather than swallowing the error.
argument-hint: "severity=<sev1|sev2|sev3> trigger_event=<text>"
metadata:
  trust-tier: T2
  kiho:
    capability: create
    topic_tags: [safety, lifecycle]
    data_classes: [observations]
---
# incident-open

Opens a durable, committee-reviewable incident record the instant kiho detects a failure that deserves more than a silent retry. Incidents are the memory that prevents kiho from repeating the same mistake; they are blameless-by-design from the moment they are written.

> **v5.21 cycle-aware.** This skill MAY be invoked atomically (legacy path; one-shot incident creation) OR as the first phase entry in `references/cycle-templates/incident-lifecycle.toml`. When invoked from cycle-runner, the cycle's `<project>/.kiho/state/cycles/<id>/index.toml` is the SSoT for lifecycle position; this skill's `incident.md` write is still the authoritative artifact for the incident's content. CEO INITIALIZE step 18 reads `cycles/INDEX.md` to know which incident cycles need advancing this turn.

## Why a durable incident record

Before v5.20, when a sub-agent double-errored or a user rejected an accept-gate, the failure evaporated: the Ralph loop retried, noted the error in telemetry, and moved on. There was no object a committee could cite, no index to count sev1s per month, no artifact to attach a postmortem to. Transient failures became invisible; recurring failures became unprovable. This skill fixes that by forcing every qualifying failure through a single ceremony that produces one Tier-1 markdown file, one index row, and (for sev1/sev2) one blocker memo. Durable records prevent repeat failures. Blameless-from-birth records make it safe to open them without stigma.

## Inputs

```
PAYLOAD:
  incident_id: <optional — broker generates iso-<slug>-<nonce> if omitted>
  severity: sev1 | sev2 | sev3
  trigger_event: <one-sentence description of what happened>
  affected_agents: [<agent-id>, ...]
  affected_tasks: [<task-slug-or-raci-row>, ...]
  first_seen_iteration: <ralph-loop iteration number>
  detector_agent: <agent-id that noticed and called this skill>
  context: <optional free-text; logs, error codes, links>
```

## Severity

Severity is a triage dial, not a judgment. Pick the highest tier that matches.

- **sev1** — invariant breach (depth-cap exceeded, AskUserQuestion called outside CEO, kb-manager bypassed, trust-tier autonomous-ship attempt), user-accept gate rejected after work was already committed, data loss or corruption in `.kiho/state/`. sev1 always emits a blocker memo and always requires a postmortem.
- **sev2** — a sub-agent double-errored on the same task, a blocker remained unresolved after 3 Ralph iterations, a user memo escalation was dropped, a committee failed to reach unanimous close after 3 rounds. sev2 emits a blocker memo; postmortem is strongly recommended.
- **sev3** — observation-only: a near-miss, a deprecation warning, an unexpected but recovered condition. sev3 records the fact for pattern-finding; no memo, postmortem optional.

## Procedure

Execute in order; every step is a deterministic call, no judgment required beyond severity triage.

### Step 1 — Write the incident record

Call `storage-broker` op=`put`:

```
NAMESPACE: state/incidents
KIND: incident
HUMAN_LEGIBLE: true
ID: <incident_id or omit to auto-generate>
BODY: |
  # Incident <id>

  - **Severity:** <sev1|sev2|sev3>
  - **Opened:** <iso-timestamp>
  - **Detector:** <detector_agent>
  - **Status:** open

  ## Trigger
  <trigger_event verbatim>

  ## Affected
  - Agents: <comma-separated affected_agents>
  - Tasks: <comma-separated affected_tasks>
  - First seen: iteration <first_seen_iteration>

  ## Timeline
  - <iso> — incident opened by <detector_agent>

  ## Context
  <verbatim context block, if supplied>

  ## Follow-up
  - Postmortem: pending
  - Corrective actions: pending
```

Because `kind=incident` is on the broker's reviewable-forced-to-md list, the broker writes Tier-1 markdown regardless of caller preference. Do not attempt to override.

### Step 2 — Append to the incident index

Call `storage-broker` op=`put`:

```
NAMESPACE: state/incidents/index
KIND: generic
BODY_FORMAT: jsonl-append
PAYLOAD:
  incident_id: <id from step 1>
  severity: <sev1|sev2|sev3>
  status: open
  opened_at: <iso>
  detector_agent: <id>
  trigger_summary: <first 120 chars of trigger_event>
  ref: <broker ref from step 1>
```

The index is Tier-2 JSONL, regenerable from the Tier-1 records. It exists so `ops-dashboard` and committee queries can count sev1s without globbing the directory.

### Step 3 — Notify CEO for sev1 and sev2

For `severity in {sev1, sev2}`, call `memo-send`:

```
to: ceo-01
severity: blocker
subject: "Incident <id> opened (<severity>)"
body: |
  <trigger_event>

  Affected: <agents>; tasks: <tasks>
  Record: <broker ref>
  Next: postmortem required (sev1) | recommended (sev2)
```

For sev3, skip the memo. The record and index row are enough; CEO polls the index during reflection cadence.

### Step 4 — Return

Return a receipt with the broker ref and the assigned incident_id. The caller (usually error-recovery or a sub-agent detecting its own invariant violation) uses the id to attach a postmortem later.

## Response shapes

```markdown
## Receipt <REQUEST_ID>
OPERATION: incident-open
STATUS: ok
INCIDENT_ID: <id>
SEVERITY: <sev1|sev2|sev3>
REF: <broker ref — project/.kiho/state/incidents/<id>.md>
INDEX_UPDATED: true
MEMO_SENT: true | false   # true for sev1/sev2, false for sev3
NOTES: <optional — e.g., "auto-assigned id">
```

This skill does not return `ERR`. Failures that occur while opening an incident are themselves recorded as new incidents (the broker retries, the index is append-only, and memo-send degrades to a local dead-letter write). Suppressing an incident-open call because the opening itself hit trouble would recreate the exact class of silent failure this skill exists to eliminate.

## Invariants

- Incident records are committee-reviewable. Tier-1 markdown is enforced by the broker via the `kind=incident` reviewable-forced-to-md rule; callers cannot downgrade.
- Status transitions (`open` → `investigating` → `closed`) mutate the record via `kb-manager`, never via `storage-broker` directly. The broker writes the immutable opening; kb-manager handles the living fields.
- The opening record never blames an agent. The schema has no `responsible_agent` or `at_fault` field. Blame-shaped prose in `trigger_event` is allowed at open time (the detector may not yet know the system cause) but the paired postmortem's blameless linter will reject it on close. Keep open-time text factual: "agent X's iteration N produced error Y" is fine; "agent X failed because it is careless" is not.
- The index row is append-only. Corrections happen via a new row with `status: superseded`, never by rewriting history.

## Non-Goals

- Not a live status page. There is no HTTP endpoint, no dashboard, no push notification. CEO and committees read the index on a cadence; humans read the Tier-1 markdown when asked.
- Not a user-facing announcement. The CEO decides whether a given incident is worth surfacing to the user; this skill only produces the internal artifact.
- Not a retrospective. Retrospectives have wider scope (a whole sprint, a whole skill generation) and different structure. Use `retrospective` for that; use this skill for single, discrete failures.
- Not a debugger. The record captures what happened and who saw it, not a trace. Attach logs via `context` only.

## Grounding

- `skills/core/storage/storage-broker/SKILL.md` — the `put` API, reviewable-forced-to-md rules for `kind=incident`, and namespace conventions.
- `references/react-storage-doctrine.md` — why incidents are Tier-1 and why the index is Tier-2.
- `skills/core/comms/memo-send/SKILL.md` — blocker severity, dead-letter fallback, CEO inbox routing.
- `skills/core/ops/postmortem/SKILL.md` — the paired close-out ceremony; read its blameless linter before writing prose in `trigger_event`.
