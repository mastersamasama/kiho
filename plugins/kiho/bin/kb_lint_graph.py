#!/usr/bin/env python3
"""
kb_lint_graph.py — graph.md adjacency-list parity check (v5.19.4).

Verifies that `<wiki>/graph.md` covers every page that has outgoing wikilinks.

Invariant enforced:

    SET(section headers in graph.md)
        == SET(page slugs that have at least one outgoing wikilink)

This is a SET-parity check on the set of SOURCE pages. Per-adjacency
completeness (all targets listed under each source section) is NOT verified
here — same philosophy as kb_lint_backlinks.py: that would duplicate the
kb-manager rebuild step 3. This checker catches sources added via new links
that never made it into the graph, and orphan graph sections whose page files
have been deleted.

graph.md format (per `agents/kiho-kb-manager.md` §Index rebuild protocol):

    ## source-page-slug
    - -> [[target-page-slug]]
    - -> [[other-target]]

Section headers SHOULD use the page's slug (filename without `.md`). If a wiki
adopts a different convention (e.g., full path), this checker will surface
drift because the header comparison is literal.

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


_INDEX_FILENAME = "graph.md"


def page_slug(wiki_root: Path, page_path: Path) -> str:
    """Slug = path relative to wiki_root with `.md` stripped, posix style."""
    rel = page_path.relative_to(wiki_root).with_suffix("").as_posix()
    return rel


def check_tier(wiki_root: Path) -> dict:
    """Return drift report for a single wiki tier."""
    # A page is a "source" iff its body has >= 1 wikilink. Derived indexes
    # have wikilinks as rebuild output, not as authored links — skip them all.
    sources: set[str] = set()
    total_pages = 0
    for path in sorted(wiki_root.rglob("*.md")):
        if path.name in DERIVED_INDEX_FILENAMES:
            continue
        total_pages += 1
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        body = body_after_frontmatter(text)
        if extract_wikilinks(body):
            sources.add(page_slug(wiki_root, path))

    index_path = wiki_root / _INDEX_FILENAME
    sections = parse_index_sections(index_path)
    indexed = {s for s in sections if s}

    # Exclude graph's own slug from either side.
    sources_filtered = {s for s in sources if s != "graph"}
    indexed_filtered = {s for s in indexed if s != "graph"}

    missing_from_index = sorted(sources_filtered - indexed_filtered)
    extra_in_index = sorted(indexed_filtered - sources_filtered)

    aligned = not missing_from_index and not extra_in_index
    return {
        "status": "ok" if aligned else "drift",
        "index_file": str(index_path),
        "index_file_exists": index_path.exists(),
        "source_pages_with_links": len(sources_filtered),
        "graph_sections": len(indexed_filtered),
        "total_pages_scanned": total_pages,
        "missing_from_index": missing_from_index,
        "extra_in_index": extra_in_index,
        "aligned": aligned,
    }


def main(argv: list[str]) -> int:
    return dispatch(
        argv,
        description=(
            "Verify graph.md adjacency-list parity against pages with "
            "outgoing wikilinks."
        ),
        checker=check_tier,
    )


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
