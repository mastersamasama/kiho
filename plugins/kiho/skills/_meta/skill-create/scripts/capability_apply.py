#!/usr/bin/env python3
"""
capability_apply.py — v5.16 Stage B one-shot: writes metadata.kiho.capability
into every SKILL.md frontmatter based on a CEO-reviewed verdict mapping.

Companion to capability_annotate.py. The annotate script emits a CSV with
heuristic proposals; the CEO reviews and corrects; this script consumes the
corrected mapping and rewrites each SKILL.md's frontmatter in place.

Idempotent: running twice produces no change on the second run.

Insertion strategy: if the frontmatter already has a `metadata:` key, find
the kiho sub-key; insert capability under it. If no metadata block exists,
append `metadata:\\n  kiho:\\n    capability: <verb>` just before the closing
`---`. Preserves every other field verbatim.

Grounding: v5.16 Primitive 2 (capability taxonomy), plan Stage B.

Usage:
    capability_apply.py                       # applies the hardcoded mapping
    capability_apply.py --dry-run             # prints diffs without writing

Exit codes (0/1/2/3):
    0 — all annotations applied (or already correct)
    1 — policy violation (unknown verb, unknown skill ID)
    2 — usage error (SKILL.md not found)
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
TAXONOMY_PATH = PLUGIN_ROOT / "references" / "capability-taxonomy.md"

# CEO-reviewed capability mapping (Apr 15 2026).
# Classification rule: primary effect of the skill, NOT secondary operations.
# This mapping is the committed v5.16 Stage B verdict.
CAPABILITY_MAP: dict[str, str] = {
    # _meta
    "sk-028": "evaluate",     # evolution-scan — Karpathy-style scanning + verdict
    "sk-create": "create",    # skill-create — greenfield authoring
    "sk-032": "delete",       # skill-deprecate — retirement
    "sk-026": "create",       # skill-derive — new specialized skill
    "sk-024": "read",         # skill-find — discovery (lookup, no mutation)
    "sk-025": "update",       # skill-improve — FIX operation on existing skill
    "sk-learn": "create",     # skill-learn — extracts/captures/synthesizes into new skills
    "sk-sao": "update",       # soul-apply-override — mutates agent souls

    # core
    "sk-007": "orchestrate",  # committee — multi-agent deliberation routing
    "sk-009": "create",       # design-agent — produces new agent .md files
    "sk-ep": "read",          # experience-pool — retrieval view (primary), registration secondary
    "sk-sim": "evaluate",     # interview-simulate — scores agent behavior
    "sk-001": "orchestrate",  # kiho — single entry point, routes everything
    "sk-005": "create",       # kiho-init — bootstraps KB from PRD
    "sk-006": "read",         # kiho-inspect — state inspection
    "sk-003": "orchestrate",  # kiho-plan — decomposes into delegations (orchestration, though produces plan.md)
    "sk-004": "create",       # kiho-setup — creates initial kiho structure
    "sk-002": "orchestrate",  # kiho-spec — runs three-stage spec ritual
    "sk-030": "update",       # org-sync — syncs registry and capability matrix
    "sk-008": "create",       # recruit — creates new agents
    "sk-010": "read",         # research — cascade retrieval (primary)
    "sk-rdp": "create",       # research-deep — produces SKILL.md skeletons
    "sk-011": "read",         # session-context — reads prior-session activity
    "sk-012": "read",         # state-read — durable state inspection

    # kb
    "sk-013": "create",       # kb-add — new wiki page
    "sk-014": "update",       # kb-update — mutates existing page
    "sk-015": "delete",       # kb-delete — removes wiki page
    "sk-016": "read",         # kb-search — query with cited answer
    "sk-017": "evaluate",     # kb-lint — 12-check lint pass, produces verdict
    "sk-018": "update",       # kb-promote — promotes project tier to company
    "sk-019": "create",       # kb-init — bootstraps a fresh KB tier
    "sk-020": "create",       # kb-ingest-raw — raw source → new wiki entries

    # memory
    "sk-021": "read",         # memory-read — reads per-agent memory
    "sk-022": "create",       # memory-write — appends new memory entry
    "sk-023": "update",       # memory-consolidate — merges and rewrites
    "sk-031": "create",       # memory-reflect — synthesizes new reflections
    "sk-cal": "communicate",  # memory-cross-agent-learn — broadcasts to targets

    # engineering
    "sk-029": "orchestrate",  # engineering-kiro — delegation wrapper
}


def load_valid_verbs() -> set[str]:
    """Read capability-taxonomy.md and extract the closed verb set from
    ### `verb` headings."""
    if not TAXONOMY_PATH.exists():
        return set()
    text = TAXONOMY_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"^### `(\w+)`", text, re.MULTILINE))


