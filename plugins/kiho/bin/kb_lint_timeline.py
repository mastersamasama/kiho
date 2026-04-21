#!/usr/bin/env python3
"""
kb_lint_timeline.py — timeline.md ordered parity check (v5.19.5).

Verifies that `<wiki>/timeline.md` lists every page as a wikilink, ordered by
frontmatter `updated_at:` descending.

Invariant enforced:

    LIST(wikilinks in timeline.md, in document order) ==
    LIST(page-slugs sorted by updated_at DESC, ties broken by slug ASC)

Pages missing `updated_at:` fall back to filesystem mtime with a note in the
JSON report (`mtime_fallback_count`). The mtime fallback is advisory — the
kb-manager rebuild step normally supplies `updated_at:` in frontmatter.

timeline.md format (per `agents/kiho-kb-manager.md` §Index rebuild protocol):
flat ordered list of wikilinks (no per-date sections required).

Drift modes reported separately:
- `missing_from_index` — slug present in source but not in timeline.md
- `extra_in_index`     — slug in timeline.md but source page does not exist
- `misordered`         — sets match, but positions differ from expected order

Exit-code convention per v5.15.2.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from kb_lint_common import (
    DERIVED_INDEX_FILENAMES,
    dispatch,
    extract_scalar_field,
    extract_wikilinks_list,
)


_INDEX_FILENAME = "timeline.md"


def page_slug(wiki_root: Path, page_path: Path) -> str:
    return page_path.relative_to(wiki_root).with_suffix("").as_posix()


def _parse_dt(raw: str | None) -> _dt.datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    # Accept "YYYY-MM-DD" or ISO-8601 with time and optional tz
    try:
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            return _dt.datetime.fromisoformat(raw + "T00:00:00+00:00")
        # fromisoformat in py3.11+ handles Z; older needs replacement
        raw_norm = raw.replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(raw_norm)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return dt
    except ValueError:
        return None


def check_tier(wiki_root: Path) -> dict:
    entries: list[tuple[_dt.datetime, str]] = []
    mtime_fallback_count = 0
    total_pages = 0
    for path in sorted(wiki_root.rglob("*.md")):
        if path.name in DERIVED_INDEX_FILENAMES:
            continue
        total_pages += 1
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        raw = extract_scalar_field(text, "updated_at")
        dt = _parse_dt(raw)
        if dt is None:
            try:
                dt = _dt.datetime.fromtimestamp(
                    path.stat().st_mtime, tz=_dt.timezone.utc
                )
                mtime_fallback_count += 1
            except OSError:
                continue
        entries.append((dt, page_slug(wiki_root, path)))

    # Expected order: updated_at DESC, then slug ASC for ties
    entries.sort(key=lambda p: (-p[0].timestamp(), p[1]))
    expected = [slug for _, slug in entries]
    expected_set = set(expected)

    index_path = wiki_root / _INDEX_FILENAME
    actual: list[str] = []
    if index_path.exists():
        try:
            actual = extract_wikilinks_list(index_path.read_text(encoding="utf-8"))
        except OSError:
            actual = []
    # Exclude self-references
    actual = [s for s in actual if s != "timeline"]
    actual_set = set(actual)

    missing_from_index = sorted(expected_set - actual_set)
    extra_in_index = sorted(actual_set - expected_set)

    # Order check: only meaningful if set matches
    misordered: list[str] = []
    if expected_set == actual_set and expected != actual:
        # Find first diverging index for a compact signal
        for i, (e, a) in enumerate(zip(expected, actual)):
            if e != a:
                misordered.append(
                    f"position {i}: expected {e!r}, got {a!r}"
                )
                break

    aligned = (
        not missing_from_index and not extra_in_index and not misordered
    )
    return {
        "status": "ok" if aligned else "drift",
        "index_file": str(index_path),
        "index_file_exists": index_path.exists(),
        "total_pages_scanned": total_pages,
        "mtime_fallback_count": mtime_fallback_count,
        "expected_entries": len(expected),
        "index_entries": len(actual),
        "missing_from_index": missing_from_index,
        "extra_in_index": extra_in_index,
        "misordered": misordered,
        "aligned": aligned,
    }


def main(argv: list[str]) -> int:
    return dispatch(
        argv,
        description=(
            "Verify timeline.md ordered parity against `updated_at:` "
            "frontmatter across wiki pages."
        ),
        checker=check_tier,
    )


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
