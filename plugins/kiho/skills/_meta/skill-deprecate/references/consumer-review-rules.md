# Consumer review rules — reference for skill-deprecate

Before any deprecation proceeds, `skill-deprecate` runs `bin/kiho_rdeps.py` against the target and applies this rule table to each consumer kind. This document is the authoritative reference for the rules; SKILL.md carries only the decision-summary pointer.

## BCP 14 key words

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119, RFC 8174) when, and only when, they appear in all capitals.

## Non-Goals

- **Not a deletion check.** This document governs the *review* phase that precedes the shim rewrite. The actual deletion (which never happens in kiho — files become shims) is governed by `skills/_meta/skill-create/references/deprecation-shim.md`.
- **Not an auto-migration spec.** Agent `skills:` arrays and consumer `metadata.kiho.requires` lists are never auto-rewritten. The review produces a *migration_followups* list for humans to drive via `skill-improve`.
- **Not a committee substitute.** The rules below decide whether to proceed or abort; they do NOT decide whether deprecation is warranted. That judgment stays with the CEO committee session that issued the `committee_id` input.
- **Not a KB audit.** kb_backrefs are surfaced for kb-update cascade; detailed KB wiki consistency is `kb-lint` territory.

## Rule table

The review reads `kiho_rdeps` output and applies these rules. Rows are evaluated independently; each kind's rule fires on its own threshold.

| Consumer kind | Count threshold | Action | Rationale |
|---|---|---|---|
| `hard_requires` | ≥ 1 | **ABORT with `status: consumers_block`.** List every blocking consumer with file + line. Do NOT touch any files. | Hard requires are the contract kiho enforces. Breaking one silently breaks every skill that depends on the target. The consumer MUST be migrated via `skill-improve` before deprecation can proceed. Non-negotiable. |
| `soft_mentions` | ≥ 1 | Surface the list in the committee proposal and the final receipt. Proceed with deprecation. | Soft mentions are audit trail, not contract. Humans migrate lazily via `skill-improve`; kb-lint flags remaining stale refs. |
| `agent_portfolios` | ≥ 1 | Surface each agent that declares the deprecated slug in its `skills:` array. Proceed. Add to `migration_followups`. Do NOT auto-edit agent files. | Agent `skills:` arrays are soul-bearing declarations per v4 soul-architecture. Auto-editing would muddy the audit trail and could break cases where the replacement doesn't cover every intended use. |
| `catalog_entries` | ≥ 1 | The deprecated sk-ID REMAINS in CATALOG.md `parent_of` lists. Note in the receipt. | Discovery MUST still find deprecated skills so the shim can redirect. Removing from `parent_of` would regress lookup to 404. |
| `body_wikilinks` | ≥ 1 | Surface the count. Proceed. These are soft refs. | Wiki-link mentions in SKILL.md bodies are human-editable documentation. Lazy migration via `skill-improve` passes is the canonical flow. |
| `kb_backrefs` | ≥ 1 | Call `kb-update` at Step 5 of the deprecation procedure to flip the skill-solutions.md entry. | kb-manager is the sole KB gateway (v4 invariant). kb-update cascades the deprecation into `.kiho/kb/wiki/skill-solutions.md` so future `kb-search` queries surface the replacement pointer. |

## The hard-requires block is non-negotiable

If any consumer declares `metadata.kiho.requires: [<target>]`, deprecation **MUST** wait. Rationale:

- **Forward-only / compute-reverse-on-demand** (v5.15 H5): `metadata.kiho.requires` is the single declaration kiho honors. Every mature ecosystem (pnpm, cargo, go mod, bazel, Terraform) refuses to break a hard dependency without explicit consumer action.
- **Silent breakage risk**: if the shim lands while a consumer's `requires: [<target>]` is still active, the consumer technically still resolves the slug (shim exists) but its intended behavior is now "redirect to replacement" — which may or may not cover the consumer's needs. The consumer author never consented to the migration.
- **Audit trail**: forcing `skill-improve` on each hard-requiring consumer produces per-consumer diffs that can be reviewed and reverted individually if the replacement turns out to be wrong.

The abort path is:

1. Return `status: consumers_block` with the full blocking list (slug, file, line).
2. Provide `next_action`: "run `skill-improve` on each blocking consumer to migrate `metadata.kiho.requires` from `<target>` to `<superseded_by>`, then re-run `skill-deprecate`".
3. `skill-deprecate` **MUST NOT** accept "`--force`" or "`--skip-review`" overrides. Callers **MUST NOT** attempt to bypass the abort. The block is the whole point.

Additional invariants:

