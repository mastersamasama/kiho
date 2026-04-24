# Decision — company-wide broadcast (committee broadcast-announcements-2026-04-23)

## Status

Accepted by unanimous close at aggregate confidence 0.91, 1 round.

## Context

Lark, DingTalk, and Feishu ship pinned company-wide announcements as a top-level surface distinct from direct messaging. kiho has `memo-send` (peer-to-peer), `help-wanted` (capability-filtered request-for-volunteer), and `shift-handoff` (turn-boundary re-surface) but no single surface for "publish once, all matching agents read, pinned until expiry, optionally track acknowledgements."

Overlap concern was real: four existing skills cover announcement-adjacent ground. The committee's central question was whether the gap is actually distinct.

## Decision

**Minimal extension.** Three existing skills get tiny additions; one new Tier-1 data class is created; ZERO new skills are authored.

### 1. Extend `memo-send` with wildcard recipients

Today: `memo-send` takes `recipient: @agent-id`. After v5.23: `recipient` accepts

- `@<agent-id>` (existing)
- `@all` — every agent in `org-registry.md`
- `@dept:<department>` — every agent whose `agent.md` frontmatter declares `department: <value>`
- `@capability:<verb>` — every agent whose `capability-matrix` row shows ≥3 on the given capability verb

Wildcard resolution uses the capability-matrix (already Tier-2 regenerable). Fan-out is bounded by the matrix size (typically ≤ 20 agents), well under the fanout cap of 5 *per spawn* (this is fan-out of a message, not of sub-agent spawning — caps don't apply).

### 2. New Tier-1 data class `.kiho/state/announcements/<yyyy-mm-dd>-<slug>.md`

Frontmatter:

```yaml
---
id: "2026-04-23-v5.23-planning-started"
emitter: "@kiho-ceo"
audience: "@all"
pinned_until: "2026-04-30T00:00:00Z"
ack_required: true
ack_by: []
basis: null
---
```

- `basis` is nullable; required ONLY if emitter is not CEO and not a dept-lead (then must point to a closed committee decision).
- `ack_by` is a mutable list; grows as agents acknowledge via their `memo-inbox-read` sweep.
- Body is markdown, free-form.

Data-storage-matrix row (flagged as Storage-fit follow-up committee dependency):

| Slug | Tier | Format | Path | Gatekeeper | Eviction |
|---|---|---|---|---|---|
| announcements | T1 | markdown | `.kiho/state/announcements/` | kiho-comms | archive after 90 days post pinned_until expiry |

### 3. Extend `shift-handoff` ceremony

At turn boundary, `shift-handoff` already re-surfaces outstanding memos per agent. Addition: also list any announcement where `announcement.pinned_until > now() AND agent not in ack_by AND (audience matches agent OR audience == @all)`. Format:

```markdown
### Unread pinned announcements
- [2026-04-23-v5.23-planning-started](<path>) — pinned until 2026-04-30 — ack required
```

### 4. Two new ledger action types

- `announcement_published` — payload: `{announcement_id, emitter, audience, ack_required}`
- `announcement_acknowledged` — payload: `{announcement_id, ack_by_agent, ack_at}`

CEO-ledger audit consumers can now measure publish-to-ack latency + compliance.

### 5. RACI for emission

`memo-send` with wildcard recipient (equivalent to "announcement emission") has a pre-emit check:

- If emitter is `@kiho-ceo` (main conversation) → permitted.
- If emitter's `agent.md` frontmatter shows `role: dept-lead` → permitted.
- Otherwise → requires `basis: <path-to-committee-decision.md>` in the announcement frontmatter. If missing, `memo-send` aborts with `status: broadcast_basis_required`.

No PreToolUse hook; the check is skill-internal (same pattern as v5.22 recruit pre-emit gate).

## Consequences

### Positive

- Closes the gap without inventing a new skill portfolio.
- Preserves distinction between mailbox (`memo-send`) and bulletin-board (`announcements/`).
- Acknowledgement tracking is non-blocking — agents ack on their own cadence via existing `memo-inbox-read`; no hard enforcement.
- Policy-bearing announcements can be kb-manager-promoted to `rules.md` via existing kb-add pipeline — no new promotion path.
- Composable with committee 06 (dashboard) — publish-to-ack latency becomes a metric candidate.

### Negative

- `memo-send` becomes dual-purpose (peer + broadcast). Skill frontmatter / docs must clearly delineate the two modes; mis-use could broadcast private feedback.
- `shift-handoff` lengthens (more content per turn) — minor attention-budget cost.
- Data-storage-matrix row addition requires a separate Storage-fit committee as follow-up (cheap but required by v5.19 doctrine).

## Alternatives considered and rejected

- **New `announce-publish` skill** — rejected as feature-factory overhead. Wildcard `memo-send` covers the emit; a new surface adds nothing.
- **Pinned memos in each agent's inbox** — rejected because mailbox/bulletin distinction is valuable, and it would bloat individual inbox files.
- **External channel integration** (Slack webhook) — rejected per charter out-of-scope.

## Scope estimate

- 1 SKILL.md edit (`memo-send` — wildcard support)
- 1 SKILL.md edit (`shift-handoff` — re-surface logic)
- 1 new data-storage-matrix row (triggers Storage-fit follow-up)
- 2 new ledger action types (documented; no code to emit)
- 0 new Python files
- Estimated implementation: ~3 hours

## Dependencies

- Storage-fit follow-up committee for the new `announcements/` matrix row.
- Committee 06 (dashboard) optional consumer.

## Next concrete step

Implementation plan authorizes: wildcard parsing in `memo-send` Procedure, `shift-handoff` re-surface addition, announcement-file schema documentation, data-storage-matrix row via Storage-fit committee.
