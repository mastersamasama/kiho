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


def _write_ledger(project: Path, entries: list[dict]) -> None:
    ledger = project / ".kiho" / "state" / "ceo-ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    import json as _json
    ledger.write_text(
        "\n".join(_json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )


def test_onboard_dispatch_fires_when_fires_at_passed(tmp_path: Path) -> None:
    """v6.2.1+ gap C fix: scheduled onboard ledger entry → onboard-dispatch action."""
    project = _seed_project(tmp_path)
    _write_ledger(project, [
        {"ts": "2026-03-15T10:00:00Z",
         "action": "okr_individual_schedule_onboard",
         "payload": {"agent": "new-engineer", "scheduled_at": "2026-03-15T10:00:00Z",
                     "fires_at": "2026-04-14T10:00:00Z"}},
    ])
    # today 2026-04-15 > fires_at 2026-04-14 → should emit onboard-dispatch
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    kinds = [a.kind for a in actions]
    assert "onboard-dispatch" in kinds
    dispatch = next(a for a in actions if a.kind == "onboard-dispatch")
    assert dispatch.payload["agent"] == "new-engineer"


def test_onboard_dispatch_suppressed_if_already_spawned(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    _write_ledger(project, [
        {"ts": "2026-03-15T10:00:00Z",
         "action": "okr_individual_schedule_onboard",
         "payload": {"agent": "eng-a", "scheduled_at": "2026-03-15T10:00:00Z",
                     "fires_at": "2026-04-14T10:00:00Z"}},
        {"ts": "2026-04-14T12:00:00Z",
         "action": "okr_dispatch_spawn",
         "payload": {"agent": "eng-a"}},
    ])
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    kinds = [a.kind for a in actions]
    assert "onboard-dispatch" not in kinds


def test_onboard_dispatch_suppressed_if_cancelled(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    _write_ledger(project, [
        {"ts": "2026-03-15T10:00:00Z",
         "action": "okr_individual_schedule_onboard",
         "payload": {"agent": "eng-b", "scheduled_at": "2026-03-15T10:00:00Z",
                     "fires_at": "2026-04-14T10:00:00Z"}},
        {"ts": "2026-04-13T12:00:00Z",
         "action": "okr_individual_schedule_cancelled",
         "payload": {"agent": "eng-b"}},
    ])
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    assert "onboard-dispatch" not in [a.kind for a in actions]


def test_onboard_dispatch_not_fired_before_fires_at(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    _write_ledger(project, [
        {"ts": "2026-03-15T10:00:00Z",
         "action": "okr_individual_schedule_onboard",
         "payload": {"agent": "eng-c", "scheduled_at": "2026-03-15T10:00:00Z",
                     "fires_at": "2026-05-01T10:00:00Z"}},
    ])
    # today 2026-04-15 < fires_at 2026-05-01
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    assert "onboard-dispatch" not in [a.kind for a in actions]


def test_settings_md_okr_block_overrides_plugin_default(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """v6.2.1+ gap G fix: $COMPANY_ROOT/settings.md [okr] block layered into cfg."""
    company_root = tmp_path / "company-root"
    company_root.mkdir()
    (company_root / "settings.md").write_text(
        "# settings\n\n[okr]\nauto_trigger_enabled = false\nstale_days = 7\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("COMPANY_ROOT", str(company_root))

    project = _seed_project(tmp_path)
    # Even though in-period with no company O, master switch OFF = zero actions
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    assert actions == []


def test_company_tier_okr_suppresses_project_propose_company(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """v6.2.1+ gap E fix: company-tier OKR in COMPANY_ROOT = scanner sees it."""
    company_root = tmp_path / "company-root"
    company_dir = company_root / "company" / "state" / "okrs" / "2026-Q2"
    company_dir.mkdir(parents=True)
    (company_dir / "O-2026Q2-company-01.md").write_text(
        "---\no_id: O-2026Q2-company-01\nokr_level: company\nperiod: 2026-Q2\n"
        "owner: user\naligns_to: null\nstatus: active\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("COMPANY_ROOT", str(company_root))

    project = _seed_project(tmp_path)  # project has no OKRs
    actions = okr_scanner.scan(project, today=date(2026, 4, 15))
    kinds = [a.kind for a in actions]
    # Company-tier company-O exists → no propose-company
    assert "propose-company" not in kinds
    # But it should trigger cascade-dept (company O has no aligned dept O)
    assert "cascade-dept" in kinds


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