def read_skill_id(skill_dir: Path) -> str:
    sid_path = skill_dir / ".skill_id"
    if sid_path.exists():
        return sid_path.read_text(encoding="utf-8").strip()
    return ""


def discover_skill_files() -> dict[str, Path]:
    """Return {skill_id: SKILL.md path}."""
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


def inject_capability(frontmatter: str, verb: str) -> tuple[str, bool]:
    """Insert or update metadata.kiho.capability in a frontmatter string.
    Returns (new_frontmatter, changed)."""
    # Case 1: capability already correct
    m = re.search(
        r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+capability:\s*(\w+)",
        frontmatter,
        re.MULTILINE,
    )
    if m:
        current = m.group(1)
        if current == verb:
            return frontmatter, False
        # Replace the existing value
        new = re.sub(
            r"(^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+capability:\s*)(\w+)",
            lambda mo: mo.group(1) + verb,
            frontmatter,
            count=1,
            flags=re.MULTILINE,
        )
        return new, True

    # Case 2: metadata: block exists but no kiho.capability yet
    if re.search(r"^metadata:\s*$", frontmatter, re.MULTILINE):
        # Check for existing kiho sub-block
        kiho_m = re.search(r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*$", frontmatter, re.MULTILINE)
        if kiho_m:
            insertion = f"    capability: {verb}\n"
            new = frontmatter[:kiho_m.end()] + "\n" + insertion + frontmatter[kiho_m.end() + 1:]
            return new, True
        # metadata: exists but no kiho: — append kiho block to it
        meta_m = re.search(r"^metadata:\s*$", frontmatter, re.MULTILINE)
        if meta_m:
            insertion = f"  kiho:\n    capability: {verb}\n"
            new = frontmatter[:meta_m.end()] + "\n" + insertion + frontmatter[meta_m.end() + 1:]
            return new, True

    # Case 3: no metadata: block — append one before the trailing newline
    # Ensure frontmatter ends with a newline
    if not frontmatter.endswith("\n"):
        frontmatter += "\n"
    appendix = f"metadata:\n  kiho:\n    capability: {verb}\n"
    return frontmatter + appendix, True


def apply_one(skill_md: Path, verb: str, dry_run: bool) -> str:
    """Rewrite one SKILL.md to inject the capability. Return a status string."""
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)", text, re.DOTALL)
    if not m:
        return f"SKIP (no frontmatter): {skill_md}"
    opening, body, closing = m.group(1), m.group(2), m.group(3)
    new_body, changed = inject_capability(body, verb)
    if not changed:
        return f"OK  (already correct): {skill_md.relative_to(PLUGIN_ROOT)}"
    rewritten = opening + new_body + closing + text[m.end():]
    if dry_run:
        return f"DRY (would update):  {skill_md.relative_to(PLUGIN_ROOT)} -> {verb}"
    skill_md.write_text(rewritten, encoding="utf-8")
    return f"UPD (written):       {skill_md.relative_to(PLUGIN_ROOT)} -> {verb}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="show what would be changed without writing")
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
                f"capability_apply: taxonomy file not found or empty: {TAXONOMY_PATH}\n"
            )
            return 2

        for sid, verb in CAPABILITY_MAP.items():
            if verb not in valid_verbs:
                sys.stderr.write(
                    f"capability_apply: {sid} has invalid verb '{verb}' "
                    f"(valid: {sorted(valid_verbs)})\n"
                )
                return 1

        files = discover_skill_files()
        missing = set(CAPABILITY_MAP) - set(files)
        if missing:
            sys.stderr.write(
                f"capability_apply: mapping references unknown skill IDs: {sorted(missing)}\n"
            )
            return 1

        unmapped = set(files) - set(CAPABILITY_MAP)
        if unmapped:
            sys.stderr.write(
                f"capability_apply: WARNING — skills on disk without mapping: {sorted(unmapped)}\n"
            )

        for sid in sorted(CAPABILITY_MAP):
            msg = apply_one(files[sid], CAPABILITY_MAP[sid], args.dry_run)
            sys.stdout.write(msg + "\n")
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"capability_apply: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
