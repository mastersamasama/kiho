---
name: integration-register
description: Use this skill when a new MCP server, native tool, or CLI integration is detected in the environment and needs to be registered for kiho-wide consumption. Records integration type, available tools, owner agent responsible for its use, trust level based on vendor and deployment context, auth mode, and failure mode. Writes to the Tier-1 integrations registry so committees can audit the trust surface. Blocks the sub-agent from silently calling unregistered MCP tools by surfacing the gap in design-agent when workflows propose MCP use. Pairs with integration-audit which periodically scans for drift.
argument-hint: "integration_id=<id> type=<mcp|native|cli>"
metadata:
  trust-tier: T2
  kiho:
    capability: create
    topic_tags: [infrastructure, governance]
    data_classes: ["integrations-registry"]
---
# integration-register

Every external tool kiho can call is an implicit trust decision. This skill makes it explicit by writing a reviewable registry entry per integration.

## Contents
- [Why a registry](#why-a-registry)
- [Inputs](#inputs)
- [Procedure](#procedure)
- [Registry entry shape](#registry-entry-shape)
- [Trust levels](#trust-levels)
- [Response shapes](#response-shapes)
- [Invariants](#invariants)
- [Non-Goals](#non-goals)
- [Grounding](#grounding)

## Why a registry

kiho is explicitly not an MCP server — but it **consumes** MCPs (Playwright, Chrome DevTools, deepwiki, etc.) and occasional native/CLI integrations. Without a registry, the trust surface is "whatever MCPs happen to be running." That is not auditable: a committee cannot review what it cannot enumerate, and the `design-agent` cannot flag a workflow that proposes MCP use if it has no list of known MCPs to check against.

The registry is a **single Tier-1 markdown collection** with one entry per integration. It's a ledger, not a dispatcher — nothing actually runs from here. The value is that every committee member, `design-agent`, and `integration-audit` reads from the same ground truth.

## Inputs

```
PAYLOAD:
  integration_id: <slug, e.g. "mcp-playwright", "cli-gh">
  type: mcp | native | cli
  display_name: <human name, e.g. "Playwright MCP">
  tools: [<tool_name_1>, <tool_name_2>, ...]
  owner_agent: <agent_id responsible for correct use>
  trust_level: vendor-official | community-vetted | unverified | forbidden
  auth_mode: none | env-var | oauth | interactive | inherited
  failure_mode: soft | hard | escalate
  notes: <optional free text — deployment caveats, known quirks>
```

All fields are required except `notes`. An integration with no `owner_agent` cannot be registered — orphan integrations are the smell `integration-audit` later flags.

## Procedure

1. **Validate** — confirm `integration_id` is kebab-case, `type` is in the enum, `tools` is non-empty, `owner_agent` resolves in the live org registry. Reject with `status: invalid_input` on any miss.
2. **Dedup check** — query the registry for an existing entry with the same `integration_id`. If present, refuse with `status: already_registered` and point the caller at `integration-update` (future skill) or manual edit via CEO.
3. **Persist** — call:
   ```
   storage-broker.put(
     namespace="state/integrations/registry",
     kind="integration",
     human_legible=True,
     body=<entry markdown>
   )
   ```
   Broker forces Tier-1 md (`integration` is on the reviewable-kind list per `react-storage-doctrine.md`).
4. **Cross-ref debt** — append a row to `state/integrations/debt.jsonl` with `status: unused` and `last_seen_ts: null`. `integration-audit` clears this row when the first telemetry event shows the integration in use.
5. **Memo** — emit a memo to `ceo-01` with `severity: info` summarizing the new integration and its trust level.

## Registry entry shape

One markdown file per integration: `<company|project>/.kiho/state/integrations/registry/<integration_id>.md`.

```markdown
---
integration_id: mcp-playwright
type: mcp
display_name: Playwright MCP
owner_agent: eng-lead-01
trust_level: vendor-official
auth_mode: env-var
failure_mode: soft
registered_at: 2026-04-19T10:00:00Z
registered_by: ceo-01
tools:
  - browser_navigate
  - browser_click
  - browser_snapshot
---
# Playwright MCP

## Purpose
Browser automation for testing and screenshot-driven debugging.

## Trust rationale
Vendor-official: published by Microsoft under the MCP spec. Source on GitHub, signed releases.

## Auth
Reads `PLAYWRIGHT_BROWSERS_PATH` from env.

## Failure mode
Soft — a Playwright failure degrades the task (no screenshot) but does not block the loop.

## Notes
<optional caveats>
```

## Trust levels

- **vendor-official** — published by the tool's vendor with verifiable provenance (signed releases, official repo). Highest trust; committees may approve without additional scrutiny.
- **community-vetted** — maintained by a named community with ≥ 3 known-good deployments within kiho. Committee review required before first use on company scope.
- **unverified** — unknown provenance or < 3 known-good deployments. Project scope only; CEO ruling required per invocation.
- **forbidden** — explicitly banned by past committee ruling. Registering does not re-enable; the entry exists so future agents see the deny-list reason.

Trust level is never auto-computed. The caller supplies it; `integration-audit` flags mismatches.

## Response shapes

```markdown
## Receipt <REQUEST_ID>
OPERATION: integration-register
STATUS: ok | already_registered | invalid_input | error
INTEGRATION_ID: mcp-playwright
REGISTRY_PATH: .kiho/state/integrations/registry/mcp-playwright.md
DEBT_ROW_ID: idbt-2026-04-19-0001
MEMO_ID: <memo-id>
NOTES: <e.g. "trust_level=unverified — project scope only">
```

Rejection shape:

```markdown
## Receipt <REQUEST_ID>
OPERATION: integration-register
STATUS: invalid_input
REASON: owner_agent "eng-ghost-99" not in live org registry
HINT: Register the owner agent first or choose an existing one.
```

## Invariants

- **Registry is Tier-1 md.** Reviewable-kind guardrail; broker refuses any other tier.
- **Owner is required.** No integration without a named owner agent — the owner is accountable for misuse, deprecation, and audit responses.
- **Never auto-trust.** The caller provides `trust_level`; the skill does no inference. Silent promotion is a known anti-pattern.
- **Register-only.** This skill creates entries. Updates require a separate skill or CEO edit; deletion is `integration-deprecate` (future).
- **Scope-aware paths.** Project scope writes under `<project>/.kiho/`; company scope under `$COMPANY_ROOT/`. Scope is inferred from the caller's `scope` field at invocation.

## Non-Goals

- **Not a credential store.** `auth_mode: env-var` records the shape, not the secret. Secrets stay in the environment.
- **Not an MCP launcher.** kiho does not start or daemonize MCPs; the environment provides them. This skill only records their existence.
- **Not a runtime gate.** Registration does not prevent a rogue agent from calling an MCP; it only makes the trust surface auditable. Prevention is `design-agent`'s job.
- **Not a version tracker.** Version drift is out of scope here; `integration-audit` may flag drift but version management belongs to the owner agent's playbook.

## Grounding

- `CLAUDE.md` §Non-Goals — "Not an MCP server"
- `references/react-storage-doctrine.md` — reviewable-kind guardrail
- `references/storage-architecture.md` — Tier-1 canonical registry
- `references/org-tracking-protocol.md` — live org registry (owner_agent resolution)
- `skills/core/integrations/integration-audit/SKILL.md` — periodic drift scan
- `skills/core/communication/comms-memo-send/SKILL.md` — memo emission
