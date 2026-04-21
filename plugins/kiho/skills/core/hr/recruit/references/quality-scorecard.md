# recruit quality scorecard — 7-layer framework

Applies the industry-synthesis 7-layer skill-quality framework (Anthropic Demystifying Evals + HELM + LangSmith + PromptBench + Snyk ToxicSkills + AgentBench + Parnas precise-documentation) to `recruit` at v5.16.7.

**Core premise:** structural compliance (L1 patterns + gates) is *necessary but not sufficient*. A skill can pass all 24 deterministic gates and still degrade downstream task success by 19% (SkillsBench arXiv 2602.12670), contain prompt-injection markers missed by static pattern rules (Snyk found 36.82% of 3,984 public skills have security flaws), or under-trigger because its description works only on one canonical phrase.

This scorecard is the template for any future `skill-improve` quality pass. Replace "recruit" below with any skill name to reuse it.

## The 7 layers

| Layer | What it measures | How to measure | kiho mechanism |
|---|---|---|---|
| L1 Structural | Size, format, schema, metadata | Deterministic gates (pattern P1-P9, Gates 3/15/20/21) + audit script | `pattern_compliance_audit.py`, `count_tokens.py` |
| L2 Semantic / Retrieval | Description-based triggering accuracy | 20-query eval set × 3 runs, 60/40 train/test split | `score_description.py` (partial — scores rules not triggering), `similarity_scan.py`, `candidate_set_budget.py` |
| L3 Behavioral / Task | With-skill vs baseline task success | Paired runs with assertion-graded outputs, delta reporting | Gate 11 transcript review (one-shot at creation); smoke tests for regression |
| L4 Robustness / Adversarial | Holds under paraphrase, typo, distractor, injection | PromptBench 4-level attacks, `reliable@k` | **not implemented** |
| L5 Safety / Supply-chain | No injection payloads, secrets, malicious patterns | Static scan on body, OWASP Agentic Top 10 check | Gate 9 security scan; static regex patterns |
| L6 Efficiency / Cost | Tokens, latency, attention-budget load | Runtime instrumentation + batch `timing.json` | Gate 3 (input tokens only), Gate 22 (candidate-set) |
| L7 Operational / Telemetry | Production fire-rate, override rate, incident signals | `skill-invocations.jsonl`, user feedback | Per-project runtime only; structurally out-of-scope in plugin source |

## recruit scoring (v5.16.7, Apr 16 2026)

### L1 Structural — PASS (7/7 applicable)

| Signal | Result | Evidence |
|---|---|---|
| P1-P7 pattern audit | 7/7 applicable PASS | `pattern_compliance_audit.py --skill skills/core/hr/recruit/SKILL.md` → `score: 7/7, meets_threshold: true` |
| Gate 3 body tokens | 4634 warn | `count_tokens.py` — < 5000 warn max, headroom to reject 6000 |
| Gate 15 description budget | 1098 / 1536 PASS | manual char count |
| Gate 20 capability | `create` | in closed 8-verb set |
| Gate 21 topic_tags | `[hiring]` | in controlled vocab |
| Gate 22 candidate-set | worst_case=2 | very clean attention budget |
| Gate 23 trigger-phrase uniqueness | catalog-wide 0 collisions | `--all` mode passes |

### L2 Semantic — PARTIAL

| Signal | Result | Evidence |
|---|---|---|
| Description rule score | 0.875 (threshold 0.85) PASS | `score_description.py` |
| Description length rule | FAIL | 1098 chars > 1024 soft cap (but < 1536 hard cap) |
| Similarity catalog-wide | 0.0148 mean-pairwise Jaccard PASS | `similarity_scan.py --catalog-health` |
| **20-query trigger eval** | **NOT RUN** | Lever 1 from quality research; requires 60 invocations |

**Gap:** trigger-fire accuracy not measured. Description is rule-compliant and non-colliding, but unknown whether it *actually fires* on real user phrasings like "hire a backend dev", "add a frontend IC", "grow the PM team", or stays silent on near-misses like "improve the existing PM agent" (should route to `skill-improve`, not `recruit`).

