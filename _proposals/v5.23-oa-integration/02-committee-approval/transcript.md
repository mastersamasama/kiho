---
committee_id: approval-chains-2026-04-23
topic: "How should kiho represent multi-stage conditional approvals without displacing committee deliberation?"
chartered_at: 2026-04-23T14:30:00Z
members:
  - "@kiho-hr-lead"
  - "@kiho-eng-lead"
  - "@kiho-auditor-cost-hawk"
  - "@kiho-auditor-pragmatist"
  - "@kiho-clerk"
quorum: 4
---

## Round 1

### research

- **@kiho-hr-lead** (confidence: 0.85) — Two in-the-wild approval chains exist today: (1) recruit hiring — HR lead convenes, auditors grade, CEO ratifies, user accepts; (2) skill-factory high-risk — eng-lead proposes, auditor grades, CEO accepts per-skill. Both use certificate-marker patterns (`RECRUIT_CERTIFICATE:`) as the terminal gate. Neither has a chain DSL; the sequence is baked into the skill's Procedure prose.
- **@kiho-eng-lead** (confidence: 0.83) — The v5.22 PreToolUse hook for agent.md effectively enforces the last stage of the recruit chain. All earlier stages (role-spec, interview-simulate, committee, rejection-feedback) are checked in the skill's Pre-emit gate section. The pattern works; the only issue is that it's prose, not declarative.
- **@kiho-auditor-cost-hawk** (confidence: 0.72) — If everything is already covered by "skill-internal pre-emit gate + final certificate-marker hook", we don't need a new skill portfolio. That would be feature-factory drift. Burden of proof is on anyone proposing new infrastructure.
- **@kiho-auditor-pragmatist** (confidence: 0.78) — Agreeing with cost-hawk on minimality, but there's a real gap: declaring a new chain today means editing a SKILL.md's Procedure + teaching the PreToolUse hook a new certificate string + possibly editing `bin/hooks/pre_write_*.py`. No single-point-of-truth for "what chains exist and what their stages are." Committee 01 punted the individual-O gate to us precisely because there's no mechanism to add a chain without writing a new Python hook file.
- **@kiho-clerk** (confidence: 0.80) — Format note: any declarative DSL we add MUST be machine-parseable, because the CEO ledger will emit `approval_*` action types referring to chain/stage IDs, and `bin/ceo_behavior_audit.py` needs to verify the stages actually ran. TOML is the house style for declarative config (per v5.19 storage-tech vote). Suggest TOML.

### suggest

- **@kiho-hr-lead** (confidence: 0.85) — Full portfolio: 4 skills — `approval-request`, `approval-route`, `approval-escalate`, `approval-close`. Stages declared in `<skill>/chain.toml` per skill. Central registry at `references/approval-chains.toml` indexes them.
- **@kiho-eng-lead** (confidence: 0.84) — Counter-proposal: minimal extension. ONE new reference file `references/approval-chains.toml` (central, not per-skill) declaring chain names, stages, conditional branches, and the certificate marker each chain emits. Existing `pre_write_agent.py` and `pre_write_kb.py` hooks get refactored to read this TOML and accept any declared certificate for the matching chain. Zero new skills. One new reference file. Two hook scripts get modified (not added).

### challenge

- **@kiho-hr-lead** (confidence: 0.80) — Challenge on eng-lead's proposal: if there are no skills, who "emits" an approval request? How does an agent invoke `approval-request` without a skill?
  > Counter: in today's recruit flow, the HR-lead agent running the `recruit` skill emits stages inline. Under eng-lead's proposal, it would continue to do so — chain.toml is READ by the skill (to know what stages to emit) and by the hook (to verify). The skill is still the emitter.
- **@kiho-auditor-cost-hawk** (confidence: 0.85) — Challenge on HR-lead's proposal (full portfolio): zero new surface is strictly better than 4 new skills if both deliver the same capability. Burden of proof: name a capability the 4-skill portfolio delivers that the TOML-only proposal does not.
  > HR-lead did not name a delta. Challenge stands unresolved going into choose.
- **@kiho-auditor-pragmatist** (confidence: 0.83) — Challenge on both: the individual-O gate from committee 01 needs a NEW chain name, NEW approver role (`dept-lead-for-okr`), and a NEW certificate marker. Either proposal handles this, but the acceptance test is: can a reader add chain X by writing ≤ 20 lines of TOML, with NO Python changes?
  > Under eng-lead's proposal: YES if the hooks are chain-agnostic (they read the TOML for the marker list). Under HR-lead's proposal: YES (add row to chain.toml in the relevant skill dir). Both pass. But HR-lead's 4-skill overhead remains unjustified.

