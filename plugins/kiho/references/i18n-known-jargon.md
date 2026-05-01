# i18n known jargon (advisory menu for sk-087 Check 6)

> **ADVISORY MENU.** Nothing in this file is enforced automatically. Projects opt-in by copying relevant rows into `<project>/.kiho/config/i18n-glossary.toml` per the v6.6.1 Check 6 schema (see `references/i18n-glossary-schema.md`). When copied, the audit emits `warn` (max-char) or `fail` (forbidden) findings — the framework still does not pick formal-vs-friendly for you.

This file catalogues high-register terms that may merit user-friendly substitution per locale. Inclusion does not imply the formal term is wrong — only that the friendlier alternative may be clearer for non-specialist users.

The list is curated, not exhaustive. Submit additions via PR with citation.

## 會計 (accounting / 簿記)

| Locale | Formal | Friendlier alternative | Notes |
|---|---|---|---|
| zh-TW | 沖正 | 撤銷 / 取消 | 沖正 is correct accounting jargon for a corrective entry but unfamiliar to lay users. "撤銷" reads as "revert" which most consumer-finance apps use. |
| zh-CN | 冲正 | 撤销 / 取消 | Same logic as zh-TW. 冲正 sounds like a back-office banking term. |
| ja | 仕訳 | 取引 / 内訳 | 仕訳 is a true accounting term ("journal entry") but consumer apps often use 取引 ("transaction") or 内訳 ("breakdown"). |
| ja | 振替 | 移動 | 振替 is the correct term for a transfer entry; 移動 is the everyday equivalent. |
| zh-TW | 損益 | 收支 | 損益 is "P&L"; 收支 is "income & expense" — both are valid, the latter is consumer-friendlier. |
| zh-CN | 损益 | 收支 | Same as zh-TW. |

## 醫療 (medical) — *(略 / abbreviated)*

> Curation not yet started. PRs welcome with citations to localisation style guides (e.g. NCBI / 国立国語研究所 medical-localization corpora).

## 法律 (legal) — *(略 / abbreviated)*

> Curation not yet started. Legal terminology localisation tends to be jurisdiction-specific; entries should cite the governing statute or industry style guide.

## How a project consumes this list (v6.6.1+)

This file is curated as a **menu**, not a default. To enforce it for your project, copy the relevant rows into `<project>/.kiho/config/i18n-glossary.toml` using the v6.6.1 Check 6 schema (see `references/i18n-glossary-schema.md`):

### Copy-paste starter — consumer ledger app

```toml
# <project>/.kiho/config/i18n-glossary.toml

[max_chars]
# Short-button labels — tight ceilings keep them on one line in narrow UIs.
"common.REVERT" = { en = 6, "zh-TW" = 4, "zh-CN" = 4, ja = 4 }
"common.CANCEL" = { en = 6, "zh-TW" = 4, "zh-CN" = 4, ja = 4 }

[forbidden]
# Picked from the 會計 (accounting) row above — deny formal jargon in
# consumer copy. Use the friendlier alternatives the row recommends.
"common.REVERT" = { "zh-TW" = ["沖正"], "zh-CN" = ["冲正"], ja = ["仕訳"] }
"common.TRANSFER" = { ja = ["振替"] }

[tone]
# v2.1 reservation — v6.6.1 ignores this block with a one-shot stderr log.
"common.REVERT" = "informal"
```

The audit will then surface (warn) any locale value that exceeds the per-locale max-char and (fail) any locale value that contains a forbidden substring.

### Copy-paste starter — finance-pro app

A finance-pro app may legitimately want 沖正; in that case, **do not copy** the `forbidden` row for `common.REVERT`. Use only the `max_chars` constraints, or omit the glossary entirely. The framework is opt-in; v1 behaviour persists when no glossary exists.

### Why no automatic adoption

Localisation is editorial. The audit will not pick formal-vs-friendly for you. Inclusion in this advisory list is a recommendation surfaced for human decision — the actual constraint lands only when an editor copies a row into the project glossary.

## Why this is opt-in

Localisation choice is editorial. A finance-pro app may legitimately want 沖正; a consumer ledger app may want 撤銷. The framework doesn't pick for you; it surfaces the candidate so you can decide.

## Cross-references

- `references/i18n-quality.md` §"v2 clarity heuristic" — public-facing description
- `references/i18n-glossary-schema.md` — full per-project glossary schema (v6.6.1)
- `skills/engineering/i18n-audit/references/i18n-quality.md` — internal heuristic catalogue
- `bin/i18n_audit.py::check_clarity` — Check 6 implementation
- `tests/test_i18n_audit_glossary.py` — synthetic acceptance + unit suite
