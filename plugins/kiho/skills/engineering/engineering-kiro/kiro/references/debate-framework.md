# Debate Framework: Multi-Perspective Decision Protocol

## Purpose

When a significant architectural or library decision arises during spec-driven development, use this framework to ensure the decision is evidence-based, considers alternatives, and produces a well-documented rationale.

## When to Trigger

- **Major architectural decisions**: State management strategy, rendering approach, data flow pattern
- **Library selection**: Choosing between 2+ viable libraries for a core capability
- **User requests debate**: `--debate` flag or "evaluate options for X"
- **Design phase uncertainty**: Multiple valid approaches with non-obvious trade-offs
- **Breaking changes**: Decisions that are expensive to reverse once implemented

## When NOT to Trigger

- Obvious answers (e.g., a library already chosen in steering — no need to re-evaluate)
- Minor decisions (e.g., CSS class naming for one component)
- User has explicitly stated their preference
- Only one viable approach exists

## Three Roles

| Role | Responsibility | Implementation |
|------|---------------|----------------|
| **Proposer** | Research and advocate for the primary recommendation | `Agent(kiro-researcher)` — researches recommended approach in depth |
| **Challenger** | Research alternatives and challenge the proposal | `Agent(kiro-researcher)` — independently researches alternative approaches |
| **Leader** | Synthesize findings, facilitate comparison, render judgment | Main `/kiro` orchestrator — compares reports, decides or escalates to user |

## Debate Flow

### Phase 1: Identify Decision Point

The Leader identifies that a decision requires debate:

```
Decision: [What needs to be decided]
Context: [Why this decision matters, what it affects]
Constraints: [Tech stack rules, performance requirements, timeline]
```

### Phase 2: Parallel Research (Proposer + Challenger)

Spawn two `kiro-researcher` agents **in parallel**:

**Proposer prompt:**
```
QUESTION: Research [recommended approach] for [use case] in this project.

CONTEXT: We need to decide [decision]. This affects [impact scope].
The initial instinct is [approach A] because [reason].

CODEBASE_SCOPE: [relevant files/patterns]
EXTERNAL_SCOPE: Research [approach A] deeply — architecture, performance benchmarks,
maintenance status, bundle size, compatibility with the project's tech stack (as defined in steering).
Include source-level analysis where possible.
```

**Challenger prompt:**
```
QUESTION: Research alternatives to [approach A] for [use case] in this project.

CONTEXT: We need to decide [decision]. The leading candidate is [approach A],
but we need to evaluate alternatives before committing.

CODEBASE_SCOPE: [relevant files/patterns]
EXTERNAL_SCOPE: Find and research 2-3 alternatives to [approach A].
For each alternative: architecture comparison, performance, maintenance status,
bundle size, compatibility with our stack. Be adversarial — find weaknesses
in [approach A] and strengths of alternatives.
```

### Phase 3: Comparison Matrix

The Leader compiles both research reports into a structured comparison:

```markdown
### Decision: [Title]

| Dimension | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| Architecture | [approach] | [approach] | [approach] |
| Bundle size | [size] | [size] | [size] |
| Maintenance | [status] | [status] | [status] |
| Primary framework support | [yes/no/partial] | [yes/no/partial] | [yes/no/partial] |
| SSR compatible | [yes/no] | [yes/no] | [yes/no] |
| TypeScript support | [quality] | [quality] | [quality] |
| Learning curve | [low/med/high] | [low/med/high] | [low/med/high] |
| Community size | [size] | [size] | [size] |
| Our stack fit | [score] | [score] | [score] |
```

### Phase 4: Decision Path

```
Is there a clear winner across most dimensions?
├── YES → Leader declares consensus
│   └── Record decision with rationale in design.md
│
├── MOSTLY YES, with trade-offs → Leader presents recommendation to user
│   ├── Show comparison matrix
│   ├── State Leader's recommendation + reasoning
│   └── User confirms or overrides
│
└── NO, genuinely split → Escalate to user with full context
    ├── Show comparison matrix with commentary
    ├── Proposer's final argument (2-3 sentences)
    ├── Challenger's final argument (2-3 sentences)
    └── User makes the call
```

### Phase 5: Deadlock Resolution

If debate extends beyond 2 rounds of back-and-forth without convergence:

1. **Leader declares time-box**: "I will make a ruling based on current evidence"
2. **Challenger makes final statement**: Last chance to present strongest argument
3. **Proposer responds**: Address Challenger's strongest point
4. **Leader renders judgment**: Final decision with explicit rationale
5. **Record dissent**: Note the Challenger's concerns in the decision record

## Decision Record Format

Record in `design.md` under a `### Decision: [Title]` section:

```markdown
### Decision: [Title]

**Decision process**: Debate — [Proposer recommended X] vs [Challenger recommended Y]
**Research depth**: [Source-level / Documentation-level / Surface-level]

| Dimension | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| ... | ... | ... | ... |

**Outcome**: [Consensus / Leader ruling / User decision]
**Choice**: [Selected option]
**Rationale**: [Why this option fits this project best]

**Challenger's dissent** _(if any)_:
> [Challenger's strongest remaining concern about the chosen approach]

**Mitigation**: [How we address the Challenger's concern]
```

## Examples

> **注意:** 以下示例来自某 React + Bun 项目，仅供参考辩论流程的运作方式。实际项目中应替换为你的技术栈和决策场景。

### Example: DOM Screenshot Library

```
Decision: Which library to use for DOM-to-image conversion?
Context: Share poster feature needs to capture a styled DOM element as PNG.
Constraints: Must work with React 19, support CSS custom properties, < 100KB bundle.

Proposer researches: html2canvas (most popular, familiar)
Challenger researches: modern-screenshot, dom-to-image-more, html-to-image

Comparison reveals:
- html2canvas: 200KB, no maintenance since 2023, poor CSS variable support
- modern-screenshot: 15KB, active maintenance, native DOM serialization
- html-to-image: 50KB, moderate maintenance, SVG-based approach

Leader consensus: modern-screenshot — smaller, maintained, better CSS support
```

### Example: State Management for Complex Form

```
Decision: How to manage multi-step restaurant registration form state?
Context: 4-step form with validation, draft saving, and cross-step dependencies.

Proposer researches: TanStack Form (already in stack)
Challenger researches: Zustand form slice, URL state per step, React Hook Form

Leader escalates to user: TanStack Form handles validation well but multi-step
coordination is complex. Zustand would be simpler for cross-step state but adds
another state source. Present both with trade-offs for user decision.
```
