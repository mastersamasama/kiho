# skill-learn op=synthesize — detailed procedure

This reference documents the full procedure for `skill-learn op=synthesize` — the third sub-operation of skill-learn that finalizes a `research-deep` skeleton into a canonical SKILL.md. The SKILL.md body only carries the top-level overview; this reference is the authoritative implementation spec.

## Contents
- [When to use synthesize](#when-to-use-synthesize)
- [Preconditions](#preconditions)
- [Section mapping](#section-mapping)
- [Procedure](#procedure)
- [Speculative flag rules](#speculative-flag-rules)
- [Security rules](#security-rules)
- [Failure modes](#failure-modes)
- [Worked example](#worked-example)

## When to use synthesize

`op=synthesize` is the ONLY skill-learn sub-operation that consumes external research findings rather than observed session behavior. It's designed to be called:

1. **By design-agent Step 4d** in the Researchable sub-path A, after `research-deep` has finished BFS doc traversal and produced a living skeleton with `status: terminated`.
2. **Manually by an agent** that has curated a skeleton externally and wants to finalize it through the same validation path.

It's NOT for:
- Session-observed patterns → use `op=extract`
- Preserving a code range → use `op=capture`
- Greenfield cold-start authoring with clear intent → use `skill-create` (v5.11)
- Specializing an existing skill → use `skill-derive`
- Mutating an existing skill → use `skill-improve`

## Preconditions

Before synthesize runs, verify all of these:

1. **Skeleton exists** at the provided `skeleton_path`.
2. **Skeleton frontmatter** has `status: terminated` (NOT `in-progress` — a mid-crawl synthesize produces partial skills).
3. **Queue log** at `.kiho/state/research-queue/<slug>.jsonl` contains a `terminate` entry with a known reason code (`novelty_exhausted`, `queue_empty`, `budget_pages`, `budget_depth`, `budget_min`, `auth_denied`).
4. **Slug match** — the `slug` in skeleton frontmatter matches the caller-provided `topic` slug (prevents cross-topic contamination).
5. **No concurrent synthesize** for the same slug — check that no other skill-learn process is operating on the skeleton (file lock or timestamp check).

Any precondition failure aborts with `status: precondition_failed, reason: <specific failure>`.

## Section mapping

The skeleton's sections map onto canonical SKILL.md structure:

| Skeleton section | Canonical SKILL.md location |
|---|---|
| `## Overview` | frontmatter `description` (condensed) + opening paragraph of body |
| `## When to use` | body `## When to use` section + trigger phrases mined into frontmatter `description` |
| `## Preconditions` | body `## Inputs` or `## Preconditions` section |
| `## Procedure` | body `## Procedure` numbered steps (or topic sections if reference-style) |
| `## Configuration` | body `## Inputs` section (config-level parameters) |
| `## Pitfalls and gotchas` | body `## Anti-patterns` section |
| `## Examples` | body `## Example usage` section |
| `## Sources` | end-of-body `## Sources` block with full URL list |
| `## Extraction log` | DISCARDED (audit-only in the skeleton; not propagated to final skill) |

## Procedure

### 1. Read the skeleton

Parse the skeleton's frontmatter (slug, topic, pages_read, extracted_concepts, last_updated) and the body sections. Record `pages_read` and `termination_reason` from the queue log for the speculative-flag decision (see below).

### 2. Dedup check

Run the standard `skill-learn` dedup check against `skills/CATALOG.md` using:
- The skeleton's `topic` phrase as primary query
- The skeleton's `extracted_concepts` list as secondary overlap terms

If any existing skill has description overlap > 0.70, abort with `status: duplicate, existing_skill_id: sk-NNN, similarity: 0.XX` and return the existing skill path. The caller (usually design-agent Step 4d) should use the existing skill instead.

If overlap is 0.40–0.70, record `status: similar` as a note on the draft but continue — the produced skill gets a `# Note: similar to sk-NNN` comment in its frontmatter for reviewer awareness.

### 3. Frontmatter synthesis

Derive the frontmatter fields:

```yaml
name: <slug from skeleton>
description: |
  <Build from skeleton Overview + concept list + role_context. Apply the
   8 effectiveness rules from skill-create's description-improvement reference.
   If the derived description scores < 0.85, iterate up to 3 times using the
   skill-create iterative improvement loop.>
version: 0.1.0
lifecycle: draft
synthesized_from_research: true
source_urls:
  - <from skeleton's Sources section>
trusted_sources_used:
  - <from the caller's trusted_sources_used input>
pages_read: <from skeleton frontmatter>
concepts_captured: <len(extracted_concepts)>
speculative: <true|false — see Speculative flag rules>
topic_tags:
  - <mined from skeleton extracted_concepts + role_context>
```

**Important:** synthesize does NOT add optional fields (`allowed-tools`, `disable-model-invocation`, `context: fork`, etc.) automatically. The caller must pass those explicitly if the produced skill needs them.

### 4. Body synthesis

Transform the skeleton body into canonical SKILL.md body:

1. **Dedupe citation-tagged bullets.** The skeleton is append-heavy; the final skill should be tight. Use normalized-phrase matching (lowercase, strip punctuation) to identify duplicates.
2. **Promote frequently-cited concepts.** Any concept that appears in at least 2 skeleton source URLs becomes a first-class `## When to use` bullet. Single-citation concepts move to a `## Notes` or `## Edge cases` section rather than the main body.
3. **Preserve code examples verbatim** but deduplicate near-identical ones (Levenshtein > 0.85 similarity → keep only the longer/clearer version).
4. **Collapse per-bullet `[<url>]` citations** into a compact `## Sources` section at the end. Each source gets a bullet with (a) the URL, (b) the concepts extracted from it, and (c) the extraction timestamp.
5. **Apply the canonical body structure** from `references/skill-authoring-standards.md` §"Body rules": H1 title → opening paragraph → Contents TOC (if body > 100 lines) → topic sections → Anti-patterns → Response shape.
6. **Enforce the 500-line body rule.** If the synthesized body exceeds 500 lines, split off the largest topic section into a per-skill reference at `<skill-dir>/references/<topic>.md` and replace it with a pointer in the body.

### 5. Script preservation

If the skeleton's Examples section contained reusable code snippets that meet the "script-worthy" criteria (deterministic, error-prone, repeatedly applicable), **do NOT execute them** — copy them verbatim into `<skill-dir>/scripts/` with a comment block at the top naming the source URL and extraction date. synthesize never executes fetched code.

### 6. Write draft

Write the synthesized skill to `.kiho/state/drafts/sk-<slug>/`:
- `SKILL.md` — the finalized body + frontmatter
- `.skill_id` — placeholder (`sk-draft-<slug>`) to be replaced on next `catalog_gen.py` full run
- `references/` — any reference files produced by body splitting in step 4
- `scripts/` — any script files preserved in step 5
- `evals.md` — if the caller provided intent for eval generation, run through `skill-create`'s Step 9 procedure; otherwise leave a placeholder stub with instructions

### 7. Register

Call `kb-add` via kb-manager with:
- `page_type: skill`
- `lifecycle: draft`
- `synthesized_from_research: true`
- `source_urls: [<list>]`
- `pages_read: <N>`
- `speculative: <bool>`

Call `experience-pool op=add_skill` to register the skill pointer in the project pool.

### 8. Archive the skeleton

Move `.kiho/state/skill-skeletons/<slug>.md` to `.kiho/state/skill-skeletons/_archive/<slug>-<iso>.md`. This prevents the next `research-deep` run for the same slug from colliding and preserves lineage.

### 9. Return

Emit the response shape:

```json
{
  "status": "ok | duplicate | similar | precondition_failed | description_irrecoverable | error",
  "op": "synthesize",
  "skill_id": "sk-<slug>",
  "draft_path": ".kiho/state/drafts/sk-<slug>/SKILL.md",
  "proposed_lifecycle": "DRAFT",
  "speculative": false,
  "synthesized_from_research": true,
  "source_urls": ["..."],
  "pages_read": 27,
  "dedup_result": {"matched": null, "similarity": 0.0},
  "description_score": 1.0,
  "description_iterations": 0,
  "archived_skeleton_path": ".kiho/state/skill-skeletons/_archive/<slug>-<iso>.md"
}
```

## Speculative flag rules

Set `speculative: true` in the frontmatter when any of:

| Condition | Why |
|---|---|
| `pages_read < 10` | Insufficient doc coverage to trust the synthesized content |
| `termination_reason == budget_pages` | BFS stopped on a budget cap, not natural novelty exhaustion — content may be incomplete |
| `termination_reason == budget_min` | Wall-clock timeout; same concern |
| `termination_reason == auth_denied` | Partial coverage due to auth walls; missing content may be significant |

Otherwise set `speculative: false`.

Speculative DRAFTs still go through the same DRAFT → ACTIVE promotion path, but the CEO committee is prompted to scrutinize them more carefully — they need a passing `interview-simulate` on a real consuming agent AND an auditor review before promotion.

## Security rules

All rules are non-negotiable:

1. **Synthesized skills start DRAFT, always.** Never ACTIVE from op=synthesize alone, regardless of caller authority.
2. **DRAFT → ACTIVE promotion** requires `interview-simulate(mode: full)` pass on a consuming agent AND CEO committee approval via the self-improvement gate. synthesize never bypasses this.
3. **Never write to the candidate agent's `tools:` allowlist** as part of synthesize. Tool additions go through design-agent Step 4b separately.
4. **Never execute any code from the skeleton's Examples section** during synthesize. Code is content, not executable spec. Copy verbatim with attribution.
5. **Secret scan** runs on the synthesized skill via Gate 9 of the shared validation pipeline (same as skill-create). A hit blocks registration.
6. **License attribution** — every code block copied from a skeleton source must carry a comment naming the source URL. This preserves the attribution trail for the original doc author.

## Failure modes

| Status | Meaning | Recovery |
|---|---|---|
| `ok` | Synthesis succeeded; DRAFT registered | caller proceeds to interview-simulate on the consuming agent |
| `duplicate` | Skeleton topic matches an existing ACTIVE skill > 0.70 | use the existing skill; skeleton is archived but no DRAFT produced |
| `similar` | Skeleton topic overlaps an existing skill 0.40–0.70 | DRAFT produced with a similar-to note; reviewer should decide |
| `precondition_failed` | Skeleton not terminated / queue log missing / slug mismatch | abort; re-run research-deep or fix the inputs |
| `description_irrecoverable` | After 3 iterative improvement loops, description score < 0.85 | abort; the topic is too vague for a discrete skill, reclassify the gap as Unfillable |
| `body_too_large` | Synthesized body > 500 lines even after splitting | abort; the topic is too broad for a single skill, split into multiple |
| `security_blocked` | Gate 9 hit a secret or other security violation | abort; clean the skeleton content and re-run |
| `error` | Unexpected error (file write failure, kb-add failure) | log and escalate |

## Worked example

**Scenario:** design-agent Step 4d needs `sk-playwright-visual-regression` for a frontend-qa candidate. Sub-path A selected. `research-deep` has just terminated with:
- `slug: sk-playwright-visual-regression`
- `topic: "Playwright visual regression testing"`
- `pages_read: 27`
- `termination_reason: novelty_exhausted`
- `extracted_concepts: [snapshot-baseline, update-workflow, pixel-threshold, ci-integration, diff-review, flakiness-mitigation, device-matrix, ...]`

**synthesize inputs:**

```yaml
op: synthesize
skeleton_path: .kiho/state/skill-skeletons/sk-playwright-visual-regression.md
topic: "Playwright visual regression testing"
role_context: "frontend-qa IC doing UI visual regression in CI"
source_urls:
  - https://playwright.dev/docs/test-snapshots
  - https://storybook.js.org/docs/writing-tests/visual-testing
trusted_sources_used: [playwright-dev, storybook-official]
```

**Procedure trace:**

1. Read skeleton. Frontmatter checks out: `status: terminated`, slug matches, queue log has `terminate: novelty_exhausted`.
2. Dedup: query CATALOG for topic overlap. No existing `sk-playwright-*` visual regression skill. Clear.
3. Frontmatter synthesis: derive description from Overview + top concepts + role_context. Score via iterative improvement loop — first draft 0.75, second draft 1.0 (added explicit trigger phrases and pushy language). Final description passes.
4. Body synthesis: collapse the skeleton's 8 concept-tagged sections into canonical body structure. Resulting body is 340 lines — under the 500 limit, no splitting needed.
5. Script preservation: the skeleton's Examples section had a Playwright test snippet for snapshot configuration. Copy to `scripts/sample_visual_test.spec.ts` with attribution comment pointing to `https://playwright.dev/docs/test-snapshots`.
6. Write draft at `.kiho/state/drafts/sk-playwright-visual-regression/`.
7. `kb-add` with `synthesized_from_research: true, source_urls: [...], pages_read: 27, speculative: false` (novelty_exhausted termination means full coverage).
8. Archive skeleton to `.kiho/state/skill-skeletons/_archive/sk-playwright-visual-regression-2026-04-15T...md`.
9. Return `status: ok` with draft path.

Caller (design-agent Step 4d) now adds `sk-playwright-visual-regression` to the frontend-qa candidate's `skills:` frontmatter, re-runs Step 4 (passes), continues to Step 7 interview-simulate where the new DRAFT is validated on the candidate.
