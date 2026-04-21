#!/usr/bin/env python3
"""Generate skills/CATALOG.md from skills/*/*/SKILL.md frontmatter and .skill_id sidecar files.

After writing the flat table, invokes routing_gen.py as a post-hook to
insert/refresh the YAML routing block at the top inside HTML-comment fences.
The routing block is load-bearing for Gate 14 (catalog_fit.py), Gate 17
(similarity_scan.py), Gate 19 (routing_sync.py), and skill-find's facet
walk (v5.16 Primitive 1).

Exit codes (0/1/2/3 per v5.15.2 convention):
    0 — catalog regenerated successfully
    1 — routing_gen post-hook failed (policy violation)
    2 — usage error or file missing
    3 — internal error
"""

import re
import subprocess
import sys
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent
SKILLS_DIR = BIN_DIR.parent / "skills"
CATALOG_PATH = SKILLS_DIR / "CATALOG.md"
ROUTING_GEN_PATH = BIN_DIR / "routing_gen.py"

# Next ID counter file — tracks the highest assigned sk-NNN
NEXT_ID_SENTINEL = "sk-"

DOMAIN_ORDER = ["_meta", "core", "kb", "memory", "engineering"]
DOMAIN_LABELS = {
    "_meta": "Meta",
    "core": "Core",
    "kb": "Knowledge Base",
    "memory": "Memory",
    "engineering": "Engineering",
}


def extract_frontmatter(skill_md: Path) -> dict:
    """Extract YAML frontmatter fields from a SKILL.md file."""
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        # Simple key: value parsing (handles multiline description on single line)
        colon_idx = line.find(":")
        if colon_idx == -1:
            continue
        key = line[:colon_idx].strip()
        value = line[colon_idx + 1:].strip().strip('"').strip("'")
        fm[key] = value
    return fm


def read_skill_id(skill_dir: Path) -> str | None:
    """Read the .skill_id sidecar file if it exists."""
    sid_path = skill_dir / ".skill_id"
    if sid_path.exists():
        return sid_path.read_text(encoding="utf-8").strip()
    return None


def next_available_id(existing_ids: set[str]) -> str:
    """Compute the next sk-NNN ID not yet taken."""
    max_num = 0
    for sid in existing_ids:
        m = re.match(r"sk-(\d+)", sid)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"sk-{max_num + 1:03d}"


def write_skill_id(skill_dir: Path, sid: str) -> None:
    """Write a .skill_id sidecar file."""
    (skill_dir / ".skill_id").write_text(sid, encoding="utf-8")


def _record_skill(
    skill_dir: Path,
    skill_md: Path,
    domain: str,
    sub_domain: str | None,
    existing_ids: set[str],
    skills_out: list[dict],
) -> None:
    fm = extract_frontmatter(skill_md)
    name = fm.get("name", skill_dir.name)
    description = fm.get("description", "")

    desc_short = description
    if len(desc_short) > 120:
        desc_short = desc_short[:117] + "..."

    sid = read_skill_id(skill_dir)
    if not sid:
        sid = next_available_id(existing_ids)
        existing_ids.add(sid)
        write_skill_id(skill_dir, sid)
        suffix = f"{sub_domain}/{skill_dir.name}" if sub_domain else skill_dir.name
        print(f"  Assigned {sid} to {domain}/{suffix}")

    if sub_domain:
        rel_path = f"{domain}/{sub_domain}/{skill_dir.name}"
    else:
        rel_path = f"{domain}/{skill_dir.name}"

    skills_out.append({
        "id": sid,
        "name": name,
        "domain": domain,
        "sub_domain": sub_domain,
        "domain_label": DOMAIN_LABELS.get(domain, domain),
        "path": rel_path,
        "description": desc_short,
    })


