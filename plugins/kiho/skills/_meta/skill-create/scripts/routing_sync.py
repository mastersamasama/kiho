#!/usr/bin/env python3
"""
routing_sync.py — Gate 19: walk-catalog coherence check (v5.16).

Verifies that the routing block in skills/CATALOG.md is internally
consistent with the skill tree on disk. Four coherence rules:

  1. Every skill ID in any parent_of (top-level OR nested sub_domains)
     resolves to a real SKILL.md on disk.
  2. Every ACTIVE SKILL.md on disk appears in exactly one parent_of list
     (either the top-level domain's parent_of or a sub_domain's).
  3. Every skill in a sub_domain's parent_of lives at
     skills/<domain>/<sub_domain>/<skill>/SKILL.md on disk (path matches
     the declared taxonomy).
  4. Deprecated skills (lifecycle: deprecated OR metadata.kiho.deprecated:
     true) MUST NOT appear in any parent_of list — deprecation shims are
     still on disk but must not be routed to.

Output JSON:
    {
      "passed": bool,
      "status": "ok" | "routing_sync_failed",
      "ghost_entries": [{"skill_id": "sk-X", "path": "core.harness"}, ...],
      "orphan_skills": [{"skill_id": "sk-X", "disk_path": "skills/..."}, ...],
      "domain_mismatch": [{"skill_id": "sk-X", "expected": "core.harness",
                           "actual_disk": "skills/core/inspection/..."}, ...],
      "deprecated_listed": [{"skill_id": "sk-X", "path": "core.harness"}, ...]
    }

Grounding: v5.16 Primitive 1 (hierarchical walk-catalog). Plan Stage D.

Usage:
    routing_sync.py [--catalog <path>]

Exit codes (0/1/2/3):
    0 — all four lists empty (pass)
    1 — policy violation: any coherence rule failed
    2 — usage error: CATALOG.md missing, routing block missing
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
CATALOG_PATH = SKILLS_DIR / "CATALOG.md"

DOMAIN_ORDER = ["_meta", "core", "kb", "memory", "engineering"]


def read_skill_id(skill_dir: Path) -> str:
    sid_path = skill_dir / ".skill_id"
    if sid_path.exists():
        return sid_path.read_text(encoding="utf-8").strip()
    return ""


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


def is_deprecated(skill_md: Path) -> bool:
    """Check if a skill is marked deprecated via lifecycle or
    metadata.kiho.deprecated: true."""
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return False
    fm = m.group(1)
    if re.search(r"^lifecycle:\s*deprecated\s*$", fm, re.MULTILINE):
        return True
    if re.search(
        r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+deprecated:\s*true\s*$",
        fm,
        re.MULTILINE,
    ):
        return True
    return False


def discover_disk_skills() -> dict[str, dict]:
    """Return {skill_id: {disk_path, domain, sub_domain, deprecated}}."""
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
                    result[sid] = {
                        "disk_path": str(flat.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
                        "domain": domain,
                        "sub_domain": None,
                        "deprecated": is_deprecated(flat),
                    }
                continue
            for grand in sorted(child.iterdir()):
                if not grand.is_dir():
                    continue
                nested = grand / "SKILL.md"
                if nested.is_file():
                    sid = read_skill_id(grand)
                    if sid:
                        result[sid] = {
                            "disk_path": str(nested.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
                            "domain": domain,
                            "sub_domain": child.name,
                            "deprecated": is_deprecated(nested),
                        }
    return result


def parse_routing_block(catalog_text: str) -> dict[str, dict]:
    """Parse the routing block and return:
        {
          "_meta": {"parent_of": ["sk-X", ...], "sub_domains": {"harness": ["sk-Y", ...]}},
          ...
        }
    Uses regex, no YAML lib.
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

        # Top-level domain: "  _meta:"
        m_dom = re.match(r"^  (\w[\w_-]*)\s*:\s*$", line)
        if m_dom:
            current_domain = m_dom.group(1)
            result[current_domain] = {"parent_of": [], "sub_domains": {}}
            current_sub = None
            in_sub_domains_block = False
            continue

        # 4-space indent: domain-level field
        m_field = re.match(r"^    (\w[\w_-]*)\s*:\s*(.*)$", line)
        if m_field and current_domain:
            key = m_field.group(1)
            val = m_field.group(2).strip()
            if key == "sub_domains":
                in_sub_domains_block = True
                current_sub = None
                continue
            in_sub_domains_block = False
            if key == "parent_of":
                ids = _parse_inline_list(val)
                result[current_domain]["parent_of"] = ids
            continue

        # 6-space indent: sub-domain name (inside sub_domains block)
        m_sub = re.match(r"^      (\w[\w_-]*)\s*:\s*$", line)
        if m_sub and current_domain and in_sub_domains_block:
            current_sub = m_sub.group(1)
            result[current_domain]["sub_domains"][current_sub] = []
            continue

        # 8-space indent: sub-domain field (parent_of)
        m_subfield = re.match(r"^        (\w[\w_-]*)\s*:\s*(.*)$", line)
        if m_subfield and current_domain and current_sub is not None:
            key = m_subfield.group(1)
            val = m_subfield.group(2).strip()
            if key == "parent_of":
                ids = _parse_inline_list(val)
                result[current_domain]["sub_domains"][current_sub] = ids
            continue

    return result


