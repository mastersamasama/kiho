#!/usr/bin/env python3
"""
storage_fit_scan.py — storage-fit audit for kiho skills (v5.19 Phase 3).

Walks `skills/**/SKILL.md` and verifies each skill's declared
`metadata.kiho.data_classes` against the row catalog in
`references/data-storage-matrix.md`. Emits per-skill verdicts without
ever mutating a SKILL.md.

Verdict taxonomy:

    ALIGNED      — all declared classes exist in the matrix with an
                   active status (FIT, MIGRATING, NEW, NEW-PATTERN).
    UNDECLARED   — the skill has no metadata.kiho.data_classes field.
                   Legacy skills are grandfathered for 180 days post-v5.19
                   ship. Warn phase: 60 days. Error phase thereafter.
    DRIFT        — the skill declares a class slug that does not exist
                   in the matrix. Always reported as policy violation.
    MATRIX_GAP   — the skill declares a class whose matrix status is
                   GAP or DEFERRED. The author MUST wait for the matrix
                   row to activate or choose a different class.

Usage:
    storage_fit_scan.py
        [--skills-root skills/]
        [--matrix-path references/data-storage-matrix.md]
        [--plugin-root .]
        [--output-md _meta-runtime/batch-report-storage-audit-<id>.md]
        [--json]
        [--grace-days 60]
        [--elapsed-days N]       # manual override; omit to auto-compute
        [--config-path <path>]   # override config.toml/yaml ship-date lookup

    When `--elapsed-days` is omitted, the script reads `v5_19_ship_date:`
    from `<plugin-root>/skills/core/harness/kiho/config.toml` (or legacy
    `.yaml` if TOML absent) and computes
    elapsed_days = (today_utc - ship_date).days. On missing or malformed
    config, falls back to elapsed_days=0 (grace never triggers — safest
    default). The summary JSON includes `elapsed_source` so callers can
    tell which path was taken.

Exit codes (v5.15.2 convention):
    0 — all skills ALIGNED or UNDECLARED (within grace); report emitted
    1 — at least one DRIFT or MATRIX_GAP verdict, or UNDECLARED beyond
        grace window (policy violation)
    2 — usage error (bad path, unreadable inputs)
    3 — internal error (unexpected exception)

Grounding:
    * references/data-storage-matrix.md (row catalog + statuses)
    * references/storage-architecture.md (three-tier invariants)
    * references/skill-authoring-standards.md § v5.19 data_classes rule
    * skills/_meta/evolution-scan/references/storage-audit-lens.md (verdict
      taxonomy + report skeleton; human-readable companion to this script)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path


# --- patterns ---------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_DATA_CLASSES_INLINE_RE = re.compile(
    r"^\s*data_classes\s*:\s*\[(.*?)\]\s*$", re.MULTILINE
)
_DATA_CLASSES_BLOCK_RE = re.compile(
    r"^\s*data_classes\s*:\s*\n((?:[ \t]*-[ \t]+.+\n)+)", re.MULTILINE
)
_LIST_ITEM_RE = re.compile(r"^[ \t]*-[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_MATRIX_ROW_RE = re.compile(
    r"^###\s+([a-z][a-z0-9-]*)\s+—\s+([A-Z][A-Z-]+)(?=\s|$|\()",
    re.MULTILINE,
)
_SKILL_NAME_RE = re.compile(r"^\s*name\s*:\s*(.+?)\s*$", re.MULTILINE)
_SHIP_DATE_RE = re.compile(
    # Accepts either TOML `key = "YYYY-MM-DD"` or YAML `key: YYYY-MM-DD`.
    # The migration to TOML (v5.19.3) flipped config.yaml → config.toml;
    # the legacy YAML form is kept so pre-migration branches still parse.
    r"^v5_19_ship_date\s*[:=]\s*\"?(\d{4}-\d{2}-\d{2})\"?\s*$",
    re.MULTILINE,
)

ACTIVE_STATUSES = frozenset({"FIT", "MIGRATING", "NEW", "NEW-PATTERN"})
GRACE_STATUSES = frozenset({"GAP", "DEFERRED"})


# --- helpers ----------------------------------------------------------------

def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def load_ship_date(config_path: Path) -> _dt.date | None:
    """Read `v5_19_ship_date` from kiho config (TOML primary, YAML fallback).

    Looks for a line matching either TOML (`key = "YYYY-MM-DD"`) or
    legacy YAML (`key: YYYY-MM-DD`). Returns the parsed date on success,
    None on any failure (missing file, missing key, unparseable date).
    Intentionally avoids tomllib / PyYAML — the regex is the entire
    reader surface so the script stays stdlib-only on 3.10+.

    If `config_path` does not exist, also tries the sibling path with
    the opposite `.toml` / `.yaml` extension. This two-probe fallback
    keeps the grace-window computation working across both sides of
    the v5.19.3 YAML→TOML migration.
    """
    candidates: list[Path] = [config_path]
    if config_path.suffix == ".toml":
        candidates.append(config_path.with_suffix(".yaml"))
    elif config_path.suffix == ".yaml":
        candidates.append(config_path.with_suffix(".toml"))

    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        m = _SHIP_DATE_RE.search(text)
        if not m:
            continue
        try:
            return _dt.date.fromisoformat(m.group(1))
        except ValueError:
            return None
    return None


def parse_matrix_rows(matrix_path: Path) -> dict[str, str]:
    """Return {slug: status} read from data-storage-matrix.md `### slug — STATUS` headings."""
    if not matrix_path.exists():
        raise FileNotFoundError(f"matrix not found: {matrix_path}")
    text = matrix_path.read_text(encoding="utf-8")
    rows: dict[str, str] = {}
    for m in _MATRIX_ROW_RE.finditer(text):
        slug = m.group(1).strip()
        status = m.group(2).strip().upper()
        rows[slug] = status
    return rows


def extract_skill_name(text: str) -> str | None:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    block = m.group(1)
    nm = _SKILL_NAME_RE.search(block)
    return nm.group(1).strip() if nm else None


def extract_data_classes(text: str) -> list[str] | None:
    """Return declared data_classes list, or None if not declared at all.

    Empty list means the field exists but contains no entries.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    block = m.group(1)

    inline = _DATA_CLASSES_INLINE_RE.search(block)
    if inline:
        raw = inline.group(1)
        return [_strip_quotes(s) for s in raw.split(",") if s.strip()]

    blk = _DATA_CLASSES_BLOCK_RE.search(block + "\n")
    if blk:
        return [
            _strip_quotes(m2.group(1))
            for m2 in _LIST_ITEM_RE.finditer(blk.group(1))
        ]

    # Look for a bare `data_classes:` line with no value or empty value
    if re.search(r"^\s*data_classes\s*:\s*(\[\s*\])?\s*$", block, re.MULTILINE):
        return []

    return None


