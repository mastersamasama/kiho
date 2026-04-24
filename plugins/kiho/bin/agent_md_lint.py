#!/usr/bin/env python3
"""
agent_md_lint.py — kiho v6 agent.md validator (PR #1 scaffold, warn-only).

Checks agent.md files against schema v2 rules:
  1. schema_version == 2
  2. Required frontmatter keys present
  3. role_generic / role_specialties / soul §1 biography / soul §4 red-line
     objects do NOT contain any project name from $COMPANY_ROOT/project-registry.md
  4. Every skills[i] has a corresponding $COMPANY_ROOT/skills/<id>/SKILL.md
  5. memory_path directory exists with lessons.md / todos.md / observations.md (non-empty)
  6. current_state.active_project (if non-null) matches some experience[].project

Modes:
  --enforce (default in PR #3)           — exits 1 if any violation
  --warn-only (opt-out, PR #1 behavior)  — exits 0, emits warnings on stdout

Usage:
  python bin/agent_md_lint.py <path>                     # lint a single agent.md
  python bin/agent_md_lint.py <company_root>/agents/     # lint all agents
  python bin/agent_md_lint.py --enforce <path>

Exit codes:
  0 = clean (or warn-only mode)
  1 = violations in enforce mode
  2 = invocation error
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --- Optional deps: prefer stdlib; fall back gracefully -----------------------

try:
    # Python 3.11+
    import tomllib  # type: ignore
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:  # pragma: no cover
        tomllib = None

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    """One lint finding."""
    path: Path
    rule: str                 # R1 .. R6
    severity: str             # "error" | "warning"
    message: str
    snippet: str = ""

    def format(self) -> str:
        return f"[{self.severity.upper()}] {self.path}: {self.rule} — {self.message}"


@dataclass
class LintReport:
    violations: list[Violation] = field(default_factory=list)
    files_checked: int = 0

    def add(self, v: Violation) -> None:
        self.violations.append(v)

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warn_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")


# ---------------------------------------------------------------------------
# Frontmatter + body parsing
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def split_frontmatter_and_body(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) tuple. Frontmatter may be empty."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text = m.group(1)
    body = text[m.end():]

    if yaml is None:
        # Ultra-minimal fallback: parse only a handful of keys we care about.
        return _naive_frontmatter_parse(fm_text), body

    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        data = {}
    return data, body


def _naive_frontmatter_parse(fm_text: str) -> dict:
    """Extremely simple fallback if PyYAML missing. Top-level keys only."""
    out: dict = {}
    for line in fm_text.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#") or line.startswith(" "):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            out[key.strip()] = val.strip().strip('"').strip("'")
    return out


# ---------------------------------------------------------------------------
# Soul body helpers
# ---------------------------------------------------------------------------


_SECTION_RE = re.compile(r"^###\s+(\d+)\.\s+(.+?)$", re.MULTILINE)


def extract_soul_section(body: str, section_num: int) -> str:
    """Return the text of soul §N (between `### N. Title` and the next `### `)."""
    m = _SECTION_RE.search(body)
    if not m:
        return ""
    # Find the specific section
    matches = list(_SECTION_RE.finditer(body))
    for i, sec_match in enumerate(matches):
        if sec_match.group(1) == str(section_num):
            start = sec_match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            return body[start:end]
    return ""


# ---------------------------------------------------------------------------
# Project-registry reader
# ---------------------------------------------------------------------------


def load_project_names(company_root: Path) -> set[str]:
    """Read $COMPANY_ROOT/project-registry.md and return lowercase project tokens."""
    registry = company_root / "project-registry.md"
    if not registry.exists():
        return set()
    names: set[str] = set()
    for raw in registry.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("<!"):
            continue
        if line.startswith("-"):
            name = line.lstrip("- ").strip().lower()
            if name:
                names.add(name)
    return names


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


REQUIRED_FRONTMATTER_KEYS = [
    "schema_version",
    "name",
    "id",
    "role_generic",
    "role_specialties",
    "soul_version",
    "experience",
    "current_state",
    "skills",
    "memory_path",
    "tools",
    "hire_provenance",
]


def rule_r1_schema_version(path: Path, fm: dict, report: LintReport, severity: str) -> None:
    """R1: schema_version must equal 2."""
    sv = fm.get("schema_version")
    if sv != 2:
        report.add(Violation(
            path, "R1", severity,
            f"schema_version missing or != 2 (got {sv!r}) — v6 requires 2",
        ))


def rule_r2_required_keys(path: Path, fm: dict, report: LintReport, severity: str) -> None:
    """R2: all required frontmatter keys present."""
    for key in REQUIRED_FRONTMATTER_KEYS:
        if key not in fm:
            report.add(Violation(
                path, "R2", severity,
                f"required frontmatter key missing: {key}",
            ))


def rule_r3_no_project_coupling(
    path: Path, fm: dict, body: str, project_names: set[str],
    report: LintReport, severity: str,
) -> None:
    """R3: role_generic / role_specialties / soul §1 / soul §4 must not contain project names."""
    if not project_names:
        return  # nothing to check against

    def _scan(scope: str, text: str) -> None:
        lower = text.lower()
        for project in project_names:
            if project in lower:
                report.add(Violation(
                    path, "R3", severity,
                    f"{scope} contains project-locked string '{project}' — agents must be portable",
                    snippet=text[:120],
                ))

    _scan("role_generic", str(fm.get("role_generic") or ""))
    for sp in fm.get("role_specialties") or []:
        _scan("role_specialties", str(sp))
    _scan("soul §1 biography", extract_soul_section(body, 1))
    _scan("soul §4 red lines", extract_soul_section(body, 4))


def rule_r4_skills_resolve(
    path: Path, fm: dict, company_root: Path, report: LintReport, severity: str,
) -> None:
    """R4: every skills[i] resolves to $COMPANY_ROOT/skills/<id>/SKILL.md."""
    skills = fm.get("skills") or []
    if not isinstance(skills, list):
        report.add(Violation(path, "R4", severity, "skills must be a list"))
        return
    for skill_id in skills:
        if not isinstance(skill_id, str):
            continue
        skill_file = company_root / "skills" / skill_id / "SKILL.md"
        if not skill_file.exists():
            report.add(Violation(
                path, "R4", severity,
                f"skill '{skill_id}' does not resolve — expected file {skill_file}",
            ))


def rule_r5_memory_populated(
    path: Path, fm: dict, company_root: Path, report: LintReport, severity: str,
) -> None:
    """R5: memory_path directory exists with non-empty lessons/todos/observations."""
    mp_raw = str(fm.get("memory_path") or "")
    mp = mp_raw.replace("$COMPANY_ROOT", str(company_root))
    mem_dir = Path(mp)
    if not mem_dir.exists() or not mem_dir.is_dir():
        report.add(Violation(
            path, "R5", severity,
            f"memory_path does not exist or is not a directory: {mem_dir}",
        ))
        return
    for f in ("lessons.md", "todos.md", "observations.md"):
        p = mem_dir / f
        if not p.exists():
            report.add(Violation(
                path, "R5", severity,
                f"memory/{f} missing at {mem_dir}",
            ))
        elif p.stat().st_size == 0:
            report.add(Violation(
                path, "R5", severity,
                f"memory/{f} is empty (seed at hire time — do not leave empty)",
            ))


def rule_r6_active_project_in_experience(
    path: Path, fm: dict, report: LintReport, severity: str,
) -> None:
    """R6: current_state.active_project (if non-null) must equal some experience[].project."""
    cs = fm.get("current_state") or {}
    ap = cs.get("active_project")
    if ap is None:
        return
    exp = fm.get("experience") or []
    projects = {str(e.get("project")) for e in exp if isinstance(e, dict)}
    if ap not in projects:
        report.add(Violation(
            path, "R6", severity,
            f"current_state.active_project={ap!r} not found in experience[] (projects={sorted(projects)})",
        ))


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def lint_file(
    path: Path, company_root: Path, project_names: set[str], report: LintReport, severity: str,
) -> None:
    report.files_checked += 1
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        report.add(Violation(path, "IO", "error", f"failed to read: {e}"))
        return
    fm, body = split_frontmatter_and_body(text)
    if not fm:
        report.add(Violation(
            path, "R2", severity,
            "no YAML frontmatter found — agent.md v2 requires frontmatter",
        ))
        return
    rule_r1_schema_version(path, fm, report, severity)
    rule_r2_required_keys(path, fm, report, severity)
    rule_r3_no_project_coupling(path, fm, body, project_names, report, severity)
    rule_r4_skills_resolve(path, fm, company_root, report, severity)
    rule_r5_memory_populated(path, fm, company_root, report, severity)
    rule_r6_active_project_in_experience(path, fm, report, severity)


def collect_agent_files(target: Path) -> list[Path]:
    """If target is a file, return [target]. If dir, return all */agent.md."""
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(target.glob("*/agent.md"))
    return []


def find_company_root(explicit: str | None) -> Path:
    """Try explicit arg, then env, then config.toml."""
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("KIHO_COMPANY_ROOT")
    if env:
        return Path(env).resolve()
    # Walk up from CWD looking for a kiho plugin config.toml
    here = Path.cwd()
    for parent in [here, *here.parents]:
        candidate = parent / "plugins" / "kiho" / "skills" / "core" / "harness" / "kiho" / "config.toml"
        if candidate.exists() and tomllib is not None:
            try:
                with open(candidate, "rb") as f:
                    cfg = tomllib.load(f)
                cr = cfg.get("company_root", "")
                if cr:
                    return Path(cr).resolve()
            except Exception:
                pass
    # Fallback: give up, return CWD (lint will skip project-name check)
    return Path.cwd()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint kiho v6 agent.md files against schema v2 rules",
    )
    parser.add_argument("target", help="path to agent.md OR to a directory of agent dirs")
    parser.add_argument(
        "--company-root", default=None,
        help="override $COMPANY_ROOT (else from KIHO_COMPANY_ROOT env or config.toml)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--warn-only", action="store_true", default=False,
                       help="warn but exit 0 (PR #1 opt-out; default changed to enforce in PR #3)")
    group.add_argument("--enforce", action="store_true", default=False,
                       help="fail with exit 1 on any violation (PR #3 default)")
    args = parser.parse_args(argv)
    # PR #3 default: enforce unless --warn-only was passed explicitly.
    if not args.enforce and not args.warn_only:
        args.enforce = True

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"agent_md_lint: target not found: {target}", file=sys.stderr)
        return 2

    company_root = find_company_root(args.company_root)
    project_names = load_project_names(company_root)

    files = collect_agent_files(target)
    if not files:
        print(f"agent_md_lint: no agent.md files found under {target}", file=sys.stderr)
        return 0

    severity = "error" if args.enforce else "warning"
    report = LintReport()
    for f in files:
        lint_file(f, company_root, project_names, report, severity)

    for v in report.violations:
        print(v.format())

    print(
        f"\nagent_md_lint: {report.files_checked} file(s) checked; "
        f"{report.error_count} error(s), {report.warn_count} warning(s)",
        file=sys.stderr,
    )

    if args.enforce and report.error_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
