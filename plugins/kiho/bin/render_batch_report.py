#!/usr/bin/env python3
"""
render_batch_report.py — re-render a markdown batch-report from a JSONL stream.

Background (v5.20 Wave 1.1): factory verdicts and storage audits now write to
authoritative JSONL streams (data-storage-matrix rows `skill-factory-verdicts`
and `evolution-scan-audits`). The legacy `_meta-runtime/batch-report-<id>.md`
is now a *rendered view* derived from those streams.

This script reproduces the markdown surface for human review without making the
JSONL a leaky abstraction. Either source can be re-rendered on demand.

Usage:
    render_batch_report.py --kind factory --batch-id <id>
        [--jsonl _meta-runtime/factory-verdicts.jsonl]
        [--out -]

    render_batch_report.py --kind audit --audit-run-id <ts>
        [--jsonl _meta-runtime/storage-audit.jsonl]
        [--out -]

Exit codes (v5.15.2 convention):
    0 — rendered successfully
    1 — batch-id / audit-run-id not found in JSONL
    2 — usage error
    3 — internal error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACTORY_JSONL = PLUGIN_ROOT / "_meta-runtime" / "factory-verdicts.jsonl"
DEFAULT_AUDIT_JSONL = PLUGIN_ROOT / "_meta-runtime" / "storage-audit.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(path)
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def render_factory_report(rows: list[dict], batch_id: str) -> str:
    matched = [r for r in rows if r.get("batch_id") == batch_id]
    if not matched:
        return ""
    counts = {"green": 0, "yellow": 0, "red": 0}
    for r in matched:
        counts[r.get("verdict", "red")] = counts.get(r.get("verdict", "red"), 0) + 1
    ts = matched[0].get("ts", "")
    lines = [
        f"# Factory batch report — {ts}",
        "",
        f"**Batch ID**: `{batch_id}` (rendered from factory-verdicts.jsonl)",
        "",
        "## Summary",
        "",
        f"- Batch size: {len(matched)} skill(s)",
        f"- Verdicts: {counts['green']} green / {counts['yellow']} yellow / {counts['red']} red",
        "",
        "## Per-skill verdicts",
        "",
    ]
    for r in matched:
        lines.append(f"### {r.get('skill_id', '?')} — {r.get('verdict', '?')}")
        lines.append("")
        steps = r.get("step_results", {}) or {}
        for step_num in sorted(steps.keys(), key=lambda s: int(s) if s.isdigit() else 99):
            lines.append(f"- Step {step_num}: **{steps[step_num]}**")
        if r.get("fail_reason"):
            lines.append(f"- Fail reason: {r['fail_reason']}")
        if r.get("ceo_decision"):
            lines.append(f"- CEO decision: {r['ceo_decision']}")
        lines.append("")
    lines.extend([
        "## CEO bulk decision",
        "",
        "Reply with one of:",
        "",
        "- `ship green, defer yellow, discuss red`",
        "- `ship green+yellow, discuss red`",
        "- `discuss all`",
        "",
    ])
    return "\n".join(lines)


def render_audit_report(rows: list[dict], audit_run_id: str) -> str:
    matched = [r for r in rows if r.get("audit_run_id") == audit_run_id]
    if not matched:
        return ""
    row = matched[0]
    t = row.get("tally", {})
    lines = [
        "# Storage-fit audit batch report (rendered)",
        "",
        f"- Audit run: `{audit_run_id}`",
        f"- Generated: {row.get('ts', '')}",
        f"- Audit lens: {row.get('audit_lens', 'storage-fit')}",
        f"- Skills scanned: {row.get('total_skills', 0)}",
        f"- Matrix rows indexed: {row.get('matrix_rows', 0)}",
        f"- Grace days: {row.get('grace_days', 0)} ({'elapsed' if row.get('beyond_grace') else 'within'})",
        f"- Elapsed source: {row.get('elapsed_source', '?')}",
        "",
        "## Summary",
        "",
        f"- ALIGNED:    {t.get('ALIGNED', 0)}",
        f"- UNDECLARED: {t.get('UNDECLARED', 0)}",
        f"- DRIFT:      {t.get('DRIFT', 0)}",
        f"- MATRIX_GAP: {t.get('MATRIX_GAP', 0)}",
        f"- ERROR:      {t.get('ERROR', 0)}",
        "",
        "## Per-skill verdicts",
        "",
    ]
    per_skill = sorted(
        row.get("per_skill", []),
        key=lambda x: (x.get("verdict", ""), x.get("skill_id", "")),
    )
    for s in per_skill:
        lines.append(f"### {s.get('skill_id', '?')} — {s.get('verdict', '?')}")
        decl = s.get("declared", [])
        lines.append(f"- Declared: {decl if decl else '(empty)'}")
        for k, v in (s.get("detail") or {}).items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Render batch-report markdown from JSONL streams.")
    p.add_argument("--kind", required=True, choices=["factory", "audit"],
                   help="Which JSONL stream to render: factory-verdicts or storage-audit.")
    p.add_argument("--batch-id", help="Required for --kind factory.")
    p.add_argument("--audit-run-id", help="Required for --kind audit.")
    p.add_argument("--jsonl", help="Override the default JSONL path.")
    p.add_argument("--out", default="-", help="Output path; '-' for stdout (default).")

    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    try:
        if args.kind == "factory":
            if not args.batch_id:
                print("--batch-id required for --kind factory", file=sys.stderr)
                return 2
            jsonl = Path(args.jsonl) if args.jsonl else DEFAULT_FACTORY_JSONL
            rows = read_jsonl(jsonl)
            md = render_factory_report(rows, args.batch_id)
            if not md:
                print(f"batch_id {args.batch_id!r} not found in {jsonl}", file=sys.stderr)
                return 1
        else:
            if not args.audit_run_id:
                print("--audit-run-id required for --kind audit", file=sys.stderr)
                return 2
            jsonl = Path(args.jsonl) if args.jsonl else DEFAULT_AUDIT_JSONL
            rows = read_jsonl(jsonl)
            md = render_audit_report(rows, args.audit_run_id)
            if not md:
                print(f"audit_run_id {args.audit_run_id!r} not found in {jsonl}", file=sys.stderr)
                return 1

        if args.out == "-":
            sys.stdout.write(md)
        else:
            Path(args.out).write_text(md, encoding="utf-8")
        return 0
    except FileNotFoundError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
