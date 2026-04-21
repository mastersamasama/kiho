#!/usr/bin/env python3
"""
topic_vocab_check.py — Gate 21: topic-tag controlled-vocabulary check (v5.16).

Verifies that every entry in a SKILL.md's frontmatter
metadata.kiho.topic_tags list comes from the controlled vocabulary defined
in kiho-plugin/references/topic-vocabulary.md. Free-form tags block the
skill-create pipeline.

Two modes:
    (a) Single-file check: --skill <SKILL.md path>
        Validates one file. Use during skill-create Step 3 frontmatter draft.
    (b) Catalog-wide audit: --all
        Walks every SKILL.md in skills/*/ and skills/*/*/ and reports
        per-skill pass/fail. Used for migration verification.

Grounding: v5.16 Primitive 3 (controlled topic vocabulary). Seed vocab
in kiho-plugin/references/topic-vocabulary.md.

Usage:
    topic_vocab_check.py --skill <path>
    topic_vocab_check.py --all

Exit codes (0/1/2/3):
    0 — all checked skills pass
    1 — policy violation: out-of-vocabulary tag found
    2 — usage error: file missing, vocabulary missing
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
VOCAB_PATH = PLUGIN_ROOT / "references" / "topic-vocabulary.md"


def load_valid_tags() -> set[str]:
    if not VOCAB_PATH.exists():
        return set()
    text = VOCAB_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"^### `([\w-]+)`", text, re.MULTILINE))


def extract_topic_tags(skill_md_path: Path) -> list[str] | None:
    """Return the list of topic_tags from frontmatter, or None if absent."""
    text = skill_md_path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    fm = m.group(1)
    tags_m = re.search(
        r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+topic_tags:\s*\[([^\]]*)\]",
        fm,
        re.MULTILINE,
    )
    if not tags_m:
        return None
    raw = tags_m.group(1).strip()
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def has_stale_outer_topic_tags(skill_md_path: Path) -> bool:
    """Detect the legacy pre-v5.16 stale pattern:

        metadata:
          topic_tags: [...]     # 2-space indent = directly under metadata
          kiho:
            topic_tags: [...]   # 4-space indent = correct nested path

    v5.16 rule: topic_tags MUST live under metadata.kiho.topic_tags. A
    top-level metadata.topic_tags is a spec violation (same treatment as
    top-level requires:). Gate 21 rejects any such declaration.
    """
    text = skill_md_path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return False
    fm = m.group(1)
    # Match `  topic_tags: [...]` at 2-space indent (directly under metadata)
    # BUT exclude `    topic_tags: [...]` at 4-space indent (under metadata.kiho).
    # The non-greedy `metadata:\s*\n` prefix ensures we're inside the metadata block.
    outer_m = re.search(
        r"^metadata:\s*\n(?:[ \t]*#[^\n]*\n)*[ \t]{0,3}topic_tags:\s*\[",
        fm,
        re.MULTILINE,
    )
    if outer_m:
        return True
    # Also match mid-block 2-space indent (after other metadata fields but before kiho:)
    lines = fm.splitlines()
    in_metadata = False
    for line in lines:
        if re.match(r"^metadata:\s*$", line):
            in_metadata = True
            continue
        if not in_metadata:
            continue
        # A 4-space indent means we've descended into a sub-block (kiho, etc.)
        if re.match(r"^    \w", line):
            continue
        # Empty / comment lines don't terminate
        if not line.strip() or line.strip().startswith("#"):
            continue
        # A 2-space-indent line that isn't "kiho:" is a top-level metadata field
        m2 = re.match(r"^  (\w[\w_-]*)\s*:", line)
        if m2 and m2.group(1) == "topic_tags":
            return True
        # A non-indented line ends the metadata block
        if not line.startswith(" "):
            break
    return False


def check_one(skill_md_path: Path, valid: set[str]) -> dict:
    rel = (
        skill_md_path.relative_to(PLUGIN_ROOT)
        if PLUGIN_ROOT in skill_md_path.parents
        else skill_md_path
    )
    if not skill_md_path.is_file():
        return {"path": str(skill_md_path), "passed": False, "status": "file_not_found"}
    # v5.16 hardening: reject stale pre-v5.16 top-level metadata.topic_tags
    if has_stale_outer_topic_tags(skill_md_path):
        return {
            "path": str(rel),
            "passed": False,
            "status": "stale_outer_topic_tags",
            "message": (
                "Found top-level metadata.topic_tags field. v5.16 requires "
                "topic_tags to live under metadata.kiho.topic_tags (same "
                "rule as top-level requires: per v5.15). Delete the outer "
                "declaration; the nested one is authoritative."
            ),
        }
    tags = extract_topic_tags(skill_md_path)
    if tags is None:
        return {
            "path": str(rel),
            "passed": False,
            "status": "missing_topic_tags",
            "message": "metadata.kiho.topic_tags field is absent",
        }
    if not tags:
        return {
            "path": str(rel),
            "passed": False,
            "status": "empty_topic_tags",
            "message": "topic_tags list is empty — every skill MUST declare at least one tag",
        }
    bad = [t for t in tags if t not in valid]
    if bad:
        return {
            "path": str(rel),
            "passed": False,
            "status": "out_of_vocabulary",
            "tags": tags,
            "bad_tags": bad,
            "valid_vocab": sorted(valid),
            "message": (
                f"tags {bad} are not in the controlled vocabulary. "
                f"Pick from: {sorted(valid)}"
            ),
        }
    return {"path": str(rel), "passed": True, "status": "ok", "tags": tags}


def discover_all_skills() -> list[Path]:
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
    g.add_argument("--skill", type=str, help="path to one SKILL.md")
    g.add_argument("--all", action="store_true",
                   help="walk skills/ and check every SKILL.md")
    return p.parse_args()


def main() -> int:
    try:
        args = parse_args()
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    try:
        valid = load_valid_tags()
        if not valid:
            sys.stderr.write(
                f"topic_vocab_check: vocabulary file missing: {VOCAB_PATH}\n"
            )
            return 2
        if args.skill:
            path = Path(args.skill)
            if not path.is_file():
                sys.stderr.write(f"topic_vocab_check: file not found: {path}\n")
                return 2
            verdict = check_one(path, valid)
            sys.stdout.write(json.dumps(verdict, indent=2) + "\n")
            return 0 if verdict["passed"] else 1

        all_files = discover_all_skills()
        if not all_files:
            sys.stderr.write("topic_vocab_check: no SKILL.md files discovered\n")
            return 2
        verdicts = [check_one(p, valid) for p in all_files]
        failed = [v for v in verdicts if not v["passed"]]
        summary = {
            "total": len(verdicts),
            "passed": len(verdicts) - len(failed),
            "failed": len(failed),
            "valid_vocab": sorted(valid),
            "failures": failed,
        }
        sys.stdout.write(json.dumps(summary, indent=2) + "\n")
        return 0 if not failed else 1
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"topic_vocab_check: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
