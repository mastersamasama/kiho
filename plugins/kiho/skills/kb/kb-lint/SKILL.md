---
name: kb-lint
description: Use this skill when kb-manager needs to run the 12-check lint pass on a wiki tier. Checks orphans, broken wikilinks, stale claims, contradictions, missing type pages, index drift, raw leakage, ownership gaps, confidence gaps, rule violations, skill-solutions drift, and v5.15 stale skill references against deprecated targets. Fixes mechanical findings directly; opens questions/ pages for judgment findings. Runs automatically at end of every kb-add/update/delete, at start of every /kiho evolve, and as the final step of CEO's Ralph loop.
argument-hint: "tier=<project|company> scope=full|incremental"
metadata:
  trust-tier: T2
  kiho:
    capability: evaluate
    topic_tags: [validation]
    data_classes: ["kb-wiki-articles", "skill-solutions"]
---
# kb-lint

Eleven checks across a wiki tier. Mechanical findings get fixed directly by kb-manager; judgment findings open questions/ pages for human or committee resolution.

## Inputs

```
TIER: project | company
SCOPE: full | incremental
PAYLOAD:
  incremental_paths: [<path>]         # only if scope=incremental
  auto_fix: <bool, default true>      # if false, report only
REQUEST_ID: <uuid>
```

`full` scans everything under the tier. `incremental` scans only the pages listed in `incremental_paths` plus their back-linkers.

## The 12 checks

### 1. Orphans

Pages in `wiki/` with zero incoming backlinks (from `backlinks.md`) AND zero mentions in `index.md`.

**Fix**: auto-add to `index.md` in the appropriate section. If still zero backlinks after that, leave the page but flag in `memos.md` so a human can decide.

### 2. Broken wikilinks

Parse every `wiki/` page for `[[name]]` references. Check if each resolves to an existing page.

**Fix**: if the target name matches an existing page with a typo (Levenshtein distance 1), auto-correct. Otherwise, flag in `memos.md` with the specific broken link and the page that contained it.

### 3. Stale claims

Pages whose `last_verified` is older than 90 days AND that are referenced by pages updated in the last 30 days.

**Fix**: no auto-fix. Add the page to `stale.md` and leave a note in `memos.md` suggesting re-verification.

### 4. Contradictions

Two pages making opposing claims without a `CONTRADICTS:` callout. Detect by scanning for claims that negate each other (simple heuristic: page A says "X is safe" and page B says "X is unsafe").

**Fix**: auto-add CONTRADICTS callouts on both pages; open a `questions/Q-<slug>.md` listing both claims.

### 5. Missing type pages

Concept referenced in 3+ other pages via wikilinks that does not have its own `wiki/concepts/<name>.md`.