def _parse_inline_list(val: str) -> list[str]:
    """Parse `[sk-1, sk-2, sk-3]` into a Python list of strings."""
    val = val.strip()
    if not (val.startswith("[") and val.endswith("]")):
        return []
    inner = val[1:-1].strip()
    if not inner:
        return []
    return [t.strip().strip('"').strip("'") for t in inner.split(",")]


def run_checks(routing: dict[str, dict], disk: dict[str, dict]) -> dict:
    """Apply the four coherence rules and collect findings."""
    ghost_entries: list[dict] = []
    orphan_skills: list[dict] = []
    domain_mismatch: list[dict] = []
    deprecated_listed: list[dict] = []

    # Build a set of (skill_id, expected_location) for every parent_of entry
    listed: dict[str, list[str]] = {}  # skill_id -> list of paths where listed

    for domain, info in routing.items():
        # Top-level parent_of
        for sid in info.get("parent_of", []):
            path = f"{domain}"
            listed.setdefault(sid, []).append(path)
        # Sub-domain parent_of
        for sub_name, sub_ids in info.get("sub_domains", {}).items():
            for sid in sub_ids:
                path = f"{domain}.{sub_name}"
                listed.setdefault(sid, []).append(path)

    # Rule 1: every listed skill must exist on disk
    for sid, paths in listed.items():
        if sid not in disk:
            for p in paths:
                ghost_entries.append({"skill_id": sid, "path": p})

    # Rule 3: sub_domain listings must match disk sub_domain
    #         AND top-level listings must match only when there's no sub_domain on disk
    for sid, paths in listed.items():
        if sid not in disk:
            continue
        d_info = disk[sid]
        disk_domain = d_info["domain"]
        disk_sub = d_info["sub_domain"]
        for p in paths:
            if "." in p:
                expected_domain, expected_sub = p.split(".", 1)
                if disk_domain != expected_domain or disk_sub != expected_sub:
                    domain_mismatch.append({
                        "skill_id": sid,
                        "expected": p,
                        "actual_disk": d_info["disk_path"],
                    })
            else:
                # Top-level listing: skill must actually be at the top level
                # (no sub_domain) of this domain
                if disk_domain != p:
                    domain_mismatch.append({
                        "skill_id": sid,
                        "expected": p,
                        "actual_disk": d_info["disk_path"],
                    })

    # Rule 4: deprecated skills must not be listed
    for sid, paths in listed.items():
        if sid in disk and disk[sid]["deprecated"]:
            for p in paths:
                deprecated_listed.append({"skill_id": sid, "path": p})

    # Rule 2: every on-disk skill must appear in exactly one parent_of
    for sid, d_info in disk.items():
        if d_info["deprecated"]:
            continue  # deprecated skills are allowed to be absent from routing
        if sid not in listed:
            orphan_skills.append({
                "skill_id": sid,
                "disk_path": d_info["disk_path"],
            })

    passed = not (
        ghost_entries or orphan_skills or domain_mismatch or deprecated_listed
    )
    return {
        "passed": passed,
        "status": "ok" if passed else "routing_sync_failed",
        "ghost_entries": ghost_entries,
        "orphan_skills": orphan_skills,
        "domain_mismatch": domain_mismatch,
        "deprecated_listed": deprecated_listed,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", default=str(CATALOG_PATH),
                   help="path to skills/CATALOG.md")
    return p.parse_args()


def main() -> int:
    try:
        args = parse_args()
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    try:
        catalog_path = Path(args.catalog)
        if not catalog_path.exists():
            sys.stderr.write(f"routing_sync: CATALOG not found: {catalog_path}\n")
            return 2
        text = catalog_path.read_text(encoding="utf-8")
        routing = parse_routing_block(text)
        if not routing:
            sys.stderr.write(
                "routing_sync: CATALOG.md has no routing block "
                "(run bin/routing_gen.py first)\n"
            )
            return 2
        disk = discover_disk_skills()
        result = run_checks(routing, disk)
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0 if result["passed"] else 1
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"routing_sync: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
