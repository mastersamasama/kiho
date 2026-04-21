#!/usr/bin/env python3
"""
budget_preflight.py — Gate 15: Claude Code description budget pre-flight (v5.14).

Claude Code loads all skill `name` + `description` fields into the Skill tool
prompt at session start, capped at 1% of context window (default) or 8,000
chars (fallback). Each individual skill's combined `description +
when_to_use` is hard-capped at 1,536 chars regardless of total budget.

This script scans the ACTIVE skill set in the catalog, sums description sizes,
and reports whether adding the pending new skill would push the total past
90% of the budget. If it would, Gate 15 fails and the caller must trim.

Usage:
    budget_preflight.py [--catalog skills/CATALOG.md]
                        [--new-description text-or-file]
                        [--context-window 200000]
                        [--budget-fraction 0.01]
                        [--fallback-chars 8000]
                        [--warn-at 0.90]

Exit codes:
    0 — within budget with headroom
    1 — would exceed 90% of budget with the new skill added (warning)
    2 — would exceed budget entirely (hard reject)

Grounding:
    code.claude.com/docs/en/skills — SLASH_COMMAND_TOOL_CHAR_BUDGET defaults,
    1% of context window / 8000 char fallback, 1,536-char per-skill cap.
    kiho v5.14 Thread 2 + H3.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PER_SKILL_HARD_CAP = 1536  # chars; per Claude Code docs (2026)


def parse_catalog_descriptions(catalog_text: str) -> list[tuple[str, str]]:
    """Extract (skill_id, description) tuples from CATALOG.md tables.

    Catalog rows look like:
        | `sk-024` | **skill-find** | `_meta/skill-find/` | Runtime skill discovery... |

    We pull the last column as the (truncated) description. This script does
    NOT load the actual SKILL.md files — it uses the CATALOG-rendered
    descriptions as a proxy, because those are what Claude Code actually
    injects into the Skill tool prompt (via 00-index.md / the catalog).
    """
    rows: list[tuple[str, str]] = []
    pat = re.compile(
        r"^\|\s*`(sk[-\w]+)`\s*\|\s*\*\*[^*]+\*\*\s*\|\s*`[^`]*`\s*\|\s*([^|]+?)\s*\|\s*$",
        re.MULTILINE,
    )
    for m in pat.finditer(catalog_text):
        skill_id = m.group(1)
        desc = m.group(2).strip()
        # Catalog descriptions end with "..." if truncated; we use them as-is
        rows.append((skill_id, desc))
    return rows


def resolve_description(arg: str | None) -> str:
    if not arg:
        return ""
    path = Path(arg)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return arg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="skills/CATALOG.md")
    p.add_argument("--new-description", default=None,
                   help="description of the pending new skill (text or file)")
    p.add_argument("--new-when-to-use", default=None,
                   help="when_to_use field for the pending new skill (v5.14)")
    p.add_argument("--context-window", type=int, default=200000,
                   help="context window in tokens (default 200000)")
    p.add_argument("--budget-fraction", type=float, default=0.01,
                   help="fraction of context window reserved for skill descs")
    p.add_argument("--fallback-chars", type=int, default=8000,
                   help="fallback char budget if computed budget is zero")
    p.add_argument("--warn-at", type=float, default=0.90,
                   help="warn threshold as fraction of budget")
    p.add_argument("--chars-per-token", type=float, default=3.5,
                   help="chars-per-token estimate for budget conversion")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        sys.stderr.write(f"CATALOG not found: {catalog_path}\n")
        return 2

    catalog_text = catalog_path.read_text(encoding="utf-8")
    descriptions = parse_catalog_descriptions(catalog_text)

    total_chars_existing = sum(len(d) for _, d in descriptions)
    max_existing = max((len(d) for _, d in descriptions), default=0)

    # Compute the actual char budget
    budget_from_context = int(
        args.context_window * args.chars_per_token * args.budget_fraction
    )
    char_budget = max(budget_from_context, args.fallback_chars)

    # Pending new skill
    new_desc = resolve_description(args.new_description)
    new_wtu = resolve_description(args.new_when_to_use)
    combined_new = len(new_desc) + len(new_wtu)
    combined_new_over_cap = combined_new > PER_SKILL_HARD_CAP

    projected_total = total_chars_existing + combined_new
    projected_usage = projected_total / char_budget if char_budget else 0.0

    # Flag oversized existing skills
    oversized_existing = [
        {"skill_id": sid, "length": len(d)}
        for sid, d in descriptions
        if len(d) > PER_SKILL_HARD_CAP
    ]

    result = {
        "catalog": str(catalog_path),
        "skill_count": len(descriptions),
        "total_chars_existing": total_chars_existing,
        "longest_existing_chars": max_existing,
        "per_skill_hard_cap": PER_SKILL_HARD_CAP,
        "char_budget": char_budget,
        "budget_source": (
            "context_window * chars_per_token * fraction"
            if budget_from_context >= args.fallback_chars
            else "fallback"
        ),
        "new_description_chars": len(new_desc),
        "new_when_to_use_chars": len(new_wtu),
        "combined_new_chars": combined_new,
        "combined_new_over_per_skill_cap": combined_new_over_cap,
        "projected_total_chars": projected_total,
        "projected_usage_fraction": round(projected_usage, 3),
        "warn_at": args.warn_at,
        "oversized_existing": oversized_existing,
    }

    if combined_new_over_cap or projected_usage >= 1.0:
        result["verdict"] = "rejected"
        sys.stdout.write(json.dumps(result, indent=2))
        sys.stdout.write("\n")
        return 2

    if projected_usage >= args.warn_at:
        result["verdict"] = "warn"
        sys.stdout.write(json.dumps(result, indent=2))
        sys.stdout.write("\n")
        return 1

    result["verdict"] = "ok"
    sys.stdout.write(json.dumps(result, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
