#!/usr/bin/env python3
"""
routing_gen.py — Generate the routing block inside skills/CATALOG.md.

Walks every SKILL.md in skills/<domain>/*/ (flat layout) and
skills/<domain>/<sub_domain>/*/ (hierarchical layout, post-Stage D),
groups skills by top-level domain + optional sub-domain, and emits a YAML
routing block inside HTML-comment fences at the top of CATALOG.md.

The routing-description per domain is generated via TF-IDF over the
domain's aggregated skill descriptions, ranked against the other domains
as the negative corpus. Top-10 substantive keywords form the
routing-description.

parent_of lists are the sorted skill IDs in each domain / sub-domain.

Idempotent regen: only content between <!-- routing-block-start --> and
<!-- routing-block-end --> fences is replaced. A <!-- human-edited -->
marker inside the fences instructs regen to preserve the block unchanged.

Grounding: v5.16 Primitive 1 (hierarchical walk-catalog) in the kiho plan
at C:\\Users\\wky\\.claude\\plans\\bright-toasting-diffie.md v5.16 section.

Usage:
    routing_gen.py [--catalog <path>] [--dry-run]

Exit codes (0/1/2/3 per v5.15.2 convention):
    0 — routing block regenerated or dry-run completed successfully
    1 — policy violation: no skills discovered OR human-edited block preserved
    2 — usage error: catalog path missing or unreadable
    3 — internal error
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
CATALOG_PATH = SKILLS_DIR / "CATALOG.md"

ROUTING_BLOCK_START = "<!-- routing-block-start -->"
ROUTING_BLOCK_END = "<!-- routing-block-end -->"
HUMAN_EDITED_MARKER = "<!-- human-edited -->"

# Reused from catalog_fit.py for consistency. Do not diverge — every v5.16
# script that tokenizes descriptions MUST share this set.
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

DOMAIN_ORDER = ["_meta", "core", "kb", "memory", "engineering"]

# Hand-curated routing-descriptions per domain. TF-IDF over small per-domain
# corpora produces noisy keywords (e.g., "needs; triggers; around; place")
# that defeat Gate 14's catalog-fit check. The CEO-reviewed overrides below
# anchor each domain on its canonical vocabulary. TF-IDF is used only as a
# fallback when a domain lacks an override entry.
#
# To refresh an override: edit the string here and re-run routing_gen.py.
# parent_of lists always regenerate fresh from disk — overrides apply only
# to the routing-description string.
#
# Seeded 2026-04-15 during v5.16 Stage A (kiho-plugin plan bright-toasting-diffie).
ROUTING_DESCRIPTION_OVERRIDES: dict[str, str] = {
    "_meta": (
        "skill authoring; lifecycle; creation; discovery; improvement; "
        "specialization; deprecation; soul override; experience learning; "
        "meta-operations; catalog management"
    ),
    "core": (
        "orchestration; ceo operations; planning; deliberation; recruitment; "
        "research; session inspection; state access; committee voting; "
        "interview simulation; experience pool; org sync; harness setup"
    ),
    "kb": (
        "knowledge base; wiki management; add pages; update pages; "
        "delete pages; search; lint; promote; initialize; ingest raw documents; "
        "retention; kb-manager operations"
    ),
    "memory": (
        "agent memory; observations; reflections; lessons; todos; "
        "consolidation; cross-agent learning; periodic reflection; "
        "memory read write; drift detection"
    ),
    "engineering": (
        "spec-driven engineering; kiro runner; requirements; design; tasks; "
        "three-stage ritual; ears format; feature bugfix refactor vibe modes; "
        "engineering lead delegation"
    ),
}


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens >=3 chars, stop words removed. Returns a list
    (not a set) so TF computation can count term frequency."""
    raw = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    return [t for t in raw if t not in STOP_WORDS]


def extract_frontmatter_field(skill_md: Path, field: str) -> str:
    """Pull a single frontmatter field value from a SKILL.md. Empty string
    if missing. Simple single-line key: value parser — mirrors
    catalog_gen.py's extract_frontmatter semantics."""
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        colon_idx = line.find(":")
        if colon_idx == -1:
            continue
        key = line[:colon_idx].strip()
        if key == field:
            return line[colon_idx + 1:].strip().strip('"').strip("'")
    return ""