### L3 Behavioral — UNMEASURED post-regeneration

| Signal | Result | Evidence |
|---|---|---|
| End-to-end smoke test | **NOT RUN** | scenario authored at `references/smoke-test.md`; not executed |
| Paired with-skill vs baseline | **NOT RUN** | Lever 2 from quality research |
| Gate 11 transcript review | not re-run post-regen | Gate 11 is a one-shot at creation; v5.16.3 plan reserves re-run for behavioral changes |

**Gap:** v5.16.6 integrated 5 research-driven adoptions (role-spec planner, work-sample dimension, per-dim floors, heterogeneity mandate, 8-round probe). None of these has been end-to-end validated with a real invocation. The new `role-spec.md` output format is documented but unverified against design-agent's actual Step 0 intake signature.

**Highest-ROI next step:** run Scenario 1 from `smoke-test.md` manually and capture the transcript as a regression anchor.

### L4 Robustness — NOT MEASURED

**Gap:** recruit has not been tested under paraphrased triggers, typo injection, or distractor prompts. Per IFEval++ (arXiv 2512.14754), nuanced rephrasing drops performance up to 61.8% on 46 LLMs. kiho's similarity scan catches duplication but not *paraphrase brittleness*.

**Follow-up:** generate 3-5 cousin phrasings per trigger (e.g., "recruit" → "hire", "staff up", "bring on", "onboard", "find someone for"). Measure `reliable@k` — does the skill fire on all variants?

### L5 Safety / Supply-chain — PASS

Static scan run Apr 16 2026 against OWASP Agentic Top 10 + Snyk 8-category patterns:

| Pattern | Result |
|---|---|
| Prompt injection markers (`ignore previous`, `override instructions`) | 0 hits |
| Role-override phrases (`role: system`, fake system prompts) | 0 hits |
| Hardcoded secrets (`password=`, `api_key=`, `token=`) | 0 hits |
| Shell command payloads (`subprocess.`, `os.system`, `curl ... | sh`) | 0 hits |
| Script injection (`<script`, `javascript:`, `eval(`) | 0 hits |
| External URL allowlist | All 6 URLs from trusted domains (kubernetes.io, arxiv.org, anthropic.com, geoffreylitt.com, ubalt.edu, washington.edu) |

recruit's body is clean of supply-chain attack markers.

### L6 Efficiency — PARTIAL

| Signal | Result |
|---|---|
| Input tokens (body) | 4634 warn |
| Input tokens (frontmatter description) | ~275 (1098 chars × 0.25 tokens/char estimate) |
| Candidate-set attention budget | worst_case=2 (very efficient for retrieval) |
| Runtime tokens / latency | **NOT INSTRUMENTED** — requires per-invocation telemetry |

**Gap:** no runtime cost data. Cannot answer "is this skill getting cheaper or more expensive over time?" until L7 telemetry exists.

### L7 Operational — OUT OF SCOPE

kiho's "no persistent runtime DB as source of truth" constraint (CLAUDE.md Non-Goal #1) means operational telemetry lives per-project in `.kiho/state/skill-invocations.jsonl` (Tier-2 JSONL). Plugin-source audit cannot measure this layer.

**Substitute:** F1 (regression harness for deployed skills) from skill-create's Future possibilities would periodically re-run smoke tests and surface drift.

### Evidence fidelity (part of L4, added by this audit)

**Citation verification run Apr 16 2026** against 4 of 6 Grounding URLs via WebFetch:

