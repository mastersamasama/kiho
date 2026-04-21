#!/usr/bin/env python3
"""
kiho_fm_doctor.py — idempotent frontmatter migration tool (v5.20).

Scans existing markdown files, reports frontmatter drift against the
canonical schema in `kiho_frontmatter.py`, and (in --fix mode) fills
missing canonical fields with safe defaults. Never deletes unknown keys
(forward-compat for legacy schemas). Never invents an `id` — if a file
has no id, the doctor flags it and the caller must decide.

The doctor is the safety net for the migration: Week-0 runs it in
--dry-run, observes drift, fixes ad-hoc. After the bulk migration it
runs in CI as a lint gate.

Usage:
    kiho_fm_doctor.py --dry-run <path-or-dir>...         # report only
    kiho_fm_doctor.py --fix <path-or-dir>... [--kind X]  # backfill defaults
    kiho_fm_doctor.py --report <path-or-dir>...          # json summary

Exit codes:
    0 — clean (dry-run: no drift; fix: no files needed changes)
    1 — drift detected (dry-run) OR fixes applied (fix)
    2 — usage error
    3 — internal error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kiho_frontmatter as _fm  # type: ignore


def _iter_md(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for target in paths:
        p = Path(target)
        if p.is_dir():
            out.extend(p.rglob("*.md"))
        elif p.is_file():
            out.append(p)
    return out


def _infer_kind(path: Path, meta: dict) -> str | None:
    if meta.get("kind"):
        return str(meta["kind"])
    parts = path.parts
    # Heuristics for legacy files
    if "SKILL.md" in parts[-1]:
        return "skill-md"
    if "agents" in parts and path.suffix == ".md":
        return "soul"
    if "kb" in parts and "wiki" in parts:
        return "kb-article"
    if "memory" in parts:
        return "memory"
    if "committees" in parts and "transcript" in path.stem:
        return "committee-transcript"
    if "incidents" in parts:
        return "incident"
    if "postmortems" in parts:
        return "postmortem"
    if "retros" in parts:
        return "retrospective"
    if "decisions" in parts or "decision" in path.stem:
        return "decision"
    return None


def _diagnose(path: Path) -> tuple[dict, dict, list[str], str | None]:
    """Return (meta, proposed_meta, errors, inferred_kind)."""
    meta, _ = _fm.read(path)
    if not meta:
        return {}, {}, ["no frontmatter"], None
    kind = _infer_kind(path, meta)
    proposed = dict(meta)
    proposed.setdefault("id", path.stem)
    if kind:
        proposed.setdefault("kind", kind)
    proposed = _fm.merge_defaults(proposed.get("kind", "generic"), proposed)
    errors = _fm.validate(proposed, kind=proposed.get("kind"))
    return meta, proposed, errors, kind


def _cmd(args: argparse.Namespace) -> int:
    any_drift = False
    any_fix = False
    files = _iter_md(args.paths)
    summary = {"files": len(files), "drift": 0, "fixed": 0, "clean": 0, "errors": []}
    for f in files:
        try:
            meta, proposed, errors, _kind = _diagnose(f)
        except Exception as exc:  # pragma: no cover
            summary["errors"].append({"path": str(f), "error": str(exc)})
            continue
        needs_change = (proposed != meta) or errors
        if not needs_change:
            summary["clean"] += 1
            continue
        any_drift = True
        summary["drift"] += 1
        if args.report:
            continue
        if args.dry_run:
            print(f"DRIFT {f}")
            for e in errors:
                print(f"  error: {e}")
            for k, v in proposed.items():
                if k not in meta or meta[k] != v:
                    print(f"  would set {k}={v!r}")
            continue
        if args.fix:
            # Preserve body verbatim; only rewrite frontmatter.
            _, body = _fm.read(f)
            _fm.write(f, proposed, body)
            any_fix = True
            summary["fixed"] += 1
            print(f"FIXED {f}")
    if args.report:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1 if summary["drift"] else 0
    if args.dry_run and any_drift:
        return 1
    if args.fix and any_fix:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kiho_fm_doctor", description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="report drift without writing")
    mode.add_argument("--fix", action="store_true",
                      help="backfill canonical fields with safe defaults")
    mode.add_argument("--report", action="store_true",
                      help="emit JSON summary (for CI)")
    ap.add_argument("paths", nargs="+", help="files or directories")
    args = ap.parse_args(argv)
    try:
        return _cmd(args)
    except Exception as exc:  # pragma: no cover
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
