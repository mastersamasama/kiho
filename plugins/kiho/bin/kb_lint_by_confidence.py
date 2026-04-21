#!/usr/bin/env python3
"""
kb_lint_by_confidence.py — by-confidence.md ordered parity check (v5.19.5).

Verifies that `<wiki>/by-confidence.md` lists every page with a numeric
`confidence:` frontmatter scalar, ordered ASCENDING (lowest confidence first).

Invariant enforced:

    LIST(wikilinks in by-confidence.md, in document order) ==
    LIST(page-slugs sorted by confidence ASC, ties broken by slug ASC)

Pages missing `confidence:` or with a value outside [0.0, 1.0] are skipped.

by-confidence.md format (per `agents/kiho-kb-manager.md` §Index rebuild
protocol): flat ordered list of wikilinks (lowest-confidence first so
reviewers see the weakest claims first).

Drift modes mirror kb_lint_timeline.py: set-parity + first-misorder.
Exit-code convention per v5.15.2.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kb_lint_common import (
    DERIVED_INDEX_FILENAMES,
    dispatch,
    extract_scalar_field,
    extract_wikilinks_list,
)


_INDEX_FILENAME = "by-confidence.md"


def page_slug(wiki_root: Path, page_path: Path) -> str:
    return page_path.relative_to(wiki_root).with_suffix("").as_posix()


def _parse_conf(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        v = float(raw.strip())
    except ValueError:
        return None
    if 0.0 <= v <= 1.0:
        return v
    return None


def check_tier(wiki_root: Path) -> dict:
    entries: list[tuple[float, str]] = []
    total_pages = 0
    no_confidence = 0
    out_of_range = 0
    for path in sorted(wiki_root.rglob("*.md")):
        if path.name in DERIVED_INDEX_FILENAMES:
            continue
        total_pages += 1
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        raw = extract_scalar_field(text, "confidence")
        if raw is None:
            no_confidence += 1
            continue
        v = _parse_conf(raw)
        if v is None:
            out_of_range += 1
            continue
        entries.append((v, page_slug(wiki_root, path)))

    entries.sort(key=lambda p: (p[0], p[1]))
    expected = [slug for _, slug in entries]
    expected_set = set(expected)

    index_path = wiki_root / _INDEX_FILENAME
    actual: list[str] = []
    if index_path.exists():
        try:
            actual = extract_wikilinks_list(index_path.read_text(encoding="utf-8"))
        except OSError:
            actual = []
    actual = [s for s in actual if s != "by-confidence"]
    actual_set = set(actual)

    missing_from_index = sorted(expected_set - actual_set)
    extra_in_index = sorted(actual_set - expected_set)

    misordered: list[str] = []
    if expected_set == actual_set and expected != actual:
        for i, (e, a) in enumerate(zip(expected, actual)):
            if e != a:
                misordered.append(f"position {i}: expected {e!r}, got {a!r}")
                break

    aligned = (
        not missing_from_index and not extra_in_index and not misordered
    )
    return {
        "status": "ok" if aligned else "drift",
        "index_file": str(index_path),
        "index_file_exists": index_path.exists(),
        "total_pages_scanned": total_pages,
        "pages_without_confidence": no_confidence,
        "pages_with_out_of_range_confidence": out_of_range,
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
            "Verify by-confidence.md ordered parity against `confidence:` "
            "frontmatter across wiki pages."
        ),
        checker=check_tier,
    )


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