def read_skill_id(skill_dir: Path) -> str:
    """Read the .skill_id sidecar file; empty string if missing."""
    sid_path = skill_dir / ".skill_id"
    if sid_path.exists():
        return sid_path.read_text(encoding="utf-8").strip()
    return ""


def discover_skills_by_domain() -> dict[str, list[dict]]:
    """Walk skills/<domain>/{<sub>/}?<skill>/SKILL.md and group by top-level
    domain. Supports both flat (pre-Stage D) and hierarchical (post-Stage D)
    layouts.

    Flat: skills/kb/kb-add/SKILL.md -> domain=kb, sub_domain=None
    Hierarchical: skills/core/harness/kiho/SKILL.md -> domain=core, sub_domain=harness
    """
    result: dict[str, list[dict]] = {d: [] for d in DOMAIN_ORDER}
    for domain in DOMAIN_ORDER:
        domain_dir = SKILLS_DIR / domain
        if not domain_dir.is_dir():
            continue
        for child in sorted(domain_dir.iterdir()):
            if not child.is_dir():
                continue
            flat_skill = child / "SKILL.md"
            if flat_skill.is_file():
                sid = read_skill_id(child)
                desc = extract_frontmatter_field(flat_skill, "description")
                name = extract_frontmatter_field(flat_skill, "name") or child.name
                if sid:
                    result[domain].append({
                        "id": sid,
                        "name": name,
                        "description": desc,
                        "sub_domain": None,
                    })
                continue
            # Hierarchical: sub-domain dirs under child
            for grandchild in sorted(child.iterdir()):
                if not grandchild.is_dir():
                    continue
                nested_skill = grandchild / "SKILL.md"
                if not nested_skill.is_file():
                    continue
                sid = read_skill_id(grandchild)
                desc = extract_frontmatter_field(nested_skill, "description")
                name = extract_frontmatter_field(nested_skill, "name") or grandchild.name
                if sid:
                    result[domain].append({
                        "id": sid,
                        "name": name,
                        "description": desc,
                        "sub_domain": child.name,
                    })
    return result


def compute_tfidf_keywords(
    skills_by_domain: dict[str, list[dict]],
    top_k: int = 10,
) -> dict[str, list[str]]:
    """TF-IDF ranking: each domain is a 'document' of concatenated skill
    descriptions. Ranks terms per domain against the other domains as the
    negative corpus. Returns top_k substantive keywords per domain.

    Score = TF(term, domain) * (log((N+1) / (DF(term)+1)) + 1.0)

    The +1 smoothing prevents division issues and guarantees positive IDF
    for any term. Ties broken alphabetically for determinism.
    """
    domain_tokens: dict[str, list[str]] = {}
    for domain, skills in skills_by_domain.items():
        if not skills:
            continue
        text = " ".join(s["description"] for s in skills)
        domain_tokens[domain] = tokenize(text)

    num_domains = len(domain_tokens)
    if num_domains == 0:
        return {}

    df: Counter = Counter()
    for tokens in domain_tokens.values():
        for term in set(tokens):
            df[term] += 1

    result: dict[str, list[str]] = {}
    for domain, tokens in domain_tokens.items():
        tf = Counter(tokens)
        scored: list[tuple[str, float]] = []
        for term, count in tf.items():
            idf = math.log((num_domains + 1) / (df[term] + 1)) + 1.0
            scored.append((term, count * idf))
        scored.sort(key=lambda x: (-x[1], x[0]))
        result[domain] = [t for t, _ in scored[:top_k]]
    return result


def render_routing_block(
    skills_by_domain: dict[str, list[dict]],
    keywords_by_domain: dict[str, list[str]],
) -> str:
    """Render the YAML routing block wrapped in HTML-comment fences."""
    lines: list[str] = [
        ROUTING_BLOCK_START,
        "",
        "```yaml",
        "routing:",
    ]
    for domain in DOMAIN_ORDER:
        skills = skills_by_domain.get(domain, [])
        if not skills:
            continue
        # Prefer hand-curated override over TF-IDF when present
        override = ROUTING_DESCRIPTION_OVERRIDES.get(domain)
        if override:
            desc = override
        else:
            keywords = keywords_by_domain.get(domain, [])
            desc = "; ".join(keywords) if keywords else f"{domain} skills"
        parent_ids = sorted(s["id"] for s in skills)
        inline_ids = ", ".join(parent_ids)
        lines.append(f"  {domain}:")
        lines.append(f"    routing-description: \"{desc}\"")
        lines.append(f"    parent_of: [{inline_ids}]")
        # Emit sub_domains block only when hierarchy is present
        subs: dict[str, list[str]] = {}
        for s in skills:
            sub = s.get("sub_domain")
            if sub:
                subs.setdefault(sub, []).append(s["id"])
        if subs:
            lines.append("    sub_domains:")
            for sub_name in sorted(subs):
                sub_ids = sorted(subs[sub_name])
                lines.append(f"      {sub_name}:")
                lines.append(f"        parent_of: [{', '.join(sub_ids)}]")
    lines.append("```")
    lines.append("")
    lines.append(ROUTING_BLOCK_END)
    return "\n".join(lines)


