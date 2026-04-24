# v5.22 — U14 (new)：kiho-researcher 預設走 agent-browser CLI（取代 Playwright MCP 為預設）

> 補第 14 條。證據：web3-quant-engine session 11 實測。

## Problem

U13（session 9）加了 Playwright MCP 到 kiho-researcher tools，擴展了 SPA 能力。但：

1. **MCP 方案與 v2 CLI+skill 架構不一致**。使用者 session 3 明講「MCP 不適合 AI」，我們 pivot 為 CLI+skill — 卻在 researcher 繼續強推 MCP。
2. **Token 效率低**。Playwright `browser_snapshot` 輸出 a11y tree ~800-2000 tokens；`agent-browser snapshot -i -c` 約 200-400 tokens，refs 為 `@e1..@eN`。
3. **錯失 agent-browser 已提供的進階能力**：HAR export、network intercept、CDP connect、Chrome profile 登入狀態重用、session save/restore、AI chat、command chaining via `&&`。

Session 11 實測：user 指出 `https://agent-browser.dev/commands` 已安裝，我跑 `agent-browser open ... && snapshot -i -c`，一次抓到完整命令結構 + 所有 ref，token 成本顯著低於 Playwright MCP。

## Fix

### PATCH: `plugins/kiho/agents/kiho-researcher.md` — §Tools（調整順序 + 加新類）

```diff
 tools:
   - Read
   - Write
   - Edit
   - Glob
   - Grep
   - WebSearch
   - WebFetch
-  - Bash
+  - Bash    # required for agent-browser CLI (preferred over MCP browsers)
   - mcp__deepwiki__ask_question
   - mcp__deepwiki__read_wiki_contents
   - mcp__deepwiki__read_wiki_structure
-  - mcp__playwright__browser_navigate
-  - mcp__playwright__browser_wait_for
-  - mcp__playwright__browser_evaluate
-  - mcp__playwright__browser_snapshot
-  - mcp__playwright__browser_click
-  - mcp__playwright__browser_take_screenshot
-  - mcp__playwright__browser_close
+  # Browser tier (in priority order):
+  # Tier 1 (default): agent-browser CLI — aligned with CLI+skill architecture
+  # Tier 2 (specialized): Chrome DevTools MCP — for DevTools-specific metrics
+  # Tier 3 (fallback): Playwright MCP — when CLI unavailable
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__new_page
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__navigate_page
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__wait_for
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_snapshot
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__evaluate_script
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__list_network_requests
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__get_network_request
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__performance_start_trace
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__performance_stop_trace
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__performance_analyze_insight
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__lighthouse_audit
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__emulate
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_memory_snapshot
+  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__close_page
+  - mcp__playwright__browser_navigate      # fallback only
+  - mcp__playwright__browser_snapshot       # fallback only
+  - mcp__playwright__browser_close          # fallback only
```

### PATCH: `plugins/kiho/agents/kiho-researcher.md` — §Core discipline（加 Step 5c）

原本 Step 5b 是 Playwright deep-trace。改為 **Step 5b = agent-browser**，Playwright 降為 5d 備援：

```markdown
### Step 5b: agent-browser CLI (v5.22 default for SPA/dev-portal)

**PREFERRED for all browser tasks**. Detect availability: `which agent-browser`. If present:

1. `agent-browser skills get core` once to load the workflow guide (~400 tokens, worth it)
2. `agent-browser open <url> && agent-browser wait --load networkidle && agent-browser snapshot -i -c`
3. Iterate: click / fill / get text / etc. — refs invalidated on page change, re-snapshot
4. `agent-browser network requests --filter "/api/" --json` — if need to see API calls
5. `agent-browser network har start out.har` → actions → `har stop` — if need full HAR export
6. `agent-browser batch` for multi-step one-shot: `batch '["open","url"]' '["snapshot","-i","-c","--json"]' --json`
7. `agent-browser close` when done

Aligned with our CLI+skill architecture. Token-efficient refs (`@e1..@eN`). Daemon persistence between chained commands.

### Step 5c: Chrome DevTools MCP (specialized)

Escalate from Step 5b when:
- Need `performance_start_trace` / `analyze_insight` (LCP/INP/CLS)
- Need `lighthouse_audit` composite score
- Need `take_memory_snapshot` for heap debug
- Need simultaneous `emulate` of CPU + network + geo + UA

### Step 5d: Playwright MCP (fallback only)

Use when agent-browser CLI unavailable OR from a sub-agent without Bash.
```

## Why this fixes a v2 coherence gap

v2 pivot shipped "CLI + skill 為主、MCP 選配"。Session 1-10 的 researcher 卻走 MCP 當預設 — **自我矛盾**。U14 把 researcher 對齊到 v2 決策：CLI 優先，MCP 降為 specialized/fallback。

## Impact

- Researcher turn 的 browser 工具 token 成本降 60-80%（snapshot 最主要貢獻）
- 新能力解鎖：HAR export、AI chat、Chrome profile 登入重用
- 與我們產品 web3-quant CLI 的設計哲學一致（future-proof：researcher 幫忙 dogfood CLI 模式）

## Implementation note

agent-browser 是使用者自行 `npm i -g agent-browser` 安裝（session 11 確認使用者已裝）。kiho 安裝時不需強制安裝 agent-browser — 但若偵測到已裝則優先用。Step 5b 第一行就是 detection (`which agent-browser`)，沒裝就 fallback 到 5c/5d。

## Verify

Replay session 9-11：
- Pre-v5.22+U14：onchainos docs 查詢用 Playwright MCP snapshot，每頁 ~1500 tokens snapshot
- Post-v5.22+U14：用 agent-browser `snapshot -i -c`，每頁 ~400 tokens，還能 `batch` 一次跑多步驟