**Fix**: auto-create a stub `concepts/<name>.md` with:
- `confidence: 0.3` (uncertain — it's a stub)
- Body: `> [!note] This is a stub auto-created by kb-lint on <iso>. Referenced by: [[page1]], [[page2]], [[page3]]. A full definition has not been written yet.`
- Frontmatter flag `stub: true` so future linters and humans know it needs content.

### 6. Index drift

Any file in `wiki/` that isn't listed in `index.md`, or any `index.md` entry that points to a deleted file.

**Fix**: auto-regenerate `index.md` from the current `wiki/` contents. This is a full rebuild, not an incremental patch.

### 7. Raw leakage

Any `wiki/` page that contains a `[[raw:...]]` or `[[raw/...]]` wikilink. Raw sources should be cited by prose attribution, not wikilinks.

**Fix**: auto-rewrite the wikilink to prose form: `[[raw:sources/foo.md]]` becomes `(see raw source: raw/sources/foo.md)`.

### 8. Ownership gaps

Any `wiki/` page with no `author_agent` frontmatter.

**Fix**: auto-set `author_agent: unknown` and add to `memos.md` for a human to investigate. If git history is available, try to recover the author from git blame (but this is optional; kiho does not assume git).

### 9. Confidence gaps

Any `wiki/` page with no `confidence` frontmatter.

**Fix**: auto-set `confidence: 0.5` with a comment `# defaulted by kb-lint` and add to `memos.md`.

### 10. Rule violations

Read `rules.md`. Scan every `wiki/` page against every must-follow rule. Flag violations.

**Fix**: no auto-fix. Open a `questions/Q-rule-violation-<iso>.md` listing the violated rule and the offending pages. The question page's resolution is someone (CEO or user) fixing the pages to comply with the rule.

### 11. Skill-solutions drift

Parse `skill-solutions.md`. For each listed skill, verify:
- The skill ID still exists in one of the tiers (plugin / company / project)
- The skill's lifecycle is not `archived`
- The skill's back-references in wiki pages' frontmatter match `skill-solutions.md`

**Fix**: auto-remove entries pointing at archived or missing skills. Auto-sync back-references on wiki pages. Note removed skills in `memos.md` so future evolution runs can decide whether to resurrect.

### 12. Stale reference (v5.15)

For every skill carrying a forward-dep declaration, check whether any declared target has been deprecated. Scan sources:

1. **Skill frontmatter.** For every `<skill>/SKILL.md`, parse `metadata.kiho.requires: [...]` and `metadata.kiho.mentions: [...]`. For each listed target, check whether the target's own frontmatter has `metadata.kiho.deprecated: true`. If yes, emit `stale_reference: <consumer> → <deprecated-target> (superseded by <replacement>)`.
2. **Agent portfolios.** For every `agents/*.md`, parse the `skills: [...]` frontmatter array. Apply the same check.
3. **Consistency.** For every deprecated skill, verify that BOTH `metadata.lifecycle: deprecated` AND `metadata.kiho.deprecated: true` are set (both flags must agree). A mismatch is flagged as `inconsistent_deprecation`.

**Fix**: no auto-fix. Migration from a deprecated reference to its replacement usually requires semantic judgment (the replacement's signature may not be 1:1 equivalent). Each stale reference is logged to `memos.md` with a suggested migration target.

**Escalation**: advisory by default (exit 0 with warnings). When the total number of `stale_reference` findings exceeds the threshold (`stale_reference_threshold`, default 5), kb-lint exits 1 and forces the CEO committee to address migration debt before other work can proceed. Threshold is tunable via the input.

Grounding: kiho v5.15 Feature E, npm/cargo shim-pattern precedent, forward-only compute-reverse-on-demand principle (H5). `bin/kiho_rdeps.py` is used internally to resolve the consumer list during per-target checks.

## Procedure

1. **Load rules.md** for the tier.
2. **Scan** `wiki/` (or `incremental_paths` if scope=incremental) for all 11 checks. Collect findings.
3. **Apply auto-fixes** (if `auto_fix: true`) via `kb-update` sub-skill for each finding. Each fix is its own atomic update.
4. **Open `questions/` pages** for judgment findings (checks 3, 4, 10).
5. **Append one lint entry** to `log.md` summarizing the pass:
   ```markdown
   ## [<iso>] lint | by=kiho-kb-manager | req=<REQUEST_ID>
   Scope: <full|incremental>
   Issues found: <N>
   Auto-fixed: <M>
   Opened questions: [<list>]
   Flagged in memos: [<list>]
   ```
6. **Return receipt.**

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: lint
TIER: <tier>
STATUS: ok | issues_found | error
SCOPE: <full|incremental>
ISSUES_FOUND: <count>
AUTO_FIXED: <count>
OPENED_QUESTIONS: [<path>, ...]
FLAGGED_IN_MEMOS: [<line>, ...]
FINDINGS:
  orphans: <count>
  broken_wikilinks: <count>
  stale_claims: <count>
  contradictions: <count>
  missing_type_pages: <count>
  index_drift: <count>
  raw_leakage: <count>
  ownership_gaps: <count>
  confidence_gaps: <count>
  rule_violations: <count>
  skill_solutions_drift: <count>
  stale_reference: <count>          # v5.15
  inconsistent_deprecation: <count> # v5.15
```

The `stale_reference` count escalates the overall STATUS to `migration_debt` and exit code 1 when it exceeds `stale_reference_threshold` (default 5).

## Anti-patterns

- Do not run full lint incrementally. If scope is "full", scan everything; otherwise use `scope: incremental` with explicit paths.
- Do not auto-fix judgment findings (3, 4, 10). These need human or committee input.
- Do not silently drop findings. If you can't fix something, report it in FLAGGED_IN_MEMOS.
- Do not trigger lint recursively. A lint pass that triggers a kb-update that triggers a lint pass can loop forever — lint is one-level only.
