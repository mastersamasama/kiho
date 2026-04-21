#!/usr/bin/env python3
"""
compute_precision_recall.py — description triggering metrics (v5.14).

Reads a JSONL of triggering results (one record per prompt tested) and
computes precision, recall, F1, and balanced accuracy. Used by Step 4 Phase 2
(iterative description rewriter) to score a description against the 20-prompt
triggering corpus.

Previously (v5.13) improve_description.py only reported train/test accuracy.
v5.14 extends this to precision+recall+F1 because accuracy is a misleading
metric when the positive/negative class balance is not 1:1 or when the cost
of a false positive differs from the cost of a false negative. F1 and
balanced accuracy are more robust to those failure modes.

Grounding: anthropics/skills Mar 6 2026 commit b0cbd3d (run_loop.py reports
precision, recall, accuracy — not just accuracy). kiho v5.14 H1 + Thread 9.

Input JSONL format (one record per line):
    {"prompt": "...", "should_trigger": true, "actually_triggered": false, "split": "train"|"test"}

The "split" field is optional; if present, metrics are reported per-split.

Exit codes:
    0 — F1 >= threshold on the test split (or on all if no split)
    1 — F1 below threshold
    2 — usage or input error
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_F1_THRESHOLD = 0.80
DEFAULT_TRAIN_TEST_OVERFITTING_GAP = 0.20


@dataclass
class Record:
    prompt: str
    should_trigger: bool
    actually_triggered: bool
    split: str


def load_jsonl(path: Path) -> list[Record]:
    records: list[Record] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        records.append(Record(
            prompt=str(obj.get("prompt", "")),
            should_trigger=bool(obj.get("should_trigger", False)),
            actually_triggered=bool(obj.get("actually_triggered", False)),
            split=str(obj.get("split", "all")),
        ))
    return records


def compute_metrics(records: list[Record]) -> dict[str, float]:
    """Classic binary classification metrics.

    Positive class = should_trigger=True.
    """
    tp = sum(1 for r in records if r.should_trigger and r.actually_triggered)
    fp = sum(1 for r in records if not r.should_trigger and r.actually_triggered)
    fn = sum(1 for r in records if r.should_trigger and not r.actually_triggered)
    tn = sum(1 for r in records if not r.should_trigger and not r.actually_triggered)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(records) if records else 0.0

    pos = [r for r in records if r.should_trigger]
    neg = [r for r in records if not r.should_trigger]
    pos_accuracy = sum(1 for r in pos if r.actually_triggered) / len(pos) if pos else 0.0
    neg_accuracy = sum(1 for r in neg if not r.actually_triggered) / len(neg) if neg else 0.0
    balanced_accuracy = (pos_accuracy + neg_accuracy) / 2.0

    return {
        "n": len(records),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "accuracy": round(accuracy, 3),
        "balanced_accuracy": round(balanced_accuracy, 3),
    }


def compute_stratified(records: list[Record]) -> dict[str, dict[str, float]]:
    """Split metrics by the 'split' field."""
    splits: dict[str, list[Record]] = {}
    for r in records:
        splits.setdefault(r.split, []).append(r)
    return {name: compute_metrics(rs) for name, rs in splits.items()}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("input", help="path to triggering JSONL or '-' for stdin")
    p.add_argument("--threshold", type=float, default=DEFAULT_F1_THRESHOLD,
                   help=f"F1 threshold for pass/fail (default {DEFAULT_F1_THRESHOLD})")
    p.add_argument("--overfitting-gap", type=float,
                   default=DEFAULT_TRAIN_TEST_OVERFITTING_GAP,
                   help="train-vs-test F1 gap that triggers an overfitting warning")
    p.add_argument("--gate-on", choices=["test", "all"], default="test",
                   help="which split's metrics determine the exit code")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.input == "-":
        text = sys.stdin.read()
        records = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            records.append(Record(
                prompt=str(obj.get("prompt", "")),
                should_trigger=bool(obj.get("should_trigger", False)),
                actually_triggered=bool(obj.get("actually_triggered", False)),
                split=str(obj.get("split", "all")),
            ))
    else:
        records = load_jsonl(Path(args.input))

    if not records:
        sys.stderr.write("no records loaded\n")
        return 2

    overall = compute_metrics(records)
    per_split = compute_stratified(records)

    # Overfitting detection
    overfitting_warning = None
    if "train" in per_split and "test" in per_split:
        gap = per_split["train"]["f1"] - per_split["test"]["f1"]
        if gap > args.overfitting_gap:
            overfitting_warning = (
                f"train F1 {per_split['train']['f1']} exceeds test F1 "
                f"{per_split['test']['f1']} by {round(gap, 3)} "
                f"(> {args.overfitting_gap}) — likely overfitting"
            )

    # Gate-on decision
    if args.gate_on == "test" and "test" in per_split:
        gate_f1 = per_split["test"]["f1"]
    else:
        gate_f1 = overall["f1"]
    passed = gate_f1 >= args.threshold

    result = {
        "overall": overall,
        "per_split": per_split,
        "threshold": args.threshold,
        "gate_on": args.gate_on,
        "gate_f1": gate_f1,
        "passed": passed,
        "overfitting_warning": overfitting_warning,
    }
    sys.stdout.write(json.dumps(result, indent=2))
    sys.stdout.write("\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
