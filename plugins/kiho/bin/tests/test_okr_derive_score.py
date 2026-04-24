"""Unit tests for bin/okr_derive_score.py (v6.2+).

Covers: outcome derivation (success / success-with-blockers / abort /
in-progress), conservative formula at base + stretch KRs, cap at 1.0,
zero-weight KRs no-op.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE.parent
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

import okr_derive_score  # type: ignore  # noqa: E402


def _okr(weight: int = 50, current: float = 0.3, stretch: bool = False, kr_id: str = "k1") -> str:
    return textwrap.dedent(f"""
    ---
    o_id: O-test-01
    ---
    # Test O

    ## Key Results

    ### {kr_id}

    - weight: {weight}
    - current_score: {current}
    - stretch: {str(stretch).lower()}
    """).lstrip()


def test_success_outcome_applies_base_delta(tmp_path: Path) -> None:
    okr = tmp_path / "O.md"
    okr.write_text(_okr(weight=100, current=0.30, stretch=False), encoding="utf-8")
    handoffs = [{"status": "closed-success"}]
    result = okr_derive_score.compute_deltas(okr, handoffs)
    assert result["outcome"] == "success"
    assert result["success_weight"] == 1.0
    d = result["deltas"][0]
    # 0.05 × 1.0 × 1.0 = 0.05
    assert d["proposed_delta"] == 0.05
    assert d["new_score"] == 0.35


def test_success_with_blockers_halves_delta(tmp_path: Path) -> None:
    okr = tmp_path / "O.md"
    okr.write_text(_okr(weight=100, current=0.30), encoding="utf-8")
    handoffs = [
        {"status": "blocked", "blockers": ["something"]},
        {"status": "closed-success"},
    ]
    result = okr_derive_score.compute_deltas(okr, handoffs)
    assert result["outcome"] == "success-with-blockers"
    assert result["success_weight"] == 0.5
    assert result["deltas"][0]["proposed_delta"] == 0.025


def test_abort_outcome_zero_delta(tmp_path: Path) -> None:
    okr = tmp_path / "O.md"
    okr.write_text(_okr(weight=100, current=0.30), encoding="utf-8")
    handoffs = [{"status": "closed-failure"}]
    result = okr_derive_score.compute_deltas(okr, handoffs)
    assert result["outcome"] == "abort"
    assert result["success_weight"] == 0.0
    assert result["deltas"][0]["proposed_delta"] == 0.0


def test_stretch_kr_halved(tmp_path: Path) -> None:
    okr = tmp_path / "O.md"
    okr.write_text(_okr(weight=100, current=0.30, stretch=True), encoding="utf-8")
    handoffs = [{"status": "closed-success"}]
    result = okr_derive_score.compute_deltas(okr, handoffs)
    # 0.05 × 1.0 × 1.0 × 0.5 stretch multiplier = 0.025
    assert result["deltas"][0]["proposed_delta"] == 0.025


def test_delta_capped_at_one(tmp_path: Path) -> None:
    okr = tmp_path / "O.md"
    okr.write_text(_okr(weight=100, current=0.98), encoding="utf-8")
    handoffs = [{"status": "closed-success"}]
    result = okr_derive_score.compute_deltas(okr, handoffs)
    # Would propose 0.05 but cap at 1.0 means applied delta = 0.02
    assert result["deltas"][0]["new_score"] == 1.0
    assert result["deltas"][0]["proposed_delta"] == 0.02


def test_multiple_krs_weighted(tmp_path: Path) -> None:
    okr = tmp_path / "O.md"
    body = textwrap.dedent("""
    ---
    o_id: O-test-01
    ---
    ## Key Results

    ### k1
    - weight: 40
    - current_score: 0.0
    - stretch: false

    ### k2
    - weight: 60
    - current_score: 0.0
    - stretch: false
    """).lstrip()
    okr.write_text(body, encoding="utf-8")
    handoffs = [{"status": "closed-success"}]
    result = okr_derive_score.compute_deltas(okr, handoffs)
    by_id = {d["kr_id"]: d for d in result["deltas"]}
    # 0.05 × 0.40 × 1.0 = 0.02
    assert by_id["k1"]["proposed_delta"] == 0.02
    # 0.05 × 0.60 × 1.0 = 0.03
    assert by_id["k2"]["proposed_delta"] == 0.03


def test_zero_weight_kr_no_op(tmp_path: Path) -> None:
    okr = tmp_path / "O.md"
    okr.write_text(_okr(weight=0, current=0.50), encoding="utf-8")
    handoffs = [{"status": "closed-success"}]
    result = okr_derive_score.compute_deltas(okr, handoffs)
    assert result["deltas"][0]["proposed_delta"] == 0.0


def test_empty_handoffs_is_in_progress(tmp_path: Path) -> None:
    okr = tmp_path / "O.md"
    okr.write_text(_okr(weight=100, current=0.30), encoding="utf-8")
    handoffs: list[dict] = []
    result = okr_derive_score.compute_deltas(okr, handoffs)
    assert result["outcome"] == "in-progress"
    assert result["deltas"][0]["proposed_delta"] == 0.0


def test_parse_outcome_last_state_wins(tmp_path: Path) -> None:
    # Blocker earlier then clean success → success-with-blockers
    handoffs = [
        {"status": "in-progress"},
        {"status": "blocked", "blockers": ["dep"]},
        {"status": "in-progress"},
        {"status": "closed-success"},
    ]
    okr = tmp_path / "O.md"
    okr.write_text(_okr(), encoding="utf-8")
    result = okr_derive_score.compute_deltas(okr, handoffs)
    assert result["outcome"] == "success-with-blockers"
