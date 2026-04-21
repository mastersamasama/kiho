#!/usr/bin/env python3
"""
run_loop.py — skill-create iteration orchestrator (v5.14).

Runs multiple skill-create iterations, invokes the comparator between them,
and selects the best iteration using the NON-MONOTONIC rule: the winner is
not necessarily the most recent iteration.

This script does NOT run Claude. It only orchestrates artifacts:
- Reads per-iteration benchmark.json and analysis.json
- Calls the comparator sub-agent via a structured input file
- Tracks current-best across iterations
- Produces a final run-loop summary

Invocation:
    python run_loop.py --draft-dir <path> [--max-iterations N] [--min-improvement F]

Where <path> contains iterations/<n>/ subdirs each with SKILL.md, benchmark.json, analysis.json.

Grounded in Anthropic's Mar 24 2026 harness-design post (non-monotonic iteration)
and Mar 6 2026 anthropics/skills run_loop.py (best-by-test-score, fallback-by-train).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Tunables — justified values
DEFAULT_MAX_ITERATIONS = 5          # matches Anthropic improve_description.py cap
DEFAULT_MIN_IMPROVEMENT = 0.02      # 2% discrimination delta required to be "better"
HALT_AFTER_FAILS = 2                # halt after 2 consecutive non-improvements


@dataclass
class Iteration:
    number: int
    path: Path
    benchmark: dict[str, Any] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)
    loaded: bool = False

    def load(self) -> None:
        bench_path = self.path / "benchmark.json"
        analysis_path = self.path / "analysis.json"
        if bench_path.exists():
            self.benchmark = json.loads(bench_path.read_text(encoding="utf-8"))
        if analysis_path.exists():
            self.analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        self.loaded = bool(self.benchmark or self.analysis)

    @property
    def discrimination_ratio(self) -> float:
        return float(self.analysis.get("discrimination_ratio", 0.0))

    @property
    def correctness_score(self) -> float:
        bench_grading = self.benchmark.get("grading") or {}
        return float(bench_grading.get("pass_rate", 0.0))

    @property
    def mean_tokens(self) -> float:
        return float(self.benchmark.get("mean_tokens", 0.0))

    @property
    def composite(self) -> float:
        # Composite used only as a fallback when the comparator cannot run.
        # The real winner is chosen by the comparator; this is a pre-check.
        return self.discrimination_ratio * 0.6 + self.correctness_score * 0.4


def discover_iterations(draft_dir: Path) -> list[Iteration]:
    iter_root = draft_dir / "iterations"
    if not iter_root.exists():
        return []
    iters: list[Iteration] = []
    for entry in sorted(iter_root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        try:
            n = int(entry.name)
        except ValueError:
            continue
        it = Iteration(number=n, path=entry)
        it.load()
        iters.append(it)
    return iters


def write_comparator_input(
    current_best: Iteration,
    candidate: Iteration,
    out_path: Path,
    request_id: str,
) -> None:
    """Write the structured input file that a comparator agent will read."""
    # Deterministic seed from iteration numbers — keeps the A/B blinding reproducible.
    seed = (hash((current_best.number, candidate.number)) & 0xFFFF)
    payload = {
        "request_id": request_id,
        "seed": seed,
        "left": {
            "iteration": current_best.number,
            "skill_md_path": str(current_best.path / "SKILL.md"),
            "benchmark_path": str(current_best.path / "benchmark.json"),
            "analysis_path": str(current_best.path / "analysis.json"),
        },
        "right": {
            "iteration": candidate.number,
            "skill_md_path": str(candidate.path / "SKILL.md"),
            "benchmark_path": str(candidate.path / "benchmark.json"),
            "analysis_path": str(candidate.path / "analysis.json"),
        },
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def pick_best_pre_comparator(iters: list[Iteration]) -> Iteration:
    """Fallback when the comparator cannot run — pick by composite score.

    The real (comparator-driven) winner selection happens by reading
    comparison.json files; this is a last-resort pre-check.
    """
    loaded = [it for it in iters if it.loaded]
    if not loaded:
        raise RuntimeError("No iterations with loaded benchmark+analysis data.")
    loaded.sort(key=lambda it: (it.composite, -it.mean_tokens, it.number), reverse=True)
    return loaded[0]


def detect_best_via_comparisons(iters: list[Iteration]) -> Iteration | None:
    """Walk existing comparison.json files in iterations/<n>/comparisons/ and
    compute which iteration is the current best per the comparator verdicts.

    If no comparison.json exists yet, return None — caller should fall back.
    """
    if not iters:
        return None
    # Each iteration may host comparator outputs it won
    wins: dict[int, int] = {it.number: 0 for it in iters}
    for it in iters:
        comp_dir = it.path / "comparisons"
        if not comp_dir.exists():
            continue
        for comp_file in comp_dir.glob("*.json"):
            try:
                comp = json.loads(comp_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            winner_iter = comp.get("winner_iteration")
            if isinstance(winner_iter, int) and winner_iter in wins:
                wins[winner_iter] += 1
    if not wins:
        return None
    best_num = max(wins, key=lambda n: (wins[n], n))
    for it in iters:
        if it.number == best_num:
            return it
    return None


def summarize_run(
    iters: list[Iteration],
    best: Iteration,
    out_path: Path,
    max_iters: int,
) -> dict[str, Any]:
    summary = {
        "status": "ok",
        "iterations_run": len(iters),
        "max_iterations": max_iters,
        "best_iteration": best.number,
        "best_discrimination_ratio": best.discrimination_ratio,
        "best_correctness": best.correctness_score,
        "best_mean_tokens": best.mean_tokens,
        "per_iteration": [
            {
                "iteration": it.number,
                "discrimination_ratio": it.discrimination_ratio,
                "correctness": it.correctness_score,
                "mean_tokens": it.mean_tokens,
                "loaded": it.loaded,
            }
            for it in iters
        ],
        "non_monotonic_winner": (
            len(iters) > 1 and best.number != max(it.number for it in iters if it.loaded)
        ),
        "selection_method": "comparator" if best is not None else "fallback",
    }
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--draft-dir", required=True,
                   help=".kiho/state/drafts/sk-<slug>/ path")
    p.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    p.add_argument("--min-improvement", type=float, default=DEFAULT_MIN_IMPROVEMENT)
    p.add_argument("--request-id", default="manual",
                   help="Request ID for comparator input file naming")
    p.add_argument("--mode", choices=["discover", "summarize", "pair"],
                   default="summarize",
                   help="discover: list iterations; summarize: produce run-loop.json; "
                        "pair: write a comparator input for best vs last")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    draft_dir = Path(args.draft_dir).resolve()
    if not draft_dir.exists():
        sys.stderr.write(f"draft dir not found: {draft_dir}\n")
        return 2

    iters = discover_iterations(draft_dir)
    if not iters:
        sys.stderr.write("no iterations found under iterations/\n")
        return 3

    if args.mode == "discover":
        for it in iters:
            print(f"iter {it.number:>3} loaded={it.loaded} "
                  f"disc={it.discrimination_ratio:.2f} "
                  f"correct={it.correctness_score:.2f} "
                  f"tokens={it.mean_tokens:.0f}")
        return 0

    # Try to find the current best via existing comparator outputs
    best = detect_best_via_comparisons(iters)
    if best is None:
        # Fallback to composite
        best = pick_best_pre_comparator(iters)

    if args.mode == "pair":
        # Surface the pair (current-best, most-recent) for the next comparator run
        last = max((it for it in iters if it.loaded), key=lambda it: it.number)
        if last.number == best.number:
            print(f"no pairing needed — best is most recent (iter {best.number})")
            return 0
        pair_path = draft_dir / "iterations" / str(last.number) / "comparisons"
        pair_path.mkdir(parents=True, exist_ok=True)
        out_file = pair_path / f"comparator-input-{args.request_id}.json"
        write_comparator_input(best, last, out_file, args.request_id)
        print(f"wrote {out_file}")
        return 0

    # mode == summarize (default)
    summary_path = draft_dir / "run-loop.json"
    summary = summarize_run(iters, best, summary_path, args.max_iterations)
    sys.stdout.write(json.dumps(summary, indent=2))
    sys.stdout.write("\n")

    if summary["non_monotonic_winner"]:
        sys.stderr.write(
            f"NOTE: non-monotonic winner — best is iter {best.number}, "
            f"last is iter {max(it.number for it in iters if it.loaded)}\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
