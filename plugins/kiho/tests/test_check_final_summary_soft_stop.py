"""Unit tests for v6.6.5 Signal 5 — `check_final_summary_soft_stop`.

Mirrors the 5 self-test fixtures in `bin/ceo_behavior_audit.py:run_self_test()`
and adds 2 edge cases (empty payload text / non-string text). Run with:

    pytest plugins/kiho/tests/test_check_final_summary_soft_stop.py -v

or under the project's existing test runner. No external deps beyond stdlib +
pytest.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


# Dynamically load the audit module without requiring it on PYTHONPATH.
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_AUDIT_PATH = _PLUGIN_ROOT / "bin" / "ceo_behavior_audit.py"
_spec = importlib.util.spec_from_file_location("ceo_behavior_audit", _AUDIT_PATH)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
sys.modules["ceo_behavior_audit"] = _module
_spec.loader.exec_module(_module)

check_final_summary_soft_stop = _module.check_final_summary_soft_stop
Drift = _module.Drift


def _setup_project(tmp_path: Path, pending_count: int) -> Path:
    """Create a minimal `<project>/.kiho/state/plan.md` for the scan."""
    (tmp_path / ".kiho" / "state").mkdir(parents=True, exist_ok=True)
    plan_md = tmp_path / ".kiho" / "state" / "plan.md"
    if pending_count > 0:
        lines = ["# plan", "", "## Pending"]
        lines.extend(f"- item {i}" for i in range(pending_count))
        plan_md.write_text("\n".join(lines), encoding="utf-8")
    else:
        plan_md.write_text(
            "# plan\n\n## Pending\n\n## Completed\n", encoding="utf-8"
        )
    return tmp_path


# ---------------------------------------------------------------------------
# Fixture 1: clean turn — no soft-stop in prose, no drift expected
# ---------------------------------------------------------------------------


def test_clean_complete_no_softstop(tmp_path: Path) -> None:
    project = _setup_project(tmp_path, pending_count=0)
    entries = [
        {"action": "tier_declared", "value": "normal", "seq": 1},
        {"action": "initialize", "seq": 2},
        {
            "action": "final_summary_text",
            "payload": {
                "text": "All 3 phases shipped. Tests green. KB integrated. Audit clean."
            },
            "seq": 3,
        },
        {"action": "done", "payload": {"status": "complete"}, "seq": 4},
    ]
    drifts: list = []
    check_final_summary_soft_stop(entries, project, drifts)
    assert len(drifts) == 0


# ---------------------------------------------------------------------------
# Fixture 2: soft-stop in prose, Pending empty → MAJOR
# ---------------------------------------------------------------------------


def test_softstop_pending_empty_is_major(tmp_path: Path) -> None:
    project = _setup_project(tmp_path, pending_count=0)
    entries = [
        {"action": "tier_declared", "value": "careful", "seq": 1},
        {"action": "initialize", "seq": 2},
        {
            "action": "final_summary_text",
            "payload": {"text": "Done. 要我接下來幫你提 PR 嗎？還是先擱置？"},
            "seq": 3,
        },
        {"action": "done", "payload": {"status": "complete"}, "seq": 4},
    ]
    drifts: list = []
    check_final_summary_soft_stop(entries, project, drifts)
    assert len(drifts) == 1
    d: Drift = drifts[0]
    assert d.severity == "major"
    assert d.check == "final_summary_soft_stop"


# ---------------------------------------------------------------------------
# Fixture 3: soft-stop in prose, Pending non-empty → CRITICAL
# ---------------------------------------------------------------------------


def test_softstop_pending_nonempty_is_critical(tmp_path: Path) -> None:
    project = _setup_project(tmp_path, pending_count=5)
    entries = [
        {"action": "tier_declared", "value": "careful", "seq": 1},
        {"action": "initialize", "seq": 2},
        {
            "action": "final_summary_text",
            "payload": {
                "text": "Phase A done. Want me to start Phase B next, or pause?"
            },
            "seq": 3,
        },
        {"action": "done", "payload": {"status": "complete"}, "seq": 4},
    ]
    drifts: list = []
    check_final_summary_soft_stop(entries, project, drifts)
    assert len(drifts) == 1
    d: Drift = drifts[0]
    assert d.severity == "critical"
    assert d.check == "plan_pending_with_final_summary_soft_stop"


# ---------------------------------------------------------------------------
# Fixture 4: AskUserQuestion called → soft-stop prose suppressed
# ---------------------------------------------------------------------------


def test_softstop_with_ask_user_is_suppressed(tmp_path: Path) -> None:
    project = _setup_project(tmp_path, pending_count=5)
    entries = [
        {"action": "tier_declared", "value": "careful", "seq": 1},
        {"action": "initialize", "seq": 2},
        {"action": "ask_user", "seq": 3},
        {
            "action": "final_summary_text",
            "payload": {
                "text": "Per your answer, 要我繼續往 Phase B 走 (referencing prior Q)"
            },
            "seq": 4,
        },
        {"action": "done", "payload": {"status": "complete"}, "seq": 5},
    ]
    drifts: list = []
    check_final_summary_soft_stop(entries, project, drifts)
    assert len(drifts) == 0


# ---------------------------------------------------------------------------
# Fixture 5: no final_summary_text logged → no scan, no drift
# ---------------------------------------------------------------------------


def test_no_final_summary_text_no_drift(tmp_path: Path) -> None:
    project = _setup_project(tmp_path, pending_count=5)
    entries = [
        {"action": "tier_declared", "value": "normal", "seq": 1},
        {"action": "initialize", "seq": 2},
        {"action": "done", "payload": {"status": "complete"}, "seq": 3},
    ]
    drifts: list = []
    check_final_summary_soft_stop(entries, project, drifts)
    assert len(drifts) == 0


# ---------------------------------------------------------------------------
# Edge case A: empty payload.text — no scan, no drift
# ---------------------------------------------------------------------------


def test_empty_payload_text_no_drift(tmp_path: Path) -> None:
    project = _setup_project(tmp_path, pending_count=0)
    entries = [
        {"action": "tier_declared", "value": "normal", "seq": 1},
        {"action": "initialize", "seq": 2},
        {"action": "final_summary_text", "payload": {"text": ""}, "seq": 3},
        {"action": "done", "payload": {"status": "complete"}, "seq": 4},
    ]
    drifts: list = []
    check_final_summary_soft_stop(entries, project, drifts)
    assert len(drifts) == 0


# ---------------------------------------------------------------------------
# Edge case B: non-string payload.text — no crash, no drift
# ---------------------------------------------------------------------------


def test_non_string_payload_text_no_crash(tmp_path: Path) -> None:
    project = _setup_project(tmp_path, pending_count=0)
    entries = [
        {"action": "tier_declared", "value": "normal", "seq": 1},
        {"action": "initialize", "seq": 2},
        {"action": "final_summary_text", "payload": {"text": None}, "seq": 3},
        {"action": "final_summary_text", "payload": {"text": 42}, "seq": 4},
        {"action": "final_summary_text", "payload": {"text": ["array"]}, "seq": 5},
        {"action": "done", "payload": {"status": "complete"}, "seq": 6},
    ]
    drifts: list = []
    # Must not raise even with unexpected types
    check_final_summary_soft_stop(entries, project, drifts)
    assert len(drifts) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
