---
name: skill-improve
description: Applies a FIX operation to an underperforming skill following OpenSpace semantics. Reads the target skill, analyzes failure evidence from session context, proposes a minimal diff, validates against the skill's test case, applies the fix, bumps the version, preserves the old version in versions/, and appends to changelog.md. Calls kb-add to update the skill's registration in the KB. Use when a skill produces incorrect output, misses triggers, or fails its test case. Triggers on "fix this skill", "skill is broken", "improve skill", "skill-improve", or when the evolution-scan identifies a FIX candidate.
metadata:
  trust-tier: T3
  kiho:
    capability: update
    topic_tags: [authoring, lifecycle]
    data_classes: ["skill-definitions"]
---
# skill-improve

The FIX operation from OpenSpace's skill evolution model. Makes a single, minimal, targeted improvement to a skill based on concrete failure evidence. Never rewrites from scratch — always the smallest change that fixes the observed problem.

> **v5.21 cycle-aware.** This skill is the `improve` phase entry in `references/cycle-templates/skill-evolution.toml` (fired when the upstream `critic` phase fails). When run from cycle-runner, the cycle's `index.toml` carries `index.critic.axes_below_threshold` as the failure evidence; this skill's iters_attempted + final_score + patch_accepted write back into `index.improve.*`. The Wave 1.2 critic re-score gate (post-FIX critic must improve) remains active in both invocation paths.

