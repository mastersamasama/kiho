#!/usr/bin/env python3
"""
kb_lint_index.py — index.md per-type parity check (v5.19.5).

Verifies that `<wiki>/index.md` groups every page by its frontmatter `type:`
scalar into one `## <type>` section.

Invariant enforced:

    FOR EACH type T appearing in either source or index:
        SET(pages with frontmatter "type: T") ==
        SET(wikilinks under "## T" section of index.md)

index.md format (per `agents/kiho-kb-manager.md` §Index rebuild protocol):

    ## <type-name>
    - [[page-slug]]
    - [[other-page]]

    ## <other-type-name>
    - ...

Pages without a `type:` frontmatter field are not the responsibility of this
checker (the kb-manager lint pass flags them separately as missing-metadata).
Exit-code convention per v5.15.2.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kb_lint_common import (
    DERIVED_INDEX_FILENAMES,
    dispatch,
    extract_scalar_field,
    parse_index_sections,
)


_INDEX_FILENAME = "index.md"


def page_slug(wiki_root: Path, page_path: Path) -> str:
    return page_path.relative_to(wiki_root).with_suffix("").as_posix()


def check_tier(wiki_root: Path) -> dict:
    source_by_type: dict[str, set[str]] = {}
    total_pages = 0
    typed_pages = 0
    for path in sorted(wiki_root.rglob("*.md")):
        if path.name in DERIVED_INDEX_FILENAMES:
            continue
        total_pages += 1
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        t = extract_scalar_field(text, "type")
        if not t:
            continue
        typed_pages += 1
        source_by_type.setdefault(t, set()).add(page_slug(wiki_root, path))

    index_path = wiki_root / _INDEX_FILENAME
    sections = parse_index_sections(index_path)
    # Drop the preamble sentinel; drop "index" self-section if the rebuild
    # happened to include one.
    sections.pop("", None)
    sections.pop("index", None)

    # Per-type set diff
    all_types = set(source_by_type) | set(sections)
    missing_from_index: list[str] = []
    extra_in_index: list[str] = []
    orphan_sections: list[str] = []

    for t in sorted(all_types):
        src = source_by_type.get(t, set())
        idx = sections.get(t, set())
        if not src and idx:
            orphan_sections.append(t)
        for slug in sorted(src - idx):
            missing_from_index.append(f"{t}:{slug}")
        for slug in sorted(idx - src):
            extra_in_index.append(f"{t}:{slug}")

    aligned = (
        not missing_from_index and not extra_in_index and not orphan_sections
    )
    return {
        "status": "ok" if aligned else "drift",
        "index_file": str(index_path),
        "index_file_exists": index_path.exists(),
        "total_pages_scanned": total_pages,
        "typed_pages": typed_pages,
        "distinct_types": len(source_by_type),
        "index_sections": len(sections),
        "missing_from_index": missing_from_index,
        "extra_in_index": extra_in_index,
        "orphan_sections": orphan_sections,
        "aligned": aligned,
    }


def main(argv: list[str]) -> int:
    return dispatch(
        argv,
        description=(
            "Verify index.md per-type parity against page `type:` frontmatter."
        ),
        checker=check_tier,
    )


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
