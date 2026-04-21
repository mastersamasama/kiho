# Deprecation shim reference (v5.15)

When a skill is retired, kiho rewrites it in-place to a one-paragraph redirect ("use `<replacement>` instead") rather than deleting the file. The rewritten file is the **deprecation shim**: a thin placeholder that keeps the slug resolvable so consumers that still reference the old name land on a clean migration banner instead of a missing-skill error.

This is a direct port of the npm and cargo rename patterns. It is not an invention.

## Contents
- [Why a shim and not deletion](#why-a-shim-and-not-deletion)
- [Shim lifecycle](#shim-lifecycle)
- [Frontmatter markers](#frontmatter-markers)
- [Shim body template](#shim-body-template)
- [How `skill-find` handles shims](#how-skill-find-handles-shims)
- [How `kb-lint` handles shims](#how-kb-lint-handles-shims)
- [How `skill-create` handles shims](#how-skill-create-handles-shims)
- [Consumer migration cadence](#consumer-migration-cadence)
- [When to re-activate a shimmed skill](#when-to-re-activate-a-shimmed-skill)
- [Anti-patterns](#anti-patterns)
- [Grounding](#grounding)

## Why a shim and not deletion

If kiho deleted the SKILL.md when a skill is retired, every remaining consumer that references it by slug or sk-ID would silently break. The `skills:` array in `kiho-kb-manager.md` would point at a non-existent file. A `metadata.kiho.requires: [sk-013]` declaration in another skill would resolve to nothing. `kb-search` would return a stale back-ref. The loss would only surface when someone actually tried to use the deprecated slug, at which point the failure is opaque ("skill not found") rather than instructive ("this skill was retired, use X instead").

Every mature package manager follows the same pattern for the same reason:

- **npm `deprecate`** — `npm deprecate pkg@"*" "use foo instead"` marks the package but leaves the tarball live. Installs print a warning with the message.
- **cargo rename-shim** — publish the old crate as a thin `pub use foo::*;` wrapper around the new crate. Rust's equivalent of a cargo `deprecate` metadata field is still open (rust-lang/crates.io#549 since 2017) — the community settled on the shim pattern instead.
- **Kubernetes API deprecation** — deprecated APIs continue to respond for at least one release cycle with a warning header.

kiho adopts the same invariant: **the file stays, the content redirects**.

## Shim lifecycle

A shim is not a permanent state. It is a transitional marker that lets consumers migrate lazily without breaking.

```
ACTIVE                       →   SHIM (deprecated)              →   ARCHIVED
(normal SKILL.md body)            (redirect body + frontmatter      (file removed from
                                   flags; consumers still resolve)  catalog after all
                                                                    consumers migrate)
   |                                   |                                |
   |                                   |                                |
   v                                   v                                v
 skill-improve                      skill-deprecate                   (future op, not
 runs on it                         runs on it                        in v5.15)
```

v5.15 implements the ACTIVE → SHIM transition via `skill-deprecate`. The SHIM → ARCHIVED transition is deferred — archiving requires that all consumers have migrated, and kiho does not yet have enough deprecation pressure to need an archive operation. When mean-shim-age climbs past six months in a future version, v5.16 can add the archive operation.

## Frontmatter markers

Five fields control shim state. Three are required, two are recommended.

| Field | Required | Purpose |
|---|---|---|
| `metadata.lifecycle: deprecated` | yes | top-level lifecycle flag — used by kb-lint, skill-find, catalog_gen |
| `metadata.kiho.deprecated: true` | yes | namespaced flag for mechanical scripts that parse metadata.kiho only |
| `metadata.kiho.superseded-by: <slug>` | yes | the replacement pointer — required, no empty values |
| `metadata.version` | recommended | bumped minor on deprecation |
| `metadata.kiho.deprecated-at: <YYYY-MM-DD>` | optional | date for age audits |

**Why two deprecated flags?** `lifecycle: deprecated` is the canonical top-level flag consumed by kb-lint and catalog_gen. `metadata.kiho.deprecated: true` is the namespaced mirror that scripts like `similarity_scan.py` and `kiho_rdeps.py` can check without needing to parse the full frontmatter. Both must be present and must agree. A mismatch (one true, one false) is flagged by kb-lint as `inconsistent_deprecation`.

## Shim body template

The post-frontmatter body is rewritten to exactly this content:

```markdown
# <original-name> — deprecated

> This skill has been deprecated. Use **`<superseded_by>`** instead.
>
> Rationale: <rationale>
>
> Deprecated in version <new_version> via CEO committee session `<committee_id>`.

## Migration guidance

If you previously loaded `<original-name>`, switch to `<superseded_by>`. The replacement is listed in the CATALOG.md entry for `<superseded_by>` and offers the same (or a broader) surface area.

If you find yourself needing a specific capability that `<superseded_by>` does not cover, open an issue with the CEO committee — re-activating a deprecated skill is an exceptional action and requires re-review.

## History

The pre-deprecation body is preserved at `versions/v<old_version>.md` for reference.
```

The template is intentionally small. An agent that loads a deprecated skill sees roughly 10 sentences — enough to understand the state but not enough to accidentally execute the deprecated instructions. The old body is preserved at `versions/v<old>.md` and is **not** linked from the shim except as a history pointer.

## How `skill-find` handles shims

`skill-find` (sk-024) matches on description text. Since the shim preserves the original `description` field, the deprecated skill still surfaces in matches — which is the intended behavior. What changes is that `skill-find` must check `metadata.lifecycle` and emit an annotated result:

```
Match: old-thing (DEPRECATED — use new-thing instead)
  Path: skills/_meta/old-thing/SKILL.md
  Lifecycle: deprecated
  Superseded-by: new-thing
  Description: (original)
```

The consumer decides whether to load `old-thing` (getting the shim) or `new-thing` (getting the live skill). Most consumers should load the replacement.

v5.15 adds this lifecycle-aware reporting to `skill-find`'s output format. The check is one line: `if metadata.lifecycle == "deprecated": prepend "(DEPRECATED — use <superseded-by>)"`.

## How `kb-lint` handles shims

`kb-lint` gains a new check: **stale_reference**. For every skill, it parses `metadata.kiho.requires` and `metadata.kiho.mentions`. For each referenced target, it checks whether the target has `metadata.kiho.deprecated: true`. If yes, it emits:

```
stale_reference: <consumer> → <deprecated-target> (superseded by <replacement>)
```

Same check applies to agent `skills: [...]` arrays in `agents/*.md`.

The check is advisory by default (exit 0 with warnings). It escalates to exit 1 only when the number of stale references exceeds a configurable threshold (default 5). The escalation creates back-pressure: when the deprecation migration debt grows past the threshold, CEO committee sees the failure and schedules migration work.

`kb-lint` does NOT auto-fix stale references. Humans drive migration via `skill-improve` on each consumer. The fix is manual because migration sometimes requires semantic judgment (the replacement's signature may not be 1:1 equivalent to the deprecated skill's signature).

## How `skill-create` handles shims

`skill-create` Gate 17 (novel-contribution similarity scan) runs against every skill in the catalog including deprecated shims. A draft that near-duplicates a deprecated skill is still blocked — but the top-match report surfaces the deprecation state, which usually reveals that the author should be drafting a skill under the *replacement's* extension point, not a new skill.

Gate 17's suggested action on a deprecated top-match is `improve <superseded_by>` (not `improve <deprecated>`), because there is no sense telling the author to improve a shim.

## Consumer migration cadence

After a skill is deprecated, consumer migration happens lazily:

1. **Immediate (at deprecation time).** `skill-deprecate` surfaces the consumer list. The CEO committee reads the migration_followups section of the receipt and schedules migration work via `skill-improve` on each consumer, with a 30-day target.
2. **Periodic (weekly).** `kb-lint` runs as part of the CEO self-reflection loop and re-checks stale references. Any consumer still carrying the deprecated reference is flagged for the management journal.
3. **Escalation (at threshold).** When stale reference count > 5, kb-lint exits 1 and the CEO committee is forced to address migration debt before other work.
4. **Re-activation (rare).** If a deprecated skill turns out to be load-bearing and the replacement is insufficient, the CEO committee may re-activate the shim. See next section.

Do not try to auto-migrate. Migration sometimes requires semantic work that a regex cannot do (the replacement's inputs may be shaped differently). `skill-improve` is the right tool for per-consumer migration because it already carries the version-bump + changelog + validation procedure.

## When to re-activate a shimmed skill

Re-activating a shim is an exceptional action. It should happen only when:

- A consumer that cannot be migrated is identified (the replacement genuinely does not cover the needed capability).
- The CEO committee votes unanimously to re-activate.
- The skill is re-activated with a new version bump (minor or major depending on scope) and the `lifecycle: active` flag restored. The `metadata.kiho.superseded-by` field is removed.
- The rationale for re-activation is appended to `changelog.md`.
- `versions/v<old>.md` (the pre-deprecation body) is used as the baseline for the re-activated body — do not leave the shim body in place.

v5.15 does not provide an automated `skill-reactivate` operation because the frequency is expected to be near zero. If it becomes common, a v5.16 operation can formalize it.

## Anti-patterns

- **Preserving both the old body and the shim in the same file.** Do not. The shim is the entire post-frontmatter content. Old body lives in `versions/v<old>.md`. Mixing them risks agents executing the deprecated instructions by accident.
- **Deleting the SKILL.md file.** Do not. The whole value of the shim is that the file exists and the slug resolves.
- **Using a different slug for the replacement that collides with the old slug.** Do not. Slug collision breaks skill-find and kiho_rdeps. Replacements get new slugs.
- **Omitting `superseded-by`.** Do not. Every deprecation must point at something. If the responsibility is being eliminated rather than replaced, escalate to the CEO committee and adopt a different lifecycle transition.
- **Treating a deprecated skill as still-active for similarity checks.** Gate 17 includes deprecated skills in the scan (so authors can't accidentally recreate them), but the `suggested_action` for a deprecated top-match is `improve <superseded_by>`, not `improve <deprecated>`.
- **Auto-editing agent `skills: [...]` arrays when a skill is deprecated.** Do not. Agent files are Soul-bearing and require explicit `skill-improve` (or manual) migration to preserve the audit trail.
- **Using a shim to hide a security incident.** If a skill is being retired because of a security vulnerability or ClawHavoc-style malicious pattern, deprecation is too weak — use the security-taxonomy escalation from `references/security-v5.14.md` instead. Shims are for quality/scope transitions, not security incidents.

## Grounding

- npm deprecate — https://docs.npmjs.com/cli/v11/commands/npm-deprecate/
- cargo rename discussion — https://users.rust-lang.org/t/best-practice-to-rename-a-published-crate/66273
- crates.io deprecate metadata issue — https://github.com/rust-lang/crates.io/issues/549 (open since 2017, community settled on shim pattern)
- Kubernetes API deprecation policy — https://kubernetes.io/docs/reference/using-api/deprecation-policy/
- kiho v5.15 research findings, Q7 (rename/deprecate cascade) and H5 (compute-reverse-on-demand)
- kiho v5.15 plan, Feature D
- `skills/_meta/skill-deprecate/SKILL.md` — the skill that applies this pattern