## Contents
- [Inputs](#inputs)
- [FIX procedure](#fix-procedure)
- [Diff constraints](#diff-constraints)
- [Version management](#version-management)
- [Validation](#validation)
- [Response shape](#response-shape)
- [Anti-patterns](#anti-patterns)

## Inputs

```
skill_path: <path to the skill directory, e.g., skills/kb-add/>
failure_evidence: <description of what went wrong — session context, error message, incorrect output>
test_case_delta: <optional updated test case if the existing one is insufficient>
```

## FIX procedure

### Consumer check (v5.15, runs before Diagnose)

Before reading the skill itself, run `bin/kiho_rdeps.py` against the target to enumerate every consumer. This catches downstream impact of the proposed change before the diff is even drafted.

```bash
python bin/kiho_rdeps.py <skill-slug-or-id>
```

Parse the JSON output and apply these rules during Propose:

- **Record the consumer counts** (`hard_requires`, `soft_mentions`, `agent_portfolios`, `catalog_entries`, `body_wikilinks`, `kb_backrefs`) in the proposal. This becomes part of the changelog entry and the receipt.
- **Scan `metadata.kiho.reads` of each hard-dep consumer.** If a consumer declares that it reads a specific section of this skill (e.g., `reads: [skills/_meta/skill-improve/SKILL.md#propose]`), any diff that touches that section must be explicitly acknowledged in the proposal. The author decides whether to adjust the diff or notify the consumer.
- **Emit a warning when an agent portfolio declares this skill.** Agent `skills: [...]` arrays preload the skill content at sub-agent startup. A large change to the skill may change the preloaded token cost — surface the new token count if the body changed by more than 10%.
- **No consumer is a block for `skill-improve`.** Unlike `skill-deprecate`, improve is a forward mutation that preserves the skill's contract — consumers stay functional. The consumer list is **informational**, not blocking.

Record the consumer review output in `.kiho/state/improve/<skill-slug>/consumer-review.json` so subsequent steps can reference it, and the committee proposal includes the same output.

### Diagnose

1. Read `<skill_path>/SKILL.md` — the current skill.
2. Read `<skill_path>/changelog.md` if it exists — prior changes.
3. Read the failure evidence provided by the caller.
4. Identify the root cause. Classify as one of:
   - **Trigger miss:** description does not match the scenario that should invoke this skill
   - **Wrong instruction:** body gives incorrect or ambiguous guidance
   - **Missing example:** a key operation lacks a worked example
   - **Missing anti-pattern:** the skill does not warn against the observed failure mode
   - **Outdated content:** the skill references patterns that no longer apply

### Propose

5. Draft a minimal diff. The diff must:
   - Change the fewest lines possible
   - Not alter unrelated sections
   - Preserve the skill's existing voice and structure
   - Follow `references/skill-authoring-standards.md`

6. Present the diff as a before/after pair:

```markdown
## Proposed fix

**Root cause:** Trigger miss — description lacks "merge PDFs" as a trigger phrase
**Classification:** trigger-miss

### Before
description: Use this skill for reading PDF files and extracting text...

### After
description: Use this skill for reading PDF files, extracting text, merging multiple PDFs into one, and splitting PDFs apart...
```

### Validate

7. If the skill has a `test_case` in its frontmatter, replay it against the proposed fix:
   - Mentally simulate: given the test case input, would the fixed skill produce the expected output?
   - If yes, proceed
   - If no, revise the diff

8. If `test_case_delta` is provided, add or replace the test case in the skill's frontmatter.

### Apply

9. Preserve the current version: copy `SKILL.md` to `versions/v<current_version>.md` (create the `versions/` directory if needed).
10. Apply the diff to `SKILL.md`.
11. Bump the version number in frontmatter (patch increment: 1.0.0 → 1.0.1).
12. Append to `changelog.md`:

```markdown
## v1.0.1 — 2026-04-11
- **FIX:** <root cause classification> — <one-line description of change>
- **Evidence:** <brief failure description>
- **Diff:** <lines changed count>
```

### Register

13. Call `kb-add` (via kb-manager) to update the skill's registration in the KB with the new version and description.

## Hermes refinement modes

Four refinement operations, inspired by the Hermes Agent (NousResearch). Pick the narrowest operation that accomplishes the fix.

### 1. `edit` — full replacement
Replaces the entire SKILL.md body. Use when:
- The skill's structure is fundamentally wrong
- Multiple sections need coordinated changes
- The prior version was a draft that needs complete rewrite

Cost: high (rewrites everything). Use sparingly.

### 2. `patch` — targeted find-replace
Replaces specific strings within SKILL.md. Use when:
- A single rule, threshold, or example needs updating
- A typo or naming correction
- Most fixes (default choice)

Cost: low (token-efficient). Preferred default.

Format: `{find: "<exact string>", replace: "<new string>", occurrences: 1|all}`

### 3. `write_file` — add supporting asset
Adds a new file to the skill's directory (references/, templates/, scripts/). Use when:
- Adding a new reference doc
- Adding an example template
- Adding a helper script

Does NOT modify SKILL.md. References the new file from the body.

### 4. `remove_file` — delete supporting asset
Removes a file from the skill's directory. Use when:
- A reference doc is stale and the content has moved elsewhere
- A template is no longer used by the skill body
- Cleaning up orphan files

Never deletes SKILL.md itself.

## Picking a mode

Order of preference: patch > write_file > remove_file > edit. Always prefer the most targeted operation that accomplishes the fix. Reserve edit for structural rewrites.

## Diff constraints

- **Maximum 20 lines changed** per FIX. If the fix requires more, the skill needs a DERIVED variant or a rewrite (escalate to CEO).
- **No structural reorganization.** Do not move sections around, rename headings, or change the progressive disclosure layout.
- **Preserve all existing anti-patterns.** Only add new ones; never remove.
- **One root cause per FIX.** If the skill has multiple problems, run multiple FIX operations sequentially.

### Lazy YAML→TOML migration hook (v5.19.3+)

Before applying a diff to a skill that ships a `config.yaml` or `soul-overrides*.yaml` adjacent to the SKILL.md, first check whether the target row in `references/data-storage-matrix.md` §2 is still MIGRATING. (Note: `canonical-rubric` was migrated in v5.19.5; it is no longer MIGRATING.) If yes, migrate the file via:

```bash
python bin/yaml_to_toml.py convert --in <path-to-yaml> --in-place
```

Then apply the FIX diff against the new `.toml` file (update any SKILL.md references that hard-code the old `.yaml` path in the same diff). This keeps the lazy migration discipline: files convert on author-touch, never in a mass sweep. The converter is stdlib-only; review its output for comment placement before shipping (TOML requires top-level scalars before `[table]` blocks — section header comments may need one-line manual reordering). First reference migration shipped: `config.yaml` → `config.toml` in v5.19.3.

## Version management

```
<skill_path>/
  SKILL.md              # current version
  changelog.md          # append-only change log
  versions/
    v1.0.0.md           # original version
    v1.0.1.md           # after first fix
```

Version numbers follow semver: MAJOR.MINOR.PATCH. FIX operations always increment PATCH. DERIVED operations create a new skill (not a version bump). Major changes require CEO approval.

## Validation

Before applying, confirm:
- [ ] The diff is under 20 lines
- [ ] The description is still under 1024 characters
- [ ] The body is still under 500 lines
- [ ] The test case (if any) passes with the fix applied
- [ ] No existing anti-patterns were removed
- [ ] `references/skill-authoring-standards.md` rules are still met

### Critic re-score gate (v5.20 Wave 1.2)

After applying the diff (Step 10) but **before** committing the version bump (Step 11), run the deterministic critic against the patched SKILL.md:

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/_meta/skill-critic/scripts/critic_score.py \
  --skill-path <skill_path>/SKILL.md \
  --plugin-root ${CLAUDE_PLUGIN_ROOT} \
  --invocation-source evolve-trigger
```

Compare the resulting `overall_score` against the most recent pre-FIX score in `_meta-runtime/critic-verdicts.jsonl` for the same `skill_id`:

- **score did NOT improve** (new ≤ old) → REJECT the patch. Restore from `versions/v<old>.md`. Record the rejection in `changelog.md` as `REJECTED-FIX:` with the failed-improvement evidence so the same diff is not retried verbatim.
- **score improved** → proceed to version bump (Step 11) and changelog append.

This rule applies to FIXes triggered by the `evolution-scan --audit=critic-drift` agenda; for FIXes driven by other failure evidence (consumer report, runtime crash) the gate is RECOMMENDED but the failure-evidence remains the authoritative justification.

## Response shape

```json
{
  "status": "ok | error",
  "skill_path": "skills/kb-add/",
  "old_version": "1.0.0",
  "new_version": "1.0.1",
  "root_cause": "trigger-miss",
  "lines_changed": 3,
  "changelog_entry": "FIX: trigger-miss — added 'merge PDFs' to description triggers",
  "test_case_passed": true,
  "kb_updated": true
}
```

## Anti-patterns

- Never rewrite a skill from scratch via FIX. If more than 20 lines need changing, use `skill-derive` to create a new variant.
- Never fix a skill without concrete failure evidence. "I think it could be better" is not evidence.
- Never remove anti-patterns during a FIX. They are accumulated wisdom.
- Never skip the version preservation step. Old versions must be recoverable.
- Never batch multiple root causes into one FIX. One cause, one fix, one version bump.
