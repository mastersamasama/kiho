#!/usr/bin/env python3
"""
catalog_fit.py — Gate 14: catalog-fit scorer (v5.14, hardened in v5.16).

Given a new skill's draft description and its target domain, checks that the
description overlaps the domain's routing-description by at least one
substantive keyword. Substantive = not a stop word, >=3 characters, present in
the domain's routing-description keyword list.

Reads the routing block from skills/CATALOG.md. The routing block is a YAML
fenced block inside HTML-comment fences (<!-- routing-block-start --> ...
<!-- routing-block-end -->) at the top of CATALOG.md, containing per-domain
routing-descriptions. This script does not parse YAML — it uses a simple
regex extractor to avoid pulling PyYAML as a dependency.

v5.16 hardening: when the routing block is missing or empty, exit 1 with
status: routing_block_missing (was: silent pass in v5.14-v5.15). Regression
test for the silent-bug that kept Gate 14 a no-op since v5.14. Reads the
v5.16 'routing-description' field first, falls back to the v5.14
'description' field for backward compatibility.

Grounding: AgentSkillOS arXiv 2603.02176 (hierarchical catalogs beat flat),
kiho v5.14 H3, v5.16 Primitive 1 (hierarchical walk-catalog).

Usage:
    catalog_fit.py --description <text-or-file> --domain <name>
                   [--catalog <path>] [--min-overlap 1]

Exit codes (0/1/2/3 per v5.15.2 convention):
    0 — fit (overlap >= threshold)
    1 — mis-fit (overlap below threshold) OR routing block missing
    2 — usage error: catalog path missing / domain not in block
    3 — internal error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


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


def extract_routing_block(catalog_text: str) -> dict[str, dict[str, str]]:
    """Pull the yaml-fenced routing block from CATALOG.md and parse it into
    {domain: {description, ...}}. Uses a simple regex-driven parser."""
    match = re.search(
        r"```yaml\s*\n\s*routing:\s*\n(.*?)\n```",
        catalog_text,
        re.DOTALL,
    )
    if not match:
        return {}
    body = match.group(1)

    domains: dict[str, dict[str, str]] = {}
    current_domain = ""
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        # Top-level: "  _meta:"
        m = re.match(r"^  (\w[\w_-]*)\s*:\s*$", line)
        if m:
            current_domain = m.group(1)
            domains[current_domain] = {}
            continue
        # Field under domain: "    description: \"...\""
        m = re.match(r"^    (\w[\w_-]*)\s*:\s*(.*)$", line)
        if m and current_domain:
            key, val = m.group(1), m.group(2).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            domains[current_domain][key] = val
    return domains


def tokenize(text: str) -> set[str]:
    """Lowercase word tokens >=3 chars, stop words removed."""
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    return {t for t in tokens if t not in STOP_WORDS}


def score_fit(description: str, routing_description: str) -> dict[str, object]:
    desc_tokens = tokenize(description)
    route_tokens = tokenize(routing_description)
    overlap = desc_tokens & route_tokens
    return {
        "desc_tokens": len(desc_tokens),
        "route_tokens": len(route_tokens),
        "overlap_count": len(overlap),
        "overlap_tokens": sorted(overlap),
        "desc_only_sample": sorted(list(desc_tokens - route_tokens))[:10],
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--description", required=True,
                   help="new skill description (literal text or path to file)")
    p.add_argument("--domain", required=True,
                   help="target catalog domain (e.g., _meta, core, kb)")
    p.add_argument("--catalog", default="skills/CATALOG.md",
                   help="path to skills/CATALOG.md")
    p.add_argument("--min-overlap", type=int, default=1,
                   help="minimum keyword overlap required to pass (default 1)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Resolve description
    desc_arg = args.description
    if Path(desc_arg).is_file():
        description = Path(desc_arg).read_text(encoding="utf-8")
    else:
        description = desc_arg

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        sys.stderr.write(f"CATALOG not found: {catalog_path}\n")
        return 2

    catalog_text = catalog_path.read_text(encoding="utf-8")
    domains = extract_routing_block(catalog_text)

    # v5.16 hardening: explicit error when the routing block is missing.
    # Previously this path silently returned exit 2 "domain not found" on
    # an empty domains dict, which skill-create could mis-classify as a
    # usage error and skip. v5.16 emits status: routing_block_missing and
    # exits 1 (policy violation) so Gate 14 loudly reports the bug.
    if not domains:
        result = {
            "status": "routing_block_missing",
            "passed": False,
            "domain": args.domain,
            "min_overlap": args.min_overlap,
            "message": (
                "CATALOG.md has no routing block. Run bin/routing_gen.py "
                "to populate it. Gate 14 cannot evaluate without the block."
            ),
        }
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 1

    if args.domain not in domains:
        sys.stderr.write(
            f"domain '{args.domain}' not found in CATALOG routing block; "
            f"known: {sorted(domains)}\n"
        )
        return 2

    # v5.16 prefers 'routing-description'; v5.14 'description' kept as fallback.
    route_desc = (
        domains[args.domain].get("routing-description")
        or domains[args.domain].get("description", "")
    )
    if not route_desc:
        sys.stderr.write(
            f"domain '{args.domain}' has no routing-description\n"
        )
        return 2

    result = score_fit(description, route_desc)
    passed = int(result["overlap_count"]) >= args.min_overlap  # type: ignore[arg-type]
    result["domain"] = args.domain
    result["min_overlap"] = args.min_overlap
    result["passed"] = passed
    result["status"] = "fit" if passed else "misfit"
    sys.stdout.write(json.dumps(result, indent=2))
    sys.stdout.write("\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
