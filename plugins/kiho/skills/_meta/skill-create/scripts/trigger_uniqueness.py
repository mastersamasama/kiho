#!/usr/bin/env python3
"""
trigger_uniqueness.py — Gate 23: trigger-phrase uniqueness (v5.16).

Gate 17 (similarity_scan.py) checks description Jaccard. Trigger phrases
are separate metadata and can collide independently — two skills may
have distinct descriptions but share `when_to_use` phrasing, so agents
picking by trigger phrase alone will roll a coin. Gate 23 catches this
by computing pairwise Jaccard on unigrams over the `## When to use`
section (or metadata.kiho.trigger_phrases when declared).

Threshold 0.70 is stricter than description's 0.60 because trigger
phrases are literal and collisions have immediate routing impact. Fixing
a shipped skill's trigger phrase is a bigger migration than rewriting a
description.

Two modes:
    --draft <path>   Check one draft against every existing skill
    --all            Audit pairwise matrix over the whole catalog

Grounding: v5.16 Primitive 3 + plan Stage F. Nelhage fuzzy-dedup
writeup (0.30/0.60 defaults for description-level Jaccard; +0.10
offset for trigger-phrase strictness is a kiho-specific calibration).

Usage:
    trigger_uniqueness.py --draft <path>
    trigger_uniqueness.py --all [--block 0.70] [--warn 0.50]

Exit codes (0/1/2/3):
    0 — no pairs above block threshold
    1 — policy violation: at least one pair at or above block threshold
    2 — usage error
    3 — internal error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent.parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"

DEFAULT_BLOCK = 0.70
DEFAULT_WARN = 0.50

# STOP_WORDS mirrored from catalog_fit.py
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


def tokenize(text: str) -> set[str]:
    raw = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    return {t for t in raw if t not in STOP_WORDS}


def read_skill_id(skill_dir: Path) -> str:
    sid_path = skill_dir / ".skill_id"
    if sid_path.exists():
        return sid_path.read_text(encoding="utf-8").strip()
    return ""


def extract_trigger_text(skill_md: Path) -> str:
    """Extract trigger signal text. Priority:
      1. metadata.kiho.trigger_phrases list (joined)
      2. `## When to use` section body
      3. empty string (skill contributes nothing to the check)
    """
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if m:
        fm = m.group(1)
        trig_m = re.search(
            r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+trigger_phrases:\s*\[([^\]]*)\]",
            fm,
            re.MULTILINE,
        )
        if trig_m:
            raw = trig_m.group(1)
            phrases = [
                p.strip().strip('"').strip("'")
                for p in raw.split(",")
                if p.strip()
            ]
            if phrases:
                return " ".join(phrases)
    wtu_m = re.search(
        r"^##\s+When to use\b[^\n]*\n(.*?)(?=^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if wtu_m:
        return wtu_m.group(1)
    return ""


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return inter / union


def discover_all_skills() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for domain in ("_meta", "core", "kb", "memory", "engineering"):
        domain_dir = SKILLS_DIR / domain
        if not domain_dir.is_dir():
            continue
        for child in sorted(domain_dir.iterdir()):
            if not child.is_dir():
                continue
            flat = child / "SKILL.md"
            if flat.is_file():
                sid = read_skill_id(child)
                if sid:
                    result[sid] = flat
                continue
            for grand in sorted(child.iterdir()):
                if not grand.is_dir():
                    continue
                nested = grand / "SKILL.md"
                if nested.is_file():
                    sid = read_skill_id(grand)
                    if sid:
                        result[sid] = nested
    return result


def check_pairwise(
    skills: dict[str, Path],
    block: float,
    warn: float,
) -> dict:
    """Compute pairwise Jaccard over the whole catalog. Returns all pairs
    at or above `warn` threshold with their scores, sorted descending."""
    tokens: dict[str, set[str]] = {}
    for sid, path in skills.items():
        tokens[sid] = tokenize(extract_trigger_text(path))
    ids = sorted(tokens)
    pairs: list[dict] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            score = jaccard(tokens[a], tokens[b])
            if score >= warn:
                pairs.append({
                    "a": a,
                    "b": b,
                    "jaccard": round(score, 4),
                    "level": "block" if score >= block else "warn",
                })
    pairs.sort(key=lambda p: -p["jaccard"])
    blocked = [p for p in pairs if p["level"] == "block"]
    warnings = [p for p in pairs if p["level"] == "warn"]
    return {
        "passed": not blocked,
        "status": "ok" if not blocked else "trigger_collision",
        "block_threshold": block,
        "warn_threshold": warn,
        "total_skills": len(ids),
        "block_pairs": blocked,
        "warn_pairs": warnings,
    }


def check_draft_against_catalog(
    draft_path: Path,
    skills: dict[str, Path],
    block: float,
    warn: float,
) -> dict:
    """Compare a draft against every existing skill."""
    if not draft_path.is_file():
        return {"passed": False, "status": "draft_not_found", "path": str(draft_path)}
    draft_tokens = tokenize(extract_trigger_text(draft_path))
    if not draft_tokens:
        return {
            "passed": False,
            "status": "no_trigger_text",
            "path": str(draft_path),
            "message": "draft has no ## When to use section and no trigger_phrases",
        }
    matches: list[dict] = []
    for sid, path in skills.items():
        other_tokens = tokenize(extract_trigger_text(path))
        if not other_tokens:
            continue
        score = jaccard(draft_tokens, other_tokens)
        if score >= warn:
            matches.append({
                "skill_id": sid,
                "jaccard": round(score, 4),
                "level": "block" if score >= block else "warn",
                "shared_tokens": sorted(draft_tokens & other_tokens)[:10],
            })
    matches.sort(key=lambda m: -m["jaccard"])
    blocked = [m for m in matches if m["level"] == "block"]
    return {
        "passed": not blocked,
        "status": "ok" if not blocked else "trigger_collision",
        "draft_path": str(draft_path),
        "block_threshold": block,
        "warn_threshold": warn,
        "top_matches": matches[:3],
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--draft", type=str, help="path to a draft SKILL.md")
    g.add_argument("--all", action="store_true",
                   help="audit pairwise matrix over the whole catalog")
    p.add_argument("--block", type=float, default=DEFAULT_BLOCK,
                   help="block threshold (default 0.70)")
    p.add_argument("--warn", type=float, default=DEFAULT_WARN,
                   help="warn threshold (default 0.50)")
    return p.parse_args()


def main() -> int:
    try:
        args = parse_args()
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    try:
        skills = discover_all_skills()
        if not skills:
            sys.stderr.write("trigger_uniqueness: no skills discovered\n")
            return 2
        if args.draft:
            result = check_draft_against_catalog(
                Path(args.draft), skills, args.block, args.warn,
            )
        else:
            result = check_pairwise(skills, args.block, args.warn)
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0 if result["passed"] else 1
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"trigger_uniqueness: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
