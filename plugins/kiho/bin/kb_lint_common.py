#!/usr/bin/env python3
"""
kb_lint_common.py — shared helpers for the kb_lint_* parity checker family.

Lives next to the per-index scripts (kb_lint_skill_solutions.py,
kb_lint_tags.py, kb_lint_backlinks.py, kb_lint_graph.py,
kb_lint_cross_project.py). Provides frontmatter parsing, wikilink extraction,
index-section parsing, and the shared argparse + tier-selection scaffold so
each per-index script stays under ~120 LOC.

Exit-code convention (v5.15.2): 0 aligned/no-wiki, 1 drift, 2 usage, 3 internal.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable


# --- regex ------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_LIST_ITEM_RE = re.compile(r"^[ \t]+-[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|[^\]]*)?\]\]")
_H2_HEADER_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

# The 12 derived indexes rebuilt by kiho-kb-manager (see agents/kiho-kb-manager.md
# §"Index rebuild protocol"). Source-page walkers MUST skip these to avoid
# treating one derived index's wikilinks as authored content belonging to another
# index's parity calculation. Kept in module scope so every checker shares the
# same list — any additions go here first.
DERIVED_INDEX_FILENAMES: frozenset[str] = frozenset({
    "index.md",
    "log.md",
    "tags.md",
    "backlinks.md",
    "timeline.md",
    "stale.md",
    "open-questions.md",
    "graph.md",
    "by-confidence.md",
    "by-owner.md",
    "skill-solutions.md",
    "cross-project.md",
})


def strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


# --- frontmatter extraction -------------------------------------------------

def extract_frontmatter_block(text: str) -> str | None:
    """Return the frontmatter body (between ---) or None if absent."""
    m = _FRONTMATTER_RE.match(text)
    return m.group(1) if m else None


def extract_list_field(text: str, field: str) -> list[str]:
    """Return a list of strings from a frontmatter field that may be written as
    inline array, block list, or absent. Tolerates quoted values.
    """
    block = extract_frontmatter_block(text)
    if block is None:
        return []
    # inline form: tags: [a, b, c]
    inline_re = re.compile(
        rf"^\s*{re.escape(field)}\s*:\s*\[(.*?)\]\s*$", re.MULTILINE
    )
    m = inline_re.search(block)
    if m:
        return [strip_quotes(x) for x in m.group(1).split(",") if x.strip()]
    # block form:
    # tags:
    #   - a
    #   - b
    block_re = re.compile(
        rf"^\s*{re.escape(field)}\s*:\s*\n((?:[ \t]+-[ \t]+.+\n)+)",
        re.MULTILINE,
    )
    m = block_re.search(block + "\n")
    if m:
        return [
            strip_quotes(mi.group(1))
            for mi in _LIST_ITEM_RE.finditer(m.group(1))
        ]
    return []


def extract_scalar_field(text: str, field: str) -> str | None:
    """Return a frontmatter scalar field value (or None if absent)."""
    block = extract_frontmatter_block(text)
    if block is None:
        return None
    scalar_re = re.compile(
        rf"^\s*{re.escape(field)}\s*:\s*(.+?)\s*$", re.MULTILINE
    )
    m = scalar_re.search(block)
    if not m:
        return None
    val = m.group(1).strip()
    # Skip "follows-on-next-line" block-list markers
    if val == "" or val.startswith("["):
        return None
    return strip_quotes(val)


def body_after_frontmatter(text: str) -> str:
    """Return the body text after the frontmatter block (full text if none)."""
    m = _FRONTMATTER_RE.match(text)
    return text[m.end():] if m else text


# --- wikilink extraction ----------------------------------------------------

def extract_wikilinks(text: str) -> set[str]:
    """Return the set of all [[wikilink]] targets in the text.

    Strips |alias pipes; preserves case. Filters no paths (callers decide
    whether path-style wikilinks count; see kb_lint_skill_solutions.py for
    precedent)."""
    return {m.group(1).strip() for m in _WIKILINK_RE.finditer(text)}


def extract_wikilinks_list(text: str) -> list[str]:
    """List form of extract_wikilinks, preserving order + duplicates."""
    return [m.group(1).strip() for m in _WIKILINK_RE.finditer(text)]


# --- index parsing ----------------------------------------------------------

def parse_index_sections(index_path: Path) -> dict[str, set[str]]:
    """Parse a derived index file into a dict of section_header -> set of
    wikilink targets under that section.

    Treats each `## <header>` as starting a new section. Wikilinks before the
    first `## ` header attach to a sentinel key "" (empty string) so no data is
    lost, but most callers should ignore that key.
    """
    sections: dict[str, set[str]] = {}
    if not index_path.exists():
        return sections
    try:
        text = index_path.read_text(encoding="utf-8")
    except OSError:
        return sections

    current = ""
    sections[current] = set()
    for line in text.splitlines():
        hm = _H2_HEADER_RE.match(line + "\n")
        if hm:
            current = hm.group(1).strip()
            sections.setdefault(current, set())
            continue
        for lm in _WIKILINK_RE.finditer(line):
            sections[current].add(lm.group(1).strip())
    return sections


# --- tier orchestration -----------------------------------------------------

def resolve_project_wiki(project_root: str) -> Path:
    return Path(project_root).resolve() / ".kiho" / "kb" / "wiki"


def resolve_company_wiki(company_root: str) -> Path:
    return Path(company_root).resolve() / "company" / "wiki"


def run_tier_check(
    tier_name: str,
    wiki_root: Path,
    checker: Callable[[Path], dict],
) -> dict:
    """Dispatch a per-tier check. Returns the checker's dict with tier +
    wiki_exists + wiki_root annotations added."""
    result: dict = {
        "tier": tier_name,
        "wiki_root": str(wiki_root),
        "wiki_exists": wiki_root.exists(),
    }
    if not wiki_root.exists():
        result["status"] = "no_wiki"
        result["detail"] = f"{wiki_root} does not exist; skipping (advisory)"
        return result
    result.update(checker(wiki_root))
    return result


# --- telemetry (best-effort; v5.19.5 N2) -----------------------------------

def safe_telemetry_record(
    op: str,
    *,
    key: str | None = None,
    duration_ms: int | None = None,
    plugin_root: Path | str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Best-effort wrapper around `storage_telemetry.record()`.

    Swallows ImportError (storage_telemetry unavailable) AND any exception
    from the record() call itself. Telemetry is diagnostic-only and MUST NOT
    break kb_lint behavior. Matches the pattern in `bin/skill_catalog_index.py`
    lines 64-76.
    """
    try:
        from storage_telemetry import record as _record
    except ImportError:
        return
    try:
        _record(
            op=op,
            key=key,
            duration_ms=duration_ms,
            plugin_root=plugin_root,
            extra=extra,
        )
    except Exception:  # pragma: no cover — defensive
        pass


