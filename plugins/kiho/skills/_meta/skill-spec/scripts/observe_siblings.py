#!/usr/bin/env python3
"""
observe_siblings.py — Step C of skill-architect: sibling pattern observer.

For a given parent_domain, walks the catalog and computes the modal layout,
modal capability, and divergence score against the proposal. Output drives
Step D (LLM critic fires only if divergence > 0.30) and Step E (user
confirmation surfaces sibling evidence in the rationale).

Exit codes (0/1/2/3):
    0 — observation complete
    1 — insufficient siblings (< 2 siblings in domain) — domain too new for telemetry
    2 — usage error
    3 — internal error

Usage:
    observe_siblings.py --domain core/harness
    observe_siblings.py --domain _meta --proposal-layout meta-with-scripts
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = PLUGIN_ROOT / "skills"


def observe_skill_layout(skill_md: Path) -> dict[str, Any]:
    skill_dir = skill_md.parent
    has_scripts = (skill_dir / "scripts").is_dir() and any((skill_dir / "scripts").glob("*.py"))
    has_refs = (skill_dir / "references").is_dir() and any((skill_dir / "references").glob("*.md"))

    if has_scripts and has_refs:
        layout = "meta-with-both"
    elif has_scripts:
        layout = "meta-with-scripts"
    elif has_refs:
        layout = "meta-with-refs"
    else:
        layout = "standard"

    text = skill_md.read_text(encoding="utf-8")
    cap_match = re.search(r"^\s+capability:\s*(\S+)", text, re.M)
    capability = cap_match.group(1) if cap_match else "unknown"

    return {"layout": layout, "capability": capability,
            "path": str(skill_md.relative_to(PLUGIN_ROOT)).replace("\\", "/")}


def list_siblings(domain: str) -> list[Path]:
    """List SKILL.md files in the given parent_domain (path under skills/)."""
    domain_path = SKILLS_ROOT / domain
    if not domain_path.is_dir():
        return []
    return sorted(domain_path.glob("*/SKILL.md"))


def observe_domain(domain: str) -> dict[str, Any]:
    sibling_files = list_siblings(domain)
    if len(sibling_files) < 2:
        return {"status": "insufficient_siblings", "domain": domain, "n": len(sibling_files)}

    observations = [observe_skill_layout(s) for s in sibling_files]
    layouts = [o["layout"] for o in observations]
    capabilities = [o["capability"] for o in observations]

    layout_counter = Counter(layouts)
    capability_counter = Counter(capabilities)

    modal_layout, modal_layout_count = layout_counter.most_common(1)[0]
    modal_capability, modal_capability_count = capability_counter.most_common(1)[0]

    layout_consensus = modal_layout_count / len(layouts)

    return {
        "status": "ok",
        "domain": domain,
        "n_siblings": len(observations),
        "modal_layout": modal_layout,
        "modal_layout_consensus": round(layout_consensus, 2),
        "layout_distribution": dict(layout_counter),
        "modal_capability": modal_capability,
        "capability_distribution": dict(capability_counter),
        "siblings": observations,
    }


def compute_divergence(domain_obs: dict[str, Any], proposal_layout: str | None) -> dict[str, Any]:
    if domain_obs["status"] != "ok" or proposal_layout is None:
        return {"divergence_score": 0.0, "matches_modal": None}

    modal = domain_obs["modal_layout"]
    if proposal_layout == modal:
        return {
            "divergence_score": 0.0,
            "matches_modal": True,
            "evidence": f"proposal '{proposal_layout}' matches modal layout for {domain_obs['domain']} (consensus {domain_obs['modal_layout_consensus']})",
        }

    domain_share = domain_obs["layout_distribution"].get(proposal_layout, 0) / domain_obs["n_siblings"]
    divergence = 1.0 - domain_share
    return {
        "divergence_score": round(divergence, 2),
        "matches_modal": False,
        "evidence": (
            f"proposal '{proposal_layout}' matches {round(domain_share, 2)} share of siblings; "
            f"modal is '{modal}' ({domain_obs['modal_layout_consensus']})"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="skill-architect Step C — sibling pattern observer")
    ap.add_argument("--domain", required=True,
                    help="parent_domain path (e.g., core/harness, _meta)")
    ap.add_argument("--proposal-layout", help="proposed parity_layout for divergence calculation")
    args = ap.parse_args()

    try:
        domain_obs = observe_domain(args.domain)
        if domain_obs["status"] == "insufficient_siblings":
            print(json.dumps(domain_obs, indent=2))
            return 1

        divergence = compute_divergence(domain_obs, args.proposal_layout)

        result = {
            **domain_obs,
            "divergence": divergence,
        }
        print(json.dumps(result, indent=2))
        return 0

    except SystemExit:
        raise
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
