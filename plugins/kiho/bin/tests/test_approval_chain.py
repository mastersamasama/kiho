"""Unit tests for bin/approval_chain.py (v5.23+).

Covers: schema load, schema violations, certificate-marker listing,
path→chain lookup, and verify_ran correctness for both complete and
missing-stage ledger windows.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BIN = HERE.parent
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

import approval_chain  # type: ignore  # noqa: E402


def _write_registry(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "approval-chains.toml"
    p.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return p


def test_load_minimal_valid_registry(tmp_path: Path) -> None:
    reg = _write_registry(
        tmp_path,
        """\
        schema_version = "1.0"

        [[chain]]
        id = "test-chain"
        certificate_marker = "TEST_CERT:"
        terminal_path_pattern = '.*[/\\\\]test\\.md$'
        description = "test"
        governing_skill = "kiho:test"

          [[chain.stages]]
          stage_id = "only-stage"
          approver_role = "tester"
          on_deny = "abort"
        """,
    )
    chains = approval_chain.load_registry(reg)
    assert len(chains) == 1
    assert chains[0].id == "test-chain"
    assert chains[0].certificate_marker == "TEST_CERT:"
    assert len(chains[0].stages) == 1
    assert chains[0].stages[0].stage_id == "only-stage"


def test_load_rejects_missing_required_field(tmp_path: Path) -> None:
    reg = _write_registry(
        tmp_path,
        """\
        schema_version = "1.0"

        [[chain]]
        id = "broken"
        certificate_marker = "X:"
        # terminal_path_pattern missing
        description = "no"
        governing_skill = "kiho:x"

          [[chain.stages]]
          stage_id = "a"
          approver_role = "b"
          on_deny = "abort"
        """,
    )
    with pytest.raises(ValueError, match="missing fields"):
        approval_chain.load_registry(reg)


def test_load_rejects_bad_on_deny(tmp_path: Path) -> None:
    reg = _write_registry(
        tmp_path,
        """\
        schema_version = "1.0"

        [[chain]]
        id = "x"
        certificate_marker = "X:"
        terminal_path_pattern = 'x'
        description = "x"
        governing_skill = "kiho:x"

          [[chain.stages]]
          stage_id = "a"
          approver_role = "b"
          on_deny = "teleport-to-moon"
        """,
    )
    with pytest.raises(ValueError, match="bad on_deny"):
        approval_chain.load_registry(reg)


def test_load_rejects_duplicate_marker(tmp_path: Path) -> None:
    reg = _write_registry(
        tmp_path,
        """\
        schema_version = "1.0"

        [[chain]]
        id = "a"
        certificate_marker = "DUP:"
        terminal_path_pattern = 'a'
        description = "a"
        governing_skill = "kiho:a"

          [[chain.stages]]
          stage_id = "s"
          approver_role = "r"
          on_deny = "abort"

        [[chain]]
        id = "b"
        certificate_marker = "DUP:"
        terminal_path_pattern = 'b'
        description = "b"
        governing_skill = "kiho:b"

          [[chain.stages]]
          stage_id = "s"
          approver_role = "r"
          on_deny = "abort"
        """,
    )
    with pytest.raises(ValueError, match="duplicate certificate_marker"):
        approval_chain.load_registry(reg)


def test_list_certificate_markers_from_production_registry() -> None:
    markers = approval_chain.list_certificate_markers()
    assert "RECRUIT_CERTIFICATE:" in markers
    assert "KB_MANAGER_CERTIFICATE:" in markers
    assert "DEPT_LEAD_OKR_CERTIFICATE:" in markers


def test_get_chain_for_path_recruit() -> None:
    match = approval_chain.get_chain_for_path(
        "D:/Tools/kiho/agents/test-agent/agent.md"
    )
    assert match is not None
    assert match.id == "recruit-hiring"


def test_get_chain_for_path_kb_wiki() -> None:
    match = approval_chain.get_chain_for_path(
        "/project/.kiho/kb/wiki/concepts/foo.md"
    )
    assert match is not None
    assert match.id == "kb-writes"


def test_get_chain_for_path_okr_individual() -> None:
    match = approval_chain.get_chain_for_path(
        "/project/.kiho/state/okrs/2026-Q2/O-2026Q2-individual-eng-lead-01.md"
    )
    assert match is not None
    assert match.id == "okr-individual"


def test_get_chain_for_path_no_match() -> None:
    assert approval_chain.get_chain_for_path("/project/src/main.py") is None


def test_verify_ran_all_stages_present() -> None:
    entries = [
        {
            "action": "approval_stage_granted",
            "payload": {"chain_id": "recruit-hiring", "stage_id": sid},
        }
        for sid in [
            "role-spec",
            "interview-simulate",
            "hiring-committee",
            "ceo-ratify",
            "user-accept",
        ]
    ]
    ok, missing = approval_chain.verify_ran("recruit-hiring", entries)
    assert ok is True
    assert missing == []


def test_verify_ran_missing_stage() -> None:
    entries = [
        {
            "action": "approval_stage_granted",
            "payload": {"chain_id": "recruit-hiring", "stage_id": "role-spec"},
        },
        # 4 stages missing
    ]
    ok, missing = approval_chain.verify_ran("recruit-hiring", entries)
    assert ok is False
    assert set(missing) == {
        "interview-simulate",
        "hiring-committee",
        "ceo-ratify",
        "user-accept",
    }


def test_verify_ran_unknown_chain() -> None:
    ok, reason = approval_chain.verify_ran("does-not-exist", [])
    assert ok is False
    assert reason == ["unknown chain: does-not-exist"]


def test_verify_ran_ignores_other_chains() -> None:
    entries = [
        {
            "action": "approval_stage_granted",
            "payload": {"chain_id": "kb-writes", "stage_id": "kb-manager-emit"},
        },
        {
            "action": "approval_stage_granted",
            "payload": {"chain_id": "recruit-hiring", "stage_id": "role-spec"},
        },
    ]
    ok, missing = approval_chain.verify_ran("kb-writes", entries)
    # kb-writes has one stage "kb-manager-emit" — present
    assert ok is True
    assert missing == []
    # recruit-hiring has 5 stages, only 1 matches
    ok2, missing2 = approval_chain.verify_ran("recruit-hiring", entries)
    assert ok2 is False
    assert len(missing2) == 4