def classify(
    declared: list[str] | None,
    matrix: dict[str, str],
) -> tuple[str, dict]:
    """Return (verdict, detail) given declared classes and matrix."""
    if declared is None:
        return "UNDECLARED", {}

    if not declared:
        # v5.21: explicit empty list = author asserts "no tracked data class".
        # Legitimate for pure-infrastructure dispatchers (e.g., storage-broker
        # which routes everything but owns no class) and vendor-sandbox skills
        # (e.g., engineering-kiro). The author has reviewed and concluded the
        # skill produces no rows in any matrix-tracked class — that's a
        # different state from "field missing".
        return "ALIGNED", {
            "declared_empty": True,
            "detail": "data_classes: [] — author asserts no tracked class",
        }

    missing = [c for c in declared if c not in matrix]
    gap_or_deferred = [
        c for c in declared if c in matrix and matrix[c] in GRACE_STATUSES
    ]

    if missing:
        return "DRIFT", {
            "unknown_slugs": sorted(missing),
            "known_slugs": sorted(c for c in declared if c in matrix),
        }
    if gap_or_deferred:
        return "MATRIX_GAP", {
            "gap_or_deferred_slugs": sorted(gap_or_deferred),
            "their_statuses": {c: matrix[c] for c in gap_or_deferred},
            "active_slugs": sorted(
                c for c in declared if matrix.get(c) in ACTIVE_STATUSES
            ),
        }
    return "ALIGNED", {
        "active_slugs": sorted(declared),
    }


def scan_skills(skills_root: Path, matrix: dict[str, str]) -> list[dict]:
    """Walk skills_root/**/SKILL.md; return list of per-skill result dicts."""
    results: list[dict] = []
    for path in sorted(skills_root.rglob("SKILL.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            results.append({
                "path": path.relative_to(skills_root).as_posix(),
                "name": None,
                "verdict": "ERROR",
                "detail": {"read_error": repr(exc)},
            })
            continue
        name = extract_skill_name(text) or path.parent.name
        declared = extract_data_classes(text)
        verdict, detail = classify(declared, matrix)
        results.append({
            "path": path.relative_to(skills_root).as_posix(),
            "name": name,
            "declared": declared or [],
            "declared_present": declared is not None,
            "verdict": verdict,
            "detail": detail,
        })
    return results


