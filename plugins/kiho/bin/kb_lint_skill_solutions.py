#!/usr/bin/env python3
"""
kb_lint_skill_solutions.py — skill-solutions index parity check (v5.19 pre-work).

Verifies that `<wiki>/skill-solutions.md` matches the union of `skill_solutions:`
frontmatter lists across all wiki pages. Runs on project tier (default) and/or
company tier (when $COMPANY_ROOT or --company-root is set).

The invariant enforced:

    SET(wikilinks in skill-solutions.md) == SET(union of skill_solutions:
        frontmatter entries across <wiki>/**/*.md, excluding the index itself)

Per `agents/kiho-kb-manager.md` lines 140-157, kb-manager rebuilds 12 derived
indexes after every wiki write, including `skill-solutions.md`. This script is
the deterministic post-hook parity check that verifies the rebuild happened
and stayed correct. The script NEVER rewrites — it only reports drift.

When to run:
    * after kb-manager op=add / op=update returns status:ok
    * periodically (weekly) as part of the catalog-walk audit
    * ad-hoc when a stale-reference warning fires elsewhere

Usage:
    kb_lint_skill_solutions.py
        [--project-root .]
        [--company-root $COMPANY_ROOT]
        [--tier project|company|both]

Exit codes:
    0 — parity verified for every checked tier, or wiki not present (advisory)
    1 — drift detected on at least one tier (policy violation)
    2 — usage error (bad --tier, unreadable --project-root)
    3 — internal error (unexpected exception; report as kiho bug)

Grounding:
    * agents/kiho-kb-manager.md § "Post-write index rebuild protocol"
    * references/storage-architecture.md §T2-MUST-1 (regenerability invariant)
    * references/skill-authoring-standards.md § v5.15.2 (0/1/2/3 exit-code rule)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


# --- frontmatter extraction (approximate, stdlib-only) ----------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SKILL_SOL_INLINE_RE = re.compile(
    r"^\s*skill_solutions\s*:\s*\[(.*?)\]\s*$", re.MULTILINE
)
_SKILL_SOL_BLOCK_RE = re.compile(
    r"^\s*skill_solutions\s*:\s*\n((?:[ \t]*-[ \t]+.+\n)+)", re.MULTILINE
)
_LIST_ITEM_RE = re.compile(r"^[ \t]*-[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|[^\]]*)?\]\]")


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def extract_skill_solutions_from_frontmatter(text: str) -> list[str]:
    """Return the skill_solutions list from a markdown file's frontmatter.

    Tolerates inline-array form (`skill_solutions: [a, b]`) and block-list form.
    Returns an empty list when no frontmatter, no field, or an empty field.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return []
    block = m.group(1)

    inline = _SKILL_SOL_INLINE_RE.search(block)
    if inline:
        raw = inline.group(1)
        return [_strip_quotes(s) for s in raw.split(",") if s.strip()]

    blk = _SKILL_SOL_BLOCK_RE.search(block + "\n")
    if blk:
        return [
            _strip_quotes(m2.group(1))
            for m2 in _LIST_ITEM_RE.finditer(blk.group(1))
        ]

    return []


def collect_frontmatter_union(wiki_root: Path) -> tuple[set[str], dict[str, list[str]]]:
    """Walk wiki_root/**/*.md, union all skill_solutions: frontmatter lists.

    Skips skill-solutions.md itself (the derived index).

    Returns:
        (union_set, per_page_map) — per_page_map keys are posix-style
        paths relative to wiki_root.
    """
    union: set[str] = set()
    per_page: dict[str, list[str]] = {}
    for path in sorted(wiki_root.rglob("*.md")):
        if path.name == "skill-solutions.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        entries = extract_skill_solutions_from_frontmatter(text)
        if not entries:
            continue
        rel = path.relative_to(wiki_root).as_posix()
        per_page[rel] = entries
        union.update(entries)
    return union, per_page


def extract_index_wikilinks(index_path: Path) -> set[str]:
    """Return the set of wikilink targets appearing in skill-solutions.md.

    Uses the `[[slug]]` and `[[slug|label]]` forms per the Karpathy wiki
    protocol. Returns an empty set if the index file does not exist (a
    separate tier-level `wiki_exists: False` handles that case upstream).
    """
    if not index_path.exists():
        return set()
    try:
        text = index_path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {m.group(1).strip() for m in _WIKILINK_RE.finditer(text)}


