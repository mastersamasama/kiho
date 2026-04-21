---
name: skill-create
description: Deliberative greenfield skill authoring that produces a SKILL.md aligned with 2026 best practices through a 10-step validation pipeline. Takes a skill intent (domain, use cases, consumer agents, trigger phrases) and drafts a v2026 SKILL.md — iteratively improves the description until it passes 8 effectiveness rules, drafts topic-based body with progressive disclosure, generates scripts/references/templates only when justified, runs 10 validation gates (frontmatter syntax, description effectiveness, body structure, example presence, terminology consistency, script integrity, no time-sensitive content, dedup, security scan, eval suite), enforces the Lethal Trifecta rule, generates a 3-minimum eval suite, and registers as DRAFT. Differs from skill-learn (mines session experience), skill-derive (specializes parent skills), skill-improve (mutates existing skills) — this is for CREATING A NEW SKILL FROM SCRATCH aligned with standards. Use when a user, agent, or design-agent Step 4d needs a brand-new skill drafted deliberately to 2026 spec. Triggers on "create a skill", "author new skill", "draft skill for", "make skill", "skill-create", "new skill from scratch".
metadata:
  trust-tier: T3
  kiho:
    capability: create
    topic_tags: [authoring]
    data_classes: ["skill-definitions", "skill-drafts"]
---
# skill-create

Deliberative greenfield skill authoring. Where `skill-learn op=extract` mines session context and `skill-learn op=synthesize` finalizes a research-deep skeleton, `skill-create` takes a structured intent and produces a validated SKILL.md through a **24-gate pipeline** (v5.16) aligned with the 2026 SKILL.md open standard, OWASP Agentic Skills Top 10, the Snyk 8-category taxonomy, and the v5.16 hierarchical-catalog + capability-taxonomy + faceted-retrieval architecture.

## Non-Goals

skill-create is defined as much by what it refuses to do as by what it does. These are things that could reasonably be goals but are explicitly not:

- **Not a fast-path generator.** skill-create is deliberative by design — 24 gates run on every draft, and the pipeline can take multiple minutes even on a clean input. If you want to ship a skill in <30 seconds, use `skill-learn op=capture` instead.
- **Not an LLM judge at every gate.** Gates 1-9 and 14-17 are mechanical Python scripts. Only Gate 11 (transcript review, v5.14) calls a fresh skeptical evaluator subagent. This is a policy choice grounded in Anthropic's "Demystifying Evals" (Jan 2026): *deterministic gates should not call judges.*
- **Not a lint-only check.** skill-create does not just validate an existing draft — it produces a complete SKILL.md from a structured intent. If you already have a draft and want it validated without regeneration, use `skill-improve` with `failure_evidence: "initial lint"`.
- **Not a retroactive auditor.** The 24 gates run on NEW drafts only, not on the existing catalog. Catalog-wide health checks run under `bin/catalog_walk_audit.py` on a weekly schedule managed by kiho-kb-manager (v5.16) — that's a different workflow.
- **Not an automated promoter.** skill-create produces DRAFT-lifecycle skills only. DRAFT → ACTIVE promotion requires a passing `interview-simulate` on a consuming agent + CEO committee approval. There is no bypass.
- **Not a merge tool.** When Gate 17 detects a near-duplicate, the suggested action is `improve <top-match>` or `derive from <top-match>`, never "merge these two". Mechanical skill merging is an open problem in the 2024-2026 literature (see kiho v5.15 research findings H4); skill-create provides overlap inputs and lets humans drive the merge.
- **Not a multi-author collaboration tool.** One author per invocation. Conflicts between concurrent drafts are resolved via CATALOG regeneration + `kb-lint`, not via a merge algorithm inside skill-create.

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals. Lowercase "must", "should", "do not" remain informal prose guidance. This declaration applies to skill-create's own body text and to any prohibitions it surfaces during the 24-gate pipeline.

