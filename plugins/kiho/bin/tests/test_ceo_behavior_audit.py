"""Unit tests for bin/ceo_behavior_audit.py.

Uses only stdlib — no pytest dependency. Run with:
    python -m unittest plugins.kiho.bin.tests.test_ceo_behavior_audit -v
or directly:
    python plugins/kiho/bin/tests/test_ceo_behavior_audit.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE.parent
sys.path.insert(0, str(BIN))

import ceo_behavior_audit as cba  # noqa: E402


def _entry(seq: int, action: str, **kw) -> dict:
    base = {"seq": seq, "ts": "2026-04-22T12:00:00Z", "action": action}
    base.update(kw)
    return base


def _write_ledger(path: Path, entries: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


class TestDelegateChecks(unittest.TestCase):
    def test_known_subagent_is_clean(self) -> None:
        drifts: list[cba.Drift] = []
        cba.check_delegate(_entry(1, "delegate", target="kiho:kiho-researcher"), drifts)
        self.assertEqual(drifts, [])

    def test_fanout_suffix_is_major(self) -> None:
        drifts: list[cba.Drift] = []
        cba.check_delegate(_entry(2, "delegate", target="kiho-researcher-x5"), drifts)
        self.assertEqual(len(drifts), 1)
        self.assertEqual(drifts[0].severity, "major")
        self.assertEqual(drifts[0].check, "delegate_target_narrative")

    def test_concat_tools_is_critical(self) -> None:
        drifts: list[cba.Drift] = []
        cba.check_delegate(_entry(3, "delegate", target="deepwiki-mcp+websearch"), drifts)
        self.assertEqual(len(drifts), 1)
        self.assertEqual(drifts[0].severity, "critical")
        self.assertEqual(drifts[0].check, "delegate_target_fabricated")

    def test_unknown_target_is_minor(self) -> None:
        drifts: list[cba.Drift] = []
        cba.check_delegate(_entry(4, "delegate", target="some-unknown-agent"), drifts)
        self.assertEqual(len(drifts), 1)
        self.assertEqual(drifts[0].severity, "minor")

    def test_general_purpose_is_allowed(self) -> None:
        drifts: list[cba.Drift] = []
        cba.check_delegate(_entry(5, "delegate", target="general-purpose"), drifts)
        self.assertEqual(drifts, [])


class TestRecruitChecks(unittest.TestCase):
    def test_missing_role_spec_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            drifts: list[cba.Drift] = []
            cba.check_recruit(
                _entry(1, "recruit", payload={"agents": ["foo-agent"]}), project, drifts
            )
            # Two drifts (no role-spec, no interview)
            self.assertTrue(any(d.check == "recruit_no_role_spec" for d in drifts))
            self.assertTrue(any(d.check == "recruit_no_interview" for d in drifts))
            self.assertTrue(all(d.severity == "critical" for d in drifts))

    def test_role_spec_present_no_interview_is_partial(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            spec_dir = project / ".kiho" / "state" / "recruit" / "foo-agent"
            spec_dir.mkdir(parents=True)
            (spec_dir / "role-spec.md").write_text("# spec", encoding="utf-8")
            drifts: list[cba.Drift] = []
            cba.check_recruit(
                _entry(1, "recruit", payload={"agents": ["foo-agent"]}), project, drifts
            )
            self.assertEqual(len(drifts), 1)
            self.assertEqual(drifts[0].check, "recruit_no_interview")


class TestKbAddChecks(unittest.TestCase):
    def test_missing_wiki_file_is_major(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            drifts: list[cba.Drift] = []
            cba.check_kb_add(
                _entry(1, "kb_add", payload={"entries": ["my-slug"]}), project, drifts
            )
            self.assertEqual(len(drifts), 1)
            self.assertEqual(drifts[0].severity, "major")
            self.assertEqual(drifts[0].check, "kb_add_missing_file")

    def test_wiki_file_with_certificate_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            wiki = project / ".kiho" / "kb" / "wiki"
            wiki.mkdir(parents=True)
            (wiki / "my-slug.md").write_text(
                "# Title\ncontent\n<!-- KB_MANAGER_CERTIFICATE: ok -->\n",
                encoding="utf-8",
            )
            drifts: list[cba.Drift] = []
            cba.check_kb_add(
                _entry(1, "kb_add", payload={"entries": ["my-slug"]}), project, drifts
            )
            self.assertEqual(drifts, [])


class TestLedgerEpochAmnesty(unittest.TestCase):
    def test_pre_epoch_entries_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            state = project / ".kiho" / "state"
            state.mkdir(parents=True)
            ledger = state / "ceo-ledger.jsonl"
            _write_ledger(
                ledger,
                [
                    _entry(1, "delegate", target="kiho-researcher-x5"),  # pre-epoch drift
                    _entry(
                        2,
                        "ledger_epoch_marker",
                        payload={"epoch": "v5.22_active"},
                    ),
                    _entry(3, "delegate", target="kiho:kiho-researcher"),  # post-epoch clean
                ],
            )
            entries = list(cba.iter_ledger(ledger, None, skip_pre_epoch=True))
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["seq"], 3)

    def test_full_flag_returns_pre_epoch_too(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            state = project / ".kiho" / "state"
            state.mkdir(parents=True)
            ledger = state / "ceo-ledger.jsonl"
            _write_ledger(
                ledger,
                [
                    _entry(1, "delegate", target="kiho-researcher-x5"),
                    _entry(2, "delegate", target="kiho:kiho-researcher"),
                ],
            )
            entries = list(cba.iter_ledger(ledger, None, skip_pre_epoch=False))
            self.assertEqual(len(entries), 2)


class TestSummarize(unittest.TestCase):
    def test_clean_when_no_drifts(self) -> None:
        self.assertEqual(cba.summarize([])["status"], "clean")

    def test_severity_escalates_to_highest(self) -> None:
        drifts = [
            cba.Drift(1, "minor", "x", "a", "b"),
            cba.Drift(2, "critical", "y", "c", "d"),
            cba.Drift(3, "major", "z", "e", "f"),
        ]
        self.assertEqual(cba.summarize(drifts)["status"], "critical")


if __name__ == "__main__":
    unittest.main(verbosity=2)
