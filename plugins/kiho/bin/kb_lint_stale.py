#!/usr/bin/env python3
"""
kb_lint_stale.py — stale.md content-invariant parity check (v5.19.5).

Verifies that `<wiki>/stale.md` lists every page whose frontmatter
`last_verified:` is older than 90 days.

Invariant enforced:

    SET(wikilinks in stale.md) ==
    SET(page-slugs where (today - last_verified) > threshold_days)

Pages missing `last_verified:` are skipped (the kb-manager main lint pass flags
them separately as missing-metadata).

stale.md format (per `agents/kiho-kb-manager.md` §Index rebuild protocol):
flat list of wikilinks (no per-age sections required).

Flags:
- `--threshold-days N`  override the 90-day default (useful for fixture tests)
- `--today YYYY-MM-DD`  override the current date (also for fixtures)

Exit-code convention per v5.15.2.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path

from kb_lint_common import (
    DERIVED_INDEX_FILENAMES,
    extract_scalar_field,
    extract_wikilinks,
    resolve_company_wiki,
    resolve_project_wiki,
    run_tier_check,
    safe_telemetry_record,
)


_INDEX_FILENAME = "stale.md"
_DEFAULT_THRESHOLD_DAYS = 90


def page_slug(wiki_root: Path, page_path: Path) -> str:
    return page_path.relative_to(wiki_root).with_suffix("").as_posix()


def _parse_date(raw: str | None) -> _dt.date | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            return _dt.date.fromisoformat(raw)
        raw_norm = raw.replace("Z", "+00:00")
        return _dt.datetime.fromisoformat(raw_norm).date()
    except ValueError:
        return None


def make_checker(today: _dt.date, threshold_days: int):
    def check_tier(wiki_root: Path) -> dict:
        expected: set[str] = set()
        total_pages = 0
        undeclared = 0
        for path in sorted(wiki_root.rglob("*.md")):
            if path.name in DERIVED_INDEX_FILENAMES:
                continue
            total_pages += 1
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            raw = extract_scalar_field(text, "last_verified")
            d = _parse_date(raw)
            if d is None:
                undeclared += 1
                continue
            if (today - d).days > threshold_days:
                expected.add(page_slug(wiki_root, path))

        index_path = wiki_root / _INDEX_FILENAME
        indexed: set[str] = set()
        if index_path.exists():
            try:
                indexed = extract_wikilinks(index_path.read_text(encoding="utf-8"))
            except OSError:
                indexed = set()
        # Exclude self-reference
        indexed = {s for s in indexed if s != "stale"}

        missing_from_index = sorted(expected - indexed)
        extra_in_index = sorted(indexed - expected)

        aligned = not missing_from_index and not extra_in_index
        return {
            "status": "ok" if aligned else "drift",
            "index_file": str(index_path),
            "index_file_exists": index_path.exists(),
            "total_pages_scanned": total_pages,
            "pages_without_last_verified": undeclared,
            "expected_stale_count": len(expected),
            "index_entries": len(indexed),
            "threshold_days": threshold_days,
            "today": today.isoformat(),
            "missing_from_index": missing_from_index,
            "extra_in_index": extra_in_index,
            "aligned": aligned,
        }

    return check_tier


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify stale.md parity against pages with "
            "last_verified older than threshold (default 90d)."
        ),
        epilog="Exit codes: 0 aligned/no-wiki, 1 drift, 2 usage, 3 internal.",
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--company-root", default=os.environ.get("COMPANY_ROOT", "")
    )
    parser.add_argument(
        "--tier", choices=["project", "company", "both"], default="both"
    )
    parser.add_argument(
        "--threshold-days", type=int, default=_DEFAULT_THRESHOLD_DAYS
    )
    parser.add_argument(
        "--today",
        default="",
        help="Override current date (YYYY-MM-DD); default: UTC today.",
    )
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    today: _dt.date
    if args.today:
        parsed = _parse_date(args.today)
        if parsed is None:
            print(
                json.dumps({"status": "error", "error": f"bad --today {args.today!r}"}),
                file=sys.stderr,
            )
            return 2
        today = parsed
    else:
        today = _dt.datetime.now(_dt.timezone.utc).date()

    checker = make_checker(today, args.threshold_days)
    project_path = Path(args.project_root)
    if args.tier in ("project", "both") and (
        not project_path.exists() or not project_path.is_dir()
    ):
        print(
            json.dumps({"status": "error", "error": f"--project-root {args.project_root!r} invalid"}),
            file=sys.stderr,
        )
        return 2

    report: dict = {"status": "ok", "tiers": []}
    drift_seen = False
    _t0 = time.perf_counter()

    try:
        if args.tier in ("project", "both"):
            r = run_tier_check("project", resolve_project_wiki(args.project_root), checker)
            report["tiers"].append(r)
            if r.get("status") == "drift":
                drift_seen = True
        if args.tier in ("company", "both"):
            if not args.company_root:
                report["tiers"].append({
                    "tier": "company",
                    "status": "skip",
                    "detail": "--company-root not set and $COMPANY_ROOT empty",
                })
            else:
                r = run_tier_check("company", resolve_company_wiki(args.company_root), checker)
                report["tiers"].append(r)
                if r.get("status") == "drift":
                    drift_seen = True
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr)
        return 3

    if drift_seen:
        report["status"] = "drift"

    _duration_ms = int((time.perf_counter() - _t0) * 1000)
    _ran_any = any(
        t.get("status") in ("ok", "drift") for t in report["tiers"]
    )
    if _ran_any:
        drift_count = sum(
            len(t.get("missing_from_index", []) or [])
            + len(t.get("extra_in_index", []) or [])
            for t in report["tiers"]
        )
        safe_telemetry_record(
            op="kb_lint",
            key="kb_lint_stale",
            duration_ms=_duration_ms,
            plugin_root=Path(__file__).resolve().parents[1],
            extra={
                "tier": args.tier,
                "aligned": not drift_seen,
                "drift_count": drift_count,
                "threshold_days": args.threshold_days,
                "tiers_ran": sum(
                    1 for t in report["tiers"]
                    if t.get("status") in ("ok", "drift")
                ),
            },
        )

    print(json.dumps(report, indent=2))
    return 1 if drift_seen else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