# --- report rendering -------------------------------------------------------

def tally(results: list[dict]) -> dict[str, int]:
    tally = {
        "ALIGNED": 0, "UNDECLARED": 0, "DRIFT": 0,
        "MATRIX_GAP": 0, "ERROR": 0,
    }
    for r in results:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    return tally


def render_batch_report(
    results: list[dict],
    matrix_rows: int,
    skills_root: Path,
    matrix_path: Path,
    grace_days: int,
    beyond_grace: bool,
) -> str:
    t = tally(results)
    total = len(results)
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: list[str] = [
        "# Storage-fit audit batch report",
        "",
        f"- Generated: {ts}",
        f"- Skills scanned: {total}",
        f"- Matrix path: `{matrix_path.as_posix()}` "
        f"(rows indexed: {matrix_rows})",
        f"- Skills root: `{skills_root.as_posix()}`",
        f"- Grace window for UNDECLARED: {grace_days} days "
        f"({'elapsed' if beyond_grace else 'within'})",
        "",
        "## Summary",
        "",
        f"- ALIGNED:    {t['ALIGNED']}",
        f"- UNDECLARED: {t['UNDECLARED']}  "
        f"({'policy violation' if beyond_grace else 'grandfathered'})",
        f"- DRIFT:      {t['DRIFT']}  (policy violation; unknown slug)",
        f"- MATRIX_GAP: {t['MATRIX_GAP']}  "
        f"(policy violation; declared row is GAP or DEFERRED)",
        f"- ERROR:      {t['ERROR']}  (read failure)",
        "",
        "## Per-skill verdicts",
        "",
    ]

    for r in sorted(results, key=lambda x: (x["verdict"], x["path"])):
        lines.append(f"### {r['name']} — {r['verdict']}")
        lines.append(f"- Path: `{r['path']}`")
        if r.get("declared_present"):
            decl = r.get("declared") or []
            lines.append(f"- Declared: {decl if decl else '(empty)'}")
        else:
            lines.append("- Declared: (no data_classes field)")
        if r["detail"]:
            for k, v in r["detail"].items():
                lines.append(f"- {k}: {v}")
        lines.append("")

    lines.extend([
        "## CEO bulk decision",
        "",
        "Reply format: `approve: [...], defer: [...], reject: [...], discuss: [...]`",
        "",
        "## Notes",
        "",
        "- Zero SKILL.md files were modified by this audit.",
        "- Follow-up migrations go through `skill-improve` per skill, one iteration each (Ralph discipline).",
        "- Matrix additions for DRIFT slugs require a storage-fit committee vote per `references/committee-rules.md`.",
    ])
    return "\n".join(lines) + "\n"


# --- CLI --------------------------------------------------------------------

