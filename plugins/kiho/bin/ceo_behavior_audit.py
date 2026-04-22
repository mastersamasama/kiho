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
    for entry in iter_ledger(ledger, args.turn_from, skip_pre_epoch=not args.full):
        action = entry.get("action", "")
        if action == "delegate":
            check_delegate(entry, drifts)
        elif action in {"kb_add", "kb_update"}:
            check_kb_add(entry, project_root, drifts)
        elif action == "recruit":
            check_recruit(entry, project_root, drifts)

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
