#!/usr/bin/env python3
"""
isolation_manifest.py — Gate 12 isolation manifest generator (v5.14).

Scans a draft skill directory and lists every filesystem path, environment
variable, and external-resource touch point the skill declares in its body,
scripts, or references. Produces a manifest that the Gate 11 eval harness
must clean/reset before each trial to ensure scenario independence.

Grounding: Anthropic Jan 2026 "Demystifying Evals for AI Agents" — environment
isolation per trial is one of the three core eval principles. v5.14 H1.

Usage:
    isolation_manifest.py --draft-dir <path> [--out manifest.json]

Exit codes:
    0 — manifest generated (empty or populated)
    1 — warnings found (reserved; currently unused)
    2 — usage error or draft dir missing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# Patterns that indicate an external touch point. Tuned for false-positive
# avoidance over exhaustiveness — prefer missing a niche case than flagging
# every innocuous string.
FS_WRITE_PATTERNS = [
    re.compile(r"\bWrite\(", re.IGNORECASE),
    re.compile(r"\bEdit\(", re.IGNORECASE),
    re.compile(r"open\([^)]*['\"]w", re.IGNORECASE),
    re.compile(r"\.write_text\(", re.IGNORECASE),
    re.compile(r"\.write_bytes\(", re.IGNORECASE),
    re.compile(r"\bmkdir\b", re.IGNORECASE),
    re.compile(r"\brm\s", re.IGNORECASE),
    re.compile(r"\bmv\s", re.IGNORECASE),
]

ENV_VAR_PATTERN = re.compile(r"(?:os\.environ|getenv|\$\{?)([A-Z_][A-Z0-9_]{2,})")

NETWORK_PATTERNS = [
    re.compile(r"\bWebFetch\(", re.IGNORECASE),
    re.compile(r"\bWebSearch\(", re.IGNORECASE),
    re.compile(r"\brequests\.(?:get|post|put|delete)", re.IGNORECASE),
    re.compile(r"\burllib\.", re.IGNORECASE),
    re.compile(r"\bhttpx\.", re.IGNORECASE),
    re.compile(r"\burllib3\.", re.IGNORECASE),
    re.compile(r"\bcurl\s", re.IGNORECASE),
    re.compile(r"\bwget\s", re.IGNORECASE),
    re.compile(r"\bgit\s+(?:clone|fetch|pull|push)", re.IGNORECASE),
]

PATH_HINT_PATTERN = re.compile(
    r"[\"']((?:/|~|\./|\.\./|[A-Z]:[/\\])[^\"'\s]{2,})[\"']"
)


def collect_files(draft_dir: Path) -> list[Path]:
    """Return all skill files to scan: SKILL.md, scripts/*, references/*."""
    files: list[Path] = []
    skill_md = draft_dir / "SKILL.md"
    if skill_md.exists():
        files.append(skill_md)
    for sub in ("scripts", "references", "templates"):
        sub_dir = draft_dir / sub
        if sub_dir.exists():
            files.extend(sorted(sub_dir.rglob("*")))
    return [f for f in files if f.is_file()]


def scan_file(path: Path) -> dict[str, list[str]]:
    """Scan one file and return categorized touch points."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"error": [f"read failed: {exc}"]}

    fs_writes = set()
    env_vars = set()
    network = set()
    paths = set()

    for line in text.splitlines():
        for pat in FS_WRITE_PATTERNS:
            if pat.search(line):
                fs_writes.add(line.strip()[:120])
                break
        for pat in NETWORK_PATTERNS:
            if pat.search(line):
                network.add(line.strip()[:120])
                break
        for m in ENV_VAR_PATTERN.finditer(line):
            env_vars.add(m.group(1))
        for m in PATH_HINT_PATTERN.finditer(line):
            p = m.group(1)
            # Skip test-fixture paths and common benign paths
            if "test" in p.lower() or "fixture" in p.lower():
                continue
            if len(p) > 200:
                continue
            paths.add(p)

    return {
        "fs_writes": sorted(fs_writes),
        "env_vars": sorted(env_vars),
        "network": sorted(network),
        "paths": sorted(paths),
    }


def build_manifest(draft_dir: Path) -> dict[str, Any]:
    files = collect_files(draft_dir)
    per_file: list[dict[str, Any]] = []
    agg_fs: set[str] = set()
    agg_env: set[str] = set()
    agg_net: set[str] = set()
    agg_paths: set[str] = set()

    for f in files:
        rel = str(f.relative_to(draft_dir)).replace("\\", "/")
        scan = scan_file(f)
        if scan.get("error"):
            per_file.append({"file": rel, "error": scan["error"]})
            continue
        per_file.append({
            "file": rel,
            "fs_write_count": len(scan["fs_writes"]),
            "env_var_count": len(scan["env_vars"]),
            "network_count": len(scan["network"]),
            "path_hint_count": len(scan["paths"]),
        })
        agg_fs.update(scan["fs_writes"])
        agg_env.update(scan["env_vars"])
        agg_net.update(scan["network"])
        agg_paths.update(scan["paths"])

    side_effect_count = len(agg_fs) + len(agg_net)
    isolation_required = side_effect_count > 0 or bool(agg_env)

    return {
        "draft_dir": str(draft_dir),
        "files_scanned": len(files),
        "isolation_required": isolation_required,
        "cleanup_before_each_trial": {
            "filesystem_writes": sorted(agg_fs),
            "network_calls": sorted(agg_net),
            "env_vars_read": sorted(agg_env),
            "path_hints": sorted(agg_paths),
        },
        "side_effect_count": side_effect_count,
        "per_file": per_file,
        "harness_note": (
            "The Gate 11 eval harness must reset the above filesystem paths and "
            "env vars between each scenario trial. Network calls should be "
            "mocked or replaced with fixtures for deterministic results."
        ),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--draft-dir", required=True, help="path to .kiho/state/drafts/sk-<slug>/")
    p.add_argument("--out", default="-", help="output path or '-' for stdout")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    draft_dir = Path(args.draft_dir).resolve()
    if not draft_dir.exists():
        sys.stderr.write(f"draft dir not found: {draft_dir}\n")
        return 2
    manifest = build_manifest(draft_dir)
    text = json.dumps(manifest, indent=2)
    if args.out == "-":
        sys.stdout.write(text + "\n")
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        sys.stderr.write(f"wrote {args.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