def build_argparser(description: str, epilog_extra: str = "") -> argparse.ArgumentParser:
    """Shared argparse scaffold. Returns the parser; caller calls parse_args."""
    p = argparse.ArgumentParser(
        description=description,
        epilog=(
            "Exit codes: 0 aligned/no-wiki, 1 drift, 2 usage, 3 internal. "
            + epilog_extra
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
    return p


def dispatch(
    argv: list[str],
    description: str,
    checker: Callable[[Path], dict],
    *,
    company_only: bool = False,
    epilog_extra: str = "",
) -> int:
    """Shared main() body for the kb_lint family.

    - parses CLI
    - validates project-root (unless company_only)
    - dispatches per-tier
    - emits JSON report
    - returns the conventional exit code (0 aligned, 1 drift, 2 usage, 3 internal)

    The caller's `checker(wiki_root)` MUST return a dict with a `status` field
    valued "ok" or "drift" (other values pass through unchanged).
    """
    parser = build_argparser(description, epilog_extra)
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    project_path = Path(args.project_root)
    if not company_only and args.tier in ("project", "both"):
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
    _t0 = time.perf_counter()

    try:
        if not company_only and args.tier in ("project", "both"):
            r = run_tier_check(
                "project", resolve_project_wiki(args.project_root), checker
            )
            report["tiers"].append(r)
            if r.get("status") == "drift":
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
                r = run_tier_check(
                    "company", resolve_company_wiki(args.company_root), checker
                )
                report["tiers"].append(r)
                if r.get("status") == "drift":
                    drift_seen = True

        if company_only and args.tier == "project":
            report["tiers"].append(
                {
                    "tier": "project",
                    "status": "skip",
                    "detail": "this checker is company-tier only",
                }
            )
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr)
        return 3

    if drift_seen:
        report["status"] = "drift"

    # Emit one telemetry event per invocation. Gate on at least one tier
    # actually running a check (skip/no_wiki tiers alone → no event) so
    # empty-wiki or no-company-root invocations stay quiet.
    _duration_ms = int((time.perf_counter() - _t0) * 1000)
    _ran_any = any(
        t.get("status") in ("ok", "drift") for t in report["tiers"]
    )
    if _ran_any:
        # Derive checker name from caller's sys.argv[0]
        _checker = Path(argv[0]).stem if argv else "kb_lint_unknown"
        drift_count = sum(
            len(t.get("missing_from_index", []) or [])
            + len(t.get("extra_in_index", []) or [])
            + len(t.get("misordered", []) or [])
            + len(t.get("orphan_sections", []) or [])
            for t in report["tiers"]
        )
        safe_telemetry_record(
            op="kb_lint",
            key=_checker,
            duration_ms=_duration_ms,
            plugin_root=_plugin_root_guess(),
            extra={
                "tier": args.tier,
                "aligned": not drift_seen,
                "drift_count": drift_count,
                "tiers_ran": sum(
                    1 for t in report["tiers"]
                    if t.get("status") in ("ok", "drift")
                ),
            },
        )

    print(json.dumps(report, indent=2))
    return 1 if drift_seen else 0


def _plugin_root_guess() -> Path:
    """Guess kiho-plugin root for telemetry.record(): parent of bin/."""
    return Path(__file__).resolve().parents[1]
