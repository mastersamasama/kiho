#!/usr/bin/env python3
"""
kb_lint_tags.py — tags.md index parity check (v5.19.4).

Verifies that `<wiki>/tags.md` matches the union of `tags:` frontmatter entries
across all wiki pages.

Invariant enforced:

    SET(section headers in tags.md) == SET(union of tags: frontmatter entries
        across <wiki>/**/*.md, excluding tags.md itself)

tags.md format (per `agents/kiho-kb-manager.md` §Index rebuild protocol):

    ## tag-name
    - [[page-slug]]
    - [[other-page]]

Per-tag membership lists are NOT verified here (that is a deeper semantic check
which would duplicate the rebuild step 3 and be redundant). This checker
verifies tag SET parity only — catches tags added to a page that never made it
into the index, and orphaned tag sections whose contributing pages have
retired. Exit-code convention per v5.15.2.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kb_lint_common import (
    DERIVED_INDEX_FILENAMES,
    dispatch,
    extract_list_field,
    parse_index_sections,
)


_INDEX_FILENAME = "tags.md"


def check_tier(wiki_root: Path) -> dict:
    """Return drift report for a single wiki tier."""
    # Skip all 12 derived indexes (not just tags.md) — their `tags:` frontmatter
    # is usually absent, but guarding here future-proofs the checker against
    # indexes that grow frontmatter fields later.
    union: set[str] = set()
    per_page: dict[str, list[str]] = {}
    for path in sorted(wiki_root.rglob("*.md")):
        if path.name in DERIVED_INDEX_FILENAMES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        entries = extract_list_field(text, "tags")
        if not entries:
            continue
        rel = path.relative_to(wiki_root).as_posix()
        per_page[rel] = entries
        union.update(entries)

    index_path = wiki_root / _INDEX_FILENAME
    sections = parse_index_sections(index_path)
    # Drop the anonymous preamble section
    index_tags = {t for t in sections if t}

    missing_from_index = sorted(union - index_tags)
    extra_in_index = sorted(index_tags - union)

    aligned = not missing_from_index and not extra_in_index
    return {
        "status": "ok" if aligned else "drift",
        "index_file": str(index_path),
        "index_file_exists": index_path.exists(),
        "frontmatter_tags_count": len(union),
        "index_tag_sections_count": len(index_tags),
        "pages_contributing": len(per_page),
        "missing_from_index": missing_from_index,
        "extra_in_index": extra_in_index,
        "aligned": aligned,
    }


def main(argv: list[str]) -> int:
    return dispatch(
        argv,
        description="Verify tags.md parity against page `tags:` frontmatter.",
        checker=check_tier,
    )


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
