#!/usr/bin/env python3
"""
kb_lint_by_owner.py — by-owner.md grouped parity check (v5.19.5).

Verifies that `<wiki>/by-owner.md` groups pages under one `## <author>`
section per distinct `author_agent:` frontmatter value.

Invariant enforced:

    FOR EACH author A appearing in either source or index:
        SET(pages with frontmatter "author_agent: A") ==
        SET(wikilinks under "## A" section of by-owner.md)

by-owner.md format (per `agents/kiho-kb-manager.md` §Index rebuild protocol):

    ## <author-agent-name>
    - [[page-slug]]
    - [[other-page]]

    ## <another-author>
    - ...

Pages without an `author_agent:` field are skipped (the kb-manager main lint
pass flags them separately). Exit-code convention per v5.15.2.
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


_INDEX_FILENAME = "by-owner.md"


def page_slug(wiki_root: Path, page_path: Path) -> str:
    return page_path.relative_to(wiki_root).with_suffix("").as_posix()


def check_tier(wiki_root: Path) -> dict:
    source_by_owner: dict[str, set[str]] = {}
    total_pages = 0
    owned_pages = 0
    for path in sorted(wiki_root.rglob("*.md")):
        if path.name in DERIVED_INDEX_FILENAMES:
            continue
        total_pages += 1
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        owner = extract_scalar_field(text, "author_agent")
        if not owner:
            continue
        owned_pages += 1
        source_by_owner.setdefault(owner, set()).add(page_slug(wiki_root, path))

    index_path = wiki_root / _INDEX_FILENAME
    sections = parse_index_sections(index_path)
    sections.pop("", None)
    sections.pop("by-owner", None)

    all_owners = set(source_by_owner) | set(sections)
    missing_from_index: list[str] = []
    extra_in_index: list[str] = []
    orphan_sections: list[str] = []

    for owner in sorted(all_owners):
        src = source_by_owner.get(owner, set())
        idx = sections.get(owner, set())
        if not src and idx:
            orphan_sections.append(owner)
        for slug in sorted(src - idx):
            missing_from_index.append(f"{owner}:{slug}")
        for slug in sorted(idx - src):
            extra_in_index.append(f"{owner}:{slug}")

    aligned = (
        not missing_from_index and not extra_in_index and not orphan_sections
    )
    return {
        "status": "ok" if aligned else "drift",
        "index_file": str(index_path),
        "index_file_exists": index_path.exists(),
        "total_pages_scanned": total_pages,
        "owned_pages": owned_pages,
        "distinct_owners": len(source_by_owner),
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
            "Verify by-owner.md grouped parity against page `author_agent:` "
            "frontmatter."
        ),
        checker=check_tier,
    )


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
