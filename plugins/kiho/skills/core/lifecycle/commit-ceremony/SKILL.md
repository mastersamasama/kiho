---
name: commit-ceremony
description: Use this skill as the generalised observer→pending→commit→broadcast engine shared by soul-apply-override, skill-improve, skill-sunset-announce, and any future lifecycle mutation that follows the same pattern. Caller declares the target canonical artifact, the pending-entry namespace, the coherence-validator skill to invoke, the broadcast targets, the auth policy, and the rate limit; commit-ceremony drains the pending queue via storage-broker, validates each entry, applies merges, writes a canonical evolution row, dispatches broadcasts, and marks entries applied. Domain-specific merge logic and section auth rules stay with the caller — commit-ceremony never interprets payloads. This is the skill that removed the three-way reimplementation of the same ceremony across soul / skill / sunset lifecycles.
argument-hint: "target_canonical_ref=<ref> pending_namespace=<ns> coherence_validator=<skill>"
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: active
  kiho:
    capability: orchestrate
    topic_tags: [lifecycle, governance]
    data_classes: ["commit-ceremony-pending"]
---
# commit-ceremony

The shared lifecycle commit engine. Pre-v5.20 three _meta skills each re-implemented the same five-beat ceremony — drain pending, validate, merge, broadcast, audit — with divergent storage, schema, and error handling. This skill extracts the common bones; callers plug in the domain logic.

## Why a ceremony engine

The observer→pending→commit→broadcast pattern appears everywhere in kiho's self-modification surface:

| caller | observer | pending | commit | broadcast |
|---|---|---|---|---|
| soul-apply-override | memory-reflect | soul-overrides queue | agent.md | org-sync + kb-update + cross-agent-learn |
| skill-improve | evolution-scan | proposed diff | SKILL.md | kb-add + catalog-gen |
| skill-sunset-announce | skill-deprecate | deprecation record | announcement.md | fan-out memos + capability-matrix |

Each ceremony has two failure modes: mid-merge crash (some entries applied, some not) and broadcast partial failure (agent.md written, kb-update failed). Before this skill, each caller reimplemented rollback and idempotency. Now they declare inputs and this skill owns the atomicity envelope.

## Inputs

```
PAYLOAD:
  target_canonical_ref:       <storage-broker Ref OR fs path to T1 md to mutate>
  pending_namespace:           <broker jsonl namespace holding pending entries>
  pending_filter:              <optional dict; default {status: "pending"}>
  coherence_validator:         <skill name, e.g. "soul-validate">
  validator_input_builder:     <caller-provided function name OR inline template
                                for building the validator's input from the
                                merged candidate state>
  broadcast_targets:            [<skill name>, ...]  # applied in order; partial failure logged, not fatal
  authorized_by:                <caller slug>
  auth_policy:                  <dict mapping section → required-role>
                                <caller-specific; this skill only passes through>
  rate_limit:                   <int; default 3>
  evolution_kind:               <string; default "evolution">
  evolution_skill_id_template: <template like "<agent_id>-soul" or "<skill-slug>">
  merge_fn:                     <caller-provided merge function name>
                                <this skill calls it with (current_state, entry)
                                and gets back new_state; never interprets payload>
  dry_run:                      <bool; default false>
```

Callers that don't yet have the validator/merge/broadcast surfaces broken out can pass inline lambdas; the skill body shows the preferred "named skill/function" form because it keeps the audit trail clean.

## Procedure

1. **Load current state** — read `target_canonical_ref` content. If the path doesn't exist, caller must pre-create it or fail.

2. **Drain pending** — call `storage-broker` op=query, `namespace=<pending_namespace>`, `where=<pending_filter>`, `order_by="created_at asc"`, `limit=<rate_limit>`. If zero rows, return `{status: "ok", applied: 0}` immediately.

3. **Auth gate** — for each entry, consult `auth_policy[entry.section]` to determine required role. Reject any entry whose `authorized_by` doesn't meet the requirement. Never escalate silently; return `status=error` with the first failing entry.

4. **Candidate merge** — for each entry (in queue order) call `merge_fn(current_state, entry)` → `new_state`. Accumulate applied entries; if `merge_fn` raises, roll back all pending-turn merges, leave pending queue untouched, return `status=error`.

5. **Coherence validate** — build validator input via `validator_input_builder(new_state)`, call the `coherence_validator` skill with `mode=strict`. If validator returns `status=error`, roll back all merges, leave pending queue untouched, return the validator's issue list verbatim.

6. **Write canonical** — persist `new_state` to `target_canonical_ref`. For `dry_run=true`, skip and return the diff.

7. **Write evolution row** — call `storage-broker` op=put, `namespace="state/evolution/history"`, `kind=<evolution_kind>`, payload includes `skill_id` (per template), `action`, `before_version`, `after_version`, `applied_entry_ids`, `authorized_by`, `rationale_summary`, `validator_verdict`. Single row per ceremony run, regardless of how many entries applied.

