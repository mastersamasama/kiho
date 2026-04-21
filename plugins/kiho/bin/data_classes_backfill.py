#!/usr/bin/env python3
"""
data_classes_backfill.py — v5.19 `data_classes:` frontmatter one-shot backfill.

Walks `skills/**/SKILL.md` and, for skills without a `metadata.kiho.data_classes:`
frontmatter field, proposes (or writes, with --apply) a list of matrix-row
slugs the skill primarily reads or writes.

The mapping below is **curated by hand** based on reading each SKILL.md. It is
not a heuristic inference — storage-audit-lens.md line 138 explicitly forbids
auto-inference without author review. Running this script with `--dry-run`
(the default) surfaces the proposed changes for the author to review before
invoking `--apply` writes them.

Doctrine-compliance: the review gate is the dry-run step. The author reads
the diff, confirms each skill's declared classes are correct, then invokes
`--apply` (or edits the mapping and re-runs).

Usage:
    data_classes_backfill.py propose [--plugin-root .]
    data_classes_backfill.py apply   [--plugin-root .] [--skill <slug>]

    propose  — dry-run: print the proposed frontmatter patches to stdout
               as a JSON report and an optional per-skill diff preview.
    apply    — write the data_classes field into each SKILL.md frontmatter.
               A skill-specific subset can be written via `--skill <name>`
               (match by directory basename) — other skills stay untouched.

Exit codes (v5.15.2 convention):
    0 — propose/apply completed; all targeted skills were written (apply mode)
        or proposed (propose mode). Skills already declaring data_classes
        are skipped without changing exit status.
    1 — at least one proposed slug is not in the matrix, OR the targeted
        skill isn't in the curated mapping (policy violation: no silent
        guess). Run the storage-fit audit or update `_MAPPING`.
    2 — usage error (bad flag, bad --skill).
    3 — internal error.

Scope (intentional limits):
    * Only edits the `metadata.kiho` block.
    * Does NOT touch any other frontmatter key.
    * Does NOT modify SKILL.md body content.
    * Does NOT add matrix rows. If the curated mapping cites a slug that
      does not exist in the matrix, the script exits 1 (not 0) so the
      caller notices the drift before shipping.

Grounding:
    * references/data-storage-matrix.md (authoritative slugs + statuses)
    * skills/_meta/evolution-scan/references/storage-audit-lens.md §138
      ("Do NOT auto-rewrite SKILL.md without the author's review")
    * skills/_meta/evolution-scan/scripts/storage_fit_scan.py (the audit
      reads back the field this script writes)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# --- curated mapping --------------------------------------------------------
#
# Key: skill directory relative to skills/ (e.g., "kb/kb-add").
# Value: list of matrix row slugs this skill primarily reads/writes.
# An explicitly empty list declares "this skill touches no tracked data class"
# (legitimate for sandbox / external-vendor skills; produces ALIGNED verdict
# because `data_classes: []` is treated as "field present, deliberately empty"
# by the audit lens — see storage_fit_scan.py extract_data_classes()).
#
# Curated 2026-04-19 by reading each SKILL.md's Inputs/Procedure sections.
# Refine via normal skill-improve touches over time.

_MAPPING: dict[str, list[str]] = {
    # --- KB skills (_meta/kb): primary kb-wiki-articles writers ---
    "kb/kb-add": ["kb-wiki-articles"],
    "kb/kb-update": ["kb-wiki-articles"],
    "kb/kb-delete": ["kb-wiki-articles"],
    "kb/kb-search": ["kb-wiki-articles"],
    "kb/kb-init": ["kb-wiki-articles", "templates"],
    "kb/kb-ingest-raw": ["kb-wiki-articles", "kb-drafts"],
    "kb/kb-lint": ["kb-wiki-articles", "skill-solutions"],
    "kb/kb-promote": ["kb-wiki-articles", "cross-project-lessons"],

    # --- Memory skills ---
    "memory/memory-write": ["observations"],
    "memory/memory-reflect": ["reflections", "observations"],
    "memory/memory-consolidate": ["observations", "reflections", "lessons"],
    "memory/memory-cross-agent-learn": ["cross-agent-learnings", "lessons"],
    "memory/memory-read": ["observations", "reflections", "lessons", "todos"],

    # --- _meta authoring skills (SKILL.md read/write) ---
    "_meta/skill-create": ["skill-definitions", "skill-drafts"],
    "_meta/skill-improve": ["skill-definitions"],
    "_meta/skill-deprecate": ["skill-definitions", "changelog"],
    "_meta/skill-derive": ["skill-definitions", "skill-drafts"],
    "_meta/skill-factory": ["skill-definitions", "skill-drafts"],
    "_meta/skill-architect": ["skill-skeletons"],
    "_meta/skill-find": ["skill-catalog-index", "skill-definitions"],
    "_meta/skill-spec": ["skill-definitions", "skill-skeletons"],
    "_meta/skill-parity": ["skill-definitions"],
    "_meta/skill-graph": ["skill-definitions"],
    "_meta/skill-structural-gate": ["skill-definitions", "gate-observations"],
    "_meta/skill-learn": ["skill-skeletons", "observations"],
    "_meta/evolution-scan": ["skill-definitions", "skill-invocations", "drift-trend"],
    "_meta/soul-apply-override": ["soul-overrides", "agent-souls"],

    # --- Harness skills ---
    "core/harness/kiho": ["kiho-config", "ceo-ledger", "continuity", "plan"],
    "core/harness/kiho-setup": ["kiho-config", "templates"],
    "core/harness/kiho-init": ["ceo-ledger", "plan"],
    "core/harness/kiho-spec": ["plan", "completion"],
    "core/harness/org-sync": ["org-registry", "capability-matrix", "agent-performance"],

    # --- HR skills ---
    "core/hr/design-agent": ["agent-souls", "agent-md"],
    "core/hr/recruit": ["recruit-role-specs", "agent-md", "agent-souls"],

    # --- Inspection skills ---
    "core/inspection/kiho-inspect": ["org-registry", "capability-matrix", "agent-performance"],
    "core/inspection/session-context": ["scratch-per-script"],
    "core/inspection/state-read": ["ceo-ledger", "plan", "completion"],

    # --- Knowledge skills ---
    "core/knowledge/research": ["research-cache", "kb-wiki-articles"],
    "core/knowledge/research-deep": ["research-cache", "kb-wiki-articles"],
    "core/knowledge/experience-pool": ["cross-project-lessons", "lessons"],

    # --- Planning skills ---
    "core/planning/committee": ["committee-transcript", "committee-records-jsonl"],
    "core/planning/interview-simulate": ["canonical-rubric"],
    "core/planning/kiho-plan": ["plan"],

    # --- Engineering skills (external vendor; explicitly empty) ---
    "engineering/engineering-kiro": [],
    "engineering/engineering-kiro/kiro": [],
}


# --- frontmatter parse + emit ----------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_META_KIHO_RE = re.compile(
    r"^(metadata:\s*\n(?:[ \t]+.+\n)*?[ \t]+kiho:\s*\n(?:[ \t]+[A-Za-z_].+\n)*)",
    re.MULTILINE,
)
_DATA_CLASSES_RE = re.compile(r"^[ \t]+data_classes\s*:", re.MULTILINE)


def load_matrix_slugs(matrix_path: Path) -> set[str]:
    text = matrix_path.read_text(encoding="utf-8")
    row_re = re.compile(r"^###\s+([a-z][a-z0-9-]*)\s+—", re.MULTILINE)
    return {m.group(1) for m in row_re.finditer(text)}


def has_data_classes(text: str) -> bool:
    fm = _FRONTMATTER_RE.match(text)
    if not fm:
        return False
    block = fm.group(1)
    return bool(_DATA_CLASSES_RE.search(block))


def insert_data_classes(text: str, slugs: list[str]) -> str:
    """Insert `data_classes:` into the metadata.kiho block.

    Strategy: locate the `  kiho:` block (the standard YAML frontmatter
    pattern kiho uses), append `    data_classes: [<slugs>]` as the last
    line of that block. If a kiho block does not exist, add one.
    """
    fm = _FRONTMATTER_RE.match(text)
    if not fm:
        raise ValueError("SKILL.md missing YAML frontmatter")
    fm_block = fm.group(1)

    # Emit as flow-list form for readability; quote each slug.
    list_literal = "[" + ", ".join(f'"{s}"' for s in slugs) + "]"

    kiho_match = _META_KIHO_RE.search(fm_block)
    if not kiho_match:
        # Frontmatter has no metadata.kiho block; add one.
        new_kiho = (
            "metadata:\n"
            "  kiho:\n"
            f"    data_classes: {list_literal}\n"
        )
        new_fm = fm_block.rstrip() + "\n" + new_kiho
    else:
        kiho_block = kiho_match.group(1)
        # Append the data_classes line before the block ends.
        # The kiho block ends at the next top-level frontmatter key or EOF.
        appended = kiho_block.rstrip() + f"\n    data_classes: {list_literal}\n"
        new_fm = fm_block.replace(kiho_block, appended, 1)

    rebuilt = "---\n" + new_fm + (
        "" if new_fm.endswith("\n") else "\n"
    ) + "---\n" + text[fm.end():]
    return rebuilt


# --- main pipeline ----------------------------------------------------------

def build_report(
    skills_root: Path,
    matrix_slugs: set[str],
) -> tuple[dict, bool]:
    """Return (report, any_violation_flag)."""
    report: dict = {
        "skills": [],
        "counts": {
            "already_declared": 0,
            "proposed": 0,
            "unmapped": 0,
            "invalid_slugs": 0,
        },
    }
    any_violation = False
    for skill_md in sorted(skills_root.rglob("SKILL.md")):
        rel = skill_md.relative_to(skills_root).parent.as_posix()
        text = skill_md.read_text(encoding="utf-8")
        entry: dict = {
            "path": rel,
            "skill_md": str(skill_md.relative_to(skills_root.parent)),
        }
        if has_data_classes(text):
            entry["status"] = "already_declared"
            report["counts"]["already_declared"] += 1
            report["skills"].append(entry)
            continue
        if rel not in _MAPPING:
            entry["status"] = "unmapped"
            entry["detail"] = (
                "no entry in curated _MAPPING; add one and re-run, "
                "or use skill-improve lazy backfill on next touch"
            )
            report["counts"]["unmapped"] += 1
            any_violation = True
            report["skills"].append(entry)
            continue
        slugs = _MAPPING[rel]
        bad = [s for s in slugs if s not in matrix_slugs]
        if bad:
            entry["status"] = "invalid_slugs"
            entry["proposed"] = slugs
            entry["bad_slugs"] = bad
            entry["detail"] = (
                "mapping cites slugs that are not in data-storage-matrix.md"
            )
            report["counts"]["invalid_slugs"] += 1
            any_violation = True
            report["skills"].append(entry)
            continue
        entry["status"] = "proposed"
        entry["proposed"] = slugs
        report["counts"]["proposed"] += 1
        report["skills"].append(entry)
    return report, any_violation


def apply_backfill(
    skills_root: Path,
    report: dict,
    only_skill: str | None,
) -> list[str]:
    """Write data_classes into SKILL.md for every entry with status=proposed.

    If `only_skill` is set, only that skill's directory basename is written;
    others stay untouched. Returns the list of written paths.
    """
    written: list[str] = []
    for entry in report["skills"]:
        if entry["status"] != "proposed":
            continue
        rel = entry["path"]
        if only_skill is not None and Path(rel).name != only_skill:
            continue
        skill_md = skills_root / rel / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        new_text = insert_data_classes(text, entry["proposed"])
        skill_md.write_text(new_text, encoding="utf-8")
        written.append(str(skill_md.relative_to(skills_root.parent)))
    return written


# --- CLI --------------------------------------------------------------------

def _plugin_root_default() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Backfill `metadata.kiho.data_classes:` frontmatter across "
            "45 SKILL.md files using a curated path→row mapping."
        ),
        epilog=(
            "Exit codes: 0 ok, 1 policy violation (unmapped skill or bad "
            "slug), 2 usage, 3 internal. Dry-run by default."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("propose", help="Dry-run: print proposed patches")
    pp.add_argument("--plugin-root", default=str(_plugin_root_default()))
    pp.add_argument("--json", action="store_true",
                    help="Emit only JSON (no human preamble)")

    pa = sub.add_parser("apply", help="Write data_classes into SKILL.md files")
    pa.add_argument("--plugin-root", default=str(_plugin_root_default()))
    pa.add_argument(
        "--skill",
        default=None,
        help="Apply to one skill only (by directory basename, e.g., kb-add)",
    )

    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    try:
        plugin_root = Path(args.plugin_root).resolve()
        skills_root = plugin_root / "skills"
        matrix_path = plugin_root / "references" / "data-storage-matrix.md"
        if not skills_root.is_dir():
            print(
                json.dumps({"status": "error",
                            "error": f"skills dir not found: {skills_root}"}),
                file=sys.stderr,
            )
            return 2
        if not matrix_path.is_file():
            print(
                json.dumps({"status": "error",
                            "error": f"matrix not found: {matrix_path}"}),
                file=sys.stderr,
            )
            return 2

        matrix_slugs = load_matrix_slugs(matrix_path)
        report, violation = build_report(skills_root, matrix_slugs)

        if args.cmd == "propose":
            if not getattr(args, "json", False):
                print("# data_classes backfill — dry-run report")
                print(f"Mapped:           {len(_MAPPING)} / 45 skills")
                print(f"Already declared: {report['counts']['already_declared']}")
                print(f"Proposed:         {report['counts']['proposed']}")
                print(f"Unmapped:         {report['counts']['unmapped']}")
                print(f"Invalid slugs:    {report['counts']['invalid_slugs']}")
                print("")
            print(json.dumps(report, indent=2))
            return 1 if violation else 0

        if args.cmd == "apply":
            if violation:
                print(
                    json.dumps({
                        "status": "policy_violation",
                        "error": "unmapped or invalid slugs — fix _MAPPING "
                                 "or run propose first",
                        "counts": report["counts"],
                    }),
                    file=sys.stderr,
                )
                return 1
            written = apply_backfill(skills_root, report, args.skill)
            print(json.dumps({
                "status": "ok",
                "written": written,
                "count": len(written),
                "skipped_already_declared": report["counts"]["already_declared"],
                "filter_skill": args.skill,
            }, indent=2))
            return 0

        print(
            json.dumps({"status": "error",
                        "error": f"unknown subcommand {args.cmd!r}"}),
            file=sys.stderr,
        )
        return 2

    except Exception as exc:  # pragma: no cover — defensive
        print(
            json.dumps({"status": "error", "error": repr(exc)}),
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
