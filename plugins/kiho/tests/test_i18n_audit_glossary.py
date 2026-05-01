#!/usr/bin/env python3
"""Synthetic tests for kiho v6.6.1 i18n_audit Check 6 — glossary clarity.

Stdlib-only. Run with `python plugins/kiho/tests/test_i18n_audit_glossary.py`
from the kiho-plugin repo root, OR with `python -m unittest` after adding
the `bin/` dir to sys.path (this script does that itself).

Tests:
  1. max_chars over-limit fires `clarity_max_chars` warn finding.
  2. forbidden term in locale value fires `clarity_forbidden_jargon` fail.
  3. glossary=None (file missing) is silent skip — no findings.
  4. tone block populated → no findings (v2.1 stub).
  5. End-to-end loader + checker via temp glossary file (skipped if neither
     tomllib nor tomli is installed — this is informational, not a hard fail).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Make the audit script importable without packaging it.
HERE = Path(__file__).resolve().parent
BIN_DIR = HERE.parent / "bin"
sys.path.insert(0, str(BIN_DIR))

import i18n_audit  # noqa: E402 — path injection above


def _run_check(
    locales: dict[str, dict[str, str]],
    glossary: dict | None,
    canonical: str = "en",
) -> list[i18n_audit.Finding]:
    state = i18n_audit.AuditState()
    i18n_audit.check_clarity(locales, canonical, glossary, state)
    return state.findings


class TestMaxChars(unittest.TestCase):
    def test_over_limit_fires_warn(self):
        locales = {
            "en": {"common.REVERT": "Revert"},
            "zh-TW": {"common.REVERT": "沖正修正処理"},  # 6 codepoints
        }
        glossary = {
            "max_chars": {
                "common.REVERT": {"en": 6, "zh-TW": 4},
            }
        }
        findings = _run_check(locales, glossary)
        # Expect exactly one finding for zh-TW (en value 'Revert' is len 6 == 6, OK)
        clarity = [f for f in findings if f.check == "clarity"]
        self.assertEqual(len(clarity), 1, f"expected 1 finding, got {clarity}")
        f = clarity[0]
        self.assertEqual(f.severity, "warn")
        self.assertEqual(f.locale, "zh-TW")
        self.assertEqual(f.key, "common.REVERT")
        self.assertIn("len=", f.evidence)
        self.assertIn("max_chars[zh-TW]=4", f.evidence)

    def test_at_limit_no_finding(self):
        locales = {"zh-TW": {"common.CANCEL": "取消"}}  # 2 codepoints
        glossary = {"max_chars": {"common.CANCEL": {"zh-TW": 4}}}
        self.assertEqual(_run_check(locales, glossary), [])

    def test_missing_key_silent(self):
        locales = {"zh-TW": {}}  # key absent — Check 1 covers it
        glossary = {"max_chars": {"common.REVERT": {"zh-TW": 4}}}
        self.assertEqual(_run_check(locales, glossary), [])

    def test_missing_locale_silent(self):
        locales = {"en": {"common.REVERT": "Revert"}}
        glossary = {"max_chars": {"common.REVERT": {"zh-TW": 4}}}
        self.assertEqual(_run_check(locales, glossary), [])


class TestForbidden(unittest.TestCase):
    def test_forbidden_substring_fires_fail(self):
        locales = {"zh-TW": {"common.REVERT": "沖正修正処理"}}
        glossary = {
            "forbidden": {
                "common.REVERT": {"zh-TW": ["沖正"]},
            }
        }
        findings = _run_check(locales, glossary)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.check, "clarity")
        self.assertEqual(f.severity, "fail")
        self.assertEqual(f.locale, "zh-TW")
        self.assertIn("沖正", f.evidence)

    def test_clean_value_no_finding(self):
        locales = {"zh-TW": {"common.REVERT": "撤銷"}}
        glossary = {"forbidden": {"common.REVERT": {"zh-TW": ["沖正"]}}}
        self.assertEqual(_run_check(locales, glossary), [])

    def test_multiple_forbidden_words_each_emit(self):
        locales = {"zh-TW": {"common.REVERT": "沖正修正処理"}}
        glossary = {
            "forbidden": {
                "common.REVERT": {"zh-TW": ["沖正", "修正処理"]},
            }
        }
        findings = _run_check(locales, glossary)
        self.assertEqual(len(findings), 2)
        self.assertTrue(all(f.severity == "fail" for f in findings))


class TestOptIn(unittest.TestCase):
    def test_glossary_none_silent(self):
        locales = {"zh-TW": {"common.REVERT": "沖正修正処理"}}
        self.assertEqual(_run_check(locales, None), [])

    def test_empty_glossary_silent(self):
        locales = {"zh-TW": {"common.REVERT": "沖正修正処理"}}
        self.assertEqual(_run_check(locales, {}), [])


class TestToneStub(unittest.TestCase):
    def test_tone_populated_emits_no_findings(self):
        # Reset stub-log latch so this test is order-independent.
        i18n_audit._TONE_STUB_LOGGED = True  # suppress stderr in test
        locales = {"zh-TW": {"common.REVERT": "撤銷"}}
        glossary = {"tone": {"common.REVERT": "informal"}}
        findings = _run_check(locales, glossary)
        self.assertEqual(findings, [])


class TestLoader(unittest.TestCase):
    def test_missing_file_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "does-not-exist.toml"
            self.assertIsNone(i18n_audit.load_glossary(p))

    def test_none_path_returns_none(self):
        self.assertIsNone(i18n_audit.load_glossary(None))

    def test_load_real_toml_if_available(self):
        if i18n_audit.tomllib is None:
            self.skipTest("tomllib/tomli not available on this Python")
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "i18n-glossary.toml"
            p.write_text(
                '[max_chars]\n'
                '"common.REVERT" = { "zh-TW" = 4 }\n'
                '\n'
                '[forbidden]\n'
                '"common.REVERT" = { "zh-TW" = ["沖正"] }\n',
                encoding="utf-8",
            )
            data = i18n_audit.load_glossary(p)
            self.assertIsNotNone(data)
            self.assertEqual(data["max_chars"]["common.REVERT"]["zh-TW"], 4)
            self.assertEqual(
                data["forbidden"]["common.REVERT"]["zh-TW"], ["沖正"]
            )


def run_synthetic_acceptance() -> bool:
    """The exact synthetic fixture called out in turn 6 part C task §3.

    fixture: zh-TW.json `{ "common": { "REVERT": "沖正修正処理" } }`
    glossary: max_chars."common.REVERT".zh-TW = 4
    expected: fires `clarity_max_chars` finding (check=clarity, severity=warn)
    """
    locales = {"zh-TW": {"common.REVERT": "沖正修正処理"}}
    glossary = {"max_chars": {"common.REVERT": {"zh-TW": 4}}}
    state = i18n_audit.AuditState()
    i18n_audit.check_clarity(locales, "en", glossary, state)
    if len(state.findings) != 1:
        return False
    f = state.findings[0]
    return (
        f.check == "clarity"
        and f.severity == "warn"
        and f.locale == "zh-TW"
        and f.key == "common.REVERT"
        and "len=" in f.evidence
        and "max_chars[zh-TW]=4" in f.evidence
    )


if __name__ == "__main__":
    # Run the spec-mandated acceptance check first; print a clear marker.
    ok = run_synthetic_acceptance()
    print(f"SYNTHETIC_ACCEPTANCE: {'PASS' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)
    # Then run the full unittest suite.
    unittest.main(argv=[sys.argv[0], "-v"], exit=True)
