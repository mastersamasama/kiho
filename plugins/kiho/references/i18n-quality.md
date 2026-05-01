# i18n quality (sk-087, public reference)

This reference documents kiho's translation-health audit framework — the public-facing companion to skill `sk-087 i18n-audit`. The audit lives at `bin/i18n_audit.py` and is a pure-stdlib (Python 3.11+) read-only validator that any kiho-using project can wire into CI.

## When this reference applies

Any kiho-using project with a translation tree (i.e. `<locale>.json` files) and source code that calls `t('...')` for user-facing strings. The framework is React-Native-flavoured today (JSX `<Text>`, `accessibilityLabel`, `Alert.alert`, `ActionSheetIOS`) but the parity / placeholder / dead-key checks are language-agnostic.

## The 5 checks (severity matrix)

| # | Check | Severity | Blocks CI? | What it catches |
|---|---|---|---|---|
| 1 | parity | `fail` | yes | key present in canonical but missing in another locale, or vice versa |
| 2 | placeholder | `fail` | yes | `{var}` and ICU `{count, plural, ...}` set mismatch across locales |
| 3 | untranslated | `warn` | with `--strict-warn` | non-canonical value identical to canonical, minus brand allowlist |
| 4 | hardcoded | `fail` | yes | source-code literal that should have been a `t(...)` call |
| 5 | dead-key | `warn` | with `--strict-warn` | locale key never referenced; not in `// i18n-keep` escape hatch |

Exit codes: `0` clean / `1` warn-only / `2` fail / `3` crash.

The choice of severities is a deliberate ergonomic split:
- **fail** is anything a translator or developer can definitively answer "yes, fix this" to. A missing key is missing. A `<Text>Cancel</Text>` in source is wrong.
- **warn** is anything that needs human judgement: "is this intentionally identical?", "is this key actually used dynamically?". The audit can't decide for you, so it surfaces for review.

## Project rollout playbook

The framework is meant to be adopted in three stages, not big-bang.

### Stage 1 — Warn-only

Drop the GitHub Action without `--strict-warn`. Run on every PR. Triage the first report:
- Triage all `fail` findings — these are real bugs. Fix in-PR or open follow-up issues.
- Triage `warn` findings — populate `i18n-allowlist.toml` brand sections, add `// i18n-keep` comments where you have dynamic key access, decide which dead-keys are amnesty (kept for future work) vs delete-now.

This is the **bootstrap pass**. Expect 30-200 findings on a multi-screen app the first time.

### Stage 2 — Fail-on-fail

Once `fail` count is zero on main, the workflow is "every PR keeps fail at zero". `warn` is still informational. CI returns 2 only on `fail` regression.

### Stage 3 — Strict

Add `--strict-warn` to the CI command. Now warns also fail CI. Use this once the project's translation discipline is robust enough that drift means real action items, not noise.

Most projects sit comfortably at Stage 2. Stage 3 is for shipping products with active i18n SLAs.

## v2 glossary clarity heuristic (preview)

A future iteration (sk-087.v2) will surface high-register jargon that may merit user-friendly substitution. Examples:

| Domain | Formal | Friendlier |
|---|---|---|
| 會計 (accounting) | 沖正 | 撤銷 / 取消 |
| 醫療 (medical) | (advisory only) | (per locale) |
| 法律 (legal) | (advisory only) | (per locale) |

The advisory list lives at `references/i18n-known-jargon.md`. Projects opt in via `<project>/.kiho/config/glossary.toml`:

```toml
[clarity]
adopt_advisory = true
domains = ["accounting"]   # only check accounting jargon
```

When opted in, the v2 check emits `severity: info` findings only — never blocks CI. v6.5 ships with a stub that returns no findings; the framework hook is wired so v2 can land without a script API change.

## CI integration shape (GitHub Actions)

Template at `templates/i18n-audit.yml`. The minimal shape:

```yaml
name: i18n quality
on: [pull_request]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - uses: actions/checkout@v4
        with: { repository: mastersamasama/kiho, path: .kiho-plugin }
      - run: |
          python .kiho-plugin/plugins/kiho/bin/i18n_audit.py \
            --project-root . \
            --locales-dir apps/mobile/src/i18n/locales \
            --code-glob "apps/mobile/src/**/*.{ts,tsx}" \
            --canonical en \
            --config .kiho/config/i18n-allowlist.toml \
            --json-out i18n-audit.json \
            --md-out i18n-audit.md
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: i18n-audit, path: 'i18n-audit.*' }
```

The artifact upload runs on `if: always()` so reviewers can read the markdown report even when the job fails — that's where the copy-pasteable rewrite suggestions live.

## Lane assignment (per `references/content-routing.md`)

The audit's report itself is a **Lane A** artefact: it's turn-scoped evidence ("here's what the codebase looked like at this commit"), not durable principle. Archive to `.kiho/audit/i18n/<iso-date>.md`. KB writes happen separately when an audit triggers a discovery worth elevating to a convention (e.g. "we discovered we never test ICU plurals in zh-CN, going forward we have a CV-PLURAL-TEST-COVERAGE rule").

## Limitations and non-goals

- **Not a translator.** The audit suggests `t('common.CANCEL')` in rewrite snippets but never writes to source.
- **Not a linter.** Hard-coded-string detection uses regex, not an AST parser. False positives are possible; the allowlist + per-file path filter is the escape hatch.
- **No semantic translation review.** "Is the Japanese translation idiomatic?" is out of scope — the audit only checks structural integrity.
- **No runtime detection.** Dynamic keys (`t(\`events.\${kind}\`)`) need explicit `// i18n-keep prefix=events.` annotations; the audit cannot infer them.

## Cross-references

- `skills/engineering/i18n-audit/SKILL.md` — skill manifest with worked examples
- `skills/engineering/i18n-audit/references/i18n-quality.md` — internal heuristic catalogue
- `references/i18n-allowlist.example.toml` — allowlist schema with comments
- `references/i18n-known-jargon.md` — advisory glossary input for v2
- `templates/i18n-audit.yml` — GitHub Action template
- `bin/i18n_audit.py` — implementation
- `references/content-routing.md` §Lane A — where audit reports live