def _plugin_root_default() -> Path:
    # Script lives at skills/_meta/evolution-scan/scripts/storage_fit_scan.py
    return Path(__file__).resolve().parents[4]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Audit skills against data-storage-matrix.md (read-only).",
        epilog=(
            "Exit codes: 0 aligned-or-within-grace, 1 policy violation, "
            "2 usage, 3 internal. See storage-audit-lens.md for verdict taxonomy."
        ),
    )
    plugin_root_default = _plugin_root_default()
    p.add_argument(
        "--plugin-root",
        default=str(plugin_root_default),
        help=f"kiho plugin root (default: {plugin_root_default})",
    )
    p.add_argument(
        "--skills-root",
        default=None,
        help="Skills root; default: <plugin-root>/skills",
    )
    p.add_argument(
        "--matrix-path",
        default=None,
        help=(
            "Path to data-storage-matrix.md; "
            "default: <plugin-root>/references/data-storage-matrix.md"
        ),
    )
    p.add_argument(
        "--output-md",
        default=None,
        help=(
            "Write batch report markdown to this path; "
            "default: <plugin-root>/_meta-runtime/batch-report-storage-audit-<ts>.md"
        ),
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Also emit full JSON results to stdout",
    )
    p.add_argument(
        "--grace-days",
        type=int,
        default=60,
        help="Grace window for UNDECLARED (default: 60 days; warn<=grace, error thereafter)",
    )
    p.add_argument(
        "--elapsed-days",
        type=int,
        default=None,
        help=(
            "Days elapsed since v5.19 ship (for grace calculation). "
            "Default: auto-compute from <plugin-root>/skills/core/harness/kiho/config.toml "
            "`v5_19_ship_date:` key. Falls back to 0 if config unreadable."
        ),
    )
    p.add_argument(
        "--config-path",
        default=None,
        help=(
            "Path to kiho config (TOML preferred, YAML fallback) for "
            "ship-date lookup; default: "
            "<plugin-root>/skills/core/harness/kiho/config.toml"
        ),
    )
    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    try:
        plugin_root = Path(args.plugin_root).resolve()
        skills_root = (
            Path(args.skills_root).resolve()
            if args.skills_root
            else plugin_root / "skills"
        )
        matrix_path = (
            Path(args.matrix_path).resolve()
            if args.matrix_path
            else plugin_root / "references" / "data-storage-matrix.md"
        )
        if not skills_root.is_dir():
            print(
                json.dumps({
                    "status": "error",
                    "error": f"skills-root {skills_root} is not a directory",
                }),
                file=sys.stderr,
            )
            return 2
        if not matrix_path.is_file():
            print(
                json.dumps({
                    "status": "error",
                    "error": f"matrix-path {matrix_path} is not a file",
                }),
                file=sys.stderr,
            )
            return 2

        matrix = parse_matrix_rows(matrix_path)
        results = scan_skills(skills_root, matrix)

        # Auto-compute elapsed_days from kiho config when flag omitted.
        # Default path is config.toml (post v5.19.3 migration); the
        # load_ship_date helper also probes config.yaml as a fallback.
        if args.elapsed_days is None:
            config_path = (
                Path(args.config_path).resolve()
                if args.config_path
                else plugin_root / "skills" / "core" / "harness" / "kiho" / "config.toml"
            )
            ship_date = load_ship_date(config_path)
            if ship_date is not None:
                today_utc = _dt.datetime.now(_dt.timezone.utc).date()
                elapsed_days = max(0, (today_utc - ship_date).days)
                elapsed_source = f"auto (config v5_19_ship_date={ship_date.isoformat()})"
            else:
                elapsed_days = 0
                elapsed_source = "fallback (config unreadable or missing v5_19_ship_date)"
        else:
            elapsed_days = args.elapsed_days
            elapsed_source = "override (--elapsed-days flag)"

        beyond_grace = elapsed_days > args.grace_days
        t = tally(results)
        violation = (
            t.get("DRIFT", 0) > 0
            or t.get("MATRIX_GAP", 0) > 0
            or (beyond_grace and t.get("UNDECLARED", 0) > 0)
        )

        # Resolve output path
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_md = (
            Path(args.output_md).resolve()
            if args.output_md
            else plugin_root
            / "_meta-runtime"
            / f"batch-report-storage-audit-{ts}.md"
        )
        output_md.parent.mkdir(parents=True, exist_ok=True)

        md = render_batch_report(
            results,
            matrix_rows=len(matrix),
            skills_root=skills_root,
            matrix_path=matrix_path,
            grace_days=args.grace_days,
            beyond_grace=beyond_grace,
        )
        output_md.write_text(md, encoding="utf-8")

        # Append one JSONL row per audit run to _meta-runtime/storage-audit.jsonl
        # (data-storage-matrix row `evolution-scan-audits`). The JSONL is the
        # source of truth; the markdown above is the rendered view.
        audit_jsonl = plugin_root / "_meta-runtime" / "storage-audit.jsonl"
        try:
            audit_jsonl.parent.mkdir(parents=True, exist_ok=True)
            audit_row = {
                "ts": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "audit_run_id": ts,
                "audit_lens": "storage-fit",
                "total_skills": len(results),
                "tally": t,
                "matrix_rows": len(matrix),
                "grace_days": args.grace_days,
                "beyond_grace": beyond_grace,
                "elapsed_days": elapsed_days,
                "elapsed_source": elapsed_source,
                "per_skill": [
                    {
                        "skill_id": r.get("name"),
                        "verdict": r.get("verdict"),
                        "declared": r.get("declared", []),
                        "detail": r.get("detail", {}),
                    }
                    for r in results
                ],
            }
            with audit_jsonl.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(audit_row, ensure_ascii=False) + "\n")
        except OSError:
            pass

        summary = {
            "status": "drift" if violation else "ok",
            "total": len(results),
            "tally": t,
            "matrix_rows": len(matrix),
            "elapsed_days": elapsed_days,
            "elapsed_source": elapsed_source,
            "grace_days": args.grace_days,
            "beyond_grace": beyond_grace,
            "report_md": str(output_md),
            "audit_jsonl": str(audit_jsonl),
        }
        if args.json:
            summary["results"] = results
        print(json.dumps(summary, indent=2))

        return 1 if violation else 0

    except FileNotFoundError as exc:  # pragma: no cover — usage error
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover — defensive
        print(json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
