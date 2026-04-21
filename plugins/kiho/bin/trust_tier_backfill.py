#!/usr/bin/env python3
"""
trust_tier_backfill.py — one-shot metadata.trust-tier backfill (v5.21 close-the-gaps).

CLAUDE.md invariant: every SKILL.md carries `metadata.trust-tier: T1|T2|T3|T4`.
At v5.21 ship, 0 of 81 SKILL.md files declare it in frontmatter. This script
performs the origin-heuristic backfill per the approved plan:

    skills/_meta/*                             -> T3 (kernel)
    skills/core/harness/*                      -> T3 (load-bearing)
    skills/core/storage/storage-broker         -> T3 (invariant)
    skills/core/{ceremony,communication,...}/* -> T2 (hand-authored flow)
    skills/kb/*, skills/memory/*               -> T2 (gateway + audited)
    skills/engineering/*                       -> T2 (vendored + hand-authored)
    everything else                            -> T1 (unvetted)

Insertion strategy: line-surgical, not round-tripped through a YAML parser.
kiho_frontmatter.py's stdlib subset refuses nested mappings, so we preserve
the existing frontmatter text byte-for-byte and inject a single
`  trust-tier: TX` line immediately after the `metadata:` line, before any
nested key. Idempotent: re-running detects the existing key and skips.

Exit codes:
    0 — all files processed (see report)
    1 — one or more files failed parse/write
    2 — usage error
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DELIM = "---"

TIER_T3_META_NAMES = {
    "skill-create", "skill-critic", "skill-improve", "skill-verify",
    "skill-spec", "skill-graph", "skill-parity", "skill-intake",
    "skill-find", "skill-derive", "skill-structural-gate", "skill-architect",
    "skill-cousin-prompt", "skill-deprecate", "skill-sunset-announce",
    "skill-factory", "skill-learn", "evolution-scan",
    "soul-validate", "soul-apply-override", "cycle-runner",
}

TIER_T3_CORE_HARNESS = {"kiho", "kiho-init", "kiho-setup", "kiho-spec", "org-sync"}


def assign_tier(skill_path: Path) -> str:
    parts = skill_path.parts
    try:
        skills_idx = parts.index("skills")
    except ValueError:
        return "T1"
    tail = parts[skills_idx + 1:]
    if not tail:
        return "T1"
    domain = tail[0]
    # skills/_meta/<name>/SKILL.md
    if domain == "_meta" and len(tail) >= 2 and tail[1] in TIER_T3_META_NAMES:
        return "T3"
    if domain == "core" and len(tail) >= 3:
        sub = tail[1]
        skill_name = tail[2]
        if sub == "harness" and skill_name in TIER_T3_CORE_HARNESS:
            return "T3"
        if sub == "storage" and skill_name == "storage-broker":
            return "T3"
        # Hand-authored team flow under core/{ceremony,communication,feedback,
        # hr,inspection,integrations,knowledge,lifecycle,ops,planning,values}
        if sub in {
            "ceremony", "communication", "feedback", "hr", "inspection",
            "integrations", "knowledge", "lifecycle", "ops", "planning", "values",
        }:
            return "T2"
    if domain in {"kb", "memory"}:
        return "T2"
    if domain == "engineering":
        return "T2"
    return "T1"


_FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_METADATA_LINE_RE = re.compile(r"^(?P<indent>\s*)metadata\s*:\s*$", re.MULTILINE)
_TRUST_TIER_ANY = re.compile(r"^\s*trust[-_]tier\s*:", re.MULTILINE)


def backfill_one(path: Path, dry_run: bool = False) -> tuple[str, str | None]:
    """Return (status, tier_assigned_or_reason).

    status in {"inserted", "already-present", "no-metadata-block",
               "no-frontmatter", "error"}
    """
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        return "no-frontmatter", None
    fm_start, fm_end = m.span(1)
    fm_block = text[fm_start:fm_end]
    if _TRUST_TIER_ANY.search(fm_block):
        return "already-present", None
    meta_match = _METADATA_LINE_RE.search(fm_block)
    if not meta_match:
        return "no-metadata-block", None
    tier = assign_tier(path)
    insertion = f"\n{meta_match.group('indent')}  trust-tier: {tier}"
    # Insert right after the end of the metadata: line
    insert_at = fm_start + meta_match.end()
    new_text = text[:insert_at] + insertion + text[insert_at:]
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return "inserted", tier


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", help="plugin root (e.g. D:/programme/ai/kiho-plugin)")
    ap.add_argument("--dry-run", action="store_true",
                    help="do not write; print what would change")
    ap.add_argument("--report", default=None,
                    help="write a markdown report to this path")
    args = ap.parse_args(argv)

    root = Path(args.root)
    skills_root = root / "skills"
    if not skills_root.is_dir():
        print(f"not a plugin root: {root}", file=sys.stderr)
        return 2

    files = sorted(skills_root.rglob("SKILL.md"))
    summary: dict[str, list[tuple[Path, str | None]]] = {
        "inserted": [], "already-present": [], "no-metadata-block": [],
        "no-frontmatter": [], "error": [],
    }
    for f in files:
        try:
            status, tier = backfill_one(f, dry_run=args.dry_run)
        except Exception as exc:  # pragma: no cover
            summary["error"].append((f, str(exc)))
            continue
        summary[status].append((f, tier))

    for k, rows in summary.items():
        print(f"{k}: {len(rows)}")
        if k == "inserted":
            for p, t in rows:
                print(f"  [{t}] {p.relative_to(root)}")

    if args.report:
        lines = [
            "# trust-tier backfill report",
            "",
            f"Root: `{root}`",
            f"Mode: {'dry-run' if args.dry_run else 'write'}",
            "",
            f"Total SKILL.md scanned: {len(files)}",
            "",
        ]
        for k, rows in summary.items():
            lines.append(f"## {k} ({len(rows)})")
            lines.append("")
            if not rows:
                lines.append("_none_")
                lines.append("")
                continue
            for p, t in rows:
                lines.append(f"- `{p.relative_to(root)}` {'— ' + str(t) if t else ''}")
            lines.append("")
        Path(args.report).write_text("\n".join(lines), encoding="utf-8")
        print(f"report: {args.report}")

    return 0 if not summary["error"] else 1


if __name__ == "__main__":
    sys.exit(main())