| Source | Verbatim match? | Fix applied |
|---|---|---|
| Anthropic Harness Design §sprint criteria | ✓ exact match | none |
| Anthropic Multi-Agent Research §delegation | ⚠️ paraphrase drift | rewrote quote to actual verbatim (Apr 16) |
| arXiv 2402.10962 persona drift | ⚠️ paraphrase drift | rewrote quote to actual verbatim (Apr 16) |
| Allen School Hivemind article | ✗ 60% claim not in article | removed unsupported figure, kept general correlated-errors framing (Apr 16) |
| MAST arXiv 2503.13657 percentages | ⚠️ approximate values | updated to paper's actual Figure 2 values ≈ 40/35/25 (Apr 16) |
| Schmidt-Hunter 1998 r-values | not re-verified | accepted as widely-cited consensus values; marked for future manual check |

**Lesson:** paraphrase drift is the dominant citation failure mode. Quoting the research agent's *summary* rather than re-fetching the source is the bug. Mitigation: for every `> **Source:** *"..."*` blockquote, the author MUST re-fetch the URL and diff the quote against source text before committing.

## Quality posture summary

| Layer | Status | Next lever |
|---|---|---|
| L1 Structural | **PASS** | maintain via lazy graduation |
| L2 Semantic | **PARTIAL** | Lever 1: 20-query trigger eval with 60/40 split |
| L3 Behavioral | **UNMEASURED** | Lever 2: execute `smoke-test.md` Scenario 1 manually; capture transcript |
| L4 Robustness | **NOT MEASURED** | Lever 3: cousin-prompt probe (3-5 paraphrases per trigger) |
| L5 Safety | **PASS** | maintain via pre-commit static scan |
| L6 Efficiency | **PARTIAL** | Lever 5: LLM-as-judge on body (naming, S/N, progressive disclosure) |
| L7 Operational | **OUT OF SCOPE** | F1 future possibility — regression harness |

**Current overall rating**: L1 + L5 solid; L2 + L6 partial with known gaps; L3 + L4 untested; L7 structurally deferred. This is a **typical post-regeneration state** — the rewrite closed structural gaps but couldn't close behavioral gaps without runtime execution.

## How to raise recruit's quality (prioritized)

**Tier 1 — ≤ 1 day of work each:**
1. **Execute smoke-test Scenario 1.** Capture the transcript. If any phase deviates from expected, file specific defects. Highest ROI — directly addresses L3.
2. **Fix L2 description length rule.** Trim frontmatter description from 1098 → ≤ 1024 chars. Gate 2 moves from 7/8 rules to 8/8.

**Tier 2 — ≤ 1 week of work each:**
3. **Run the 20-query trigger eval.** Author the corpus (≈ 10 should-trigger + 10 near-miss), run recruit's description against it 3× via a test harness, iterate up to 5 rounds. Closes L2 gap.
4. **Cousin-prompt robustness probe.** Generate 3-5 paraphrases per trigger phrase; measure `reliable@k`. Closes L4 gap for triggering.
5. **LLM-as-judge on body.** Single rubric evaluator scoring naming / examples-over-rules / why-inclusion / signal-to-noise / progressive-disclosure / failure-mode guidance. Output stored as `references/body-rubric.md`. Closes qualitative L1/L2 gaps.

**Tier 3 — architectural:**
6. **F1 regression harness.** Automate smoke-test scenarios to run on every `skill-improve` pass. Addresses L3 + L7 jointly.
7. **Extract role-spec planner to its own `_meta/` skill.** Would let design-agent Step 0 reuse the same planner. Reduces duplication, surfaces contract between recruit + design-agent.

## Reusing this scorecard for other skills

This framework generalizes. To score any skill `<target>`:

1. Run `pattern_compliance_audit.py --skill <path>` → fill L1 row.
2. Run `score_description.py` + `similarity_scan.py --catalog-health` + `candidate_set_budget.py --draft <path>` → fill L2 row.
3. Author a `references/smoke-test.md` with ≥ 1 canonical scenario → L3 follows.
4. Generate cousin prompts → L4.
5. Grep for OWASP Agentic Top 10 patterns → L5.
6. Run `count_tokens.py` + measure candidate-set budget → L6.
7. Check `.kiho/state/skill-invocations.jsonl` if it exists in the target project → L7.

The scorecard is a reusable audit artifact, not a one-time recruit exercise.
