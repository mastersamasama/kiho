# i18n known jargon (advisory, sk-087.v2 input)

> **ADVISORY ONLY.** Projects choose adoption via `<project>/.kiho/config/glossary.toml` with `clarity.adopt_advisory = true`. The audit does NOT enforce these substitutions; the v2 clarity check (when shipped) emits `severity: info` findings only.

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

## How a project consumes this list

```toml
# <project>/.kiho/config/glossary.toml
[clarity]
adopt_advisory = true
domains = ["accounting"]   # only check accounting jargon
```

When v2 is shipped, the audit will read this glossary, cross-reference matching keys against this advisory list, and emit `severity: info` findings for any locale string that uses a formal term where the friendlier alternative might suit. The findings are advisory only — they never block CI.

## Why this is opt-in

Localisation choice is editorial. A finance-pro app may legitimately want 沖正; a consumer ledger app may want 撤銷. The framework doesn't pick for you; it surfaces the candidate so you can decide.

## Cross-references

- `references/i18n-quality.md` §"v2 glossary clarity heuristic" — public-facing description
- `skills/engineering/i18n-audit/references/i18n-quality.md` §"v2 clarity heuristic" — internal hook spec
- `bin/i18n_audit.py::_check_clarity_v2` — stub implementation
