# i18n per-project glossary schema (sk-087.v2, opt-in)

This reference documents the schema for `<project>/.kiho/config/i18n-glossary.toml`, the **opt-in** clarity heuristic input read by Check 6 of `bin/i18n_audit.py` (kiho v6.6.1+).

## Why opt-in

Localisation choice is editorial. A finance-pro app may legitimately want 沖正; a consumer ledger app may want 撤銷. Per-locale max-char limits and forbidden-jargon lists are project-scoped, not framework-scoped. The audit ships with **zero defaults** — if `i18n-glossary.toml` does not exist, Check 6 silently skips and v1 users see no behaviour change.

## File location

```
<project>/.kiho/config/i18n-glossary.toml
```

Override via `--glossary <path>` on the audit CLI. If `--glossary` is not passed, the audit looks for the default path; if neither exists, Check 6 is skipped.

## Schema

Three optional top-level tables. Any can be omitted; missing tables produce no findings.

### `[max_chars]` — per-locale character ceiling per key

Each entry maps a flattened i18n key (dotted path) to a per-locale character limit. Locales not listed for a given key are unconstrained for that key.

```toml
[max_chars]
"common.REVERT" = { en = 6, "zh-TW" = 4, "zh-CN" = 4, ja = 6 }
"common.CANCEL" = { en = 6, "zh-TW" = 4, "zh-CN" = 4, ja = 6 }
"errors.NETWORK_TIMEOUT" = { en = 40, "zh-TW" = 18, ja = 24 }
```

**Semantics:**
- The audit fetches `locale.json[key]` for each (key, locale) pair, computes `len(value)` (Python string length — Unicode codepoints, not bytes), and emits `clarity_max_chars` as **`severity: warn`** if the value exceeds the limit.
- Warn-only by design: tight max-char ceilings are aspirational; `--strict-warn` will still escalate them to fails for projects that want a hard gate.
- A key listed here but missing from a locale is silently skipped — the parity check (Check 1) already covers missing keys.

### `[forbidden]` — per-locale deny words per key

Each entry maps a key to a per-locale list of forbidden substrings. If any forbidden substring appears in the locale's value for that key, a `clarity_forbidden_jargon` finding fires at **`severity: fail`**.

```toml
[forbidden]
"common.REVERT" = { "zh-TW" = ["沖正", "修正処理"], "zh-CN" = ["冲正"] }
"common.SAVE"   = { ja = ["保存処理"] }
```

**Semantics:**
- Substring check (case-sensitive, codepoint-exact). Designed for exact jargon lookups; not regex.
- Fail-severity: a forbidden word is an explicit editorial decision the project has made ("we never want this term"), so it should block CI.
- Suggestions in findings reference the canonical advisory list (`references/i18n-known-jargon.md`) when the forbidden term matches a curated jargon entry.

### `[tone]` — required register per key (v2.1, **stub only**)

Each entry maps a key to one of `"informal"` or `"formal"`. The semantic check is **not implemented in v6.6.1** — it requires NLP heuristics that are out of scope for the deterministic-only framework.

```toml
[tone]
"common.REVERT" = "informal"
"errors.NETWORK_TIMEOUT" = "informal"
"settings.legal.TERMS_OF_SERVICE" = "formal"
```

**v6.6.1 behaviour:** The audit logs an info-level skip note ("`[tone]` block detected but tone NLP is v2.1 work — entries ignored") to stderr exactly once per run. No findings are emitted. The block is preserved in the schema so projects can populate it now and have it become live in v2.1 without a migration.

## Check 6 finding shapes

```json
{
  "check": "clarity",
  "severity": "warn",
  "locale": "zh-TW",
  "key": "common.REVERT",
  "evidence": "value '沖正修正処理' len=7 > max_chars[zh-TW]=4",
  "suggestion": "shorten 'common.REVERT' for zh-TW to ≤4 chars (consider '撤銷' or '取消'); see references/i18n-known-jargon.md"
}
```

```json
{
  "check": "clarity",
  "severity": "fail",
  "locale": "zh-TW",
  "key": "common.REVERT",
  "evidence": "value '沖正修正処理' contains forbidden term '沖正'",
  "suggestion": "replace '沖正' with a friendlier alternative (撤銷 / 取消); see references/i18n-known-jargon.md"
}
```

## Worked example — minimal opt-in

A consumer-finance ledger app that wants two short button labels and no accounting jargon in zh-TW:

```toml
# .kiho/config/i18n-glossary.toml
[max_chars]
"common.REVERT" = { "zh-TW" = 4, "zh-CN" = 4, ja = 4 }
"common.CANCEL" = { "zh-TW" = 4, "zh-CN" = 4, ja = 4 }

[forbidden]
"common.REVERT" = { "zh-TW" = ["沖正"], "zh-CN" = ["冲正"], ja = ["仕訳"] }
```

That is the minimum useful glossary. Add keys as the team decides on their tone.

## Composition with the existing allowlist

`i18n-allowlist.toml` (v1) and `i18n-glossary.toml` (v2) are **independent files**:
- The allowlist suppresses false positives from Checks 1–5.
- The glossary adds Check 6 constraints.

Neither file is required. A project can adopt either, both, or neither.

## CLI

```bash
python bin/i18n_audit.py \
  --project-root . \
  --locales-dir apps/mobile/src/i18n/locales \
  --code-glob "apps/mobile/src/**/*.{ts,tsx}" \
  --canonical en \
  --config .kiho/config/i18n-allowlist.toml \
  --glossary .kiho/config/i18n-glossary.toml \
  --json-out i18n-audit.json
```

`--glossary` defaults to `.kiho/config/i18n-glossary.toml` (relative to `--project-root`). If the file does not exist, Check 6 is silently skipped — same as the v1 allowlist behaviour.

## Cross-references

- `references/i18n-known-jargon.md` — advisory jargon list to copy into project glossaries
- `references/i18n-quality.md` §"v2 clarity heuristic" — public-facing description
- `skills/engineering/i18n-audit/SKILL.md` §"Check 6" — invocation surface
- `bin/i18n_audit.py::check_clarity` — implementation
