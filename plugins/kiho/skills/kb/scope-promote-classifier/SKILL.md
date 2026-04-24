---
name: scope-promote-classifier
description: Classifies a freshly-written project file into project-scope (keep in .kiho/audit/**), company-scope (promote to $COMPANY_ROOT/company/wiki/), or split (project-remainder + generic-extract). Invoked by kiho-ceo at DONE step 3 (scope-promote sweep) on each file created under .kiho/audit/** and .kiho/state/research/** this turn. Outputs {classification, confidence, extracted_sections_for_company, project_remainder_path}. On "company" or "split" classification it hands off to kiho-kb-manager kb-add to write $COMPANY_ROOT/company/wiki/<category>/<filename>.md. Governed by settings.promote.auto_scope_classify_on_done (default true) and settings.promote.dry_run_before_write (default true — user sees diff before any $COMPANY_ROOT write).
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: draft
  kiho:
    capability: read
    topic_tags: [curation, lifecycle, scope-boundary]
    data_classes: ["kb-wiki-articles", "cross-project-lessons"]
    storage_fit:
      reads: ["<project>/.kiho/audit/**", "<project>/.kiho/state/research/**", "$COMPANY_ROOT/project-registry.md", "$COMPANY_ROOT/settings.md", "$COMPANY_ROOT/company/wiki/**"]
      writes: []   # classifier is READ-only; kb-manager does the write
---
# scope-promote-classifier

Decides whether a freshly-written file belongs in the project scope
(project-specific), the company scope (reusable / generic), or is a SPLIT
(mixed — extract generic sections only). Runs at CEO DONE step 3 as part
of the scope-promote sweep.

## When to use

Invoke from:

- `kiho-ceo` DONE step 3 — for each file in `.kiho/audit/**` or
  `.kiho/state/research/**` created THIS turn (identified via git status
  against the turn-start commit OR via mtime > turn_start_ts)
- `kb-manager` op=classify-scope — when any agent asks for a scope opinion
- LOOP step e INTEGRATE — optional: when `settings.skill_library.auto_consolidate_research == true`
  AND a file has been referenced ≥ `reuse_threshold_count` times, this
  classifier can be invoked to surface promotion candidates

Do NOT invoke when:

- The file is already under `$COMPANY_ROOT/` — it's already at company
  scope, nothing to promote
- The file is inside `<project>/.kiho/state/recruit/` — that's recruit
  working state, never promoted
- `settings.promote.auto_scope_classify_on_done == false` — user opted out

## Non-Goals

- Does NOT write any files itself. Returns a classification + extracted
  sections; the caller invokes `kiho-kb-manager op=kb-add`.
- Does NOT delete the project-side file. Promotion is always a COPY.
- Does NOT resolve merge conflicts with existing company wiki entries. If
  an existing entry with similar content exists, the classifier flags
  `duplicate_candidate` and the caller's kb-add handles the decision tree.

## BCP 14 key words

MUST / MUST NOT / SHOULD / SHOULD NOT / MAY — per RFC 2119 and RFC 8174.

## Inputs

```
file_path:       <absolute path to a .md or .jsonl file>
file_content:    <optional — if provided, skip read>
project_root:    <absolute path to the project root, for .kiho-relative paths>
company_root:    <absolute path — from $COMPANY_ROOT>
project_names:   <optional — cached list from $COMPANY_ROOT/project-registry.md>
config:          <inline overrides; else read settings.promote.* from settings.md>
```

## Procedure

### Step 1 — Load project names + signal vocabularies

Read `$COMPANY_ROOT/project-registry.md` (one project name per `- name`
bullet). Lowercase, deduplicate. If the file is absent, the classifier
falls back to an empty set — in that case only content signals decide.

Load project-brand strings from `settings.promote.project_brand_strings`
if present; these are product names, customer names, internal module
names the user has flagged as project-specific.

### Step 2 — Scan for project signals

For each of these signal categories, count weighted hits:

| Signal | Weight | Examples |
|---|---|---|
| Project name (case-insensitive substring) | +3 per unique match | "33ledger", "kirito" |
| Project-brand string | +2 per unique match | user-configured |
| Sprint/plan-item ID | +2 per match | `P\d{3}`, `wave-\d+[a-z]?`, `sprint-\d+` |
| Project-local filepath | +1.5 per match | `src/`, `./apps/`, `<project>/.kiho/` |
| Project-specific URL/domain | +1 per match | internal-only subdomains |
| Proper-noun sentence subject for project entity | +0.5 per match | "33Ledger uses X" vs "Users use X" |

A file with project_score ≥ 3.0 is "strongly project".

### Step 3 — Scan for company/generic signals

| Signal | Weight | Examples |
|---|---|---|
| "framework" / "scoring matrix" / "decision tree" / "boilerplate" | +2 per hit | literal phrases |
| "reusable pattern" / "best practice" / "methodology" | +2 per hit |  |
| Library comparison (≥ 2 named libraries, generic terms) | +1.5 per comparison | "Zustand vs Valibot for state" |
| Generic framework version (no project binding) | +1 | "React Native 0.74" |
| Algorithm / formula / rule in abstract form | +1.5 | "the score = alpha * X + beta * Y" |
| Cross-language portability | +1 | Python + JS examples for same concept |

A file with company_score ≥ 3.0 is "strongly company".

### Step 4 — Decide classification

```
project_score = sum of project-signal weights
company_score = sum of company-signal weights

if project_score == 0 and company_score == 0:
  classification = "project"   # empty signals → conservative: keep as-is
  confidence = 0.50

elif company_score >= 3.0 and project_score <= 1.0:
  classification = "company"
  confidence = min(0.95, 0.70 + 0.05 * company_score)

elif project_score >= 3.0 and company_score <= 1.0:
  classification = "project"
  confidence = min(0.95, 0.70 + 0.05 * project_score)

elif company_score >= 2.0 and project_score >= 2.0:
  classification = "split"
  confidence = 0.70

elif company_score > project_score * 1.5:
  classification = "company"
  confidence = 0.60

elif project_score > company_score * 1.5:
  classification = "project"
  confidence = 0.60

else:
  classification = "project"   # tie or near-tie → conservative
  confidence = 0.55
```

### Step 5 — For "split": extract generic sections

A file classified as "split" usually has a clear generic section — often
a § titled "Framework", "Scoring", "Principles", "Reusable", "Library
comparison", etc. Heuristic extractor:

```
generic_headings = [
  "framework", "scoring", "matrix", "principles", "reusable",
  "library comparison", "trade-offs", "tradeoffs", "decision tree",
  "methodology", "boilerplate", "generic", "patterns"
]

for h2_or_h3_heading in file_content:
  if any(kw in heading.lower() for kw in generic_headings):
    extracted_sections.append({
      heading: heading_text,
      content: section_markdown_until_next_same_level_heading,
      start_line: N,
      end_line: M
    })
```

If no headings match, fall back to a "§§Generic" narrower scan: paragraphs
starting with "Generally,", "In general,", "As a framework,", "The
pattern is:" are candidates.

If extraction yields 0 sections, downgrade classification to `project`
(with a note that content is mixed but indistinguishable) — do NOT
auto-promote ambiguous material.

### Step 6 — Propose company-scope category

For "company" or "split" with extracted sections, propose a wiki
category based on content:

| Signals | Proposed category |
|---|---|
| "decision to use X", ADR-style | `decisions` |
| "framework", "scoring matrix", "methodology" | `concepts` |
| Named library + comparison | `concepts` |
| "principle", "invariant", "rule" | `principles` |
| Glossary-style entity definition | `entities` |
| Question pending resolution | `questions` |
| Synthesis of multiple entries | `synthesis` |

Default fallback: `concepts`.

### Step 7 — Check for existing company-scope match

Quick scan of `$COMPANY_ROOT/company/wiki/<category>/` for potential
duplicates — title similarity ≥ 0.80 OR content similarity ≥ 0.70 via
TF-IDF fallback (no embedding required).

If match → set `duplicate_candidate: <path>` in the output. The caller's
`kb-add` will handle the decision tree (duplicate → keep existing / merge /
supersede).

## Output shape

```json
{
  "status": "ok | error",
  "classification": "project | company | split",
  "confidence": 0.82,
  "project_score": 1.5,
  "company_score": 4.0,
  "proposed_category": "concepts",
  "proposed_title": "Expo RN i18n framework",
  "proposed_filename": "expo-rn-i18n-framework.md",
  "extracted_sections_for_company": [
    {
      "heading": "Library comparison",
      "content": "...markdown...",
      "start_line": 42,
      "end_line": 98
    }
  ],
  "project_remainder_path": "<project>/.kiho/audit/i18n-recommendation.md",
  "project_remainder_action": "keep | strip_promoted_section",
  "duplicate_candidate": null,
  "signals_summary": {
    "project_hits": [
      {"signal": "project_name", "match": "33ledger", "count": 0},
      {"signal": "sprint_id", "match": "wave-14a", "count": 2}
    ],
    "company_hits": [
      {"signal": "framework_phrase", "match": "scoring matrix", "count": 3},
      {"signal": "library_comparison", "match": "i18next vs lingui vs formatjs", "count": 1}
    ]
  },
  "recommendation": "Promote extracted Library-comparison and Boot-flow sections to $COMPANY_ROOT/company/wiki/concepts/expo-rn-i18n-framework.md via kb-manager kb-add. Keep project remainder at original path."
}
```

## Wiring with kb-manager

When the caller receives `classification: company` or `split`, it invokes:

```
kiho-kb-manager(
  op: "kb-add",
  payload: {
    page_type: <proposed_category>,
    title: <proposed_title>,
    content: <extracted_content_or_full_file>,
    tags: [<auto_extracted_tags>],
    sources: [<original_project_path>],
    confidence: <classifier_confidence>,
    provenance: [{kind: "scope_promoted", ref: <original_project_path>}],
    author_agent: "kiho-ceo"
  },
  tier: "company"
)
```

If `settings.promote.dry_run_before_write == true`:

1. kb-manager writes the draft to a staging path
2. CEO presents a diff via `AskUserQuestion`:
   ```
   Promote to company wiki?
   From: <project_path>
   To:   $COMPANY_ROOT/company/wiki/<category>/<filename>.md
   Confidence: <conf>
   Signals: <top 3 signals>
   [Show diff]
   ```
3. User options: Promote / Promote with edits / Skip / Defer to next turn
4. On Promote → kb-manager flushes staging to canonical path

## Heuristics edge cases

### Hybrid doc with clear separator

Format:
```
## Project-specific
(33Ledger-specific implementation details...)

## Framework (portable)
(generic methodology applicable to any fintech app...)
```

Classification: `split` with confidence 0.85. Extract the "Framework
(portable)" section to company; keep the whole file in project.

### Code-heavy doc with generic comments

File contains 200 lines of project-specific TypeScript but the module-doc
comment at the top is a generic explanation of the pattern.

Classification: `split` with confidence 0.65. Extract the doc comment as a
`concepts/<pattern>.md`; keep the code file in project.

### Pure project state (plan.md, ledger, brief)

Classification: `project` with confidence 0.95. Sprint IDs + assignments
+ RACI are project-tier by definition.

### Research output with "applicable to any X" phrasing

Classification: `company` with confidence ≥ 0.80. Phrases like "for any
mobile app" or "applies broadly" are strong generic signals.

### Research output with one project name in an example

Classification: `split` — extract generic principle, strip project example.
Confidence: 0.70.

## Failure modes

| Situation | Route |
|---|---|
| Binary file | Return `classification: project, confidence: 1.0` — binaries not promoted |
| File > 500KB | Return `classification: project, confidence: 0.50` — too large for inline classification; recommend manual review |
| Empty file (≤ 10 bytes) | Return `classification: project, confidence: 0.90` — nothing to promote |
| Non-ASCII heavy (binary-in-md) | Emit warning; proceed with plain signal scan |
| `$COMPANY_ROOT` unresolvable | Return `status: error, error: "company_root not set"` |

## Worked example — `.kiho/audit/i18n-recommendation.md` on 33Ledger

**Input file content (paraphrased):**

```markdown
# i18n recommendation for 33Ledger wave 11

## Library comparison

Evaluated i18next, lingui, formatjs. Scoring matrix:
| Library | Bundle | Perf | TS support | ICU |
| i18next | 40kb | OK | good | full |
...

## CJK fallback strategy

For apps with zh-TW support, fallback chain: zh-TW → zh → en.
The pattern applies to any Unicode-Latin-first-design app with
subsequent CJK support.

## 33Ledger boot flow

In 33Ledger, we bootstrap i18n at `src/i18n/init.ts` using...
```

**Step 2 scan:**
- project_name "33ledger" matches 2× → +6
- sprint id "wave 11" matches 1× → +2
- project filepath "src/i18n/init.ts" matches 1× → +1.5
- project_score = 9.5

**Step 3 scan:**
- "scoring matrix" → +2
- "library comparison" → +1.5
- "the pattern applies to any" → +1.5
- "fallback chain" as generic method → +1
- "scoring matrix" header → +2
- company_score = 8.0

**Step 4:** both ≥ 2.0 AND company_score ≥ 3.0 AND project_score ≥ 3.0
→ `split`, confidence 0.70

**Step 5:** extracted sections:
- "Library comparison" heading
- "CJK fallback strategy" heading (marked generic by "any Unicode-…")

**Step 6:** proposed category → `concepts`; proposed filename
→ `expo-rn-i18n-framework.md`

**Step 7:** no duplicate in `$COMPANY_ROOT/company/wiki/concepts/`.

**Output:**
```json
{
  "classification": "split",
  "confidence": 0.70,
  "proposed_category": "concepts",
  "extracted_sections_for_company": [<library comparison>, <CJK fallback>],
  "project_remainder_path": "<project>/.kiho/audit/i18n-recommendation.md",
  "project_remainder_action": "keep"
}
```

CEO presents dry-run diff; user approves; kb-manager writes to
`$COMPANY_ROOT/company/wiki/concepts/expo-rn-i18n-framework.md`. Original
file stays in project scope.

## Anti-patterns

- **MUST NOT** delete the project-side file. Promotion is COPY.
- **MUST NOT** promote a file without running Step 7 duplicate check.
  Polluting the company wiki with duplicates is the exact failure this
  whole step prevents.
- **MUST NOT** bypass dry-run when `settings.promote.dry_run_before_write
  == true`. Every first-v6-run user gets to review before any
  $COMPANY_ROOT write.
- Do not classify binary files as promotable. The system has no sanitizer
  for non-text content.
- Do not invent headings to extract from. If the file has no clear
  generic section, classify as `project` and move on.
- Do not promote decisions that name a specific project in the title.
  Generalize title first or route to project KB.

## Grounding

- **v6 plan §3.4 — Scope boundary enforcement.** User direction:
  *"generic reusable patterns live in $COMPANY_ROOT/company/wiki/**;
  project-specific facts stay in <project>/.kiho/."* The classifier is
  the automated boundary-check at CEO DONE step 3.
- **`kb-promote` existing skill** — the sanitization + decision-tree
  logic lives in `kb-manager`; this classifier is the UPSTREAM step that
  decides what to hand to kb-promote / kb-add.
- **Conservative default on low confidence.** From RFC 2119 and kiho
  doctrine (ledger truthfulness) — when signals are weak, keep in
  project and surface the ambiguity rather than auto-promote.
