# Security v5.14: Snyk 8-category taxonomy, trust tiers, 2.12× rule, delta-consent

This file replaces the "Lethal Trifecta" framing from v5.11–v5.13. The trifecta rule wasn't wrong — it was incomplete. v5.14 adopts the **Snyk ToxicSkills 8-category taxonomy** (Feb 5 2026) as kiho's canonical threat labels, layered with the **4-tier trust model** from arXiv 2602.12430 and the **delta-consent** primitive from arXiv 2604.02837.

## Contents
- [Why this replaces Lethal Trifecta](#why-this-replaces-lethal-trifecta)
- [The 8-category taxonomy](#the-8-category-taxonomy)
- [Trust tiers T1..T4](#trust-tiers-t1t4)
- [The 2.12× rule for script-bearing skills](#the-212-rule-for-script-bearing-skills)
- [Delta-consent: re-approval on substantial change](#delta-consent-re-approval-on-substantial-change)
- [What kiho does NOT do](#what-kiho-does-not-do)
- [Gate 9 procedure](#gate-9-procedure)
- [Grounding](#grounding)

## Why this replaces Lethal Trifecta

The Lethal Trifecta (private data access + untrusted content exposure + network egress) is a good mental model but only catches skills that hit all three axes simultaneously. Three 2026 primary sources all conclude that the threat model is wider:

- **Snyk ToxicSkills (Feb 5 2026)** scanned 3,984 ClawHub skills and found **13.4% have at least one critical issue**, **36.82% have any flaw**, and **76 confirmed malicious payloads** — distributed across 8 distinct threat categories, not 3.
- **arXiv 2602.12430 "Agent Skills for LLMs: Architecture, Acquisition, Security"** (Feb 2026) scanned 31,132 community skills and found **26.1% have vulnerabilities**. It establishes that **scripts increase vulnerability risk by 2.12×** compared to instructions-only skills.
- **arXiv 2604.02837 "Towards Secure Agent Skills"** (March 2026) publishes a 7-category threat taxonomy across 3 layers and concludes that **static AST analysis cannot solve malicious intent detection** because SKILL.md collapses the data/instructions boundary in natural language. It pivots to runtime + versioning controls.

The consensus:

1. The threat surface is broader than the trifecta's 3 axes.
2. Scripts are significantly riskier than prose.
3. Static intent detection is a dead end — pivot to runtime, provenance, and change-based controls.
4. Trust is tiered and revocable, not binary.

## The 8-category taxonomy

From Snyk ToxicSkills, adopted as kiho's canonical security-scan label set in Gate 9:

| # | Category | What to look for |
|---|---|---|
| 1 | **Prompt injection** | Instructions embedded in data the skill reads; attempts to override the calling agent's system prompt; "ignore previous instructions" patterns; indirect injections via fetched URLs |
| 2 | **Malicious code** | Destructive commands (`rm -rf`, `DROP TABLE`, `format`), code that modifies its own source, unexplained base64 blobs, eval() on fetched content |
| 3 | **Suspicious downloads** | `curl`/`wget`/`pip install` of URLs that are not well-known CDNs or official repos; binary fetches; unvalidated tarball extraction |
| 4 | **Credential handling** | Skills that touch `.env`, `~/.aws`, `~/.ssh`, `credentials.json`, keyring access without justification |
| 5 | **Hardcoded secrets** | API keys, tokens, passwords, private keys embedded in the skill body, scripts, or templates (also covered by the existing secret-regex check) |
| 6 | **Third-party content exposure** | Skills that fetch untrusted URLs and feed the content back into the prompt context without sanitization — the "indirect prompt injection" vector |
| 7 | **Unverifiable dependencies** | Scripts that import from non-standard-library packages without pinning versions; `pip install` in the skill body; dependencies on git URLs |
| 8 | **Direct money access** | Skills that touch payment APIs (Stripe, PayPal, etc.) without an explicit user-in-the-loop gate; skills that can spend budget (cloud, LLM API) without a cost cap |

Gate 9 runs deterministic regex + heuristic checks for each category and flags hits with a concrete category label. Multi-category hits score cumulatively.

## Trust tiers T1..T4

Every kiho skill carries `metadata.trust-tier: T1 | T2 | T3 | T4` in frontmatter. Tier is enforced at every read and at every write.

| Tier | Label | Meaning | Who can promote TO this tier |
|---|---|---|---|
| T1 | unvetted | Just created by skill-create; passed basic gates but has no runtime track record | skill-create default at DRAFT creation |
| T2 | community | Used by ≥3 different agents across ≥2 separate sessions without regression | automatic via skill-learn telemetry |
| T3 | trusted | Committee-approved ACTIVE skill with clean Gate 11 + analyzer + run_loop history | CEO committee |
| T4 | fully-trusted | Long-running ACTIVE skill with regression bucket populated and zero regressions over ≥30 days | CEO explicitly, with user approval |

**Promotion rules:**

- T1 → T2: **automatic**, via `experience-pool` telemetry when the use + session thresholds are met.
- T2 → T3: **CEO committee decision only**, via the self-improvement committee.
- T3 → T4: **CEO + user approval**, because T4 skills can be invoked by other T4 skills without further checks.
- Any tier → lower: **automatic on delta-consent trigger** OR committee decision.

**Read rules:**

- A T1 skill can only be invoked by the agent that created it AND only in the session where it was created. No cross-agent or cross-session use.
- A T2 skill can be invoked by any agent but only within the originating project.
- A T3 skill can be invoked across projects within the same `$COMPANY_ROOT`.
- A T4 skill can be invoked by other T4 skills without further trust checks.

**Write rule:** `kb-add` rejects promotion requests that skip a tier. T1 → T3 requires going through T2 first.

## The 2.12× rule for script-bearing skills

From arXiv 2602.12430: scripts (Python, shell) increase a skill's vulnerability risk by **2.12×** relative to instructions-only skills. kiho enforces this by applying heavier validation to any skill containing non-empty `scripts/` content:

| Check | Instructions-only skill | Script-bearing skill |
|---|---|---|
| Eval suite minimum | 5 tests | **5 tests + 1 additional adversarial test** |
| Gate 11 transcript review | 3 scenarios | **3 scenarios + 1 adversarial scenario** |
| Token budget for body | 5000 | **4500** (reserve 500 for the required "Security" section) |
| Gate 13 grader review sample rate | 10% | **15%** (smaller pool per assertion, reviewer looks harder) |
| Trust tier at DRAFT creation | T1 | T1 (same) but with `script_scan_required: true` |
| Delta-consent threshold | 10% body change | **5% body or any script change** |

Any skill with scripts must also include a `## Security` section in its body justifying the scripts' presence, enumerating their side effects, and explaining the fail-closed default.

## Delta-consent: re-approval on substantial change

From arXiv 2604.02837: the biggest ClawHavoc-class attack vector is **trust-by-installation** — a skill gets approved once and then mutates. Delta-consent prevents this by requiring re-approval when a skill changes substantially.

**Trigger:** on every `skill-improve` mutation, `kb-manager` computes the byte-level diff against the prior version.

| Change size | Script-bearing? | Action |
|---|---|---|
| < 5% | no | auto-accept, log |
| 5–10% | no | auto-accept, log, notify CEO |
| > 10% | no | downgrade to T1, re-run full Gate 11 + 12 + 13, CEO committee for re-promotion |
| < 5% | yes | log, notify CEO, **any script change at all triggers the next row** |
| any script change | yes | downgrade to T1, re-run Gate 9 + 11 + 12 + 13, CEO committee for re-promotion |

**Implementation:** kb-manager's `kb-update` operation calls `bin/delta_consent.py` (a narrow Python helper — not yet in kiho but referenced here for future addition) which emits the diff percentage and the script-change flag. The `kb-update` handler then routes accordingly.

**Why this matters:** a T3 skill that quietly rewrites its body between sessions is the exact ClawHavoc pattern. Delta-consent makes the mutation visible and forces it back through the committee gate.

## What kiho does NOT do

These are deliberate non-goals, documented so future sessions don't re-add them:

1. **No AST-based malicious-intent detection.** Three independent papers (2510.26328, 2604.02837, 2602.12430) all concluded this is fundamentally infeasible because SKILL.md blurs the data/instructions boundary. kiho uses deterministic regex + category labeling + runtime controls instead.
2. **No external malicious-skill scanner as a hard gate.** Tools like Snyk's `mcp-scan` are excellent, but coupling kiho to a third-party tool's release cadence creates fragility. kiho may run `mcp-scan` advisorily but never as a blocking gate.
3. **No cross-model consensus judging at Gate 11.** The Demystifying Evals Swiss Cheese Model would suggest it, but kiho's single-turn budget and CEO-only-user-interaction rule make it too expensive. Single-judge with the separated-evaluator pattern is sufficient.
4. **No auto-promotion past T2.** Every T2 → T3 and T3 → T4 transition requires a CEO committee decision. Automating past T2 would reintroduce the ClawHavoc install-once-trust-forever pattern.
5. **No runtime sandbox.** Claude Code does not provide skill-level sandboxing; adding one to kiho would require a Claude Code feature we do not control. Trust tiers + delta-consent + pre-deployment gates are kiho's substitute.

## Gate 9 procedure

Step 8 security scan in skill-create runs Gate 9 with the following procedure:

1. **Category scan.** For each of the 8 Snyk categories, run the category-specific deterministic check against body + scripts + references + templates. Record hits with the category label.
2. **Trust-tier enforcement.** Confirm `metadata.trust-tier` is set to `T1` (skill-create default). Reject any other value at creation time.
3. **Script detection.** Check for non-empty `scripts/` directory. If present, set `script_scan_required: true` and apply the 2.12× rule.
4. **Delta-consent precondition.** For skill-improve flows (not skill-create), compute the diff percentage against the prior version and enforce the table above. For skill-create (greenfield), delta-consent does not apply.
5. **Remediation routing.** On any category hit with `severity: blocking`, return `status: security_blocked` with the category and the specific hit. On `severity: warning`, record in audit block but allow.
6. **Audit block update.** Write:
   ```yaml
   security_category_hits: [prompt_injection, hardcoded_secrets]
   security_severity: warning | blocking
   trust_tier: T1
   script_scan_required: true
   delta_consent_applicable: false
   ```

## Grounding

Primary sources for the v5.14 security rework:

- **Snyk ToxicSkills** (Feb 5 2026) — https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/ — the 8-category taxonomy and scan-rate numbers
- **arXiv 2602.12430 "Agent Skills for LLMs: Architecture, Acquisition, Security, and the Path Forward"** (Feb 2026) — the 4-gate / 4-tier framework and the 2.12× rule
- **arXiv 2604.02837 "Towards Secure Agent Skills"** (March 2026) — delta-consent and the "no AST static analysis" conclusion
- **arXiv 2510.26328** — concrete example of permission escalation via skill files
- **kiho v5.14 H4 headline finding** — full excerpt at `kiho-plugin/references/v5.14-research-findings.md`

Reference the primary sources — not this file — when extending the taxonomy or tier rules. This file is the kiho-specific distillation, not the authoritative source.