def insert_routing_block(catalog_text: str, block: str) -> tuple[str, str]:
    """Insert or replace the routing block in CATALOG.md.

    Returns (updated_text, action) where action is one of:
      - "replaced": existing fences found, content replaced
      - "inserted": no existing fences, block inserted
      - "preserved": human-edited marker present, block left unchanged
    """
    fence_re = re.compile(
        re.escape(ROUTING_BLOCK_START) + r".*?" + re.escape(ROUTING_BLOCK_END),
        re.DOTALL,
    )
    match = fence_re.search(catalog_text)
    if match:
        existing_block = match.group(0)
        if HUMAN_EDITED_MARKER in existing_block:
            sys.stderr.write(
                f"routing_gen: preserving human-edited routing block "
                f"(remove {HUMAN_EDITED_MARKER} marker to regenerate)\n"
            )
            return catalog_text, "preserved"
        updated = catalog_text[:match.start()] + block + catalog_text[match.end():]
        return updated, "replaced"
    first_heading = re.search(r"^## ", catalog_text, re.MULTILINE)
    if first_heading:
        pos = first_heading.start()
        updated = catalog_text[:pos] + block + "\n\n" + catalog_text[pos:]
        return updated, "inserted"
    updated = catalog_text.rstrip() + "\n\n" + block + "\n"
    return updated, "inserted"


def regenerate_catalog_routing_block(catalog_path: Path, dry_run: bool = False) -> int:
    if not catalog_path.exists():
        sys.stderr.write(f"routing_gen: CATALOG not found: {catalog_path}\n")
        return 2

    skills_by_domain = discover_skills_by_domain()
    total = sum(len(v) for v in skills_by_domain.values())
    if total == 0:
        sys.stderr.write("routing_gen: no skills discovered in skills/ tree\n")
        return 1

    keywords = compute_tfidf_keywords(skills_by_domain)
    block = render_routing_block(skills_by_domain, keywords)

    catalog_text = catalog_path.read_text(encoding="utf-8")
    updated, action = insert_routing_block(catalog_text, block)

    if dry_run:
        sys.stdout.write(block + "\n")
        sys.stdout.write(f"\nrouting_gen: dry-run action={action} "
                         f"total_skills={total}\n")
        return 0

    if action == "preserved":
        return 1

    if updated != catalog_text:
        # Atomic write: write to a sibling temp file, then rename.
        # Path.replace() is atomic on POSIX and Windows when the source
        # and destination are on the same filesystem — which is guaranteed
        # here because the temp file sits next to the target.
        # This closes the race window where a concurrent reader could see
        # CATALOG.md without the routing block between catalog_gen.py's
        # initial write and routing_gen.py's rewrite.
        tmp_path = catalog_path.with_suffix(catalog_path.suffix + ".tmp")
        tmp_path.write_text(updated, encoding="utf-8")
        tmp_path.replace(catalog_path)
        sys.stdout.write(
            f"routing_gen: action={action} total_skills={total} "
            f"catalog={catalog_path} (atomic)\n"
        )
    else:
        sys.stdout.write(
            f"routing_gen: action=no_change total_skills={total}\n"
        )
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", default=str(CATALOG_PATH),
                   help="path to skills/CATALOG.md")
    p.add_argument("--dry-run", action="store_true",
                   help="emit block to stdout, do not write file")
    return p.parse_args()


def main() -> int:
    try:
        args = parse_args()
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    try:
        return regenerate_catalog_routing_block(
            Path(args.catalog), dry_run=args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001 — exit-code convention wants a catch-all
        sys.stderr.write(f"routing_gen: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
