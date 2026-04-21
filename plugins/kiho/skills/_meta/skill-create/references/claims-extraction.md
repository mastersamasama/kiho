# Claims extraction protocol (v5.14)

Gate 11's v5.14 evaluator extracts a `claims[]` array from every transcript it reviews. A "claim" is any implicit factual, process, or quality assertion the skill made that could be verified independently. Uncertainty defaults to **FAIL** — the burden of proof is affirmative.

## Contents
- [Why extract claims](#why-extract-claims)
- [Types of claims](#types-of-claims)
- [Extraction procedure](#extraction-procedure)
- [Verification](#verification)
- [Uncertainty defaults to FAIL](#uncertainty-defaults-to-fail)
- [Integration with Gate 13 grader review](#integration-with-gate-13-grader-review)
- [Anti-patterns](#anti-patterns)
- [Grounding](#grounding)

## Why extract claims

A skill's response can pass the 4-dimensional rubric (tool use, error handling, scope, output shape) while quietly making factual claims that are wrong. Example: a skill that extracts text from a PDF might claim "this PDF has 12 pages" when it actually has 10. The 4 dimensions don't catch that — but a claims check does.

Claims extraction comes from `anthropics/skills/agents/grader.md`, which documents an 8-step grader process with an explicit `claims[]` field capturing "implicit factual/process/quality claims" that must be verified separately from the rubric scoring.

## Types of claims

Three kinds, each handled differently:

### Factual claims

The skill asserts a fact about the world, the input, or the system state. Example: "The input file has 12 pages." "The API returned 200 OK." "This function has 3 callers."

**Verification:** check against ground truth (the actual file, the actual response, the actual callgraph). If the ground truth is not accessible from the transcript alone, mark `verification: unreachable` — which routes into the "uncertainty defaults to FAIL" rule.

### Process claims

The skill asserts it performed a specific action. Example: "I used pdfplumber for extraction." "I added the record to the database." "I computed the hash over the file."

**Verification:** cross-reference against the tool-call log in the transcript. If the skill says it used pdfplumber but the log shows only a `Read` tool call, the claim is **false**.

### Quality claims

The skill asserts something about the quality of its output. Example: "This is the highest-confidence match." "The result is complete." "All edge cases are handled."

**Verification:** quality claims are often unprovable in isolation. Flag them as `verification: subjective` and let the evaluator apply the uncertainty rule. Most quality claims are rhetoric and should be rewritten as factual claims ("matched 0.87 on the confidence score") or removed.

## Extraction procedure

The evaluator subagent runs this procedure on each transcript:

1. **Read the full transcript** — response text + tool call log + any outputs.
2. **Identify sentences that make assertions.** Heuristic: sentences containing "has", "is", "was", "returned", "found", "extracted", "computed", "verified", "confirmed", "matches", "exceeds", "failed", "succeeded", past-tense verbs describing an action the skill took, or comparative/superlative claims.
3. **Categorize each sentence** as factual / process / quality.
4. **Emit a claim record** per sentence:
   ```json
   {
     "id": "c1",
     "type": "factual",
     "text": "the PDF has 12 pages",
     "source_span": "lines 23-23 in transcript",
     "verification": "pending"
   }
   ```
5. **Attempt verification** using the tool-call log, the input files, and the declared response shape.
6. **Set `verification`** to one of: `verified` (ground truth confirms), `false` (ground truth contradicts), `unreachable` (ground truth not accessible), `subjective` (quality claim with no ground truth).

## Verification

For each claim, verification runs these checks in order:

| Claim type | Check |
|---|---|
| Factual | Compare against tool outputs in the transcript (e.g., file stat, API response body, query result). If no tool output covers the claim, mark `unreachable`. |
| Process | Match the action name against the tool-call log. If the log shows the action, mark `verified`. If the log shows a different action, mark `false`. If the log is empty, mark `false` (the skill claimed it did X but never invoked any tool). |
| Quality | Mark `subjective`. The evaluator may downgrade the rubric's "instruction clarity" score if quality claims dominate the response. |

A claim with `verification: false` is an automatic Gate 11 failure — the transcript gets a low score on the relevant rubric dimension (usually "tool use correctness" for process claims, "scope adherence" for factual claims), and the transcript is flagged in the analysis.

## Uncertainty defaults to FAIL

From `anthropics/skills/agents/grader.md`: "uncertainty defaults to FAIL — the burden of proof is affirmative." kiho adopts this verbatim.

Practical implications:

- A claim with `verification: unreachable` is treated as a soft fail. The evaluator notes it in the rubric evidence but does not deduct points directly.
- If unreachable claims make up >50% of a transcript's claims, the whole transcript fails Gate 11 (`status: too_many_unverifiable_claims`) and the skill routes back to Step 5 with the guidance: "add deterministic outputs (file stats, counts, hashes) so claims become verifiable."
- The evaluator does NOT give the skill the benefit of the doubt when claims can't be checked. If the skill wants credit for a claim, the skill must produce evidence.

This is the same discipline as `anthropics/skills/agents/grader.md` step 8: "Only after you've verified every claim affirmatively, give a pass verdict."

## Integration with Gate 13 grader review

Claims extraction feeds Gate 13 (grader review) as follows:

1. Every claim with `verification: verified | false` is a graded grader output.
2. Gate 13 samples 10% of these claims deterministically (via `grader_review.py`).
3. For each sampled claim, kiho-kb-manager reviews whether the claim classification is correct (did the evaluator correctly identify this as a factual/process/quality claim?) AND whether the verification verdict is correct.
4. >10% disagreement on claim classification or verification routes the skill back to Step 9 — the issue is in the grader, not the skill.

This is the "graded graders" discipline from Anthropic's Jan 2026 Demystifying Evals post: you can't trust the evaluator's verdict unless the evaluator itself has been reviewed.

## Anti-patterns

- **Treating every statement as a claim.** Descriptive prose ("Here are the results:") is not a claim. Only assertions that could be true or false are claims.
- **Verifying quality claims via "I looked and it seems good."** Quality claims are subjective by definition. Mark them subjective and move on.
- **Giving the skill the benefit of the doubt on unreachable claims.** Uncertainty defaults to FAIL. If the skill wants credit, the skill must produce evidence.
- **Passing a transcript because the rubric scores are high but the claims are unverified.** A skill that scores 5/5 on all 4 rubric dimensions but makes 15 unverified factual claims is NOT a passing transcript. Claims extraction exists to catch that case.
- **Running claims extraction without a baseline.** The evaluator needs the input file (or a hash of it) to verify factual claims about the input. Gate 11's v5.14 benchmark.json + baseline.json pair provides this.

## Grounding

- `anthropics/skills/agents/grader.md` (raw at `https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/agents/grader.md`) — 8-step grader process, `claims[]` field, uncertainty-defaults-to-FAIL rule
- Anthropic "Demystifying Evals for AI Agents" (Jan 9 2026) — graded-graders principle
- kiho v5.14 Thread 1 and Thread 7 — full excerpt at `kiho-plugin/references/v5.14-research-findings.md`
