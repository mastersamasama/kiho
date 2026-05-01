---
id: sk-087
name: i18n-audit
title: i18n quality auditor for kiho-using projects
description: 5 deterministic checks (parity, placeholder, untranslated, hardcoded, dead-key) + glossary opt-in clarity heuristic v2. Surfaces via /kiho evolve --audit=i18n.
domain: engineering
capability: evaluate
topic_tags: [validation, i18n, locales]
trust_tier: T1
status: active
soul_version: v5
created: 2026-05-01
---

# i18n-audit (sk-087)

A read-only translation-health auditor for any kiho-using project. Runs five deterministic checks against the project's locale JSON tree and source code, emits JSON + markdown reports, and returns a CI-actionable exit code.

## When to invoke

Three entry points:

1. **INITIALIZE auto-detect** — when `kiho-clerk` reads `project-card.toml` and finds `i18n_locales_path = "..."` set, the clerk schedules a baseline i18n audit at the next DONE step. Output goes to `.kiho/audit/i18n/<iso-date>.md` (Lane A artefact per `references/content-routing.md`).
2. **Explicit user invocation** — `/kiho evolve --audit=i18n` from the CEO scratchpad. Useful when the user has just finished a translation pass and wants a clean-bill-of-health report.
3. **CI direct call** — GitHub Action / GitLab job invokes `bin/i18n_audit.py` directly (see `templates/i18n-audit.yml`). Exits non-zero on `fail` severity, optionally on `warn` with `--strict-warn`.

## Inputs

| Field | Required | Description |
|---|---|---|
| `--project-root` | yes | absolute path to the project root |
| `--locales-dir` | yes | path RELATIVE to project-root, e.g. `apps/mobile/src/i18n/locales` |
| `--code-glob` | yes | glob RELATIVE to project-root, e.g. `apps/mobile/src/**/*.{ts,tsx}` |
| `--canonical` | no | canonical locale name (default `en`) |
| `--config` | no | path to `i18n-allowlist.toml` (defaults applied if missing) |
| `--json-out` | no | path or `-` for stdout |
| `--md-out` | no | path or `-` for stdout |
| `--strict-warn` | no | promote warns to fails (CI hard-stop) |

If neither `--json-out` nor `--md-out` is given, JSON is printed to stdout for ergonomics.

## Outputs

### JSON (machine-readable, schema v1)

```json
{
  "version": 1,
  "summary": {
    "total_findings": 7,
    "by_severity": {"fail": 2, "warn": 5, "info": 0}
  },
  "findings": [
    {
      "check": "parity|placeholder|untranslated|hardcoded|dead",
      "severity": "fail|warn|info",
      "locale": "zh-TW",
      "key": "common.REVERT",
      "evidence": "apps/mobile/src/screens/LedgerScreen.tsx:343",
      "suggestion": "use t('common.CANCEL')"
    }
  ]
}
```

### Markdown (human-readable)

Same data grouped by severity, then by check. Each finding includes copy-pasteable rewrite snippets. Pinned to `.kiho/audit/i18n/<iso-date>.md` for Lane A archive.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | clean — no findings |
| 1 | warn only (dead-key / untranslated) |
| 2 | fail (parity break / placeholder mismatch / hard-coded) |
| 3 | crash (uncaught exception / invalid input) |

`--strict-warn` flips warn → fail for projects that want zero-warn CI.

## The 5 checks

| # | Check | Severity | What it catches |
|---|---|---|---|
| 1 | **parity** | fail | Key present in canonical but missing in another locale, or vice versa. Recursive flatten + set diff. |
| 2 | **placeholder** | fail | `{var}` and ICU `{count, plural, ...}` set mismatch across locales. Set equality required; order is free. |
| 3 | **untranslated** | warn | Non-canonical value identical to canonical value, minus brand allowlist. |
| 4 | **hardcoded** | fail | Source-code regex scan for `<Text>literal</Text>`, `accessibilityLabel="literal"`, `Alert.alert("title", "msg")`, `ActionSheetIOS` options. |
| 5 | **dead** | warn | Locale key not referenced via `t('...')` and not covered by `// i18n-keep` escape hatch or allowlist prefix. |

See `references/i18n-quality.md` for full heuristic spec.

## Invariants