## Contents
- [Bundled resources](#bundled-resources)
- [When to use](#when-to-use)
- [Inputs](#inputs)
- [Pipeline overview](#pipeline-overview)

## Bundled resources

This skill bundles scripts and references alongside the SKILL.md body. The body is the quick reference; each bundled resource is the authoritative detail.

**Scripts** (deterministic, called via `Bash`):
- `scripts/score_description.py` — **fast binary gate**: 8-rule description effectiveness scorer. First-pass check. v5.14 adds precision/recall/F1 output alongside the binary verdict.
- `scripts/improve_description.py` — **iterative train/test rewriter** (v5.13): Anthropic-style workflow that generates 20 test prompts, splits 60/40 train/test, rewrites based on train-set failures only (blind comparison), reports final train/test accuracy + overfitting warning. Max 5 iterations. v5.14 adds "generalize away from failed queries" prompting and the stratified balanced split.
- `scripts/generate_triggering_tests.py` — **20-prompt corpus generator** (v5.13): deterministic 10 should-trigger + 10 should-not-trigger prompt set. v5.14 enforces stratified splits balanced by `should_trigger` true/false.
- `scripts/count_tokens.py` — **token budget helper** (v5.13): measures SKILL.md body tokens via tiktoken (fallback to word-count × 1.3). Used by Gate 3.
- `scripts/run_loop.py` — **iteration orchestrator** (v5.14): tracks multiple iterations of a draft skill, calls the comparator sub-agent, selects the current best using the non-monotonic rule, writes `run-loop.json`.
- `scripts/compute_discrimination.py` — **assertion-discrimination scorer** (v5.14): computes per-assertion delta between benchmark.json (with-skill) and baseline.json (without-skill). Used by the analyzer sub-agent and by Gate 12.
- `scripts/isolation_manifest.py` — **isolation manifest generator** (v5.14): walks the draft SKILL.md + scripts + references and lists every filesystem/env-var dependency, for Gate 12.
- `scripts/grader_review.py` — **grader review sampler** (v5.14): picks a 10% sample of graded transcripts per assertion and emits a review worksheet for kiho-kb-manager to audit. Gate 13.
- `scripts/catalog_fit.py` — **catalog-fit scorer** (v5.14): checks that a new skill's description overlaps its parent catalog node's `routing-description` by at least one substantive keyword. Gate 14.
- `scripts/budget_preflight.py` — **Claude Code budget pre-flight** (v5.14): sums all ACTIVE skill descriptions and compares against the 1%/8k char budget and the 1,536-char per-skill cap. Gate 15.
- `scripts/compaction_budget.py` — **post-compaction budget check** (v5.14): projects the 25k-token combined-skills ceiling after conversation summarization. Gate 16.
- `scripts/similarity_scan.py` — **novel-contribution similarity scan** (v5.15): compares the draft description against every existing skill's description via Jaccard on unigrams + bigrams. Blocks near-duplicates (Jaccard ≥ 0.60), warns on partial overlap (0.30-0.60), passes novel drafts. Gate 17.

**Agents** (sub-agents invoked by this skill):
- `agents/analyzer.md` — **v5.14**. Reads benchmark.json + baseline.json and produces analysis.json with assertion-discrimination scoring. Invoked at Step 10.5 (after Gate 11, before Step 11).
- `agents/comparator.md` — **v5.14**. Performs blind A/B comparison between two iterations of a draft skill; produces comparison.json. Enforces non-monotonic iteration.

**References** (progressive disclosure; loaded when SKILL.md body links out):
- `references/description-improvement.md` — full 8-rule binary spec + v5.13 train/test split workflow, blind comparisons, overfitting detection, v5.14 precision/recall/F1 scoring and "generalize away from failed queries" prompting
- `references/security-scan.md` — Gate 9 mechanical checks, secret regexes, v5.14 Snyk 8-category taxonomy, trust-tier protocol, 2.12× rule for script-bearing skills, delta-consent, remediation playbook
- `references/eval-generation.md` — Step 9 per-test-type generation procedures (basic, edge, refusal, triggering_accuracy, transcript_correctness), v5.14 capability/regression split, schema validation, minimum coverage rules
- `references/transcript-review.md` — Gate 11 procedure: simulate 3 invocations of the draft, capture transcripts, run blind review on tool use / error handling / scope / output shape. **v5.14: evaluator is a fresh skeptical subagent, never the author.**
- `references/analyzer-comparator.md` — **v5.14**. Full reference for the analyzer and comparator sub-agents, the analysis.json / comparison.json schemas, the non-monotonic iteration rule, and the per-iteration artifact layout.
- `references/claims-extraction.md` — **v5.14**. Protocol for extracting implicit factual/process/quality claims from Gate 11 transcripts; uncertainty defaults to FAIL.
- `references/novel-contribution.md` — **v5.15**. Gate 17 procedure, threshold rationale (Jaccard 0.60 block / 0.30 warn), tokenization rules, worked examples, failure routes (skill-improve vs skill-derive vs override), grounding in arXiv 2601.04748 semantic confusability.
- `references/deprecation-shim.md` — **v5.15**. The deprecation shim pattern used by `skill-deprecate`: shim body template, frontmatter markers, how skill-find/kb-lint/skill-create handle shims, consumer migration cadence, grounding in npm/cargo rename conventions.

**Plugin-level references** (shared across skills; live in `kiho-plugin/references/`):
- `kiho-plugin/references/skill-authoring-standards.md` — canonical rulebook for every kiho skill: frontmatter spec, description effectiveness rules, body rules, progressive disclosure, versioning, evals schema, security, validation gates, exit-code convention (v5.15.2). skill-create cites this at Gate 1 (frontmatter) and Gate 6 (script integrity).
- `kiho-plugin/references/skill-authoring-patterns.md` — **v5.15.2**. The 9 research-validated documentation patterns that every kiho reference doc should demonstrate: **P1 Non-Goals**, **P2 primary-source §-quotes**, **P3 playbook decision trees**, **P4 byte-identical worked examples**, **P5 Future-Possibilities with RFC 2561 disclaimer**, **P6 BCP 14 MUST NOT / SHOULD NOT**, **P7 MADR 4.0 ADRs with Considered Options**, **P8 gate tier ladder (tracked/warn/error)**, **P9 exit-code convention (0/1/2/3)**. skill-create uses this as its style guide — produced SKILL.md files should score ≥ 6/9 on the Review checklist. Gate 18 (v5.15.2) measures compliance at `tracked` tier.
- `kiho-plugin/references/v5.14-research-findings.md` — durable provenance anchor for v5.14 design decisions (analyzer/comparator, capability/regression split, Snyk taxonomy, trust tiers, catalog routing). Every v5.14 change cites this file.
- `kiho-plugin/references/v5.15-research-findings.md` — durable provenance anchor for v5.15 dependency + similarity design decisions (H1-H5 headlines, 10 Q&A, rejected alternatives, 36 primary-source URLs).

- [Step 1: Intake](#step-1-intake)
- [Step 2: Dedup check](#step-2-dedup-check)
- [Step 3: Frontmatter draft](#step-3-frontmatter-draft)
- [Step 4: Description iterative improvement](#step-4-description-iterative-improvement)
- [Step 5: Body draft with progressive disclosure](#step-5-body-draft-with-progressive-disclosure)
- [Step 6: Scripts, references, templates (optional)](#step-6-scripts-references-templates-optional)
- [Step 7: Ten validation gates](#step-7-ten-validation-gates)
- [Step 8: Security scan](#step-8-security-scan)
- [Step 9: Eval generation](#step-9-eval-generation)
- [Step 10.5: Analyzer pass + comparator (v5.14)](#step-105-analyzer-pass--comparator-v514)
- [Step 11: Register as DRAFT](#step-11-register-as-draft)
- [Frontmatter rules for the produced skill](#frontmatter-rules-for-the-produced-skill)
- [Response shape](#response-shape)
- [When to use skill-create vs sibling skills](#when-to-use-skill-create-vs-sibling-skills)
- [Anti-patterns](#anti-patterns)

## When to use

| Scenario | Use this skill |
|---|---|
| A brand-new skill is needed and no parent exists in CATALOG | ✓ |
| design-agent Step 4d has a Researchable gap with clear intent but no external docs to crawl | ✓ |
| An agent describes a pattern in a brief and wants it captured immediately | ✓ (combine with skill-learn op=capture for the content) |
| Mining session behavior for a pattern that already played out | **use `skill-learn op=extract`** |
| Finalizing a research-deep skeleton after BFS traversal | **use `skill-learn op=synthesize`** |
| Specializing an existing skill for a narrower use case | **use `skill-derive`** |
| Fixing a bug or adding steps to an existing skill | **use `skill-improve`** |

skill-create is the **cold-start** authoring skill. The others require prior content (session behavior, research skeleton, parent skill, existing SKILL.md).

## Inputs

```
intent:            short phrase — "what this skill does in one line"
domain:            _meta | core | kb | memory | engineering
consumer_agents:   list of agent-ids that will use this skill (can be empty)
trigger_phrases:   list of user/agent phrases that should activate the skill
use_cases:         list of concrete actions the skill performs (5-8 recommended)
sources:           optional list of URLs or KB entries informing the content
                   (passed through to the body + evals but NOT authoritative)
scripts_needed:    bool — does the skill bundle executable scripts?
references_needed: bool — does the skill need reference subdocs?
lifecycle_hint:    draft | active   (default draft; active only if caller is CEO)
risk_tier_hint:    low | medium | high   (security scan may override)
requestor:         agent-id of caller (design-agent, CEO, HR, user)
```

**Preconditions:** `intent`, `domain`, and at least 3 `trigger_phrases` are required. Missing any aborts with `status: incomplete_intake`.

## Pipeline overview

```
Step 1:   Intake            -> validated requirements dict
Step 2:   Dedup check       -> abort if duplicate in CATALOG (>0.70 overlap)
Step 3:   Frontmatter       -> draft name + description + optional fields
Step 4:   Description loop  -> two-phase: binary gate then iterative train/test rewriter
                               (v5.14: precision/recall/F1 + stratified split + "generalize away")
Step 5:   Body draft        -> topic-based sections with progressive disclosure plan
                               (token-budget enforced via count_tokens.py)
Step 6:   Resources         -> scripts/references/templates (conditional)
Step 7:   Validation gates  -> 24 hard checks (v5.16; was 17 at v5.15, 18 counting Gate 18 tracked); any failure routes back
Step 8:   Security scan     -> v5.14 Snyk 8-category + trust-tier + 2.12x rule + delta-consent
Step 9:   Eval generation   -> v5.14 capability/regression split + 5-minimum suite
Step 10:  Transcript review -> Gate 11: spawn draft on 3 scenarios, produce benchmark.json
                               AND baseline.json, review via fresh skeptical subagent (v5.14)
Step 10.5: Analyzer pass    -> v5.14. Compute assertion-discrimination, write analysis.json.
                               Run comparator if iteration > 1 (non-monotonic winner selection).
Step 11:  Register          -> DRAFT to .kiho/state/drafts/ + kb-add + experience-pool
```

Failure at any gate returns to the earliest relevant step. Max 3 total revision loops across all gates combined; then abort with `status: revision_limit_exceeded`.

**v5.14 changes from v5.13:**
- Step 4 description scoring now reports precision + recall + F1 (was binary only); gates on F1 / balanced accuracy
- Step 4 stratified split balanced by should_trigger true/false (was uniform random split)
- Step 4 rewriter prompting now tells the model to *generalize away from* failed queries rather than memorize them (per Mar 6 2026 anthropics/skills commit b0cbd3d)
- Step 8 security drops Lethal Trifecta framing in favor of Snyk 8-category taxonomy; adds trust-tier T1..T4, 2.12× rule for script-bearing skills, delta-consent auto-downgrade
- Step 9 eval generation separates capability/* from regression/* buckets (per Anthropic Jan 2026 "Demystifying Evals")
- Step 10 Gate 11 now uses a fresh skeptical evaluator subagent (never the author or the runner); produces baseline.json alongside benchmark.json
- **NEW Step 10.5** — analyzer pass computes assertion-discrimination; rejects skills whose >50% of assertions don't change outcomes; comparator picks the best iteration non-monotonically (best may be a middle iteration)
- Gate 7 now covers 16 validation gates:

**v5.15 changes from v5.14:**
- **NEW Gate 17** — novel-contribution similarity scan via `similarity_scan.py` runs after Gate 14 catalog-fit and before Gate 15 budget pre-flight. Jaccard on unigrams + bigrams. Blocks near-duplicates (≥0.60), warns on related drafts (0.30-0.60), passes novel drafts (<0.30). Full reference: `references/novel-contribution.md`. Grounding: arXiv 2601.04748 §5.3 semantic confusability.
- Step 3 frontmatter draft now prompts the author for `metadata.kiho.requires`, `metadata.kiho.mentions`, and `metadata.kiho.reads` (forward-only dependency declarations). All optional. No top-level `requires:` — spec-compliant only under `metadata.kiho.*`.
- New sibling skill `skills/_meta/skill-deprecate/` for the deprecation shim workflow — separate from `skill-improve` because deprecation is a lifecycle transition, not a FIX.
- New on-demand reverse-lookup script `bin/kiho_rdeps.py` — walks forward edges in SKILL.md frontmatter, agent portfolios, CATALOG parent_of, and wiki-link body mentions. Zero on-disk cache. Used by `skill-improve` Step 0 and `skill-deprecate` consumer review.
  12. isolation manifest (every fs/env dep declared and cleaned before each eval trial)
  13. grader review (10% sample audit of graded transcripts)
  14. catalog-fit (parent domain routing-description overlaps the new skill)
  15. budget pre-flight (1%/8k char catalog budget + 1,536-char per-skill cap)
  16. compaction budget (25k token post-summary ceiling across concurrently-loaded skills)
- Grounded in: Anthropic Mar 24 2026 "Harness design for long-running application development"; `anthropics/skills` commits `b0cbd3d` (Mar 6 2026) and `1ed29a0` (Feb 6 2026); AgentSkillOS arXiv 2603.02176; Snyk ToxicSkills Feb 5 2026; "Towards Secure Agent Skills" arXiv 2604.02837; full excerpt at `kiho-plugin/references/v5.14-research-findings.md`.

**v5.13 changes from v5.11:**
- Step 4 now two-phase (fast binary gate → slow iterative train/test rewriter)
- Step 5 now token-budget-enforced (≤5000 tokens body, not just line count)
- Step 9 eval minimum is now 5 tests (added `triggering_accuracy` + `transcript_correctness`)
- New Gate 11 (transcript review) runs before Step 11 register
- Grounded in Anthropic's Jan 2026 "Demystifying Evals for AI Agents" 8-step pattern

## Step 1: Intake

Validate inputs and build a `requirements` dict:

- `intent` — must be non-empty and under 200 chars
- `domain` — must be one of the 5 kiho domains
- `consumer_agents` — may be empty (general-purpose skill); if non-empty, verify each agent exists in `agents/` or `.kiho/state/org-registry.md`
- `trigger_phrases` — minimum 3, each 3–15 words, no duplicates
- `use_cases` — minimum 3 concrete actions; if the caller provides fewer, expand from the intent via a structured prompt
- `sources` — optional; record for provenance but do not treat as authoritative content
- `lifecycle_hint` — DRAFT is the default and only option unless the caller is CEO explicitly bootstrapping a trusted skill

Derive the skill's `name` candidate from the intent (slug it; verify ≤ 64 chars, kebab-case, no reserved words). If the derived name collides with an existing CATALOG entry, append a disambiguator.

## Step 2: Dedup check

Run Gate 8 early — bail before wasting work.

1. Read `skills/CATALOG.md`.
2. For each existing skill, compute description overlap against the intent + trigger phrases using word-set similarity.
3. If any existing skill has **overlap > 0.70**, abort with `status: duplicate, existing_skill_id: sk-NNN, similarity: 0.XX` and return the existing skill's path. The caller should use or extend the existing skill instead.
4. If overlap is 0.40–0.70, record as `status: similar` but continue — the draft frontmatter will include a `# Note: similar to sk-NNN` comment for reviewer awareness.
5. If overlap < 0.40, clear to proceed.

This runs at Step 2 (not Step 7) because early failure saves budget — no point drafting content for a duplicate.

## Step 3: Frontmatter draft

Use `templates/skill-frontmatter.template.md` as the canonical starting point. Fill in:

**Required fields:**
- `name` — from Step 1 (validated)
- `description` — first draft from intent + use_cases + trigger_phrases. Will be iteratively improved in Step 4.

**Kiho-required lifecycle fields:**
- `version: 0.1.0`
- `lifecycle: draft`
- `topic_tags` — derived from intent + use_cases

**Optional fields — include only with justification:**
- `argument-hint` — if the skill takes a single user-supplied argument
- `user-invocable` — default true; set false only for knowledge-only skills
- `disable-model-invocation` — set true ONLY if the skill has destructive side effects AND `risk_tier_hint != low`
- `allowed-tools` — only if the skill can justify narrowly-scoped tool pre-approval; never wildcards
- `model` / `effort` — only if the skill's reasoning requirements clearly differ from the caller's default
- `context: fork` — only if the body is >300 lines OR handles sensitive content
- `paths` — only if the skill applies to specific file extensions

**v5.15 `metadata.kiho.*` dependency block (all optional, forward-only):**
- `metadata.kiho.requires: [sk-NNN, ...]` — **hard** dependencies. If declared, `skill-deprecate` blocks deprecation of any listed target until this skill is migrated. Runtime is not enforced; the contract is enforced at evolution time.
- `metadata.kiho.mentions: [sk-NNN, ...]` — **soft** references. The body links to the listed skill (e.g., "see also") but does not execute it. `kb-lint` reports stale mentions but does not block.
- `metadata.kiho.reads: [kb/<path>.md, ...]` — KB page paths the skill consumes. `skill-improve` Step 0 warns when a proposed diff touches a section in this list.
- `metadata.kiho.supersedes`, `metadata.kiho.deprecated`, `metadata.kiho.superseded-by` — managed by `skill-deprecate`; authors do not populate these by hand.

Authors **MUST NOT** declare a top-level `requires:` field. All dependency declarations live strictly under `metadata.kiho.*`. Gate 2 frontmatter validation rejects top-level `requires:` as a spec violation per Claude Code issue #27113 ("not planned") and agentskills RFC #252 precedent — see [Rejected alternatives A5](#a5--top-level-requires-field-in-frontmatter).

**Gate 17 — novel-contribution similarity scan (v5.15):** After Gate 14 catalog-fit passes (domain fit check), run Gate 17 BEFORE Gate 15 budget-preflight:

```bash
python skills/_meta/skill-create/scripts/similarity_scan.py \
    --description "$(cat .kiho/state/drafts/sk-<slug>/description.txt)" \
    --catalog-root skills \
    --exclude .kiho/state/drafts/sk-<slug>/SKILL.md
```

Parse the output:
- `status: novel` → proceed to Gate 15.
- `status: related_review` → proceed to Gate 15 but include the top-3 matches in the committee proposal and acknowledge why this skill is distinct.
- `status: near_duplicate` → **STOP.** Exit this step with the `suggested_action` surfaced. The author must either (a) run `skill-improve` on the top match, (b) run `skill-derive` to specialize it, (c) tighten the draft description to reduce overlap and re-run Gate 17, or (d) escalate to the CEO committee for a `--force-overlap` vote.

The `--force-overlap` flag is not a retry button. It is a CEO committee decision point and every forced override is logged to `skill-invocations.jsonl` with the approving session ID.

**skill-create audit block** (populated by this skill at generation time):
```yaml
created_by: skill-create
created_at: {{iso_timestamp}}
validation_gates_passed: []          # filled after Step 7
security_risk_tier: {{risk_tier}}    # filled after Step 8
lethal_trifecta_check: pending       # filled after Step 8
iterative_description_score: 0       # filled after Step 4
iterative_description_loops: 0       # filled after Step 4
```

Every optional field added without a justification in `requirements` is stripped back out. The default should be a minimal frontmatter.

## Step 4: Description iterative improvement

The description is load-bearing — it's the primary trigger mechanism. v5.13 uses a **two-phase approach** grounded in Anthropic's official `skill-creator` workflow.

**Phase 1 — Fast binary gate (score_description.py).** Cheap filter for obvious failures.

```bash
python skills/_meta/skill-create/scripts/score_description.py <draft-literal-or-file>
```

Returns JSON with `score`, `passed`, and `diagnoses` array. 8 binary rules (concrete verbs, trigger phrases, pushy language, third-person, single paragraph, 50–1024 chars, no vague verbs, no meta-commentary). Pass threshold 0.85 (7/8). If the draft fails this gate, revise the failed rules specifically and re-score. Max 3 iterations here.

**Phase 2 — Iterative train/test rewriter (improve_description.py).** Anthropic-pattern validation via actual triggering simulation. Runs after Phase 1 passes.

```bash
# First generate the 20-prompt corpus
python skills/_meta/skill-create/scripts/generate_triggering_tests.py <intake-input.json> > corpus.json

# Then run the rewriter (it reads the corpus from its input)
python skills/_meta/skill-create/scripts/improve_description.py <improve-input.json>
```

The rewriter:
- Splits the 20-prompt corpus 60/40 train/test with a deterministic seed
- Scores the current description against BOTH sets, but only reveals train-set failures to the rewriter (blind comparison — the test set is held out)
- Rewrites based on train failures: missing trigger terms become additions, false-positive terms become disclaimers
- Re-scores, iterates max 5 times or until train accuracy ≥ 0.90
- Reports final train accuracy + test accuracy + overfitting warning if the gap > 0.20

Ship threshold: **test accuracy ≥ 0.75**. Overfitting warning: train/test gap > 0.20.

**Failure playbook — Step 4 (description improvement):**

- **Severity:** error (blocking; no DRAFT is registered)
- **Impact:** blocks skill-create at Step 4; no subsequent steps run. Root-cause is almost always an under-specified or over-broad intent.
- **Taxonomy:** `input` (intent too vague / too broad — caller bug) or `config` (trigger_phrases too generic — author should revise intent)

```
Step 4 result
   │
   ├─ Phase 1 score < 0.85 after 3 iterations       → Route 4-A  (binary rules failing)
   │
   ├─ Phase 1 ≥ 0.85, Phase 2 test acc < 0.75
   │   after 5 iterations, overfitting_warning=false → Route 4-B  (genuinely unlearnable)
   │
   ├─ Phase 1 ≥ 0.85, Phase 2 test acc < 0.75
   │   after 5 iterations, overfitting_warning=true  → Route 4-C  (train/test gap > 0.20)
   │
   └─ Phase 2 hits ship threshold                    → PROCEED to Step 5
```

- **Route 4-A — Binary rules failing.** The 8-rule scorer cannot reach 7/8. Read the `diagnoses` array in `score_description.py` output; fix the failing rules one at a time (concrete verbs, trigger phrases, pushy language, third-person, single paragraph, length, no vague verbs, no meta-commentary). If the same rule fails 3 iterations in a row, abort with `status: description_irrecoverable` — the intent is too vague or too broad for a discrete skill. Escalate to the caller to narrow the intent.
- **Route 4-B — Genuinely unlearnable.** The rewriter converged on a stable description but test-set accuracy stayed below 0.75 with no overfitting signal. This means the skill description *can* trigger consistently but *cannot* discriminate against the should-not-trigger prompts. Root cause is almost always domain overlap with an existing skill — run Gate 8 dedup diagnostics manually and check whether a sibling skill already covers this use case. If so, the intent should be redirected to `skill-improve` or `skill-derive` instead.
- **Route 4-C — Overfitting.** Train accuracy high, test accuracy low, gap > 0.20. The rewriter memorized the train set instead of generalizing. Regenerate the 20-prompt corpus with a different seed, or broaden the `trigger_phrases` input to include more variety. This is a Phase 2 retry, not a hard abort.

Aborts from Route 4-A return `status: description_irrecoverable` with the failing rule diagnoses attached. Aborts from Route 4-B return `status: description_irrecoverable` with a suggested redirect to a sibling skill-create variant. Route 4-C retries count against the 3-loop budget.

Full 8-rule spec, train/test split details, blind-comparison rationale, and worked examples in `references/description-improvement.md`.

Record in the audit block:
- `iterative_description_score` — Phase 1 binary score
- `iterative_description_loops` — Phase 1 iteration count
- `train_accuracy`, `test_accuracy`, `overfitting_warning` — Phase 2 results

## Step 5: Body draft with progressive disclosure

Draft the body as **topic-based reference material**, not step-by-step narration (except for genuinely procedural workflows — see §"Body rules" in skill-authoring-standards).

**Token budget (v5.13).** Body length is measured as **tokens**, not just lines. Run after each draft:

```bash
python skills/_meta/skill-create/scripts/count_tokens.py <skill-md-path>
```

| Token count | Verdict | Action |
|---|---|---|
| < 4000 | pass | continue |
| 4000–5000 | warn | consider moving a section to `references/` |
| 6000–8000 | reject | Gate 3 fail; move content to references |
| ≥ 8000 | hard_reject | skill is too broad; split into multiple skills |

The script uses tiktoken when available (cl100k_base encoding) and falls back to word_count × 1.3 otherwise. The warn zone catches body bloat before it becomes a Gate 3 reject.

**Canonical section order:**

1. `# <skill-name>` — H1 title matching frontmatter name
2. One-paragraph opening stating the skill's purpose (same voice as description, rewritten)
3. `## Contents` — table of contents (required if body > 100 lines)
4. `## When to use` — a decision table or bullet list making the trigger decision obvious
5. `## Inputs` — structured input schema (YAML block is fine)
6. `## Procedure` — the core content. For workflow skills, numbered steps (≤ 7). For reference skills, topic-based headings.
7. `## Configuration` — optional knobs and their rationale
8. `## Response shape` — structured return format (JSON schema or example)
9. `## Anti-patterns` — what NOT to do
10. Optional: `## Examples`, `## Troubleshooting`, `## Old patterns` (if any)

**Progressive disclosure plan:**

Before writing content, decide what goes where:

| Tier | Content | Target size |
|---|---|---|
| 1 — Metadata | name + description (already done in Step 3/4) | ~100 tokens |
| 2 — SKILL.md body | Quick reference for the most common operations | target ≤ 500 lines |
| 3 — `references/` | Detailed specs, edge-case handling, domain knowledge | loaded only when body links out |

**Rule (normative).** If content would push the body past 500 lines, split it into references. Authors **MUST NOT** nest references inside references — `references/foo.md` must not point at `references/foo/bar.md`. Gate 3 rejects nested reference trees. Rationale: Claude's progressive-disclosure retrieval collapses silently when a preview at `head -100` does not surface the target section; a flat one-level-deep layout is the only shape that reliably resolves.

**Writing discipline:**
- Imperative voice ("Read the file", not "You should read")
- Concrete examples for every key operation
- Consistent terminology throughout (pick one word per concept)
- Forward slashes in all paths
- No time-sensitive content ("as of 2026", "latest version") unless quarantined in `## Old patterns` with `<details>`
- No meta-narration ("You are loading this skill. Your job is...")

## Step 6: Scripts, references, templates (optional)

Only create these if the caller's `scripts_needed` or `references_needed` flags are true, OR if the body would exceed 500 lines.

### Scripts (`scripts/`)

Create a script when:
- The same code would be rewritten repeatedly
- Deterministic execution matters more than explanation
- The operation is fragile and error-prone

**Script requirements** (enforced by Gate 6):
- Explicit error handling (no bare `open(path)` without `try/except`)
- No voodoo constants (every magic number gets a comment explaining why)
- Cross-platform paths (`pathlib.Path`, forward slashes everywhere)
- `python -m py_compile` passes
- Input validation (no `os.system(user_input)`, no `shell=True` with untrusted args)
- Audit-trail logging for external API calls (endpoint, status code; NEVER response body)

### References (`references/`)

Create a reference file when:
- A topic would push SKILL.md body past 500 lines
- A domain-specific sub-area has its own expert knowledge (BigQuery `finance.md` vs `sales.md`)
- Large examples would clutter the body

**Reference requirements** (enforced by Gate 3):
- One level deep only — `references/foo.md` must NOT point to `references/foo/bar.md`
- Any reference >100 lines must have a table of contents
- Named descriptively: `form-validation-rules.md`, not `doc2.md`

### Templates (`templates/`)

Create a template when:
- The skill produces structured output that needs a scaffold
- Callers fill in placeholders rather than writing from scratch

Template files use `{{placeholder_name}}` syntax with inline comments explaining each placeholder.

## Step 7: Twenty-four validation gates

Run all 24 gates in order (was 10 in v5.11; 11 in v5.13; 16 in v5.14; 17 in v5.15; 18 in v5.15.2; **24 in v5.16**). Any failure returns to the earliest relevant step. Max 3 revision loops across all gates combined.

**v5.16 additions (Gates 19-24).** Primitive 1 (hierarchical walk-catalog) adds Gate 19 (routing sync); Primitive 2 (closed 8-verb capability taxonomy) adds Gate 20 (capability check); Primitive 3 (controlled topic vocabulary + faceted retrieval) adds Gate 21 (topic-vocab check) and Gate 22 (candidate-set attention budget — the new **primary attention gate** replacing token-count framing); Gate 23 (trigger uniqueness) and Gate 24 (agent portfolio density) close the remaining discoverability gaps. **Gate 3 (body token budget) is demoted to `warn` in v5.16** — body length is a kiho authoring preference, not a platform constraint or an attention failure. Gate 22 is the real attention gate.

See `references/skill-authoring-standards.md` for Gates 1-10 (still authoritative). Gate 11 → `references/transcript-review.md`. Gates 12-16 → their respective v5.14 references. Gate 17 → `references/novel-contribution.md`. Gates 19-24 → `references/v5.16-facet-retrieval.md`.

**Tier column.** Each gate carries a tier: **tracked** (metric logged, exit 0 always), **warn** (warning printed, exit 0), **error** (exit 1, playbook applies).

| Gate | Checks | tier | Failure action |
|---|---|---|---|
| 1 Frontmatter syntax | YAML well-formed, name 3–64 kebab-case, description 50–1024 chars, no reserved words; v5.14 adds skills-ref CLI cross-check and `metadata.trust-tier` presence | **error** | → Step 3 |
| 2 Description effectiveness | Phase 1 binary rules pass AND Phase 2 **test F1 ≥ 0.80 AND balanced_accuracy ≥ 0.80** (v5.14, was raw accuracy ≥ 0.75) | **error** | → Step 4 |
| 3 Body structure | Topic-based sections, TOC if >100 lines, references one level deep. Token count (≤ 5000 via count_tokens.py) reported but **no longer blocking** (demoted from error to warn in v5.16 — Gate 22 is the real attention gate) | **warn** | → Step 5 (advisory) |
| 4 Example presence | At least one concrete worked example per major operation | **error** | → Step 5 |
| 5 Terminology consistency | Same concept word throughout; no synonym mixing | **error** | → Step 5 |
| 6 Script integrity | Error handling, no voodoo constants, cross-platform paths, py_compile passes | **error** | → Step 6 |
| 7 No time-sensitive content | No "as of 2026" / "latest version" outside quarantined sections | **error** | → Step 5 |
| 8 Dedup | No existing skill in CATALOG with >0.70 overlap | **error** | abort `status: duplicate` (done in Step 2) |
| 9 Security scan | v5.14: Snyk 8-category taxonomy (secrets, prompt injection, malicious code, suspicious downloads, hardcoded creds, third-party content exposure, unverifiable deps, direct money access), trust-tier, 2.12× rule for script-bearing skills, delta-consent | **error** | → Step 5/6 or abort |
| 10 Eval suite | ≥5 tests covering basic, edge, refusal, triggering_accuracy, transcript_correctness; **v5.14: split into capability/ and regression/ buckets** | **error** | → Step 9 |
| 11 Transcript review | 3 scenarios spawn-and-review; **v5.14: fresh skeptical evaluator, never author or runner; produces both benchmark.json AND baseline.json**; pass = every transcript mean ≥ 4.0 AND no dim < 3.0 | **error** | → Step 5 |
| **12 Isolation manifest** (v5.14) | `isolation_manifest.py` lists every fs/env-var/network dep; the eval harness must clean them before each trial; skill must declare a cleanup procedure if side_effect_count > 0 | **error** | → Step 5/6 |
| **13 Grader review** (v5.14) | `grader_review.py` samples 10% of graded transcripts per assertion; kiho-kb-manager audits; >10% disagreement routes to Step 9 | **error** | → Step 9 |
| **14 Catalog-fit** (v5.14, hardened v5.16) | `catalog_fit.py` — new skill's description must overlap its parent catalog node's `routing-description` by at least one substantive keyword. v5.16 hardening: exit 1 `status: routing_block_missing` when the routing block is absent (regression test for the silent bug since v5.14) | **error** | → Step 3 |
| **15 Budget pre-flight** (v5.14) | `budget_preflight.py` — sum of all ACTIVE descriptions must stay under 90% of 1%/8k char budget; per-skill description+when_to_use ≤ 1,536 chars. Platform constraint only, NOT the organization mechanism | **error** | → Step 3 or abort `status: catalog_budget_exceeded` |
| **16 Compaction budget** (v5.14) | `compaction_budget.py` — projected post-summarization 25k-token ceiling across concurrently-loaded skills; warn if the new skill pushes the top-N recent-invocation set past 80% of ceiling. Platform constraint only | **warn** | → Step 5 (shrink body) |
| **17 Novel contribution** (v5.15) | `similarity_scan.py` — Jaccard on unigrams + bigrams between the draft description and every existing skill's description. Block at `Jaccard ≥ 0.60` with `suggested_action: improve <top-match>`. Warn at `0.30 ≤ Jaccard < 0.60`. CEO-only `--force-overlap` override. Full reference: `references/novel-contribution.md` | **error** | → Step 4 (tighten description), `skill-improve`, `skill-derive`, or CEO-approved override |
| **18 Pattern compliance** (v5.15.2) | Reviewer-driven check against `kiho-plugin/references/skill-authoring-patterns.md` §"Review checklist". Score ≥ 6/9 is the pass bar | **tracked** | → log result; surface `pattern_compliance_warnings`; do NOT block |
| **19 Routing-block sync** (v5.16) | `routing_sync.py` — verify that every `parent_of` entry resolves to a real non-deprecated skill in the declared domain/sub-domain, every ACTIVE skill appears in exactly one `parent_of`, and no deprecated skills are routed to. Nested dot-path support for hierarchical catalogs | **error** | → routing_gen.py regen or hand-fix |
| **20 Capability declared** (v5.16) | `capability_check.py` — frontmatter MUST declare `metadata.kiho.capability` from the closed 8-verb set in `kiho-plugin/references/capability-taxonomy.md` (create/read/update/delete/evaluate/orchestrate/communicate/decide) | **error** | → Step 3 (pick verb) or committee vote (extend set) |
| **21 Topic-vocabulary check** (v5.16) | `topic_vocab_check.py` — every entry in `metadata.kiho.topic_tags` MUST come from `kiho-plugin/references/topic-vocabulary.md`. Free-form tags are rejected | **error** | → Step 3 (pick vocab tag) or committee vote (extend vocab) |
| **22 Candidate-set budget** (v5.16, primary attention gate) | `candidate_set_budget.py` — simulates `skill-find` facet walk against the draft's own trigger phrases (description + `## When to use`) with the draft's capability + topic_tags forced. Worst-case candidate set after facet filtering MUST be ≤10. Replaces token-count framing as the primary organization metric | **error** | → Step 3 (add discriminating topic tag) or Step 4 (reconsider capability verb) or Gate 17 (genuine similarity) |
| **23 Trigger-phrase uniqueness** (v5.16) | `trigger_uniqueness.py` — pairwise Jaccard on `## When to use` / `trigger_phrases`. Block at ≥0.70 (stricter than description's 0.60 because triggers are literal) | **error** | → rewrite trigger phrase OR redirect to `skill-derive` |
| **24 Agent attention portfolio** (v5.16) | `agent_density.py` — per-agent skill-portfolio density across two axes. Per-capability warn ≥5 / error ≥8. Per-domain warn ≥8 / error ≥12. Runs at design-agent Step 4 + standalone audit | **warn** | → slim agent portfolio, split agent, or cascade to Gate 19 |

Gate 8 runs early (Step 2). Gates 14, 15, 17, 19, 20, 21 run in Step 3 (frontmatter). Gate 22 runs in Step 4 (post-description-improvement). Gate 23 runs in Step 3 or Step 5. Gate 9 runs in Step 8. Gates 1-7 and 16 run after every body revision. Gate 10 runs in Step 9. Gates 11, 12 run in Step 10. Gate 13 runs after Step 10.5 analyzer. Gate 18 runs after Step 11 register (post-flight audit, not pre-registration). Gate 24 runs at `design-agent` Step 4 and as standalone audit, not inside skill-create.

## Step 8: Security scan

Enforce OWASP Agentic Skills Top 10 and the Lethal Trifecta rule. Full spec with regex patterns, detection rules, risk-tier mapping, and remediation playbook in `references/security-scan.md`.

**Summary of the 6 mechanical checks:**

1. Secret detection across body + scripts + references + templates + evals
2. Input validation in scripts (no untrusted shell construction, no path traversal, no `eval()` on fetched content)
3. `allowed-tools` scope check (reject wildcards)
4. Tool wrapper check (reject skills < 20 lines of non-boilerplate)
5. Fail-closed defaults in scripts
6. Audit-trail logging (log endpoint + status, never response bodies)

**Lethal Trifecta:** evaluate the skill against three axes — private data access, untrusted content exposure, network egress. Skills hitting all 3 are blocked unless `disable-model-invocation: true`. Record `security_risk_tier` and `lethal_trifecta_check` in the audit block.

On hit, the remediation playbook in `references/security-scan.md` maps each failure to a concrete fix. Re-run Gate 9 after every revision.

## Step 9: Eval generation

Generate a minimum eval suite from the intent + trigger phrases + use cases + the 20-prompt corpus from `scripts/generate_triggering_tests.py`. Full per-test-type patterns, schema rules, and generation procedure in `references/eval-generation.md`.

**Minimum coverage (v5.13 — 5 tests, was 3):**
- 1 × `basic` (happy path)
- 1 × `edge` (ambiguous input; triggers uncertainty thresholds)
- 1 × `refusal` or negative test (red-line trigger if consumer agents given; else a superficially-similar out-of-scope prompt with `must_invoke_skill: false`)
- **1 × `triggering_accuracy`** (v5.13): uses the 10+10 corpus from `generate_triggering_tests.py`; passes if the skill correctly activates on should-trigger prompts and correctly ignores should-not-trigger prompts. Pass threshold: 80% accuracy on held-out test set.
- **1 × `transcript_correctness`** (v5.13): uses Gate 11 transcript review output as a durable regression test. Captures the 3-scenario review so future `skill-improve` mutations can re-run and compare.

**Recommended additional tests** (when `consumer_agents` is non-empty): `tool_use`, `coherence`, `drift`, `refusal_robustness`.

**Schema validation:** every test must have `id`, `test_type`, `scenario`, `must_invoke_skill`, `expected_behavior`, `rubric_dimensions`. Missing any field is a hard fail. Full schema in `templates/skill-evals.template.md`.

**Step 9 does NOT run the evals.** It only generates and validates the schema. Actual execution happens at Gate 11 (for triggering_accuracy and transcript_correctness, in-isolation) and at DRAFT → ACTIVE promotion via `interview-simulate(mode: full)` on a consuming agent (for all 5 test types).

## Step 10: Gate 11 transcript review (v5.13, evaluator-separated in v5.14)

After Step 9 generates the eval suite, run Gate 11 before proceeding to Step 10.5 analyzer pass.

**Procedure** (full detail in `references/transcript-review.md`):

1. Pick 3 scenarios from the `should_trigger` prompts in the 20-prompt corpus, maximizing diversity via pairwise content-word distance.
2. **First pass (with-skill):** Spawn the draft skill (ephemeral — not registered in CATALOG yet) against each scenario via `Agent` with the draft SKILL.md as inline system prompt. Capture: response text, tool calls, output shape, wall-clock time, token counts. Write `.kiho/state/drafts/sk-<slug>/iterations/<n>/benchmark.json`.
3. **Second pass (without-skill) — NEW v5.14:** re-run each scenario with the draft SKILL.md **removed** from the consuming agent's context (or replaced with an empty stub skill at the same path). Capture the same data shape. Write `.kiho/state/drafts/sk-<slug>/iterations/<n>/baseline.json`. This is the baseline for the analyzer pass.
4. **Blind review — NEW v5.14 evaluator separation:** spawn a **fresh skeptical evaluator** via `Agent(subagent_type="skill-create-analyzer", ...)` — NEVER the same agent that authored the skill, NEVER the same agent that ran the first or second pass. The evaluator's system prompt explicitly starts with "uncertainty defaults to FAIL; praise is affirmative and must be earned." It scores each transcript on 4 dimensions (tool use correctness, error handling, scope adherence, output shape match) on 1–5 without seeing the skill's self-scoring.
5. **Pass criteria:** every transcript has mean ≥ 4.0 AND no single dimension < 3.0 AND at least 2 of 3 scenarios ran cleanly.
6. **Claims extraction — NEW v5.14:** the evaluator also extracts a `claims[]` field from each transcript: implicit factual/process/quality claims the skill made. Any claim flagged `unverified` contributes to the Gate 13 grader review 10% sample audit. Full protocol in `references/claims-extraction.md`.

**Failure playbook — Step 10 (Gate 11 transcript review):**

- **Severity:** error (blocking; skill is not registered as DRAFT)
- **Impact:** blocks skill-create at Step 10; analyzer (Step 10.5) and register (Step 11) do not run. Content drift into Step 5 required.
- **Taxonomy:** `input` (body doesn't match description promises), `transient` (flaky scenario), or `config` (missing consumer-agent context)

```
Gate 11 result
   │
   ├─ ≥2 of 3 transcripts mean < 4.0                 → Route 10-A  (body drift; return to Step 5)
   │
   ├─ 1 of 3 transcripts failed, cause = transient    → Route 10-B  (retry the failed scenario once)
   │
   ├─ Any dimension < 3.0                             → Route 10-A  (hard failure on one dim — body drift)
   │
   ├─ Claims extraction shows > 50% unverifiable      → Route 10-C  (too_many_unverifiable_claims; Step 5)
   │
   └─ Gate 13 grader-review disagreement > 10%        → Route 10-D  (grader is the problem, not the skill)
```

- **Route 10-A — Body drift; return to Step 5.** The skill's body text promises behavior the transcripts do not demonstrate. The Step 5 retry carries the specific failing dimensions and the evaluator's `observations[]` array as guidance. Max 1 revision loop (counts against the overall 3-loop budget). If Route 10-A fires twice on the same draft, abort with `status: gate_11_irrecoverable`.
- **Route 10-B — Transient retry.** The failed scenario showed flaky behavior (e.g., intermittent tool error, timing-dependent output). Re-run that scenario once; if it passes, accept the set. If it fails a second time, it is not transient — reclassify as Route 10-A and go to Step 5.
- **Route 10-C — Unverifiable claims.** The evaluator's claims extraction found > 50% of factual/process claims cannot be verified against the tool-call log or input state. Per `references/claims-extraction.md`, uncertainty defaults to FAIL. Return to Step 5 with the unverifiable claims surfaced; the author should rewrite the body so that every claim is grounded in a deterministic tool output.
- **Route 10-D — Grader-review disagreement.** Gate 13 sampled 10% of graded transcripts and kiho-kb-manager disagreed with the grader's verdicts on > 10% of the sample. This means the **grader**, not the skill, is the problem. Return to **Step 9** (eval generation) to replace weak assertions, NOT to Step 5. The skill itself may be fine.

**Why this matters (grounded):**

> **Anthropic "Demystifying Evals for AI Agents" (Jan 9 2026), §step 7:** *"You won't know if your graders are working well unless you read the transcripts and grades from many trials."*
>
> **Anthropic "Harness design for long-running application development" (Mar 24 2026):** *"Tuning a standalone evaluator to be skeptical turns out to be far more tractable than making a generator critical of its own work."*

These two quotes drive Gate 11's design: transcripts are read (not just scored) and the evaluator is always a fresh skeptical subagent, never the author.

**Scope note:** Gate 11 ≠ design-agent Step 7. Gate 11 validates the skill **in isolation** before it's registered. design-agent Step 7 validates the **consuming agent** after the skill is available. Both run; they catch different failure modes.

## Step 10.5: Analyzer pass + comparator (v5.14)

After Gate 11 produces benchmark.json + baseline.json for the current iteration, run the analyzer sub-agent and (if iteration > 1) the comparator.

**Procedure** (full detail in `references/analyzer-comparator.md`):

1. **Analyzer pass.** Spawn `skill-create-analyzer` with `DRAFT_PATH`, `BENCHMARK_PATH`, `BASELINE_PATH`, `REQUEST_ID`. The analyzer runs `scripts/compute_discrimination.py` under the hood and produces `.kiho/state/drafts/sk-<slug>/iterations/<n>/analysis.json` with per-assertion discrimination deltas.
2. **Discrimination pool check.** If `discrimination_ratio < 0.50`, status is `rejected_non_discriminating` — route back to Step 9 to replace weak/saturated assertions (or Step 5 if the body is the problem). If `anti_count > 0`, status is `rejected_anti_discriminating` — route back to Step 5 with the anti-assertion evidence.
3. **If iteration > 1, run the comparator.** `scripts/run_loop.py --mode pair` writes a comparator input file pairing the current iteration against the existing current-best. Spawn `skill-create-comparator` with a blind A/B mapping (the seed randomizes which iteration is labeled A vs B). The comparator produces `comparisons/comparator-input-<req>.json` → comparator → `comparisons/comparison-<req>.json`.
4. **Non-monotonic winner selection.** `scripts/run_loop.py --mode summarize` walks all `comparisons/*.json` files, tallies wins, selects the current best. The winner is NOT necessarily the most recent iteration. If `non_monotonic_winner: true`, the winning iteration's SKILL.md is copied to `sk-<slug>/SKILL.md` and the newer iteration is retained only for lineage.
5. **Retry budget.** If the new iteration loses vs current best, run_loop may attempt one more iteration with the loser's `loser_weaknesses` injected as explicit guidance to Step 5. If the second retry also loses, halt with current best.

**Failure playbook — Step 10.5 (analyzer + comparator):**

- **Severity:** error (blocking for `rejected_anti_discriminating`), warn (recoverable for `rejected_non_discriminating`)
- **Impact:** blocks Step 11 registration. Either the eval suite is the problem (Step 9 retry) or the body is the problem (Step 5 retry). Analyzer's `decision_basis` field identifies which.
- **Taxonomy:** `input` (body drift) or `config` (eval suite has saturated/non-discriminating assertions)

```
analysis.json status
   │
   ├─ status: rejected_anti_discriminating           → Route 10.5-A  (Step 5; anti-assertions found)
   │   (any assertion with delta < 0.00)
   │
   ├─ status: rejected_non_discriminating             → Route 10.5-B  (Step 9 or Step 5 per decision_basis)
   │   (discrimination_ratio < 0.50)
   │
   ├─ status: insufficient_input                      → Route 10.5-C  (Gate 11 didn't emit files; re-run)
   │
   ├─ comparator verdict: both_fail                   → Route 10.5-D  (halt; revision_limit_exceeded)
   │
   └─ comparator verdict: new_wins | current_best_wins → PROCEED to Step 11 with winning iteration
```

- **Route 10.5-A — Anti-discrimination (skill made things worse).** Hard fail, return to Step 5 with the specific anti-assertions flagged. Anti-discrimination means adding the skill *reduced* pass rate on at least one assertion — the skill is actively harmful for that case. Root cause is almost always body content that overrides the consuming agent's normally-correct behavior.
- **Route 10.5-B — Non-discrimination (skill didn't help enough).** `discrimination_ratio < 0.50` means fewer than half of the assertions changed outcome when the skill was added. Analyzer's `decision_basis` field picks the return target: `body` → Step 5 (rewrite for more specificity), `eval_suite` → Step 9 (replace saturated assertions with harder ones).
- **Route 10.5-C — Insufficient input.** Gate 11 didn't emit benchmark.json or baseline.json. This is a Gate 11 infrastructure problem — re-run Gate 11 once. If it fails twice, the evaluator sub-agent is broken and the issue is a kiho bug, not an author error.
- **Route 10.5-D — Comparator both_fail.** Both the new iteration and the current best failed analyzer discrimination. This means the author's revision budget is spent and no iteration discriminates. Halt with `status: revision_limit_exceeded` and surface all iterations' `analysis.json` for CEO review. The CEO committee decides whether to re-scope the intent or retire the skill attempt.

Non-monotonic winner note: Route 10.5 passes happen at comparator verdict `current_best_wins` — the current best is NOT necessarily the most recent iteration. See `references/analyzer-comparator.md` for the non-monotonic selection rule.

**Record in audit block:**
```yaml
analyzer_decision: ok | rejected_non_discriminating | rejected_anti_discriminating
analyzer_discrimination_ratio: 0.67
analyzer_weak_assertions: [a3, a7]
run_loop_iterations: 3
run_loop_best_iteration: 2
non_monotonic_winner: true
```

## Step 11: Register as DRAFT

1. **Write SKILL.md** to `.kiho/state/drafts/sk-<slug>/SKILL.md`.
2. **Write `.skill_id` sidecar** with `sk-<slug>` (or a placeholder that `bin/catalog_gen.py` will assign a final ID).
3. **Write scripts/references/templates** into sub-directories if Step 6 produced any.
4. **Write evals.md** from Step 9 (5-test minimum).
5. **Write transcript-review.md** at `.kiho/state/drafts/sk-<slug>/transcript-review.md` — the Gate 11 review output. This is lineage, not part of the skill itself.
6. **Call `kb-add`** via kb-manager with:
   - `page_type: skill`
   - `lifecycle: draft`
   - `created_by: skill-create`
   - `validation_gates_passed: [1..11]`
   - `security_risk_tier: <tier>`
   - `gate_11_min_mean: <score>` — Gate 11 minimum transcript mean
   - `description_train_accuracy: <score>` — Phase 2 rewriter train accuracy
   - `description_test_accuracy: <score>` — Phase 2 rewriter test accuracy
7. **Call `experience-pool op=add_skill`** to register the skill pointer in the project pool.
8. **Return** the response shape (see below).

**What does NOT happen at Step 10:**
- The skill is NOT added to CATALOG.md (only ACTIVE skills are in CATALOG)
- The skill is NOT available for automatic invocation by other agents
- No `interview-simulate` run — that happens at promotion time

DRAFT → ACTIVE promotion is a separate workflow:
1. A consuming agent picks up the DRAFT (via design-agent Step 4d's Researchable path)
2. `interview-simulate(mode: full)` runs the eval suite
3. If all gates pass, CEO convenes the self-improvement committee
4. Committee approves → move skill from `.kiho/state/drafts/` to `skills/<domain>/<slug>/`, run `catalog_gen.py`, bump frontmatter `lifecycle: active` and `version: 1.0.0`

## Frontmatter rules for the produced skill

The produced SKILL.md frontmatter follows `templates/skill-frontmatter.template.md`. The `skill-create` audit block is added automatically:

```yaml
---
name: <skill-name>
description: <iteratively improved, passing 8 effectiveness rules>

version: 0.1.0
lifecycle: draft
topic_tags: [<derived from intent + use_cases>]

# ... optional fields only if justified ...

# Audit block (populated by skill-create)
created_by: skill-create
created_at: <iso>
validation_gates_passed: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
security_risk_tier: low | medium | high | trifecta
lethal_trifecta_check: passed | warning | blocked
iterative_description_score: 1.0
iterative_description_loops: 0
---
```

## Response shape

```json
{
  "status": "ok | duplicate | similar | description_irrecoverable | revision_limit_exceeded | security_blocked | incomplete_intake",
  "skill_id": "sk-<slug>",
  "skill_name": "<name>",
  "draft_path": ".kiho/state/drafts/sk-<slug>/SKILL.md",
  "evals_path": ".kiho/state/drafts/sk-<slug>/evals.md",
  "dedup_result": {"matched": "sk-NNN | null", "similarity": 0.XX},
  "validation_gates_passed": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "gates_failed": [],
  "security_risk_tier": "low",
  "lethal_trifecta_check": "passed",
  "iterative_description_score": 1.0,
  "iterative_description_loops": 0,
  "revision_loops": 0,
  "lifecycle": "draft",
  "kb_registered": true,
  "experience_pool_entry_id": "<ep-NNN>",
  "next_step": "DRAFT created. Run interview-simulate(mode: full) on a consuming agent to validate the eval suite, then CEO committee for promotion to ACTIVE."
}
```

## When to use skill-create vs sibling skills

| You have... | Use... | Why |
|---|---|---|
| An intent + trigger phrases + use cases, but no content yet | **skill-create** | Greenfield cold-start authoring |
| A session where the pattern already played out | `skill-learn op=extract` | Mines completed behavior; you don't need to draft from nothing |
| A specific code range to preserve as a skill | `skill-learn op=capture` | Direct code → skill conversion |
| A research-deep skeleton from BFS doc crawl | `skill-learn op=synthesize` | Finalization of an already-consolidated skeleton |
| An existing parent skill to specialize | `skill-derive` | Inheritance + narrowing, not greenfield |
| An existing skill that needs a bug fix or step added | `skill-improve` | Mutation of existing, with regression check |

skill-create is the **cold-start** case. If any of the other patterns fit, use that instead — skill-create's deliberative pipeline is overkill when the content already exists somewhere.

## Rejected alternatives

This section records design choices that could have gone differently and the evidence that drove the rejection. It follows the MADR 4.0 lightweight format: "What it would look like" → "Rejected because" → "Source". Future authors re-examining a decision should read the primary source first and decide whether the rejection still applies. This section **MUST NOT** be treated as permanent — re-opening a rejected alternative requires a CEO committee vote and a counter-evidence bundle.

### A1 — LLM judge at every gate

**What it would look like.** Replace the mechanical Python scripts behind Gates 1-9 and 14-17 with sub-agent calls. Every gate spawns a fresh judge sub-agent, feeds it the draft + the gate's criteria, and reads the verdict out of a structured JSON response.

**Rejected because.**
- **Non-determinism.** The same draft evaluated twice can produce different verdicts. CI reproducibility breaks; a failing Gate 3 on one run passes on the next.
- **Token cost.** At ~2000 tokens per judge call × 16 gates × 3 revision loops = ~96k tokens per skill-create run on mechanical gates alone. Gate 11 (the one gate that legitimately uses a judge) already consumes ~30-50k tokens. Doubling the judge footprint is prohibitive inside a single main-agent turn budget.
- **Explainability loss.** A judge verdict says "frontmatter fails" without naming the specific field. The mechanical `score_description.py` returns an 8-rule diagnoses array that identifies the failing rule by name.
- **Anthropic guidance.** *"Demystifying Evals"* explicitly warns against judges for deterministic checks: judges belong at Gate 11 where ground truth is unavailable, not at Gates 1-9 where ground truth is mechanical.

**Source:** Anthropic "Demystifying Evals for AI Agents" (Jan 9 2026) — https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents. Also grounding for Gate 11's evaluator-separation rule via Anthropic's Mar 24 2026 Harness Design post.

### A2 — Single-phase description loop (no train/test split)

**What it would look like.** Step 4 runs a single LLM rewrite of the description against a single scorer, without holding out any test prompts. The loop exits when the scorer passes.

**Rejected because.**
- **Overfitting invisibility.** A single-set scorer cannot distinguish "the description learned the trigger pattern" from "the description memorized these specific prompts". The rewriter games the score.
- **Empirical evidence.** Anthropic's `skills/skill-creator` commit `b0cbd3d` (Mar 6 2026) introduced the two-phase split specifically because the single-phase variant was producing high-score descriptions that failed in production. The split catches the gap: train accuracy stays high while test accuracy drops when the rewriter is memorizing rather than generalizing.
- **kiho-specific cost.** Phase 2's 20-prompt corpus costs a deterministic one-time generation (no rerun across revisions) and the train/test split is free. The upside (overfitting detection) dominates.

**Source:** `anthropics/skills` commit `b0cbd3df1533b396d281a6886d5132f623393a9c` (Mar 6 2026, `skills/skill-creator/scripts/improve_description.py`). kiho v5.14 research findings H1.

### A3 — Author self-evaluation at Gate 11

**What it would look like.** The agent that authored the skill also runs the transcript review — sees the transcripts it produced, scores them against the rubric, and decides whether Gate 11 passes.

**Rejected because.**
- **Leniency bias.** When Anthropic asked agents to evaluate their own work, they *"tend to respond by confidently praising the work — even when quality is obviously mediocre"* (Harness Design post, verbatim). A self-evaluator never says "this is bad".
- **Evaluator-generator separation is tractable; self-criticism is not.** A separate skeptical evaluator can be tuned to the "uncertainty defaults to FAIL" discipline. A self-evaluator cannot — any tuning toward skepticism also suppresses generation quality.
- **Claims-extraction needs a second pair of eyes.** Factual/process/quality claims are verified against the tool-call log, which the author already wrote. Having the author verify their own claims is a closed loop with no real check.

**Source:** Anthropic "Harness design for long-running application development" (Mar 24 2026) — https://www.anthropic.com/engineering/harness-design-long-running-apps. See also `references/claims-extraction.md` for the claims-verification protocol that builds on this.

### A4 — Flat CATALOG.md with no routing block

**What it would look like.** `skills/CATALOG.md` lists every skill at the same depth with descriptions only; no domain grouping, no `routing-description` per domain, no `parent_of` lists.

**Rejected because.**
- **Phase transition.** arXiv 2601.04748 §5.2 measures a phase transition in skill-selection accuracy: accuracy stays above 90% at |S| ≤ 20, degrades steadily past |S| = 30, collapses to ~20% at |S| = 200 on flat catalogs. kiho at 39 skills is already past the inflection.
- **Hierarchical routing scores 4× better.** AgentSkillOS (arXiv 2603.02176) measures Bradley-Terry scores of 100.0 for hierarchical routing vs 24.3 for flat routing at |S| = 200.
- **Gate 14 needs the routing block.** catalog_fit.py checks that a new skill's description overlaps its parent domain's routing-description. Without a routing block, Gate 14 cannot exist and the "wrong domain" failure mode is undetectable.

**Source:** arXiv 2601.04748 §5.2, §5.3 — https://arxiv.org/html/2601.04748v1. arXiv 2603.02176 (AgentSkillOS) §2.1.1 — https://arxiv.org/html/2603.02176v1. kiho v5.14 research findings H3.

### A5 — Top-level `requires:` field in frontmatter

**What it would look like.** Put dependency declarations at the top level of SKILL.md frontmatter: `requires: [sk-013, sk-016]` adjacent to `name` and `description`, not nested under `metadata`.

**Rejected because.**
- **Upstream rejection.** Claude Code issue #27113 proposed a top-level `dependencies` block and was closed "not planned" with no maintainer reasoning. Using a top-level field now would collide with any future upstream spec addition.
- **Precedent.** agentskills RFC #252 proposed a top-level `signature` field and was rejected on the precedent that *"structural metadata belongs outside the skill file when possible."* kiho follows the same precedent.
- **Gate 2 enforcement.** Frontmatter validation rejects top-level `requires:` as a spec violation. Forward-only dependency declarations live under `metadata.kiho.requires` per v5.15 (see `kiho-plugin/references/skill-authoring-standards.md` §"v5.15 additions").

**Source:** https://github.com/anthropics/claude-code/issues/27113. https://github.com/agentskills/agentskills/discussions/252. kiho v5.15 research findings H2.

### A6 — Auto-promote DRAFT → ACTIVE after Gate 17 passes

**What it would look like.** After Gate 17 passes at Step 3 bracket, skip the interview-simulate + committee-approval gate and write the skill directly into `skills/<domain>/<slug>/` with `lifecycle: active`.

**Rejected because.**
- **Supply-chain risk.** Snyk's ToxicSkills study (Feb 5 2026) scanned 3,984 community skills and found 13.4% critical security issues. Without a human-in-the-loop promotion gate, a malicious skill that passes all 17 mechanical gates could be auto-published — this is the ClawHavoc attack pattern.
- **CEO committee is the only human gate.** kiho's architectural invariant is that only the CEO agent interacts with the user, and committee approval is the only place a human decision enters the skill lifecycle. Auto-promotion would delete that check.
- **interview-simulate catches behavioral issues.** The Gate 11 transcript review validates the skill *in isolation* against synthetic scenarios. interview-simulate validates the skill *inside a consuming agent* against real-world rubric dimensions. They catch different failure modes.

**Source:** Snyk ToxicSkills study (Feb 5 2026) — https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/. kiho v5.14 research findings H4. `references/security-v5.14.md` for the full T1-T4 trust-tier protocol.

### A7 — Keep Gate 3 (body token budget) as the primary attention gate

**What it would look like.** Keep Gate 3 at **error** tier with a strict <5000-token body-length ceiling as the primary v5.16 attention gate. Do NOT add Gate 22 (candidate-set budget). Trust that short bodies correlate with good discoverability.

**Rejected because.**
- **Token count is a proxy, not the metric.** A 3k-token skill sitting in a cluster of 12 near-duplicates is *worse* than a 6k-token skill that is cleanly discriminated against every other skill. The failure mode at scale is *the agent cannot decide which skill to pick*, not *the context overflowed*. Gate 3 measures the wrong thing.
- **arXiv 2601.04748 §5.2 phase transition.** LLM skill-selection accuracy plateaus above 90% at |S|≤20, degrades past |S|=30, collapses to ~20% at |S|=200 on flat catalogs. The degradation curve correlates with *candidate set size*, not *per-skill body length*. Optimizing body length without addressing candidate set size is optimizing the wrong axis.
- **arXiv §5.3 semantic confusability dominance.** At identical |S|=20, replacing unique skills with base-competitor pairs causes an 18–30% accuracy drop. *Two similar skills hurt more than two extra unrelated skills.* A 3k-token skill in a tight cluster fails where a 6k-token skill in a clean neighborhood succeeds.
- **Empirical false positives and false negatives.** Gate 3 at error tier would reject skill-create itself (~10k tokens after v5.16 upgrades) — a self-hosted meta-skill with a known grandfather exemption. It would also accept a vague 2k-token skill that trips Gate 22 with a 13-skill candidate set. The correlation between body length and discoverability is too weak to justify the gate.
- **Migration evidence.** On the 38-skill Apr 2026 catalog, 6 skills initially tripped Gate 22 with `worst_case=13` (create-domain skills whose own description didn't contain discriminating topic-tag keywords). The fix was tightening topic tags — a discoverability fix — not shrinking bodies. Body-length adjustments would not have resolved any of those failures.

**Source:** arXiv 2601.04748 §5.2 + §5.3 (semantic confusability phase transition); kiho v5.16 plan Primitive 3 (faceted retrieval with ≤10 candidate-set ceiling); empirical Stage E verification on the 38-skill catalog showing topic-tag forcing resolved all 6 initial Gate 22 failures without body-length changes.

**Corollary.** Gate 3 is NOT deleted — it's demoted from `error` to `warn`. Body token count stays informational because authors still benefit from knowing when a body grows large, but it no longer blocks registration. Gates 15 (description budget pre-flight) and 16 (compaction budget) remain at their platform-constraint tiers; those measure Claude Code platform ceilings, not kiho's organization mechanism.

## Future possibilities (non-binding)

> **Non-binding note (Rust RFC 2561 convention, BCP convention):** *Having something written down in this section is not a reason to accept the current or a future proposal; such notes should be in the section on motivation or rationale in this or subsequent specs.* The items below are hints for the author who eventually picks each one up. They do not commit kiho v5.15.2 to any v5.16+ behavior, and they do not count as decisions.

### F1 — Gate 18 automation script (upgrade from tracked to warn/error)

**Trigger condition.** Gate 18 at `tracked` tier has ≥ 50 observations logged to `.kiho/state/gate-observations.jsonl` AND at least 5 of 9 patterns show a consistent detectable signature AND the kiho-kb-manager false-positive rate on the reviewer checklist is < 5%.

**Sketch.** Add `skills/_meta/skill-create/scripts/pattern_compliance.py` (~180 lines, no PyPI deps). Per-pattern heuristics: P1 grep for `^## Non-Goals\b`; P2 count `^> \*\*[^:]+§[^:]+:\*\* \*"` blockquotes; P3 grep for `^## Failure playbook\b|^## Failure routes\b` + ASCII tree heuristic; P4 count `^**Expected output:**` blocks; P5 grep for `Future possibilities\b.*RFC 2561`; P6 grep for `BCP 14|^### BCP 14|\bMUST NOT\b`; P7 grep for `^## Rejected alternatives\b` + count `^### A[0-9]` subsection; P8 grep for `tier.*tracked|warn|error` in gate table; P9 grep for `Exit codes:\s*\n\s*0 —` in script docstrings. Emit JSON with per-pattern score + aggregate. Graduation to `warn` tier happens when script + reviewer disagree < 10%; graduation to `error` tier happens one quarter after warn with < 10% disagreement rate.

**Estimate.** ~180 lines Python + ~40 lines docstring + tests. Reuses STOP_WORDS pattern from catalog_fit.py. Does NOT depend on any v5.16+ infrastructure.

### F2 — Catalog-health graduation

**Trigger condition.** The `--catalog-health` mean-pairwise Jaccard metric (currently at `tracked` tier with baseline 0.0146) exceeds 0.10 in a quarterly measurement, OR the top-pair Jaccard exceeds 0.30.

**Sketch.** Add `--health-block-threshold 0.30` and `--health-warn-threshold 0.10` flags to `similarity_scan.py`. On `--catalog-health`, compute mean-pairwise Jaccard + top-pair Jaccard. Exit 0 when both below warn threshold; exit 0 with warning when between warn and block thresholds; exit 1 when top-pair > 0.30. Wire into `bin/catalog_gen.py` as a post-hook: after regenerating CATALOG.md, run `similarity_scan.py --catalog-health` and surface warnings in the generator's output. Graduation to blocking requires a CEO committee vote and a manual audit of any existing pairs above threshold.

**Estimate.** ~40 lines added to similarity_scan.py + ~20 lines in catalog_gen.py.

### F3 — Regression harness for deployed ACTIVE skills

**Trigger condition.** Catalog size > 75 ACTIVE skills OR first known regression (an ACTIVE skill fails an inbound eval after a model upgrade).

**Sketch.** New `bin/replay_regression.py` (~400 lines). For every ACTIVE skill, load `evals/regression/*.md` and replay each test via `Agent(subagent_type=<consumer>, ...)` with the skill's SKILL.md pre-loaded. Compare output against the stored baseline (v5.14 capability/regression split). Emit pass/fail matrix to `.kiho/state/regression-replays/<timestamp>.jsonl`. Run monthly on a schedule; run on demand before any model-version upgrade. Does NOT mutate skills automatically — regressions are surfaced to the CEO committee for investigation.

**Estimate.** ~400 lines Python + schedule entry + CI hook. Depends on v5.14 capability/regression split (already shipped).

### F4 — Byte-identical worked-example verification CI (P4 full enforcement)

**Trigger condition.** ≥ 3 produced skills ship worked examples that drift from their referenced scripts (detected by post-merge diff against the author's baseline).

**Sketch.** Gate 4 upgrade: every worked example in a produced SKILL.md must include (input, expected output, status) triples AND every example MUST link to a `testdata/*.golden` file via a relative path. New `scripts/examples_verify.py` (~150 lines) — walks SKILL.md, extracts code blocks tagged `<!-- example-input -->` and `<!-- example-output -->`, runs the input through the referenced script, diffs actual vs expected, exits 1 on drift. Adopts the Go golden-file pattern verbatim.

**Estimate.** ~150 lines Python + Gate 4 upgrade + testdata/ convention documentation.

### F5 — Cross-model consensus at Gate 11

**Trigger condition.** Gate 11 evaluator false-negative rate exceeds 10% (measured via the grader-review disagreement metric from Gate 13), indicating the single evaluator is too strict or too lenient.

**Sketch.** Parallel spawn of two evaluator sub-agents with the same transcript bundle. Require agreement on pass/fail; on disagreement, route to a tie-breaker (either a third model or CEO committee). Cost tradeoff: doubles Gate 11's token budget, so graduation to standard usage requires committee authorization + demonstrated false-negative rate.

**Estimate.** ~100 lines added to the Gate 11 procedure + new evaluator sub-agent `agents/evaluator-b.md` with different system prompt tuning.

### F6 — mcp-scan as an advisory Gate 9 check

**Trigger condition.** Snyk's `mcp-scan` tool reaches 1.0 stable release AND the tool achieves T2 trust tier in kiho's v5.14 trust registry (≥3 agents × ≥2 sessions of reliable operation).

**Sketch.** New `scripts/mcp_scan_runner.py` (~80 lines) wraps the `mcp-scan` CLI, parses its JSON output, and maps findings into Gate 9's Snyk 8-category taxonomy. Runs at `warn` tier initially — surfaces findings to the author but does NOT block. Graduation to `error` tier requires ≥ 100 observations and a demonstrated < 10% false-positive rate. This is advisory only; Gate 9's primary checks remain the mechanical kiho scans.

**Estimate.** ~80 lines Python + trust-registry entry + committee authorization.

### Do NOT on the upgrade path

- **MUST NOT** introduce LLM judges at Gates 1-9. See [Rejected alternative A1](#a1--llm-judge-at-every-gate).
- **MUST NOT** skip the CEO committee at promotion. See [Rejected alternative A6](#a6--auto-promote-draft--active-after-gate-17-passes).
- **MUST NOT** persist any reverse-dependency cache to disk. H5 (compute-reverse-on-demand) applies across all v5.16+ work.
- **MUST NOT** switch from Jaccard to embeddings at Gate 17. See `references/novel-contribution.md` §"Rejected alternatives A2".
- **MUST NOT** add a new exit code outside 0/1/2/3 without a CEO committee vote. See `references/skill-authoring-patterns.md` §P9.

## Grounding

Every load-bearing design decision in skill-create is anchored in a primary source. Verbatim quotes are preserved so future authors can re-check the claim without reading the full source.

### Core research sources

> **arXiv 2601.04748 §5.2 (*When Single-Agent with Skills Replace Multi-Agent Systems*, Apr 2026):** *"At small scales (|S| ≤ 20), accuracy remains above 90%, but degrades steadily beyond |S| = 30, falling to approximately 20% at |S| = 200."*
>
> **arXiv 2601.04748 §5.3:** *"At identical |S| = 20, replacing unique skills with base-competitor pairs causes an 18–30% accuracy drop. This demonstrates that semantic structure determines selection difficulty."*

Used by: Gate 17 (novel contribution threshold calibration), [Rejected alternative A4](#a4--flat-catalogmd-with-no-routing-block).

---

> **Anthropic "Demystifying Evals for AI Agents" (Jan 9 2026), §step 7 (Review transcripts):** *"You won't know if your graders are working well unless you read the transcripts and grades from many trials."*

Used by: Gate 11 (transcript review, not score review), [Rejected alternative A1](#a1--llm-judge-at-every-gate), Step 9 capability/regression split.

---

> **Anthropic "Harness design for long-running application development" (Mar 24 2026):** *"Tuning a standalone evaluator to be skeptical turns out to be far more tractable than making a generator critical of its own work."*
>
> **Same source, same post:** *"I regularly saw cases where I preferred a middle iteration over the last one."*

Used by: Gate 11 evaluator-generator separation, [Rejected alternative A3](#a3--author-self-evaluation-at-gate-11), Step 10.5 non-monotonic iteration rule.

---

> **arXiv 2603.02176 (AgentSkillOS) §2.1.1:** *"If the number of skills in any generated category after Skill Assignment is equal to 1, that category and all its skills will be merged into the most relevant target category."*

Used by: CATALOG.md routing block (v5.14), Gate 14 catalog-fit, [Rejected alternative A4](#a4--flat-catalogmd-with-no-routing-block).

---

> **arXiv 2604.02837 §4 (*Towards Secure Agent Skills*, Mar 2026):** *"Because no static analysis tool can fully characterize the behavioral scope of natural language instructions, the gap between declared and actual behavior is not detectable at authorship time."*

Used by: Gate 17's rejection of AST-based similarity (see `references/novel-contribution.md` §A6), Gate 9's rejection of static-malicious-intent detection.

---

> **Snyk "ToxicSkills: Malicious AI Agent Skills" (Feb 5 2026):** 3,984 skills scanned, 13.4% with critical issues, 36.82% with any flaw, 76 confirmed malicious. 8-category taxonomy.

Used by: Gate 9 (Snyk 8-category security taxonomy), [Rejected alternative A6](#a6--auto-promote-draft--active-after-gate-17-passes), `references/security-v5.14.md`.

---

### Upstream skill-creator commits

**`anthropics/skills` commit `b0cbd3df1533b396d281a6886d5132f623393a9c` (Mar 6 2026).** The commit that introduced train/test split in `improve_description.py` and the "generalize away from failed queries" prompting. kiho's Step 4 Phase 2 is modeled on this commit's logic.

**`anthropics/skills/skill-creator/SKILL.md` (upstream reference):** has **no** pre-create similarity check, **no** per-gate mechanical validators outside the description loop, **no** hierarchical walk-catalog, **no** closed capability taxonomy, **no** controlled topic vocabulary, and **no** versioning/lifecycle metadata. kiho's 24-gate pipeline is an explicit kiho extension beyond the upstream reference — the divergence list lives in `kiho-plugin/references/skill-authoring-standards.md` §"kiho vs Anthropic skill-creator divergences".

### Full research archives

- `kiho-plugin/references/v5.14-research-findings.md` — v5.14 design decisions (analyzer/comparator, capability/regression split, Snyk taxonomy, trust tiers, CATALOG routing).
- `kiho-plugin/references/v5.15-research-findings.md` — v5.15 design decisions (forward-only deps, reverse-lookup, similarity scan, deprecation shim); includes 10 Q&A and 36 primary-source URLs.
- `kiho-plugin/references/skill-authoring-patterns.md` (v5.15.2) — the 9-pattern style guide; every pattern validated against a primary source in an isolated Apr 2026 research pass.

## Anti-patterns

- **Running skill-create when skill-learn fits.** If the pattern already played out in a session, extract from the session instead of drafting from scratch. skill-create is more expensive and has no signal from real use.
- **Adding optional frontmatter fields without justification.** Every optional field costs metadata tokens. Start minimal; add only fields you will use.
- **Bypassing the description iterative loop.** Manual description edits lose the 8-rule scoring. If you think you know better than the loop, you are undertriggering.
- **Skipping Step 9 eval generation.** A skill without evals cannot be validated at promotion time. DRAFT skills without evals are stuck as DRAFT forever.
- **Passing the Lethal Trifecta by adding `disable-model-invocation: true` without documenting why.** Trifecta risks require explicit user-in-the-loop patterns AND a rationale in the skill body's "Security" section.
- **Writing a skill that wraps a single tool.** Gate 9 rejects this as supply-chain bloat. Skills add domain knowledge, orchestration, or multi-step coordination — not tool pass-through.
- **Promoting DRAFT to ACTIVE without the committee gate.** Every DRAFT → ACTIVE transition requires: (1) passing `interview-simulate` on a consuming agent, (2) CEO committee approval. Skipping either is a CATALOG.md pollution risk.
- **Using skill-create for a one-off task.** Reuse likelihood < 0.50 means the pattern is not a skill; put it in the calling agent's memory as a lesson.
- **Ignoring dedup results in the 0.40–0.70 similar range.** Even "similar but not duplicate" skills pollute routing. Cite the similar skill in the draft and confirm the new skill has a distinct, non-overlapping use case.
- **Writing the description after the body.** The description is load-bearing and must be iterated first (Step 4). Body content that doesn't match the description is a Step 5 revision trigger.
