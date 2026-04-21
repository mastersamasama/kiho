# Round phases — detailed rules

Loaded by the committee runner when phase-level detail is needed. Each round consists of five phases executed sequentially. All members participate in every phase.

## Contents
- [Phase 1: Research](#phase-1-research)
- [Phase 2: Suggest](#phase-2-suggest)
- [Phase 3: Combine](#phase-3-combine)
- [Phase 4: Challenge](#phase-4-challenge)
- [Phase 5: Choose](#phase-5-choose)
- [Cross-phase rules](#cross-phase-rules)

## Phase 1: Research

**Purpose:** Gather evidence before forming opinions.

**Preconditions:**
- Committee `index.md` exists with topic and members
- `transcript.md` initialized
- For rounds 2+: prior round's unresolved challenges and dissent are available

**Agent actions:**
- Read the committee topic from `index.md`
- Query KB via `kb-search` with the topic and related terms
- Read any raw sources referenced in the committee brief
- For rounds 2+: read the prior round's challenge messages and unresolved items
- Post a research message to `transcript.md` summarizing findings

**Output shape per message:**
```yaml
phase: research
position: null
confidence: null
reasoning: "<summary of evidence found>"
sources:
  - "<kb-page-id or url>"
  - "<kb-page-id or url>"
challenges: []
resolved: []
```

**Postconditions:**
- Every member has posted exactly one research message this round
- Each message cites at least one source (KB page, raw doc, or external URL)

## Phase 2: Suggest

**Purpose:** Each member proposes their position based on research.

**Preconditions:**
- All members have posted research messages for this round

**Agent actions:**
- Read all research messages from this round
- Form an independent position on the topic
- Assign a confidence value (0.0-1.0) — be conservative; raw LLM confidence is typically overconfident, so discount by 0.10-0.15
- Post a suggest message with position, confidence, and reasoning

**Output shape per message:**
```yaml
phase: suggest
position: "<clear, one-sentence position statement>"
confidence: 0.78
reasoning: "<2-3 sentences explaining why this position, citing research>"
sources:
  - "<source supporting this position>"
challenges: []
resolved: []
```

**Postconditions:**
- Every member has posted exactly one suggest message this round
- Each position is a single clear statement (not "it depends" — pick a side)
- Confidence values are between 0.0 and 1.0

## Phase 3: Combine

**Purpose:** Find synthesis across positions. Reduce the number of distinct positions.

**Preconditions:**
- All members have posted suggest messages for this round

**Agent actions:**
- Read all suggest messages from this round
- Identify areas of agreement and disagreement
- Propose a combined position that captures the strongest elements, or explain why combination is not possible
- If two positions are compatible, propose a merged position with combined confidence
- Post a combine message

**Output shape per message:**
```yaml
phase: combine
position: "<proposed combined position or reaffirmed original>"
confidence: 0.82
reasoning: "<how this combines prior suggestions, or why combination failed>"
sources:
  - "<any additional sources>"
challenges: []
resolved: []
```

**Postconditions:**
- Every member has posted exactly one combine message
- The number of distinct positions is equal to or fewer than in the suggest phase

## Phase 4: Challenge

**Purpose:** Stress-test positions. Raise objections, edge cases, contradictions, missing considerations.

**Preconditions:**
- All members have posted combine messages for this round

**Agent actions:**
- Read all combine messages
- For each position (including your own), identify weaknesses:
  - Edge cases not considered
  - Contradictions with known KB facts
  - Cost/performance/security implications
  - Reversibility concerns
  - Implementation risks
- Post challenges as structured items in the message
- If a prior challenge (from a previous round) is now addressed, mark it resolved

**Output shape per message:**
```yaml
phase: challenge
position: "<current position, may be unchanged>"
confidence: 0.75
reasoning: "<summary of challenges raised and why they matter>"
sources:
  - "<evidence supporting the challenge>"
challenges:
  - id: "ch-<round>-<seq>"
    target_position: "<which position this challenges>"
    description: "<specific objection>"
    severity: "blocking | significant | minor"
resolved:
  - id: "ch-<prior-round>-<seq>"
    resolution: "<how the concern was addressed>"
```

**Postconditions:**
- Every member has posted exactly one challenge message
- At least one challenge has been raised (even if positions agree — challenge forces rigor)
- Each challenge has an id, target, description, and severity

## Phase 5: Choose

**Purpose:** Final position declaration for this round, incorporating challenges.

**Preconditions:**
- All members have posted challenge messages for this round

**Agent actions:**
- Read all challenge messages
- Decide whether any challenge changes your position
- If challenges are blocking and unresolved, lower your confidence
- Declare your final position and confidence for this round
- Mark any challenges you consider resolved (with explanation)

**Output shape per message:**
```yaml
phase: choose
position: "<final position for this round>"
confidence: 0.88
reasoning: "<why this position survives challenges>"
sources:
  - "<key supporting evidence>"
challenges: []
resolved:
  - id: "ch-1-2"
    resolution: "<how addressed>"
```

**Postconditions:**
- Every member has posted exactly one choose message
- Confidence reflects challenge impact (lower if unresolved blockers exist)
- The close rule is evaluated immediately after all choose messages are posted

## Cross-phase rules

- **Message ordering:** Within a phase, members post sequentially (not in parallel). Order rotates each round to prevent anchoring bias. Round 1: alphabetical by agent name. Round 2: reverse. Round 3: random.
- **No edits:** Messages are append-only. A member cannot edit a prior message. To retract a position, post a new message in the current phase.
- **Phase boundaries are strict:** No member may post a phase-N message until all members have posted their phase-(N-1) messages.
- **Private consultations:** May be initiated during any phase. The consultation response is available before the member's next message. See `references/consultation.md`.
- **Confidence calibration:** Members should calibrate confidence relative to the decision's impact. For irreversible decisions, a confidence of 0.85 should mean "I would bet my job on this." For reversible decisions, 0.85 means "this is strongly preferred but we can switch later."