def discover_skills() -> list[dict]:
    """Walk skills/<domain>/{<sub>/}?<skill>/SKILL.md and collect metadata.

    Supports both flat and hierarchical (v5.16 Stage D) layouts:
      Flat:         skills/kb/kb-add/SKILL.md              -> sub_domain=None
      Hierarchical: skills/core/harness/kiho/SKILL.md       -> sub_domain=harness
    """
    skills: list[dict] = []
    existing_ids: set[str] = set()

    # First pass: harvest all existing IDs from both layouts
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
                    existing_ids.add(sid)
                continue
            for grand in sorted(child.iterdir()):
                if not grand.is_dir():
                    continue
                if (grand / "SKILL.md").is_file():
                    sid = read_skill_id(grand)
                    if sid:
                        existing_ids.add(sid)

    # Second pass: collect metadata, assigning IDs to any unregistered skills
    for domain in DOMAIN_ORDER:
        domain_dir = SKILLS_DIR / domain
        if not domain_dir.is_dir():
            continue
        for child in sorted(domain_dir.iterdir()):
            if not child.is_dir():
                continue
            flat = child / "SKILL.md"
            if flat.is_file():
                _record_skill(child, flat, domain, None, existing_ids, skills)
                continue
            # Hierarchical: child is the sub-domain dir; walk its children
            for grand in sorted(child.iterdir()):
                if not grand.is_dir():
                    continue
                nested_md = grand / "SKILL.md"
                if nested_md.is_file():
                    _record_skill(
                        grand, nested_md, domain, child.name,
                        existing_ids, skills,
                    )

    return skills


def _emit_table(lines: list[str], skills: list[dict]) -> None:
    lines.append("| ID | Skill | Path | Description |")
    lines.append("|---|---|---|---|")
    for s in sorted(skills, key=lambda x: x["id"]):
        lines.append(
            f"| `{s['id']}` | **{s['name']}** | `{s['path']}/` | {s['description']} |"
        )
    lines.append("")


def generate_catalog(skills: list[dict]) -> str:
    """Render CATALOG.md content. Hierarchical-aware: emits a sub-heading per
    sub-domain within each top-level domain when any sub-domains exist.
    """
    lines = [
        "# Skill Catalog",
        "",
        f"Auto-generated by `bin/catalog_gen.py` — {len(skills)} skills registered.",
        "",
    ]

    by_domain: dict[str, list[dict]] = {}
    for s in skills:
        by_domain.setdefault(s["domain"], []).append(s)

    for domain in DOMAIN_ORDER:
        domain_skills = by_domain.get(domain, [])
        if not domain_skills:
            continue
        label = DOMAIN_LABELS.get(domain, domain)
        lines.append(f"## {label} (`{domain}/`)")
        lines.append("")

        # Partition into flat skills (sub_domain is None) and per-sub-domain groups
        flat_skills = [s for s in domain_skills if not s.get("sub_domain")]
        sub_groups: dict[str, list[dict]] = {}
        for s in domain_skills:
            sub = s.get("sub_domain")
            if sub:
                sub_groups.setdefault(sub, []).append(s)

        if sub_groups:
            # Hierarchical domain: emit each sub-domain as its own sub-heading
            if flat_skills:
                lines.append("### (ungrouped)")
                lines.append("")
                _emit_table(lines, flat_skills)
            for sub_name in sorted(sub_groups):
                lines.append(f"### {sub_name} (`{domain}/{sub_name}/`)")
                lines.append("")
                _emit_table(lines, sub_groups[sub_name])
        else:
            # Flat domain: one table per domain
            _emit_table(lines, flat_skills)

    return "\n".join(lines)


def run_routing_gen() -> int:
    """Invoke bin/routing_gen.py as a post-hook to refresh the routing block.

    Returns the child's exit code. 0 is success, 1 is policy violation
    (e.g., human-edited block preserved), 2 is usage error, 3 is internal.
    """
    if not ROUTING_GEN_PATH.exists():
        sys.stderr.write(f"catalog_gen: routing_gen.py not found at {ROUTING_GEN_PATH}\n")
        return 2
    result = subprocess.run(
        [sys.executable, str(ROUTING_GEN_PATH)],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


def main() -> int:
    print(f"Scanning {SKILLS_DIR} ...")
    skills = discover_skills()
    catalog = generate_catalog(skills)
    # Atomic write: write to sibling temp file, rename into place. Closes
    # the window where a concurrent reader sees a truncated or stale
    # CATALOG.md between the initial write and the routing_gen post-hook.
    tmp_path = CATALOG_PATH.with_suffix(CATALOG_PATH.suffix + ".tmp")
    tmp_path.write_text(catalog, encoding="utf-8")
    tmp_path.replace(CATALOG_PATH)
    print(f"Wrote {CATALOG_PATH} with {len(skills)} entries (atomic).")

    rc = run_routing_gen()
    if rc != 0:
        sys.stderr.write(
            f"catalog_gen: routing_gen post-hook failed with exit {rc}\n"
        )
        # Do not fail the whole catalog regen on a preserved (rc=1) block —
        # the skill tables are still correct. But propagate 2/3 as failure.
        if rc >= 2:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
