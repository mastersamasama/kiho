# kiho v5.22 — Concrete Patch Diffs (ready to apply)

> 把 `00-gap-analysis.md` + `01-upgrade-proposals.md` 的決策落成可 copy-paste 的檔案。
> 每段標示 `# WRITE: <path>` 或 `# PATCH: <path>` 告訴你放哪。
> 套用順序依 `01-upgrade-proposals.md` PR 1 → PR 5。

---

## PR 1 — Hooks + CEO Invariants

### WRITE: `plugins/kiho/hooks/pre-write-agent.json`
```json
{
  "event": "PreToolUse",
  "matcher": "Write",
  "when": "tool_input.file_path matches '.*[\\\\/]kiho[\\\\/]agents[\\\\/][^\\\\/]+[\\\\/]agent\\.md$'",
  "disabled": false,
  "description": "Block direct agent.md writes; enforce recruit skill.",
  "prompt": "You are about to write an agent.md file directly. This bypasses the `recruit` skill (role-spec → design-agent candidates → interview-simulate → auditor review → hiring committee). Before proceeding:\n\n1. If this is the FINAL materialization AFTER the recruit skill completed in this turn, include in your response (ABOVE the Write call) a visible certificate:\n   `RECRUIT_CERTIFICATE: quick-hire|careful-hire <role_name> — interview_score <X.XX> — committee: approved — role_spec_path: <path>`\n2. Otherwise, abort this Write. Invoke `recruit` skill first. The recruit skill will eventually call Write through its own protocol."
}
```

### WRITE: `plugins/kiho/hooks/pre-write-kb.json`
```json
{
  "event": "PreToolUse",
  "matcher": "Write|Edit",
  "when": "tool_input.file_path matches '.*[\\\\/]\\.kiho[\\\\/]kb[\\\\/]wiki[\\\\/].*\\.md$'",
  "disabled": false,
  "description": "Block direct KB wiki writes; enforce kiho-kb-manager.",
  "prompt": "Direct writes to `.kiho/kb/wiki/` are forbidden for all agents except kiho-kb-manager. Karpathy-wiki invariants (root files, tier indexes, post-write lint pipeline) are only maintained by kiho-kb-manager. Route this write via: `Agent(subagent_type: 'kiho:kiho-kb-manager', prompt: 'kb-add/kb-update with <content>')`. If the current agent IS kiho-kb-manager, include the certificate `KB_MANAGER_CERTIFICATE: op=<add|update|delete> entry=<slug> tier=<project|company>` above the Write."
}
```

