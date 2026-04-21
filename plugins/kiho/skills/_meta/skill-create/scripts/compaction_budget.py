#!/usr/bin/env python3
"""
compaction_budget.py — Gate 16: post-compaction skill budget (v5.14).

Claude Code keeps the first 5,000 tokens of the most recent invocation of
each skill after conversation summarization, with a combined cap of
25,000 tokens across re-attached skills. This script estimates the per-skill
body token cost, ranks the likely "recent invocation" set, and warns when
the top-N would exceed 80% of the compaction ceiling.

Input: the draft SKILL.md path (for body tokens) and the catalog (to compute
the recent-invocation set from `last_used_at` or similar heuristics).

Output: a budget projection in JSON. Exit 0 if within 80%, 1 if above.

Grounding:
    code.claude.com/docs/en/skills — skill content lifecycle in compaction:
    first 5,000 tokens of the most recent invocation of each skill, combined
    25k-token budget across re-attached skills. kiho v5.14 Thread 2.

Usage:
    compaction_budget.py --draft <path-to-draft-SKILL.md> [--top-n 5]
                         [--per-skill-token-cap 5000] [--total-cap 25000]
                         [--warn-fraction 0.80]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_PER_SKILL = 5000
DEFAULT_TOTAL = 25000
DEFAULT_TOP_N = 5            # approximate "recent invocation set" in a /kiho turn
DEFAULT_WARN_FRACTION = 0.80
CHARS_PER_TOKEN = 3.5


def tiktoken_count(text: str) -> int | None:
    try:
        import tiktoken  # type: ignore
    except ImportError:
        return None
    try:
        enc = tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None
    return len(enc.encode(text))


def token_count(text: str) -> int:
    n = tiktoken_count(text)
    if n is not None:
        return n
    # Fallback: word_count * 1.3 (per count_tokens.py convention)
    words = text.split()
    return int(len(words) * 1.3)


def load_draft(path: Path) -> int:
    if not path.exists():
        sys.stderr.write(f"draft not found: {path}\n")
        sys.exit(2)
    return token_count(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--draft", required=True, help="path to draft SKILL.md")
    p.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    p.add_argument("--per-skill-token-cap", type=int, default=DEFAULT_PER_SKILL)
    p.add_argument("--total-cap", type=int, default=DEFAULT_TOTAL)
    p.add_argument("--warn-fraction", type=float, default=DEFAULT_WARN_FRACTION)
    p.add_argument("--siblings", nargs="*", default=[],
                   help="paths to sibling active-skill SKILL.md files that would"
                        " likely be re-attached in the same session")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    draft_path = Path(args.draft)
    draft_tokens = load_draft(draft_path)

    sibling_costs: list[dict[str, int | str]] = []
    for s in args.siblings:
        sp = Path(s)
        if not sp.exists():
            continue
        text = sp.read_text(encoding="utf-8")
        t = token_count(text)
        sibling_costs.append({
            "path": str(sp),
            "tokens": min(t, args.per_skill_token_cap),
            "raw_tokens": t,
        })

    # The draft enters the recent-invocation set
    draft_cost = min(draft_tokens, args.per_skill_token_cap)

    # Take the top-N siblings with the highest cost as the likely set
    sibling_costs.sort(key=lambda r: int(r["tokens"]), reverse=True)
    retained = sibling_costs[: max(0, args.top_n - 1)]
    retained_tokens = sum(int(r["tokens"]) for r in retained)
    projected_total = draft_cost + retained_tokens

    warn_ceiling = int(args.total_cap * args.warn_fraction)

    result = {
        "draft": str(draft_path),
        "draft_body_tokens": draft_tokens,
        "draft_capped_at_per_skill": draft_cost,
        "per_skill_token_cap": args.per_skill_token_cap,
        "total_cap": args.total_cap,
        "warn_at": warn_ceiling,
        "top_n": args.top_n,
        "sibling_count": len(sibling_costs),
        "sibling_retained": retained,
        "projected_total_tokens": projected_total,
        "usage_fraction": round(projected_total / args.total_cap, 3),
    }

    if projected_total > args.total_cap:
        result["verdict"] = "rejected"
        sys.stdout.write(json.dumps(result, indent=2))
        sys.stdout.write("\n")
        return 2

    if projected_total > warn_ceiling:
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
