#!/usr/bin/env python3
"""
facet_walk.py — v5.16 faceted skill retrieval (replaces flat lexical scoring).

Walks the CATALOG.md routing block + hierarchical sub-catalogs using
three deterministic facet filters — capability, domain, topic_tags — to
produce a candidate set of at most MAX_CANDIDATES (default 10). Falls
back to flat lexical scoring ONLY when every facet is unresolvable.

Procedure:
  1. Parse query tokens. Map verb keywords -> capability facet via
     deterministic rules (no LLM).
  2. Map domain keywords -> domain facet (from routing-description
     lookup).
  3. Map remaining content keywords -> topic facet.
  4. Walk routing block: start with full catalog, intersect by each
     present facet, producing a candidate set.
  5. Enforce HARD_CEILING (default 10). If candidate set > HARD_CEILING
     after every applied facet, emit status: underspecified with the
     list of facets that would help narrow. Exit 1 in --gate-mode, or
     return a ranked-ish fallback in --best-effort mode.
  6. Within the candidate set, apply lexical scoring (word overlap) and
     return the top-N.

This script implements the v5.16 Primitive 3 retrieval engine. It is
deterministic, stateless, and stdlib-only.

Grounding: v5.16 plan Primitive 3 + Gate 22 attention-budget framing.
arXiv 2601.04748 §5.2 phase transition at |S|<=20.

Usage:
    facet_walk.py --query "update a skill body to fix a bug"
                  [--capability <verb>] [--domain <name>]
                  [--topic-tag <tag>] [--limit 3]
                  [--hard-ceiling 10] [--gate-mode]
                  [--catalog <path>]

Exit codes (0/1/2/3):
    0 — candidates returned (either facet-filtered or lexical fallback)
    1 — --gate-mode and the candidate set is >hard-ceiling (underspecified)
    2 — usage error: CATALOG missing, query missing
    3 — internal error
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent.parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
CATALOG_PATH = SKILLS_DIR / "CATALOG.md"
TAXONOMY_PATH = PLUGIN_ROOT / "references" / "capability-taxonomy.md"
VOCAB_PATH = PLUGIN_ROOT / "references" / "topic-vocabulary.md"

DEFAULT_HARD_CEILING = 10
DEFAULT_LIMIT = 3

# v5.19.5 N4: revisit-trigger instrumentation for the semantic-embedding-cache
# deferral (storage-tech-stack.md §6 trigger #1). Append one JSONL line per
# ceiling-hit so catalog_walk_audit.py can compute a rolling 30d hit count.
TRIGGER_LOG = PLUGIN_ROOT / ".kiho" / "state" / "tier3" / "semantic-embedding-triggers.jsonl"


def _log_ceiling_hit(query: str, candidate_count: int, hard_ceiling: int) -> None:
    """Best-effort append to semantic-embedding-triggers.jsonl. Errors are
    swallowed — instrumentation MUST NOT break gate-mode behavior."""
    try:
        TRIGGER_LOG.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "query": query,
            "candidate_count": candidate_count,
            "hard_ceiling": hard_ceiling,
        }
        with TRIGGER_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False))
            f.write("\n")
    except OSError:
        pass

DOMAIN_ORDER = ["_meta", "core", "kb", "memory", "engineering"]

# Stop-word set: same as catalog_fit.py + routing_gen.py
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

# Deterministic verb -> capability mapping. Multiple synonyms map to one verb.
# Matched against the query tokens; first match wins per position.
CAPABILITY_KEYWORDS: dict[str, list[str]] = {
    "create":       ["create", "draft", "generate", "produce", "author", "write", "make", "build", "bootstrap", "recruit", "derive", "add"],
    "read":         ["find", "search", "lookup", "query", "inspect", "view", "read", "show", "list", "discover", "retrieve"],
    "update":       ["update", "improve", "fix", "patch", "mutate", "consolidate", "promote", "sync", "correct", "amend", "override", "apply"],
    "delete":       ["delete", "deprecate", "retire", "remove", "archive"],
    "evaluate":     ["evaluate", "score", "lint", "validate", "audit", "check", "simulate", "verify", "review"],
    "orchestrate":  ["orchestrate", "route", "delegate", "decompose", "plan", "coordinate", "dispatch"],
    "communicate":  ["notify", "broadcast", "announce", "escalate", "send", "message"],
    "decide":       ["decide", "vote", "adjudicate", "choose"],
}


def tokenize(text: str) -> set[str]:
    raw = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    return {t for t in raw if t not in STOP_WORDS}


def load_capability_set() -> set[str]:
    if not TAXONOMY_PATH.exists():
        return set()
    text = TAXONOMY_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"^### `(\w+)`", text, re.MULTILINE))


def load_vocab_set() -> set[str]:
    if not VOCAB_PATH.exists():
        return set()
    text = VOCAB_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"^### `([\w-]+)`", text, re.MULTILINE))


def parse_routing_block(catalog_text: str) -> dict[str, dict]:
    """Extract the routing block with its routing-description, parent_of,
    and sub_domains. Returns:
        {
          "_meta": {
            "routing-description": "...",
            "parent_of": ["sk-X", ...],
            "sub_domains": {"harness": ["sk-Y", ...]}
          },
          ...
        }
    """
    m = re.search(
        r"```yaml\s*\n\s*routing:\s*\n(.*?)\n```",
        catalog_text,
        re.DOTALL,
    )
    if not m:
        return {}
    body = m.group(1)

    result: dict[str, dict] = {}
    current_domain = ""
    current_sub: str | None = None
    in_sub_domains_block = False

    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        m_dom = re.match(r"^  (\w[\w_-]*)\s*:\s*$", line)
        if m_dom:
            current_domain = m_dom.group(1)
            result[current_domain] = {
                "routing-description": "",
                "parent_of": [],
                "sub_domains": {},
            }
            current_sub = None
            in_sub_domains_block = False
            continue

        m_field = re.match(r"^    (\w[\w_-]*)\s*:\s*(.*)$", line)
        if m_field and current_domain:
            key = m_field.group(1)
            val = m_field.group(2).strip()
            if key == "sub_domains":
                in_sub_domains_block = True
                current_sub = None
                continue
            in_sub_domains_block = False
            if key == "routing-description":
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                result[current_domain]["routing-description"] = val
            elif key == "parent_of":
                result[current_domain]["parent_of"] = _parse_inline_list(val)
            continue

        m_sub = re.match(r"^      (\w[\w_-]*)\s*:\s*$", line)
        if m_sub and current_domain and in_sub_domains_block:
            current_sub = m_sub.group(1)
            result[current_domain]["sub_domains"][current_sub] = []
            continue

        m_subfield = re.match(r"^        (\w[\w_-]*)\s*:\s*(.*)$", line)
        if m_subfield and current_domain and current_sub is not None:
            key = m_subfield.group(1)
            val = m_subfield.group(2).strip()
            if key == "parent_of":
                result[current_domain]["sub_domains"][current_sub] = _parse_inline_list(val)
            continue

    return result


def _parse_inline_list(val: str) -> list[str]:
    val = val.strip()
    if not (val.startswith("[") and val.endswith("]")):
        return []
    inner = val[1:-1].strip()
    if not inner:
        return []
    return [t.strip().strip('"').strip("'") for t in inner.split(",")]


def read_skill_id(skill_dir: Path) -> str:
    sid_path = skill_dir / ".skill_id"
    if sid_path.exists():
        return sid_path.read_text(encoding="utf-8").strip()
    return ""


def extract_skill_metadata(skill_md: Path) -> dict:
    """Read frontmatter name + description + metadata.kiho.capability + topic_tags."""
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    fm = m.group(1)
    meta = {"name": "", "description": "", "capability": "", "topic_tags": []}
    for line in fm.splitlines():
        colon_idx = line.find(":")
        if colon_idx == -1:
            continue
        key = line[:colon_idx].strip()
        val = line[colon_idx + 1:].strip().strip('"').strip("'")
        if key == "name" and not meta["name"]:
            meta["name"] = val
        elif key == "description" and not meta["description"]:
            meta["description"] = val
    # Capability + topic_tags live under metadata.kiho
    cap_m = re.search(
        r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+capability:\s*(\w+)",
        fm,
        re.MULTILINE,
    )
    if cap_m:
        meta["capability"] = cap_m.group(1)
    tags_m = re.search(
        r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+topic_tags:\s*\[([^\]]*)\]",
        fm,
        re.MULTILINE,
    )
    if tags_m:
        raw = tags_m.group(1).strip()
        meta["topic_tags"] = [t.strip() for t in raw.split(",") if t.strip()]
    return meta


def discover_disk_skills() -> dict[str, dict]:
    """Return {skill_id: metadata} for every SKILL.md on disk."""
    result: dict[str, dict] = {}
    for domain in DOMAIN_ORDER:
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
                    md = extract_skill_metadata(flat)
                    md["id"] = sid
                    md["domain"] = domain
                    md["sub_domain"] = None
                    md["path"] = str(flat.relative_to(PLUGIN_ROOT)).replace("\\", "/")
                    result[sid] = md
                continue
            for grand in sorted(child.iterdir()):
                if not grand.is_dir():
                    continue
                nested = grand / "SKILL.md"
                if nested.is_file():
                    sid = read_skill_id(grand)
                    if sid:
                        md = extract_skill_metadata(nested)
                        md["id"] = sid
                        md["domain"] = domain
                        md["sub_domain"] = child.name
                        md["path"] = str(nested.relative_to(PLUGIN_ROOT)).replace("\\", "/")
                        result[sid] = md
    return result


def infer_capability(query_tokens: set[str], valid_verbs: set[str]) -> str | None:
    """Map query tokens to a capability verb via CAPABILITY_KEYWORDS."""
    for verb, keywords in CAPABILITY_KEYWORDS.items():
        if verb not in valid_verbs:
            continue
        for kw in keywords:
            if kw in query_tokens:
                return verb
    return None


def infer_domain(query_tokens: set[str], routing: dict[str, dict]) -> str | None:
    """Map query tokens to a top-level domain by keyword overlap against
    each domain's routing-description. Winner must beat runner-up by >2x."""
    scores: list[tuple[str, int]] = []
    for dom, info in routing.items():
        rd_tokens = tokenize(info.get("routing-description", ""))
        overlap = len(query_tokens & rd_tokens)
        scores.append((dom, overlap))
    scores.sort(key=lambda x: (-x[1], x[0]))
    if not scores or scores[0][1] == 0:
        return None
    if len(scores) == 1:
        return scores[0][0]
    top, runner = scores[0], scores[1]
    if top[1] >= max(1, 2 * runner[1]):
        return top[0]
    return None


