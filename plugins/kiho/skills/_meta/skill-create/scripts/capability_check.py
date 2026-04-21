#!/usr/bin/env python3
"""
capability_check.py — Gate 20: capability verb validation (v5.16).

Verifies that a SKILL.md's frontmatter declares exactly one
metadata.kiho.capability verb from the closed 8-element set defined in
kiho-plugin/references/capability-taxonomy.md. Missing or out-of-set
verbs block the skill-create pipeline.

Two modes:
    (a) Single-file check: --skill <SKILL.md path>
        Validates one file. Use during skill-create Step 3 frontmatter draft.
    (b) Catalog-wide audit: --all
        Walks every SKILL.md in skills/*/ and skills/*/*/ and reports
        per-skill pass/fail. Used for migration verification.

Grounding: v5.16 Primitive 2. Closed set defined in
kiho-plugin/references/capability-taxonomy.md.

Usage:
    capability_check.py --skill <path>
    capability_check.py --all

Exit codes (0/1/2/3):
    0 — all checked skills declare a valid capability verb
    1 — policy violation: missing or out-of-set capability
    2 — usage error: SKILL.md path missing, taxonomy file missing
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
TAXONOMY_PATH = PLUGIN_ROOT / "references" / "capability-taxonomy.md"


def load_valid_verbs() -> set[str]:
    """Extract the closed verb set from capability-taxonomy.md '### `verb`' headings."""
    if not TAXONOMY_PATH.exists():
        return set()
    text = TAXONOMY_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"^### `(\w+)`", text, re.MULTILINE))


def extract_capability(skill_md_path: Path) -> str | None:
    """Parse frontmatter and return metadata.kiho.capability value, or None if absent."""
    text = skill_md_path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    fm = m.group(1)
    cap = re.search(
        r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+capability:\s*(\w+)",
        fm,
        re.MULTILINE,
    )
    if cap:
        return cap.group(1)
    return None


def check_one(skill_md_path: Path, valid_verbs: set[str]) -> dict:
    """Return a verdict dict for one SKILL.md."""
    if not skill_md_path.is_file():
        return {
            "path": str(skill_md_path),
            "passed": False,
            "status": "file_not_found",
        }
    verb = extract_capability(skill_md_path)
    if verb is None:
        return {
            "path": str(skill_md_path.relative_to(PLUGIN_ROOT) if PLUGIN_ROOT in skill_md_path.parents else skill_md_path),
            "passed": False,
            "status": "missing_capability",
            "message": "metadata.kiho.capability field is absent or malformed",
        }
    if verb not in valid_verbs:
        return {
            "path": str(skill_md_path.relative_to(PLUGIN_ROOT) if PLUGIN_ROOT in skill_md_path.parents else skill_md_path),
            "passed": False,
            "status": "out_of_set",
            "capability": verb,
            "valid_verbs": sorted(valid_verbs),
            "message": f"'{verb}' is not in the closed verb set",
        }
    return {
        "path": str(skill_md_path.relative_to(PLUGIN_ROOT) if PLUGIN_ROOT in skill_md_path.parents else skill_md_path),
        "passed": True,
        "status": "ok",
        "capability": verb,
    }


def discover_all_skills() -> list[Path]:
    """Walk skills/ and return every SKILL.md path (flat + hierarchical)."""
    result: list[Path] = []
    for domain in ("_meta", "core", "kb", "memory", "engineering"):
        domain_dir = SKILLS_DIR / domain
        if not domain_dir.is_dir():
            continue
        for child in sorted(domain_dir.iterdir()):
            if not child.is_dir():
                continue
            flat = child / "SKILL.md"
            if flat.is_file():
                result.append(flat)
                continue
            for grand in sorted(child.iterdir()):
                if not grand.is_dir():
                    continue
                nested = grand / "SKILL.md"
                if nested.is_file():
                    result.append(nested)
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--skill", type=str,
                   help="path to a single SKILL.md to check")
    g.add_argument("--all", action="store_true",
                   help="walk skills/ and check every SKILL.md")
    return p.parse_args()


def main() -> int:
    try:
        args = parse_args()
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    try:
        valid_verbs = load_valid_verbs()
        if not valid_verbs:
            sys.stderr.write(
                f"capability_check: taxonomy file missing or empty: {TAXONOMY_PATH}\n"
            )
            return 2

        if args.skill:
            path = Path(args.skill)
            if not path.is_file():
                sys.stderr.write(f"capability_check: file not found: {path}\n")
                return 2
            verdict = check_one(path, valid_verbs)
            sys.stdout.write(json.dumps(verdict, indent=2) + "\n")
            return 0 if verdict["passed"] else 1

        # --all mode: walk and report
        all_files = discover_all_skills()
        if not all_files:
            sys.stderr.write("capability_check: no SKILL.md files discovered\n")
            return 2
        verdicts = [check_one(p, valid_verbs) for p in all_files]
        failed = [v for v in verdicts if not v["passed"]]
        summary = {
            "total": len(verdicts),
            "passed": len(verdicts) - len(failed),
            "failed": len(failed),
            "valid_verbs": sorted(valid_verbs),
            "failures": failed,
        }
        sys.stdout.write(json.dumps(summary, indent=2) + "\n")
        return 0 if not failed else 1
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"capability_check: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
