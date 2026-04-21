# Storage-fit audit lens

Reference companion to `scripts/storage_fit_scan.py`. Describes the verdict taxonomy, report skeleton, and how the lens integrates with the main evolution-scan loop.

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.

## What this lens does

The storage-fit lens is an **audit-only** mode of evolution-scan. It runs when the caller passes `audit_lens: storage-fit` and `report_only: true`. It differs from the normal examine → propose → validate → decide loop in three ways:

1. **Read-only.** No SKILL.md is mutated. No `skill-improve` is invoked.
2. **Deterministic.** The audit is a pure Python walk; no LLM gates, no structural-gate round-trip.
3. **Bulk reporting.** A single `_meta-runtime/batch-report-storage-audit-<ts>.md` is produced; CEO makes one bulk decision per run per the `bin/skill_factory.py:465` convention.

The lens does not route to FIX, DERIVED, or CAPTURED. It surfaces drift; remediation is a separate per-skill `skill-improve` iteration at the user's discretion.

## Verdict taxonomy

Each SKILL.md scanned receives exactly one verdict:

| Verdict | Meaning | Policy violation? | CEO action |
|---|---|---|---|
| `ALIGNED` | Skill declares `metadata.kiho.data_classes:` and every slug appears in the matrix with an active status (FIT / MIGRATING / NEW / NEW-PATTERN) | no | none (noop) |
| `UNDECLARED` | Skill has no `data_classes:` field, or the field is present but empty | during grace: no; after grace: yes | within grace: none; after grace: queue `skill-improve` to add the field |
| `DRIFT` | Skill declares a slug that does not appear in the matrix | yes (always) | either add the slug to the matrix via storage-fit committee, or route to `skill-improve` to fix the typo / choose a valid slug |
| `MATRIX_GAP` | Skill declares a slug whose matrix status is GAP or DEFERRED | yes (always) | wait for the matrix row to activate (GAP → implementation) or choose a different slug |
| `ERROR` | SKILL.md could not be read (filesystem issue, encoding failure) | investigation | fix the file or filesystem; not a matrix-fit failure per se |

### Grace window

v5.19 introduces `metadata.kiho.data_classes:` as a new frontmatter field. Legacy skills are grandfathered:

- **0–59 days post-ship** (`--grace-days 60` default, `--elapsed-days < 60`): UNDECLARED skills are reported but do NOT count as policy violations. Exit code 0 unless there are DRIFT / MATRIX_GAP verdicts elsewhere.
- **60+ days post-ship** (`--elapsed-days >= grace_days`): UNDECLARED becomes a policy violation. Exit code 1.

The `--elapsed-days` flag is passed by the caller (typically a scheduled audit or a committee-triggered run). Defaults to 0 for the initial ship; later runs compute elapsed days from the v5.19 ship date.

## Report skeleton

```markdown
# Storage-fit audit batch report

- Generated: <iso-ts>
- Skills scanned: <n>
- Matrix path: `references/data-storage-matrix.md` (rows indexed: <m>)
- Skills root: `skills/`
- Grace window for UNDECLARED: 60 days (within | elapsed)

## Summary

- ALIGNED:    <n>
- UNDECLARED: <n>  (policy violation | grandfathered)
- DRIFT:      <n>  (policy violation; unknown slug)
- MATRIX_GAP: <n>  (policy violation; declared row is GAP or DEFERRED)
- ERROR:      <n>  (read failure)

## Per-skill verdicts

### <skill-name> — <VERDICT>
- Path: `skills/.../SKILL.md`
- Declared: [...]  or  "(no data_classes field)"
- <detail keys per verdict>

... (repeated per skill, sorted by verdict then path) ...

## CEO bulk decision

Reply format: `approve: [...], defer: [...], reject: [...], discuss: [...]`

## Notes

- Zero SKILL.md files were modified by this audit.
- Follow-up migrations go through `skill-improve` per skill, one iteration each (Ralph discipline).
- Matrix additions for DRIFT slugs require a storage-fit committee vote per `references/committee-rules.md`.
```

## How to read a verdict

Given a row like:

