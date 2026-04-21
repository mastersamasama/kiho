#!/usr/bin/env python3
"""
capability_annotate.py — v5.16 Stage B one-shot migration.

Classifies every existing SKILL.md by capability verb from the closed 8-verb
set defined in kiho-plugin/references/capability-taxonomy.md. Uses keyword
heuristics on the description field to propose a verb. Emits a CSV review
worksheet to stdout (or --output) so the CEO can review and correct before
committing to frontmatter.

The CSV has columns: skill_id, domain, name, proposed_capability, evidence,
current_description (truncated to 80 chars). The CEO reviews each row,
confirms or corrects the proposed_capability, and then runs
scripts/apply_capability_csv.py (or hand-edits each SKILL.md frontmatter).

This is a one-shot migration — not a durable pipeline step. After Stage B
commits, Gate 20 (capability_check.py) enforces the field on all new skills
and this script can be archived.

Heuristic classification: matches verb-specific keyword patterns against the
description. First matching verb wins. If no match, proposed_capability is
"?" and the row requires manual classification.

Grounding: v5.16 Primitive 2 (capability taxonomy). Plan at
plans/bright-toasting-diffie.md v5.16 Execution commitment Stage B.

Usage:
    capability_annotate.py [--output <csv-path>]

Exit codes (0/1/2/3):
    0 — CSV emitted successfully
    1 — policy violation (no skills discovered)
    2 — usage error
    3 — internal error
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent.parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"

DOMAIN_ORDER = ["_meta", "core", "kb", "memory", "engineering"]

# Keyword patterns per capability verb. First match wins — order matters.
# These are first-pass heuristics; the CEO review catches misclassifications.
CAPABILITY_PATTERNS: list[tuple[str, list[str]]] = [
    # Delete patterns first (otherwise "retire" would match update)
    ("delete", [
        r"\bdeprecat", r"\bretir(e|es|ing)", r"\bremov(e|ed|ing)",
        r"\bsoft-delete", r"\bdeletion",
    ]),
    # Evaluate patterns before update/create (otherwise "scans for" → create)
    ("evaluate", [
        r"\blint\b", r"\bscor(e|es|ing)\b", r"\bvalidat",
        r"\bsimulat", r"\baudit", r"\bevolution-scan",
        r"\banalyz(e|es|ing)\b", r"\bverif",
    ]),
    # Orchestrate — meta-skills that spawn others
    ("orchestrate", [
        r"\borchestrat", r"\bcommittee\b", r"\broute(s|d|r)?\b",
        r"\bdelegate", r"\bdecompose", r"\bspec.?driven",
        r"\bentry point", r"^use this skill whenever.*invokes",
    ]),
    # Create patterns — new artifacts
    ("create", [
        r"\bcreat(e|es|ed|ing)\b", r"\bauthor(ing)?\b", r"\bdraft",
        r"\bgenerat(e|es|ed|ing)", r"\bproduc(e|es|ing)",
        r"\bbootstrap", r"\binitial", r"\bbuild(s|ing)?\b",
        r"\bingest", r"\brecruit", r"\bderive(d)?",
        r"\bwrite(s|n)?\b",
    ]),
    # Update patterns — modify existing
    ("update", [
        r"\bupdat(e|es|ing)", r"\bimprov(e|es|ing)",
        r"\bmutat(e|es|ing)", r"\bpromot(e|es|ing)",
        r"\bconsolidat(e|es|ing)", r"\bsynchroniz",
        r"\boverrid(e|es|ing)", r"\bappl(y|ies|ied)",
        r"\bcorrect", r"\bamend",
    ]),
    # Read patterns — retrieval, inspection
    ("read", [
        r"\bread(s|ing)?\b", r"\bfind(s|ing)?\b", r"\bsearch",
        r"\binspect", r"\bretriev", r"\bquer(y|ies|ied)",
        r"\bview(s|ing)?\b", r"\blookup", r"\bdiscovery",
        r"\breturn(s|ing)?.*(list|entries|matching)",
    ]),
    # Communicate — external notifications (rare in current catalog)
    ("communicate", [
        r"\bescalate", r"\bnotif(y|ies|ication)",
        r"\bbroadcast", r"\bannounce",
    ]),
    # Decide — committee-gated decision records (reserved; rare match)
    ("decide", [
        r"\bdecision record", r"\bverdict",
    ]),
]


def extract_frontmatter_field(skill_md: Path, field: str) -> str:
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
    sid_path = skill_dir / ".skill_id"
    if sid_path.exists():
        return sid_path.read_text(encoding="utf-8").strip()
    return ""


def classify(description: str) -> tuple[str, str]:
    """Return (verb, matched_evidence_snippet) using the first-match rule."""
    text = description.lower()
    for verb, patterns in CAPABILITY_PATTERNS:
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 20)
                return verb, f"...{text[start:end]}..."
    return "?", ""


def discover_skills() -> list[dict]:
    skills: list[dict] = []
    for domain in DOMAIN_ORDER:
        domain_dir = SKILLS_DIR / domain
        if not domain_dir.is_dir():
            continue
        for child in sorted(domain_dir.iterdir()):
            if not child.is_dir():
                continue
            flat = child / "SKILL.md"
            if flat.is_file():
                skills.append(_row(domain, child, flat))
                continue
            for grand in sorted(child.iterdir()):
                if not grand.is_dir():
                    continue
                nested = grand / "SKILL.md"
                if nested.is_file():
                    skills.append(_row(domain, grand, nested, sub=child.name))
    return [s for s in skills if s]


def _row(domain: str, skill_dir: Path, skill_md: Path, sub: str = "") -> dict:
    sid = read_skill_id(skill_dir)
    if not sid:
        return {}
    desc = extract_frontmatter_field(skill_md, "description")
    name = extract_frontmatter_field(skill_md, "name") or skill_dir.name
    verb, evidence = classify(desc)
    return {
        "skill_id": sid,
        "domain": domain,
        "sub_domain": sub,
        "name": name,
        "proposed_capability": verb,
        "evidence": evidence,
        "current_description": desc[:80] + ("..." if len(desc) > 80 else ""),
        "path": str(skill_md.relative_to(PLUGIN_ROOT)),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", default="-",
                   help="output CSV path (default: stdout)")
    return p.parse_args()


def main() -> int:
    try:
        args = parse_args()
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    try:
        skills = discover_skills()
        if not skills:
            sys.stderr.write("capability_annotate: no skills discovered\n")
            return 1
        fieldnames = [
            "skill_id", "domain", "sub_domain", "name",
            "proposed_capability", "evidence", "current_description", "path",
        ]
        if args.output == "-":
            writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(skills)
        else:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(skills)
            sys.stdout.write(f"capability_annotate: wrote {len(skills)} rows to {out_path}\n")
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"capability_annotate: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
