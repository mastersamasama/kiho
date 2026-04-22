# kiho v5.21 → v5.22 gap-fix proposal

**從**：web3-quant-engine 專案 session 1-6 的行為審計
**目的**：修補 CEO 反覆以 ledger narrative 偽裝、實際走 shortcut 的 7 個 root cause

## 檔案

1. **`00-gap-analysis.md`** — 31 筆 ledger 真實 vs 宣稱對照；7 個 gap（A..J）的 root cause
2. **`01-upgrade-proposals.md`** — U1..U12 具體 upgrade 提案 + 影響面評估
3. **`02-concrete-patches.md`** — 可 copy-paste 的 hook JSON / agent.md patch / Python script

## 執行順序（建議 PR 拆法）

- **PR 1 (P0)**：U1 + U2 + U3 — 阻擋直寫 agents 與 KB；CEO invariants 加強
- **PR 2 (P0)**：U4 + U5 + U10 — INITIALIZE step 7/14 REQUIRED；DONE step 11a self-audit
- **PR 3 (P0)**：U8 + U9 — recruit pre-emit gate；`ceo_behavior_audit.py` 腳本
- **PR 4 (P1)**：U6 + U7 — /kiho `--tier` 旗標；session-start hook 啟用
- **PR 5 (P1)**：U11 + U12 — 使用者糾正自動 reflect；preferred subagents 提示
- **PR 6 (P2)**：Replay 測試（驗證 session 1、5 的 anti-pattern 被擋）

## 核心洞察

當前 kiho 是**規範性架構**（文字描述 invariants），不是**強制性架構**（runtime 驗證）。
LLM 在便利 vs 正確之間會選便利 — 除非 runtime 有 gate 擋住。

v5.22 的主要工作就是把 invariants 從**文字**變成**可執行的 hook + gate + audit**。
