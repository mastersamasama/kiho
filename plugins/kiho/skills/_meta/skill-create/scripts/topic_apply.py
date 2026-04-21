#!/usr/bin/env python3
"""
topic_apply.py — v5.16 Stage C one-shot: writes metadata.kiho.topic_tags
into every SKILL.md frontmatter from a CEO-reviewed mapping.

Companion to the capability_apply.py pattern. The pre-v5.16 catalog had
no real topic_tags (one template placeholder at most), so Stage C is a
fresh seed rather than a free-form → controlled migration. The mapping
below is the CEO-solo verdict for all 38 existing skills.

Idempotent: running twice produces no change on the second run.

Insertion strategy: inserts topic_tags under metadata.kiho.* alongside
capability. Preserves every other frontmatter field verbatim.

Grounding: v5.16 Primitive 3 (controlled topic vocabulary), plan Stage C.

Usage:
    topic_apply.py                 # applies the hardcoded mapping
    topic_apply.py --dry-run       # prints diffs without writing

Exit codes (0/1/2/3):
    0 — annotations applied (or already correct)
    1 — policy violation (unknown tag, unknown skill)
    2 — usage error
    3 — internal error
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent.parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
VOCAB_PATH = PLUGIN_ROOT / "references" / "topic-vocabulary.md"

# CEO-reviewed topic-tag mapping (Apr 15 2026). Each skill gets 1-3 tags
# from the controlled vocabulary in references/topic-vocabulary.md.
# Classification rule: tag by what the skill is ABOUT, not by its operation.
TOPIC_MAP: dict[str, list[str]] = {
    # _meta
    "sk-028": ["lifecycle", "validation"],          # evolution-scan
    "sk-create": ["authoring"],                     # skill-create
    "sk-032": ["authoring", "lifecycle"],           # skill-deprecate
    "sk-026": ["authoring"],                        # skill-derive
    "sk-024": ["discovery"],                        # skill-find
    "sk-025": ["authoring", "lifecycle"],           # skill-improve
    "sk-learn": ["authoring", "learning"],          # skill-learn
    "sk-sao": ["persona", "lifecycle"],             # soul-apply-override

    # core
    "sk-007": ["deliberation", "orchestration"],    # committee
    "sk-009": ["hiring", "persona"],                # design-agent
    "sk-ep": ["learning", "retrieval"],             # experience-pool
    "sk-sim": ["hiring", "validation"],             # interview-simulate
    "sk-001": ["orchestration"],                    # kiho
    "sk-005": ["bootstrap", "ingestion"],           # kiho-init
    "sk-006": ["observability"],                    # kiho-inspect
    "sk-003": ["deliberation", "orchestration"],    # kiho-plan
    "sk-004": ["bootstrap"],                        # kiho-setup
    "sk-002": ["orchestration", "engineering"],     # kiho-spec
    "sk-030": ["state-management"],                 # org-sync
    "sk-008": ["hiring"],                           # recruit
    "sk-010": ["research", "retrieval"],            # research
    "sk-rdp": ["research", "authoring"],            # research-deep
    "sk-011": ["observability"],                    # session-context
    "sk-012": ["observability", "state-management"],# state-read

    # kb
    "sk-013": ["ingestion"],                        # kb-add
    "sk-014": ["curation"],                         # kb-update
    "sk-015": ["curation", "lifecycle"],            # kb-delete
    "sk-016": ["retrieval"],                        # kb-search
    "sk-017": ["validation"],                       # kb-lint
    "sk-018": ["curation", "lifecycle"],            # kb-promote
    "sk-019": ["bootstrap"],                        # kb-init
    "sk-020": ["ingestion"],                        # kb-ingest-raw

    # memory
    "sk-021": ["retrieval"],                        # memory-read
    "sk-022": ["ingestion"],                        # memory-write
    "sk-023": ["reflection", "curation"],           # memory-consolidate
    "sk-031": ["reflection"],                       # memory-reflect
    "sk-cal": ["learning"],                         # memory-cross-agent-learn

    # engineering
    "sk-029": ["engineering", "orchestration"],     # engineering-kiro
}


def load_valid_tags() -> set[str]:
    if not VOCAB_PATH.exists():
        return set()
    text = VOCAB_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"^### `([\w-]+)`", text, re.MULTILINE))


def read_skill_id(skill_dir: Path) -> str:
    sid_path = skill_dir / ".skill_id"
    if sid_path.exists():
        return sid_path.read_text(encoding="utf-8").strip()
    return ""


def discover_skill_files() -> dict[str, Path]:
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


def format_tags(tags: list[str]) -> str:
    return "[" + ", ".join(tags) + "]"


def inject_topic_tags(frontmatter: str, tags: list[str]) -> tuple[str, bool]:
    """Insert or update metadata.kiho.topic_tags. Returns (new, changed)."""
    desired = format_tags(tags)

    # Case 1: topic_tags already set under metadata.kiho
    m = re.search(
        r"(^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+topic_tags:\s*)(\[[^\]]*\])",
        frontmatter,
        re.MULTILINE,
    )
    if m:
        current = m.group(2)
        if current == desired:
            return frontmatter, False
        new = frontmatter[:m.start(2)] + desired + frontmatter[m.end(2):]
        return new, True

    # Case 2: metadata.kiho block exists but no topic_tags yet —
    # insert topic_tags immediately after the capability line.
    cap_m = re.search(
        r"(^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+capability:\s*\w+\n)",
        frontmatter,
        re.MULTILINE,
    )
    if cap_m:
        insertion = f"    topic_tags: {desired}\n"
        new = frontmatter[:cap_m.end()] + insertion + frontmatter[cap_m.end():]
        return new, True

    # Case 3: metadata.kiho exists without capability (rare) — append topic_tags under kiho
    kiho_m = re.search(
        r"(^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n)",
        frontmatter,
        re.MULTILINE,
    )
    if kiho_m:
        insertion = f"    topic_tags: {desired}\n"
        new = frontmatter[:kiho_m.end()] + insertion + frontmatter[kiho_m.end():]
        return new, True

    # Case 4: no metadata block at all — append a full one
    if not frontmatter.endswith("\n"):
        frontmatter += "\n"
    appendix = f"metadata:\n  kiho:\n    topic_tags: {desired}\n"
    return frontmatter + appendix, True


def apply_one(skill_md: Path, tags: list[str], dry_run: bool) -> str:
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)", text, re.DOTALL)
    if not m:
        return f"SKIP (no frontmatter): {skill_md}"
    opening, body, closing = m.group(1), m.group(2), m.group(3)
    new_body, changed = inject_topic_tags(body, tags)
    if not changed:
        return f"OK  (already correct): {skill_md.relative_to(PLUGIN_ROOT)}"
    rewritten = opening + new_body + closing + text[m.end():]
    if dry_run:
        return f"DRY (would update):  {skill_md.relative_to(PLUGIN_ROOT)} -> {format_tags(tags)}"
    skill_md.write_text(rewritten, encoding="utf-8")
    return f"UPD (written):       {skill_md.relative_to(PLUGIN_ROOT)} -> {format_tags(tags)}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="print changes without writing")
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
                f"topic_apply: vocabulary file missing or empty: {VOCAB_PATH}\n"
            )
            return 2
        for sid, tags in TOPIC_MAP.items():
            bad = [t for t in tags if t not in valid]
            if bad:
                sys.stderr.write(
                    f"topic_apply: {sid} has invalid tags {bad} "
                    f"(valid: {sorted(valid)})\n"
                )
                return 1
        files = discover_skill_files()
        missing = set(TOPIC_MAP) - set(files)
        if missing:
            sys.stderr.write(
                f"topic_apply: mapping references unknown skill IDs: {sorted(missing)}\n"
            )
            return 1
        for sid in sorted(TOPIC_MAP):
            msg = apply_one(files[sid], TOPIC_MAP[sid], args.dry_run)
            sys.stdout.write(msg + "\n")
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"topic_apply: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
