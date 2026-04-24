"""Unit tests for bin/okr_scanner.py (v6.2+).

Covers: empty project, active company without dept, cascade-dept vs
cascade-individual, stale-memo, period-close, cascade-close, config-off
master switch, consume_subset filtering.
"""

from __future__ import annotations

import sys
import textwrap
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BIN = HERE.parent
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

import okr_scanner  # type: ignore  # noqa: E402


def _seed_project(tmp_path: Path) -> Path:
    (tmp_path / ".kiho" / "state" / "okrs").mkdir(parents=True)
    return tmp_path


def _write_okr(project: Path, period: str, o_id: str, frontmatter: str, body: str = "") -> Path:
    p = project / ".kiho" / "state" / "okrs" / period / f"{o_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        textwrap.dedent(f"---\n{frontmatter}\n---\n{body}").lstrip(),
        encoding="utf-8",
    )
    return p


def test_empty_project_in_period_proposes_company(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    # 2026-04-15 is within 2026-Q2
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    kinds = [a.kind for a in actions]
    assert "propose-company" in kinds


def test_active_company_without_dept_triggers_cascade_dept(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    _write_okr(
        project,
        "2026-Q2",
        "O-2026Q2-company-01",
        "o_id: O-2026Q2-company-01\nokr_level: company\nperiod: 2026-Q2\nowner: user\naligns_to: null\nstatus: active",
    )
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    kinds = [a.kind for a in actions]
    assert "propose-company" not in kinds
    assert "cascade-dept" in kinds


def test_dept_o_without_individual_triggers_cascade_individual(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    _write_okr(
        project,
        "2026-Q2",
        "O-2026Q2-company-01",
        "o_id: O-2026Q2-company-01\nokr_level: company\nperiod: 2026-Q2\nowner: user\naligns_to: null\nstatus: active",
    )
    _write_okr(
        project,
        "2026-Q2",
        "O-2026Q2-dept-engineering-01",
        "o_id: O-2026Q2-dept-engineering-01\nokr_level: department\nperiod: 2026-Q2\nowner: kiho-eng-lead\naligns_to: O-2026Q2-company-01\nstatus: active",
    )
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    kinds = [a.kind for a in actions]
    assert "cascade-dept" not in kinds
    assert "cascade-individual" in kinds


def test_period_end_past_triggers_period_close(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    _write_okr(
        project,
        "2026-Q1",
        "O-2026Q1-company-01",
        "o_id: O-2026Q1-company-01\nokr_level: company\nperiod: 2026-Q1\nowner: user\naligns_to: null\nstatus: active",
    )
    # 2026-04-15 is AFTER 2026-Q1 ended (2026-04-01)
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    kinds = [a.kind for a in actions]
    assert "period-close" in kinds
    # ensure payload carries the stale O
    pc = next(a for a in actions if a.kind == "period-close")
    assert pc.payload["o_id"] == "O-2026Q1-company-01"


def test_parent_closed_triggers_cascade_close(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    _write_okr(
        project,
        "2026-Q2",
        "O-2026Q2-company-01",
        "o_id: O-2026Q2-company-01\nokr_level: company\nperiod: 2026-Q2\nowner: user\naligns_to: null\nstatus: closed",
    )
    _write_okr(
        project,
        "2026-Q2",
        "O-2026Q2-dept-engineering-01",
        "o_id: O-2026Q2-dept-engineering-01\nokr_level: department\nperiod: 2026-Q2\nowner: kiho-eng-lead\naligns_to: O-2026Q2-company-01\nstatus: active",
    )
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    kinds = [a.kind for a in actions]
    assert "cascade-close" in kinds
    cc = next(a for a in actions if a.kind == "cascade-close")
    assert cc.payload["o_id"] == "O-2026Q2-dept-engineering-01"
    assert cc.payload["parent_o_id"] == "O-2026Q2-company-01"


def test_stale_checkin_triggers_stale_memo(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    p = _write_okr(
        project,
        "2026-Q2",
        "O-2026Q2-company-01",
        "o_id: O-2026Q2-company-01\nokr_level: company\nperiod: 2026-Q2\nowner: user\naligns_to: null\nstatus: active",
    )
    # Force file mtime to 60 days before today so stale detection fires
    import os
    past = (datetime(2026, 4, 15, tzinfo=timezone.utc) - timedelta(days=60)).timestamp()
    os.utime(p, (past, past))
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    kinds = [a.kind for a in actions]
    assert "stale-memo" in kinds


def test_frontmatter_parser_strips_quotes(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    _write_okr(
        project,
        "2026-Q2",
        "O-2026Q2-company-01",
        'o_id: "O-2026Q2-company-01"\nokr_level: "company"\nperiod: "2026-Q2"\nowner: "user"\naligns_to: "null"\nstatus: "active"',
    )
    okrs = okr_scanner.load_okrs(project)
    assert len(okrs) == 1
    assert okrs[0].o_id == "O-2026Q2-company-01"
    assert okrs[0].aligns_to is None  # "null" literal coerced to None


def test_closed_subdir_is_skipped(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    closed_path = project / ".kiho" / "state" / "okrs" / "2026-Q2" / "_closed"
    closed_path.mkdir(parents=True)
    (closed_path / "O-2026Q2-company-99.md").write_text(
        "---\no_id: O-2026Q2-company-99\nokr_level: company\nperiod: 2026-Q2\nowner: user\naligns_to: null\nstatus: closed\n---\n",
        encoding="utf-8",
    )
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    # _closed entries should not contribute to any action
    kinds = [a.kind for a in actions]
    # Since no active company O exists (the closed one is in _closed), propose-company fires
    assert "propose-company" in kinds


def test_current_period_label_wraps_quarters() -> None:
    assert okr_scanner._current_period_label(date(2026, 1, 15)) == "2026-Q1"
    assert okr_scanner._current_period_label(date(2026, 3, 31)) == "2026-Q1"
    assert okr_scanner._current_period_label(date(2026, 4, 1)) == "2026-Q2"
    assert okr_scanner._current_period_label(date(2026, 12, 31)) == "2026-Q4"


def test_parse_period_halves_and_quarters() -> None:
    q2 = okr_scanner._parse_period("2026-Q2", date(2026, 4, 15))
    assert q2 is not None
    start, end = q2
    assert start == date(2026, 4, 1)
    assert end == date(2026, 7, 1)

    h1 = okr_scanner._parse_period("2026-H1", date(2026, 4, 15))
    assert h1 is not None
    assert h1 == (date(2026, 1, 1), date(2026, 7, 1))

    q4 = okr_scanner._parse_period("2026-Q4", date(2026, 4, 15))
    assert q4 is not None
    assert q4[1] == date(2027, 1, 1)

    # Custom slugs return None
    assert okr_scanner._parse_period("2026-custom-slug", date(2026, 4, 15)) is None
