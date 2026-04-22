# kiho v5.22 — Upgrade Proposals

> **編號法**：`U1..U12`，每條含 problem / patch 檔案 / diff summary / 驗收。

---

## U1 — PreToolUse hook：攔截 agent.md 直寫（enforces `recruit`）

**問題**：CEO 直接 `Write` 到 `$COMPANY_ROOT/agents/<id>/agent.md` 繞過 `recruit` skill。

**新檔**：`plugins/kiho/hooks/pre-write-agent.json`

```json
{
  "event": "PreToolUse",
  "matcher": "Write",
  "when": "tool_input.file_path matches '.*kiho[/\\\\]agents[/\\\\][^/\\\\]+[/\\\\]agent\\.md$'",
  "disabled": false,
  "prompt": "You are about to write an agent.md file. This MUST go through the `recruit` skill (quick-hire or careful-hire), not direct Write. The recruit skill produces role-spec → candidate pool (design-agent) → interview-simulate → auditor review → hiring committee → agent.md. If you have ALREADY completed those steps this turn and this Write is the final materialization, include in your response before the Write: `RECRUIT_CERTIFICATE: ceo-01 confirms recruit skill session <id> completed with interview score >= 3.5 and committee approval`. Otherwise abort this Write and invoke `recruit` skill."
}
```

**驗收**：在 web3-quant-engine session 5 情境下，CEO 會被擋下來無法直接 Write agent.md。

---

## U2 — PreToolUse hook：攔截 KB wiki 直寫

**問題**：CEO Write 直接寫到 `.kiho/kb/wiki/*.md` 跳過 `kiho-kb-manager`。

**新檔**：`plugins/kiho/hooks/pre-write-kb.json`

```json
{
  "event": "PreToolUse",
  "matcher": "Write|Edit",
  "when": "tool_input.file_path matches '.*\\.kiho[/\\\\]kb[/\\\\]wiki[/\\\\].*\\.md$' AND current_agent != 'kiho-kb-manager'",
  "disabled": false,
  "prompt": "Direct writes to .kiho/kb/wiki/ are forbidden. Use `kiho-kb-manager` skill via Agent(subagent_type: 'kiho:kiho-kb-manager'). This enforces Karpathy-wiki invariants (root files, tier indexes, post-write lint). See `skills/kb/kb-add/SKILL.md`."
}
```

**驗收**：session 1-6 的 KB 寫入被擋；CEO 強制繞 kiho-kb-manager。

---

## U3 — CEO persona：Invariants 加兩條 + 明示 ledger 真實性

**改**：`plugins/kiho/agents/kiho-ceo.md` §Invariants

原本：
```
- **Delegate every request.** Inline execution bypasses RACI...
- **Route every KB write through `kiho-kb-manager`.** Direct writes corrupt...
```