- skill-deprecate **MUST NOT** auto-edit consumer `metadata.kiho.requires` lists even when every blocking consumer declares the same replacement.
- skill-deprecate **MUST NOT** proceed when only a partial consumer review has been performed (e.g., `kiho_rdeps` returned an error). Partial data is worse than no data — a missed hard_requires is silent breakage.

## Worked examples

### Example 1 — clean deprecation (no hard_requires)

```json
{
  "counts": {
    "hard_requires": 0,
    "soft_mentions": 2,
    "agent_portfolios": 1,
    "catalog_entries": 1,
    "body_wikilinks": 3,
    "kb_backrefs": 0
  }
}
```

**Verdict**: proceed. migration_followups surfaces the agent portfolio (1) + body wikilinks (3) + soft mentions (2). kb-update returns `no-op` because kb_backrefs is 0.

### Example 2 — blocked deprecation (hard_requires present)

```json
{
  "counts": {"hard_requires": 3, "soft_mentions": 5, "agent_portfolios": 2, "kb_backrefs": 7}
}
```

**Verdict**: ABORT. status: consumers_block. List the 3 blocking consumers. Next action: run `skill-improve` on each to migrate their `requires` list, then re-invoke skill-deprecate. The soft_mentions + agent_portfolios + kb_backrefs counts are reported but do not affect the abort — only hard_requires does.

### Example 3 — KB cascade only

```json
{
  "counts": {"hard_requires": 0, "soft_mentions": 0, "agent_portfolios": 0, "catalog_entries": 1, "body_wikilinks": 0, "kb_backrefs": 4}
}
```

**Verdict**: proceed. The deprecation is procedurally simple (no consumer migration needed) but kb-update will cascade the shim into 4 skill-solutions.md back-refs. Receipt will report `kb_update_status: "applied"` with 4 entries rewritten.

## Rejected alternatives

### A1 — Skip review on "tiny" or "obvious" deprecations

**What it would look like**: a `--skip-review` flag for skills with fewer than N consumers, or a fast-path for skills that haven't been used in 90+ days.

**Rejected because**: the whole value of `skill-deprecate` over a manual soft-delete is the forced consumer review. Stale skills accumulate consumers slowly and silently — the use_count heuristic is not a safe proxy for "nobody depends on it." A hard_requires consumer that hasn't fired in 90 days will still silently break when it fires next. No shortcut permitted.

**Source**: kiho v5.15 H5 (forward-only / compute-reverse-on-demand); npm deprecate convention (never skips the warning).

### A2 — Auto-migrate consumers when replacement mapping is unambiguous

**What it would look like**: if every blocking `hard_requires` consumer has the same replacement mapping (`target` → `superseded_by`), auto-rewrite the `requires` lists.

**Rejected because**: consumer `metadata.kiho.requires` declarations carry intentional consent. An auto-rewrite removes that consent and could silently activate the replacement in contexts where the replacement's scope is subtly different. The current manual `skill-improve` per consumer produces reviewable per-consumer diffs that can be reverted individually.

**Source**: kiho v5.15 Q7 (rename/deprecate cascade rationale); v4 soul-architecture (intentional agent declarations).

### A3 — Treat `body_wikilinks` as a block (not a soft ref)

**What it would look like**: surface wiki-link mentions in other skills' bodies (`[[target]]`) as blocking consumers and abort until they are migrated.

**Rejected because**: wiki-link mentions in SKILL.md bodies are human-editable documentation, not contract declarations. Blocking on them would make every deprecation slow and noisy for what is ultimately a lazy `skill-improve` pass. They are reported but never block. `kb-lint` flags any remaining wiki-link mentions of deprecated targets as `stale_reference` warnings (advisory).

**Source**: kiho v5.15 Feature E (`kb-lint` stale_reference check); lazy-migration policy.

## Grounding

> **kiho v5.15 research findings H5**: *"every mature ecosystem (pnpm why, cargo tree --invert, go mod why, bazel rdeps, Terraform destroy-walk) computes reverse dependencies on demand and refuses to break a hard dependency without explicit consumer action."* — grounds the non-negotiable hard_requires block. Internal: `references/v5.15-research-findings.md`.

The single-gateway rule for KB cascades (kb-update, not direct wiki writes) is grounded in the **v4 kb-manager invariant** (`kiho-plugin/CLAUDE.md`). The rationale for not auto-editing agent `skills:` arrays traces to **v4 soul-architecture** (`references/soul-architecture.md`) — agent portfolios are soul-bearing declarations carrying intentional consent.

For shim body format + frontmatter markers + shim lifecycle (separate concern from consumer review), see `skills/_meta/skill-create/references/deprecation-shim.md`.
