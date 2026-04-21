#!/usr/bin/env python3
"""
experience_pool_render.py — Render `$COMPANY_ROOT/company/wiki/experience-pool.md`
from `cross-project-lessons/*.md` (v5.19.5 N3).

Invoked by the `experience-pool` skill's `op=render-company-pool`. Reads every
sanitized lesson under `company/wiki/cross-project-lessons/`, groups by the
`topic:` frontmatter scalar, dedupes within a topic by char-3-gram Jaccard
similarity > 0.85 (same 0.85 threshold as `kb-promote` dedup, matching the
v5.19 pattern doctrine), sorts each topic group by confidence desc +
updated_at desc, and emits one synthesized markdown file.

Output frontmatter identifies the file as `generated_by: bin/experience_pool_render.py`
so kb-manager's `op=update` receipt trail includes the provenance.

Exit codes (per v5.15.2):
    0 — rendered (or no-lessons no-op)
    1 — drift (not used here; reserved)
    2 — usage error
    3 — internal error

Dedup algorithm:
    1. Tokenize each lesson body to the set of 3-character n-grams (case-folded).
    2. For each topic group, sorted by (confidence desc, updated_at desc, slug),
       greedy-add each candidate to a kept list; skip if Jaccard(candidate, any
       kept) > 0.85.
    3. Kept list is the rendered order for that topic.

Char-ngram Jaccard is the established kiho v5.19 deterministic similarity
baseline (no ML, stdlib-only). See `skills/_meta/skill-create/scripts/similarity_scan.py`
for a precedent.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _scalar(fm_block: str, field: str) -> str | None:
    """Extract a single-line scalar field from a YAML-ish frontmatter block."""
    m = re.search(
        rf"^\s*{re.escape(field)}\s*:\s*(.+?)\s*$", fm_block, re.MULTILINE
    )
    if not m:
        return None
    v = m.group(1).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    if v == "" or v.startswith("["):
        return None
    return v


def _parse_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter-block-or-empty, body-without-frontmatter)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def _char_ngram_set(s: str, n: int = 3) -> frozenset[str]:
    """Lowercased whitespace-collapsed char n-grams; empty strings yield ()."""
    s = re.sub(r"\s+", " ", s.lower().strip())
    if len(s) < n:
        return frozenset()
    return frozenset(s[i:i + n] for i in range(len(s) - n + 1))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _collect_lessons(company_root: Path) -> tuple[list[dict], Path]:
    """Walk cross-project-lessons/, return (entries, lessons_dir_path)."""
    lessons_dir = company_root / "company" / "wiki" / "cross-project-lessons"
    entries: list[dict] = []
    if not lessons_dir.exists() or not lessons_dir.is_dir():
        return entries, lessons_dir
    wiki_root = company_root / "company" / "wiki"
    for path in sorted(lessons_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, body = _parse_frontmatter(text)
        topic = _scalar(fm, "topic") or "uncategorized"
        updated_at = _scalar(fm, "updated_at") or ""
        conf_raw = _scalar(fm, "confidence")
        try:
            confidence = float(conf_raw) if conf_raw is not None else 0.0
        except ValueError:
            confidence = 0.0
        slug = path.relative_to(wiki_root).with_suffix("").as_posix()
        entries.append({
            "slug": slug,
            "topic": topic,
            "updated_at": updated_at,
            "confidence": confidence,
            "ngrams": _char_ngram_set(body),
        })
    return entries, lessons_dir


def _dedup_topic(items: list[dict], threshold: float = 0.85) -> list[dict]:
    """Greedy dedup: keep first item in sorted order; skip subsequent items
    whose Jaccard vs any kept exceeds threshold."""
    # Sort: confidence desc, updated_at desc (ISO strings compare correctly), slug asc
    items = sorted(
        items,
        key=lambda e: (-e["confidence"], "" if not e["updated_at"] else e["updated_at"], e["slug"]),
    )
    # For updated_at we want desc; flipped via reverse-tuple:
    items = sorted(
        items,
        key=lambda e: (-e["confidence"], _neg_str(e["updated_at"]), e["slug"]),
    )
    kept: list[dict] = []
    for cand in items:
        is_dup = any(_jaccard(cand["ngrams"], k["ngrams"]) > threshold for k in kept)
        if not is_dup:
            kept.append(cand)
    return kept


def _neg_str(s: str) -> tuple:
    """Produce a sort key that inverts ascending string order to descending."""
    # Two entries where s1 > s2 (lexicographic) should have neg_str(s1) < neg_str(s2).
    # Trick: encode each char as 0xFFFF - ord(c) so that the original max becomes min.
    return tuple(0xFFFF - ord(c) for c in s)


def _render(dedup_per_topic: dict[str, list[dict]]) -> str:
    lines: list[str] = []
    lines.append("---")
    lines.append("title: experience-pool")
    lines.append("scope: cross-project")
    lines.append("generated_by: bin/experience_pool_render.py")
    lines.append(
        f"generated_at: {_dt.datetime.now(_dt.timezone.utc).isoformat(timespec='seconds')}"
    )
    lines.append("---")
    lines.append("")
    lines.append("# experience-pool")
    lines.append("")
    lines.append("Synthesized view of lessons promoted to company tier.")
    lines.append(
        "Source: `company/wiki/cross-project-lessons/*.md`. Regenerate via "
        "`bin/experience_pool_render.py` (see `skills/core/knowledge/experience-pool` "
        "op=render-company-pool)."
    )
    lines.append("")
    for topic in sorted(dedup_per_topic):
        items = dedup_per_topic[topic]
        if not items:
            continue
        lines.append(f"## {topic}")
        lines.append("")
        for item in items:
            conf_str = f"{item['confidence']:.2f}" if item["confidence"] > 0 else "—"
            ua_str = item["updated_at"] or "—"
            lines.append(
                f"- [[{item['slug']}]] — confidence {conf_str} · updated {ua_str}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Render experience-pool.md from cross-project-lessons/*",
        epilog="Exit codes: 0 ok/no-lessons, 2 usage, 3 internal.",
    )
    p.add_argument(
        "--company-root",
        default=os.environ.get("COMPANY_ROOT", ""),
        help="Company root. Default: $COMPANY_ROOT env.",
    )
    p.add_argument(
        "--out",
        default="",
        help=(
            "Output path (default: <company-root>/company/wiki/experience-pool.md)"
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rendered markdown to stdout; do not write.",
    )
    p.add_argument(
        "--dedup-threshold",
        type=float,
        default=0.85,
        help="Jaccard threshold (default 0.85, matching kb-promote dedup).",
    )
    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    if not args.company_root:
        print(
            json.dumps({"status": "error", "error": "--company-root not set and $COMPANY_ROOT empty"}),
            file=sys.stderr,
        )
        return 2

    company_root = Path(args.company_root).resolve()
    if not company_root.exists() or not company_root.is_dir():
        print(
            json.dumps({"status": "error", "error": f"{company_root} is not a directory"}),
            file=sys.stderr,
        )
        return 2

    try:
        entries, lessons_dir = _collect_lessons(company_root)
        if not entries:
            print(json.dumps({
                "status": "no_lessons",
                "detail": f"{lessons_dir} missing or empty",
                "lessons_dir": str(lessons_dir),
            }))
            return 0

        by_topic: dict[str, list[dict]] = defaultdict(list)
        for e in entries:
            by_topic[e["topic"]].append(e)
        dedup_per_topic = {
            topic: _dedup_topic(items, args.dedup_threshold)
            for topic, items in by_topic.items()
        }

        content = _render(dedup_per_topic)
        total_in = sum(len(v) for v in by_topic.values())
        total_out = sum(len(v) for v in dedup_per_topic.values())

        if args.dry_run:
            sys.stdout.write(content)
            report = {
                "status": "ok",
                "dry_run": True,
                "topics": len(dedup_per_topic),
                "lessons_scanned": total_in,
                "lessons_after_dedup": total_out,
            }
            print(json.dumps(report), file=sys.stderr)
            return 0

        out_path = (
            Path(args.out)
            if args.out
            else company_root / "company" / "wiki" / "experience-pool.md"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")

        print(json.dumps({
            "status": "ok",
            "out": str(out_path),
            "chars": len(content),
            "topics": len(dedup_per_topic),
            "lessons_scanned": total_in,
            "lessons_after_dedup": total_out,
            "dedup_dropped": total_in - total_out,
        }))
        return 0
    except Exception as exc:  # pragma: no cover — defensive
        print(json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