def infer_topic_tags(query_tokens: set[str], valid_vocab: set[str]) -> list[str]:
    """A topic tag is matched if the query literally contains that tag
    (or a close lexical variant). Returns all matching tags."""
    return sorted(query_tokens & valid_vocab)


def lexical_score(query_tokens: set[str], skill_md: dict) -> float:
    """Simple word-overlap score used inside the candidate set."""
    if not query_tokens:
        return 0.0
    desc_tokens = tokenize(skill_md.get("description", "") + " " + skill_md.get("name", ""))
    if not desc_tokens:
        return 0.0
    overlap = len(query_tokens & desc_tokens)
    return overlap / len(query_tokens)


def walk_filter(
    disk: dict[str, dict],
    capability: str | None,
    domain: str | None,
    topic_tags: list[str],
) -> list[dict]:
    """Produce the candidate set by intersecting the three facet filters."""
    candidates = list(disk.values())
    if capability:
        candidates = [s for s in candidates if s.get("capability") == capability]
    if domain:
        candidates = [s for s in candidates if s.get("domain") == domain]
    if topic_tags:
        candidates = [
            s for s in candidates
            if any(t in s.get("topic_tags", []) for t in topic_tags)
        ]
    return candidates


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", required=True, help="natural-language query")
    p.add_argument("--capability", default=None,
                   help="force a capability facet (skip inference)")
    p.add_argument("--domain", default=None,
                   help="force a domain facet (skip inference)")
    p.add_argument("--topic-tag", action="append", default=[],
                   help="force a topic-tag facet (can repeat)")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                   help="max top-N results after lexical scoring")
    p.add_argument("--hard-ceiling", type=int, default=DEFAULT_HARD_CEILING,
                   help="hard candidate-set ceiling before lexical scoring")
    p.add_argument("--gate-mode", action="store_true",
                   help="exit 1 with status: underspecified when ceiling exceeded")
    p.add_argument("--catalog", default=str(CATALOG_PATH),
                   help="override CATALOG.md path")
    return p.parse_args()