# --- per-tier check ---------------------------------------------------------

def check_tier(tier_name: str, wiki_root: Path) -> dict:
    """Parity check a single wiki tier. Never raises on a missing wiki."""
    result: dict = {
        "tier": tier_name,
        "wiki_root": str(wiki_root),
        "wiki_exists": wiki_root.exists(),
    }
    if not wiki_root.exists():
        result["status"] = "no_wiki"
        result["detail"] = f"{wiki_root} does not exist; skipping (advisory)"
        return result

    index_path = wiki_root / "skill-solutions.md"
    union, per_page = collect_frontmatter_union(wiki_root)
    index_refs = extract_index_wikilinks(index_path)

    # Drift is asymmetric. A skill in frontmatter but not in the index is a
    # missing rebuild. A token in the index but not in any frontmatter is an
    # orphan reference. skill-solutions.md contains two kinds of wikilinks:
    # skill slugs (which we care about) and KB page wikilinks like
    # [[concepts/concept-x]] that map the index entries (legitimate). Filter
    # out path-style wikilinks (contain "/") and the index's own slug.
    # Remaining orphans are suspected skill references that don't exist.
    missing_from_index = sorted(union - index_refs)
    candidate_extras = {
        x for x in (index_refs - union)
        if "/" not in x and x != "skill-solutions"
    }
    extra_in_index = sorted(candidate_extras)

    result["index_file"] = str(index_path)
    result["index_file_exists"] = index_path.exists()
    result["frontmatter_refs_count"] = len(union)
    result["index_refs_count"] = len(index_refs)
    result["pages_contributing"] = len(per_page)
    result["missing_from_index"] = missing_from_index
    result["extra_in_index"] = extra_in_index
    result["aligned"] = not missing_from_index and not extra_in_index
    result["status"] = "ok" if result["aligned"] else "drift"
    return result


# --- CLI --------------------------------------------------------------------

def _resolve_project_wiki(project_root: str) -> Path:
    return Path(project_root).resolve() / ".kiho" / "kb" / "wiki"


def _resolve_company_wiki(company_root: str) -> Path:
    return Path(company_root).resolve() / "company" / "wiki"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Verify skill-solutions.md parity against page frontmatter.",
        epilog=(
            "Exit codes: 0 aligned/no-wiki, 1 drift, 2 usage, 3 internal. "
            "See module docstring for grounding."
        ),
    )
    p.add_argument(
        "--project-root",
        default=".",
        help="Project root; wiki at <project-root>/.kiho/kb/wiki/ (default: .)",
    )
    p.add_argument(
        "--company-root",
        default=os.environ.get("COMPANY_ROOT", ""),
        help="Company root; wiki at <company-root>/company/wiki/. "
        "Default: $COMPANY_ROOT env var.",
    )
    p.add_argument(
        "--tier",
        choices=["project", "company", "both"],
        default="both",
        help="Which tier(s) to check (default: both).",
    )
    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        # argparse exits 2 on bad args; surface that as our convention-2.
        return int(e.code) if e.code is not None else 2

    # Validate project-root readability up front.
    project_path = Path(args.project_root)
    if args.tier in ("project", "both"):
        if not project_path.exists() or not project_path.is_dir():
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error": f"--project-root {args.project_root!r} "
                        f"is not a directory",
                    }
                ),
                file=sys.stderr,
            )
            return 2

    report: dict = {"status": "ok", "tiers": []}
    drift_seen = False

    try:
        if args.tier in ("project", "both"):
            r = check_tier("project", _resolve_project_wiki(args.project_root))
            report["tiers"].append(r)
            if r["status"] == "drift":
                drift_seen = True

        if args.tier in ("company", "both"):
            if not args.company_root:
                report["tiers"].append(
                    {
                        "tier": "company",
                        "status": "skip",
                        "detail": "--company-root not set and $COMPANY_ROOT empty",
                    }
                )
            else:
                r = check_tier("company", _resolve_company_wiki(args.company_root))
                report["tiers"].append(r)
                if r["status"] == "drift":
                    drift_seen = True
    except Exception as exc:  # pragma: no cover — defensive; 0/1/2/3 convention
        print(
            json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr
        )
        return 3

    if drift_seen:
        report["status"] = "drift"

    print(json.dumps(report, indent=2))
    return 1 if drift_seen else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
