#!/usr/bin/env python3
"""Minimal replay-scenario runner for kiho v5.22 gates.

Reads a scenario markdown file with an "Expected CEO behavior under v5.22"
section and checks a ceo-ledger.jsonl against the keyword patterns in the
expectations. Prints PASS/FAIL lines; exits non-zero on any FAIL.

Usage:
    python runner.py --scenario <path> --ledger <path> [--audit-script <path>]

The scenario encodes expected behavior via keyword presence/absence in the
"Expected CEO behavior under v5.22" section. The runner's keyword-to-check
table is explicit (see CHECKS below); new keywords require updating the
runner in the same PR.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


# (keyword in scenario, ledger-entry check function)
# Each entry: if the scenario mentions this keyword, require the ledger to
# contain at least one entry whose `action` matches `ledger_action`.
CHECKS = [
    ("tier_declared", "tier_declared"),
    ("ledger_epoch_marker", "ledger_epoch_marker"),
    ("kb_empty_acknowledged", "kb_empty_acknowledged"),
    ("kb_no_match", "kb_no_match"),
    ("ceo_reflect_complete", "ceo_reflect_complete"),
    ("self_audit_clean", "self_audit_clean"),
    ("self_audit_drift_detected", "self_audit_drift_detected"),
]

# Negative checks — if scenario mentions, require the ledger NOT to have these
NEGATIVE_CHECKS = [
    # "No fanout syntax" in scenario means no target matching *-x<N>
    ("no fanout syntax", re.compile(r'"target":\s*"[^"]*-x\d+"', re.IGNORECASE)),
    # "no direct Write" — we can't fully verify without transcript, but flag
    # if the ledger explicitly has hook_blocked_write entries (those mean the
    # hook fired, which is actually expected under v5.22).
]


def parse_expectations(scenario_path: Path) -> set[str]:
    """Return set of keywords mentioned in the "Expected CEO behavior" section."""
    text = scenario_path.read_text(encoding="utf-8").lower()
    # Isolate the "Expected CEO behavior under v5.22" section
    marker = "expected ceo behavior under v5.22"
    idx = text.find(marker)
    if idx < 0:
        return set()
    section = text[idx:]
    # Cut at next H2 heading
    end = section.find("\n## ", len(marker))
    if end > 0:
        section = section[:end]
    keywords = set()
    for kw, _ in CHECKS:
        if kw.lower() in section:
            keywords.add(kw)
    return keywords


def parse_negatives(scenario_path: Path) -> set[str]:
    text = scenario_path.read_text(encoding="utf-8").lower()
    idx = text.find("expected ceo behavior under v5.22")
    if idx < 0:
        return set()
    section = text[idx:]
    end = section.find("\n## ", 40)
    if end > 0:
        section = section[:end]
    found = set()
    for phrase, _ in NEGATIVE_CHECKS:
        if phrase in section:
            found.add(phrase)
    return found


def iter_ledger(ledger_path: Path):
    try:
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def run_checks(scenario_path: Path, ledger_path: Path, audit_script: Path | None) -> list[CheckResult]:
    results: list[CheckResult] = []
    expected = parse_expectations(scenario_path)
    negatives = parse_negatives(scenario_path)

    ledger_entries = list(iter_ledger(ledger_path))
    actions_seen = {(e.get("action") or "").lower() for e in ledger_entries}
    ledger_raw = ledger_path.read_text(encoding="utf-8", errors="ignore") if ledger_path.exists() else ""

    for kw, ledger_action in CHECKS:
        if kw not in expected:
            continue
        found = ledger_action.lower() in actions_seen
        results.append(
            CheckResult(
                name=f"expect action={ledger_action}",
                passed=found,
                detail="" if found else f"no ledger entry with action={ledger_action}",
            )
        )

    for phrase, pat in NEGATIVE_CHECKS:
        if phrase not in negatives:
            continue
        match = pat.search(ledger_raw)
        results.append(
            CheckResult(
                name=f"expect NO match /{pat.pattern}/",
                passed=match is None,
                detail="" if match is None else f"matched at: {match.group(0)}",
            )
        )

    if audit_script and audit_script.exists():
        try:
            # Use --full so the harness sees drift even on ledgers without an
            # epoch marker (replay scenarios are synthetic; production ledgers
            # write the marker in INITIALIZE step 0).
            rc = subprocess.run(
                ["python", str(audit_script), "--ledger", str(ledger_path), "--json", "--full"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            audit_clean = rc.returncode == 0
            results.append(
                CheckResult(
                    name="ceo_behavior_audit.py exits 0",
                    passed=audit_clean,
                    detail=f"exit={rc.returncode}" if not audit_clean else "",
                )
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            results.append(
                CheckResult(
                    name="ceo_behavior_audit.py invocation",
                    passed=False,
                    detail=f"error: {e}",
                )
            )

    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, type=Path)
    ap.add_argument("--ledger", required=True, type=Path)
    ap.add_argument(
        "--audit-script",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "bin" / "ceo_behavior_audit.py",
        help="path to ceo_behavior_audit.py (default: sibling in bin/)",
    )
    args = ap.parse_args()

    if not args.scenario.exists():
        print(f"ERROR: scenario not found: {args.scenario}", file=sys.stderr)
        return 2
    if not args.ledger.exists():
        print(f"ERROR: ledger not found: {args.ledger}", file=sys.stderr)
        return 2

    results = run_checks(args.scenario, args.ledger, args.audit_script)
    if not results:
        print(f"WARN: no expectations parsed from {args.scenario.name}")
        return 1

    failed = 0
    print(f"Scenario: {args.scenario.name}")
    print(f"Ledger:   {args.ledger}")
    print("-" * 60)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        line = f"  {status}  {r.name}"
        if r.detail:
            line += f"  ({r.detail})"
        print(line)
        if not r.passed:
            failed += 1
    print("-" * 60)
    print(f"{len(results) - failed}/{len(results)} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