改後加：
```
- **Never write to `$COMPANY_ROOT/agents/*.md` directly.** New agents MUST pass through `recruit` skill (quick-hire: 2 candidates, mini-committee; careful-hire: 4 candidates × 6 rounds × 4 auditors + full committee). Direct Write bypasses role-spec, interview-simulate, rubric, auditor review — the four mechanisms that catch bad agent design. If you believe a shortcut is justified, log it as `action: recruit_shortcut_taken` with `reason: <why>` and flag for next perf-review cycle.

- **Ledger truthfulness.** Every `action: delegate, target: X` entry MUST correspond to a real `Agent(subagent_type: X-or-compatible)` tool call in this turn. Before writing `action: done`, walk back through the ledger and confirm each delegate has a matching subagent_return. If any delegate lacks a return, classify as drift: log `ledger_drift_detected: true` and flag for next turn's self-reflect.
```

**驗收**：CEO 書寫 ledger 前要先自檢。下次若想寫 `target: kiho-researcher` 而實際用 general-purpose，自檢會抓。

---

## U4 — CEO INITIALIZE：step 7 改為 REQUIRED

**改**：`plugins/kiho/agents/kiho-ceo.md` §INITIALIZE

原本 step 7 是 LAZY：
> 7. Invoke `research` skill op=`kb-search` with the user's request as query — check if the KB already has relevant context. Do not proceed without this.

當前 LAZY 註解：「on a fresh project ... MUST fall through silently」。

改為 **REQUIRED with explicit skip logging**：
```
7. **[REQUIRED]** Invoke `research` skill op=`kb-search` with the user's request as query. If the KB has ≥1 matching entry with confidence ≥ 0.75, incorporate into context. If KB is empty (fresh project), MUST log `action: kb_empty_acknowledged, next: will_spawn_kiho_researcher_on_demand` to ceo-ledger. Silent skip is now a drift signal flagged by bin/ceo_behavior_audit.py.
```

**驗收**：CEO 即使在 fresh project 也會寫明「我知道 KB 是空的、我打算怎麼補」。

---

## U5 — CEO INITIALIZE：step 14 移出 LAZY，加 seed 機制

**改**：`plugins/kiho/agents/kiho-ceo.md` §INITIALIZE step 14

原本：LAZY，要讀 `.kiho/agents/ceo-01/memory/.last-reflect` — 該目錄通常不存在。

改為：
```
14. **[REQUIRED]** CEO self-reflection check.
    (a) `ls <project>/.kiho/agents/ceo-01/memory/` — if directory doesn't exist, `mkdir -p` and `touch .last-reflect` with epoch 0, then proceed as "never reflected".
    (b) Read `.last-reflect` timestamp. If epoch 0 OR age > ceo_turn_interval * <avg turn duration>, invoke `memory-reflect` with `agent_id: ceo-01, trigger_type: periodic`.
    (c) Integrate reflection output into this turn's recomposition threshold.
    (d) Update `.last-reflect` to now.
    (e) Log `action: ceo_reflect_complete, age_at_trigger: <seconds>` to ceo-ledger.
```

**驗收**：CEO 第一次跑某專案就會建自己的 memory 目錄；每一後續 turn 都會 reflect 一次（default ceo_turn_interval=1）。

---

## U6 — /kiho entry skill：加 `--tier` 旗標

**改**：`plugins/kiho/skills/kiho/SKILL.md` §Mode parsing

新加旗標：
```
--tier=minimal | normal | careful

    minimal  — skip committees, auditors, interview-simulate. CEO writes ledger with
               `tier: minimal` marker. Use for: throwaway exploration, single-file edit,
               time-boxed spike.
    normal   — default. quick-hire for new agents, research cascade mandatory,
               mini-committee for non-trivial decisions.
    careful  — full machinery. careful-hire for all new agents, 4-auditor review
               for all spec decisions, drift replay on interviews.
```

**新加** §Tier enforcement：
```
When `--tier=minimal` is set, CEO MUST include in every response a visible header:
  ⚠️ MINIMAL TIER — ceremonies skipped. See `.kiho/state/ceo-ledger.jsonl` for what was shortened.
When `--tier=careful` is set, CEO MUST NOT write any action without explicit skill invocation
  — no `Write` to `$COMPANY_ROOT/agents/`, no `Write` to `.kiho/kb/wiki/`, no main-thread
  research beyond 30 seconds.
```

**驗收**：使用者明示選 tier；CEO 沒有隱性簡化空間。

---

## U7 — Session-start hook：啟用 + 強制 tier 宣告

**改**：`plugins/kiho/hooks/session-start.json`

```json
{
  "event": "SessionStart",
  "disabled": false,
  "description": "Remind CEO to declare operating tier at start of every /kiho turn.",
  "prompt": "If user invokes /kiho (any form) in this turn, CEO MUST declare tier as first action in response, using visible marker: `TIER: minimal | normal | careful` (default: normal unless user specified --tier). This declaration goes into ceo-ledger `action: tier_declared` entry before any delegation."
}
```

**驗收**：每 /kiho turn 開頭都有明示 tier；使用者看得見 CEO 在哪個 discipline 等級。

---

## U8 — Recruit skill：加 pre-emit gate

**改**：`plugins/kiho/skills/core/hr/recruit/SKILL.md` §Procedure

在「emit agent.md」步驟前加：
```
### Pre-emit gate (v5.22)

Before writing agent.md to `$COMPANY_ROOT/agents/<id>/agent.md`, recruit MUST confirm:

1. role_spec.md exists at `<spec_path>` with four-field contract complete
2. interview-simulate output exists at `_meta-runtime/interview-runs/<candidate_id>/<timestamp>.json`
   with `aggregate.mean >= 3.5` (quick-hire) or >= 4.0 (careful-hire)
3. For careful-hire: 4 auditor scores + committee decision exist at
   `_meta-runtime/hiring-committees/<spec_id>/decision.md` with status: approved
4. rejection-feedback written for all non-winning candidates (careful-hire only)

If any of (1)-(4) is missing, recruit MUST NOT emit the agent.md. Abort with
`status: pre_emit_gate_failed, missing: [...]`.

This gate is enforced by the write-to-agents hook (U1). The hook blocks direct Write
unless the response includes `RECRUIT_CERTIFICATE: <spec_id> gate_passed`.
```

**驗收**：即使 CEO 想繞過 recruit，hook 會擋；recruit 自己也有 gate 不讓半路出廠。

---

## U9 — Ledger integrity audit 腳本

**新檔**：`plugins/kiho/bin/ceo_behavior_audit.py`

偽碼：
```python
#!/usr/bin/env python
"""
Scan ceo-ledger.jsonl and flag drift between declared actions and actual tool calls.

Input:  <project>/.kiho/state/ceo-ledger.jsonl
        + session transcript (if available) or reconstruct via Bash tool history
Output: _meta-runtime/ceo-behavior-audit-<ts>.md

Checks per ledger entry:
  - action: delegate
      → confirm matching Agent tool_use with subagent_type == target (or alias)
      → confirm corresponding subagent_return entry exists
  - action: kb_add, kb_update
      → confirm caller was kiho-kb-manager (not direct Write)
  - action: recruit
      → confirm role-spec + interview-simulate artifacts exist on disk
  - action: committee_open
      → confirm 3+ participant votes in committee log

Drift severity:
  - CRITICAL: declared recruit but no role-spec exists
  - CRITICAL: declared kb_add but wiki file mtime > ledger entry with Write tool (not kb-manager)
  - MAJOR:    declared target but no subagent_return
  - MINOR:    target mismatch (e.g., general-purpose substituted for kiho-researcher)

Output appended to next turn's CEO INITIALIZE as "last turn drift report".
"""
```

**驗收**：session 1-6 的 ledger 跑這腳本會產出 ~10 個 CRITICAL drift，逼使用者看到。

---

## U10 — CEO DONE step：加 ledger integrity check

**改**：`plugins/kiho/agents/kiho-ceo.md` §DONE

原 step 11：「Report a structured summary to the user. Then end the turn.」

插入新 step 11a（step 11 往後移）：
```
11a. **[REQUIRED]** Run `python ${CLAUDE_PLUGIN_ROOT}/bin/ceo_behavior_audit.py
     --ledger <project>/.kiho/state/ceo-ledger.jsonl --turn-from <start_ts>`.
     If audit returns CRITICAL drift:
       - Prepend to user summary: "⚠️ I found drift in my own ledger: <summary>."
       - Append proposal to next turn's plan.md: "Address drift: <items>"
       - Log `action: self_audit_drift_detected, severity: critical, count: N`
     If MAJOR drift: include a briefer note.
     If clean: log `action: self_audit_clean`.
```

**驗收**：CEO 每 turn 結束前要誠實自審，不能假裝；使用者看到明示的 drift 警告。

---

## U11 — `memory-reflect` auto-invoke on user feedback

**問題**：使用者 session 3 說「MCP 不適合 AI」、session 5 糾正「kiho 是 dev tool」、session 6 問「有跑 interview 嗎」— 這些珍貴 feedback 只進了管理 journal，沒進 CEO 的 soul/memory，未來 session 可能再犯。

**改**：`plugins/kiho/agents/kiho-ceo.md` §LOOP step d (VERIFY)

當結果是 `ASK_USER` 且使用者回覆包含糾正語氣（keywords：「actually」、「wrong」、「not right」、「over-engineer」、「should」、「why didn't you」、中文「應該」、「其實」、「不要」、「改」）：

```
Add to step d:
  If user_reply contains correction keywords:
    - Before proceeding, invoke `memory-reflect` with:
        agent_id: ceo-01
        trigger_type: user_correction
        correction_text: <user_reply>
        prior_action: <what I just did that was corrected>
    - The reflection updates my soul's §6 Behavioral rules or §10 Blindspots if warranted
    - Log `action: ceo_reflect_from_correction, skill_candidate: <if any>`
    - If the correction touches a project-invariant (architecture / tooling pivot),
      also queue a `skill-derive` candidate for project-KB
```

**驗收**：使用者糾正一次，CEO 在自己的 soul 永久記住，不再重犯。

---

## U12 — Sub-agent type autocomplete / suggestion

**問題**：`kiho:kiho-researcher` 名字長，CEO 習慣用 `general-purpose`。

**新檔**：`plugins/kiho/agents/_kiho-lint.md`（非 agent，是 meta 說明被 CEO 載入）

內容：
```
# Preferred sub-agents for CEO

When considering `Agent(subagent_type: ...)`, prefer the specialized kiho agent over
`general-purpose` for these cases:

| Intent | Preferred subagent_type | Why |
|---|---|---|
| 研究 (facts, market data, SDK) | `kiho:kiho-researcher` | Has deepwiki+WebSearch+trusted-source registry discipline |
| KB 操作 | `kiho:kiho-kb-manager` | Only agent authorized for `.kiho/kb/wiki/` |
| 招募 | `kiho:kiho-recruiter` | Runs role-spec + interview-simulate |
| 委員會決議 | `kiho:kiho-clerk` | Impartial transcript extraction |
| Agent 設計 | 透過 `recruit` skill → `kiho:kiho-hr-lead` | Not direct |
| 一次性探索 / 混合任務 | `general-purpose` | OK for quick spikes |

If you find yourself about to Agent(subagent_type: "general-purpose") for research,
stop: that's the anti-pattern. Re-route through kiho:kiho-researcher.
```

**改**：`plugins/kiho/agents/kiho-ceo.md` front-matter `skills` list 加 `sk-meta-prefer-kiho-agents`（或在 §Invariants 引用此檔）。

**驗收**：CEO 看到這個 cheat sheet 有較大機率選對。搭配 U10 的 ledger audit 可持續校準。

---

## 套用順序（建議 PR 拆法）

- **PR 1 (P0, 1 commit)**：U1 + U2（hooks）+ U3 CEO invariants — 阻擋直寫 agents 與 KB
- **PR 2 (P0, 1 commit)**：U4 + U5 + U10 DONE audit — CEO 自檢
- **PR 3 (P0, 1 commit)**：U8 recruit pre-emit gate + U9 audit script — recruit 嚴謹化
- **PR 4 (P1, 1 commit)**：U6 `--tier` + U7 session-start hook — tier discipline
- **PR 5 (P1, 1 commit)**：U11 memory-reflect on correction + U12 preferred subagents — learning loop
- **PR 6 (P2)**：回歸測試 — 跑 web3-quant-engine session 1-6 prompt replay（或 skill `_meta/ceo-replay-harness` 新建），驗證新規則下 CEO 不再 drift

## 影響面 / 破壞性

| Upgrade | 現有 project 需遷移？ | User 感受 |
|---|---|---|
| U1 hook | 舊 project 不受影響（只在 CEO 想 Write 時觸發） | CEO 變嚴格；可能 turn 會多一次 recruit |
| U2 hook | 同上 | KB 寫入會多一跳 |
| U3 invariants | 舊 ledger 可能有 "drift" 被標註 | CEO 更可信 |
| U4/U5 INITIALIZE | CEO 每 turn 多 2-3 個 tool call | 第一次跑 +300 tokens，後續穩定 |
| U6 --tier | 完全向後相容（default normal） | 使用者得新旗標 |
| U7 session-start | 視覺上每 turn 多一行 TIER 宣告 | 一眼看出 CEO 紀律 |
| U8 recruit gate | 沒跑正規 recruit 的 project 改 career-hire 時會被擋 | 對 — 這就是目的 |
| U9 audit script | 需 Python 3.11+（已是 kiho 前提） | 使用者多一條 `web3-quant audit self` 命令可跑 |
| U10 DONE audit | 每 turn 結束多 1 個 Bash call | 誠實稅 |
| U11 memory-reflect auto | CEO soul 會隨糾正演化 | 長期越來越對齊使用者 |
| U12 preferred subagents | 純 documentation | 零負擔 |