```
### kb-add — DRIFT
- Path: `kb/kb-add/SKILL.md`
- Declared: ['kb-wiki-articles', 'old-deprecated-slug']
- unknown_slugs: ['old-deprecated-slug']
- known_slugs: ['kb-wiki-articles']
```

Interpretation: kb-add's declaration includes one valid slug (`kb-wiki-articles`) and one unknown one (`old-deprecated-slug`). The remediation is either (a) matrix PR to add `old-deprecated-slug` as a row (if that class is real and missing from the matrix) or (b) `skill-improve` on kb-add to remove the typo or rename it.

For `MATRIX_GAP`:

```
### future-skill — MATRIX_GAP
- Path: `experimental/future-skill/SKILL.md`
- Declared: ['semantic-embedding-cache', 'agent-performance']
- gap_or_deferred_slugs: ['semantic-embedding-cache']
- their_statuses: {'semantic-embedding-cache': 'DEFERRED'}
- active_slugs: ['agent-performance']
```

Interpretation: future-skill declares a DEFERRED row. The skill is ahead of the matrix. Remediation is either to wait (if the revisit trigger is close to firing) or choose a currently-active class that approximates the intended data shape.

## Invocation

```bash
python skills/_meta/evolution-scan/scripts/storage_fit_scan.py \
  [--plugin-root <plugin>] \
  [--skills-root <plugin>/skills] \
  [--matrix-path <plugin>/references/data-storage-matrix.md] \
  [--output-md <plugin>/_meta-runtime/batch-report-storage-audit-<ts>.md] \
  [--grace-days 60] \
  [--elapsed-days 0] \
  [--json]
```

Exit codes:

| Code | Meaning |
|---|---|
| 0 | All skills are ALIGNED or UNDECLARED-within-grace. Report still written. |
| 1 | At least one DRIFT, MATRIX_GAP, or UNDECLARED-beyond-grace. Report written. |
| 2 | Usage error (bad path, unreadable inputs). No report written. |
| 3 | Internal error. Unexpected exception. Report as a kiho bug. |

## Integration with evolution-scan

evolution-scan's main loop (examine → propose → validate → decide → log) triggers this lens when:

- User invokes `/kiho evolve --audit=storage-fit` explicitly.
- CEO observes post-session that a recently-promoted skill lacks `data_classes:` declaration (single-skill audit).
- Periodic audit (weekly) — runs with `--grace-days 60 --elapsed-days <days-since-v5.19-ship>`.

In audit mode, evolution-scan's normal signal table is **bypassed**; the lens runs directly and emits its batch report. The main loop's FIX / DERIVED / CAPTURED operations are not triggered by the lens itself — subsequent per-skill remediation goes through normal `skill-improve` invocation at the user's discretion.

## Migration-policy anti-patterns

- **Do NOT** auto-rewrite SKILL.md to add `data_classes:` without the author's review. The field's correct value depends on what the skill actually reads/writes; heuristics can mis-classify.
- **Do NOT** treat UNDECLARED as an error within the grace window. The grace exists precisely to let backfill happen lazily on `skill-improve` touches.
- **Do NOT** add DRIFT slugs to the matrix silently. Every matrix row addition requires a storage-fit committee vote per `references/committee-rules.md`.
- **Do NOT** fold the audit's report into an existing batch report. Keep audit reports distinct (`batch-report-storage-audit-<ts>.md`), so the CEO bulk decision has a single artifact per run.

## Future possibilities

- **F1 — Trust-tier interaction.** Trigger: `data_classes:` drift becomes a recurring issue for T1 (unvetted) skills. Sketch: T1 skills MAY not be promoted to T2 without ALIGNED verdict.
- **F2 — Matrix-row usage analytics.** Trigger: matrix grows past 60 rows. Sketch: audit tracks which slugs are cited by how many skills; rows with 0 citations become deprecation candidates.
- **F3 — Cross-project audit.** Trigger: company-tier KB writes are shared. Sketch: audit walks `$COMPANY_ROOT/company/wiki/` and checks that cross-project-lessons pages' `skill_solutions:` lists cite ALIGNED skills.

**Do NOT** add:

- LLM-based `data_classes:` inference (non-deterministic; audit must stay reproducible).
- Auto-commit of suggested matrix rows (committee-gated by design).
