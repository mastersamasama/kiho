---
name: skill-deprecate
description: Retire an existing skill by rewriting its body to a one-paragraph "use <replacement> instead" redirect, flipping metadata.kiho.deprecated to true, preserving the old version in versions/, and requiring a kiho_rdeps consumer review before the deprecation completes. Distinct from skill-improve (which mutates a skill forward to fix problems). Use when a skill is being superseded by a newer or better-scoped skill, when a skill's domain no longer applies, when evolution-scan flags it for retirement, or when Gate 17 catches a near-duplicate and the existing skill is the one that should step aside. Triggers on "deprecate this skill", "retire skill", "sunset skill", "superseded by", "mark skill deprecated", or when an author explicitly decides to retire a skill in favor of a replacement.
license: proprietary
metadata:
  trust-tier: T3
  version: 2.1.0
  lifecycle: active
  kiho:
    capability: delete
    topic_tags: [authoring, lifecycle]
    requires: []
    mentions: [skill-improve, kb-update, kb-lint]
    data_classes: ["skill-definitions", "changelog"]
    reads: []
---
# skill-deprecate

Lifecycle transition skill. Marks a skill as deprecated in-place with a shim body that redirects consumers to the replacement. Never deletes the file — deletion would break any consumer that still references the old name by slug or sk-ID. This is the **deprecation shim pattern** borrowed from npm's `npm deprecate` and cargo's rename convention: the old artifact stays present as a thin redirect, and consumers migrate lazily.

`skill-deprecate` is the *opposite* of `skill-improve`. Improve mutates a skill forward to fix problems; deprecate declares that the skill is no longer the answer and points at what is. Do not fold these two operations into one; their inputs, outputs, and validation procedures are meaningfully different.

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119, RFC 8174) when, and only when, they appear in all capitals.

## When to use

Invoke skill-deprecate when:

- A skill is being **superseded** by a newer or better-scoped skill; the replacement is named.
- A skill's **domain no longer applies** (e.g., migration complete, external dependency removed) AND a replacement exists.
- `evolution-scan` flags a skill for retirement after a `staleness-check` assessment.
- `skill-create` Gate 17 catches a near-duplicate and the CEO committee decides the **existing** skill is the one to step aside in favor of the new one.
- An author or CEO explicitly says "deprecate this skill", "retire skill", "sunset skill", "superseded by", or "mark skill deprecated".

Do **NOT** invoke skill-deprecate for:

- **Bug fixes** — use `skill-improve`. Deprecation means "this skill is no longer the answer"; a fixable bug means the skill still IS the answer.
- **No-replacement retirements** — every deprecation MUST point at a `superseded_by`. If the responsibility is genuinely being eliminated, ask CEO committee to author an `archived` lifecycle transition instead.
- **Draft skills that were never promoted** — just delete the directory; the shim pattern is only for skills that have ACTIVE consumers.
- **Forcing a rename** — use the cargo rename convention explicitly (publish new-slug, redirect old-slug to it via skill-deprecate) rather than doing in-place slug edits.

## Non-Goals

- **Not a deletion tool.** The shim stays on disk so slug resolution still works. Consumers that still reference the old name by slug or sk-ID land on the redirect, not a 404.
- **Not an auto-migration tool.** Agent `skills:` arrays and consumer `metadata.kiho.requires` lists are soul-bearing or contract-bearing declarations; they **MUST NOT** be auto-edited. Surface the migration list; humans drive `skill-improve` on each consumer.
- **Not a CEO-bypass path.** A `committee_id` is required. No "quick deprecate" mode. Deprecation creates downstream work for every consumer; that warrants authorization.
- **Not reversible in-place.** Once the shim body is written, restoring the old body requires a new `skill-improve` pass that reads from `versions/v<old>.md`. There is no `skill-undeprecate` — resurrection is an exceptional action, not a quick toggle.
- **Not the same as skill-improve.** Distinct inputs (requires `superseded_by` + `committee_id`), distinct outputs (shim body, not forward diff), distinct validation (consumer review, not test_case replay). Merging them would hide the decision tree.
- **Not a KB editor.** `skill-deprecate` calls `kb-update` to cascade the deprecation into `skill-solutions.md`; it does not write to `.kiho/kb/wiki/` directly. kb-manager is the sole KB gateway.