def main() -> int:
    try:
        args = parse_args()
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    try:
        catalog_path = Path(args.catalog)
        if not catalog_path.exists():
            sys.stderr.write(f"facet_walk: CATALOG not found: {catalog_path}\n")
            return 2
        routing = parse_routing_block(catalog_path.read_text(encoding="utf-8"))
        if not routing:
            sys.stderr.write("facet_walk: routing block missing\n")
            return 2

        valid_verbs = load_capability_set()
        valid_vocab = load_vocab_set()
        query_tokens = tokenize(args.query)

        cap = args.capability or infer_capability(query_tokens, valid_verbs)
        dom = args.domain or infer_domain(query_tokens, routing)
        tags = list(args.topic_tag) if args.topic_tag else infer_topic_tags(query_tokens, valid_vocab)

        disk = discover_disk_skills()
        candidates = walk_filter(disk, cap, dom, tags)

        if len(candidates) > args.hard_ceiling:
            # Underspecified — suggest narrower facets
            # v5.19.5 N4: log the ceiling hit for semantic-embedding-cache
            # revisit-trigger accounting (see TRIGGER_LOG docstring above).
            _log_ceiling_hit(args.query, len(candidates), args.hard_ceiling)
            facet_hints: list[str] = []
            if not cap:
                facet_hints.append("capability")
            if not dom:
                facet_hints.append("domain")
            if not tags:
                facet_hints.append("topic_tag")
            result = {
                "passed": False,
                "status": "underspecified",
                "query": args.query,
                "applied_facets": {
                    "capability": cap,
                    "domain": dom,
                    "topic_tags": tags,
                },
                "candidate_count": len(candidates),
                "hard_ceiling": args.hard_ceiling,
                "narrowing_hints": facet_hints,
                "message": (
                    f"Candidate set is {len(candidates)} > ceiling {args.hard_ceiling}. "
                    f"Add one of these facets to narrow: {facet_hints}"
                ),
            }
            sys.stdout.write(json.dumps(result, indent=2) + "\n")
            return 1 if args.gate_mode else 0

        # Lexical scoring inside the candidate set
        scored = [
            (lexical_score(query_tokens, s), s) for s in candidates
        ]
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        top = [
            {
                "id": s["id"],
                "name": s.get("name", ""),
                "path": s.get("path", ""),
                "score": round(score, 3),
                "capability": s.get("capability", ""),
                "topic_tags": s.get("topic_tags", []),
                "description_preview": (s.get("description", "")[:100] + "..."),
            }
            for score, s in scored[: args.limit]
        ]
        result = {
            "passed": True,
            "status": "ok",
            "query": args.query,
            "applied_facets": {
                "capability": cap,
                "domain": dom,
                "topic_tags": tags,
            },
            "candidate_count": len(candidates),
            "hard_ceiling": args.hard_ceiling,
            "top_results": top,
        }
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"facet_walk: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
