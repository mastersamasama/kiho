# skill-critic rubric (v1.0.0)

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this
> document are to be interpreted as described in BCP 14 (RFC 2119, RFC 8174).

Axis definitions and scoring logic for `scripts/critic_score.py`. Every axis here MUST stay in sync with the script — a drift between this file and the script is a Gate 15 (stale-path) violation.

## Axis index

| # | Name | Weight | Source |
|---|---|---|---|
| 1 | description_quality | 0.20 | `skill-authoring-standards.md` §description rules |
| 2 | body_length | 0.05 | `skill-authoring-standards.md` §body length cap |
| 3 | structure | 0.15 | progressive disclosure pattern |
| 4 | examples | 0.15 | `skill-authoring-patterns.md` Pattern 4 (worked examples) |
| 5 | anti_patterns | 0.15 | `skill-authoring-patterns.md` Pattern 8 |
| 6 | frontmatter_completeness | 0.15 | `skill-authoring-standards.md` §required frontmatter |
| 7 | capability_valid | 0.05 | `capability-taxonomy.md` (closed 8-verb set) |
| 8 | topic_tags_valid | 0.10 | `topic-vocabulary.md` (controlled 18-tag set) |

Total weight: 1.00.

## Axis 1 — description_quality (weight 0.20)

**Grounding**: the description is the primary trigger surface. Claude Code reads the description field to decide whether to invoke the skill at all. A weak description causes trigger misses; a long description burns token budget.

Three sub-checks, averaged:

1. **Length** — `50 <= len(description) <= 1024`. Below 50 is almost certainly a trigger miss; above 1024 violates the Anthropic-authored skill-creator's hard cap.
2. **Tone** — starts with "Use this skill" OR does not start with first/second-person pronouns ("I ", "You ", "We "). Third-person instructional tone is the Anthropic standard.
3. **Trigger phrase hints** — counts matches against a seed list of trigger-intent words (`"use this skill"`, `"triggers on"`, `"invoke"`, `"when the user"`, `"when to use"`, `"when a"`, `"when "`, `"for "`). Three hits → full credit; fewer hits scales linearly.

## Axis 2 — body_length (weight 0.05)

**Grounding**: `skill-authoring-standards.md` caps body at 500 lines. Above 500 the skill has failed progressive disclosure (overflow goes to `references/`).

- `< 400` lines → 1.0 (full credit)
- `400 ≤ lines < 500` → 0.8 (yellow; consider splitting into references/)
- `≥ 500` → 0.0 (red)

## Axis 3 — structure (weight 0.15)

**Grounding**: every SKILL.md MUST have a single H1 title matching the skill name, and at least one H2 section that scopes the content. Skills without H2 sections are either stubs or single-paragraph trivia that don't warrant a skill.

- `has_h1` → +0.5
- `h2_count ≥ 1` → +0.3
- `h2_count ≥ 3` → +0.2 (progressive disclosure bonus)

Maximum: 1.0.

## Axis 4 — examples (weight 0.15)

**Grounding**: Pattern 4 (worked examples) is the single most-predictive indicator of a well-documented skill. An example shows the invocation format, the input shape, and the response shape all at once.

- Fenced code block (```) AND an `## Example` heading → 1.0
- Either one alone → 0.7
- Neither → 0.0

Both forms count: `### Example 1`, `## Worked examples`, `## Examples` all match via case-insensitive substring `"example"`.

## Axis 5 — anti_patterns (weight 0.15)

**Grounding**: anti-patterns are accumulated wisdom that tells the caller what NOT to do. `skill-improve`'s diff constraints forbid removing anti-patterns. A skill without any anti-pattern section is either brand new (no wisdom yet) or has lost the section (red flag).

- Heading matching regex `^##+\s+(anti[- ]?patterns?|do not|avoid|never)\b` (case-insensitive) → 1.0
- No such heading → 0.0

## Axis 6 — frontmatter_completeness (weight 0.15)

**Grounding**: `skill-authoring-standards.md` makes `name` and `description` required and strongly recommends the `metadata.kiho` block (capability + topic_tags + data_classes). Missing optional fields do not block ship but impair facet-walk selectivity.

- `name` present → +0.3
- `description` present → +0.3
- `metadata.kiho.capability` present → +0.15
- `metadata.kiho.topic_tags` present and non-empty → +0.15
- `metadata.kiho.data_classes` declared (even empty list) → +0.10

Maximum: 1.0.

## Axis 7 — capability_valid (weight 0.05)

**Grounding**: the closed 8-verb set (`capability-taxonomy.md`) is enforced by Gate 20 (`capability_vocab_check.py`) at skill-spec time. This axis is a second-line catch for drafts that slipped the structural gate.

- No capability declared → 0.0
- Capability not in the closed set → 0.0
- Capability in the closed set → 1.0
- `capability-taxonomy.md` unreadable → 1.0 with detail `"axis skipped"` (graceful degradation — better to under-scrutinize than crash the critic)

## Axis 8 — topic_tags_valid (weight 0.10)

**Grounding**: the controlled 18-tag vocabulary (`topic-vocabulary.md`) enforced by Gate 21 (`topic_vocab_check.py`). Same second-line role as axis 7.

- No tags declared → 0.0
- All tags in vocabulary → 1.0
- Some invalid → score = `valid_count / total_count`
- `topic-vocabulary.md` unreadable → 1.0 with detail `"axis skipped"`

## Overall score formula

```
overall_score = sum(axis.score * axis.weight for axis in axes) / sum(axis.weight)
```

Since weights sum to 1.00, the denominator is nominally 1.00. The formula is written this way so future axis additions or weight tuning do not break the report shape — the normalizer accommodates any total.

## Hard-fail rules (override the overall score)

Two structural defects trigger `status: hard_fail` regardless of the score:

1. **No H1 anywhere in the body** — the skill has no title; trigger lookups will miss it.
2. **Body under 20 lines** (post-frontmatter) — the skill is a stub or empty shell.

Hard-fail surfaces as `pass: false` AND `status: "hard_fail"`, and exits 1 (factory short-circuits Steps 6-10 for this skill).

## Rationale for the weight distribution

- **description_quality** is 0.20 (highest) because trigger misses are the single biggest failure mode in practice.
- **frontmatter_completeness / structure / examples / anti_patterns** each 0.15 — these are the four Pattern-matching axes and they co-determine whether a skill is "self-contained enough to use without reading the author's mind".
- **topic_tags_valid** is 0.10 — tag validity matters for facet selectivity but an invalid tag is a quick fix.
- **body_length** and **capability_valid** each 0.05 — cheap structural checks that will usually be already-enforced upstream by the structural gate.

These weights may be tuned by CEO committee vote. Any change updates both this file and the script docstring.

## Changelog

- v1.0.0 (2026-04-19) — initial 8-axis rubric, weights 0.20/0.05/0.15/0.15/0.15/0.15/0.05/0.10.
