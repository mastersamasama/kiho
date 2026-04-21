#!/usr/bin/env python3
"""
kb_lint_open_questions.py — open-questions.md parity check (v5.19.5).

Verifies that `<wiki>/open-questions.md` lists every page under
`<wiki>/questions/` whose frontmatter `status:` is `open`.

Invariant enforced:

    SET(wikilinks in open-questions.md) ==
    SET(slugs of <wiki>/questions/**/*.md pages with frontmatter status: open)

open-questions.md format (per `agents/kiho-kb-manager.md` §Index rebuild
protocol): flat list of wikilinks. Only the questions/ subdirectory is scanned
because kb-manager's open-question contract is scoped to that directory; other
subdirectories may use `status:` for unrelated state.

Exit-code convention per v5.15.2.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kb_lint_common import (
    DERIVED_INDEX_FILENAMES,
    dispatch,
    extract_scalar_field,
    extract_wikilinks,
)


_INDEX_FILENAME = "open-questions.md"
_QUESTIONS_SUBDIR = "questions"


def page_slug(wiki_root: Path, page_path: Path) -> str:
    return page_path.relative_to(wiki_root).with_suffix("").as_posix()


def check_tier(wiki_root: Path) -> dict:
    questions_dir = wiki_root / _QUESTIONS_SUBDIR
    expected: set[str] = set()
    total_questions = 0
    if questions_dir.exists() and questions_dir.is_dir():
        for path in sorted(questions_dir.rglob("*.md")):
            if path.name in DERIVED_INDEX_FILENAMES:
                continue
            total_questions += 1
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            status = extract_scalar_field(text, "status")
            if status and status.strip().lower() == "open":
                expected.add(page_slug(wiki_root, path))

    index_path = wiki_root / _INDEX_FILENAME
    indexed: set[str] = set()
    if index_path.exists():
        try:
            indexed = extract_wikilinks(index_path.read_text(encoding="utf-8"))
        except OSError:
            indexed = set()
    indexed = {s for s in indexed if s != "open-questions"}

    missing_from_index = sorted(expected - indexed)
    extra_in_index = sorted(indexed - expected)

    aligned = not missing_from_index and not extra_in_index
    return {
        "status": "ok" if aligned else "drift",
        "index_file": str(index_path),
        "index_file_exists": index_path.exists(),
        "questions_dir": str(questions_dir),
        "questions_dir_exists": questions_dir.exists(),
        "total_questions_scanned": total_questions,
        "expected_open_count": len(expected),
        "index_entries": len(indexed),
        "missing_from_index": missing_from_index,
        "extra_in_index": extra_in_index,
        "aligned": aligned,
    }


def main(argv: list[str]) -> int:
    return dispatch(
        argv,
        description=(
            "Verify open-questions.md parity against pages in wiki/questions/ "
            "with `status: open` frontmatter."
        ),
        checker=check_tier,
    )


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
