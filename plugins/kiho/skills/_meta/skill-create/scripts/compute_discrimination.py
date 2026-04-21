#!/usr/bin/env python3
"""
compute_discrimination.py — assertion-discrimination scorer (v5.14).

Computes the per-assertion discrimination delta between a with-skill benchmark
run and a without-skill baseline run. Used by the skill-create analyzer sub-agent
and by Gate 12. Exit 0 if the draft skill has discrimination_ratio >= 0.50 and
zero anti-discriminating assertions; exit 1 otherwise.

Input: two JSON files (benchmark, baseline) each with the same scenario set and
per-scenario per-assertion pass records.

Output: JSON to stdout with the full analysis.json shape defined in
agents/analyzer.md.

Grounding: anthropics/skills Mar 6 2026 commit b0cbd3d, schemas.md analysis.json.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Tunables — justified values
DISCRIMINATING_THRESHOLD = 0.20   # delta >= 0.20 means the skill actually changes outcomes
SATURATION_FLOOR = 0.95           # both runs > 0.95 means trivially saturated assertion
FLAKINESS_THRESHOLD = 0.20        # stddev/mean > 0.20 across runs means flaky
POOL_DISCRIMINATION_RATIO = 0.50  # at least 50% of assertions must discriminate
SLOW_TIME_MULT = 2.0              # >2x baseline time = slow
EXPENSIVE_TOKEN_MULT = 3.0        # >3x baseline tokens = expensive


@dataclass
class AssertionResult:
    assertion_id: str
    delta: float
    pass_with: float
    pass_without: float
    verdict: str


def load_run(path: Path) -> dict[str, Any]:
    if not path.exists():
        sys.stderr.write(f"missing run file: {path}\n")
        sys.exit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def collect_assertions(run: dict[str, Any]) -> dict[str, list[bool]]:
    """Return {assertion_id: [pass_for_scenario1, pass_for_scenario2, ...]}.

    Accepts two input shapes:
      shape A:  scenarios: [{assertions: [{id, passed}, ...]}, ...]
      shape B:  assertions: {<id>: [true, false, ...]}
    """
    out: dict[str, list[bool]] = {}

    if isinstance(run.get("scenarios"), list):
        for scen in run["scenarios"]:
            for a in scen.get("assertions", []):
                aid = str(a.get("id") or a.get("assertion_id"))
                passed = bool(a.get("passed"))
                out.setdefault(aid, []).append(passed)
        return out

    if isinstance(run.get("assertions"), dict):
        for aid, values in run["assertions"].items():
            out[str(aid)] = [bool(v) for v in values]
        return out

    sys.stderr.write("run has neither scenarios[] nor assertions{} — cannot parse\n")
    sys.exit(3)


def pass_rate(bools: list[bool]) -> float:
    if not bools:
        return 0.0
    return sum(1 for b in bools if b) / len(bools)


def compute_delta(with_run: dict[str, list[bool]],
                  without_run: dict[str, list[bool]]) -> list[AssertionResult]:
    results: list[AssertionResult] = []
    all_ids = set(with_run) | set(without_run)
    for aid in sorted(all_ids):
        pw = pass_rate(with_run.get(aid, []))
        pwo = pass_rate(without_run.get(aid, []))
        delta = pw - pwo
        if pw >= SATURATION_FLOOR and pwo >= SATURATION_FLOOR:
            verdict = "saturated"
        elif delta < 0.0:
            verdict = "anti"
        elif delta >= DISCRIMINATING_THRESHOLD:
            verdict = "discriminating"
        else:
            verdict = "weak"
        results.append(AssertionResult(aid, delta, pw, pwo, verdict))
    return results


def compute_flakiness(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect flaky scenarios using per-run pass rates, if provided.

    Expects optional shape: scenarios[n].runs[r].pass_rate
    """
    flaky: list[dict[str, Any]] = []
    for scen in run.get("scenarios") or []:
        runs = scen.get("runs") or []
        if len(runs) < 2:
            continue
        rates = [float(r.get("pass_rate", 0.0)) for r in runs]
        mean = statistics.mean(rates) if rates else 0.0
        if mean <= 0.0:
            continue
        stdev = statistics.pstdev(rates)
        flak = stdev / mean
        if flak >= FLAKINESS_THRESHOLD:
            flaky.append({
                "scenario_id": scen.get("id") or scen.get("scenario_id"),
                "per_run_pass_rates": rates,
                "flakiness": round(flak, 3),
            })
    return flaky