8. **Broadcast** — call each skill in `broadcast_targets` in order. Failures are logged into the evolution row's `broadcast_failures` field and surfaced in the response; they do NOT roll back the canonical write (the canonical write is the commit point). Caller decides whether a broadcast failure warrants retry.

9. **Mark applied** — for each applied entry call `storage-broker` op=put to the same `pending_namespace` with `status="applied"` and `applied_at` timestamp. Broker's supersedes chain keeps the queue scan semantics intact.

10. **Return** — `{status, applied_count, skipped_count, evolution_ref, broadcast_results}`.

## Rate-limit semantics

`rate_limit` is a **per-ceremony cap**, not a per-turn cap. A caller invoking commit-ceremony three times in one turn will drain at most `3 × rate_limit` entries. If a true per-turn cap is needed, the caller enforces it (by tracking ceremony invocations in its own state). Default 3 was chosen to match the soul-apply-override anti-pattern "At most 3 overrides may be applied per turn" — soul-apply-override inherits this default when it delegates.

## Response shape

```json
{
  "status": "ok | error | dry_run",
  "applied_count": 2,
  "skipped_count": 0,
  "evolution_ref": {"tier": "jsonl", "namespace": "state/evolution/history", "key": "..."},
  "broadcast_results": [
    {"skill": "org-sync", "status": "ok"},
    {"skill": "kb-update", "status": "error", "detail": "..."}
  ],
  "applied_entry_ids": ["ov-2026-04-19-0001", "ov-2026-04-19-0002"],
  "rolled_back": false
}
```

On `status=error` from auth/merge/validate failures, `rolled_back: true`, no canonical mutation, no evolution row, no broadcasts.

## Invariants

- **Canonical-write is the commit point.** Broadcast failures do NOT roll back; evolution row is written before broadcasts so the ceremony has auditable provenance even if downstream propagation fails.
- **Pure delegation.** This skill never parses payload semantics. It calls caller-supplied `merge_fn` / `validator_input_builder` for anything domain-specific.
- **Rate-limit structural.** The broker `limit` parameter enforces it at the query; no skill-body counter required.
- **Idempotent applied-marking.** Re-running a ceremony that previously succeeded is a no-op — applied entries are filtered out by `pending_filter`.
- **Read-then-write atomicity**. The canonical read in Step 1 and the canonical write in Step 6 are separated by validator calls; callers MUST ensure no other process mutates `target_canonical_ref` between these steps. Because kiho runs one CEO per turn, this holds in practice.

## Non-Goals

- **Not a transaction manager.** No two-phase commit across broker + target canonical + broadcasts. Best-effort with explicit commit point.
- **Not a scheduler.** Caller decides when to invoke; this skill drains once per call.
- **Not a payload interpreter.** Whether an entry targets `red_lines` or `Big Five Openness` or a SKILL.md section is opaque here. Caller's merge_fn and auth_policy encode that knowledge.
- **Not a notification service.** Broadcast targets are other skills (`memo-send`, `org-sync`, `kb-update`, etc.); this skill does not directly emit user-visible signals.
- **Not a replacement for domain skills.** soul-apply-override / skill-improve / skill-sunset-announce remain thin wrappers that declare the ceremony shape; they don't disappear.

## Example invocation (soul-apply-override flow)

```yaml
op: put
target_canonical_ref: {tier: md, namespace: agents, key: eng-lead-01}
pending_namespace: state/agents/eng-lead-01/soul-overrides
coherence_validator: soul-validate
validator_input_builder: parse_soul_md_to_dict
broadcast_targets: [org-sync, kb-update, memory-cross-agent-learn]
authorized_by: ceo-01
auth_policy:
  red_lines: ceo
  values: hr-lead
  goals: hr-lead
  personality: hr-lead
rate_limit: 3
evolution_kind: evolution
evolution_skill_id_template: "<agent_id>-soul"
merge_fn: soul_section_merge    # caller-owned; knows add/replace/rerank semantics
```

## Future callers (migration candidates)

- `skills/_meta/soul-apply-override/` — Step E (FIX 3) rewires to delegate here.
- `skills/_meta/skill-improve/` — Apply + Register phases could delegate (with SKILL.md as target_canonical_ref, skill-validate-ish validator, broadcast to [kb-add, catalog-gen]).
- `skills/_meta/skill-sunset-announce/` — broadcast phase maps cleanly onto commit-ceremony's broadcast_targets.
- These migrations are deferred; this skill's existence does NOT force a rewrite — each caller migrates on next `skill-improve` touch.

## Grounding

- `skills/core/storage/storage-broker/SKILL.md` — the put/query/evict API this skill delegates to
- `skills/_meta/soul-validate/SKILL.md` — the default coherence validator for soul ceremonies
- `references/react-storage-doctrine.md` — tier selection semantics
- `bin/kiho_frontmatter.py KIND_SCHEMAS["evolution"]` — audit row shape
