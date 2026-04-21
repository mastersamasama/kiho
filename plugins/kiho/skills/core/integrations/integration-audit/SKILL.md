---
name: integration-audit
description: Use this skill periodically — typically at CEO session start — to scan registered integrations for drift. Flags integrations that have not been called in the last N sessions as integration debt, integrations registered without an owner, and unregistered MCPs found in use by scanning telemetry. Does not modify the registry itself — calls integration-register for new discoveries and emits memos to CEO for stale entries. Read-only audit; the CEO decides what to deprecate.
argument-hint: "scan_scope=<project|company> emit_debt=<bool>"
metadata:
  trust-tier: T2
  kiho:
    capability: evaluate
    topic_tags: [infrastructure, governance]
    data_classes: ["integrations-registry"]
---
# integration-audit

Reads the registry, reads telemetry, computes drift. It does not decide; it reports. The CEO deprecates.

## Contents
- [What drift looks like](#what-drift-looks-like)
- [Inputs](#inputs)
- [Procedure](#procedure)
- [Debt row shape](#debt-row-shape)
- [Response shapes](#response-shapes)
- [Invariants](#invariants)
- [Non-Goals](#non-goals)
- [Grounding](#grounding)

## What drift looks like

Three kinds of drift, each a different smell:

1. **Stale registration.** An integration is registered but has not been called in the last `stale_after_sessions` sessions (default 10). It's probably dead code on the trust surface.
2. **Orphaned entry.** An integration has no `owner_agent`, or the listed owner no longer appears in the live org registry. Audit is impossible without a responsible party.
3. **Unregistered use.** Telemetry shows an MCP or CLI was called that has no registry entry. The trust surface is larger than the ledger says.

The first two are recoverable; the CEO may ask the owner to revive or deprecate. The third is a genuine governance failure — someone called a tool kiho never agreed to trust.

## Inputs

```
PAYLOAD:
  scan_scope: project | company  # default: project
  emit_debt: <bool, default true>
  since: <iso-date — limit telemetry scan>  # default: 30 days ago
  stale_after_sessions: <int, default 10>
  include_forbidden: <bool, default false>  # scan for re-registration of forbidden entries
```

## Procedure

1. **Load registry** — `storage-broker.query(namespace="state/integrations/registry", kind="integration")`. Collect all entries into an in-memory dict keyed by `integration_id`.
2. **Load telemetry** — `storage-broker.query(namespace="state/skill-invocations", fts="mcp_|integration_|tool:")` filtered by `ts >= since`. The broker may warm a sqlite FTS cache if the spool is large; this is transparent.
3. **Compare** — for each telemetry row, extract the integration reference (if any) and build a `{integration_id → last_seen_ts, call_count}` map.
4. **Emit findings:**
   - **Stale:** any registry entry whose `last_seen_ts` is older than `stale_after_sessions` session boundaries. Append a debt row per stale entry (if `emit_debt`).
   - **Orphaned:** any registry entry whose `owner_agent` does not resolve in the current org registry, or whose `owner_agent` field is empty. Memo CEO with `severity: action`.
   - **Unregistered use:** any telemetry integration reference with no matching registry entry. Memo CEO with `severity: action` and subject `"Unregistered MCP X called by agent Y"`. Do **not** auto-register; the CEO decides.
   - **Forbidden re-register** (if `include_forbidden`): any entry whose previous incarnation was `trust_level: forbidden`. Memo CEO with `severity: block`.
5. **Return** — audit summary with counts and references. Never mutate the registry itself.

## Debt row shape

Appended to `state/integrations/debt.jsonl` (Tier-2):

```json
{
  "debt_id": "idbt-2026-04-19-0003",
  "ts": "2026-04-19T10:00:00Z",
  "integration_id": "mcp-foo",
  "reason": "stale | orphaned | unregistered | forbidden-reregister",
  "last_seen_ts": "2026-03-02T11:20:00Z",
  "sessions_since": 18,
  "owner_agent": "eng-lead-01",
  "resolved": false,
  "resolved_at": null,
  "resolved_by": null
}
```

Debt is Tier-2 jsonl because it's append-only processing — the audit may write dozens of rows per run, and the committee-reviewable artifact is the CEO memo summarizing them, not the rows themselves.

## Response shapes

```markdown
## Receipt <REQUEST_ID>
OPERATION: integration-audit
STATUS: ok | error
SCAN_SCOPE: project
REGISTRY_SIZE: 14
TELEMETRY_ROWS_SCANNED: 4172
FINDINGS:
  stale: 3
  orphaned: 1
  unregistered: 2
  forbidden_reregister: 0
DEBT_ROWS_APPENDED: 4
MEMOS_EMITTED:
  - {id: memo-..., subject: "Unregistered MCP mcp-foo called by agent eng-lead-01", severity: action}
  - {id: memo-..., subject: "Orphaned integration mcp-legacy", severity: action}
NOTES: <e.g. "sqlite FTS cache warmed at row 1203; served 2827 queries from cache">
```

Empty-findings shape:

```markdown
## Receipt <REQUEST_ID>
OPERATION: integration-audit
STATUS: ok
FINDINGS: {stale: 0, orphaned: 0, unregistered: 0, forbidden_reregister: 0}
NOTES: "Registry clean. Next audit recommended in 7 days."
```

## Invariants

- **Read-only on registry.** This skill never writes to `state/integrations/registry/`. Updates go through `integration-register` (new entries, CEO-driven) or a future deprecate skill.
- **Never auto-deprecate.** Stale entries are flagged as debt; only the CEO signs off on removal. This preserves audit trail.
- **Never auto-register.** Unregistered use is a finding, not a recovery. Silently registering would defeat the point of governance.
- **Session-scope cache only.** Any sqlite FTS cache warmed by the broker is Tier-3, session-bound, evicted at loop end.
- **Scope-respecting.** Project scope audits only project-scope registry + telemetry; company scope aggregates both.

## Non-Goals

- **Not a pen-test.** This skill does not probe integrations for vulnerabilities, check CVEs, or verify signatures. Security review is human work.
- **Not a vendor monitor.** Version drift, upstream deprecation notices, and vendor outage tracking are out of scope.
- **Not a decision maker.** The audit reports; the CEO decides. Never emits a "deprecate now" directive.
- **Not a replacement for design-agent review.** Design-agent prevents misuse prospectively; this skill catches it retrospectively. Both are needed.

## Grounding

- `skills/core/integrations/integration-register/SKILL.md` — the write-side skill this audit complements
- `skills/core/storage/storage-broker/SKILL.md` — backs both registry reads and telemetry FTS
- `skills/core/communication/comms-memo-send/SKILL.md` — memo emission to CEO
- `references/react-storage-doctrine.md` — why registry is Tier-1 md and debt is Tier-2 jsonl
- `references/org-tracking-protocol.md` — owner_agent resolution
- `references/storage-architecture.md` — Tier-2/3 invariants for telemetry scan and cache
- `CLAUDE.md` §Non-Goals — "Not an MCP server"; this audit is the enforcement of that stance