### PATCH: `plugins/kiho/agents/kiho-ceo.md` — §Invariants (append)
```markdown
- **Never write to `$COMPANY_ROOT/agents/*/agent.md` directly.** New agents MUST pass through the `recruit` skill. Quick-hire: 2 candidates + mini-committee. Careful-hire: 4 candidates × 6 rounds × 4 auditors + full committee. Direct Write bypasses role-spec, interview-simulate, rubric, auditor review — the four mechanisms that catch bad agent design. If a shortcut is justified, log `action: recruit_shortcut_taken, reason: <why>, waived_gates: [role_spec|interview|auditor|committee]` — this flag is visible to `kiho-perf-reviewer` next cycle.

- **Ledger truthfulness.** Every `action: delegate, target: X` ledger entry MUST correspond to a real `Agent(subagent_type: X-or-compatible-alias)` tool call in this turn. Before writing `action: done`, run the integrity check (`bin/ceo_behavior_audit.py`); if any delegate lacks a matching subagent_return OR target mismatch (e.g., wrote `kiho-researcher` but actually spawned `general-purpose`), log `ledger_drift_detected: true` with severity, and include a ⚠️ in the final user summary.

- **Research cascade is delegated, not inline.** Main-thread WebSearch / WebFetch / mcp__deepwiki_* calls exceeding 30 seconds cumulative OR 3 tool calls in a turn MUST be re-routed via `Agent(subagent_type: 'kiho:kiho-researcher')`. CEO-direct research is acceptable only for sub-30s sanity checks. Log exceptions as `action: inline_research_justified, reason: <why>`.
```

---

## PR 2 — INITIALIZE fixes + DONE self-audit

### PATCH: `plugins/kiho/agents/kiho-ceo.md` — §INITIALIZE step 7 (replace)

原文：
> 7. Invoke `research` skill op=`kb-search` with the user's request as query — check if the KB already has relevant context. Do not proceed without this.

取代為：
```markdown
7. **[REQUIRED, no longer LAZY]** KB seed check.
   (a) Invoke `research` skill op=`kb-search` with the user's request as query, scope `both`.
   (b) If returns ≥1 entry with confidence ≥ 0.75: incorporate into working context.
   (c) If KB is empty (count == 0) on a fresh project: log `action: kb_empty_acknowledged, plan: will_spawn_kiho_researcher_on_demand_for_first_factual_question` to ceo-ledger. Proceed.
   (d) If KB has entries but NONE match (count == 0 for query): log `action: kb_no_match, query: <hash>, plan: delegate_research`. Proceed.
   (e) Silent skip is now a drift signal caught by `bin/ceo_behavior_audit.py`.
```

### PATCH: `plugins/kiho/agents/kiho-ceo.md` — §INITIALIZE step 14 (replace)

原文：LAZY self-reflection that assumed `.last-reflect` exists.

取代為：
```markdown
14. **[REQUIRED]** CEO self-reflection.
    (a) Check `<project>/.kiho/agents/ceo-01/memory/` existence. If missing: `mkdir -p` it and `touch .last-reflect` with epoch 0.
    (b) Read `.last-reflect` timestamp. If epoch 0 OR age-in-seconds > (ceo_turn_interval * 60): proceed to (c). Else skip to (e) logging `ceo_reflect_skipped_too_recent`.
    (c) Invoke `memory-reflect` skill with `agent_id: ceo-01, trigger_type: periodic`.
    (d) Integrate reflection output into this turn's recomposition threshold AND (new) set `this_turn_avoid_patterns: [...]` from the reflection.
    (e) Update `.last-reflect` to now; log `action: ceo_reflect_complete, age_at_trigger_s: <n>, patterns_to_avoid_count: <n>`.
```

### PATCH: `plugins/kiho/agents/kiho-ceo.md` — §DONE (insert new step 11a)

```markdown
11a. **[REQUIRED]** Ledger integrity self-audit.
     Run: `python ${CLAUDE_PLUGIN_ROOT}/bin/ceo_behavior_audit.py --ledger <project>/.kiho/state/ceo-ledger.jsonl --turn-from <turn_start_ts>`
     Parse the return:
       - CRITICAL drift: prepend to user summary "⚠️ Self-audit flagged: <N> critical ledger drifts — <top-3-summary>". Append plan.md entry: "Address drift: <items>". Log `action: self_audit_drift_detected, severity: critical, count: N`.
       - MAJOR drift: include a 1-line note in summary.
       - CLEAN: log `action: self_audit_clean`.
     NEVER suppress a drift finding. Honesty is a red line.
```

---

## PR 3 — Recruit pre-emit gate + audit script

### PATCH: `plugins/kiho/skills/core/hr/recruit/SKILL.md` — §Procedure (before agent.md emission)

插入新段：
```markdown
### Pre-emit gate (v5.22)

Before emitting the final agent.md at `$COMPANY_ROOT/agents/<id>/agent.md`, recruit MUST confirm all of the following artifacts exist AND are non-stale:

1. **role_spec.md** at `_meta-runtime/role-specs/<spec_id>/role-spec.md` — four-field contract complete (objective, output_format, tool_boundaries, termination, scaling_rule, work_sample).
2. **interview-simulate result** at `_meta-runtime/interview-runs/<candidate_id>/<timestamp>.json` with:
   - quick-hire: `aggregate.mean >= 3.5`
   - careful-hire: `aggregate.mean >= 4.0` AND all 5 dims >= 3.0 AND drift CV <= 0.15
3. **For careful-hire only**: 4 auditor scores at `_meta-runtime/hiring-committees/<spec_id>/auditor-<persona>.md` for each of {skeptic, pragmatist, overlap_hunter, cost_hawk}.
4. **For careful-hire only**: committee decision at `_meta-runtime/hiring-committees/<spec_id>/decision.md` with `status: approved` AND 3+ participant votes.
5. **rejection-feedback** written at `_meta-runtime/rejections/<spec_id>/<candidate_id>.md` for every non-winning candidate (careful-hire).

If ANY of (1)–(5) is missing for the applicable tier, recruit MUST NOT emit. Abort with `status: pre_emit_gate_failed, missing: [<items>]`. The pre-write-agent hook (U1) is the second-layer defense — even if recruit is bypassed, that hook blocks the Write unless a `RECRUIT_CERTIFICATE` header is present.
```

### WRITE: `plugins/kiho/bin/ceo_behavior_audit.py`
```python
#!/usr/bin/env python3
"""
CEO behavior audit — reconciles ceo-ledger.jsonl claims against actual filesystem
and (if available) transcript evidence.

Exit codes:
  0 — clean (no drift)
  1 — MINOR drift only
  2 — MAJOR drift
  3 — CRITICAL drift (invariant violations)

Usage:
  python ceo_behavior_audit.py --ledger <path> --turn-from <iso_ts>
  python ceo_behavior_audit.py --ledger <path> --full  # audit entire history

Checks (subset):
  - action=delegate, target=X  →  <X>/agent.md exists OR X is a known kiho:* subagent
  - action=kb_add              →  kb entry exists AND was last written by kb-manager
                                  (check via simple `git log --follow <file>` if the project
                                  has git, else mtime heuristic vs the ledger ts)
  - action=recruit             →  _meta-runtime/role-specs/<slug>/role-spec.md exists
                                  AND _meta-runtime/interview-runs/<id>/ has >= 1 result
  - action=committee_open      →  _meta-runtime/committees/<id>/ has >= 3 participant files
  - action=done                →  prior DONE step completion.md shows all Pending items
                                  either resolved or moved to Blocked
  - action=tier_declared       →  value in {minimal, normal, careful}

Output:
  Human markdown report at _meta-runtime/ceo-behavior-audit-<ts>.md
  JSON summary printed to stdout for CEO to parse on DONE step 11a
"""
from __future__ import annotations
import argparse, json, sys, re, subprocess
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

SEVERITY_EXIT = {"clean": 0, "minor": 1, "major": 2, "critical": 3}

@dataclass
class Drift:
    seq: int
    severity: str        # minor | major | critical
    check: str
    declared: str
    actual: str
    hint: str = ""

def iter_ledger(path: Path, turn_from: str | None):
    with path.open() as f:
        for line in f:
            entry = json.loads(line)
            if turn_from and entry.get("ts", "") < turn_from:
                continue
            yield entry

def check_delegate(entry, project_root: Path, drifts: list[Drift]):
    target = entry.get("target", "") or ""
    # Real subagent types available in kiho
    known = {
        "kiho:kiho-researcher", "kiho:kiho-kb-manager", "kiho:kiho-recruiter",
        "kiho:kiho-clerk", "kiho:kiho-auditor", "kiho:kiho-hr-lead",
        "kiho:kiho-eng-lead", "kiho:kiho-pm-lead", "kiho:kiho-perf-reviewer",
        "kiho:kiho-comms", "kiho:kiho-scheduler",
    }
    # Heuristic: if target is narrative ("kiho-researcher-x5" or "deepwiki+websearch"),
    # it's not a real subagent_type; drift.
    if target in known:
        return
    if re.match(r"^general-purpose|kiho-ceo|Explore|Plan$", target):
        return
    if "x" in target and any(c.isdigit() for c in target):   # e.g., "kiho-researcher-x5"
        drifts.append(Drift(entry["seq"], "major", "delegate_target_narrative",
                            target, "no such subagent_type",
                            "declared a fanout like -x5; real Agent calls are individual"))
        return
    if "+" in target or "," in target:   # e.g., "deepwiki-mcp+websearch"
        drifts.append(Drift(entry["seq"], "critical", "delegate_target_fabricated",
                            target, "no such subagent_type; this is main-thread tool use",
                            "route through kiho:kiho-researcher instead"))
        return
    # Otherwise unknown target
    drifts.append(Drift(entry["seq"], "minor", "delegate_target_unknown",
                        target, "not in known list",
                        "verify it exists or normalize name"))

def check_kb_add(entry, project_root: Path, drifts: list[Drift]):
    payload = entry.get("payload", {}) or {}
    entries = payload.get("entries", []) or []
    for slug in entries:
        wiki_path = project_root / ".kiho/kb/wiki" / f"{slug}.md"
        if not wiki_path.exists():
            drifts.append(Drift(entry["seq"], "major", "kb_add_missing_file",
                                slug, f"{wiki_path} not found"))
            continue
        # Best-effort: check if kiho-kb-manager was the actual writer via git blame
        try:
            blame = subprocess.check_output(
                ["git", "log", "--pretty=format:%an", "-n", "1", "--",
                 str(wiki_path)], cwd=project_root, text=True, stderr=subprocess.DEVNULL)
            if blame and "kb-manager" not in blame.lower():
                drifts.append(Drift(entry["seq"], "critical", "kb_add_not_via_manager",
                                    slug, f"last writer: {blame.strip()}",
                                    "direct Write used instead of kiho-kb-manager"))
        except Exception:
            pass  # Non-git project or git unavailable; skip this check

def check_recruit(entry, project_root: Path, drifts: list[Drift]):
    payload = entry.get("payload", {}) or {}
    agents = payload.get("agents", []) or []
    meta = project_root / "_meta-runtime"
    for aid in agents:
        role_spec = meta / "role-specs" / aid / "role-spec.md"
        interview_dir = meta / "interview-runs" / aid
        if not role_spec.exists():
            drifts.append(Drift(entry["seq"], "critical", "recruit_no_role_spec",
                                aid, f"{role_spec} not found",
                                "recruit bypassed role-spec planner"))
        if not interview_dir.exists() or not any(interview_dir.glob("*.json")):
            drifts.append(Drift(entry["seq"], "critical", "recruit_no_interview",
                                aid, f"no files in {interview_dir}",
                                "interview-simulate was not invoked"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True, type=Path)
    ap.add_argument("--turn-from", default=None)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ledger = args.ledger
    project_root = ledger.parents[2]  # .kiho/state/ledger.jsonl → project root

    drifts: list[Drift] = []
    for entry in iter_ledger(ledger, None if args.full else args.turn_from):
        a = entry.get("action", "")
        if a == "delegate":
            check_delegate(entry, project_root, drifts)
        elif a in ("kb_add", "kb_update"):
            check_kb_add(entry, project_root, drifts)
        elif a == "recruit":
            check_recruit(entry, project_root, drifts)

    # Summarize
    by_sev = {"critical": [], "major": [], "minor": []}
    for d in drifts:
        by_sev[d.severity].append(d)

    severity = ("critical" if by_sev["critical"]
                else "major" if by_sev["major"]
                else "minor" if by_sev["minor"]
                else "clean")

    summary = {
        "status": severity,
        "counts": {k: len(v) for k, v in by_sev.items()},
        "drifts": [d.__dict__ for d in drifts[:20]],  # top 20
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Status: {severity.upper()}")
        for sev in ("critical", "major", "minor"):
            for d in by_sev[sev]:
                print(f"  [{sev.upper()}] seq={d.seq} {d.check}: {d.declared} → {d.actual}")

    sys.exit(SEVERITY_EXIT[severity])

if __name__ == "__main__":
    main()
```

---

## PR 4 — /kiho --tier + session-start hook

### PATCH: `plugins/kiho/skills/kiho/SKILL.md` — §Mode parsing (add row)
```markdown
| `--tier=<minimal|normal|careful>` | (any mode) | adds tier marker to ceo-ledger, alters discipline level |
```

### PATCH: `plugins/kiho/skills/kiho/SKILL.md` — add new §Tier discipline
```markdown
## Tier discipline

`--tier` controls how strictly the CEO follows invariants. Defaults to `normal`.

| Tier | Recruit | Research | Committees | KB writes | User-visible marker |
|---|---|---|---|---|---|
| `minimal` | skip allowed (log `recruit_shortcut_taken`) | main-thread OK | skip | direct allowed (log `kb_direct_taken`) | ⚠️ MINIMAL TIER |
| `normal` (default) | quick-hire required for new agent | kiho-researcher preferred, main-thread OK for <30s | mini-committee for non-trivial | via kiho-kb-manager | (none) |
| `careful` | careful-hire only | kiho-researcher mandatory; main-thread research aborts turn | full committee with 4 auditors | strictly via kiho-kb-manager | 🔒 CAREFUL TIER |

Tier is declared in the first line of CEO response (after startup), logged as `action: tier_declared, value: <tier>`. If no tier declared, default `normal` is used and logged.

**Choosing a tier**:
- **Minimal**: throwaway spike, single-file edit, time-boxed exploration, prototype. Expect drift; tag it.
- **Normal**: day-to-day feature / bugfix / refactor. Default.
- **Careful**: lead/senior hiring, security-sensitive decisions, production-bound spec, compliance-relevant changes.
```

### PATCH: `plugins/kiho/hooks/session-start.json`
```json
{
  "event": "SessionStart",
  "disabled": false,
  "description": "CEO MUST declare tier at start of every /kiho turn.",
  "prompt": "If the user invokes /kiho (with or without --tier flag) in this turn, your VERY FIRST visible line of response must be: `TIER: <minimal|normal|careful>` followed by a one-line rationale. Then log `action: tier_declared, value: <tier>` as the first ledger entry of the turn BEFORE any other delegation."
}
```

---

## PR 5 — memory-reflect on correction + preferred subagents cheat sheet

### PATCH: `plugins/kiho/agents/kiho-ceo.md` — §LOOP step d

在 VERIFY 的 ASK_USER 分支末尾插入：
```markdown
(v5.22) If the user's reply contains correction signals — keywords "actually", "wrong", "not right", "over-engineer", "should", "why didn't you", "shortcut", "skip", "bypass" (case-insensitive; also Chinese equivalents "應該", "其實", "不要", "改", "繞過") — BEFORE resuming the loop:

1. Invoke `memory-reflect` with:
   - `agent_id: ceo-01`
   - `trigger_type: user_correction`
   - `correction_text: <first 500 chars of user reply>`
   - `prior_action: <what I just did that was corrected>`
2. Let memory-reflect update my soul's §6 Behavioral rules or §10 Blindspots.
3. Log `action: ceo_reflect_from_correction, delta: <reflect_output_summary>`.
4. If the correction touches a project-invariant (architecture / tooling / process pivot), also queue a `skill-derive` candidate for project-KB via `kiho-kb-manager`.

Resume the loop with the user's answer.
```

### WRITE: `plugins/kiho/references/preferred-subagents.md`
```markdown
# Preferred sub-agents for CEO (v5.22)

When the CEO reaches for `Agent(subagent_type: ...)`, prefer the specialized kiho agent over `general-purpose`:

| Intent | Preferred `subagent_type` | Anti-pattern |
|---|---|---|
| Research (facts, market data, SDK) | `kiho:kiho-researcher` | `general-purpose` with WebSearch — skips trusted-source registry |
| KB operations (search / add / update / lint) | `kiho:kiho-kb-manager` | Direct Write to `.kiho/kb/wiki/` |
| Recruiting a new agent | `recruit` skill → `kiho:kiho-recruiter` internal | Direct Write to `$COMPANY_ROOT/agents/` |
| Committee transcript extraction | `kiho:kiho-clerk` | CEO summarizes committee itself (bias risk) |
| Hiring auditor (with persona) | `kiho:kiho-auditor` (persona: skeptic / pragmatist / overlap_hunter / cost_hawk) | CEO gives single assessment |
| Cross-dept comms / help-wanted | `kiho:kiho-comms` | CEO manually fan-out |
| Capacity planning | `kiho:kiho-scheduler` | CEO over-books an agent |
| Quarterly review | `kiho:kiho-perf-reviewer` | CEO self-assesses |
| Generic multi-step exploration | `general-purpose` | (OK, but log `fallback: general_purpose, reason: <X>`) |

CEO reads this file at INITIALIZE step 5 (after catalog load). If the planned delegation matches an "Intent" row and the CEO is about to pick `general-purpose`, that's the anti-pattern — re-route.
```

### PATCH: `plugins/kiho/agents/kiho-ceo.md` — §INITIALIZE step 5

原 step 5 讀 CATALOG.md 載入 skill catalog。在其後追加：
```markdown
5b. **[REQUIRED v5.22]** Also read `${CLAUDE_PLUGIN_ROOT}/references/preferred-subagents.md` into context. When selecting `subagent_type` for any Agent call this turn, first check this table. Logging `fallback: general_purpose` is acceptable but MUST include `reason: <1-sentence>`.
```

---

## 驗收套件（建議放到 `_meta-runtime/tests/`）

### WRITE: `_meta-runtime/tests/session1-replay.md`
```markdown
# Replay test: session 1 (Web3 quant guide)

Input: /kiho research for how to do quant in web3 industry...
Expected under v5.22:
  - TIER declared normal
  - kb-search returns empty → log kb_empty_acknowledged
  - Agent(subagent_type='kiho:kiho-researcher', ...) used 5× (not general-purpose)
  - No direct Write to `.kiho/kb/wiki/*.md` — all via kiho-kb-manager
  - DONE step 11a runs ceo_behavior_audit.py and exits 0 (clean)
```

### WRITE: `_meta-runtime/tests/session5-replay.md`
```markdown
# Replay test: session 5 (hire 3 agents)

Input: /kiho "kiho is dev tool like vscode; recruit specialists"
Expected under v5.22:
  - CEO declares TIER: normal (or careful if user flag)
  - pre-write-agent hook fires when CEO tries direct Write to $COMPANY_ROOT/agents/
  - CEO forced to invoke `recruit` skill
  - recruit's pre-emit gate checks role-spec / interview-simulate artifacts
  - interview-simulate spawned 3× (1 per candidate) actually running the scenarios
  - After all 3 hires, capability-matrix + org-registry written by recruit's onboarding step (not by CEO directly)
  - ceo_behavior_audit.py exits 0; no drift
```
