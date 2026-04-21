---
name: soul-validate
description: Use this skill whenever any workflow needs to assert that a kiho agent soul is structurally coherent — after recruiting a new agent, after applying queued drift overrides, or when designing a new agent template. Runs the canonical coherence checklist specified in references/soul-architecture.md (Big Five scores in [1,10], values count 3-7, goals count 1-5, red lines non-empty, voice non-empty, immutable fields present) and returns a structured verdict. Two modes — strict fails on any issue, advisory returns the same issue list without failing so upstream callers can decide. This is the single source of truth for soul coherence; recruit, design-agent, soul-apply-override, and any commit-ceremony call should delegate here rather than re-implementing the checklist. Read-only; never mutates a soul.
argument-hint: "soul_dict=<parsed-soul> mode=<strict|advisory>"
metadata:
  trust-tier: T3
  version: 1.0.0
  lifecycle: active
  kiho:
    capability: evaluate
    topic_tags: [persona, validation]
    data_classes: ["agent-souls"]
---
# soul-validate

The single coherence check for kiho souls. Pre-v5.20 the check lived inline in three places — `soul-apply-override` Step 5, `recruit` soul-drafting step, `design-agent` soul synthesis — each re-implementing the rules with minor drift (notably `soul-apply-override` said Big Five range is [1,5] while `references/soul-architecture.md` §69-75 says 1-10). This skill extracts the canonical checklist into one place; `references/soul-architecture.md` stays authoritative for the rules, this skill is the callable implementation.

## Why a separate skill

The coherence rules are small (8 checks) but load-bearing. A soul with Big Five out of range, empty red lines, or missing voice undermines every downstream behaviour: committees get degenerate votes, memory-reflect can't detect drift because its baseline is malformed, cross-agent-learn filters by red-line compatibility and crashes on empty sets. Three callers needed the check, each rewrote it, each drifted. Consolidating here is forced-function: one skill to update when the architecture evolves, one test surface to cover, one audit trail.

## Inputs

```
PAYLOAD:
  soul_dict:
    identity:
      name: <string>                # immutable, required
      voice: <string>               # required, non-empty
      communication_style: <string> # optional
      signature_phrases: [<string>] # optional, 0-3 items
    personality:
      openness: <int 1..10>
      conscientiousness: <int 1..10>
      extraversion: <int 1..10>
      agreeableness: <int 1..10>
      neuroticism: <int 1..10>
    values: [<string>]              # 3-7 items, order = priority
    goals: [<string>]               # 1-5 items
    red_lines: [<string>]           # non-empty
    immutable:
      tier: <ic|lead|ceo|kb|hr|...> # required
      created_at: <iso-8601>        # required
      parent_agent: <string | null> # required (null allowed for root agents)
  mode: strict | advisory           # default: strict
```

Callers that have a raw markdown soul (not parsed) should parse first — this skill does NOT parse markdown; it takes a dict. `recruit` / `design-agent` build the dict during their own workflows; `soul-apply-override` builds the dict from the canonical `agents/<id>.md` plus pending overrides.

## Procedure

1. **Identity checks**
   - `identity.name` present and non-empty
   - `identity.voice` present and non-empty
   - `identity.signature_phrases` (if present) has 0-3 items

2. **Personality checks (Big Five)**
   - Each of the five traits present
   - Each trait is an integer in `[1, 10]` inclusive
   - No `NaN` or float; reject non-integer as an issue

3. **Values checks**
   - List present
   - `3 <= len(values) <= 7`
   - All entries non-empty strings
   - No duplicate entries (case-insensitive compare)

4. **Goals checks**
   - List present
   - `1 <= len(goals) <= 5`
   - All entries non-empty strings

5. **Red lines checks**
   - List present, non-empty
   - All entries non-empty strings

6. **Immutable checks**
   - `immutable.tier` present and non-empty
   - `immutable.created_at` present; ISO-8601 parseable
   - `immutable.parent_agent` key present (may be null, must not be missing)

7. **Assemble verdict**
   - Collect all issues into a list of `{check, detail, path}` dicts
   - In `strict` mode: `status = "ok"` iff issues list is empty, else `status = "error"`
   - In `advisory` mode: `status = "ok"` regardless; issues list returned for caller judgement

## Response shape

```json
{
  "status": "ok | error",
  "mode": "strict | advisory",
  "issue_count": 0,
  "issues": [
    {
      "check": "personality.openness_range",
      "detail": "openness=11 not in [1,10]",
      "path": "personality.openness"
    }
  ]
}
```

Callers should treat `status=error` in strict mode as a hard block on any downstream mutation (soul-apply-override refuses to write; recruit refuses to promote the draft; design-agent returns a revision request). Advisory callers log and continue.

## Storage

Read-only. No `storage-broker` writes from this skill. The soul dict comes from the caller, the verdict returns to the caller, no persistence in between. If a caller wants an audit trail of validation runs, it calls `storage-broker` itself with `kind="evolution"` after this skill returns.

## Invariants

- **Read-only.** This skill NEVER writes to `agents/*.md`, to any `.kiho/` path, or to any broker namespace. Pure function of the input dict.
- **Deterministic.** Same dict in → same verdict out. No LLM judgement, no stochastic behaviour.
- **Stdlib-only.** Implementation uses `bin/kiho_frontmatter.py` helpers only; no external deps.
- **Architecture-doc-authoritative.** When `references/soul-architecture.md` and this skill disagree, the architecture doc wins and this skill is considered drifted — triggers `skill-improve`. Do NOT update the architecture doc to match this skill.

## Non-Goals

- **Not a soul parser.** Takes dict input; does not parse markdown or YAML. Callers parse first.
- **Not a soul generator.** `recruit` and `design-agent` own soul generation; this skill only validates.
- **Not a drift detector.** `memory-reflect` owns drift detection (compares observed behaviour to declared soul over time). This skill validates the declared soul itself is well-formed.
- **Not a semantic critic.** Checks structural rules, not "is this a good soul". Committee review handles quality.
- **Not a persistence step.** Does not record its verdict anywhere; caller decides.

## Future callers (migration candidates)

- `skills/_meta/soul-apply-override/` — delegate Step 5 coherence recheck here via `commit-ceremony` Step E (see commit-ceremony.md).
- `skills/core/hr/recruit/` — delegate final soul-draft validation before hire-committee convenes.
- `skills/core/hr/design-agent/` — delegate soul-synthesis validation at the end of the 12-step pipeline.
- These migrations will correct the Big Five range drift in those skills (they currently say [1,5]; architecture.md says [1,10]).

## Grounding

- `references/soul-architecture.md` — authoritative rules (Big Five §69-75, values §78-120, goals/red lines §125+)
- `bin/kiho_frontmatter.py` — canonical frontmatter helpers for callers that parse raw soul markdown
- `skills/_meta/soul-apply-override/SKILL.md` — upstream caller post-v5.20
- `skills/core/lifecycle/commit-ceremony/SKILL.md` — orchestrates soul-validate via its `coherence_validator` input
