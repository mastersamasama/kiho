---
committee_id: broadcast-announcements-2026-04-23
topic: "How should kiho represent company-wide announcements, beyond peer-to-peer memo-send?"
chartered_at: 2026-04-23T15:00:00Z
members:
  - "@kiho-comms"
  - "@kiho-kb-manager"
  - "@kiho-hr-lead"
  - "@kiho-auditor-overlap-hunter"
quorum: 3
---

## Round 1

### research

- **@kiho-auditor-overlap-hunter** (confidence: 0.88) — Mapped the existing surfaces. `memo-send` takes a single recipient agent id. `help-wanted` broadcasts a capability-filtered request expecting one responder (not many readers). `shift-handoff` re-surfaces outstanding memos at turn boundary. `memo-inbox-read` is comms' CEO-INITIALIZE sweep. No surface today supports "publish once, every agent matching filter reads, pinned until expiry, optional acknowledgement tracking". Gap is real but narrow.
- **@kiho-comms** (confidence: 0.85) — Use cases: (a) CEO announcing a new invariant (e.g., "v5.22 hooks live"); (b) kb-manager announcing a KB conflict resolution that changes existing KRs; (c) HR-lead announcing an org change (new role, promotion, termination). All three work today via N peer-to-peer `memo-send` calls, but the N-at-once emission is inefficient and misses the "pinned" + "acknowledgement" semantics.
- **@kiho-hr-lead** (confidence: 0.80) — Acknowledgement tracking matters for policy-bearing announcements (e.g., a values-alignment-audit outcome that changes rules). Without tracking, compliance check at next retro is impossible.
- **@kiho-kb-manager** (confidence: 0.82) — A pinned announcement that outlives a turn is KB-adjacent. Proposal: announcements live at `.kiho/state/announcements/<yyyy-mm-dd>-<slug>.md` Tier-1 with YAML frontmatter (`id`, `emitter`, `audience`, `pinned_until`, `ack_required`, `ack_by`). KB-wiki promotion of the durable-invariant announcements to `rules.md` happens via existing kb-add pipeline when a dept-lead confirms the invariant is policy.

### suggest

- **@kiho-comms** (confidence: 0.88) — **Minimal extension**: (1) `memo-send` gains wildcard recipient support (`@all`, `@dept:engineering`, `@capability:create-skill`) with capability-matrix lookup; (2) new `.kiho/state/announcements/` directory with Tier-1 pinned records per kb-manager's proposal; (3) `shift-handoff` re-surfaces unread pinned announcements per-agent; (4) new ledger action `announcement_published` + `announcement_acknowledged`; (5) NO new skill.

### challenge

- **@kiho-auditor-overlap-hunter** (confidence: 0.82) — Challenge: if `memo-send @all` already works, do we need the `announcements/` directory at all? Can't we just set a `pinned: true` frontmatter on the memo itself and have shift-handoff re-surface any pinned unread memo?
  > Resolved: pinned memos would pollute individual inbox files. Separate `announcements/` directory keeps the mailbox vs bulletin-board distinction clean. Also enables kb-manager to promote invariant-bearing announcements to `rules.md` without walking every agent's inbox.
- **@kiho-hr-lead** (confidence: 0.80) — Challenge: acknowledgement tracking semantics. If 30 agents receive, who closes the loop? Is it a blocking operation?
  > Resolved: non-blocking. `ack_required: true` means agents acknowledge via `memo-inbox-read` ceremony; the announcement tracks which @agent-ids have acked in its `ack_by` list. Retrospective skill reads unresolved acks as a metric. No hard gate on non-ack; it's a visibility mechanism, not an enforcement one.
- **@kiho-kb-manager** (confidence: 0.83) — Challenge: who may emit an announcement? An all-agents broadcast from a low-trust IC agent would be noise abuse.
  > Resolved: emission restricted to (a) CEO (main conversation), (b) any dept-lead (hr-lead, eng-lead, pm-lead, kb-manager, comms), (c) other agents ONLY if they cite a closed committee decision in the announcement frontmatter (`basis: committees/<id>/decision.md`). No PreToolUse hook needed — enforcement is in the `memo-send` skill's pre-emit check.

### choose

- **@kiho-comms** (confidence: 0.92) — Adopt minimal extension: wildcard memo-send + announcements/ directory + shift-handoff resurface + 2 ledger actions + emission RACI. Zero new skills.
- **@kiho-kb-manager** (confidence: 0.90) — Same.
- **@kiho-hr-lead** (confidence: 0.90) — Same, with non-blocking ack semantics confirmed.
- **@kiho-auditor-overlap-hunter** (confidence: 0.92) — Same. Overlap concern dissolved — the announcements/ directory is a legitimately distinct surface.

Aggregate = mean(0.92, 0.90, 0.90, 0.92) = **0.910** ≥ 0.90. Unanimous. No unresolved challenges. **CLOSE.**

## Close

- outcome: unanimous
- final_confidence: 0.91
- rounds_used: 1
- decision: "Minimal extension — add wildcard recipient support to memo-send, create Tier-1 `.kiho/state/announcements/` directory with YAML-frontmatter pinned records, extend shift-handoff to re-surface unread pinned announcements, add 2 ledger action types (announcement_published + announcement_acknowledged), restrict emission to CEO / dept-leads / committee-basis-citing agents. ZERO new skills."
