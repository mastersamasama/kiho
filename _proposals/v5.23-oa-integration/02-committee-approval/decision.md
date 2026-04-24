# Decision — multi-stage approval chains (committee approval-chains-2026-04-23)

## Status

Accepted by unanimous close at aggregate confidence 0.91, 2 rounds.

## Context

DingTalk-style sequential approval chains (form → dept lead → finance → CEO, amount-threshold routing) have no direct kiho analog today. Two chains exist in the wild but are encoded as prose inside skill Procedures: (1) recruit hiring (HR-lead + auditors + CEO) and (2) skill-factory high-risk (eng-lead + auditor + CEO). Committee 01 (OKR) created a third requirement (individual-OKR approval by dept-lead). Without a declarative representation, every new chain requires Python hook changes.

## Decision

**Adopt the minimal extension.** Zero new skills. Five concrete deliverables:

### 1. `plugins/kiho/references/approval-chains.toml`

Central, declarative registry of all approval chains. Schema:

```toml
[[chain]]
id = "recruit-hiring"
certificate_marker = "RECRUIT_CERTIFICATE:"
description = "HR-lead convenes + auditors grade + CEO ratifies + user accepts"

  [[chain.stages]]
  stage_id = "role-spec"
  approver_role = "kiho-recruiter"
  prerequisites = ["role-spec file exists under _meta-runtime/role-specs/"]
  on_deny = "abort"

  [[chain.stages]]
  stage_id = "interview-simulate"
  approver_role = "kiho-recruiter"
  prerequisites = ["_meta-runtime/interview-runs/<role>/ exists"]
  on_deny = "abort"

  [[chain.stages]]
  stage_id = "hiring-committee"
  approver_role = "kiho-hr-lead"
  prerequisites = ["_meta-runtime/hiring-committees/<id>/decision.md closed unanimous"]
  on_deny = "rejection-feedback"

  [[chain.stages]]
  stage_id = "ceo-ratify"
  approver_role = "kiho-ceo"
  prerequisites = []
  on_deny = "abort"

  [[chain.stages]]
  stage_id = "user-accept"
  approver_role = "user"
  prerequisites = []
  on_deny = "rejection-feedback"
```

Three chain definitions ship in v5.23: `recruit-hiring`, `skill-factory-high-risk`, `okr-individual`. Adding a new chain is ≤ 20 lines of TOML with zero Python changes.

### 2. `plugins/kiho/bin/approval_chain.py`

Stdlib-only helper exposing:

- `load_chain(chain_id) -> Chain` — reads TOML, validates schema.
- `list_certificate_markers() -> list[str]` — used by hooks to know which markers authorize writes.
- `verify_ran(chain_id, ledger_path) -> bool` — scans ledger for `approval_stage_*` entries proving every stage executed.
- `next_stage(chain_id, current_stage, context) -> Stage | None` — applies conditional_branches evaluation.

CLI entry: `python bin/approval_chain.py --validate` for CI.

### 3. Refactor of `pre_write_agent.py` and `pre_write_kb.py`

Currently hard-coded to one certificate marker each. After refactor: consult `approval_chain.list_certificate_markers()`; accept any declared marker whose chain terminates at a matching file path regex. Backwards-compatible — existing `RECRUIT_CERTIFICATE:` and `KB_MANAGER_CERTIFICATE:` stay functional, just now sourced from TOML.

### 4. Four new ledger action types

- `approval_stage_entered` — payload: `{chain_id, stage_id, approver_role, approver_agent}`
- `approval_stage_granted` — payload: `{chain_id, stage_id, reason_citation}`
- `approval_stage_denied` — payload: `{chain_id, stage_id, denial_reason, on_deny_action}`
- `approval_chain_closed` — payload: `{chain_id, outcome: granted | denied | aborted, rounds_used}`

### 5. Extend `bin/ceo_behavior_audit.py`

New drift class `approval_chain_skipped`: a `RECRUIT_CERTIFICATE:`-bearing agent.md write WITHOUT the corresponding sequence of `approval_stage_*` entries in the ledger is a CRITICAL drift. Exit code 3. This catches forged certificates and skipped stages at DONE self-audit.

**User-stage bubble-up**: When a chain stage has `approver_role = "user"`, the skill invoking the chain emits `status: pre_emit_gate_needs_user` and returns. The CEO then invokes `AskUserQuestion` as usual. This preserves the CLAUDE.md invariant that only the CEO in main conversation calls `AskUserQuestion` — the chain infrastructure never does.

**Committee 01 dependency discharged**: individual-O creation now has a first-class mechanism. `okr-set` with `okr_level: individual` invokes `approval_chain.load_chain("okr-individual")`, which in turn requires a `DEPT_LEAD_OKR_CERTIFICATE:` in the target file after the dept-lead approval stage. No Python changes needed from committee 01 onward.

## Consequences

### Positive

- Declarative registry replaces prose-in-SKILL.md encoding of chains.
- Adding a new chain = ≤ 20 lines TOML, 0 Python changes.
- Existing chains (recruit, skill-factory) gain a clean migration path; behavior preserved.
- Audit surface improved — `ceo_behavior_audit.py` now catches chain-stage skips, not just agent.md write drift.
- CLAUDE.md invariants preserved (CEO-only user interaction).

### Negative

- Refactor of `pre_write_agent.py` and `pre_write_kb.py` risks regression of existing v5.22 hook behavior — migration requires replay-harness coverage of both chains.
- Four new ledger action types means `ceo_behavior_audit.py` changes; pre-v5.23 ledgers without these entries must be skipped via `--since-epoch v5.23_active` flag (mirrors v5.22 epoch-marker pattern).
- Chain TOML is a new config surface to misedit; the `--validate` CLI is mandatory pre-commit.

## Alternatives considered and rejected

- **Full 4-skill portfolio** (`approval-request`, `approval-route`, `approval-escalate`, `approval-close`) — rejected by auditor-cost-hawk as unjustified new surface; HR-lead could not name a capability delta over the TOML-only approach.
- **Per-skill `chain.toml` sidecar** — rejected as harder to audit globally; central registry is reviewer-friendly.
- **Extending the committee skill with a sequential flavor** — rejected because committee = deliberative convergence; approval chain = sequential binary sign-offs. Different phase of decision lifecycle; merging them would muddy both.
- **No change; leave encoding in SKILL.md prose** — rejected because adding the okr-individual chain would require duplicating the ~60 lines of recruit-chain prose in a third location, and committee 01's needs would still require hook edits.

## Scope estimate

- 1 new reference TOML (~150 lines for 3 chains + schema docs)
- 1 new helper script (~200 lines Python stdlib)
- 2 hook-script refactors (~50 line change each)
- 1 audit-script extension (~80 lines for the new drift class)
- 4 new ledger action types (documented in ledger schema; 0 code change to emit — skills emit them directly)
- Estimated implementation: ~4–6 hours

## Dependencies

- v5.22 PreToolUse hook infrastructure (shipped — baseline).
- Committee 01 (OKR) — consumer; the `okr-individual` chain definition ships under this committee's work.
- Replay harness (v5.22 shipped) — needs new scenario `session-approval-chain-replay.md` covering recruit + skill-factory + okr-individual.

## Next concrete step

An implementation plan authorizes: (1) authoring `approval-chains.toml` with the 3 chain definitions, (2) Python scaffolding of `bin/approval_chain.py` with unit tests, (3) refactor of the 2 hook scripts with backwards-compatibility tests, (4) audit-script drift-class addition with unit tests, (5) replay-harness scenario addition, (6) recruit SKILL.md prose trimming to cite the TOML rather than restate the chain.
