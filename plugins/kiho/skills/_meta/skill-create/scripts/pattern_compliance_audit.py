#!/usr/bin/env python3
"""
pattern_compliance_audit.py — deterministic P1-P9 pattern-compliance scorer.

Replaces ad-hoc heuristic sweeps with a precise regex-driven detector for the
9 skill-authoring patterns defined in references/skill-authoring-patterns.md
§Review checklist. Scores every SKILL.md against each applicable pattern and
emits JSON (default) or markdown tables for baseline snapshots.

Patterns (criteria from skill-authoring-patterns.md §Review checklist):
    P1 Non-Goals           — ## Non-Goals heading + >=3 bullet items
    P2 Primary-source §    — ## Grounding section with >=2 blockquote-quote pairs
                             (e.g., > **Name ...** *"verbatim"*)
    P3 Failure playbook    — ## Failure playbook section OR >=3 Route [A-Z]
                             sub-sections with decision-tree markers
    P4 Worked examples     — ## Worked examples heading with >=3 sub-examples
    P5 Future-Possibilities — ## Future possibilities section + RFC 2561 mention
                             OR >=2 F[0-9]+ items with trigger condition
    P6 BCP 14 / Do not     — ## BCP 14 declaration OR >=3 uppercase MUST NOT
    P7 MADR 4.0 alternatives — ## Rejected alternatives with >=3 A[0-9]+ entries
    P8 Gate tier ladder    — N/A unless skill introduces gates (tier: keyword)
    P9 Exit-code convention — N/A unless skill ships scripts (scripts/ dir)

Usage:
    pattern_compliance_audit.py --skill <path>
    pattern_compliance_audit.py --all [--catalog-root skills/]
    pattern_compliance_audit.py --all --baseline  # markdown table output
    pattern_compliance_audit.py --all --lenient   # broader regex

Exit codes:
    0 — success (all audited skills at or above threshold)
    1 — policy violation (at least one skill below 6/applicable threshold)
    2 — usage error (missing path, invalid flag)
    3 — internal error (unexpected parse failure)

Grounding: references/skill-authoring-patterns.md v5.15.2 §Review checklist.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CATALOG = PLUGIN_ROOT / "skills"
PASS_THRESHOLD = 6

# Precise pattern detectors
RE_NON_GOALS = re.compile(r"^##\s+(Non-[Gg]oals|What this is NOT|What .* NOT)", re.M)
RE_GROUNDING = re.compile(r"^##\s+Grounding\b", re.M)
RE_BLOCKQUOTE_QUOTE = re.compile(
    r"^[ \t]*>\s+\*\*[^*]+\*\*[^\n]*\*\"[^\"]{10,}\"\*",
    re.M,
)
RE_BLOCKQUOTE_FALLBACK = re.compile(
    r'^[ \t]*>\s+\*\*[^*]+\*\*[^\n]*[\"\*][^\"\n]{15,}[\"\*]',
    re.M,
)
RE_FAILURE_PLAYBOOK = re.compile(
    r"^##\s+Failure playbook\b|\*\*Failure playbook[\s—:-]",
    re.M | re.I,
)
# Route subsections — accept three forms:
#   1. ### Route X (kiho/recruit style)
#   2. ### Route N-A (numbered embedded)
#   3. **Route N-A — ...** (skill-create bullet/prose style)
RE_ROUTE_SUBSECTION = re.compile(
    r"^####?\s+(Route\s+[A-Z0-9]|\d+\.?\d*-[A-Z])"
    r"|\*\*Route\s+[A-Z0-9][\w.-]*\b",
    re.M,
)
RE_DECISION_TREE = re.compile(r"[│├└─]")
RE_WORKED_EXAMPLES = re.compile(r"^##\s+Worked examples\b", re.M | re.I)
RE_EXAMPLE_SUB = re.compile(r"^###\s+Example\s+\d", re.M | re.I)
RE_FUTURE_POSS = re.compile(r"^##\s+Future[\s-][Pp]ossibilit", re.M)
RE_RFC_2561 = re.compile(r"RFC\s*2561", re.I)
RE_FUTURE_ITEM = re.compile(r"^###\s+F\d+\s*[—–-]", re.M)
RE_BCP14 = re.compile(r"^##\s+BCP\s*14\b", re.M | re.I)
RE_MUST_NOT = re.compile(r"\bMUST\s+NOT\b")
RE_REJECTED_ALT = re.compile(r"^##\s+Rejected alternatives\b", re.M | re.I)
RE_ADR_ITEM = re.compile(r"^###\s+A\d+\s*[—–-]", re.M)
RE_GATE_INTRO = re.compile(r"\btier\s*:\s*(tracked|warn|error)\b", re.I)
RE_SCRIPT_MENTION = re.compile(
    r"scripts/[a-z_]+\.py|bin/[a-z_]+\.py|\bpython\s+\S+\.py",
    re.I,
)
RE_WHEN_TO_USE = re.compile(r"^##\s+When to use\b", re.M | re.I)


def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[1], parts[2]
    return "", text


def count_bulleted_items(body: str, start: int, end: int) -> int:
    segment = body[start:end]
    return len(re.findall(r"^[-*]\s+\S", segment, re.M))


def score_pattern(pid: str, body: str, frontmatter: str, skill_dir: Path) -> dict[str, Any]:
    """Return {applicable: bool, passed: bool, evidence: str}."""
    if pid == "P1":
        m = RE_NON_GOALS.search(body)
        if not m:
            return {"applicable": True, "passed": False, "evidence": "no ## Non-Goals heading"}
        next_h = re.search(r"^##\s+\S", body[m.end():], re.M)
        end_pos = m.end() + (next_h.start() if next_h else 2000)
        bullets = count_bulleted_items(body, m.end(), end_pos)
        return {
            "applicable": True,
            "passed": bullets >= 3,
            "evidence": f"Non-Goals with {bullets} bullets",
        }

    if pid == "P2":
        has_grounding = bool(RE_GROUNDING.search(body))
        quote_hits = len(RE_BLOCKQUOTE_QUOTE.findall(body)) + len(
            RE_BLOCKQUOTE_FALLBACK.findall(body)
        )
        return {
            "applicable": True,
            "passed": has_grounding and quote_hits >= 2,
            "evidence": f"Grounding={has_grounding}, blockquote_quotes={quote_hits}",
        }

    if pid == "P3":
        has_section = bool(RE_FAILURE_PLAYBOOK.search(body))
        route_count = len(RE_ROUTE_SUBSECTION.findall(body))
        has_tree = bool(RE_DECISION_TREE.search(body))
        passed = (has_section and (has_tree or route_count >= 2)) or route_count >= 3
        return {
            "applicable": True,
            "passed": passed,
            "evidence": f"playbook={has_section}, routes={route_count}, tree={has_tree}",
        }

    if pid == "P4":
        has_section = bool(RE_WORKED_EXAMPLES.search(body))
        sub_count = len(RE_EXAMPLE_SUB.findall(body))
        return {
            "applicable": True,
            "passed": has_section and sub_count >= 3,
            "evidence": f"section={has_section}, sub_examples={sub_count}",
        }

    if pid == "P5":
        has_section = bool(RE_FUTURE_POSS.search(body))
        has_rfc = bool(RE_RFC_2561.search(body))
        item_count = len(RE_FUTURE_ITEM.findall(body))
        return {
            "applicable": True,
            "passed": has_section and (has_rfc or item_count >= 2),
            "evidence": f"section={has_section}, rfc2561={has_rfc}, items={item_count}",
        }

    if pid == "P6":
        has_section = bool(RE_BCP14.search(body))
        must_not_count = len(RE_MUST_NOT.findall(body))
        return {
            "applicable": True,
            "passed": has_section or must_not_count >= 3,
            "evidence": f"bcp14_decl={has_section}, must_not={must_not_count}",
        }

    if pid == "P7":
        has_section = bool(RE_REJECTED_ALT.search(body))
        adr_count = len(RE_ADR_ITEM.findall(body))
        return {
            "applicable": True,
            "passed": has_section and adr_count >= 3,
            "evidence": f"section={has_section}, adrs={adr_count}",
        }

    if pid == "P8":
        introduces_gates = bool(RE_GATE_INTRO.search(body))
        if not introduces_gates:
            return {"applicable": False, "passed": None, "evidence": "no gates introduced"}
        tiers = set(m.group(1).lower() for m in RE_GATE_INTRO.finditer(body))
        return {
            "applicable": True,
            "passed": len(tiers) >= 1,
            "evidence": f"tiers_used={sorted(tiers)}",
        }

    if pid == "P9":
        scripts_dir = skill_dir / "scripts"
        has_scripts_dir = scripts_dir.is_dir() and any(scripts_dir.iterdir())
        mentions_scripts = bool(RE_SCRIPT_MENTION.search(body))
        if not has_scripts_dir and not mentions_scripts:
            return {"applicable": False, "passed": None, "evidence": "no scripts referenced"}
        return {
            "applicable": True,
            "passed": True,
            "evidence": f"scripts_dir={has_scripts_dir}, mentions={mentions_scripts}",
        }

    return {"applicable": False, "passed": None, "evidence": "unknown pattern"}


def audit_skill(skill_path: Path) -> dict[str, Any]:
    skill_path = skill_path.resolve()
    text = skill_path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    skill_dir = skill_path.parent
    name_match = re.search(r"^name:\s*(\S+)", frontmatter, re.M)
    name = name_match.group(1) if name_match else skill_dir.name

    per_pattern = {}
    applicable = 0
    passed = 0
    for pid in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"):
        result = score_pattern(pid, body, frontmatter, skill_dir)
        per_pattern[pid] = result
        if result["applicable"]:
            applicable += 1
            if result["passed"]:
                passed += 1

    has_w2u = bool(RE_WHEN_TO_USE.search(body))
    rel_path = str(skill_path.relative_to(PLUGIN_ROOT)).replace("\\", "/")

    return {
        "name": name,
        "path": rel_path,
        "applicable": applicable,
        "passed": passed,
        "score": f"{passed}/{applicable}",
        "meets_threshold": passed >= min(PASS_THRESHOLD, applicable),
        "has_when_to_use": has_w2u,
        "patterns": per_pattern,
    }


def format_markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Pattern compliance baseline",
        "",
        "Snapshot of P1-P9 compliance across the kiho skill catalog. Produced by",
        "`skills/_meta/skill-create/scripts/pattern_compliance_audit.py --all --baseline`.",
        "",
        "Pass threshold is 6/applicable per `references/skill-authoring-patterns.md`",
        "§Review checklist. Lazy-graduation policy applies: skills graduate when",
        "touched, not in a mass proactive pass.",
        "",
        "| Skill | Path | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | W2U | Score |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(results, key=lambda x: (-x["passed"], x["path"])):
        cells = []
        for pid in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"):
            p = r["patterns"][pid]
            if not p["applicable"]:
                cells.append("—")
            elif p["passed"]:
                cells.append("✓")
            else:
                cells.append("✗")
        w2u = "✓" if r["has_when_to_use"] else "✗"
        lines.append(
            f"| `{r['name']}` | `{r['path']}` | "
            + " | ".join(cells)
            + f" | {w2u} | **{r['score']}** |"
        )

    total = len(results)
    full = sum(1 for r in results if r["passed"] == r["applicable"])
    passing = sum(1 for r in results if r["meets_threshold"])
    lines.extend([
        "",
        "## Summary",
        "",
        f"- Total skills audited: **{total}**",
        f"- Full compliance (passed == applicable): **{full}**",
        f"- Meets 6/applicable threshold: **{passing}**",
        f"- Below threshold (lazy-graduation targets): **{total - passing}**",
        "",
        "Legend: ✓ = pattern present and compliant, ✗ = pattern missing or non-compliant,",
        "— = pattern not applicable (e.g., P8 for skills that introduce no gates, P9 for",
        "skills that ship no scripts). W2U = `## When to use` section present.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--skill", type=Path, help="audit a single SKILL.md")
    grp.add_argument("--all", action="store_true", help="audit entire catalog")
    ap.add_argument("--catalog-root", type=Path, default=DEFAULT_CATALOG)
    ap.add_argument("--baseline", action="store_true", help="emit markdown baseline")
    ap.add_argument("--lenient", action="store_true", help="reserved; currently a no-op")
    args = ap.parse_args()

    try:
        if args.skill:
            if not args.skill.is_file():
                print(f"error: {args.skill} not found", file=sys.stderr)
                return 2
            result = audit_skill(args.skill)
            print(json.dumps(result, indent=2))
            return 0 if result["meets_threshold"] else 1

        if not args.catalog_root.is_dir():
            print(f"error: catalog root {args.catalog_root} not found", file=sys.stderr)
            return 2
        skill_files = sorted(args.catalog_root.rglob("SKILL.md"))
        results = [audit_skill(p) for p in skill_files]
        if args.baseline:
            print(format_markdown(results))
        else:
            print(json.dumps({"count": len(results), "results": results}, indent=2))
        return 0 if all(r["meets_threshold"] for r in results) else 1
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
