#!/usr/bin/env python3
"""
graph_scan.py — inbound dependency + cross-anchor stale-path scanner.

Pre-gate for skill regenerations and deprecations. Wraps bin/kiho_rdeps.py
for the forward-edge inbound-dep half and adds a 4-anchor stale-path scan
across CLAUDE.md, agents/*.md, README.md, and templates/*.md (the four
surfaces where stale references historically hide; see v5.16.3 incident
where 4 stale `skills/kiho/config.yaml` references survived a sub-domain
split).

Modes:
    pre-regen          — full inbound + 4-anchor scan
    deprecation-check  — refuses if any consumer hard-requires the target
    rename-audit       — checks new_path doesn't collide with existing skill

Exit codes (0/1/2/3 per v5.15.2 Pattern 9):
    0 — success (scan clean OR ok_with_warnings)
    1 — policy violation (stale paths, hard consumers blocking deprecation,
        rename collision)
    2 — usage error (missing target, invalid mode)
    3 — internal error

Usage:
    graph_scan.py --target <skill_path> --mode pre-regen
    graph_scan.py --target <skill_name> --mode deprecation-check
    graph_scan.py --target <old_path> --mode rename-audit --new-path <new_path>

Grounding: v5.15 H5 (forward-only / compute-on-demand) + v5.16.3 incident.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = PLUGIN_ROOT / "skills"
KIHO_RDEPS = PLUGIN_ROOT / "bin" / "kiho_rdeps.py"

ANCHOR_FILES: list[Path] = []


def collect_anchors() -> list[Path]:
    anchors: list[Path] = []
    claude_md = PLUGIN_ROOT / "CLAUDE.md"
    if claude_md.exists():
        anchors.append(claude_md)
    readme = PLUGIN_ROOT / "README.md"
    if readme.exists():
        anchors.append(readme)
    agents_dir = PLUGIN_ROOT / "agents"
    if agents_dir.is_dir():
        anchors.extend(sorted(agents_dir.glob("*.md")))
    templates_dir = PLUGIN_ROOT / "templates"
    if templates_dir.is_dir():
        anchors.extend(sorted(templates_dir.glob("*.md")))
    return anchors


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


def derive_search_terms(target_path: Path) -> list[str]:
    """The substrings to grep for in anchor files to detect references."""
    terms: list[str] = []
    rel = target_path.relative_to(PLUGIN_ROOT).as_posix()
    skill_dir = target_path.parent.relative_to(PLUGIN_ROOT).as_posix()
    skill_name = target_path.parent.name
    terms.append(skill_dir + "/")
    terms.append(skill_dir)
    terms.append(rel)
    if skill_name not in {"SKILL.md", "_meta", "core", "kb", "memory"}:
        terms.append(f"/{skill_name}/")
    return list(dict.fromkeys(terms))


def scan_anchors(target_path: Path, search_terms: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for anchor in ANCHOR_FILES:
        try:
            text = anchor.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_num, line in enumerate(text.splitlines(), 1):
            for term in search_terms:
                if term in line and not line.lstrip().startswith("# "):
                    findings.append({
                        "file": str(anchor.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
                        "line": line_num,
                        "context": line.strip()[:120],
                        "matched_term": term,
                    })
                    break
    return findings


def scan_for_stale_paths(target_path: Path) -> list[dict[str, Any]]:
    """Look for paths that NO LONGER EXIST referenced in the 4 anchors."""
    findings: list[dict[str, Any]] = []
    rel_path = target_path.relative_to(PLUGIN_ROOT).as_posix()
    skill_dir = target_path.parent.relative_to(PLUGIN_ROOT).as_posix()
    skill_name = target_path.parent.name

    likely_old_paths = [
        f"skills/{skill_name}/",
        f"skills/{skill_name}",
    ]
    if "core/harness" in skill_dir:
        likely_old_paths.append(f"skills/{skill_name}/")
    elif "core/" in skill_dir:
        likely_old_paths.append(f"skills/{skill_name}/")

    likely_old_paths = [p for p in likely_old_paths if p != f"skills/{skill_dir.split('/')[-1]}/"]
    likely_old_paths = list(dict.fromkeys(likely_old_paths))

    for anchor in ANCHOR_FILES:
        try:
            text = anchor.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_num, line in enumerate(text.splitlines(), 1):
            for old in likely_old_paths:
                if old in line:
                    referenced_full = re.search(re.escape(old) + r"[\w./]*", line)
                    if referenced_full:
                        referenced = referenced_full.group(0)
                        full = (PLUGIN_ROOT / referenced).resolve()
                        if not full.exists():
                            suggested = referenced.replace(old, f"{skill_dir}/", 1)
                            findings.append({
                                "file": str(anchor.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
                                "line": line_num,
                                "context": referenced,
                                "suggested": suggested,
                            })
                            break
    return findings


def invoke_kiho_rdeps(target_path: Path) -> dict[str, Any]:
    if not KIHO_RDEPS.exists():
        return {"error": "kiho_rdeps.py not found", "consumers": {}}
    try:
        out = subprocess.run(
            [sys.executable, str(KIHO_RDEPS), str(target_path)],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode in (0, 1):
            try:
                return json.loads(out.stdout)
            except json.JSONDecodeError:
                return {"error": "rdeps output not JSON", "raw": out.stdout[:200]}
        return {"error": f"rdeps exit {out.returncode}", "stderr": out.stderr[:200]}
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"error": str(exc)}


def main() -> int:
    global ANCHOR_FILES
    ap = argparse.ArgumentParser(description="Inbound dep + 4-anchor stale-path scanner")
    ap.add_argument("--target", required=True, help="path / name / id of skill to scan")
    ap.add_argument("--mode", choices=["pre-regen", "deprecation-check", "rename-audit"], default="pre-regen")
    ap.add_argument("--new-path", help="proposed new path (rename-audit mode)")
    args = ap.parse_args()

    try:
        target_path = resolve_target(args.target)
        if target_path is None:
            print(json.dumps({"status": "target_not_found", "target": args.target}, indent=2))
            return 2

        ANCHOR_FILES = collect_anchors()

        if args.mode == "rename-audit":
            if not args.new_path:
                print(json.dumps({"status": "usage_error", "message": "--new-path required for rename-audit"}))
                return 2
            new_path = PLUGIN_ROOT / args.new_path
            if new_path.exists():
                print(json.dumps({
                    "status": "rename_collision",
                    "target": str(target_path.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
                    "new_path": args.new_path,
                    "message": f"new_path {args.new_path} already exists",
                }, indent=2))
                return 1

        rdeps = invoke_kiho_rdeps(target_path)
        consumers = rdeps.get("consumers", {})

        if args.mode == "deprecation-check":
            hard = consumers.get("hard_requires", [])
            if hard:
                print(json.dumps({
                    "status": "consumers_block",
                    "target": str(target_path.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
                    "mode": args.mode,
                    "hard_consumers": hard,
                    "message": f"{len(hard)} consumer(s) hard-require this skill; cannot deprecate",
                }, indent=2))
                return 1

        search_terms = derive_search_terms(target_path)
        anchor_refs = scan_anchors(target_path, search_terms)
        stale_findings = scan_for_stale_paths(target_path)

        if stale_findings:
            print(json.dumps({
                "status": "stale_path_references",
                "target": str(target_path.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
                "mode": args.mode,
                "stale_path_findings": stale_findings,
                "consumers": consumers,
                "anchor_references": anchor_refs,
            }, indent=2))
            return 1

        print(json.dumps({
            "status": "ok",
            "target": str(target_path.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
            "mode": args.mode,
            "consumers": consumers,
            "anchor_references": anchor_refs,
            "stale_path_findings": [],
            "warnings": [],
        }, indent=2))
        return 0

    except SystemExit:
        raise
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
