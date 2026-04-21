#!/usr/bin/env python3
"""
kb_lint_cross_project.py — cross-project.md parity check (v5.19.4).

Company-tier only. Verifies that `$COMPANY_ROOT/company/wiki/cross-project.md`
reflects the set of pages whose `scope:` frontmatter value is `cross-project`
or whose `projects:` list contains more than one project slug.

Invariant enforced:

    SET(wikilinks in cross-project.md)
        == SET(pages in $COMPANY_ROOT/company/wiki/**/*.md that declare
               cross-project scope OR projects: [> 1 entries] frontmatter)

Frontmatter signals recognized (either-or; first match wins):

1. `scope: cross-project` — scalar field. Preferred form.
2. `projects: [a, b, ...]` — block/inline list with at least 2 entries. Legacy
   form for pages authored before the `scope:` convention landed.
3. `cross_project: true` — boolean flag. Tolerated as a third spelling.

cross-project.md format (per kb-manager rebuild protocol): a flat list of
wikilinks (no per-project sections required; this is an "all cross-project
pages" index, not a projects-to-pages map).

Project-tier invocation reports `status: skip` (cross-project.md is company
tier only). Exit-code convention per v5.15.2.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kb_lint_common import (
    DERIVED_INDEX_FILENAMES,
    dispatch,
    extract_list_field,
    extract_scalar_field,
    extract_wikilinks,
)


_INDEX_FILENAME = "cross-project.md"


def _is_cross_project(text: str) -> bool:
    """Return True iff the page declares cross-project scope via any of the
    three recognized signals."""
    scope = extract_scalar_field(text, "scope")
    if scope and scope.strip().lower() == "cross-project":
        return True
    cross = extract_scalar_field(text, "cross_project")
    if cross and cross.strip().lower() in ("true", "yes", "1"):
        return True
    projects = extract_list_field(text, "projects")
    if len(projects) >= 2:
        return True
    return False


def page_slug(wiki_root: Path, page_path: Path) -> str:
    return page_path.relative_to(wiki_root).with_suffix("").as_posix()


def check_tier(wiki_root: Path) -> dict:
    declared: set[str] = set()
    total = 0
    for path in sorted(wiki_root.rglob("*.md")):
        if path.name in DERIVED_INDEX_FILENAMES:
            continue
        total += 1
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if _is_cross_project(text):
            declared.add(page_slug(wiki_root, path))

    index_path = wiki_root / _INDEX_FILENAME
    index_refs: set[str] = set()
    if index_path.exists():
        try:
            index_refs = extract_wikilinks(index_path.read_text(encoding="utf-8"))
        except OSError:
            index_refs = set()

    # Exclude the index's own slug from either side.
    declared_filtered = {s for s in declared if s != "cross-project"}
    indexed_filtered = {s for s in index_refs if s != "cross-project"}

    missing_from_index = sorted(declared_filtered - indexed_filtered)
    extra_in_index = sorted(indexed_filtered - declared_filtered)

    aligned = not missing_from_index and not extra_in_index
    return {
        "status": "ok" if aligned else "drift",
        "index_file": str(index_path),
        "index_file_exists": index_path.exists(),
        "declared_cross_project_pages": len(declared_filtered),
        "index_entries": len(indexed_filtered),
        "pages_scanned": total,
        "missing_from_index": missing_from_index,
        "extra_in_index": extra_in_index,
        "aligned": aligned,
    }


def main(argv: list[str]) -> int:
    return dispatch(
        argv,
        description=(
            "Verify company-tier cross-project.md parity against "
            "per-page cross-project frontmatter declarations."
        ),
        checker=check_tier,
        company_only=True,
        epilog_extra="Company tier only; project tier reports status=skip.",
    )


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
