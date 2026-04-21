#!/usr/bin/env python3
"""
cycle_index_gen.py — regenerate <project>/.kiho/state/cycles/INDEX.md
from per-cycle index.toml files.

Invoked from CEO DONE step 11. Read-only over per-cycle indexes; writes the
master INDEX.md atomically (temp + fsync + rename).

Usage:
    cycle_index_gen.py --project-root <path> [--max-recent-closed 20]

Exit codes:
    0 — INDEX.md regenerated (or empty if no cycles)
    2 — usage error
    3 — internal error
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import tempfile
from pathlib import Path

try:
    import tomllib as _toml
except ImportError:
    try:
        import tomli as _toml  # type: ignore
    except ImportError:
        print("FATAL: requires Python 3.11+ tomllib or tomli on 3.10", file=sys.stderr)
        sys.exit(3)

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PLUGIN_ROOT / "references" / "cycle-templates"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _list_templates() -> list[str]:
    if not TEMPLATES_DIR.is_dir():
        return []
    out = []
    for p in sorted(TEMPLATES_DIR.glob("*.toml")):
        try:
            with p.open("rb") as fp:
                data = _toml.load(fp)
            tid = data.get("meta", {}).get("template_id", p.stem)
            ver = data.get("meta", {}).get("version", "?")
            out.append(f"{tid} v{ver}")
        except Exception:
            out.append(f"{p.stem} (unreadable)")
    return out


def _load_indexes(cycles_dir: Path) -> list[dict]:
    if not cycles_dir.is_dir():
        return []
    out = []
    for cdir in sorted(cycles_dir.iterdir()):
        if not cdir.is_dir():
            continue
        ip = cdir / "index.toml"
        if not ip.is_file():
            continue
        try:
            with ip.open("rb") as fp:
                out.append(_toml.load(fp))
        except Exception as exc:
            out.append({"meta": {"cycle_id": cdir.name, "status": "unreadable",
                                 "template_id": "?", "phase": "?",
                                 "_load_error": repr(exc)},
                        "budget": {"iters_used": 0, "iters_max": 0}})
    return out


def render_index(indexes: list[dict], templates: list[str], max_recent_closed: int) -> str:
    open_cycles = [i for i in indexes if i.get("meta", {}).get("status") in ("in_progress", "blocked", "paused")]
    closed_cycles = [i for i in indexes if i.get("meta", {}).get("status", "").startswith("closed-") or i.get("meta", {}).get("status") == "cancelled"]

    closed_cycles.sort(key=lambda i: i.get("meta", {}).get("opened_at", ""), reverse=True)
    closed_cycles = closed_cycles[:max_recent_closed]

    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# kiho cycles — live state",
        "",
        f"_Generated: {now} by bin/cycle_index_gen.py from cycles/*/index.toml_",
        "",
    ]

    lines.append(f"## Open cycles ({len(open_cycles)})")
    lines.append("")
    if open_cycles:
        lines.append("| cycle_id | template | phase | iters | status | next-action |")
        lines.append("|---|---|---|---|---|---|")
        for idx in open_cycles:
            meta = idx.get("meta", {})
            budget = idx.get("budget", {})
            blockers = idx.get("blockers", {})
            iters = f"{budget.get('iters_used', 0)}/{budget.get('iters_max', '?')}"
            status = meta.get("status", "?")
            phase = meta.get("phase", "?")
            template = f"{meta.get('template_id', '?')} v{meta.get('template_version', '?')}"
            next_action = "advance" if status == "in_progress" else (
                "unblock" if status == "blocked" else "resume" if status == "paused" else "?"
            )
            blocker_note = f" — {blockers.get('last_reason')}" if status == "blocked" and blockers.get("last_reason") else ""
            lines.append(f"| {meta.get('cycle_id', '?')} | {template} | {phase} | {iters} | {status}{blocker_note} | {next_action} |")
    else:
        lines.append("_No open cycles._")
    lines.append("")

    lines.append(f"## Recently closed (last {max_recent_closed})")
    lines.append("")
    if closed_cycles:
        for idx in closed_cycles:
            meta = idx.get("meta", {})
            cid = meta.get("cycle_id", "?")
            template = meta.get("template_id", "?")
            status = meta.get("status", "?")
            opened = meta.get("opened_at", "?")
            lines.append(f"- `{cid}` ({template}): {status} (opened {opened})")
    else:
        lines.append("_No recently closed cycles._")
    lines.append("")

    lines.append(f"## Templates available ({len(templates)})")
    lines.append("")
    for t in templates:
        lines.append(f"- {t}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Regenerate cycles/INDEX.md from per-cycle index.toml")
    p.add_argument("--project-root", default=".")
    p.add_argument("--max-recent-closed", type=int, default=20)
    p.add_argument("--out", default=None, help="override output path")
    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    try:
        project_root = Path(args.project_root).resolve()
        cycles_dir = project_root / ".kiho" / "state" / "cycles"
        indexes = _load_indexes(cycles_dir)
        templates = _list_templates()
        out = Path(args.out) if args.out else cycles_dir / "INDEX.md"
        md = render_index(indexes, templates, args.max_recent_closed)
        _atomic_write(out, md)
        print(json.dumps({
            "status": "ok",
            "out": str(out),
            "open_cycles": sum(1 for i in indexes if i.get("meta", {}).get("status") in ("in_progress", "blocked", "paused")),
            "closed_cycles": sum(1 for i in indexes if i.get("meta", {}).get("status", "").startswith("closed-") or i.get("meta", {}).get("status") == "cancelled"),
            "templates_available": len(templates),
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
