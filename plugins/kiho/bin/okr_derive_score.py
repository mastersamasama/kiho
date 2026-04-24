#!/usr/bin/env python3
"""Derive a conservative KR score delta from cycle handoffs (v6.2+).

Called by the cycle-runner `okr-checkin` hook when a cycle closes with
`aligns_to_okr` set. Reads the cycle's `handoffs.jsonl`, counts phase-owner
successes, and proposes per-KR score increments using a CONSERVATIVE formula
that avoids over-crediting:

    delta_kr = 0.05 × (kr.weight / 100) × success_weight
    success_weight = 1.0 for clean success, 0.5 for success-with-blockers, 0 for abort

The resulting score never exceeds 1.0 (capped at emit) and stretch KRs have
their delta halved (they're aspirational, not standard progress).

Invocation:
    python bin/okr_derive_score.py --project <path> --cycle-id <id> \\
        --o-id <okr-id> [--dry-run] [--json]

Exit codes:
  0 — delta computed (even if zero)
  2 — usage error
  3 — cycle or OKR file missing / unparseable

Output (JSON):
    {
      "cycle_id": "...",
      "o_id": "...",
      "outcome": "success" | "success-with-blockers" | "abort" | "in-progress",
      "deltas": [
        {"kr_id": "...", "current_score": 0.60, "proposed_delta": 0.04, "new_score": 0.64, "stretch": false},
        ...
      ],
      "formula_used": "conservative-v6.2",
      "success_weight": 1.0
    }

Decision: v6.2 OKR auto-flow; stretch cap matches committee-01 decision
(which v6.1 okr-close honors) — stretch KRs can't inflate the aggregate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

BASE_DELTA = 0.05  # conservative: 5% credit per clean success
ABORT_WEIGHT = 0.0
BLOCKED_SUCCESS_WEIGHT = 0.5
CLEAN_SUCCESS_WEIGHT = 1.0
STRETCH_MULT = 0.5  # stretch KRs get half credit per cycle-close


@dataclass
class KRRow:
    kr_id: str
    weight: int
    current_score: float
    stretch: bool


def _iter_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _parse_outcome(handoffs: list[dict]) -> str:
    """Derive cycle outcome from handoffs.jsonl last-state."""
    if not handoffs:
        return "in-progress"
    last = handoffs[-1]
    status = str(last.get("status", "")).lower()
    if status in {"closed-success", "closed_success", "success"}:
        # Check for blocker annotations anywhere in the stream
        for h in handoffs:
            if h.get("blockers") or h.get("status") == "blocked":
                return "success-with-blockers"
        return "success"
    if status in {"closed-failure", "cancelled", "aborted", "abort", "closed_abort"}:
        return "abort"
    return "in-progress"


def _load_okr_krs(okr_file: Path) -> list[KRRow]:
    """Best-effort parse of KR blocks from the Tier-1 markdown OKR file."""
    if not okr_file.exists():
        raise FileNotFoundError(okr_file)
    text = okr_file.read_text(encoding="utf-8", errors="ignore")
    krs: list[KRRow] = []
    # Split on "### <kr_id>" headers; collect fields until next ### or end
    sections = re.split(r"\n###\s+", text)
    if not sections:
        return krs
    for sec in sections[1:]:
        # First line is the kr_id
        head, _, rest = sec.partition("\n")
        kr_id = head.strip()
        if not kr_id:
            continue
        weight_m = re.search(r"-\s*weight\s*:\s*(\d+)", rest)
        score_m = re.search(r"-\s*current_score\s*:\s*([\d.]+)", rest)
        stretch_m = re.search(r"-\s*stretch\s*:\s*(true|false)", rest, re.IGNORECASE)
        if not weight_m:
            continue
        weight = int(weight_m.group(1))
        current = float(score_m.group(1)) if score_m else 0.0
        stretch = bool(stretch_m and stretch_m.group(1).lower() == "true")
        krs.append(KRRow(kr_id=kr_id, weight=weight, current_score=current, stretch=stretch))
    return krs


def compute_deltas(okr_file: Path, cycle_handoffs: list[dict]) -> dict:
    krs = _load_okr_krs(okr_file)
    outcome = _parse_outcome(cycle_handoffs)
    success_weight = {
        "success": CLEAN_SUCCESS_WEIGHT,
        "success-with-blockers": BLOCKED_SUCCESS_WEIGHT,
        "abort": ABORT_WEIGHT,
        "in-progress": 0.0,
    }.get(outcome, 0.0)
    deltas: list[dict] = []
    for kr in krs:
        if success_weight == 0.0 or kr.weight == 0:
            proposed = 0.0
        else:
            proposed = BASE_DELTA * (kr.weight / 100) * success_weight
            if kr.stretch:
                proposed *= STRETCH_MULT
        new_score = min(1.0, kr.current_score + proposed)
        applied_delta = round(new_score - kr.current_score, 4)
        deltas.append({
            "kr_id": kr.kr_id,
            "weight": kr.weight,
            "stretch": kr.stretch,
            "current_score": kr.current_score,
            "proposed_delta": applied_delta,
            "new_score": round(new_score, 4),
        })
    return {
        "outcome": outcome,
        "success_weight": success_weight,
        "formula_used": "conservative-v6.2",
        "deltas": deltas,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="kiho v6.2 OKR score-delta deriver")
    ap.add_argument("--project", type=Path, default=Path.cwd(), help="project root")
    ap.add_argument("--cycle-id", required=True, help="cycle id")
    ap.add_argument("--o-id", required=True, help="target OKR id (aligns_to_okr)")
    ap.add_argument("--dry-run", action="store_true", help="compute but do not emit a writeable payload")
    args = ap.parse_args(argv)

    project = args.project.resolve()
    # Find the OKR file — period is embedded in the O-id (e.g., O-2026Q2-company-01)
    m = re.match(r"^O-(\d{4}-[QH][1-4]|\d{4}-[a-z0-9-]+)-", args.o_id)
    if not m:
        print(f"bad --o-id format: {args.o_id}", file=sys.stderr)
        return 2
    period = m.group(1)
    okr_file = project / ".kiho" / "state" / "okrs" / period / f"{args.o_id}.md"
    if not okr_file.exists():
        # Fall back to searching under _closed (shouldn't happen — checking aligned-to-closed O is a separate cascade path)
        closed_file = project / ".kiho" / "state" / "okrs" / period / "_closed" / f"{args.o_id}.md"
        if closed_file.exists():
            print(f"target OKR is already closed: {closed_file}", file=sys.stderr)
            return 3
        print(f"OKR file not found: {okr_file}", file=sys.stderr)
        return 3

    cycle_file = project / ".kiho" / "state" / "cycles" / args.cycle_id / "handoffs.jsonl"
    cycle_handoffs = _iter_jsonl(cycle_file)
    if not cycle_handoffs:
        print(f"cycle handoffs.jsonl missing or empty: {cycle_file}", file=sys.stderr)
        return 3

    result = compute_deltas(okr_file, cycle_handoffs)
    result["cycle_id"] = args.cycle_id
    result["o_id"] = args.o_id
    if args.dry_run:
        result["dry_run"] = True

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
