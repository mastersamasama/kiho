#!/usr/bin/env python3
"""
agent_density.py — Gate 24: per-agent skill-portfolio density (v5.16).

Measures each agent's skill portfolio across two axes:
  - per-CAPABILITY density (warn >=5, error >=8)
  - per-DOMAIN density     (warn >=8, error >=12)

At |S| >= 20, the arXiv 2601.04748 §5.2 phase transition kicks in: if
an agent loads too many skills with the same capability verb or from
the same domain, the in-agent selection accuracy drops even when the
global catalog is clean. Gate 24 is a warn tier in v5.16 — it cannot
block skill-create (agent design is out of that scope), but it runs
during design-agent Step 4 and as a standalone audit.

Reads agents/*.md frontmatter `skills: [sk-X, sk-Y, ...]` arrays, looks
up each skill ID in the skills/ tree, and aggregates density counts
keyed by (agent, capability) and (agent, domain).

Grounding: v5.16 Primitive 2 (capability taxonomy enables per-capability
density) + arXiv §5.2 phase transition. Plan Stage F.

Usage:
    agent_density.py
    agent_density.py --cap-warn 5 --cap-err 8 --dom-warn 8 --dom-err 12

Exit codes (0/1/2/3):
    0 — all agents within warn thresholds
    1 — policy violation: at least one agent exceeds an error threshold
    2 — usage error
    3 — internal error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent.parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
AGENTS_DIR = PLUGIN_ROOT / "agents"

DEFAULT_CAP_WARN = 5
DEFAULT_CAP_ERR = 8
DEFAULT_DOM_WARN = 8
DEFAULT_DOM_ERR = 12


def read_skill_id(skill_dir: Path) -> str:
    sid_path = skill_dir / ".skill_id"
    if sid_path.exists():
        return sid_path.read_text(encoding="utf-8").strip()
    return ""


def extract_skill_facets(skill_md: Path) -> dict:
    """Return {capability, topic_tags, domain, sub_domain}."""
    text = skill_md.read_text(encoding="utf-8")
    out = {"capability": "", "topic_tags": [], "domain": "", "sub_domain": None}
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return out
    fm = m.group(1)
    cap_m = re.search(
        r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+capability:\s*(\w+)",
        fm,
        re.MULTILINE,
    )
    if cap_m:
        out["capability"] = cap_m.group(1)
    return out


def build_skill_index() -> dict[str, dict]:
    """Return {skill_id: {capability, domain, sub_domain, path}}."""
    index: dict[str, dict] = {}
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
                    facets = extract_skill_facets(flat)
                    facets["domain"] = domain
                    facets["sub_domain"] = None
                    facets["path"] = str(flat.relative_to(PLUGIN_ROOT)).replace("\\", "/")
                    index[sid] = facets
                continue
            for grand in sorted(child.iterdir()):
                if not grand.is_dir():
                    continue
                nested = grand / "SKILL.md"
                if nested.is_file():
                    sid = read_skill_id(grand)
                    if sid:
                        facets = extract_skill_facets(nested)
                        facets["domain"] = domain
                        facets["sub_domain"] = child.name
                        facets["path"] = str(nested.relative_to(PLUGIN_ROOT)).replace("\\", "/")
                        index[sid] = facets
    return index


def extract_agent_skills(agent_md: Path) -> list[str]:
    """Parse frontmatter 'skills: [sk-X, sk-Y, ...]' array."""
    text = agent_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return []
    fm = m.group(1)
    sk_m = re.search(r"^skills:\s*\[([^\]]*)\]", fm, re.MULTILINE)
    if not sk_m:
        return []
    raw = sk_m.group(1)
    return [t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()]


def discover_agents() -> list[Path]:
    result: list[Path] = []
    if not AGENTS_DIR.is_dir():
        return result
    for child in sorted(AGENTS_DIR.iterdir()):
        if child.is_file() and child.suffix == ".md" and not child.name.startswith("_"):
            result.append(child)
    return result


def assess_agent(
    agent_path: Path,
    skill_index: dict[str, dict],
    cap_warn: int,
    cap_err: int,
    dom_warn: int,
    dom_err: int,
) -> dict:
    skill_ids = extract_agent_skills(agent_path)
    total = len(skill_ids)
    cap_counts: Counter = Counter()
    dom_counts: Counter = Counter()
    unknown_ids: list[str] = []
    for sid in skill_ids:
        if sid not in skill_index:
            unknown_ids.append(sid)
            continue
        facets = skill_index[sid]
        cap = facets.get("capability", "")
        dom = facets.get("domain", "")
        if cap:
            cap_counts[cap] += 1
        if dom:
            dom_counts[dom] += 1

    flags: list[dict] = []
    worst_level = "ok"
    for cap, count in cap_counts.items():
        if count >= cap_err:
            flags.append({"axis": "capability", "key": cap, "count": count, "level": "error"})
            worst_level = "error"
        elif count >= cap_warn:
            flags.append({"axis": "capability", "key": cap, "count": count, "level": "warn"})
            if worst_level == "ok":
                worst_level = "warn"
    for dom, count in dom_counts.items():
        if count >= dom_err:
            flags.append({"axis": "domain", "key": dom, "count": count, "level": "error"})
            worst_level = "error"
        elif count >= dom_warn:
            flags.append({"axis": "domain", "key": dom, "count": count, "level": "warn"})
            if worst_level == "ok":
                worst_level = "warn"

    return {
        "agent": agent_path.stem,
        "total_skills": total,
        "capability_counts": dict(cap_counts),
        "domain_counts": dict(dom_counts),
        "unknown_skill_ids": unknown_ids,
        "flags": flags,
        "level": worst_level,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cap-warn", type=int, default=DEFAULT_CAP_WARN)
    p.add_argument("--cap-err", type=int, default=DEFAULT_CAP_ERR)
    p.add_argument("--dom-warn", type=int, default=DEFAULT_DOM_WARN)
    p.add_argument("--dom-err", type=int, default=DEFAULT_DOM_ERR)
    return p.parse_args()


def main() -> int:
    try:
        args = parse_args()
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    try:
        index = build_skill_index()
        if not index:
            sys.stderr.write("agent_density: no skills discovered\n")
            return 2
        agents = discover_agents()
        if not agents:
            sys.stderr.write("agent_density: no agents discovered\n")
            return 2
        reports = [
            assess_agent(a, index, args.cap_warn, args.cap_err, args.dom_warn, args.dom_err)
            for a in agents
        ]
        errors = [r for r in reports if r["level"] == "error"]
        warnings_ = [r for r in reports if r["level"] == "warn"]
        summary = {
            "total_agents": len(reports),
            "errors": len(errors),
            "warnings": len(warnings_),
            "passing": len(reports) - len(errors) - len(warnings_),
            "thresholds": {
                "cap_warn": args.cap_warn,
                "cap_err": args.cap_err,
                "dom_warn": args.dom_warn,
                "dom_err": args.dom_err,
            },
            "reports": reports,
        }
        sys.stdout.write(json.dumps(summary, indent=2) + "\n")
        return 1 if errors else 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"agent_density: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
