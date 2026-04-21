#!/usr/bin/env python3
"""
kb_lint_backlinks.py — backlinks.md index parity check (v5.19.4).

Verifies that `<wiki>/backlinks.md` reflects the reverse-link map computed from
wikilinks across all wiki pages.

Invariant enforced:

    SET(section headers in backlinks.md)
        == SET(link targets that appear in at least one page body)

This is a SET-parity check on the set of link targets. The per-target linker
list is NOT verified (that is a deeper semantic check redundant with the
kb-manager rebuild step 3). Catches targets added via new links that never made
it into the index, and orphan backlinks sections whose sources have retired.

backlinks.md format (per `agents/kiho-kb-manager.md` §Index rebuild protocol):

    ## target-page-slug
    - [[linker-page]]
    - [[other-linker]]

Exit-code convention per v5.15.2.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kb_lint_common import (
    DERIVED_INDEX_FILENAMES,
    body_after_frontmatter,
    dispatch,
    extract_wikilinks,
    parse_index_sections,
)


_INDEX_FILENAME = "backlinks.md"


def check_tier(wiki_root: Path) -> dict:
    """Return drift report for a single wiki tier."""
    # Collect the set of all link targets across authored pages only. The 12
    # derived indexes (tags.md, graph.md, etc.) contain wikilinks as part of
    # their rebuild output, not as authored backlinks — skip them all.
    targets: set[str] = set()
    source_count = 0
    for path in sorted(wiki_root.rglob("*.md")):
        if path.name in DERIVED_INDEX_FILENAMES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        body = body_after_frontmatter(text)
        page_targets = extract_wikilinks(body)
        if page_targets:
            source_count += 1
            targets.update(page_targets)

    index_path = wiki_root / _INDEX_FILENAME
    sections = parse_index_sections(index_path)
    indexed = {t for t in sections if t}

    # Backlinks.md section headers should correspond to link TARGETS. Exclude
    # targets that are clearly not page wikilinks: those containing `/` are
    # path-style (like `[[concepts/concept-x]]`) and are legitimate cross-KB
    # references; we keep them. But we exclude the index's own slug.
    targets_filtered = {t for t in targets if t != "backlinks"}
    indexed_filtered = {t for t in indexed if t != "backlinks"}

    missing_from_index = sorted(targets_filtered - indexed_filtered)
    extra_in_index = sorted(indexed_filtered - targets_filtered)

    aligned = not missing_from_index and not extra_in_index
    return {
        "status": "ok" if aligned else "drift",
        "index_file": str(index_path),
        "index_file_exists": index_path.exists(),
        "link_targets_found": len(targets_filtered),
        "indexed_targets": len(indexed_filtered),
        "pages_with_links": source_count,
        "missing_from_index": missing_from_index,
        "extra_in_index": extra_in_index,
        "aligned": aligned,
    }


def main(argv: list[str]) -> int:
    return dispatch(
        argv,
        description="Verify backlinks.md parity against wikilink reverse-map.",
        checker=check_tier,
    )


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
