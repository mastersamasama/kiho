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


def check_kb_integrate_discipline(entries: list[dict], drifts: list[Drift]) -> None:
    """[v6.3 — L-KB-MID-LOOP-MANDATORY enforcement]

    Every iteration's confidence ≥0.90 decision MUST trigger immediate
    `kb_add` OR explicit `kb_deferred` ledger entry. Silent skip is drift.

    Audit logic:
      - Find every `subagent_return` entry with payload.confidence >= 0.90
        AND payload.status in {ok, complete}
      - For each, verify a subsequent `kb_add` OR `kb_deferred` entry exists
        within the same turn (between this entry and the next `done`/`tier_declared`)
      - Missing match = MAJOR drift `kb_integrate_skipped`
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

    for idx, return_entry in high_conf_returns:
        # Find the next turn boundary AFTER this return
        next_boundary = next(
            (b for b in turn_boundaries if b > idx), len(entries)
        )
        # Look for kb_add or kb_deferred between idx+1 and next_boundary
        window = entries[idx + 1 : next_boundary]
        has_kb = any(
            (e.get("action") or "") in ("kb_add", "kb_deferred", "kb_add_batch")
            for e in window
        )
        if not has_kb:
            drifts.append(
                Drift(
                    return_entry.get("seq"),
                    "major",
                    "kb_integrate_skipped",
                    return_entry.get("target") or "<unknown>",
                    f"high-confidence return ({return_entry.get('payload', {}).get('confidence')}) without subsequent kb_add or kb_deferred entry",
                    "v6.3 L-KB-MID-LOOP-MANDATORY: every confidence ≥0.90 decision MUST trigger kb_add (immediate) or kb_deferred (explicit defer with reason)",
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
    ap = argparse.ArgumentParser(description="kiho v5.22 CEO behavior audit")
    ap.add_argument("--ledger", required=True, type=Path, help="path to ceo-ledger.jsonl")
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

    # Fifth pass (v6.3+): KB integrate + ralph anti-stop discipline.
    # See L-KB-MID-LOOP-MANDATORY and L-RALPH-PENDING-NONEMPTY lessons.
    check_kb_integrate_discipline(collected, drifts)
    check_ralph_anti_stop(collected, project_root, drifts)

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
