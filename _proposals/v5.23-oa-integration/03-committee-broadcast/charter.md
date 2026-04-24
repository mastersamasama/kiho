# Charter — company-wide broadcast committee

## Committee identity

- **committee_id:** `broadcast-announcements-2026-04-23`
- **topic:** "How should kiho represent company-wide announcements, beyond peer-to-peer memo-send?"
- **chartered_at:** 2026-04-23T15:00:00Z
- **reversibility:** reversible
- **knowledge_update:** true

## Members (quorum 3 of 4)

- **@kiho-comms** — owner of all cross-departmental communication (memo routing, shift-handoff, help-wanted broadcasts)
- **@kiho-kb-manager** — because a pinned announcement that outlives a turn is KB-adjacent state
- **@kiho-hr-lead** — announcements often carry policy / org-change content; HR owns that content
- **@kiho-auditor-overlap-hunter** — persona whose job is specifically to catch "this is already what X does"

Clerk: auto-assigned. Not a member.

## Input context

- User gap: Lark pinned announcements + all-employee broadcast vs kiho's peer-to-peer `memo-send`.
- Gap score from `00-gap-analysis.md` §matrix row 3: **MEDIUM** — new skill plausible; overlap with shift-handoff to watch.
- The overlap risk is high: `memo-send`, `memo-inbox-read`, `help-wanted`, and `shift-handoff` already cover announcement-adjacent surfaces.

## Questions the committee MUST answer

| # | Question | Why it matters |
|---|---|---|
| Q1 | **Is there a meaningful capability gap today?** Can `memo-send` with a wildcard recipient, plus the `memo-inbox-read` sweep already done by `kiho-comms`, cover "broadcast"? | Overlap-hunter's primary concern |
| Q2 | **If yes: storage location** — new `announcements/` directory under `.kiho/state/`? Append to `org-registry.md`? New KB wiki page type? | Must pick a tier + gatekeeper consistent with data-storage-matrix |
| Q3 | **Subscription/filter model** — all agents? By capability (capability-matrix query)? By department? | Determines how `memo-inbox-read` routes broadcasts |
| Q4 | **Pin + expire semantics** — does an announcement auto-delete after a TTL? Does it require manual unpin? Does shift-handoff re-surface unread pins? | Without expiry, `announcements/` grows unbounded |
| Q5 | **Acknowledgement tracking** — does the broadcast require each recipient to acknowledge? How is that stored? | Required for policy-bearing announcements; optional for informational |
| Q6 | **Who may emit a broadcast?** CEO only? CEO + department leads? Any agent with a committee decision behind it? | RACI question; overlap with `values-flag` for broadcast-worthy values escalations |

## Success criteria

Unanimous position that either:

- **Endorses extension** — specifies new skill ID (likely `memo-broadcast` or `announce-publish`) + storage location + subscription model + pin/expire rules + emission RACI, OR
- **Endorses rejection** — argues that existing `memo-send` + `memo-inbox-read` + `shift-handoff` cover the workload, with a worked example (e.g., "CEO wants all agents to know that v5.22 hooks are live — this fits `memo-send` with recipient=`all` + one-line addition to `shift-handoff` re-surface rules, no new skill needed").

Either outcome is acceptable if it closes unanimously at ≥ 0.90.

## Constraints + references

- `plugins/kiho/skills/core/communication/memo-send/SKILL.md` — existing peer-to-peer protocol.
- `plugins/kiho/skills/core/communication/memo-inbox-read/SKILL.md` — the sweep comms runs at CEO INITIALIZE.
- `plugins/kiho/skills/core/communication/help-wanted/SKILL.md` — closest existing "to multiple agents" primitive; capability-matrix filtered.
- `plugins/kiho/skills/core/ceremony/shift-handoff/SKILL.md` — the turn-boundary ceremony where pinned content would re-surface.
- `plugins/kiho/agents/kiho-comms.md` — committee's natural executor.
- `plugins/kiho/references/data-storage-matrix.md` — any new `announcements/` row requires matrix addition (Storage-fit follow-up).

## Out of scope (explicit)

- **No external channel integration.** No Slack webhooks, no email, no SMS. Announcements live in kiho state.
- **No per-user subscription opt-out.** Agents do not refuse broadcasts; aggregate attention is managed via capability-matrix filtering (a broadcast to "engineering agents" does not reach HR agents in the first place).
- **No audio/video announcements.** Markdown only. An announcement is a memo with broader fan-out.

## Escalation triggers

- Overlap-hunter establishes in round 1 that ALL use cases fit existing skills → consider closing with "no new surface" unanimously.
- Committee splits on Q4 (pin/expire semantics) because there's no natural default — PROCEED with winner if confidence > 0.80 (reversible + design detail).
