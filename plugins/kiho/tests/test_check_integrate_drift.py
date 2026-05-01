#!/usr/bin/env python3
"""Synthetic tests for kiho v6.6.3 ceo_behavior_audit.check_integrate_drift.

Stdlib-only; uses tempdir-built project skeletons (no real .kiho project state).
Run from repo root with:
    python -m unittest plugins.kiho.tests.test_check_integrate_drift -v

Or directly:
    python plugins/kiho/tests/test_check_integrate_drift.py

Tests (6 cases — v6.6.3 §5 + v6.6.4 auto-fix happy path):
  1. clean         — no candidate keywords in MD                     → no drift
  2. bare match    — 1 "Lane B (KB) candidate", 0 kb_add_called      → MAJOR drift
  3. systemic      — 4 "high confidence ≥ 0.90", 0 kb_add_called     → CRITICAL drift (≥3)
  4. resolved      — 2 candidates + 2 kb_add_called in ledger        → no drift
  5. integrated    — candidate line carries [INTEGRATED commit ABCD] → no drift
  6. v6.6.4 auto   — persona self-spawned kb-manager mid-loop AND
                     audit MD carries [INTEGRATED commit ABCD]       → no drift
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Make bin/ importable without packaging it.
HERE = Path(__file__).resolve().parent
BIN_DIR = HERE.parent / "bin"
sys.path.insert(0, str(BIN_DIR))

import ceo_behavior_audit as audit  # type: ignore[import-not-found]  # noqa: E402


def _make_project(
    tmp: Path,
    audit_md_body: str | None,
    md_subpath: str = "2026-05-02/session/notes.md",
) -> Path:
    """Build a minimal .kiho/audit/<md_subpath> tree with a single MD body.

    Returns the project root. The ledger is the caller's responsibility — we
    pass the entries list directly into check_integrate_drift.
    """
    audit_dir = tmp / ".kiho" / "audit" / Path(md_subpath).parent
    audit_dir.mkdir(parents=True, exist_ok=True)
    if audit_md_body is not None:
        md = audit_dir / Path(md_subpath).name
        md.write_text(audit_md_body, encoding="utf-8")
        # Bump mtime to "now" so the turn-window filter does not skip it.
        # (turn_start_ts is older than `time.time()` by construction below.)
        now = time.time()
        os.utime(md, (now, now))
    return tmp


def _ledger_window(actions: list[str]) -> list[dict]:
    """Build a synthetic ledger window with a turn boundary (`tier_declared`)
    at seq 1 and the given actions following it. Timestamps are 1-second
    apart in 1970 — well before any test-run mtime, so the audit MD always
    counts as "this turn" relative to the boundary.
    """
    entries: list[dict] = [
        {"seq": 1, "ts": "1970-01-01T00:00:01Z", "action": "tier_declared", "payload": {"value": "normal"}}
    ]
    for i, action in enumerate(actions, start=2):
        entries.append(
            {
                "seq": i,
                "ts": f"1970-01-01T00:00:{i:02d}Z",
                "action": action,
                "target": "kiho:kiho-kb-manager" if action.startswith("kb_") else "",
                "payload": {"slug": f"test-slug-{i}"} if action == "kb_add" else {},
            }
        )
    return entries


class CheckIntegrateDriftTest(unittest.TestCase):
    def _run(self, body: str | None, ledger_actions: list[str]) -> list[audit.Drift]:
        with tempfile.TemporaryDirectory() as td:
            root = _make_project(Path(td), body)
            entries = _ledger_window(ledger_actions)
            drifts: list[audit.Drift] = []
            audit.check_integrate_drift(entries, root, drifts)
            return drifts

    def test_1_clean_no_candidate_keywords(self):
        body = (
            "# Session notes\n"
            "Refactored logger.ts. Updated 3 imports. No reusable principle\n"
            "surfaced this turn — pure mechanical edit.\n"
        )
        drifts = self._run(body, [])
        self.assertEqual(drifts, [], f"expected no drift on clean MD, got {drifts}")

    def test_2_bare_match_fires_major(self):
        body = (
            "# Audit 2026-05-02\n"
            "## Findings\n"
            "- Lane B (KB) candidate: CV-RUST-FFI-SHELL-PURE — keep FFI as a\n"
            "  thin shell; logic stays in pure Rust.\n"
        )
        drifts = self._run(body, [])  # ledger has zero kb_add evidence
        self.assertEqual(len(drifts), 1, f"expected 1 drift, got {drifts}")
        d = drifts[0]
        self.assertEqual(d.severity, "major")
        self.assertEqual(d.check, "integrate_skipped")
        self.assertIn("Lane B", d.actual)

    def test_3_systemic_escalates_to_critical(self):
        # 4 candidates → ≥3 threshold → CRITICAL across the board.
        body = (
            "# Multi-candidate audit\n"
            "1. high confidence ≥ 0.90 — use revert-then-append for edits.\n"
            "2. high confidence ≥ 0.90 — pnl projection optional per pair.\n"
            "3. high confidence ≥ 0.90 — vendor docs cited inline only.\n"
            "4. high confidence ≥ 0.90 — provider wire protocol classified.\n"
        )
        drifts = self._run(body, [])
        self.assertEqual(len(drifts), 4, f"expected 4 drifts, got {len(drifts)}")
        for d in drifts:
            self.assertEqual(d.severity, "critical")
            self.assertEqual(d.check, "integrate_skipped")

    def test_4_resolved_when_ledger_has_kb_add(self):
        body = (
            "# Audit\n"
            "- Lane B (KB) candidate: CV-RUST-FFI-SHELL-PURE\n"
            "- Lane B (KB) candidate: CV-EDIT-VIA-REVERT-APPEND\n"
        )
        # Two kb_add_called entries — sufficient evidence kb-manager ran.
        drifts = self._run(body, ["kb_add_called", "kb_add"])
        self.assertEqual(drifts, [], f"expected no drift when ledger shows kb-add, got {drifts}")

    def test_5_integrated_marker_skips_line(self):
        body = (
            "# Past + present\n"
            "- Lane B (KB) candidate: CV-OLD [INTEGRATED commit ABCD] — already shipped.\n"
            "- Routine note with no candidate language.\n"
        )
        drifts = self._run(body, [])  # no fresh kb-add this turn
        self.assertEqual(
            drifts,
            [],
            f"[INTEGRATED ...] marker should suppress the candidate line, got {drifts}",
        )

    def test_6_v664_persona_auto_fix_happy_path(self):
        """v6.6.4: when CEO persona self-detects and spawns kb-manager mid-loop,
        the ledger ends with kb_add_called and the audit MD has [INTEGRATED ...]
        marker. Detector should NOT flag drift in this happy path.

        Why both signals together: the [INTEGRATED ...] marker proves the audit
        MD reflects post-spawn reality (line-level suppression), and the ledger
        kb_add_called proves the spawn actually happened (turn-level
        suppression). Either alone is enough; both together is the canonical
        v6.6.4 footprint.
        """
        body = (
            "# Audit 2026-05-02\n"
            "## Findings\n"
            "- Lane B (KB) candidate: CV-FOO 0.92 [INTEGRATED commit abc123 wiki/decisions/CV-FOO.md] — auto-spawned kb-manager mid-loop.\n"
        )
        drifts = self._run(body, ["kb_add_called"])
        self.assertEqual(
            drifts,
            [],
            f"v6.6.4 happy path (persona auto-fix + [INTEGRATED ...] marker) should produce no drift, got {drifts}",
        )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "-v"], exit=True)