def compute_efficiency(
    with_run: dict[str, Any],
    without_run: dict[str, Any],
    delta_sum: float,
) -> tuple[float, list[str], list[str]]:
    with_time = float(with_run.get("mean_time_ms", 0.0))
    without_time = float(without_run.get("mean_time_ms", 0.0))
    with_tokens = float(with_run.get("mean_tokens", 0.0))
    without_tokens = float(without_run.get("mean_tokens", 0.0))
    slow: list[str] = []
    expensive: list[str] = []
    if without_time > 0 and with_time > SLOW_TIME_MULT * without_time:
        slow.append(f"mean_time {with_time:.0f}ms > 2x baseline {without_time:.0f}ms")
    if without_tokens > 0 and with_tokens > EXPENSIVE_TOKEN_MULT * without_tokens:
        expensive.append(f"mean_tokens {with_tokens:.0f} > 3x baseline {without_tokens:.0f}")
    token_diff = max(1.0, with_tokens - without_tokens)
    efficiency = delta_sum / (1.0 + math.log10(token_diff))
    return round(efficiency, 3), slow, expensive


def build_analysis(
    with_run: dict[str, Any],
    without_run: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    with_assertions = collect_assertions(with_run)
    without_assertions = collect_assertions(without_run)
    results = compute_delta(with_assertions, without_assertions)

    counts = {"discriminating": 0, "weak": 0, "saturated": 0, "anti": 0}
    for r in results:
        counts[r.verdict] += 1
    total = len(results)
    discrimination_ratio = (counts["discriminating"] / total) if total else 0.0

    flaky = compute_flakiness(with_run)
    delta_sum = sum(max(0.0, r.delta) for r in results)
    efficiency, slow, expensive = compute_efficiency(with_run, without_run, delta_sum)

    if counts["anti"] > 0:
        status = "rejected_anti_discriminating"
    elif discrimination_ratio < POOL_DISCRIMINATION_RATIO:
        status = "rejected_non_discriminating"
    else:
        status = "ok"

    analysis = {
        "status": status,
        "request_id": request_id,
        "benchmark_scenarios": len(with_run.get("scenarios") or []),
        "assertion_count": total,
        "discriminating_count": counts["discriminating"],
        "weak_count": counts["weak"],
        "saturated_count": counts["saturated"],
        "anti_count": counts["anti"],
        "discrimination_ratio": round(discrimination_ratio, 3),
        "per_assertion": [
            {
                "assertion_id": r.assertion_id,
                "delta": round(r.delta, 3),
                "pass_with": round(r.pass_with, 3),
                "pass_without": round(r.pass_without, 3),
                "verdict": r.verdict,
            }
            for r in results
        ],
        "flaky_scenarios": flaky,
        "efficiency_score": efficiency,
        "slow_scenarios": slow,
        "expensive_scenarios": expensive,
        "improvement_suggestions": _build_suggestions(results, flaky, slow, expensive),
        "transcript_insights": [],  # populated by the analyzer sub-agent, not this script
    }
    return analysis


def _build_suggestions(
    results: list[AssertionResult],
    flaky: list[dict[str, Any]],
    slow: list[str],
    expensive: list[str],
) -> list[str]:
    out: list[str] = []
    for r in results:
        if r.verdict == "saturated":
            out.append(
                f"Assertion '{r.assertion_id}' saturates at "
                f"{r.pass_with:.2f}/{r.pass_without:.2f} — consider replacing with a harder test."
            )
        elif r.verdict == "anti":
            out.append(
                f"Assertion '{r.assertion_id}' regresses: delta {r.delta:.2f} "
                f"({r.pass_without:.2f} without -> {r.pass_with:.2f} with). "
                f"Route back to Step 5 with this evidence."
            )
        elif r.verdict == "weak":
            out.append(
                f"Assertion '{r.assertion_id}' is weakly discriminating (delta {r.delta:.2f}). "
                f"Consider replacing or strengthening."
            )
    for f in flaky:
        out.append(
            f"Scenario '{f['scenario_id']}' is flaky (flakiness {f['flakiness']:.2f}). "
            f"Add a deterministic fixture."
        )
    out.extend(slow)
    out.extend(expensive)
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--with-run", required=True,
                   help="benchmark.json (with-skill run results)")
    p.add_argument("--without-run", required=True,
                   help="baseline.json (without-skill run results)")
    p.add_argument("--out", default="-",
                   help="output path for analysis.json, or '-' for stdout")
    p.add_argument("--request-id", default="compute",
                   help="request id for the analysis record")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    with_run = load_run(Path(args.with_run))
    without_run = load_run(Path(args.without_run))
    analysis = build_analysis(with_run, without_run, args.request_id)

    if args.out == "-":
        sys.stdout.write(json.dumps(analysis, indent=2))
        sys.stdout.write("\n")
    else:
        Path(args.out).write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        sys.stderr.write(f"wrote {args.out}\n")

    return 0 if analysis["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
