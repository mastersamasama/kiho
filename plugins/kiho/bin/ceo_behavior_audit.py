#!/usr/bin/env python3
"""CEO behavior audit — reconcile ceo-ledger.jsonl claims against filesystem truth.

Written for kiho v5.22. Invoked at DONE step 11 (see `agents/kiho-ceo.md`). Reads
the project's `ceo-ledger.jsonl`, walks each entry claiming a delegation, KB op, or
recruit action, and verifies the claim is backed by real artifacts or tool calls.

Three drift severities:
  - CRITICAL: invariant violations — fabricated subagent targets, KB writes that
    bypassed kiho-kb-manager (detected via git blame when the project is a git
    repo), recruit actions missing role-spec or interview artifacts.
  - MAJOR:    narrative-style targets like "kiho-researcher-x5" (implies fanout
    that Claude Code never actually performs); delegates without a matching
    subagent_return entry.
  - MINOR:    unknown-but-plausible targets (might be typo or new agent not in
    the known list).

Exit codes:
  0 — clean
  1 — MINOR drift only
  2 — MAJOR drift present
  3 — CRITICAL drift present

Usage:
  python ceo_behavior_audit.py --ledger <path> --turn-from <iso_ts>
  python ceo_behavior_audit.py --ledger <path> --full    # entire history
  python ceo_behavior_audit.py --ledger <path> --json    # stdout JSON for CEO to parse

Ledger-epoch amnesty: ledger entries written before a `ledger_epoch: v5.22_active`
marker in the same file are skipped unless `--full` is passed. This prevents pre-
v5.22 drift from showing up on the first v5.22 turn, which would be noise rather
than signal.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SEVERITY_EXIT = {"clean": 0, "minor": 1, "major": 2, "critical": 3}

KNOWN_SUBAGENTS = {
    # kiho-namespaced specialized agents
    "kiho:kiho-researcher",
    "kiho:kiho-kb-manager",
    "kiho:kiho-recruiter",
    "kiho:kiho-clerk",
    "kiho:kiho-auditor",
    "kiho:kiho-hr-lead",
    "kiho:kiho-eng-lead",
    "kiho:kiho-pm-lead",
    "kiho:kiho-perf-reviewer",
    "kiho:kiho-comms",
    "kiho:kiho-scheduler",
    "kiho:kiho-spec",
    # Claude Code builtins / allowed fallbacks
    "general-purpose",
    "Explore",
    "Plan",
    "kiho-ceo",
    # Department leads and common IC names (pattern, checked below)
}

# Narrative-style fanout patterns — these are NOT real subagent types
FANOUT_RE = re.compile(r"-x\d+$|_x\d+$", re.IGNORECASE)
# Concatenated tool-list-as-target — indicates main-thread tool use disguised
FABRICATED_RE = re.compile(r"[+,]")


@dataclass
class Drift:
    seq: int | None
    severity: str
    check: str
    declared: str
    actual: str
    hint: str = ""


def iter_ledger(path: Path, turn_from: str | None, skip_pre_epoch: bool):
    """Yield ledger entries. If skip_pre_epoch, skip everything before the first
    entry with `action: ledger_epoch_marker` and `payload.epoch == v5.22_active`.
    """
    in_v5_22 = not skip_pre_epoch
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if skip_pre_epoch and not in_v5_22:
            action = entry.get("action", "")
            payload = entry.get("payload") or {}
            if action == "ledger_epoch_marker" and payload.get("epoch") == "v5.22_active":
                in_v5_22 = True
            continue
        if turn_from and entry.get("ts", "") < turn_from:
            continue
        yield entry


def check_delegate(entry: dict, drifts: list[Drift]) -> None:
    target = str(entry.get("target") or "").strip()
    if not target:
        return
    if target in KNOWN_SUBAGENTS:
        return
    # Narrative fanout like "kiho-researcher-x5" — the CEO described the intent
    # but Agent calls are always individual. Major drift.
    if FANOUT_RE.search(target):
        drifts.append(
            Drift(
                entry.get("seq"),
                "major",
                "delegate_target_narrative",
                target,
                "no such subagent_type (fanout suffix)",
                "Agent calls are individual; spawn N times or re-state as N delegates",
            )
        )
        return
    # Concatenated tools — this is main-thread tool use labeled as delegation
    if FABRICATED_RE.search(target):
        drifts.append(
            Drift(
                entry.get("seq"),
                "critical",
                "delegate_target_fabricated",
                target,
                "no such subagent_type (tool-list syntax); main-thread tool use disguised",
                "route through kiho:kiho-researcher or the matching specialized agent",
            )
        )
        return
    # Unknown plausible target — could be a typo or a new agent not yet registered
    drifts.append(
        Drift(
            entry.get("seq"),
            "minor",
            "delegate_target_unknown",
            target,
            "not in KNOWN_SUBAGENTS registry",
            "verify agent name or normalize to canonical form",
        )
    )


def _git_last_author(project_root: Path, wiki_path: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "log", "--pretty=format:%an", "-n", "1", "--", str(wiki_path)],
            cwd=str(project_root),
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def check_kb_add(entry: dict, project_root: Path, drifts: list[Drift]) -> None:
    payload = entry.get("payload") or {}
    entries = payload.get("entries") or payload.get("slugs") or []
    if isinstance(entries, str):
        entries = [entries]
    for slug in entries:
        if not slug:
            continue
        wiki_path = project_root / ".kiho" / "kb" / "wiki" / f"{slug}.md"
        if not wiki_path.exists():
            drifts.append(
                Drift(
                    entry.get("seq"),
                    "major",
                    "kb_add_missing_file",
                    str(slug),
                    f"{wiki_path} not found",
                )
            )
            continue
        # Look for the KB_MANAGER_CERTIFICATE marker written by kiho-kb-manager
        try:
            content = wiki_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "KB_MANAGER_CERTIFICATE:" in content:
            continue
        # Fallback heuristic: git blame. Only helpful in git repos; silent on
        # non-git projects per spec.
        last_author = _git_last_author(project_root, wiki_path)
        if last_author and "kb-manager" not in last_author.lower():
            drifts.append(
                Drift(
                    entry.get("seq"),
                    "critical",
                    "kb_add_not_via_manager",
                    str(slug),
                    f"last writer: {last_author}; no KB_MANAGER_CERTIFICATE in content",
                    "direct Write used instead of kiho-kb-manager",
                )
            )


def check_recruit(entry: dict, project_root: Path, drifts: list[Drift]) -> None:
    payload = entry.get("payload") or {}
    agents = payload.get("agents") or payload.get("hired") or []
    if isinstance(agents, str):
        agents = [agents]
    for aid in agents:
        if not aid:
            continue
        role_spec_a = project_root / ".kiho" / "state" / "recruit" / aid / "role-spec.md"
        role_spec_b = project_root / "_meta-runtime" / "role-specs" / aid / "role-spec.md"
        interview_a = project_root / ".kiho" / "runs" / "interview-simulate"
        interview_b = project_root / "_meta-runtime" / "interview-runs" / aid
        has_role_spec = role_spec_a.exists() or role_spec_b.exists()
        has_interview = False
        if interview_b.exists() and any(interview_b.glob("*.json*")):
            has_interview = True
        elif interview_a.exists() and any(
            p for p in interview_a.glob(f"*{aid}*.jsonl") if p.is_file()
        ):
            has_interview = True
        if not has_role_spec:
            drifts.append(
                Drift(
                    entry.get("seq"),
                    "critical",
                    "recruit_no_role_spec",
                    aid,
                    "role-spec.md absent in either recruit/ or _meta-runtime/role-specs/",
                    "recruit skipped role-spec planner — cannot emit agent.md per v5.22 pre-emit gate",
                )
            )
        if not has_interview:
            drifts.append(
                Drift(
                    entry.get("seq"),
                    "critical",
                    "recruit_no_interview",
                    aid,
                    "no interview-simulate transcript found",
                    "interview-simulate was not invoked — hire is ungated",
                )
            )


def check_okr_hook_to_checkin(entries: list[dict], drifts: list[Drift]) -> None:
    """v6.2.1+ (gap K). A cycle close with aligns_to_okr fired the okr-checkin
    hook → there MUST be a matching `okr_auto_checkin_from_cycle` (or
    `okr_checkin` manual) ledger entry within the same turn window. Missing
    entry = hook was deferred to CEO but CEO never dispatched (gap H
    symptom if it ever regresses).
    """
    by_cycle: dict[str, dict] = {}
    for entry in entries:
        action = entry.get("action", "")
        payload = entry.get("payload") or {}
        if action in {"cycle_close_success", "cycle_closed_success"}:
            cycle_id = payload.get("cycle_id")
            if cycle_id and payload.get("aligns_to_okr"):
                by_cycle.setdefault(cycle_id, {"closed_with_okr": True, "checked_in": False,
                                                "aligns_to_okr": payload["aligns_to_okr"]})
        elif action in {"okr_auto_checkin_from_cycle", "okr_checkin"}:
            cycle_id = payload.get("cycle_id")
            if cycle_id and cycle_id in by_cycle:
                by_cycle[cycle_id]["checked_in"] = True
    for cycle_id, state in by_cycle.items():
        if state["closed_with_okr"] and not state["checked_in"]:
            drifts.append(
                Drift(
                    seq=None,
                    severity="major",
                    check="okr_hook_without_checkin",
                    declared=f"cycle {cycle_id} aligns_to_okr={state['aligns_to_okr']}",
                    actual="no okr_auto_checkin_from_cycle entry — hook fired but CEO did not dispatch",
                    hint="verify cycle_runner HOOK_VERBS includes okr-checkin and CEO INTEGRATE step dispatches the verb",
                )
            )


def check_committee_to_okr_set(entries: list[dict], drifts: list[Drift]) -> None:
    """v6.2.1+ (gap K). Committee close with topic containing 'OKR' + unanimous
    outcome MUST be followed (within ~20 entries) by either
    `committee_requests_okr_set` (clerk emitted the request) and then
    `okr_set` (CEO dispatched) — OR an explicit `okr_set_request_skipped`
    ledger entry. Missing both = gap D symptom.
    """
    pending_committee_closes: list[dict] = []
    for idx, entry in enumerate(entries):
        action = entry.get("action", "")
        payload = entry.get("payload") or {}
        if action == "committee_closed":
            topic = str(payload.get("topic", "")).lower()
            outcome = str(payload.get("outcome", "")).lower()
            if outcome == "unanimous" and any(k in topic for k in ("okr", "objective")):
                pending_committee_closes.append({
                    "seq": entry.get("seq") or idx,
                    "committee_id": payload.get("committee_id", ""),
                    "topic": topic,
                    "resolved": False,
                })
        elif action in {"committee_requests_okr_set", "okr_set_request_skipped", "okr_set"}:
            # Mark the most recent pending close as resolved (LIFO within window)
            for p in reversed(pending_committee_closes):
                if not p["resolved"]:
                    p["resolved"] = True
                    break
    for p in pending_committee_closes:
        if not p["resolved"]:
            drifts.append(
                Drift(
                    seq=p["seq"],
                    severity="major",
                    check="okr_committee_without_okr_set",
                    declared=f"committee {p['committee_id']} (topic: OKR) closed unanimous",
                    actual="no committee_requests_okr_set OR okr_set OR okr_set_request_skipped in ledger",
                    hint="committee SKILL.md §clerk step 6 (v6.2.1+) should emit the request — check it ran",
                )
            )


def check_okr_state(entries: list[dict], project_root: Path, drifts: list[Drift]) -> None:
    """Detect OKR state drift (v6.2+).

    Two drift classes:
      - okr_stale_o — active O with no checkin/close > [okr] stale_days
      - okr_period_overrun — active O in a period that ended > 7 days ago
                             without a period-close ledger entry in this turn

    Lazy import of okr_scanner — audit stays runnable even without scanner.
    Introduced by v6.2 OKR auto-flow.
    """
    try:
        here = Path(__file__).resolve().parent
        if str(here) not in sys.path:
            sys.path.insert(0, str(here))
        import okr_scanner  # type: ignore
    except Exception:
        return  # scanner unavailable; silent no-op

    try:
        actions = okr_scanner.scan(project_root)
    except Exception:
        return

    # Collected period-close and cascade-close ledger entries in this audit window
    closed_periods_in_window = {
        (e.get("payload") or {}).get("period")
        for e in entries
        if e.get("action") in {"okr_period_auto_close_complete", "okr_period_auto_close"}
    }

    for action in actions:
        if action.kind == "stale-memo":
            drifts.append(
                Drift(
                    seq=None,
                    severity="minor",
                    check="okr_stale_o",
                    declared=action.payload.get("o_id", ""),
                    actual=f"{action.payload.get('days_since_checkin', '?')} days without checkin",
                    hint="owner should okr-checkin, or CEO should memo owner",
                )
            )
        elif action.kind == "period-close":
            period = action.payload.get("period", "")
            if period in closed_periods_in_window:
                continue  # already handled in this turn
            drifts.append(
                Drift(
                    seq=None,
                    severity="major",
                    check="okr_period_overrun",
                    declared=action.payload.get("o_id", ""),
                    actual=f"period {period} ended; no okr-close-period invocation in ledger",
                    hint="OKR-master should be invoked with close-period for this period",
                )
            )


def check_approval_chains(entries: list[dict], drifts: list[Drift]) -> None:
    """Verify approval_chain_closed:granted entries have all stages logged.

    A chain is declared complete by an `approval_chain_closed` ledger entry
    with `outcome: granted`. Every stage of the chain (per
    `references/approval-chains.toml`) MUST have a corresponding
    `approval_stage_granted` entry in the same ledger window before the
    close entry. Missing stages = skipped stages = approval_chain_skipped
    drift (CRITICAL).

    Introduced by decision: approval-chains-2026-04-23 (v5.23).
    Lazy import of approval_chain module — audit stays runnable even if
    the registry is unavailable (degrades to no-op on this check).
    """
    try:
        here = Path(__file__).resolve().parent
        if str(here) not in sys.path:
            sys.path.insert(0, str(here))
        import approval_chain  # type: ignore
    except Exception:
        return  # registry unavailable; silent no-op for this check

    for entry in entries:
        if entry.get("action") != "approval_chain_closed":
            continue
        payload = entry.get("payload") or {}
        if payload.get("outcome") != "granted":
            continue
        chain_id = payload.get("chain_id")
        if not chain_id:
            continue
        # Only consider stage_granted entries that appear BEFORE this close.
        close_seq = entry.get("seq")
        prior = [
            e
            for e in entries
            if (close_seq is None or (e.get("seq") or -1) < close_seq)
        ]
        ok, missing = approval_chain.verify_ran(chain_id, prior)
        if not ok and missing:
            drifts.append(
                Drift(
                    entry.get("seq"),
                    "critical",
                    "approval_chain_skipped",
                    chain_id,
                    f"missing stage_granted entries: {missing}",
                    "chain closed but some stages never logged; forged certificate or skipped stage",
                )
            )


def check_kb_integrate_or_classify_skipped(entries: list[dict], drifts: list[Drift]) -> None:
    """[v6.3 — L-KB-MID-LOOP-MANDATORY enforcement; v6.4 extended]

    Every iteration's confidence ≥0.90 decision MUST trigger ONE of:
      - kb_add (Lane B — durable project knowledge)
      - state_decision (Lane A — turn-scoped artefact, v6.4+)
      - memory_write (Lane C — cross-project reusable lesson, v6.4+)
      - kb_deferred (explicit defer with reason)

    Silent skip across ALL FOUR is drift.

    Audit logic:
      - Find every `subagent_return` entry with payload.confidence >= 0.90
        AND payload.status in {ok, complete}
      - For each, verify a subsequent capture entry of any accepted kind
        exists within the same turn (between this entry and the next
        `done`/`tier_declared`)
      - Missing match = MAJOR drift `kb_integrate_or_classify_skipped`
        (v6.3 callers used `kb_integrate_skipped`; v6.4 unified the code)
    """
    high_conf_returns = []
    turn_boundaries = [0]  # seqs where new turn started
    for i, e in enumerate(entries):
        action = e.get("action") or ""
        if action in ("tier_declared", "initialize", "done"):
            turn_boundaries.append(i)
        if action == "subagent_return":
            payload = e.get("payload") or {}
            conf = payload.get("confidence")
            status = payload.get("status") or ""
            if conf is not None and conf >= 0.90 and status in ("ok", "complete"):
                high_conf_returns.append((i, e))

    accepted_actions = {
        "kb_add",
        "kb_add_batch",
        "kb_deferred",
        "state_decision",  # v6.4 Lane A
        "memory_write",    # v6.4 Lane C
    }

    for idx, return_entry in high_conf_returns:
        # Find the next turn boundary AFTER this return
        next_boundary = next(
            (b for b in turn_boundaries if b > idx), len(entries)
        )
        # Look for any accepted capture action between idx+1 and next_boundary
        window = entries[idx + 1 : next_boundary]
        has_capture = any(
            (e.get("action") or "") in accepted_actions for e in window
        )
        if not has_capture:
            drifts.append(
                Drift(
                    return_entry.get("seq"),
                    "major",
                    "kb_integrate_or_classify_skipped",
                    return_entry.get("target") or "<unknown>",
                    f"high-confidence return ({return_entry.get('payload', {}).get('confidence')}) without subsequent kb_add / state_decision / memory_write / kb_deferred entry",
                    "v6.4 content-routing classifier: every confidence ≥0.90 decision MUST trigger one of {kb_add (Lane B), state_decision (Lane A), memory_write (Lane C), kb_deferred (explicit ambiguous)}",
                )
            )


# Backwards-compat alias for any external callers pinned to the v6.3 name.
check_kb_integrate_discipline = check_kb_integrate_or_classify_skipped


def check_kb_classification_drift(kb_root: Path, drifts: list[Drift], turn_from: str | None = None) -> None:
    """[v6.4 — content-routing classifier counter-check]

    Walk `<kb_root>/decisions/*.md` for entries whose body is state-shaped
    (Lane A heuristics) but landed in KB anyway. State-ness score is a
    weighted sum of 4 heuristic checks; score ≥0.50 = MAJOR drift.

    Heuristics (from agents/kiho-ceo.md §INTEGRATE Lane A):
      +0.30  body cites evidence_paths / source_seq / specific file:line
             as load-bearing (e.g. "src/.../X.tsx:343" or "seq 264")
      +0.25  title contains feature/spec slug pattern (D-FU-* / D-BB-* /
             D-s-* / similar) without a generalising verb
      +0.25  rationale section is >70% commit / screenshot / curl
             citations rather than reusable principle
      +0.20  zero outbound wikilinks (orphan in KB graph)
    """
    if not kb_root.exists():
        return
    decisions_dir = kb_root / "decisions"
    if not decisions_dir.exists():
        return

    import re

    # Compile detection regexes once
    file_line_pattern = re.compile(r"\b[\w./\-]+\.\w+:\d+\b")
    seq_pattern = re.compile(r"\b(?:source_seq|seq)\s*[:=]?\s*\d+", re.IGNORECASE)
    screenshot_pattern = re.compile(r"\.(?:png|jpg|jpeg)\b", re.IGNORECASE)
    feature_slug_pattern = re.compile(r"\b(?:D|CV|C|L)?-?(?:BB|FU|s)-[A-Z0-9-]+\b")
    generalising_verbs = re.compile(r"\b(?:Use|Prefer|Always|Never|MUST|SHOULD|Avoid)\b", re.IGNORECASE)
    wikilink_pattern = re.compile(r"\[\[[^\]]+\]\]")

    for entry in sorted(decisions_dir.glob("*.md")):
        try:
            text = entry.read_text(encoding="utf-8")
        except Exception:
            continue

        # Parse frontmatter `date:` for --turn-from filter (grandfather pre-v6.4)
        if turn_from:
            date_match = re.search(r"^date:\s*([\d\-T:Z]+)", text, re.MULTILINE)
            if date_match and date_match.group(1) < turn_from:
                continue  # legacy entry — grandfathered

        # Score
        score = 0.0
        body = text[:6000]  # first 50ish lines

        # +0.30 evidence_paths cited
        if (
            file_line_pattern.search(body)
            or seq_pattern.search(body)
            or screenshot_pattern.search(body)
        ):
            score += 0.30

        # +0.25 feature/spec slug in title without generalising verb
        title_match = re.search(r"^title:\s*[\"']?(.+?)[\"']?$", text, re.MULTILINE)
        title = title_match.group(1) if title_match else entry.stem
        slug_in_title = bool(feature_slug_pattern.search(entry.stem) or feature_slug_pattern.search(title))
        verb_in_title = bool(generalising_verbs.search(title))
        if slug_in_title and not verb_in_title:
            score += 0.25

        # +0.25 rationale section is mostly citations
        # Heuristic: if Verification / Sources / Screenshot blocks dominate body
        rationale_section = re.search(
            r"##\s*(?:Rationale|Verification)(.*?)(?=\n##\s|\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if rationale_section:
            r_text = rationale_section.group(1)
            citation_chars = sum(
                len(m.group(0)) for m in file_line_pattern.finditer(r_text)
            ) + sum(
                len(m.group(0)) for m in screenshot_pattern.finditer(r_text)
            )
            if r_text and citation_chars / max(len(r_text), 1) > 0.07:
                score += 0.25

        # +0.20 zero outbound wikilinks
        if not wikilink_pattern.search(body):
            score += 0.20

        if score >= 0.50:
            drifts.append(
                Drift(
                    None,
                    "major",
                    "kb_state_artefact",
                    entry.stem,
                    f"KB entry {entry.stem} scores state-ness {score:.2f} (≥0.50 threshold) — likely belongs in state_decision ledger, not KB",
                    f"v6.4 classifier: title={title!r}, slug_match={slug_in_title}, has_verb={verb_in_title}",
                )
            )


def check_orphan_state_lessons(state_root: Path, drifts: list[Drift]) -> None:
    """[v6.4] Lessons should live in agents/<name>/memory/lessons.md or
    Claude Code's per-project memory, not in `.kiho/state/`. Detect
    leaked `*-lesson*.md` / `lessons-*.md` files in state.
    """
    if not state_root.exists():
        return
    candidates = list(state_root.rglob("*-lesson*.md")) + list(
        state_root.rglob("lessons-*.md")
    )
    for f in candidates:
        # Skip the audit dir (legitimate to host lesson archives)
        if "audit" in f.parts:
            continue
        drifts.append(
            Drift(
                None,
                "minor",
                "lesson_in_state_should_be_memory",
                str(f.relative_to(state_root)),
                f"lesson-shaped file {f.name} in state/ — route to agents/<name>/memory/lessons.md or ~/.claude/projects/<cwd>/memory/feedback_*.md",
                "v6.4 content-routing classifier Lane C",
            )
        )


SOFT_STOP_RE = re.compile(
    r"(要我繼續嗎|要我立刻|要不要我|要我接著|繼續嗎|"
    r"shall I proceed|want me to|should I (?:continue|start)|continue\?)",
    re.IGNORECASE,
)

# v6.5.2 — Signal 3: structural soft-stop wrapped inside a `next_action` field.
# The CEO learned to bypass v6.5.1's narration regex by emitting:
#   {"status": "complete", "next_action": "下個 /kiho 接 plan §5 Turn 2"}
# This regex matches re-invoke / future-/kiho / wait-for-user patterns that are
# structurally identical to soft-stop but live inside JSON.
NEXT_ACTION_SOFT_STOP_RE = re.compile(
    r"(下個\s*/kiho|下一個\s*/kiho|下次\s*/kiho|next\s+/kiho|re-invoke|"
    r"user\s+(?:reviews|re-invokes|will\s+invoke|should\s+invoke)|"
    r"待\s*user\s*(?:確認|觸發|呼叫)|"
    r"等\s*(?:user|您)\s*(?:re-invoke|觸發|啟動)|"
    r"please\s+(?:run|invoke|trigger)|"
    r"接[\s下]+/kiho)",
    re.IGNORECASE,
)


def _scan_plan_pending(plan_md_path: Path) -> tuple[int, bool]:
    """Scan plan.md once and return (pending_count, found).

    found = False if the file is missing/unreadable (caller treats as
    "unknown" — do not escalate Signal 3 to CRITICAL). Otherwise found=True
    and pending_count is the number of substantive Pending items (table rows
    or bullets, excluding markdown separators and boilerplate "id" header rows).

    Recognises ## Pending / ### Pending headers, plus ## In progress because
    CEO sometimes parks future-turn items there. Counter resets when the next
    ##/### header arrives.
    """
    if not plan_md_path.exists():
        return (0, False)
    try:
        text = plan_md_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return (0, False)
    pending_lines: list[str] = []
    in_pending = False
    for line in text.splitlines():
        stripped = line.strip()
        if (
            stripped.startswith("## Pending")
            or stripped.startswith("### Pending")
            or ("Pending" in line and line.startswith(("##", "###")))
        ):
            in_pending = True
            continue
        if in_pending and line.startswith(("# ", "## ", "### ")):
            in_pending = False
            continue
        if in_pending and stripped.startswith(("|", "-", "*")) and not stripped.startswith("---"):
            content = stripped.lstrip("|-* ").strip()
            if content and not content.startswith("(") and "id" not in content[:5].lower():
                pending_lines.append(content)
    return (len(pending_lines), True)


def check_soft_stop_drift(entries: list[dict], project_root: Path, drifts: list[Drift]) -> None:
    """[v6.5.1 — strict Ralph loop invariant; v6.5.2 — Signal 3 next_action]

    Detect soft-stop drift: the CEO ended a turn without `AskUserQuestion` AND
    without `status: complete` AND `plan.md` Pending was non-empty. Mid-loop
    "do you want me to continue?" prompts violate the Ralph loop contract — the
    user authorised a multi-iteration scope at ExitPlanMode time, so re-asking
    for permission on each iteration places the burden on the user to re-trigger
    the CEO.

    Audit logic (three complementary signals — any match → flag drift):

    Signal 1: structural — for each `action: done` (or `turn_summary`) entry,
      walk back to the prior `tier_declared` / `initialize` boundary; if no
      `ask_user` action appears in the window AND `payload.status != "complete"`
      AND `plan.md` currently has non-empty Pending items, flag drift.

    Signal 2: textual — search any `action: turn_summary` payload `summary`
      field (or `done` payload `narration` / `reason`) for the SOFT_STOP_RE
      regex (Chinese 「要我繼續嗎」/「要我立刻」/「要不要我」/「要我接著」/
      「繼續嗎」 + English "shall I proceed" / "want me to" / "should I
      continue|start" / "continue?"). Any match → flag drift even if
      structural signal didn't fire (the regex is the fallback when plan.md
      reconstruction is unreliable).

    Signal 3 (v6.5.2): structured `next_action` soft-stop — search the
      `next_action` field of `done` / `turn_summary` payloads for
      NEXT_ACTION_SOFT_STOP_RE (「下個 /kiho」/「next /kiho」/「re-invoke」/
      「待 user 確認」/「等 user 觸發」/「please run」/「接 下 /kiho」). MAJOR
      drift on bare match (`next_action_soft_stop`); CRITICAL when plan.md
      Pending is also non-empty (`plan_pending_with_soft_stop_next_action` —
      the loop should have iterated, not handed off to a future invocation).
    """
    plan_path = project_root / ".kiho" / "state" / "plan.md"
    pending_count, plan_found = _scan_plan_pending(plan_path)
    # Signal 3 fires CRITICAL when plan.md exists AND has any pending item.
    # Signal 1 keeps v6.5.1's stricter ">3" threshold to ignore boilerplate
    # header rows that may slip through the filter on edge-case formats.
    pending_present_for_signal3 = plan_found and pending_count > 0
    pending_nonempty = pending_count > 3

    # Walk DONE / turn_summary entries
    for i, entry in enumerate(entries):
        action = entry.get("action") or ""
        if action not in ("done", "turn_summary"):
            continue

        payload = entry.get("payload") or {}

        # Signal 3 (v6.5.2) — structured next_action soft-stop.
        # Inspect next_action FIRST so it gets its own dedicated drift check
        # name (`next_action_soft_stop` / `plan_pending_with_soft_stop_next_action`)
        # rather than being subsumed by Signal 2's generic `soft_stop_drift`.
        flagged_signal3 = False
        next_action_val = payload.get("next_action")
        if isinstance(next_action_val, str) and next_action_val:
            na_match = NEXT_ACTION_SOFT_STOP_RE.search(next_action_val)
            if na_match is not None:
                # 5-line context around the matched span for the drift message
                start = max(0, na_match.start() - 80)
                end = min(len(next_action_val), na_match.end() + 80)
                context = next_action_val[start:end].replace("\n", " ⏎ ")
                if pending_present_for_signal3:
                    drifts.append(
                        Drift(
                            entry.get("seq"),
                            "critical",
                            "plan_pending_with_soft_stop_next_action",
                            "ceo",
                            (
                                f"next_action soft-stop {na_match.group(0)!r} emitted "
                                f"WHILE plan.md Pending non-empty — loop should have "
                                f"continued iterating or hit max_iterations checkpoint. "
                                f"Context: …{context}…"
                            ),
                            "v6.5.2: structured soft-stop wrapped in next_action JSON field is the SAME drift as natural-language 「要我繼續嗎」 — Ralph LOOP must NOT defer to a future /kiho invocation while Pending non-empty",
                        )
                    )
                else:
                    drifts.append(
                        Drift(
                            entry.get("seq"),
                            "major",
                            "next_action_soft_stop",
                            "ceo",
                            (
                                f"next_action contains re-invoke / future-/kiho pattern "
                                f"{na_match.group(0)!r}. Context: …{context}…"
                            ),
                            "v6.5.2: next_action MUST describe a within-loop next step (e.g., 'spawn implementer for T7'), NEVER a meta-instruction telling the user to re-invoke /kiho",
                        )
                    )
                flagged_signal3 = True

        # Signal 2 — textual regex match against turn_summary / done narration.
        text_blobs: list[str] = []
        for field_name in ("summary", "narration", "reason", "next_action", "turn_outcome"):
            v = payload.get(field_name)
            if isinstance(v, str):
                text_blobs.append(v)
        # Also fall through to top-level "reason" (some legacy entries flatten it)
        top_reason = entry.get("reason")
        if isinstance(top_reason, str):
            text_blobs.append(top_reason)
        joined = "\n".join(text_blobs)
        match = SOFT_STOP_RE.search(joined) if joined else None
        if match is not None and not flagged_signal3:
            drifts.append(
                Drift(
                    entry.get("seq"),
                    "major",
                    "soft_stop_drift",
                    "ceo",
                    f"turn-end narration contains soft-stop prompt: {match.group(0)!r}",
                    "v6.5.1: CEO MUST iterate, AskUserQuestion, or status:complete — never linger asking for permission",
                )
            )
            continue  # don't double-flag the same entry from signal 1

        if flagged_signal3:
            # Signal 3 already flagged this entry; skip Signal 1 to avoid
            # double-counting the same drift.
            continue

        # Signal 1 — structural. Only fires when plan.md Pending is non-empty.
        if not pending_nonempty:
            continue
        status = payload.get("status") or ""
        if status == "complete":
            continue
        # Walk back to last tier_declared / initialize for turn start
        turn_start = 0
        for j in range(i - 1, -1, -1):
            a = entries[j].get("action") or ""
            if a in ("tier_declared", "initialize"):
                turn_start = j
                break
        window = entries[turn_start : i + 1]
        has_ask_user = any(
            (w.get("action") or "") == "ask_user" for w in window
        )
        if has_ask_user:
            continue
        drifts.append(
            Drift(
                entry.get("seq"),
                "major",
                "soft_stop_drift",
                "ceo",
                f"action: {action} with non-empty plan.md Pending, no ask_user in turn, status != complete",
                "v6.5.1: turn ended without AskUserQuestion AND without status:complete while plan still has pending work — Ralph loop must continue iterating",
            )
        )


# v6.6.3 — Signal 4: structural INTEGRATE skip in audit MDs.
# CEO drafts "Lane B (KB) candidate" / "high confidence ≥ 0.90" / "promote to KB"
# in `.kiho/audit/**/*.md` but never spawns kiho-kb-manager in the same turn.
# This is the structural twin of soft-stop: listing intent without acting.
INTEGRATE_CANDIDATE_RE = re.compile(
    r"(Lane B \(KB\) candidate|Lane B candidate|"
    r"promote to KB|kb candidate|knowledge candidate|"
    r"high confidence(?:\s*[≥>=]+\s*0?\.9\d?)?|"
    r"confidence:\s*0?\.9[0-9]|"
    r"will be promoted|"
    r"待\s*evolve\s*固化|"
    r"下次\s*evolve|"
    r"待 KB)",
    re.IGNORECASE,
)

# Marker the CEO can write next to a candidate to signal it has already been
# integrated in a prior turn ("[INTEGRATED commit ABCD]"). When present on the
# same line, that line is excluded from the candidate count.
INTEGRATED_MARKER_RE = re.compile(r"\[INTEGRATED\b[^\]]*\]", re.IGNORECASE)

# Ledger actions that count as evidence the CEO actually spawned kb-manager
# (or routed knowledge through an equivalent mechanism) in the same turn.
KB_INTEGRATE_ACTIONS = {
    "kb_add",
    "kb_added",
    "kb_add_called",
    "kb_add_batch",
    "kbm_called",
    "kb_manager_spawn",
    "kb-manager-spawn",
    "knowledge_update_routed",
}

# Free-form payload / target tokens that also count as kb-manager spawn evidence.
KB_INTEGRATE_TOKENS = (
    "kb_add",
    "kb_added",
    "kb_add_called",
    "kb-manager-spawn",
    "kbm_called",
    "knowledge_update_routed",
    "kiho-kb-manager",
    "kiho:kiho-kb-manager",
)


def _turn_window_start(entries: list[dict]) -> str | None:
    """Pick the timestamp of the most recent turn boundary, or None if no
    boundary entries exist. Used to filter audit MD mtimes — files older than
    the boundary were authored in a prior turn and should not be re-flagged.
    """
    for entry in reversed(entries):
        action = entry.get("action") or ""
        if action in ("tier_declared", "initialize"):
            ts = entry.get("ts")
            if isinstance(ts, str) and ts:
                return ts
            return None
    return None


def _ledger_has_kb_integrate(entries: list[dict]) -> bool:
    """True if any entry in the window evidences a kb-manager spawn or KB
    capture call. Looks at action names AND payload/target tokens because
    different code paths log it differently across kiho versions.
    """
    for entry in entries:
        action = entry.get("action") or ""
        if action in KB_INTEGRATE_ACTIONS:
            return True
        target = str(entry.get("target") or "")
        if target and any(tok in target for tok in KB_INTEGRATE_TOKENS):
            return True
        payload = entry.get("payload") or {}
        try:
            payload_str = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError):
            payload_str = str(payload)
        if any(tok in payload_str for tok in KB_INTEGRATE_TOKENS):
            return True
    return False


def check_integrate_drift(entries: list[dict], project_root: Path, drifts: list[Drift]) -> None:
    """[v6.6.3 — INTEGRATE skip in audit/state markdown]

    The structural twin of soft-stop drift. v6.4 INTEGRATE rule says decisions
    with confidence ≥ 0.90 must route through kiho-kb-manager via kb-add
    mid-loop. CEO had been drafting "Lane B (KB) candidate" lists in audit
    MDs without ever spawning kb-manager.

    Audit logic:
      - Glob `<project_root>/.kiho/audit/**/*.md` (and `state/**/*.md` as a
        secondary surface, since some sessions park candidates there).
      - For each MD modified after the current turn boundary (or all MDs if
        the boundary is unknown — fail-loud rather than silently skip),
        scan body for INTEGRATE_CANDIDATE_RE matches. Skip lines that carry
        an `[INTEGRATED commit ABCD]` marker (already done, just remembered).
      - If 0 ledger entries evidence a kb-manager spawn / kb_add_called →
        every match is MAJOR drift `integrate_skipped`. CRITICAL severity
        when ≥ 3 candidates skipped in same turn (systemic drift).

    Edge cases:
      - No audit MDs (fresh project) → no drift possible, silent skip.
      - No ledger window (caller passed empty list) → cannot evaluate;
        log structured warning via stderr-free no-op (Drift list unchanged).
      - MD older than turn boundary → already integrated previously, skip.
    """
    audit_root = project_root / ".kiho" / "audit"
    if not audit_root.exists():
        return  # fresh project — no drift surface
    if not entries:
        return  # cannot evaluate without ledger context

    turn_start_ts = _turn_window_start(entries)
    # Fall back to file mtime relative to the earliest entry timestamp in window
    # (best-effort) when no explicit turn boundary is found.
    fallback_ts = None
    if turn_start_ts is None:
        for entry in entries:
            ts = entry.get("ts")
            if isinstance(ts, str) and ts:
                fallback_ts = ts
                break

    md_files = sorted(audit_root.rglob("*.md"))
    if not md_files:
        return

    # Cheap ledger-side check once; if kb-manager was spawned this turn,
    # every candidate is automatically resolved (no per-file iteration needed).
    has_integrate = _ledger_has_kb_integrate(entries)

    candidate_hits: list[tuple[Path, str, str]] = []
    for md in md_files:
        # Filter out files authored in a prior turn — already integrated then or
        # never expected to fire here. Use mtime as a cheap proxy for "touched
        # this turn." Compare ISO timestamps lexicographically (UTC ISO sorts
        # correctly as strings).
        try:
            mtime_iso = (
                __import__("datetime")
                .datetime.utcfromtimestamp(md.stat().st_mtime)
                .strftime("%Y-%m-%dT%H:%M:%SZ")
            )
        except OSError:
            continue
        threshold = turn_start_ts or fallback_ts
        if threshold and mtime_iso < threshold:
            continue

        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            m = INTEGRATE_CANDIDATE_RE.search(line)
            if m is None:
                continue
            # Skip lines explicitly marked as already integrated — the CEO is
            # just remembering past work, not declaring new candidates.
            if INTEGRATED_MARKER_RE.search(line):
                continue
            # 5-line context (2 above + match + 2 below) for the drift message
            ctx_start = max(0, i - 2)
            ctx_end = min(len(lines), i + 3)
            context = "\n".join(lines[ctx_start:ctx_end])
            try:
                rel = md.relative_to(project_root)
            except ValueError:
                rel = md
            candidate_hits.append((md, m.group(0), f"{rel}:{i + 1}\n{context}"))

    if not candidate_hits:
        return  # nothing drafted this turn

    if has_integrate:
        return  # CEO did spawn kb-manager — candidates are being processed

    # Severity: MAJOR per match, escalates to CRITICAL when ≥ 3 candidates skipped
    # in same turn (systemic drift, matches v6.5.2 plan-pending CRITICAL pattern).
    severity = "critical" if len(candidate_hits) >= 3 else "major"
    for md_path, matched, ctx in candidate_hits:
        try:
            rel = md_path.relative_to(project_root)
        except ValueError:
            rel = md_path
        drifts.append(
            Drift(
                seq=None,
                severity=severity,
                check="integrate_skipped",
                declared=str(rel),
                actual=(
                    f"audit MD lists KB candidate {matched!r} but turn ledger has "
                    f"zero kb_add_called / kb-manager-spawn entries. Context:\n{ctx}"
                ),
                hint=(
                    "v6.6.3: drafting a Lane B candidate IS the INTEGRATE step's "
                    "trigger — same turn must spawn kiho-kb-manager (op=add) or "
                    "log action: kb_deferred with reason. If session is ending "
                    "without kb-add, switch to status: max_iterations Route D "
                    "checkpoint instead of status: complete."
                ),
            )
        )


def check_ralph_anti_stop(entries: list[dict], project_root: Path, drifts: list[Drift]) -> None:
    """[v6.3 — L-RALPH-PENDING-NONEMPTY enforcement]

    The Ralph LOOP MUST NOT exit DONE while plan.md Pending list is non-empty,
    UNLESS one of:
      (i) AskUserQuestion fired (`action: ask_user` in same turn)
      (ii) max_ralph_iterations exceeded (`action: max_iterations_hit` or
           `action: checkpoint_via_route_d`)
      (iii) Budget exceeded (`action: budget_exceeded`)
      (iv) All Pending Blocked (`action: all_pending_blocked` + ASK_USER)

    Audit logic:
      - For each `action: done` entry in this turn, check if plan.md
        currently has non-empty Pending section
      - If Pending non-empty AND no escalation entry in same turn = MAJOR drift
        `ralph_stopped_early`
    """
    plan_path = project_root / ".kiho" / "state" / "plan.md"
    if not plan_path.exists():
        return  # fresh project; no plan yet — not drift

    # Naive Pending detection: count items under "## Pending" headers
    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except Exception:
        return

    # Find all Pending sections (skip those marked done/empty)
    pending_lines = []
    in_pending = False
    for line in plan_text.splitlines():
        if line.strip().startswith("## Pending") or line.strip().startswith("### Pending") or "Pending" in line and line.startswith(("##", "###")):
            in_pending = True
            continue
        if in_pending and line.startswith(("# ", "## ", "### ")):
            in_pending = False
            continue
        if in_pending and line.strip().startswith(("|", "-", "*")) and not line.strip().startswith("---"):
            # Filter out table separator + comment lines
            content = line.strip().lstrip("|-* ").strip()
            if content and not content.startswith("(") and "id" not in content[:5].lower():
                pending_lines.append(content)

    pending_nonempty = len(pending_lines) > 3  # threshold: ignore boilerplate header rows

    if not pending_nonempty:
        return  # plan empty or near-empty — no drift

    # Find done entries
    for i, e in enumerate(entries):
        if (e.get("action") or "") != "done":
            continue
        # Walk back to last tier_declared / initialize for turn start
        turn_start = 0
        for j in range(i - 1, -1, -1):
            a = entries[j].get("action") or ""
            if a in ("tier_declared", "initialize"):
                turn_start = j
                break
        window = entries[turn_start : i + 1]
        # Check for legitimate escalation
        escalation_actions = {
            "ask_user",
            "max_iterations_hit",
            "checkpoint_via_route_d",
            "budget_exceeded",
            "all_pending_blocked",
        }
        has_escalation = any(
            (w.get("action") or "") in escalation_actions for w in window
        )
        if not has_escalation:
            drifts.append(
                Drift(
                    e.get("seq"),
                    "major",
                    "ralph_stopped_early",
                    "ceo",
                    f"action: done with non-empty plan.md Pending ({len(pending_lines)} items) and no escalation entry in turn",
                    "v6.3 L-RALPH-PENDING-NONEMPTY: Ralph LOOP must continue iterating while Pending non-empty unless legitimate escalation (ask_user / max_iterations / budget_exceeded / all_pending_blocked)",
                )
            )


def summarize(drifts: list[Drift]) -> dict:
    by_sev: dict[str, list[Drift]] = {"critical": [], "major": [], "minor": []}
    for d in drifts:
        by_sev.setdefault(d.severity, []).append(d)
    severity = (
        "critical"
        if by_sev["critical"]
        else "major"
        if by_sev["major"]
        else "minor"
        if by_sev["minor"]
        else "clean"
    )
    return {
        "status": severity,
        "counts": {k: len(v) for k, v in by_sev.items()},
        "drifts": [d.__dict__ for d in drifts[:20]],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="kiho v6.4 CEO behavior audit")
    ap.add_argument("--ledger", required=True, type=Path, help="path to ceo-ledger.jsonl")
    ap.add_argument(
        "--kb-root",
        default=None,
        type=Path,
        help="path to .kiho/kb/wiki/ (enables v6.4 classification-drift check)",
    )
    ap.add_argument("--turn-from", default=None, help="ISO timestamp to filter from")
    ap.add_argument("--full", action="store_true", help="audit entire history incl. pre-v5.22")
    ap.add_argument("--json", action="store_true", help="emit JSON summary to stdout")
    args = ap.parse_args()

    ledger: Path = args.ledger
    if not ledger.exists():
        # No ledger is itself not an error — the first turn of a fresh project.
        summary = {"status": "clean", "counts": {"critical": 0, "major": 0, "minor": 0}, "drifts": [], "note": "ledger absent"}
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print("Status: CLEAN (ledger absent — fresh project)")
        return SEVERITY_EXIT["clean"]

    # Infer project root from ledger path. Standard layout is
    # <project>/.kiho/state/ceo-ledger.jsonl → parents[2] is <project>.
    try:
        project_root = ledger.resolve().parents[2]
    except IndexError:
        project_root = ledger.resolve().parent

    drifts: list[Drift] = []
    # First pass: per-entry checks. Collect entries for the second-pass
    # cross-entry check (approval-chain verification).
    collected: list[dict] = []
    for entry in iter_ledger(ledger, args.turn_from, skip_pre_epoch=not args.full):
        collected.append(entry)
        action = entry.get("action", "")
        if action == "delegate":
            check_delegate(entry, drifts)
        elif action in {"kb_add", "kb_update"}:
            check_kb_add(entry, project_root, drifts)
        elif action == "recruit":
            check_recruit(entry, project_root, drifts)

    # Second pass (v5.23+): approval-chain verification — needs the full
    # entry list so we can correlate chain_closed with prior stage_granted.
    check_approval_chains(collected, drifts)

    # Third pass (v6.2+): OKR state drift — stale Os + period overruns.
    check_okr_state(collected, project_root, drifts)

    # Fourth pass (v6.2.1+, gap K): cycle-close-with-okr-aligns-to had a
    # matching checkin; and OKR-topic committee closes emitted okr-set request.
    check_okr_hook_to_checkin(collected, drifts)
    check_committee_to_okr_set(collected, drifts)

    # Fifth pass (v6.3+; renamed v6.4): KB integrate / classify + ralph anti-stop.
    # See L-KB-MID-LOOP-MANDATORY and L-RALPH-PENDING-NONEMPTY lessons.
    check_kb_integrate_or_classify_skipped(collected, drifts)
    check_ralph_anti_stop(collected, project_root, drifts)

    # Sixth pass (v6.4+): content-routing drift counter-check. Walk KB
    # decisions/ for state-shaped entries that landed in KB anyway. Also
    # detect lesson-shaped files that leaked into state/ instead of memory.
    kb_root = args.kb_root or (project_root / ".kiho" / "kb" / "wiki")
    if kb_root.exists():
        check_kb_classification_drift(kb_root, drifts, args.turn_from)
    state_root = project_root / ".kiho" / "state"
    if state_root.exists():
        check_orphan_state_lessons(state_root, drifts)

    # Seventh pass (v6.5.1+): soft-stop drift — CEO ended turn without
    # AskUserQuestion AND without status:complete while plan.md Pending
    # was non-empty. See agents/kiho-ceo.md "No soft-stop prompts" invariant.
    check_soft_stop_drift(collected, project_root, drifts)

    # Eighth pass (v6.6.3+): INTEGRATE skip drift — CEO drafted Lane B (KB)
    # candidates in audit MDs but never spawned kiho-kb-manager. Structural
    # twin of soft-stop: listing intent without acting on it.
    check_integrate_drift(collected, project_root, drifts)

    summary = summarize(drifts)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Status: {summary['status'].upper()}")
        for sev in ("critical", "major", "minor"):
            for d in drifts:
                if d.severity != sev:
                    continue
                print(f"  [{sev.upper()}] seq={d.seq} {d.check}: {d.declared} → {d.actual}")

    return SEVERITY_EXIT[summary["status"]]


if __name__ == "__main__":
    sys.exit(main())
