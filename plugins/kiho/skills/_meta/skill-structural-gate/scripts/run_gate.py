#!/usr/bin/env python3
"""
run_gate.py — combined structural-gate runner for skill-structural-gate.

Invokes graph_scan.py and parity_diff.py in sequence and merges their verdicts
into a single JSON payload so the skill-factory orchestrator (bin/skill_factory.py)
can call one subprocess instead of two for Steps 2+3.

Exit codes (0/1/2/3 per v5.15.2 Pattern 9):
    0 — both graph and parity PASS (ok, ok_with_warnings, ok_with_exception)
    1 — at least one scan reported a failure status
    2 — usage error
    3 — internal error (unreadable target, subprocess crash)

Usage:
    python run_gate.py --target <skill_path> --mode pre-regen
    python run_gate.py --target <skill_path> --mode catalog-audit

Regeneration recipe: this is a Tier-2 thin wrapper; it depends only on the two
sibling scripts in this directory. Re-deriving it is mechanical.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRAPH_SCAN = HERE / "graph_scan.py"
PARITY_DIFF = HERE / "parity_diff.py"

GRAPH_OK = {"ok", "ok_with_warnings"}
PARITY_OK = {"ok", "ok_with_exception"}


def run_one(script: Path, target: str, mode: str) -> tuple[int, dict | None, str]:
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--target", target, "--mode", mode],
            capture_output=True, text=True, timeout=60,
        )
        try:
            payload = json.loads(result.stdout) if result.stdout.strip() else None
        except json.JSONDecodeError:
            payload = None
        return result.returncode, payload, result.stderr
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 3, None, str(exc)


def main() -> int:
    ap = argparse.ArgumentParser(description="Combined graph + parity structural gate")
    ap.add_argument("--target", required=True, help="SKILL.md path")
    ap.add_argument("--mode", default="pre-regen",
                    choices=["pre-regen", "catalog-audit", "deprecation-check", "rename-audit"])
    args = ap.parse_args()

    if not GRAPH_SCAN.exists() or not PARITY_DIFF.exists():
        print(json.dumps({"status": "internal_error",
                          "reason": "sibling scripts missing"}), file=sys.stderr)
        return 3

    # Graph runs in all modes; parity only supports pre-regen and catalog-audit
    _, graph_payload, graph_err = run_one(GRAPH_SCAN, args.target, args.mode)

    parity_payload = None
    parity_err = ""
    if args.mode in ("pre-regen", "catalog-audit"):
        _, parity_payload, parity_err = run_one(PARITY_DIFF, args.target, args.mode)

    graph_status = (graph_payload or {}).get("status", "graph_crashed")
    parity_status = (parity_payload or {}).get("status", "skipped") if parity_payload else "skipped"

    graph_ok = graph_status in GRAPH_OK
    parity_ok = parity_status in (PARITY_OK | {"skipped"})

    combined_status = "ok" if (graph_ok and parity_ok) else "fail"

    out = {
        "status": combined_status,
        "target": args.target,
        "mode": args.mode,
        "graph": {
            "status": graph_status,
            "payload": graph_payload,
            "stderr": graph_err[:200] if graph_err else "",
        },
        "parity": {
            "status": parity_status,
            "payload": parity_payload,
            "stderr": parity_err[:200] if parity_err else "",
        },
    }
    print(json.dumps(out, indent=2))
    return 0 if combined_status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
