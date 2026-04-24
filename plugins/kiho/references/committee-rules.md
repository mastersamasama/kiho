# Committee rules — offline reference

Loaded when the CEO, committee runner, or clerk needs the full specification of committee governance rules. This is the single authoritative source for close conditions, round limits, and escalation.

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.

## Non-Goals

- **Not a voting theory primer.** Committees use a unanimous-close rule with no-unresolved-challenges constraint. Preferential voting, Condorcet, and related methods are out of scope.
- **Not a replacement for CEO judgment.** Committees produce recommendations; the CEO ratifies. Escalation to the CEO is a feature, not a failure.
- **Not a forum for open-ended debate.** Committees have hard round limits (default 3). A committee that cannot converge in 3 rounds escalates; it does not keep running.

## Contents
- [Close rule](#close-rule)
- [Round limits](#round-limits)
- [Escalation decision table](#escalation-decision-table)
- [Confidence aggregation](#confidence-aggregation)
- [Special committee types](#special-committee-types)
- [Quorum and membership](#quorum-and-membership)
- [Transcript format](#transcript-format)

## Close rule

A committee closes successfully when ALL three conditions are met after a round's choose phase:

| # | Condition | Measurement |
|---|---|---|
| 1 | **Unanimous position** | Every member's latest choose-phase message names the identical position (exact string match after normalization) |
| 2 | **No unresolved challenges** | Every `challenges` entry across all rounds has a corresponding `resolved` entry with `resolution` text |
| 3 | **Aggregate confidence >= 0.90** | Mean of all members' final choose-phase confidence values is at least 0.90 |

Check the close rule after every choose phase. If met, close immediately — do not start another round.

### Partial close scenarios

| Scenario | Action |
|---|---|
| Unanimous + no challenges + confidence 0.87 | NOT closed. Start next round focusing on raising confidence. |
| Unanimous + one unresolved minor challenge + confidence 0.95 | NOT closed. Resolve the challenge first, even if minor. |
| 2/3 agree + no challenges + confidence 0.92 | NOT closed. Need unanimity. |
| Unanimous + no challenges + confidence 0.90 exactly | Closed. The threshold is inclusive (>=). |

## Round limits

- **Maximum rounds per committee:** 3
- **Minimum rounds:** 1 (a single round can close if close rule met)
- **Inter-round injection:** At the start of round N+1, the committee runner injects into each member's research-phase context:
  - All unresolved challenges from round N
  - The dissent positions and their reasoning
  - A prompt: "Focus this round on resolving the challenges below and finding common ground."

## Escalation decision table

When round 3 completes without meeting the close rule, the committee escalates to CEO. The CEO applies this table (matches top-to-bottom, first match wins):

| # | Condition | CEO action |
|---|---|---|
| 1 | Irreversible decision + no pre-approval | ASK_USER with the committee summary and all positions |
| 2 | Strong dissent (dissent conf > 0.80 AND winner conf < 0.95) | RECONVENE once with dissent injected. If still fails, ASK_USER |
| 3 | Reversible + winner conf >= 0.80 | PROCEED with the winning position (accept lower confidence for reversible decisions) |
| 4 | Reversible + winner conf < 0.80 | ASK_USER — too uncertain even for a reversible decision |
| 5 | All members conf < 0.70 | ASK_USER — the committee lacks sufficient evidence |
| 6 | Budget exhausted | ASK_USER with what's known so far |
| 7 | Otherwise | ASK_USER |

### RECONVENE protocol

RECONVENE spawns a new committee (max_rounds: 1) with:
- The original members
- The dissent from the prior committee injected into the research phase
- The unresolved challenges listed explicitly
- A note: "This is a reconvened committee. Prior deliberation reached N rounds without consensus. Focus on resolving the listed challenges."

RECONVENE happens at most once per originating committee. If the reconvened committee also fails, escalate to ASK_USER.

## Confidence aggregation

**Raw member confidence** is the value each member reports in their choose-phase message (0.0-1.0).

**Aggregate confidence** for a position:
```
aggregate = mean(supporters' confidence values)
```

**CEO confidence** (used for the escalation decision table):
```
ceo_confidence = aggregate * consensus_ratio - unresolved_penalty

where:
  consensus_ratio = supporters / total_members  (1.0 for unanimous)
  unresolved_penalty = 0.10 if any unresolved challenges exist, else 0.0
```

This formula compensates for LLM overconfidence. A unanimous committee at 0.92 average with no unresolved challenges yields CEO confidence 0.92. The same committee with one unresolved challenge yields 0.82 — below the typical threshold.

> **Two thresholds, two stages.** Close rule #3 (aggregate ≥ 0.90) is a **hard floor** evaluated after every choose phase: if aggregate drops below 0.90 — whether from raw member confidence or because the `unresolved_penalty` drags `ceo_confidence` down post-hoc — the committee **MUST** either open another round or escalate. It does **NOT** close. `ceo_confidence` is a **separate escalation-time metric** used by the table above *after* a committee has failed to close within its round limit; it never retroactively authorizes a close that the 0.90 floor rejected. When close-rule #2 is violated (unresolved challenges exist), the committee cannot close regardless of the aggregate number, which is why the penalty case described in the prior paragraph is always an escalation case and never a close case.

## Special committee types

### Hiring committee
- Members: HR lead + auditors (2-4 depending on tier)
- Topic: "Should we hire candidate X for role Y?"
- Knowledge_update: false (hiring decisions are not KB content)
- Reversibility: slow-reversible (agents can be terminated)
- Additional rule: auditor personas are assigned by CEO (skeptic, pragmatist, overlap_hunter, cost_hawk)

### Rubric design committee
- Members: HR lead + relevant department lead + one IC from the department
- Topic: "What evaluation rubric should we use for role Y?"
- Knowledge_update: true (rubrics are stored as KB rubric pages)
- Reversibility: reversible

### Contradiction resolution committee
- Members: kb-manager + the agents who authored the conflicting pages
- Topic: "Resolve contradiction between [[page-A]] and [[page-B]]"
- Knowledge_update: true (the resolution becomes a new decision page)
- Reversibility: reversible

### Lightweight committee (v5.23+)
- Members: minimum 2, maximum 3 (plus clerk)
- Topic: a single closed question, binary or ≤5-option multiple-choice
- Max rounds: 1 (one-round cap, not 3)
- Phases: `research` + `choose` REQUIRED; `suggest` and `challenge` OPTIONAL and typically skipped (emit `- (no entries this round)` placeholder)
- Close threshold: standard (unanimous + no unresolved challenges + aggregate ≥ 0.90 — no relaxation)
- Use case: fast signal capture on a narrow question where 3-round deliberation is overkill (e.g., a pulse-style "did this process work?" check, a binary "should we roll back?" poll)
- Escalation: if unanimous close fails in the single round, escalate to CEO per the standard escalation decision table — there is no RECONVENE for the lightweight variant (adding rounds means you should have used a regular committee from the start)
- Transcript: same format as a regular committee; `rounds_used: 1` in the Close block

Introduced by decision `04-committee-pulse/decision.md` (v5.23 planning) as the codified form of "small committee with fewer rounds" that several previous debates resolved by convention.

### Storage-fit committee (v5.19+)
- Members: proposer + kb-manager + a relevant department lead (domain of affected data class)
- Topic: "Add row X to `references/data-storage-matrix.md`" OR "Change tier/tech/eviction for existing row X" OR "Promote DEFERRED row X to active"
- Knowledge_update: false (matrix edits are referenced, not KB content)
- Reversibility: reversible for T2/T3 rows, slow-reversible for T1 (once skills cite the row, migration required)
- Additional rule: vote record **MUST** cite the relevant §section of `storage-tech-stack.md`; if the change introduces a new technology not yet in storage-tech-stack.md, a preceding `tech-stack` vote is required
- Close threshold: standard (unanimous + no unresolved challenges + aggregate ≥ 0.90)
- Vote artifact: `_meta-runtime/storage-committee-<slug>-<id>.md`

## Quorum and membership

- **Minimum members:** 2 (plus the clerk)
- **Maximum members:** 5
- **Clerk is not a member.** The clerk does not vote, does not post to the transcript, and does not count toward quorum or unanimity.
- **Convening leader may be a member** if they do not also serve as clerk. If the leader has a stake, they must participate as a member AND appoint a separate clerk.
- **No duplicate perspectives.** Do not put two agents from the same department with the same role on the same committee. Diversity of perspective is the entire point.

## Transcript format

Each committee writes one `transcript.md` per deliberation at `<project>/.kiho/committees/<committee-id>/transcript.md` (project tier) or `$COMPANY_ROOT/committees/<committee-id>/transcript.md` (company tier). `transcript.md` is the T1 canonical record; the T2 JSONL stream at `<same-dir>/records.jsonl` is regenerated from it by `bin/kiho_clerk.py extract-rounds` (per `references/data-storage-matrix.md` §5 `committee-records-jsonl` row).

### Why a parseable format

Three consumers depend on the shape:

1. **Close-rule auditing** — round-counting for the 3-round cap is only reliable if rounds are machine-identifiable.
2. **JSONL regeneration** — `kiho_clerk extract-rounds` is a deterministic parser. Drift in structure → parse error (exit 1), which is loud on purpose.
3. **Cross-committee pattern learning (Wave 2)** — `committee-index-sqlite` builds a queryable index over the JSONL stream; this only works if the JSONL schema is uniform, which depends on transcript.md discipline.

### Required structure

1. **Frontmatter (YAML)** — MUST include:
   ```yaml
   ---
   committee_id: storage-fit-tech-stack-2026-04-18
   topic: "Phase 1 tech-stack — per-category votes"
   chartered_at: 2026-04-18T09:00:00Z
   members:
     - "@kiho-ceo"
     - "@kiho-kb-manager"
     - "@kiho-eng-lead"
   quorum: 3
   ---
   ```
   - `chartered_at` MUST be ISO-8601 with timezone offset or `Z`.
   - `members` MUST list every `@agent-name` that appears in the body.
   - `quorum` MUST be ≤ len(members) and MUST satisfy the `Quorum and membership` rules above.

2. **Round blocks** — one H2 per round, numbered 1..N:
   ```markdown
   ## Round 1

   ### research

   - **@kiho-eng-lead** (confidence: 0.85) — TOML for typed config; stdlib 3.11 tomllib covers reads.
     > Python 3.11's tomllib is read-only but covers all current call sites.

   ### suggest

   - **@kiho-kb-manager** (confidence: 0.90) — Accept TOML; lazy migration at author-on-touch.

   ### challenge

   - **@kiho-ceo** (confidence: 0.88) — Does tomllib's read-only limitation block kiho-setup writes?
     > Proposed mitigation: minimalist hand-emit via f-strings for the narrow config.yaml schema.

   ### choose

   - **@kiho-eng-lead** (confidence: 0.88) — TOML, lazy migration, f-string write path.
   - **@kiho-kb-manager** (confidence: 0.90) — TOML, lazy migration, f-string write path.
   - **@kiho-ceo** (confidence: 0.88) — TOML, lazy migration, f-string write path.
   ```
   - Every round MUST contain the four phases in order: `research`, `suggest`, `challenge`, `choose`. Empty phases are permitted with an explicit `- (no entries this round)` placeholder, but MUST still appear as H3 headings.
   - Each message MUST use the bullet form `- **@agent-name** (confidence: 0.XX) — <position summary>` where `0.XX` is two decimal places, and the `@agent-name` MUST appear in the frontmatter `members` list.
   - The optional `> <rationale>` block-quote MAY follow any message; multiple lines continue via standard markdown blockquote continuation.

3. **Close block** — exactly one H2 `## Close` at the end:
   ```markdown
   ## Close

   - outcome: unanimous
   - final_confidence: 0.88
   - rounds_used: 1
   - decision: "TOML for small typed config; lazy migration; hand-emit write path."
   ```
   - `outcome` MUST be one of `unanimous | consensus | split | deferred`.
   - `final_confidence` MUST be the aggregate per the §"Confidence aggregation" formula, two decimal places.
   - `rounds_used` MUST match the count of `## Round N` blocks above.
   - `decision` MUST be a one-sentence quoted string (the canonical committee resolution).

### Two worked examples

Both examples parse byte-identically into JSONL via `kiho_clerk extract-rounds`. The first closes unanimously in one round; the second takes three rounds to resolve a challenge.

#### Example A — fast unanimous close (1 round)

```markdown
---
committee_id: color-pick-2026-05-01
topic: "Pick a color token for the warning banner"
chartered_at: 2026-05-01T10:00:00Z
members:
  - "@frontend-lead"
  - "@design-ic"
  - "@a11y-reviewer"
quorum: 3
---

## Round 1

### research

- **@design-ic** (confidence: 0.92) — Amber #F59E0B meets AA contrast on both light/dark surfaces.
- **@a11y-reviewer** (confidence: 0.90) — Confirmed WCAG 2.1 AA at 4.7:1 ratio.

### suggest

- **@design-ic** (confidence: 0.92) — Adopt amber #F59E0B as tokens.warning.

### challenge

- (no entries this round)

### choose

- **@frontend-lead** (confidence: 0.91) — Adopt amber #F59E0B.
- **@design-ic** (confidence: 0.92) — Adopt amber #F59E0B.
- **@a11y-reviewer** (confidence: 0.90) — Adopt amber #F59E0B.

## Close

- outcome: unanimous
- final_confidence: 0.91
- rounds_used: 1
- decision: "Adopt amber #F59E0B as tokens.warning."
```

#### Example B — 3-round challenge cycle

```markdown
---
committee_id: cache-eviction-policy-2026-05-08
topic: "Pick an eviction policy for the on-disk query cache"
chartered_at: 2026-05-08T14:30:00Z
members:
  - "@eng-lead"
  - "@perf-ic"
  - "@reliability-reviewer"
quorum: 3
---

## Round 1

### research

- **@perf-ic** (confidence: 0.82) — LRU is simplest; 95% hit-rate in trace replay.

### suggest

- **@perf-ic** (confidence: 0.82) — LRU with 500-entry cap.

### challenge

- **@reliability-reviewer** (confidence: 0.78) — LRU thrashes on our bimodal workload.
  > Traces show 70% of queries are one-shots; LRU will evict the hot 30%.

### choose

- **@eng-lead** (confidence: 0.72) — Defer pending challenge resolution.
- **@perf-ic** (confidence: 0.72) — Defer pending challenge resolution.
- **@reliability-reviewer** (confidence: 0.78) — Defer pending challenge resolution.

## Round 2

### research

- **@perf-ic** (confidence: 0.85) — LFU with decay handles bimodal workload; +3% hit-rate in replay.

### suggest

- **@perf-ic** (confidence: 0.85) — LFU with exponential decay (τ=1h).

### challenge

- **@reliability-reviewer** (confidence: 0.82) — LFU+decay memory overhead acceptable? 500 entries × counter = 4KB.
  > Resolved: 4KB is negligible at our scale.

### choose

- **@eng-lead** (confidence: 0.85) — LFU+decay (τ=1h).
- **@perf-ic** (confidence: 0.88) — LFU+decay (τ=1h).
- **@reliability-reviewer** (confidence: 0.85) — LFU+decay (τ=1h).

## Round 3

### research

- (no entries this round)

### suggest

- (no entries this round)

### challenge

- (no entries this round)

### choose

- **@eng-lead** (confidence: 0.91) — LFU+decay (τ=1h), 500-entry cap.
- **@perf-ic** (confidence: 0.92) — LFU+decay (τ=1h), 500-entry cap.
- **@reliability-reviewer** (confidence: 0.90) — LFU+decay (τ=1h), 500-entry cap.

## Close

- outcome: unanimous
- final_confidence: 0.91
- rounds_used: 3
- decision: "LFU with exponential decay (τ=1h), 500-entry cap."
```

### Regeneration contract

- `bin/kiho_clerk.py extract-rounds --transcript <path>` MUST parse any transcript meeting the rules above into `rounds.jsonl` (schema: `committee_id, round, phase, author, confidence, position, rationale?`) without mutation of the source.
- A transcript that violates the rules MUST cause the parser to exit 1 with a diagnostic, not silently emit partial data.
- Re-running the parser on the same input MUST produce byte-identical JSONL (idempotent).

### Normative rules (BCP 14)

- Clerks MUST write ISO-8601 `chartered_at` timestamps; naive datetimes are prohibited.
- Authors MUST use two-decimal-place confidence values; `0.9` is invalid, `0.90` is valid.
- Transcripts MUST end with exactly one `## Close` block; committees that escalate before closing still emit `## Close` with `outcome: deferred` and a `rounds_used` count.
- Clerks MUST NOT hand-write to `records.jsonl`; the JSONL is regenerable from `transcript.md` and hand-writes break the parity contract.
- Transcripts MAY embed additional H4 / H5 subheadings under phase H3s for long rationales, but bullet-form messages MUST remain direct children of the phase H3.
