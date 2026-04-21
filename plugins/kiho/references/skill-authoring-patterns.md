# Skill-authoring patterns — kiho style guide for reference docs (v5.15.2)

**Status:** v5.15.2 incorporates research-agent corrections (Apr 2026) against 9 primary sources. Major corrections: Pattern 7 now cites MADR 4.0 (not Nygard original — Nygard's ADR has no Alternatives section); Pattern 8 acknowledges no canonical ladder (closest analog is K8s Alpha/Beta/Stable); Pattern 1 adopts "Non-Goals" (KEP canonical) as its formal name; Pattern 5 imports the Rust RFC 2561 future-possibilities disclaimer; Pattern 9 documents the exit-code collision surface (POSIX 125-128, Rust panic 101, `ls`/bash builtin use 2).

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.


This file is the **style guide** for writing kiho skill reference documents. It is not about skill procedures or policies — those live in `skill-authoring-standards.md`. This file is about *how the documentation itself is written*. Nine patterns, extracted from `novel-contribution.md` (the first kiho reference doc to score highly in author review), then validated against primary sources and proved against `skill-authoring-standards.md` for self-consistency.

**What this file is NOT:**
- Not a style guide for SKILL.md body language (that's in `skill-authoring-standards.md` §"Core principles" and §"Body rules").
- Not a content policy (the 16 + 1 validation gates in `skill-create/SKILL.md` are the content policy).
- Not a document about Claude Code skills in general — it is kiho-specific.
- Not optional for new reference files. Every `references/*.md` and `skills/**/references/*.md` written after v5.15.1 MUST demonstrate at least 6 of the 9 patterns. Old references are graduated on touch.

**What this file IS.** Nine reusable patterns a reference doc should exhibit to hit the quality bar set by `novel-contribution.md`. Each pattern has: canonical form, rationale, concrete kiho example, anti-pattern. Every pattern is enforceable by a human reviewer.

## Contents
- [Why a separate pattern file](#why-a-separate-pattern-file)
- [The nine patterns](#the-nine-patterns)
  - [P1 — Negative-space opener ("what it is NOT")](#p1--negative-space-opener-what-it-is-not)
  - [P2 — Primary-source quotes with § section references](#p2--primary-source-quotes-with--section-references)
  - [P3 — Failure modes as decision trees](#p3--failure-modes-as-decision-trees)
  - [P4 — Worked examples with verifiable input/output](#p4--worked-examples-with-verifiable-inputoutput)
  - [P5 — Pre-written upgrade paths for deferred features](#p5--pre-written-upgrade-paths-for-deferred-features)
  - [P6 — Explicit "do not" guardrails](#p6--explicit-do-not-guardrails)
  - [P7 — Decision + rejected alternatives + rationale (ADR pattern)](#p7--decision--rejected-alternatives--rationale-adr-pattern)
  - [P8 — Measurement-first gate tier](#p8--measurement-first-gate-tier)
  - [P9 — Exit-code convention across scripts](#p9--exit-code-convention-across-scripts)
- [Review checklist](#review-checklist)
- [Grounding](#grounding)

## Why a separate pattern file

kiho accumulates reference documents faster than it can re-audit them. Every new skill ships 1-3 references, every new gate ships a reference, every new sub-agent ships a reference. If each author re-derives "how should I structure this reference" from scratch, quality drifts. A pattern file is the same principle as a coding style guide: codify the decisions once, enforce them via review, and spend the saved attention on the actual content.

These patterns are **not** invented. They are extracted from `novel-contribution.md` (the highest-scoring kiho reference as of Apr 2026) and validated against primary sources: Michael Nygard's ADR paper, Kubernetes KEP templates, IETF RFC 2119, the Rust RFC process, POSIX exit-code conventions, and more. Primary sources are cited per-pattern. When no canonical form exists in the external literature, the pattern is labeled **"convention, not standard"** and the kiho convention is prescribed.

## The nine patterns

### P1 — Non-Goals section (formerly "what it is NOT")

**Canonical form:** a technical reference's first or second section after the opening thesis is labeled **"Non-Goals"**. It is a bulleted list of things that could *reasonably* be goals but are explicitly chosen not to be. This is the KEP-canonical name; kiho adopts it.

**Why:** readers bring assumptions. Docs that lead with "what this is" leave the assumptions unchecked. A Non-Goals list forces a corrective reading within the first page — the reader sees what you declined to solve, and stops treating your doc as a solution for it.

**Status in the external literature:** *canonical, formalized*. The Kubernetes Enhancement Proposal (KEP) template mandates a Non-Goals section verbatim: *"What is out of scope for this KEP? Listing non-goals helps to focus discussion and make progress."* Google's design-doc guide defines non-goals as *"things that could reasonably be goals, but are explicitly chosen not to be goals"* — their own example is "ACID compliance" in a storage system that doesn't need it. Rust RFCs handle this via an informal "Motivation" section but do not mandate non-goals. IETF RFCs do not formalize non-goals. Diátaxis (the documentation system) constrains reference docs to *describing*, not instructing, which is an implicit form of scope narrowing but not an explicit Non-Goals section.

**Canonical form, kiho-specific:**

```markdown
# <title>

<one-sentence thesis>

## Goals

- <goal 1>
- <goal 2>
- <goal 3>

## Non-Goals

- **<non-goal 1>** — <one-sentence reason this could reasonably be a goal but is not>
- **<non-goal 2>** — <reason>
- **<non-goal 3>** — <reason>

## <positive content begins here>
```

For short references (under 150 lines), the kiho convention allows a compact form where Goals and Non-Goals are merged into a single "What this is / is not" block with inline bullets. `novel-contribution.md` uses this compact form.

**Concrete kiho examples:**
- `skills/_meta/skill-create/references/novel-contribution.md` lines 1-18 (compact form).
- After v5.15.2 rollout, `skills/_meta/skill-create/SKILL.md` and `CLAUDE.md` adopt explicit Non-Goals lists per this pattern.

**Anti-patterns:**

- **Listing negated goals as Non-Goals.** Google's design-doc guide is explicit: *"non-goals are not the same as negated goals."* "The system should not crash" is a negated goal, not a non-goal. "Real-time sub-millisecond latency" is a non-goal if your system targets 100ms latency — it's a reasonable thing to ask for that you chose not to solve.
- **Non-goals that are obviously impossible or absurd.** "This is not a pizza recipe" adds nothing. Every bullet must close a *plausible* misread — something the author genuinely saw a reader assume.
- **Over-use on short references.** A reference under 100 lines does not need a full Non-Goals section. Use inline negation in the opening paragraph instead: "Note: this is not a runtime check."
- **Prose-only negation without a bullet list.** Readers skim. A list of bullets registers; a paragraph of negations does not. The KEP mandate and the kiho convention both require a bulleted list.

**Source:** Kubernetes Enhancement Proposal template — https://raw.githubusercontent.com/kubernetes/enhancements/master/keps/NNNN-kep-template/README.md (mandates Non-Goals verbatim). Google design-doc guide — https://www.industrialempathy.com/posts/design-docs-at-google/ (defines non-goals vs negated goals).

---

### P2 — Primary-source quotes with § section references

**Canonical form:** every design decision that cites external research includes (a) the paper/doc title, (b) a specific section or line number, and (c) a verbatim quote in blockquote formatting. Not "research shows"; the actual sentence, in quotes, with section reference.

**Why:** kiho's design decisions are audited by future authors who may not read the primary source. A verbatim quote preserves the author's original claim across rewrites. Section numbers make re-checking fast — the reader opens the paper directly to §5.3 without re-reading the whole thing.

**Status in the external literature:** *convention, not standard*. There is no canonical inline-citation format for markdown technical docs. The closest formalized alternatives are:
- **PEP 12 footnote style** — `[#word]_` in-text with `.. [#word]` body sections, plus Sphinx roles `:pep:` and `:rfc:` for cross-spec references (https://peps.python.org/pep-0012/).
- **IEEE numbered-bracket inline** — `[1]`, `[2]` with a numbered references list at the end. IEEE explicitly forbids secondary sources: *"IEEE style does not allow for the use of secondary sources... you must locate the original source."*
- **Rust RFC inline markdown links** — no formal rules beyond "links should resolve."
- **IETF RFC `[RFCxxxx]` brackets** in text with a References section.

The kiho convention is closest to Rust RFC inline links plus verbatim italic quotes with explicit § references. **This is a convention, not a standard.** kiho prescribes it; future contributors should not expect to find it documented anywhere outside this file.

**Canonical form, kiho-specific:**

```markdown
> **<paper/doc short name> §<section>:** *"<verbatim quote>"*
```

Use the `> **source:** *"quote"*` blockquote format. Always italicize the quote. Always cite the section number; if the source has no section number, cite page + line or paragraph.

**Concrete kiho example:** `novel-contribution.md` §"Why this gate exists":

> **arXiv 2601.04748 §5.2:** *"At small scales (|S| ≤ 20), accuracy remains above 90%, but degrades steadily beyond |S| = 30..."*

**Anti-patterns:**

- **Paraphrasing instead of quoting.** "The paper shows that accuracy degrades at scale" is not a citation; it is an author's interpretation. Use the actual sentence.
- **Citing without a section.** "arXiv 2601.04748 shows..." is not enough. Future readers must be able to open the paper and find the claim in <30 seconds.
- **Over-citing.** Not every sentence needs a citation. Reserve citations for load-bearing claims — the claims that justify a design decision. Uncontroversial facts (e.g., "markdown is a text format") do not need citations.
- **Citing a secondary source when a primary source exists.** If the primary source is reachable, cite it directly. A citation to "the Wikipedia article on X" is almost always lazy.

**Source:** Rust RFC process — https://github.com/rust-lang/rfcs/blob/master/0000-template.md — mandates a "References" section but does not mandate in-text § references; the kiho convention is stricter. PEP 12 (https://peps.python.org/pep-0012/) prescribes ReStructuredText citations with unique IDs.

---

### P3 — Failure modes as playbook entries

**Canonical form:** documentation of failure modes should be organized as *decision paths*, not as *error enumerations*. Every failure state leads to exactly one of a small set of next-actions. The author draws the decision tree as an ASCII diagram **plus** structured entries that include severity, impact, debug steps, and mitigation.

**Why:** a passive error list ("Gate X fails when ...") leaves the reader with a problem. An active decision path ("Gate X fails? Do A, then B, then C") gives the reader a next step. The Google SRE Workbook formalizes this as the playbook pattern with measurable MTTR improvement.

**Status in the external literature:** *canonical, with two near-synonymous names*. Google SRE Workbook uses **"playbook"** as the preferred term: *"Playbooks, sometimes called runbooks, contain high-level instructions on how to respond to automated alerts. They explain the severity and impact of the alert, and include debugging suggestions and possible actions to take to mitigate impact and fully resolve the alert."* Prometheus canonicalizes the runbook URL via the `runbook_url` annotation on alerting rules. gRPC Status Codes (https://grpc.io/docs/guides/status-codes/) define a 17-code error taxonomy that playbooks can key off of: retriable (`UNAVAILABLE`, `DEADLINE_EXCEEDED`), permanent (`PERMISSION_DENIED`, `UNIMPLEMENTED`, `DATA_LOSS`), and input (`INVALID_ARGUMENT`, `NOT_FOUND`). kiho adopts **"playbook"** per Google SRE terminology.

**Canonical form, kiho-specific:**

Every playbook entry in a kiho reference carries five fields — severity, impact, taxonomy tag (gRPC-style), ordered debug steps, and a decision tree to mitigation routes:

```markdown
## Failure playbook

**Severity:** warn | error | critical
**Impact:** <one sentence on what the failure blocks>
**Taxonomy:** transient | permanent | input | config | resource (gRPC-style)

### Decision tree

\`\`\`
<state or exit code>
   │
   ├─ <condition A>  → Go to Route A
   │
   ├─ <condition B>  → Go to Route B
   │
   └─ <condition C>  → Go to Route C
\`\`\`

### Route A — <short name>

<1-3 paragraphs of concrete action>

### Route B — <short name>

...
```

**Concrete kiho example:** `novel-contribution.md` §"Failure routes (decision tree)". Five routes (A-E), one ASCII diagram, concrete commands per route. v5.15.2 work item: migrate the section heading from "Failure routes (decision tree)" to "Failure playbook" to align with Google SRE canonical terminology, and add the severity/impact/taxonomy header.

**Anti-patterns:**

- **Routes that end in "think about it" or "decide".** Every leaf must be actionable. "Route C — consider whether to revise" is not a route; it's a placeholder.
- **ASCII diagrams that don't match the route headings.** Keep the tree and the route list in sync. Every `Go to Route X` in the tree must have a `### Route X` heading below.
- **Too many routes.** More than 5-6 routes means the failure taxonomy is wrong — collapse similar routes or split the gate.
- **Using decision trees for non-failure content.** Decision trees are for *what to do when something goes wrong*, not for "pick a design". Use comparison tables or ADRs for design decisions.
- **Playbooks without severity/impact.** Google SRE explicitly flags this: on-call responders can't triage. Always lead with severity and impact, even if they seem self-evident.
- **Over-structured trees that stale as code changes.** The SRE Workbook warns about maintenance burden. Keep trees shallow (≤ 3 branch points) so they survive refactors.

**Source:** Google SRE Workbook §"Being On-Call" — https://sre.google/workbook/on-call/ — canonical playbook definition. gRPC status codes — https://grpc.io/docs/guides/status-codes/ — error taxonomy. Prometheus `runbook_url` annotation — https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/.

---

### P4 — Worked examples with byte-identical reproducible I/O

**Canonical form:** every procedure or gate includes at least 3 worked examples. Each example has: (a) concrete input, (b) expected output in full, (c) classification/status. **The reader MUST be able to reproduce the example byte-for-byte** — no random IDs, no timestamps, no nondeterministic output unless explicitly pinned.

**Why:** abstract procedures are slow to understand. Concrete examples short-circuit the understanding by matching the reader's own case to a similar example. Three examples is the empirical minimum for the reader to see the boundaries of the procedure (one passing case, one warning case, one edge case). Byte-identical reproducibility is the difference between "example that illustrates" and "example that tests" — the latter catches drift automatically.

**Status in the external literature:** *canonical, with tooling and two complementary forms*. 

**Form 1: inline documentation examples.** OpenAPI 3.1 (https://spec.openapis.org/oas/v3.1.0.html) defines the **Example Object** with `summary`, `description`, `value`, and `externalValue` fields — `value` and `externalValue` are mutually exclusive. JSON Schema 2020-12 (https://json-schema.org/understanding-json-schema/reference/annotations) includes `examples` as an annotation keyword explicitly marked **documentation-only**, not validation. Stripe's API docs and IETF RFCs use inline request/response blocks.

**Form 2: golden files for runnable verification.** The Go standard library's **golden-file pattern** (https://pkg.go.dev/gotest.tools/v3/golden) stores expected output as a separate `testdata/*.golden` file with an `-update` flag to regenerate. Rust, Python, and JavaScript test suites adopt similar patterns. This is the canonical form for "example that can be checked by script."

kiho uses **Form 1** for reference docs (inline examples in markdown) and should adopt **Form 2** for CI-verifiable examples in the future (store `.golden` files under `testdata/`, script-verified on every change).

**Canonical form, kiho-specific:**

```markdown
### Example N — <one-line summary> (<status/metric value>)

<1-2 sentences of context>

**Input:**
\`\`\`
<input as it would be provided, verbatim>
\`\`\`

**Expected output:**
\`\`\`json
{
  "status": "<status>",
  ...
}
\`\`\`

<1-2 sentences explaining why the status came out this way>
```

**Concrete kiho example:** `novel-contribution.md` §"Worked examples" (three examples at Jaccard 0.73, 0.56, 0.08).

**Anti-patterns:**

- **Examples without expected output.** "Here's what you'd type" without "here's what you'd see" is half the example.
- **Examples that cannot be reproduced.** If the reader can't run the example, it's not a worked example; it's an illustration.
- **Examples with only one happy path.** Include the boundary cases: the edge case, the error case, the "almost passing" case. Three is the floor; more is fine.
- **Examples in a separate file.** Readers should not have to chase a separate `examples.md` — put them inline.
- **Stale examples.** When the procedure changes, the examples must update. Treat examples as test cases: if the procedure is a policy, the examples are the policy's unit tests.

**Source:** OpenAPI 3.1 §4.7.15 — https://spec.openapis.org/oas/v3.1.0#example-object — canonical `examples` field.

---

### P5 — Pre-written Future-Possibilities sketches

**Canonical form:** every feature or capability marked "not in scope for this version" or "future work" ships with a concrete implementation sketch — 50-150 words including: trigger condition, dependencies, estimated lines of code, and a "Do NOT" list of rejected-on-upgrade items so future authors don't repeat v5.15 mistakes. **Every sketch MUST carry the Rust RFC 2561 disclaimer** (see below) — future-possibilities notes are not commitments.

**Why:** deferred features accumulate as "someone will figure this out later" notes. A year later, "someone" is the same author with no memory of the original reasoning, and the design must be re-derived. A pre-written sketch preserves the original author's thinking at the point where it was fresh.

**Status in the external literature:** *canonical, formalized, with a critical guardrail*. Rust RFC 2561 (mandatory since 2018, https://rust-lang.github.io/rfcs/2561-future-possibilities.html) made "Future possibilities" a required RFC section. The template text says: *"Think about what the natural extension and evolution of your proposal would be..."* Crucially, RFC 2561 also warns verbatim:

> **RFC 2561:** *"Having something written down in the future-possibilities section is not a reason to accept the current or a future RFC; such notes should be in the section on motivation or rationale in this or subsequent RFCs."*

Python PEP 1 mandates **"Open Issues"** (*"ideas which warrant further discussion"*) and **"Rejected Ideas"** (*"ideas which are not accepted"* with reasoning). Kubernetes KEPs mandate a **"Graduation Criteria"** section. The three formats differ; kiho's convention is closest to the Rust "Future possibilities" model with the RFC 2561 disclaimer copied verbatim.

**Canonical form, kiho-specific:**

```markdown
## Scale upgrade path (Future possibilities, non-binding)

> **Non-binding note (Rust RFC 2561 convention):** having something written down in this section is not a reason to accept the current or a future proposal; it is a hint for the author who eventually picks this up.

**Trigger conditions (any one triggers the upgrade):**

| Signal | Threshold | Where measured |
|---|---|---|
| <metric> | <concrete value> | <measurement source> |

**Upgrade recipe (pre-written so future authors don't re-derive):**

1. <step 1>
2. <step 2>
...

Implementation estimate: ~<N> lines of Python. <dependencies>. <determinism notes>.

### Do NOT on the upgrade

- <anti-pattern 1>
- <anti-pattern 2>
```

**Concrete kiho example:** `novel-contribution.md` §"Scale upgrade path". Three trigger conditions in a table, six-step recipe, explicit "Do NOT" list. v5.15.2 work item: add the RFC 2561 non-binding note to the top of the section.

**Anti-patterns:**

- **Vague trigger conditions.** "When it gets slow" is not a trigger. "When wall-clock exceeds 3 seconds" is. Concrete thresholds or it's vaporware.
- **No "Do NOT" section.** The author who deferred the feature knows which tempting-but-wrong paths to avoid. Write them down.
- **Sketches longer than the current implementation.** If the upgrade path is longer than the current feature, it is not a "sketch" — it is a shadow codebase. Pick the simplest viable path and write it in ≤ 150 words.
- **Upgrade paths without a dependency list.** If the upgrade depends on a new library or a future gate, say so. Hidden dependencies kill upgrades.

**Source:** Rust RFC template §"Future possibilities" — https://github.com/rust-lang/rfcs/blob/master/0000-template.md — prescribes the section but leaves the format open; kiho's convention tightens it.

---

### P6 — Explicit "Do not" guardrails with BCP 14 severity

**Canonical form:** every tempting-but-wrong alternative is documented as either **MUST NOT** (absolute prohibition, RFC 2119 severity) or **SHOULD NOT** (soft prohibition, conditional) or informal "Do not" (user-facing style). The severity choice is explicit; bare "Do not" conflates MUST NOT and SHOULD NOT and should not be used alone for normative content.

**Why:** tempting-wrong paths get taken if the prose hedges. "We recommend against embeddings" gets re-read a year later as "they considered embeddings but didn't do it, maybe I should." A MUST NOT with a cited reason preserves the instruction across the re-read. Severity gradation (MUST NOT vs SHOULD NOT) preserves nuance — some prohibitions have legitimate exceptions and the prose should say so.

**Status in the external literature:** *canonical, formalized as BCP 14*. IETF RFC 2119 (https://datatracker.ietf.org/doc/html/rfc2119) and RFC 8174 (https://datatracker.ietf.org/doc/html/rfc8174) together define the Best Current Practice 14 (BCP 14) vocabulary. Verbatim definitions:

> **MUST NOT:** *"This phrase... mean[s] that the definition is an absolute prohibition of the specification."*
>
> **SHOULD NOT:** *"This phrase... mean[s] that there may exist valid reasons in particular circumstances when the particular behavior is acceptable or even useful, but the full implications should be understood and the case carefully weighed before implementing any behavior described with this label."*

The uppercase form is normative; lowercase "must not" is not. RFC 8174 adds: key words have their defined meanings only when they appear in UPPERCASE. Kubernetes API conventions use both heavily without formally declaring BCP 14 (https://github.com/kubernetes/community/blob/main/contributors/devel/sig-architecture/api-conventions.md): *"Do not use numeric enums. Use aliases for string instead"*, *"Do not use unsigned integers, due to inconsistent support"*. Google's developer documentation style guide (https://developers.google.com/style/voice) recommends active voice and second-person imperatives for user-facing text — the "Don't" form in user-facing tutorials is stylistic, not normative.

**Canonical form, kiho-specific:**

Reference docs that contain normative content declare BCP 14 once at the top:

```markdown
## BCP 14 key words

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, MAY in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.
```

Then use the following severity ladder for prohibitions:

- **MUST NOT** (normative, absolute) — uppercase in the body text. Violations break a contract. Example: *"Scripts MUST NOT print to stderr on success."*
- **SHOULD NOT** (normative, conditional) — uppercase. Violations are allowed with documented rationale. Example: *"Gate authors SHOULD NOT introduce new exit codes without CEO-committee approval."*
- **Do not** (informal, user-facing) — lowercase, bolded markdown, for prose guidance that is not a protocol-level constraint. Example: *"**Do not** edit this file by hand — regenerate via `bin/catalog_gen.py`."*

Every prohibition, regardless of severity, must be followed by either (a) a one-sentence reason or (b) a link to the section where the reason is documented.

```markdown
- **MUST NOT** persist reverse-dependency indexes to disk. Grounding: H5, every mature package manager refuses persisted reverse indexes.
- **SHOULD NOT** relax Gate 17 thresholds without CEO committee authorization. Rationale: empirical baseline is calibrated against the current threshold.
- **Do not** confuse `skill-improve` with `skill-deprecate` — they are opposite operations.
```

**Concrete kiho examples:** `novel-contribution.md` §"Scale upgrade path > Do NOT on the upgrade" (uses informal "Do not"); v5.15.2 work item: migrate normative prohibitions in that section to uppercase MUST NOT.

**Anti-patterns:**

- **Uppercase MUST NOT without declaring BCP 14.** Readers don't know the phrase is normative; the keyword is wasted.
- **Bare "Do not" for normative content.** Use uppercase MUST NOT or SHOULD NOT when the prohibition has real teeth.
- **Paternalistic "Do not" for merely suboptimal actions.** Undermines trust. Reserve prohibitions for decisions with visible tempting-wrong alternatives.
- **Hedged "Try not to".** Neither normative nor actionable; delete or promote to SHOULD NOT.

**Source:** RFC 2119 — https://datatracker.ietf.org/doc/html/rfc2119. RFC 8174 — https://datatracker.ietf.org/doc/html/rfc8174. Kubernetes API conventions — https://github.com/kubernetes/community/blob/main/contributors/devel/sig-architecture/api-conventions.md. Google developer documentation style — https://developers.google.com/style/voice.

**Concrete kiho example:** `novel-contribution.md` §"Scale upgrade path > Do NOT on the upgrade" — four bullets, each starting with "Do not".

**Anti-patterns:**

- **Hedged voice.** "It's generally better to avoid X" is useless as a guardrail.
- **"Do not" without a reason.** Every "Do not" must be followed by either (a) a one-sentence reason or (b) a link to the section where the reason is documented.
- **Over-use.** If every other sentence is "Do not", the reader stops registering them. Reserve guardrails for decisions that have a visible tempting-wrong alternative.
- **Negating something that no reasonable reader would attempt.** "Do not store state in a MySQL database" in a markdown-only project is obvious and wastes space.

**Source:** IETF RFC 2119 — https://datatracker.ietf.org/doc/html/rfc2119 — the canonical requirement-level vocabulary.

---

### P7 — MADR 4.0 decision records (not Nygard original)

**Canonical form:** every non-trivial design decision records (a) the context and problem statement, (b) considered options (mandatory), (c) decision outcome, (d) pros and cons of each considered option, and (e) consequences. **This is the MADR 4.0 format, not the Nygard original** — Nygard's 2011 template has no explicit "Alternatives" section. kiho adopts MADR 4.0.

**Why:** design decisions have context that rots. "Why did we pick Jaccard over cosine similarity?" is answerable at authoring time and forgotten within a quarter. A rejected-alternatives list preserves the reasoning for future re-evaluation.

**Status in the external literature:** *canonical, multiple competing templates, with a critical correction to kiho's previous claim.*

**Important correction:** Michael Nygard's original 2011 post (https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) prescribes exactly five sections: **Title, Status, Context, Decision, Consequences**. There is NO "Alternatives" section. "Context" implicitly covers forces but does not mandate enumerating rejected alternatives. kiho's previous claim that "Nygard's ADR pattern" requires rejected alternatives was wrong.

The pattern kiho actually wants is **MADR 4.0** (https://adr.github.io/madr/, released Sept 2024), which upgrades Nygard's five sections with:
- **Context and Problem Statement** (required)
- **Considered Options** (required — this is the first-class Alternatives section)
- **Decision Outcome** (required)
- **Pros and Cons of the Options** (recommended, with explicit "Good, because..." / "Bad, because..." / "Neutral, because..." structure)
- **Consequences** (recommended)

Rust RFCs also mandate a "Rationale and alternatives" section (https://github.com/rust-lang/rfcs/blob/master/0000-template.md): *"Why is this design the best in the space of possible designs? What other designs have been considered and what is the rationale for not choosing them?"* — semantically equivalent to MADR.

**Canonical form, kiho-specific:**

```markdown
## Rejected alternatives

### A<N> — <short name>

**What it would look like:** <1-2 sentences describing the alternative>

**Rejected because:**
- <reason 1>
- <reason 2>
- <reason 3>

**Source:** <primary source URL or section reference>
```

Every rejected alternative gets a letter+number label (A1, A2, ...) so it can be referenced from elsewhere in the doc (e.g., "see [Rejected alternative A2](#a2--...)").

**Concrete kiho example:** `novel-contribution.md` §"Rejected alternatives". Six alternatives (A1-A6): LLM judge, embeddings, TF-IDF, 3-shingles, retroactive catalog gate, AST extraction. Each has a "What it would look like" sketch, a "Rejected because" bullet list, and a primary source. This is a lightweight MADR 4.0 — it has Considered Options and Pros and Cons without a separate Context section (because the whole reference doc is the context).

**Anti-patterns:**

- **Rejected lists as theater.** "We thought about X, Y, Z and decided to ship anyway" is not an ADR — it's decoration. Every rejection must have a specific reason, and the reason must be substantive (not "simpler is better").
- **Missing the "what it would look like" sketch.** Without the sketch, the reader can't evaluate whether the rejection still applies. Always describe the alternative in enough detail that the reader can re-derive it.
- **Rejecting alternatives the author never actually considered.** Rejected-alternatives sections become a liability when they fabricate alternatives for completeness. Only include alternatives that were genuinely on the table.
- **No source.** Every rejection rationale should cite a primary source (paper, blog, issue, past incident). Rejections without sources decay.
- **Missing the Consequences section.** MADR 4.0 recommends consequences explicitly. kiho's version is lightweight but still benefits from a sentence on "what happens if this decision is later reversed."
- **Confusing ADRs with RFCs.** ADRs are *after* decisions (documentation); RFCs are *before* decisions (proposal). Mixing them muddles which is authoritative for the current state.

**Source:** Michael Nygard's original ADR post — https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions (the 5-section template WITHOUT an Alternatives section). MADR 4.0 — https://adr.github.io/madr/ — the upgraded template that IS what kiho wants. MADR source — https://github.com/adr/madr. joelparkerhenderson ADR template index — https://github.com/joelparkerhenderson/architecture-decision-record. Rust RFC rationale-and-alternatives — https://github.com/rust-lang/rfcs/blob/master/0000-template.md.

---

### P8 — Gate graduation ladder (convention, not standard)

**Canonical form:** every new policy check enters kiho at **tier 0 (tracked)** — metric recorded but no author-visible action. After an empirical baseline is established, the check graduates to **tier 1 (warn)** — warnings printed but exit code unchanged. After a quarter of warn-tier operation without regressions, it graduates to **tier 2 (error)** — exit 1 on violation.

**Why:** deciding a threshold before observing the baseline is guessing. Deploying a blocking check based on a guessed threshold creates false positives or false negatives that damage author trust. Measurement-first rollout is the industry practice for policy introduction — but NOT a single formalized standard.

**Status in the external literature:** *convention, not standard — and kiho's previous claim to the contrary was wrong.*

**Important correction:** the research pass confirmed there is **no single canonical three-tier ladder** in the external literature. kiho's earlier claim that "measured → advisory → blocking" is formalized is incorrect. The closest canonical analogs:

- **Kubernetes feature-gate graduation** (https://kubernetes.io/docs/reference/using-api/deprecation-policy/) uses **Alpha / Beta / Stable (GA)** with strict rules: Alpha is disabled by default and may be removed without deprecation; Beta is enabled by default with a 9-month or 3-release deprecation window; Stable cannot be removed within a major version. KEP-5241 (https://github.com/kubernetes/enhancements/tree/master/keps/sig-architecture/5241-beta-featuregate-promotion-requirements) locks in the graduation criteria.
- **ESLint rule severity** (https://eslint.org/docs/latest/use/configure/rules) uses **off / warn / error** as the three-tier ladder. ESLint's own rationale: *"'warn' is typically used when introducing a new rule that will eventually be set to 'error'."* This is the closest match to kiho's pattern, with documented reasoning.
- **Google SRE error-budget policy** (https://sre.google/workbook/error-budget-policy/) is **NOT graduated** — it is binary: *"halt all changes and releases other than P0 issues or security fixes"* once the budget is exhausted. kiho's previous claim to ground in SRE error-budget was wrong.

kiho adopts the **ESLint-compatible** three-tier ladder because (a) it has the closest documented rationale to what kiho wants, (b) the names map to familiar CI concepts, and (c) the rationale quote "eventually be set to 'error'" is exactly kiho's measurement-first intent. kiho renames the tiers to `tracked / warn / error` to avoid confusing ESLint users — `tier 0 = tracked` (no stdout, metric recorded), `tier 1 = warn` (stdout warning, exit 0), `tier 2 = error` (stdout error, exit 1).

**Non-binding note (RFC 2561 convention):** the `tracked / warn / error` naming is a kiho choice. Future contributors MAY propose renaming to match K8s Alpha/Beta/Stable or ESLint off/warn/error via a CEO-committee vote. The rename does not break semantics — only the labels change.

**Canonical form, kiho-specific:**

Every gate table in kiho carries a `tier` column:

```markdown
| Gate | Check | tier | Failure action |
|---|---|---|---|
| 17 | novel-contribution similarity scan | **error** | → Playbook routes A-E |
| 16 | compaction budget | error | → Step 5 (shrink body) |
| X (future) | foo metric | **tracked** | → log only, no output |
```

Graduation path:

1. **tracked (tier 0).** The check runs on every skill-create invocation. Violations are logged to `.kiho/state/gate-observations.jsonl` (v5.16 artifact) with the input, the computed metric, and "would-have-blocked: true/false". No stdout output. Exit code always 0. Duration: until ≥ 50 observations are logged AND the distribution of the metric is understood.
2. **warn (tier 1).** The check prints a warning to stdout on violation. Exit code remains 0. Authors see the warning but CI does not fail. Duration: one quarter of operation without regressions AND documented graduation criteria met.
3. **error (tier 2).** The check exits 1 on violation. Playbook table (P3) applies for mitigation.

Graduation criteria for each transition MUST be documented in the gate's reference file before the transition. Required fields: (a) sample-size minimum before promotion, (b) acceptable false-positive rate at the promoting tier, (c) time-in-previous-tier minimum, (d) who authorizes promotion (typically CEO committee). The graduation decision is made by CEO committee using the empirical data, not author opinion.

**Concrete kiho example:** Gate 17's per-draft Jaccard check is already at tier 2 (error). The complementary `--catalog-health` whole-catalog metric is at tier 0 (tracked) in v5.15. Per `novel-contribution.md` §"Catalog health mode", it graduates to tier 1 (warn) if mean-pairwise Jaccard exceeds 0.10, and to tier 2 (error) if it exceeds 0.20. This is a pure application of the graduation ladder.

**Anti-patterns:**

- **Skipping tier 0 for "obviously needed" gates.** Every gate author thinks their gate is obvious. Measurement-first exists to check the obvious assumption.
- **Tier-0 gates that never graduate.** Tracked gates that sit at tier 0 for >1 year are probably not needed. Delete them or graduate them.
- **Tier-2 gates with no fallback path.** Every error-tier gate must have a Playbook (see P3) or a `--force-overlap`-equivalent override. A blocking gate with no escape is a footgun.
- **Graduating based on author opinion instead of data.** The CEO committee decides graduation based on `.kiho/state/gate-observations.jsonl`, not on vibes.
- **Renaming tiers per-check.** Readers lose the pattern. If a gate needs different severity vocabulary, propose a v6.0 rename at the CEO committee.
- **Treating SRE error-budget policy as a 3-tier ladder.** It isn't. It's binary. Don't cite it as a graduation source.

**Source:** Kubernetes feature gate graduation — https://kubernetes.io/docs/reference/using-api/deprecation-policy/ — Alpha/Beta/Stable (closest canonical analog). ESLint rule severity — https://eslint.org/docs/latest/use/configure/rules — `off/warn/error` with the rationale *"'warn' is typically used when introducing a new rule that will eventually be set to 'error'."* KEP-5241 — https://github.com/kubernetes/enhancements/tree/master/keps/sig-architecture/5241-beta-featuregate-promotion-requirements — graduation criteria. Google SRE error-budget policy (cited as **NOT a three-tier ladder**) — https://sre.google/workbook/error-budget-policy/.

---

### P9 — Exit-code convention across scripts

**Canonical form:** every Python script under `kiho-plugin/` (both `scripts/` and `bin/`) follows the same exit-code convention:

- **0** — success / pass / novel (no action needed)
- **1** — policy violation / block / gate fail (caller may retry after fix)
- **2** — usage error / bad arguments / missing input file (caller has a bug)
- **3** — internal error / unexpected exception / filesystem error (caller should report as a kiho bug)

**Why:** CI and skill-create pipelines shell out to dozens of kiho scripts. If every script uses a different convention (one script returns 1 for "usage error", another returns 2 for "policy violation"), the caller must special-case every script. A shared convention makes pipeline wiring mechanical.

**Status in the external literature:** *partially canonical, with competing conventions and a known collision surface*.

- **POSIX shell spec** (https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html) mandates hard boundaries: **127** = command not found; **126** = found but not executable; **>128** = terminated by signal (128+N where N is the signal number); **1-125** = expansion/redirection/general failure; exit values wrap to 8 bits (0-255). POSIX does not define what 1-125 mean.
- **BSD `sysexits.h`** (https://man.openbsd.org/sysexits) defines **64-78** as specific error classes (`EX_USAGE` = 64, `EX_DATAERR` = 65, `EX_NOINPUT` = 66, `EX_CONFIG` = 78). Widely cited; partially adopted by BSD ecosystem tools. GNU coreutils explicitly does not follow sysexits: *"An exit status of zero indicates success. Failure is indicated by a nonzero value – typically '1'"*.
- **Python `argparse`** exits with **2** on usage errors by default (https://docs.python.org/3/library/argparse.html#exiting-methods). kiho's tier 2 aligns with this.
- **Rust standard library panic** (https://rust-cli.github.io/book/in-depth/exit-code.html) exits with **101** on unhandled panic. kiho MUST NOT use 101.
- **Git, Docker, kubectl** vary: `git diff --exit-code` uses 0 (no diff) / 1 (diff) / 128 (error); Docker uses 125 (daemon failure) / 126 (cannot invoke) / 127 (not found).

**Known collision surface for the kiho 0/1/2/3 scheme:**
- Code **2** matches Python `argparse` default (good) BUT GNU `ls` uses 2 for "serious trouble" and bash uses 2 for "misuse of shell builtin". kiho's semantic (usage error) is compatible with the bash case but slightly broader.
- Code **3** collides with GNU `expr` which uses 3 for "an error occurred". kiho's semantic (internal error) and `expr`'s are close enough that CI rarely confuses them, but it is a documented caveat.
- Codes **≥125** are reserved by POSIX/Docker and MUST NOT be used by kiho scripts.
- Code **101** is the Rust panic exit and MUST NOT be used by kiho scripts.
- Codes **64-78** (sysexits) are NOT used by kiho — they would add a second convention that fights the 0/1/2/3 scheme.

kiho prescribes its own 4-code convention because no single external standard is canonical at the "policy violation vs usage error" distinction kiho needs. The scheme is (a) compatible with POSIX (stays under 125), (b) compatible with Python `argparse` default on code 2, (c) distinct from BSD sysexits 64-78 (which is legacy and not followed by GNU), and (d) small enough to memorize. **SHOULD NOT** introduce new codes without CEO-committee authorization.

**Canonical form, kiho-specific:**

Every script's module docstring includes an "Exit codes" section:

```python
"""
<script name> — <one-line description>

...

Exit codes:
    0 — success (<concrete success meaning for this script>)
    1 — policy violation (<concrete violation for this script>)
    2 — usage error (<concrete usage error for this script>)
    3 — internal error (<concrete internal error>, or "not reached")
"""
```

Scripts that do not have a tier-3 case (internal error) omit it from the docstring. Scripts that do not have a tier-1 case (policy violation) still use code 1 for a generic failure state if needed.

**Concrete kiho examples (as of v5.15.1 audit):**

| Script | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `similarity_scan.py` | novel/warn/forced | near_duplicate block | --description missing, catalog missing | not reached |
| `catalog_fit.py` | overlap ≥ threshold | overlap < threshold | catalog missing, domain not found | not reached |
| `budget_preflight.py` | within budget | over budget | parse error on CATALOG.md | not reached |
| `compaction_budget.py` | under ceiling | over ceiling | usage/parse error | not reached |
| `kiho_rdeps.py` | target resolves | target not found | skills root missing | not reached |
| `catalog_gen.py` | catalog regenerated | not used | args/paths error | stat error on skill |

kiho's existing scripts **already follow this convention** as of v5.15. P9 codifies the convention so future scripts inherit it automatically.

**Anti-patterns:**

- **Unique exit codes per script.** Defeats the convention. If a new script needs a semantic that doesn't fit 0/1/2/3, either (a) re-examine whether the semantic is genuinely novel or (b) propose a v6.0 convention change at the CEO committee — don't silently invent a new code.
- **Printing to stderr with exit 0.** Warnings go to stderr with exit 0 only when the script's semantic is tier-1 warn (see P8). A script at tier 2 (error) MUST exit 1 on violation.
- **Swallowing exceptions and returning 0.** An uncaught exception is tier 3 (internal error), not tier 0. Wrap the main body in try/except and return 3 on unexpected exceptions.
- **Exit codes ≥ 125.** MUST NOT. Reserved by POSIX (125-128) and Docker (125-127).
- **Exit code 101.** MUST NOT. Reserved by Rust panic.
- **New codes > 3 without CEO-committee approval.** A new tier (e.g., 4 for "policy violation but auto-retryable") is a v6.0 change and needs a committee vote. Don't sneak new codes in.
- **Swapping codes between sibling scripts.** Every script in the kiho tree uses the same 0/1/2/3 semantics. If `catalog_fit.py` returns 2 for "catalog missing" and `similarity_scan.py` returns 2 for "description missing", both are usage errors — the convention holds. If two sibling scripts assign different meanings to the same code, one is wrong.

**Source:** POSIX shell exit conventions — https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html (126/127/>128 hard mandates). BSD `sysexits.h` — https://man.openbsd.org/sysexits (64-78; cited as partially adopted legacy). GNU coreutils exit status — http://www.gnu.org/software/coreutils/manual/html_node/Exit-status.html (0/1 convention). Python `argparse` — https://docs.python.org/3/library/argparse.html (default 2 on usage error). Rust CLI book — https://rust-cli.github.io/book/in-depth/exit-code.html (Rust panic = 101). git-diff — https://git-scm.com/docs/git-diff (0/1/128 semantics).

---

## Cross-pattern observations (from Apr 2026 research pass)

These five meta-observations emerged when all 9 patterns were validated against primary sources together. They are not themselves patterns but they shape how the patterns interact.

1. **Patterns 1, 5, 7 are all variants of "make deferred thought explicit."** Non-Goals (P1), Future-Possibilities (P5), and Considered Options / Rejected Alternatives (P7) are the same meta-pattern applied to scope, time, and design space respectively. A single discipline emerges: **every interesting decision has three shadow sections** — what we chose not to pursue (non-goals), what we deferred (future possibilities), and what we considered and rejected (alternatives).

2. **Patterns 2 and 6 pull in opposite directions on formality.** Inline citations (P2) are informal; RFC 2119 key words (P6) are strictly normative. A consistent reference doc needs a rule: **normative content uses UPPERCASE BCP 14 keywords**; **evidence uses inline footnotes with verbatim quotes**. Mixing them — e.g., `MUST` inside an italic research quote — muddles which is authoritative. kiho's convention: italic blockquotes are evidence, uppercase is normative.

3. **Patterns 3, 4, 8 all depend on reproducibility.** Playbooks (P3) must be runnable, worked examples (P4) must be byte-identical reproducible, and graduated gates (P8) must be empirically measurable. Reproducibility is the common thread. A cross-cutting rule follows: **any claim in documentation that can be checked by a script SHOULD be checked by a script**, and the doc should link to the script.

4. **Pattern 7 (MADR ADR) is the natural container for Patterns 1, 5, 6, 8.** An ADR for "should we enable this policy check" naturally has a Non-Goals section (P1), a Future-Possibilities sketch (P5), normative MUST NOT guardrails (P6), and a graduation ladder entry (P8). Reference docs that make design decisions benefit from being structured as lightweight MADRs with the other patterns as required subsections.

5. **Pattern 9 is load-bearing for Patterns 3 and 8.** Playbook decision trees (P3) and gate maturation (P8) both depend on sibling scripts communicating outcomes via exit codes. If exit-code semantics are inconsistent across kiho's scripts, both patterns silently break. The 0/1/2/3 convention is not cosmetic — it is load-bearing for the other patterns.

## Review checklist

When reviewing a new kiho reference doc, score it against the 9 patterns. At least 6 of 9 must be present; more is better. Use this checklist:

- [ ] **P1** — Does the opening have a "What this is NOT" bullet list?
- [ ] **P2** — Does every design decision include a primary-source quote with § reference?
- [ ] **P3** — Are failure modes documented as decision trees (not error lists)?
- [ ] **P4** — Are there ≥ 3 worked examples with verifiable input/output?
- [ ] **P5** — Does every deferred feature have a pre-written upgrade path with concrete triggers?
- [ ] **P6** — Are tempting-but-wrong alternatives documented as "Do not" guardrails?
- [ ] **P7** — Does the doc have a "Rejected alternatives" section with ≥ 3 entries (A1, A2, A3, ...)?
- [ ] **P8** — If the doc introduces a new gate/check, is its tier (measured/advisory/blocking) documented?
- [ ] **P9** — If the doc references CLI scripts, do they follow the 0/1/2/3 exit-code convention?

A reference scoring 6/9 passes. 7-8/9 is good. 9/9 is rare and probably indicates the doc is too long — check that every pattern is load-bearing rather than decorative.

**How to apply this to existing docs.** Do not force-patch all existing references overnight. Graduate references on touch: the next time a reference is edited for any reason, the editor brings it up to 6/9 compliance. References not edited within 6 months stay at their current compliance level until an author touches them for other reasons. This is the same "lazy migration" pattern as P8 measurement-first rollout.

## Grounding

This file was extracted from `novel-contribution.md` (the first kiho reference to score 9/9 on the patterns) and then **corrected against 24 primary-source searches and 19 WebFetches in an isolated Apr 2026 research pass**. The research pass surfaced five major corrections to the original v5.15.1 draft; all are incorporated in v5.15.2.

### Primary sources by pattern

**P1 — Non-Goals:**
- Kubernetes Enhancement Proposal template — https://raw.githubusercontent.com/kubernetes/enhancements/master/keps/NNNN-kep-template/README.md (mandates Non-Goals section verbatim)
- Google design-doc guide — https://www.industrialempathy.com/posts/design-docs-at-google/ (defines non-goals vs negated goals)

**P2 — Primary-source citations:**
- PEP 12 footnote format — https://peps.python.org/pep-0012/
- IEEE citation style (primary sources only) — https://journals.ieeeauthorcenter.ieee.org/wp-content/uploads/sites/7/IEEE_Reference_Guide.pdf
- Rust RFC references — https://github.com/rust-lang/rfcs/blob/master/0000-template.md

**P3 — Playbook (failure as decision tree):**
- Google SRE Workbook §"Being On-Call" (canonical playbook definition) — https://sre.google/workbook/on-call/
- Google SRE Book original — https://sre.google/sre-book/being-on-call/
- gRPC status codes (17-code error taxonomy) — https://grpc.io/docs/guides/status-codes/
- Prometheus `runbook_url` annotation — https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/

**P4 — Worked examples with byte-identical I/O:**
- OpenAPI 3.1 Example Object — https://spec.openapis.org/oas/v3.1.0.html
- JSON Schema `examples` keyword — https://json-schema.org/understanding-json-schema/reference/annotations
- Go golden-file pattern — https://pkg.go.dev/gotest.tools/v3/golden

**P5 — Future-Possibilities sketches:**
- Rust RFC 2561 (mandated future-possibilities) — https://rust-lang.github.io/rfcs/2561-future-possibilities.html
- Rust RFC template — https://github.com/rust-lang/rfcs/blob/master/0000-template.md
- PEP 1 (Open Issues, Rejected Ideas) — https://peps.python.org/pep-0001/

**P6 — BCP 14 normative guardrails:**
- RFC 2119 — https://datatracker.ietf.org/doc/html/rfc2119
- RFC 8174 (uppercase clarification) — https://datatracker.ietf.org/doc/html/rfc8174
- Kubernetes API conventions (real-world BCP 14 usage) — https://github.com/kubernetes/community/blob/main/contributors/devel/sig-architecture/api-conventions.md
- Google developer docs voice guide — https://developers.google.com/style/voice

**P7 — MADR 4.0 decision records:**
- Michael Nygard's original ADR post (cited as the 5-section template, **not** the alternatives source) — https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- MADR 4.0 (Sept 2024) — https://adr.github.io/madr/
- MADR source repo — https://github.com/adr/madr
- joelparkerhenderson ADR template index — https://github.com/joelparkerhenderson/architecture-decision-record
- Rust RFC "Rationale and alternatives" — https://github.com/rust-lang/rfcs/blob/master/0000-template.md

**P8 — Gate graduation (convention, not standard):**
- Kubernetes feature-gate graduation (Alpha/Beta/Stable) — https://kubernetes.io/docs/reference/using-api/deprecation-policy/
- KEP-5241 beta-to-GA criteria — https://github.com/kubernetes/enhancements/tree/master/keps/sig-architecture/5241-beta-featuregate-promotion-requirements
- ESLint rule severity (off/warn/error) — https://eslint.org/docs/latest/use/configure/rules
- Google SRE error-budget policy (cited as **NOT** a three-tier ladder) — https://sre.google/workbook/error-budget-policy/

**P9 — Exit-code convention:**
- POSIX shell spec — https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html
- BSD sysexits.h — https://man.openbsd.org/sysexits
- GNU coreutils exit status — http://www.gnu.org/software/coreutils/manual/html_node/Exit-status.html
- Python argparse — https://docs.python.org/3/library/argparse.html
- Rust CLI book — https://rust-cli.github.io/book/in-depth/exit-code.html
- git-diff exit codes — https://git-scm.com/docs/git-diff

### Additional cross-references from `novel-contribution.md`

- arXiv 2604.02837, 2602.12430, 2604.03070 — AST/semantic extraction rejection (cited in P7's A6 example)
- arXiv 2601.04748 — the phase-transition paper that motivates Gate 17 (cited in P2's example)
- kiho v5.15 research findings — `references/v5.15-research-findings.md`
- kiho v5.15.2 pattern-research findings — this file's research pass; raw report in the Apr 2026 session tool-result cache

### Changelog

- **v5.15.1** (Apr 2026, initial) — 9 patterns extracted from `novel-contribution.md`, written in a single pass without external validation.
- **v5.15.2** (Apr 2026, corrected) — research pass against 24 primary sources corrected:
  - P1 renamed "negative-space opener" → "Non-Goals" (KEP canonical name)
  - P3 renamed "decision tree" → "playbook" (Google SRE canonical name), added severity/impact/taxonomy structure
  - P4 added byte-identical reproducibility requirement, cited Go golden-file pattern
  - P5 added Rust RFC 2561 non-binding disclaimer (mandatory for every future-possibilities sketch)
  - P6 added BCP 14 severity gradation (MUST NOT vs SHOULD NOT vs informal "Do not")
  - **P7 corrected from "Nygard ADR" to "MADR 4.0"** — Nygard's original has no Alternatives section; this was a material error in v5.15.1
  - P8 acknowledged as "convention, not standard" with ESLint off/warn/error as closest analog; removed false grounding in SRE error-budget (which is binary, not graduated)
  - P9 documented the collision surface (POSIX 125-128, Rust 101, GNU ls/bash builtin 2, expr 3)
  - Cross-pattern observations section added