## Contents
- [Inputs](#inputs)
- [Consumer review (required)](#consumer-review-required)
- [Deprecation procedure](#deprecation-procedure)
- [Shim body format](#shim-body-format)
- [Frontmatter changes](#frontmatter-changes)
- [kb-update integration](#kb-update-integration)
- [Response shape](#response-shape)
- [Worked examples](#worked-examples)
- [Failure playbook](#failure-playbook)
- [Anti-patterns](#anti-patterns)
- [Rejected alternatives](#rejected-alternatives)
- [Future possibilities](#future-possibilities)
- [Grounding](#grounding)

## Inputs

```
skill_path:     <path to the skill directory, e.g., skills/_meta/old-thing/>
superseded_by:  <slug or sk-ID of the replacement skill; required>
rationale:      <free-text explanation of why this skill is being retired>
committee_id:   <CEO committee session ID that authorized this; required>
```

All four inputs are required. Unlike `skill-improve`, there is no "skill-deprecate a skill at will" path — deprecation requires CEO committee authorization because it creates downstream work for every consumer.

## Consumer review (required)

**Before making any changes**, run `bin/kiho_rdeps.py` against the target to enumerate every consumer:

```
python bin/kiho_rdeps.py <target-slug>
```

Decision summary:

- **`hard_requires` ≥ 1** → **ABORT** with `status: consumers_block`. Non-negotiable.
- **All other consumer kinds** (`soft_mentions`, `agent_portfolios`, `catalog_entries`, `body_wikilinks`, `kb_backrefs`) → surface in the receipt's `migration_followups` list and proceed. Humans migrate lazily via `skill-improve`; kb-update handles the KB cascade.

Full per-kind rule table, rationale, and worked examples: `references/consumer-review-rules.md`.

## Deprecation procedure

After the consumer review passes (or only warns), perform these steps in order:

### Step 1 — Preserve the current version

1. Read `<skill_path>/SKILL.md` to confirm it exists and is not already deprecated (i.e., `metadata.kiho.deprecated` is absent or false).
2. Read the current `metadata.version` field.
3. Create `<skill_path>/versions/` if it does not exist.
4. Copy the current `SKILL.md` to `<skill_path>/versions/v<current_version>.md` so the full pre-deprecation body is recoverable.

### Step 2 — Rewrite the body

5. Compute the new body from the [Shim body format](#shim-body-format) template using `superseded_by` and `rationale`.
6. Preserve the YAML frontmatter block unchanged for now (step 3 edits it). Replace everything from the second `---` to EOF with the shim body.

### Step 3 — Update the frontmatter

7. In the frontmatter, apply these field changes (do not touch any other fields):
   - `metadata.version`: bump minor (e.g., `1.3.2` → `1.4.0`). Minor, not patch — deprecation is a meaningful lifecycle event.
   - `metadata.lifecycle`: set to `deprecated`.
   - `metadata.kiho.deprecated`: add the field, value `true`.
   - `metadata.kiho.superseded-by`: add the field, value `<superseded_by>`.
   - Preserve `name` and `description` **unchanged**. Keeping `name` means consumers still resolve the slug; keeping `description` means `skill-find` still produces a hit that surfaces the deprecation banner.

### Step 4 — Append to changelog

8. Append an entry to `<skill_path>/changelog.md` (create the file if missing):

   ```markdown
   ## v<new_version> — <YYYY-MM-DD> — deprecated

   Superseded by `<superseded_by>`.

   Rationale: <rationale>

   CEO committee session: <committee_id>

   Consumer impact at deprecation time (see kiho_rdeps report):
   - hard_requires: <n>
   - soft_mentions: <n>
   - agent_portfolios: <n>
   - catalog_entries: <n>
   - body_wikilinks: <n>
   - kb_backrefs: <n>
   ```

### Step 5 — Call kb-update

9. Spawn the `kiho-kb-manager` agent with a `kb-update` request:

   ```
   operation: kb-update
   target: skill-solutions.md
   action: mark-deprecated
   skill_slug: <target>
   superseded_by: <superseded_by>
   rationale: <rationale>
   ```

   kb-manager is responsible for updating `skill-solutions.md` to reflect the new deprecated state. Do NOT edit the KB directly — kb-manager is the sole KB gateway.

### Step 6 — Regenerate CATALOG.md

10. Run `bin/catalog_gen.py` so the CATALOG.md table reflects the new `lifecycle: deprecated` state. The routing block's `parent_of` list is untouched: deprecated skills stay listed so discovery still finds them, but their body now redirects.

### Step 7 — Return receipt

11. Emit a structured receipt (see [Response shape](#response-shape)) including the consumer counts, the new version, the replacement pointer, and any migration follow-ups surfaced by the consumer review.

## Shim body format

The post-frontmatter body is replaced with a thin redirect containing exactly four elements:

1. H1 header: `# <original-name> — deprecated`
2. A blockquote banner with the replacement pointer, rationale, and committee session ID
3. A "Migration guidance" section pointing at the replacement
4. A "History" section pointing at `versions/v<old_version>.md`

The entire post-frontmatter body MUST be these four elements and nothing else — no preserved old content, no "see below" tails. The shim is intentionally tiny and unambiguous so agents cannot accidentally execute deprecated instructions.

Full template (copy-paste ready) + formatting rules + what NOT to include: **`skills/_meta/skill-create/references/deprecation-shim.md` §Shim body template** (the canonical spec).

## Frontmatter changes

Exactly four fields change, all under `metadata`. Everything else (including `name`, `description`, `license`, and any skill-specific fields) is preserved verbatim to keep slug + description resolution intact.

| Field | Change |
|---|---|
| `metadata.version` | Bump **minor** (e.g., `1.3.2` → `1.4.0`). Deprecation is a meaningful lifecycle event, not a patch. |
| `metadata.lifecycle` | Flip `active` → `deprecated`. |
| `metadata.kiho.deprecated` | **Add** new field, value `true`. |
| `metadata.kiho.superseded-by` | **Add** new field, value `<superseded_by>` slug. |

Full before/after YAML diff + preservation rules + YAML-quoting guidance: **`skills/_meta/skill-create/references/deprecation-shim.md` §Frontmatter markers** (the canonical spec).

## kb-update integration

`kb-update` receives the deprecation notice and performs the skill-solutions.md cascade:

1. Find the skill-solutions.md entry for the target.
2. Move it from the active section to a `## Deprecated` section (create if missing).
3. Add a pointer: `→ replaced by <superseded_by>`.
4. Preserve the original entry text — do not delete the back-refs. Future `kb-search` queries still surface the deprecated entry with the replacement pointer.

If `skill-solutions.md` does not exist at the target `.kiho/kb/wiki/` location (not all projects run the full KB), the call is a no-op and the receipt reports `kb_update_status: no-op`.

## Response shape

```json
{
  "status": "deprecated | consumers_block | error",
  "target": {
    "name": "<original-name>",
    "id": "<sk-ID>",
    "path": "<skill_path>"
  },
  "version": {
    "from": "1.3.2",
    "to": "1.4.0"
  },
  "superseded_by": "<replacement-slug>",
  "committee_id": "<session-id>",
  "consumer_review": {
    "hard_requires": <n>,
    "soft_mentions": <n>,
    "agent_portfolios": <n>,
    "catalog_entries": <n>,
    "body_wikilinks": <n>,
    "kb_backrefs": <n>
  },
  "migration_followups": [
    "migrate agent kiho-kb-manager's skills: [...] array from sk-013 to sk-013b",
    "migrate 2 body-wikilinks in skills/_meta/foo/SKILL.md"
  ],
  "kb_update_status": "applied | no-op | error",
  "files_changed": [
    "<skill_path>/SKILL.md",
    "<skill_path>/versions/v1.3.2.md",
    "<skill_path>/changelog.md",
    "skills/CATALOG.md"
  ]
}
```

On `consumers_block`, no files are changed. The receipt lists the blocking `hard_requires` consumers and exits without progressing.

## Worked examples

### Example 1 — happy path (soft-mention consumers only)

**Input**
```
skill_path: skills/_meta/old-thing/
superseded_by: new-thing
rationale: "new-thing covers the old surface area and adds better error handling"
committee_id: ceo-2026-04-16-17
```

**Consumer review output**
```json
{
  "counts": {"hard_requires": 0, "soft_mentions": 2, "agent_portfolios": 1,
             "catalog_entries": 1, "body_wikilinks": 3, "kb_backrefs": 0}
}
```

**Flow** — no hard_requires → proceed. Steps 1-7 execute. Version bumps 1.3.2 → 1.4.0. Shim body written. kb-update returns `no-op` (no matching skill-solutions entry). Migration follow-ups list agent portfolio + 2 soft mentions + 3 wikilinks.

**Output**
```json
{
  "status": "deprecated",
  "target": {"name": "old-thing", "id": "sk-XXX", "path": "skills/_meta/old-thing/"},
  "version": {"from": "1.3.2", "to": "1.4.0"},
  "superseded_by": "new-thing",
  "committee_id": "ceo-2026-04-16-17",
  "consumer_review": {"hard_requires": 0, "soft_mentions": 2, "agent_portfolios": 1,
                      "catalog_entries": 1, "body_wikilinks": 3, "kb_backrefs": 0},
  "migration_followups": [
    "migrate agent foo's skills: [...] array from old-thing to new-thing",
    "migrate 3 body-wikilinks in 2 consumer SKILL.md files"
  ],
  "kb_update_status": "no-op",
  "files_changed": ["skills/_meta/old-thing/SKILL.md",
                    "skills/_meta/old-thing/versions/v1.3.2.md",
                    "skills/_meta/old-thing/changelog.md",
                    "skills/CATALOG.md"]
}
```

### Example 2 — consumers_block abort

**Input**
```
skill_path: skills/kb/kb-add/
superseded_by: kb-ingest-v2
rationale: "kb-ingest-v2 handles the same surface with streaming support"
committee_id: ceo-2026-04-16-18
```

**Consumer review output**
```json
{
  "counts": {"hard_requires": 3, "soft_mentions": 5, "agent_portfolios": 2, "kb_backrefs": 7}
}
```

**Flow** — hard_requires=3 → **ABORT** at Step 0 (consumer review). No files changed.

**Output**
```json
{
  "status": "consumers_block",
  "target": {"name": "kb-add", "id": "sk-013", "path": "skills/kb/kb-add/"},
  "blocking_consumers": [
    {"slug": "experience-pool", "file": "skills/core/knowledge/experience-pool/SKILL.md", "line": 12},
    {"slug": "skill-learn", "file": "skills/_meta/skill-learn/SKILL.md", "line": 8},
    {"slug": "kiho-plan", "file": "skills/core/planning/kiho-plan/SKILL.md", "line": 15}
  ],
  "next_action": "run skill-improve on each blocking consumer to migrate metadata.kiho.requires from kb-add to kb-ingest-v2, then re-run skill-deprecate",
  "files_changed": []
}
```

### Example 3 — kb-update no-op (minimal KB project)

**Input**
```
skill_path: skills/_meta/experimental-foo/
superseded_by: foo-v2
rationale: "design-agent v5.9 sim made the experimental variant redundant"
committee_id: ceo-2026-04-16-19
```

**Flow** — no hard_requires. Procedure steps 1-6 execute. At Step 5, `skill-solutions.md` is not present at the project's `.kiho/kb/wiki/` path (this project runs minimal KB). kb-update returns `no-op` with a log entry. Step 6 CATALOG regen proceeds normally. Receipt surfaces `kb_update_status: no-op` transparently — not an error, just an informational signal.

**Output** (abbreviated; `kb_update_status: "no-op"` is the key difference from Example 1)

## Failure playbook

**Severity**: error (consumer-block + missing inputs abort the operation)
**Impact**: one or more deprecation attempts refused, reverted, or partially applied
**Taxonomy**: consumers | inputs | kb-infra | state | rollback

```
  skill-deprecate failure
      │
      ├─ hard_requires ≥ 1                       → Route A (consumers_block)
      ├─ target already deprecated               → Route B (idempotent)
      ├─ superseded_by missing or unresolvable   → Route C (input validation)
      ├─ committee_id missing                    → Route D (authorization)
      ├─ kb-update unreachable or errors         → Route E (kb-infra)
      └─ mid-procedure failure after step 2      → Route F (partial-apply rollback)
```

### Route A — consumers_block (hard_requires ≥ 1)

1. Do NOT modify any files. Do NOT write versions/v<old>.md. Do NOT touch frontmatter.
2. Emit `status: consumers_block` with the blocking consumer list (file, line, slug).
3. Provide `next_action`: migrate each consumer's `metadata.kiho.requires` via `skill-improve`, then re-run `skill-deprecate`.
4. Do NOT proceed after a single `skill-improve` batch — re-run `kiho_rdeps` fresh to confirm the block has cleared.

### Route B — target already deprecated

1. Read frontmatter. If `metadata.kiho.deprecated: true` already, this is idempotent — do nothing.
2. Emit `status: already_deprecated` with current `superseded-by` pointer and version.
3. If `superseded_by` input differs from the already-recorded pointer: escalate to CEO committee (do NOT silently overwrite).

### Route C — superseded_by missing or unresolvable

1. If `superseded_by` is empty: exit with `status: error, reason: superseded_by_required`. No default allowed — every deprecation MUST point at a replacement.
2. If `superseded_by` resolves via `skill-find` to an ACTIVE skill: proceed.
3. If it resolves to a `lifecycle: deprecated` skill: exit with `status: error, reason: superseded_by_is_itself_deprecated`. Point at the root replacement instead.
4. If it does not resolve: exit with `status: error, reason: superseded_by_not_found`. Likely typo or the replacement hasn't been created yet.

### Route D — committee_id missing

1. `committee_id` is required. If missing: exit with `status: error, reason: committee_required`.
2. Authorization path: ask CEO to convene a committee per `references/committee-rules.md` and re-invoke with the committee session ID.
3. Do NOT accept "auto-committee" or a fake committee_id — the review creates the audit trail.

### Route E — kb-update unreachable or errors

1. kb-update failure must NOT block the deprecation — frontmatter + shim + versions/ + changelog + CATALOG are all already applied by this point (Step 5 is after Step 4).
2. Receipt reports `kb_update_status: "error"` with the kb-manager error detail.
3. Next action: manually invoke `kb-update` later; deprecation is otherwise complete and discoverable.
4. If `skill-solutions.md` does not exist at all in the project (minimal-KB setup): this is `no-op`, not `error` — transparent signal.

### Route F — mid-procedure failure after step 2

1. If failure occurs between Step 2 (body rewrite) and Step 3 (frontmatter update), the skill is in an inconsistent state: shim body with active frontmatter.
2. Rollback procedure: restore `SKILL.md` from `versions/v<old>.md`. Delete the shim. Remove the changelog entry. Leave CATALOG.md alone (not yet regenerated at this point).
3. Emit `status: error, reason: partial_apply_rolled_back` with the failure detail.
4. Author can re-invoke after resolving the underlying issue.

## Anti-patterns

- **MUST NOT** delete the deprecated skill file. Keep the shim present so slug resolution still works. Consumers that still reference the old slug land on the redirect and get a clean "use X instead" message instead of a 404.
- **MUST NOT** auto-edit agent `skills:` arrays. Agent files are Soul-bearing documents and any auto-edit would muddy the audit trail. Surface the migration list and let a human drive `skill-improve` on each agent.
- **MUST NOT** skip the consumer review because "it's a tiny skill". The whole value of skill-deprecate over a manual soft-delete is that it forces the consumer review. Skipping it is how deprecated skills silently rot in consumer lists.
- **MUST NOT** use `skill-deprecate` to fix a bug. Use `skill-improve` instead. Deprecation means "this skill is no longer the answer" — if the bug is fixable, the skill is still the answer.
- **MUST NOT** deprecate without a `superseded_by` replacement. Every deprecation must point at something. If there is genuinely no replacement, ask the CEO committee for guidance; do not invent a fake replacement.
- Do not preserve the old body under the shim header. The shim must be the entire post-frontmatter content. Old body lives in `versions/v<old>.md`.
- Do not create a new skill to replace a deprecated one using the same name. Slug collision breaks lookup. Use a new slug and let the shim point at it.

## Rejected alternatives

### A1 — Hard-delete (rm the directory)

**What it would look like**: `rm -rf skills/_meta/old-thing/` instead of the shim.

**Rejected because**: every consumer that still references `old-thing` by slug or sk-ID silently 404s. Dedupe via `skill-find` no longer surfaces the deprecated entry, so the migration pointer is lost. npm, cargo, and RubyGems all converged on the shim pattern specifically because hard-delete breaks lazy migration.

**Source**: npm deprecation docs (https://docs.npmjs.com/cli/v11/commands/npm-deprecate/); cargo rename convention.

### A2 — Unified with skill-improve (single "edit skill" op)

**What it would look like**: fold deprecation into `skill-improve` with a `mode: deprecate` flag.

**Rejected because**: the inputs (`superseded_by` + `committee_id` required for deprecate; none required for improve), validation (consumer hard-requires block for deprecate; test_case replay for improve), outputs (shim body + frontmatter flips for deprecate; forward diff for improve), and authorization path (CEO committee required for deprecate; CEO-authorized self-improvement for improve) are meaningfully different. Merging them would hide the decision tree and make both operations harder to debug.

**Source**: kiho v5 design rationale; Single Responsibility Principle.

### A3 — Auto-migrate agent `skills:` arrays and consumer `metadata.kiho.requires`

**What it would look like**: on deprecation, rewrite every consumer's declaration to point at `superseded_by`.

**Rejected because**: agent `skills:` arrays are soul-bearing declarations (the agent personally depends on the skills for its role). Auto-editing would muddy the audit trail and potentially break replacement-mismatch edge cases (replacement might not actually cover every use case). Forcing a human through `skill-improve` on each consumer preserves intentionality and lets the author accept or refuse each migration.

**Source**: kiho v4 soul-architecture invariants; `references/soul-architecture.md`.

### A4 — Committee-optional (CEO solo can deprecate)

**What it would look like**: `committee_id` optional; CEO can deprecate unilaterally.

**Rejected because**: deprecation creates downstream work for every consumer. A solo CEO decision can surprise other agents whose red lines might conflict. The committee pre-check flushes red-line conflicts before the deprecation lands (per `references/committee-rules.md` pre-committee coherence gate). The committee overhead is the point, not friction to remove.

**Source**: kiho v4 self-improvement committee rules; v5.9 pre-committee coherence gate.

## Future possibilities

*The following are sketches, not commitments. Per RFC 2561, these items describe possible future directions and are not binding on any implementer.*

- **F1 — `--consumer-review-only` dry-run flag.** Trigger: ≥3 cases where CEO wants to preview consumer impact before convening a committee. Sketch: new flag that runs Step 0 (consumer review) and exits; no changes, no committee_id required. Returns the same `consumer_review` structure the final receipt would show.
- **F2 — Automated `skill-improve` migration batch for blocking hard_requires.** Trigger: ≥3 cases where every blocking hard_requires consumer has the SAME replacement mapping (e.g., migrating kb-add → kb-ingest-v2 across all consumers). Sketch: pre-pass generates a `skill-improve` batch spec for the CEO to review; still CEO-approved, but scripted.
- **F3 — `skill-undeprecate` exceptional-action skill.** Trigger: ≥2 cases where a deprecation proves premature. Sketch: restore from `versions/v<old>.md` with committee re-authorization + fresh consumer review; currently manual via `skill-improve` reading the old version.

**Do NOT** add:
- Auto-migration of consumer declarations (rejected A3).
- Committee-optional mode (rejected A4).
- Unified deprecate+improve op (rejected A2).
- Slug recycling (anti-pattern — new replacement uses a new slug, always).

## Grounding

> **npm deprecate docs**: *"the `deprecate` command adds a message to an existing package on the registry, warning future consumers. The package itself is not removed."* — grounds the shim-not-delete pattern. https://docs.npmjs.com/cli/v11/commands/npm-deprecate/

> **cargo rename convention (RFC 2299 discussion)**: *"publish the old crate as a thin re-export wrapper around the new crate; consumers migrate lazily, build warnings flag usage."* — grounds the redirect-pointer-not-404 pattern. https://rust-lang.github.io/rfcs/

The full procedure (consumer review → versions/ preserve → body rewrite → frontmatter flip → changelog → kb-update → CATALOG regen) is specified in **kiho v5.15 plan §Feature D (deprecation shim)**. The `kiho_rdeps.py` pre-check approach is grounded in **v5.15 research findings H5** — every mature ecosystem computes reverse dependencies on demand, not stored (pnpm why, cargo tree --invert, go mod why all walk forward edges). The no-auto-migration stance is grounded in **v5.15 Q7** — lazy consumer migration via human-driven `skill-improve` passes is preferred over auto-rewrite because agent declarations carry intentional consent.

Additional internal references:
- `skills/_meta/skill-create/references/deprecation-shim.md` — detailed format reference
- `references/skill-authoring-standards.md` v5.15 section on lifecycle transitions
- `references/committee-rules.md` — committee authorization rules
- `references/v5.15-research-findings.md` — H5 + Q7 + Feature D context
