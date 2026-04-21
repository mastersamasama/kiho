#!/usr/bin/env python3
"""
parity_diff.py — cross-sibling structural-fingerprint diff against canonical layouts.

For each target skill, computes a structural fingerprint and diffs against the
canonical layout for its parent_domain (declared in
skills/_meta/skill-parity/references/canonical-layouts.md). Refuses regen when
the diff is non-empty unless the target declares
metadata.kiho.parity_exception with a one-line rationale.

Modes:
    pre-regen      — single-skill check before write
    catalog-audit  — all skills; report divergences without blocking

Exit codes (0/1/2/3 per v5.15.2 Pattern 9):
    0 — success (all targets match canonical OR have authorized exceptions)
    1 — policy violation (layout divergence without exception, OR
        unauthorized exception)
    2 — usage error (missing target, unknown domain)
    3 — internal error

Usage:
    parity_diff.py --target <skill_path> --mode pre-regen
    parity_diff.py --mode catalog-audit

Grounding: GEPA Pareto-frontier discipline (arXiv 2507.19457); v5.17 research
findings §"7 missing pieces #5".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = PLUGIN_ROOT / "skills"

LAYOUT_DEFINITIONS = {
    "standard": {
        "scripts_required": False,
        "references_required": False,
    },
    "meta-with-scripts": {
        "scripts_required": True,
        "references_required": False,
    },
    "meta-with-refs": {
        "scripts_required": False,
        "references_required": True,
    },
    "meta-with-both": {
        "scripts_required": True,
        "references_required": True,
    },
    "parity-exception": {
        "scripts_required": None,
        "references_required": None,
    },
}

DEFAULT_DOMAIN_LAYOUT = {
    "_meta/skill-create": "meta-with-both",
    "_meta/skill-spec": "meta-with-both",
    "_meta/skill-structural-gate": "meta-with-both",
    "_meta/skill-graph": "standard",       # deprecation shim — see canonical-layouts.md _meta/deprecated-shim
    "_meta/skill-parity": "standard",      # deprecation shim
    "_meta/skill-architect": "standard",   # deprecation shim
    "_meta/skill-factory": "standard",     # 2026-04-17 slimmed to SKILL.md only; cross-links to other skills for gate details
    "_meta/skill-find": "parity-exception",
    "_meta/skill-improve": "standard",
    "_meta/skill-derive": "standard",
    "_meta/skill-deprecate": "meta-with-refs",
    "_meta/skill-learn": "meta-with-refs",
    "_meta/evolution-scan": "standard",
    "_meta/soul-apply-override": "standard",
    "core/harness": "meta-with-scripts",
    "core/hr": "meta-with-refs",
    "core/inspection": "standard",
    "core/knowledge": "standard",
    "core/planning": "standard",
    "kb": "standard",
    "memory": "standard",
    "engineering": "parity-exception",
}


def load_skill(skill_md: Path) -> dict[str, Any]:
    text = skill_md.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\n(.+?)\n---\n", text, re.S)
    frontmatter: dict[str, Any] = {}
    metadata_kiho: dict[str, Any] = {}
    if fm_match:
        fm = fm_match.group(1)
        for line in fm.splitlines():
            m = re.match(r"^([a-z_-]+):\s*(.*)$", line)
            if m:
                frontmatter[m.group(1)] = m.group(2).strip()
        # Look inside metadata.kiho
        in_kiho = False
        in_metadata = False
        for line in fm.splitlines():
            if line.startswith("metadata:"):
                in_metadata = True
                continue
            if in_metadata and line.lstrip().startswith("kiho:"):
                in_kiho = True
                continue
            if in_kiho:
                m = re.match(r"^\s+([a-z_-]+):\s*(.*)$", line)
                if m and not line.startswith("    "):
                    pass
                if m:
                    metadata_kiho[m.group(1)] = m.group(2).strip().strip("[]")
                if not line.strip() or line.startswith("---"):
                    in_kiho = False

    skill_dir = skill_md.parent
    scripts_dir = skill_dir / "scripts"
    references_dir = skill_dir / "references"
    # Accept either config.toml (post v5.19.3) or config.yaml (pre-migration).
    # Layout-parity cares only about whether a config file exists; the tech
    # stack committee (Phase 1) approved either extension during the lazy-
    # migration window.
    config_file = next(
        (skill_dir / f"config.{ext}" for ext in ("toml", "yaml")
         if (skill_dir / f"config.{ext}").is_file()),
        None,
    )

    scripts_files = sorted(p.name for p in scripts_dir.glob("*.py")) if scripts_dir.is_dir() else []
    references_files = sorted(p.name for p in references_dir.glob("*.md")) if references_dir.is_dir() else []

    body = text[fm_match.end():] if fm_match else text
    headings = sorted(set(re.findall(r"^##\s+(.+)$", body, re.M)))

    return {
        "frontmatter_keys": sorted(frontmatter.keys()),
        "metadata_kiho_keys": sorted(metadata_kiho.keys()),
        "scripts_files": scripts_files,
        "references_files": references_files,
        "has_config_yaml": config_file is not None,  # legacy key name kept for
                                                     # backward-compat with
                                                     # existing callers
        "config_file": config_file.name if config_file else None,
        "body_section_headings": headings,
        "raw_metadata_kiho": metadata_kiho,
    }


def determine_domain(skill_md: Path) -> str:
    rel = skill_md.relative_to(SKILLS_ROOT).parent.as_posix()
    parts = rel.split("/")
    if parts[0] == "_meta":
        return f"_meta/{parts[1]}" if len(parts) >= 2 else "_meta"
    if parts[0] == "core" and len(parts) >= 2:
        return f"core/{parts[1]}"
    return parts[0]


def determine_canonical_layout(domain: str, skill_metadata: dict[str, Any]) -> str:
    if "parity_exception" in skill_metadata or skill_metadata.get("parity_layout") == "parity-exception":
        return "parity-exception"
    if domain in DEFAULT_DOMAIN_LAYOUT:
        return DEFAULT_DOMAIN_LAYOUT[domain]
    parent = domain.split("/")[0]
    if parent in DEFAULT_DOMAIN_LAYOUT:
        return DEFAULT_DOMAIN_LAYOUT[parent]
    return "standard"


def diff_layout(fingerprint: dict[str, Any], canonical: str) -> list[dict[str, Any]]:
    if canonical == "parity-exception":
        return []
    spec = LAYOUT_DEFINITIONS[canonical]
    diff: list[dict[str, Any]] = []

    if spec["scripts_required"] is True and not fingerprint["scripts_files"]:
        diff.append({
            "axis": "scripts_files",
            "expected": "≥ 1 .py file",
            "actual": [],
            "fix": "add scripts/ subdirectory with at least one .py file",
        })
    if spec["scripts_required"] is False and fingerprint["scripts_files"]:
        diff.append({
            "axis": "scripts_files",
            "expected": [],
            "actual": fingerprint["scripts_files"],
            "fix": "move scripts to bin/ if cross-skill, or change layout to meta-with-scripts/meta-with-both",
        })

    if spec["references_required"] is True and not fingerprint["references_files"]:
        diff.append({
            "axis": "references_files",
            "expected": "≥ 1 .md file",
            "actual": [],
            "fix": "add references/ subdirectory with at least one .md file",
        })
    if spec["references_required"] is False and fingerprint["references_files"]:
        diff.append({
            "axis": "references_files",
            "expected": [],
            "actual": fingerprint["references_files"],
            "fix": "move references inline into SKILL.md, or change layout to meta-with-refs/meta-with-both",
        })

    return diff


def check_exception(metadata: dict[str, Any]) -> tuple[bool, str]:
    if "parity_exception" in metadata:
        rationale = metadata["parity_exception"]
        if not rationale or len(rationale) < 10:
            return (False, "parity_exception declared but no rationale (≥ 10 chars)")
        return (True, rationale)
    return (False, "")


def audit_skill(skill_md: Path) -> dict[str, Any]:
    info = load_skill(skill_md)
    domain = determine_domain(skill_md)
    canonical = determine_canonical_layout(domain, info["raw_metadata_kiho"])

    if canonical == "parity-exception":
        ok, rationale = check_exception(info["raw_metadata_kiho"])
        if ok:
            status = "ok_with_exception"
            diff: list[dict[str, Any]] = []
        else:
            status = "unauthorized_exception"
            diff = [{"axis": "parity_exception", "expected": "rationale ≥ 10 chars", "actual": rationale}]
    else:
        diff = diff_layout(info, canonical)
        status = "ok" if not diff else "layout_divergence"

    return {
        "status": status,
        "target": str(skill_md.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
        "domain": domain,
        "canonical_layout": canonical,
        "fingerprint": {
            "frontmatter_keys": info["frontmatter_keys"],
            "metadata_kiho_keys": info["metadata_kiho_keys"],
            "references_files": info["references_files"],
            "scripts_files": info["scripts_files"],
            "has_config_yaml": info["has_config_yaml"],
            "body_section_headings": info["body_section_headings"][:8],
        },
        "diff": diff,
        "warnings": [],
    }


def resolve_target(target: str) -> Path | None:
    p = Path(target)
    if p.is_absolute() and p.is_file():
        return p
    candidate = PLUGIN_ROOT / target
    if candidate.is_file():
        return candidate
    if SKILLS_ROOT.is_dir():
        for skill_md in SKILLS_ROOT.rglob("SKILL.md"):
            try:
                fm = re.search(r"^name:\s*(\S+)", skill_md.read_text(encoding="utf-8"), re.M)
                if fm and fm.group(1) == target:
                    return skill_md
                if skill_md.parent.name == target:
                    return skill_md
            except (OSError, UnicodeDecodeError):
                continue
    return None


def compute_telemetry_canonical(domain: str) -> dict[str, Any]:
    """Compute the modal layout for a domain from observed siblings (Gap 4 fix)."""
    domain_path = SKILLS_ROOT / domain
    if not domain_path.is_dir():
        return {"status": "domain_not_found", "domain": domain}

    sibling_files = sorted(domain_path.glob("*/SKILL.md"))
    if len(sibling_files) < 5:
        return {
            "status": "insufficient_data",
            "domain": domain,
            "n_siblings": len(sibling_files),
            "message": "need >= 5 siblings for stable canonical inference",
        }

    layouts = []
    for skill_md in sibling_files:
        info = load_skill(skill_md)
        if info["scripts_files"] and info["references_files"]:
            layouts.append("meta-with-both")
        elif info["scripts_files"]:
            layouts.append("meta-with-scripts")
        elif info["references_files"]:
            layouts.append("meta-with-refs")
        else:
            layouts.append("standard")

    from collections import Counter
    counter = Counter(layouts)
    modal, modal_count = counter.most_common(1)[0]
    consensus = modal_count / len(layouts)

    declared = DEFAULT_DOMAIN_LAYOUT.get(domain) or DEFAULT_DOMAIN_LAYOUT.get(domain.split("/")[0])

    return {
        "status": "ok",
        "domain": domain,
        "n_siblings": len(sibling_files),
        "observed_modal": modal,
        "observed_consensus": round(consensus, 2),
        "distribution": dict(counter),
        "declared_canonical": declared,
        "drift": modal != declared,
        "stable_at_threshold_80": consensus >= 0.80,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-sibling structural-diff parity checker")
    ap.add_argument("--target", help="path / name of skill to check")
    ap.add_argument("--mode", choices=["pre-regen", "catalog-audit"], default="pre-regen")
    ap.add_argument("--telemetry-driven", action="store_true",
                    help="Compute canonical from observed siblings instead of declared (Gap 4 fix); emits warnings only")
    ap.add_argument("--domain", help="domain to inspect with --telemetry-driven (e.g., core/harness)")
    args = ap.parse_args()

    try:
        if args.telemetry_driven:
            domains_to_audit: list[str]
            if args.domain:
                domains_to_audit = [args.domain]
            else:
                domains_to_audit = sorted({
                    str(p.parent.parent.relative_to(SKILLS_ROOT)).replace("\\", "/")
                    for p in SKILLS_ROOT.rglob("SKILL.md")
                })
            results = [compute_telemetry_canonical(d) for d in domains_to_audit]
            drift = [r for r in results if r.get("status") == "ok" and r.get("drift")]
            print(json.dumps({
                "mode": "telemetry-driven",
                "domains_checked": len(results),
                "drift_count": len(drift),
                "drift_warnings": drift,
                "all_results": results,
            }, indent=2))
            return 0  # warning-only mode

        if args.mode == "catalog-audit":
            results = [audit_skill(p) for p in sorted(SKILLS_ROOT.rglob("SKILL.md"))]
            divergences = [r for r in results if r["status"] not in ("ok", "ok_with_exception")]
            print(json.dumps({
                "mode": "catalog-audit",
                "total": len(results),
                "ok": sum(1 for r in results if r["status"] == "ok"),
                "ok_with_exception": sum(1 for r in results if r["status"] == "ok_with_exception"),
                "divergent": len(divergences),
                "divergences": divergences,
            }, indent=2))
            return 0 if not divergences else 1

        if not args.target:
            print(json.dumps({"status": "usage_error", "message": "--target required for pre-regen mode"}))
            return 2

        target_path = resolve_target(args.target)
        if target_path is None:
            print(json.dumps({"status": "target_not_found", "target": args.target}))
            return 2

        result = audit_skill(target_path)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] in ("ok", "ok_with_exception") else 1

    except SystemExit:
        raise
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
