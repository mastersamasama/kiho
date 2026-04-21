#!/usr/bin/env python3
"""
similarity_scan.py — Gate 17: novel-contribution similarity scan (v5.15).

Compares a draft skill description against every existing skill's description
in the catalog via Jaccard on unigrams + bigrams (after stop-word removal).
Blocks near-duplicates, warns on partial overlap, surfaces the top-3 closest
matches with shared tokens so the author can decide whether to improve an
existing skill, derive from it, or continue creating.

Grounding:
- arXiv 2601.04748 §5.3 — semantic confusability drives the phase transition;
  two similar skills hurt more than two extra unrelated skills. kiho at 37
  skills is already past the |S|=30 inflection.
- Nelhage fuzzy-dedup (https://blog.nelhage.com/post/fuzzy-dedup/) — Jaccard
  on shingles is the industry-standard markdown-scale dedup primitive.
- arXiv 2411.04257 (LSHBloom) — 0.60 as "likely duplicate" threshold for
  short-text dedup.

Shingle choice: unigrams + bigrams (not pure 3-shingles). kiho descriptions
are typically 50-300 tokens after stop-word removal; 3-shingles are too
sparse at this scale. Unigrams+bigrams give equivalent discrimination with
better recall on short markdown metadata. At larger scale (200+ skills)
this script can be upgraded to MinHash+Jaccard in ~30 lines; see the
"Scale upgrade" section of novel-contribution.md.

Usage:
    similarity_scan.py --description <text-or-file>
                       [--catalog-root skills/]
                       [--block-threshold 0.60]
                       [--warn-threshold 0.30]
                       [--force-overlap]
                       [--catalog-health]
                       [--exclude <path>]

Exit codes:
    0 — novel, related_review (warn), or near_duplicate_forced (override)
    1 — near_duplicate blocked
    2 — usage error or catalog missing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Mirrors STOP_WORDS in catalog_fit.py (v5.14) — kept in sync manually so
# Gate 14 and Gate 17 tokenize the same way.
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "of", "for", "to", "in", "on", "at",
    "by", "with", "from", "into", "out", "as", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "can", "could", "may", "might", "must", "should", "this", "that",
    "these", "those", "it", "its", "which", "who", "whom", "whose", "use",
    "used", "using", "when", "where", "what", "why", "how", "not", "no",
    "yes", "all", "any", "some", "each", "every", "both", "few", "more",
    "most", "other", "such", "only", "own", "same", "so", "than", "too",
    "very", "just", "about", "above", "after", "again", "against", "also",
    "back", "before", "below", "between", "down", "during", "further",
    "here", "there", "then", "through", "under", "until", "up", "while",
    "skill", "skills", "via", "without", "within", "new", "existing",
    "user", "user's", "users", "agent", "agents", "kiho",
}

BLOCK_DEFAULT = 0.60
WARN_DEFAULT = 0.30


def tokenize(text: str) -> list[str]:
    """Lowercase ordered token list, stop words removed, tokens >= 3 chars."""
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


def shingles(tokens: list[str]) -> set[str]:
    """Unigrams + bigrams. See header comment for shingle choice rationale."""
    out: set[str] = set(tokens)
    for i in range(len(tokens) - 1):
        out.add(f"{tokens[i]}__{tokens[i + 1]}")
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def extract_description(text: str) -> str:
    """Pull the top-level `description:` field from a SKILL.md frontmatter
    block. Single-line scalar only (kiho convention). Returns empty string
    if no frontmatter or no description."""
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return ""
    front = m.group(1)
    for line in front.splitlines():
        dm = re.match(r"^description\s*:\s*(.*)$", line)
        if dm:
            val = dm.group(1).strip()
            # Strip surrounding quotes if present.
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            return val
    return ""


def extract_name(text: str, fallback: str) -> str:
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return fallback
    front = m.group(1)
    for line in front.splitlines():
        nm = re.match(r"^name\s*:\s*(.*)$", line)
        if nm:
            val = nm.group(1).strip()
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            return val
    return fallback


def load_catalog_skills(catalog_root: Path, exclude: set[Path]) -> list[dict]:
    """Walk catalog_root/**/SKILL.md and collect catalog entries with
    precomputed shingle sets. Paths in `exclude` are skipped (used when
    scanning against an in-progress draft)."""
    entries: list[dict] = []
    for skill_md in sorted(catalog_root.rglob("SKILL.md")):
        try:
            if skill_md.resolve() in exclude:
                continue
        except OSError:
            pass
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        desc = extract_description(text)
        if not desc:
            continue
        name = extract_name(text, fallback=skill_md.parent.name)
        toks = tokenize(desc)
        shg = shingles(toks)
        entries.append(
            {
                "name": name,
                "path": str(skill_md),
                "description": desc,
                "token_count": len(toks),
                "shingle_count": len(shg),
                "shingles": shg,
            }
        )
    return entries


def top_matches(draft_shg: set[str], catalog: list[dict], k: int = 3) -> list[dict]:
    scored: list[tuple[float, dict]] = []
    for entry in catalog:
        j = jaccard(draft_shg, entry["shingles"])
        if j > 0:
            scored.append((j, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    result: list[dict] = []
    for j, entry in scored[:k]:
        shared = sorted(draft_shg & entry["shingles"])
        unique_draft = sorted(draft_shg - entry["shingles"])[:10]
        unique_match = sorted(entry["shingles"] - draft_shg)[:10]
        result.append(
            {
                "name": entry["name"],
                "path": entry["path"],
                "jaccard": round(j, 4),
                "shared_sample": shared[:15],
                "unique_to_draft_sample": unique_draft,
                "unique_to_match_sample": unique_match,
            }
        )
    return result


def classify(top: list[dict], block_thr: float, warn_thr: float) -> str:
    if not top:
        return "novel"
    best_j = float(top[0]["jaccard"])
    if best_j >= block_thr:
        return "near_duplicate"
    if best_j >= warn_thr:
        return "related_review"
    return "novel"


def suggested_action(status: str, top: list[dict]) -> str:
    if status == "near_duplicate" and top:
        return f"improve {top[0]['name']}"
    if status == "related_review" and top:
        return f"consider derive from {top[0]['name']}"
    return "create-novel"


def mean_pairwise_jaccard(entries: list[dict]) -> float:
    n = len(entries)
    if n < 2:
        return 0.0
    total = 0.0
    count = 0
    for i in range(n):
        for k in range(i + 1, n):
            total += jaccard(entries[i]["shingles"], entries[k]["shingles"])
            count += 1
    return total / count if count else 0.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--description",
        help="new skill description (literal text or path to file)",
    )
    p.add_argument(
        "--catalog-root",
        default="skills",
        help="root directory containing skills/**/SKILL.md (default: skills)",
    )
    p.add_argument(
        "--block-threshold",
        type=float,
        default=BLOCK_DEFAULT,
        help=f"Jaccard threshold for near_duplicate block (default {BLOCK_DEFAULT})",
    )
    p.add_argument(
        "--warn-threshold",
        type=float,
        default=WARN_DEFAULT,
        help=f"Jaccard threshold for related_review warn (default {WARN_DEFAULT})",
    )
    p.add_argument(
        "--force-overlap",
        action="store_true",
        help="bypass near_duplicate block (CEO committee only; skill-create logs forced)",
    )
    p.add_argument(
        "--catalog-health",
        action="store_true",
        help="compute mean-pairwise Jaccard across the whole catalog",
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="SKILL.md path to exclude from scan (draft-in-progress)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    catalog_root = Path(args.catalog_root)
    if not catalog_root.exists():
        sys.stderr.write(f"catalog root not found: {catalog_root}\n")
        return 2

    exclude_resolved: set[Path] = set()
    for e in args.exclude:
        try:
            exclude_resolved.add(Path(e).resolve())
        except OSError:
            pass

    entries = load_catalog_skills(catalog_root, exclude_resolved)

    if args.catalog_health:
        mean_j = mean_pairwise_jaccard(entries)
        result = {
            "mode": "catalog-health",
            "catalog_root": str(catalog_root),
            "skill_count": len(entries),
            "mean_pairwise_jaccard": round(mean_j, 4),
        }
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0

    if not args.description:
        sys.stderr.write("--description required unless --catalog-health\n")
        return 2

    desc_arg = args.description
    if Path(desc_arg).is_file():
        description = Path(desc_arg).read_text(encoding="utf-8")
    else:
        description = desc_arg

    draft_toks = tokenize(description)
    draft_shg = shingles(draft_toks)

    matches = top_matches(draft_shg, entries, k=3)
    status = classify(matches, args.block_threshold, args.warn_threshold)
    action = suggested_action(status, matches)

    forced = False
    exit_code = 0
    if status == "near_duplicate":
        if args.force_overlap:
            status = "near_duplicate_forced"
            forced = True
        else:
            exit_code = 1

    result = {
        "status": status,
        "forced": forced,
        "block_threshold": args.block_threshold,
        "warn_threshold": args.warn_threshold,
        "draft_token_count": len(draft_toks),
        "draft_shingle_count": len(draft_shg),
        "catalog_skill_count": len(entries),
        "top_matches": matches,
        "suggested_action": action,
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
