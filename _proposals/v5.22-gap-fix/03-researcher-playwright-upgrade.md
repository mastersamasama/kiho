# v5.22 — U13 (new)：researcher 加 Playwright + 深挖 SOP

> 於 `01-upgrade-proposals.md` 上補第 13 條；證據來自 web3-quant-engine session 9 實測。

## Problem

session 8 的 researcher（即使用了 deepwiki + WebSearch + 本地 clone）仍然**只看到一層深**的 onchainos — 以 CLI 硬編的 16 鏈為準，錯過了：
- Open API 實際 27 鏈（backend 遠超 CLI）
- **API 有費用結構**（Trial/Basic/Enterprise；正滑點最多 10% 被捕獲）
- **x402 支付協議**（Agent 自主付費，Coinbase 規範）
- Agentic Wallet vs Open API 兩條產品線的區分
- Skills + MCP Server 是官方雙軌整合路徑

根因：`WebFetch` 無法解 JS-heavy SPA（`web3.okx.com/zh-hans/onchainos/dev-docs/*` 是 React SPA，初始 HTML 只有 shell）。需要 Playwright 走瀏覽器 hydration 後 DOM 抽取。

## Fix

### PATCH: `plugins/kiho/agents/kiho-researcher.md` — tools 加 Playwright

```diff
 tools:
   - Read
   - Write
   - Edit
   - Glob
   - Grep
   - WebSearch
   - WebFetch
   - Bash
   - mcp__deepwiki__ask_question
   - mcp__deepwiki__read_wiki_contents
   - mcp__deepwiki__read_wiki_structure
+  - mcp__playwright__browser_navigate
+  - mcp__playwright__browser_wait_for
+  - mcp__playwright__browser_evaluate
+  - mcp__playwright__browser_snapshot
+  - mcp__playwright__browser_click
+  - mcp__playwright__browser_take_screenshot
+  - mcp__playwright__browser_close
```

### PATCH: `plugins/kiho/agents/kiho-researcher.md` — §Core discipline（cascade 加一條）

原本 5 步 cascade：KB → trusted-source → Web → Deepwiki → Clone → Escalate

加入 **step 5b (Playwright deep-trace)**：
```markdown
### Step 5b: Playwright deep-trace for SPA dev portals (v5.22)

When external documentation URL is a **JS-heavy SPA** (detect: WebFetch returns < 1000 chars OR HTML body contains `<div id="root"></div>` / `<div id="__next">`), escalate from WebFetch to Playwright:

1. `mcp__playwright__browser_navigate(url)` — render
2. `mcp__playwright__browser_wait_for(text: <expected_heading>, time: 5)` — SPA hydration
3. `mcp__playwright__browser_evaluate` with DOM traversal:
   - extract `document.title`, main text (walk h1/h2/h3 + siblings)
   - enumerate `<table>` innerText (pricing / support / rate-limit 表常在這)
   - dedupe sidebar `<a>` links — **critical: sub-pages contain the real truth**
4. **Always** follow sidebar to at least:
   - `**/supported-chain` or `**/networks` — ground-truth chain list (often > marketing claim)
   - `**/api-fee` or `**/pricing` — cost structure (often hidden; often contradicts "free")
   - `**/authentication` or `**/api-access` — rate limits, KYC, gates
   - `**/sdk-introduction` — official SDK vs community forks
5. `mcp__playwright__browser_close` — clean session

Trigger is SPA-detection, not URL pattern. Confidence on Playwright output: 🟢 if DOM extracted cleanly; 🟡 if partial hydration timeout.
```

### PATCH: `plugins/kiho/agents/kiho-researcher.md` — §Anti-patterns（新增）

```markdown
## Anti-patterns

- ❌ Use `WebFetch` on a JS SPA and report "page empty" — always Playwright for SPA
- ❌ Trust first page's text alone — sidebar nav reveals much more than marketing page
- ❌ Stop at product overview — always trace to `supported-chain`, `api-fee`, `errors`, `sdk-introduction` sub-pages
- ❌ Close browser before extracting all needed data — each re-navigate costs seconds
- ❌ Report "free API" without checking `/pricing` or `/terms` — positive slippage capture is a common hidden cost
```

## Why this fixes U12 and gap-analysis Gap A more broadly

session 8 的 researcher **走對了 deepwiki + WebSearch + local clone**，但 **遇到 SPA 就卡住**（dev.com 這種 docs site 幾乎全是 SPA）。補 Playwright 之後能深挖到 `/pricing` `/supported-chain` `/authentication` 這類藏真相的子頁。

## Impact

- 每個 researcher turn 多 2-4 個 Playwright tool call（~5-10 秒 wall-clock）
- 發現 hidden cost / pricing gotcha / backend-CLI 落差的機率顯著提升
- 對量化 decision 質量提升遠大於 overhead

## Verification

case study 可 replay：
1. pre-v5.22 researcher 回答 onchainos 時不會發現 x402 / api-fee / 兩產品線
2. post-v5.22 researcher 必 Playwright `/home/supported-chain`、`/trade/api-fee`、`/home/agentic-wallet-overview` 三頁
3. Report 多出「API 費用」「正滑點捕獲」「x402 支付」三個章節

## 併入 `01-upgrade-proposals.md` 的 PR 2 還是 PR 3？

建議歸 **PR 1**（最快落地 — 就是 agent.md 加 6 個 tool 名 + cascade 加一段）。排在 U1-U3 之後即可 ship。