- **Read-only.** The audit MUST NEVER modify locale JSON, source code, or the allowlist. It only reads and reports.
- **CI fail/warn matrix is law.** Exit-code semantics are stable across versions; downstream CI configs depend on them.
- **Stdlib only.** No `requests`, no `PyYAML` — Python 3.11+ `tomllib` for the allowlist, everything else from the standard library. Keeps the audit runnable in any minimal CI image.
- **Deterministic.** Same inputs → identical output (sorted findings, stable suggestion text). No timestamps in JSON body.
- **Allowlist-aware.** Brand values like `iCloud`, `Claude`, `OpenAI` are explicitly tolerated as identical across locales.
- **No false-positive gates.** A check fires only when it can produce a copy-pasteable suggestion the user can act on.

## Worked examples

### 1. parity — missing key

```
canonical: en.json has  common.SAVE = "Save"
zh-TW.json: common.SAVE not present
```

Finding:
```json
{"check":"parity","severity":"fail","locale":"zh-TW","key":"common.SAVE",
 "evidence":"present in en.json, absent in zh-TW.json",
 "suggestion":"add 'common.SAVE' to zh-TW.json (translate from canonical)"}
```

### 2. placeholder — ICU plural collapsed to plain `{count}`

```
en.json:    "filterActive": "{count, plural, one {# tag} other {# tags}}"
zh-TW.json: "filterActive": "已過濾 {count} 個標籤"
```

Finding:
```json
{"check":"placeholder","severity":"fail","locale":"zh-TW","key":"stats.tags.filterActive",
 "evidence":"canonical=['count:plural'] vs zh-TW=['count']; missing ['count:plural']; surplus ['count']",
 "suggestion":"align placeholder set with en.json (set equality required, order free)"}
```

### 3. untranslated — brand-name false-positive avoided

```
en.json: settings.sync.ICLOUD = "iCloud"
ja.json: settings.sync.ICLOUD = "iCloud"
i18n-allowlist.toml: [brands] values = ["iCloud", ...]
```

No finding emitted — the brand allowlist suppresses identical-value warns.

### 4. hardcoded — JSX text literal

```tsx
// apps/mobile/src/components/AccountRow.tsx:47
<Text>Cancel</Text>
```

Finding:
```json
{"check":"hardcoded","severity":"fail","locale":"-","key":"<jsx-text>",
 "evidence":"apps/mobile/src/components/AccountRow.tsx:47",
 "suggestion":"replace `<Text>Cancel</Text>` with `<Text>{t('common.CANCEL')}</Text>`"}
```

### 5. dead-key — no reference and no escape hatch

```
en.json: events.KIND_LEGACY_TRANSFER = "Legacy transfer"
codebase: no t('events.KIND_LEGACY_TRANSFER') reference; no // i18n-keep prefix=events.KIND_
```

Finding:
```json
{"check":"dead","severity":"warn","locale":"en","key":"events.KIND_LEGACY_TRANSFER",
 "evidence":"no t('...') reference and no // i18n-keep escape hatch",
 "suggestion":"remove 'events.KIND_LEGACY_TRANSFER' from en.json (and sibling locales), OR add `// i18n-keep events.KIND_LEGACY_TRANSFER` near the dynamic call site, OR add prefix to [deadkey.allow_keys].prefixes"}
```

### 6. clean run

```
$ python bin/i18n_audit.py --project-root <p> --locales-dir <d> --code-glob "<g>" --canonical en
{"version":1,"summary":{"total_findings":0,"by_severity":{"fail":0,"warn":0,"info":0}},"findings":[]}
$ echo $?
0
```

## Cross-references

- `references/i18n-quality.md` — full heuristic catalogue and v2 clarity preview
- `references/i18n-allowlist.example.toml` — TOML schema with comments
- `references/i18n-known-jargon.md` — advisory glossary input for v2
- `templates/i18n-audit.yml` — GitHub Action template
- `bin/i18n_audit.py` — implementation (~470 LOC, stdlib only)

## Rollout playbook (project adoption)

1. **Warn-only first.** Drop the GitHub Action with no `--strict-warn`. Triage the report; create amnesty entries for dead-keys you intend to revisit; populate brand allowlist.
2. **Fix the fails.** Parity / placeholder / hardcoded findings all have actionable suggestions; clear them iteratively.
3. **Strict mode.** Once the report is clean, add `--strict-warn` to CI to lock in the gate.
4. **Periodic re-baseline.** When adding a locale, re-run with `--canonical en` to catch new parity gaps before merge.

## Future hooks (v2)

The clarity heuristic v2 (sk-087.v2) will read a project-level `glossary.toml` plus `references/i18n-known-jargon.md` to surface high-register terms (e.g., 沖正 vs 撤銷 in zh-TW accounting flows). v6.5 ships with a stub `_check_clarity_v2()` that returns no findings — extension surface only.