### choose

- **@kiho-hr-lead** (confidence: 0.75) — Concede on scope. Adopt eng-lead's minimal extension: TOML-only, no new skills. Withdrawing the 4-skill proposal.
- **@kiho-eng-lead** (confidence: 0.85) — Minimal extension: `references/approval-chains.toml` + chain-agnostic hook refactor + chain-lookup helper `bin/approval_chain.py`. Zero new skills.
- **@kiho-auditor-cost-hawk** (confidence: 0.88) — Minimal extension. No new skills. Agreed.
- **@kiho-auditor-pragmatist** (confidence: 0.82) — Minimal extension. Agreed, contingent on the ≤ 20 lines of TOML test.
- **@kiho-clerk** (confidence: 0.80) — Minimal extension. TOML schema needs to be documented inside the chain-lookup helper's reference file so audit script can reuse. Agreed.

Unanimous position. Aggregate = mean(0.75, 0.85, 0.88, 0.82, 0.80) = **0.820** < 0.90. No unresolved challenges. NOT closed (floor failure). Round 2 focuses on raising confidence by specifying the TOML schema + worked examples.

## Round 2

### research

- **@kiho-eng-lead** (confidence: 0.92) — Concrete TOML schema:
  > `[[chain]]` blocks with fields `id`, `certificate_marker`, `stages = [{stage_id, approver_role, prerequisites, on_deny}]`, `conditional_branches = [{if_field, if_op, if_value, goto_stage}]`. Three worked examples written: recruit-hiring (existing), skill-factory-high-risk (existing), okr-individual (new, from committee 01).
- **@kiho-hr-lead** (confidence: 0.88) — Ran the ≤ 20 lines test on okr-individual chain: 14 lines TOML. Passes. Refactor of existing recruit chain: 22 lines TOML replacing ~60 lines of prose in SKILL.md. Net win on brevity.

### suggest

- **@kiho-eng-lead** (confidence: 0.92) — Adopt the schema. Deliverables: (1) `plugins/kiho/references/approval-chains.toml` with 3 chain definitions at ship time; (2) `plugins/kiho/bin/approval_chain.py` reader + validator; (3) refactor `pre_write_agent.py` and `pre_write_kb.py` to consult the TOML for certificate markers; (4) new ledger action types `approval_stage_entered`, `approval_stage_granted`, `approval_stage_denied`, `approval_chain_closed`; (5) update `bin/ceo_behavior_audit.py` to verify that all stages of a declared chain ran before the terminal certificate was emitted.

### challenge

- **@kiho-auditor-pragmatist** (confidence: 0.88) — Does this preserve CLAUDE.md's invariant "only CEO calls AskUserQuestion"? A chain's final stage may be "user approval". Under this design, who invokes the user gate?
  > Resolved: the chain-lookup helper does NOT invoke AskUserQuestion. When a stage's approver_role is `user`, the skill-internal Pre-emit gate emits `status: pre_emit_gate_needs_user`, returning control to the CEO. CEO then invokes AskUserQuestion as usual. The chain infrastructure stays sub-main. Invariant preserved.

### choose

- **@kiho-hr-lead** (confidence: 0.92) — Adopt minimal extension + TOML schema + 4 artifacts + audit extension + user-stage bubble-up.
- **@kiho-eng-lead** (confidence: 0.93) — Same.
- **@kiho-auditor-cost-hawk** (confidence: 0.90) — Same. Still the same zero-new-skills budget.
- **@kiho-auditor-pragmatist** (confidence: 0.92) — Same.
- **@kiho-clerk** (confidence: 0.90) — Same. Transcript format confirmed compatible with new ledger action types.

Aggregate = mean(0.92, 0.93, 0.90, 0.92, 0.90) = **0.914** ≥ 0.90. Unanimous. No unresolved challenges. **CLOSE.**

## Close

- outcome: unanimous
- final_confidence: 0.91
- rounds_used: 2
- decision: "Minimal extension — one new reference TOML (`references/approval-chains.toml`), one new helper script (`bin/approval_chain.py`), refactor of two existing hook scripts to be chain-agnostic, 4 new ledger action types, and audit-script extension. ZERO new skills. User-stage bubbles to CEO per existing AskUserQuestion invariant."
