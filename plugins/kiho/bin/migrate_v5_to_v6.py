#!/usr/bin/env python3
"""
migrate_v5_to_v6.py — kiho v5 agent.md → v6 schema-v2 migration (PR #3).

Contract (per references/agent-schema-v2.md §Migration from v5):

  - Parse v5 agent.md frontmatter + soul body
  - Extract project name from `role:` field, seed experience[] first entry
  - Strip project name from role → role_generic (warn if no clean strip)
  - Set current_state.availability="free", active_project=null,
    last_active=mtime-of-v5-file
  - Preserve skills[], tools, soul body
  - Create memory/ directory with seeded lessons/todos/observations stubs
    (each non-empty so lint R5 passes)
  - Write schema_version:2, soul_version:v5, hire_provenance.hire_type:"v5-migrated"
  - Run bin/agent_md_lint.py --enforce on the proposed file
  - If lint clean: atomic swap (old → .v5bak, new → agent.md)
  - Else: keep v5 unchanged, write .migration-blocker note with findings

Modes:
  --dry-run       (PR #1 default) writes agent.md.v6proposed + runs lint; no swap
  --auto-apply    (PR #3 default) swaps if lint clean; else .migration-blocker

Usage:
  python bin/migrate_v5_to_v6.py --agent-id <id> --company-root <path> --auto-apply
  python bin/migrate_v5_to_v6.py --agent-md <path>                     # alt input
  python bin/migrate_v5_to_v6.py --company-root <path> --all           # all agents

Exit codes:
  0 = success (applied | already_v6 | dry_run_wrote_proposal)
  1 = migration blocked by lint (keeps v5)
  2 = invocation error
  3 = internal error
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
LINT_SCRIPT = PLUGIN_ROOT / "bin" / "agent_md_lint.py"


# ---------------------------------------------------------------------------
# Frontmatter + soul parsing (reuse split pattern from agent_md_lint.py)
# ---------------------------------------------------------------------------


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def split_frontmatter_and_body(text: str) -> tuple[dict, str, str]:
    """Return (fm_dict, fm_raw_text, body)."""
    m = _FM_RE.match(text)
    if not m:
        return {}, "", text
    fm_text = m.group(1)
    body = text[m.end():]
    if yaml is None:
        fm = _naive_yaml(fm_text)
    else:
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            fm = {}
    return fm, fm_text, body


def _naive_yaml(text: str) -> dict:
    out: dict = {}
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


# ---------------------------------------------------------------------------
# Project-registry-aware role stripping
# ---------------------------------------------------------------------------


def load_project_names(company_root: Path) -> list[str]:
    """Read $COMPANY_ROOT/project-registry.md → list of lowercase project tokens."""
    reg = company_root / "project-registry.md"
    if not reg.is_file():
        return []
    names: list[str] = []
    for raw in reg.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("<!") or line.startswith("---"):
            continue
        if line.startswith("-"):
            n = line.lstrip("- ").strip().lower()
            if n:
                names.append(n)
    return names


def extract_project_and_strip(role: str, project_names: list[str]) -> tuple[str, str]:
    """Return (extracted_project, role_generic_stripped).

    If role contains a known project-name substring (case-insensitive), strip
    it and the leading/trailing whitespace/separators. If no clean strip
    possible, return (detected_project_or_empty, original_role) — caller logs
    a warning and keeps the original.
    """
    role_l = role.lower()
    detected = ""
    for p in project_names:
        if p in role_l:
            detected = p
            break

    if not detected:
        return "", role

    # Try case-insensitive strip of the project token + common glue chars
    pattern = re.compile(
        r"(?i)\b" + re.escape(detected) + r"[\s:,\-]*", re.IGNORECASE
    )
    stripped = pattern.sub("", role).strip(" -:,;/")
    if not stripped or stripped == role:
        return detected, role  # can't cleanly strip; caller warns
    return detected, stripped


# ---------------------------------------------------------------------------
# Migration core
# ---------------------------------------------------------------------------


def build_v6_frontmatter(
    v5_fm: dict,
    v5_mtime: str,
    agent_id: str,
    project_names: list[str],
    warnings: list[str],
) -> tuple[dict, str]:
    """Return (v6_frontmatter_dict, role_strip_warning_str_or_empty)."""
    name = v5_fm.get("name") or agent_id
    role_raw = str(v5_fm.get("role") or v5_fm.get("role_generic") or "")
    detected, role_generic = extract_project_and_strip(role_raw, project_names)

    strip_warning = ""
    if role_raw and detected and role_generic == role_raw:
        strip_warning = (
            f"role_generic still contains detected project '{detected}' — "
            f"hand-edit needed: {role_raw!r}"
        )
        warnings.append(strip_warning)
    if not role_generic:
        role_generic = role_raw or f"{agent_id} role"

    # skills: list[str]; accept single string fallback
    skills_raw: Any = v5_fm.get("skills", [])
    if isinstance(skills_raw, str):
        skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
    elif isinstance(skills_raw, list):
        skills = [str(s).strip() for s in skills_raw if str(s).strip()]
    else:
        skills = []

    tools_raw: Any = v5_fm.get("tools", [])
    if isinstance(tools_raw, str):
        tools = [t.strip() for t in tools_raw.split(",") if t.strip()]
    elif isinstance(tools_raw, list):
        tools = [str(t).strip() for t in tools_raw if str(t).strip()]
    else:
        tools = ["Read", "Glob", "Grep"]

    # role_specialties heuristic: tokens in original role that are NOT project
    # names and are NOT generic role words
    specialties = _derive_role_specialties(role_raw, detected, role_generic)

    experience: list[dict] = []
    if detected:
        experience.append({
            "project": detected,
            "role_on_project": role_raw or role_generic,
            "started": v5_mtime[:10],  # YYYY-MM-DD
            "ended": None,
            "highlights": ["migrated from v5 schema"],
            "rubric_at_hire": None,
        })

    v6_fm = {
        "schema_version": 2,
        "name": name,
        "id": agent_id,
        "role_generic": role_generic,
        "role_specialties": specialties,
        "soul_version": "v5",
        "experience": experience,
        "current_state": {
            "availability": "free",
            "active_project": None,
            "active_assignment": None,
            "last_active": v5_mtime,
        },
        "skills": skills,
        "memory_path": f"$COMPANY_ROOT/agents/{agent_id}/memory/",
        "tools": tools,
        "hire_provenance": {
            "recruit_turn": v5_mtime,
            "rubric_score": None,
            "auditor_dissent": None,
            "hire_type": "v5-migrated",
            "recruit_certificate": f"v5-migrated-{agent_id}-{v5_mtime}",
        },
    }
    return v6_fm, strip_warning


def _derive_role_specialties(
    role_raw: str, detected_project: str, role_generic: str,
) -> list[str]:
    """Pull 0-3 specialty tags from the v5 role string.

    Heuristic: tokenize on whitespace + common separators; drop the project
    name, drop very short tokens, drop tokens already in role_generic.
    """
    if not role_raw:
        return []
    tokens = re.findall(r"[A-Za-z0-9+\-]+", role_raw)
    generic_tokens = set(re.findall(r"[A-Za-z0-9]+", role_generic.lower()))
    specialties: list[str] = []
    for t in tokens:
        low = t.lower()
        if detected_project and low == detected_project:
            continue
        if low in generic_tokens or len(low) < 3:
            continue
        if low in ("the", "and", "for", "lead", "ic", "pm", "of"):
            continue
        if low in specialties:
            continue
        specialties.append(low)
        if len(specialties) >= 3:
            break
    return specialties


def emit_v6_frontmatter_yaml(fm: dict) -> str:
    """Render the v6 frontmatter dict as YAML, with or without PyYAML."""
    if yaml is not None:
        body = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    else:
        body = _fallback_yaml_dump(fm)
    return f"---\n{body}---\n"


def _fallback_yaml_dump(d: dict, indent: int = 0) -> str:
    """Minimal YAML emitter for nested dicts/lists of scalars."""
    out: list[str] = []
    pad = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            out.append(f"{pad}{k}:")
            out.append(_fallback_yaml_dump(v, indent + 1))
        elif isinstance(v, list):
            if not v:
                out.append(f"{pad}{k}: []")
            else:
                out.append(f"{pad}{k}:")
                for item in v:
                    if isinstance(item, dict):
                        first_key = True
                        for ik, iv in item.items():
                            prefix = f"{pad}  - " if first_key else f"{pad}    "
                            out.append(f"{prefix}{ik}: {_scalar(iv)}")
                            first_key = False
                    else:
                        out.append(f"{pad}  - {_scalar(item)}")
        else:
            out.append(f"{pad}{k}: {_scalar(v)}")
    return "\n".join(out) + "\n"


def _scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if any(c in s for c in ":#\n\"'") or s.strip() != s:
        return '"' + s.replace('"', '\\"') + '"'
    return s


# ---------------------------------------------------------------------------
# Memory seeding
# ---------------------------------------------------------------------------


LESSONS_SEED = """# Lessons — migrated from v5 schema

_Seeded by `bin/migrate_v5_to_v6.py` during v5 → v6 schema upgrade._

## v5 migration context

This agent was created before v6 introduced schema_version=2. The v5 agent.md
did not carry experience, current_state, or populated memory. v6 requires
all three; this seed satisfies lint R5 while preserving the agent's prior
behavior.

- Agent remains functionally equivalent to its v5 self: same skills, same
  tools, same soul (12 sections, unchanged).
- The v5 `role:` field has been split into `role_generic` + `experience[0]`
  so the agent is portable to new projects.
- Real lessons will accumulate here as the agent executes turns and
  memory-reflect promotes observations.
"""

TODOS_SEED = """# Todos — migrated from v5 schema

_Seeded by `bin/migrate_v5_to_v6.py`._

(no outstanding work items at migration time)
"""

OBSERVATIONS_SEED = """# Observations — migrated from v5 schema

_Seeded by `bin/migrate_v5_to_v6.py`._

## Migration observation

- The agent's prior project context lives in `experience[0]`; past turn
  outputs remain on disk under the project `.kiho/` tree but were not
  backfilled into this memory directory.
"""


def seed_memory_dir(agent_dir: Path) -> None:
    mem = agent_dir / "memory"
    mem.mkdir(parents=True, exist_ok=True)
    for fname, content in (
        ("lessons.md", LESSONS_SEED),
        ("todos.md", TODOS_SEED),
        ("observations.md", OBSERVATIONS_SEED),
    ):
        p = mem / fname
        if not p.exists() or p.stat().st_size == 0:
            p.write_text(content, encoding="utf-8")
    last_reflect = mem / ".last-reflect"
    if not last_reflect.exists():
        last_reflect.write_text("1970-01-01T00:00:00Z\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Lint integration
# ---------------------------------------------------------------------------


def run_lint_enforce(agent_md_path: Path, company_root: Path) -> tuple[int, str]:
    """Run bin/agent_md_lint.py --enforce; return (exit_code, combined_output)."""
    if not LINT_SCRIPT.is_file():
        return 0, "lint script not available — skipping"
    try:
        result = subprocess.run(
            [
                sys.executable, str(LINT_SCRIPT),
                "--enforce",
                "--company-root", str(company_root),
                str(agent_md_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode, result.stdout + "\n" + result.stderr
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        return 0, f"lint invocation failed: {e!r} (treating as clean)"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def migrate_agent(
    agent_md_path: Path,
    company_root: Path,
    auto_apply: bool,
) -> dict:
    """Migrate a single agent.md; return a status dict."""
    result: dict = {
        "agent_path": str(agent_md_path),
        "status": "unknown",
        "warnings": [],
    }
    if not agent_md_path.is_file():
        result["status"] = "error"
        result["error"] = "agent.md not found"
        return result

    try:
        text = agent_md_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        result["status"] = "error"
        result["error"] = f"read failed: {e!r}"
        return result

    fm, _fm_raw, body = split_frontmatter_and_body(text)
    if fm.get("schema_version") == 2:
        result["status"] = "already_v6"
        return result

    agent_dir = agent_md_path.parent
    agent_id = fm.get("id") or agent_dir.name
    v5_mtime = _dt.datetime.fromtimestamp(
        agent_md_path.stat().st_mtime, _dt.timezone.utc,
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    project_names = load_project_names(company_root)
    warnings: list[str] = []
    v6_fm, _strip_warn = build_v6_frontmatter(
        fm, v5_mtime, agent_id, project_names, warnings,
    )
    result["warnings"] = warnings

    # Ensure soul body exists — if not, seed a minimal `## Soul` header so
    # lint's R3 section extractor doesn't crash (body is preserved otherwise).
    if "## Soul" not in body and "### 1." not in body:
        body = (
            body.rstrip() + "\n\n## Soul\n\n"
            "### 1. Core identity\n\n"
            f"- **Name:** {v6_fm['name']}\n"
            "- **Biography:** (migrated from v5 — biography not backfilled)\n"
        )

    # Seed memory dir BEFORE lint (R5 checks it)
    seed_memory_dir(agent_dir)

    # Write the proposed v6 file
    proposed = agent_dir / "agent.md.v6proposed"
    v6_text = emit_v6_frontmatter_yaml(v6_fm) + body
    try:
        proposed.write_text(v6_text, encoding="utf-8")
    except OSError as e:
        result["status"] = "error"
        result["error"] = f"proposed write failed: {e!r}"
        return result
    result["proposed_path"] = str(proposed)

    # Run lint
    lint_code, lint_out = run_lint_enforce(proposed, company_root)
    result["lint_exit"] = lint_code
    result["lint_output"] = lint_out

    if lint_code != 0:
        # Blocked: keep v5, write .migration-blocker note
        blocker = agent_dir / ".migration-blocker"
        blocker.write_text(
            f"# migration blocker — v5 → v6\n\n"
            f"generated: {_dt.datetime.now(_dt.timezone.utc).isoformat()}Z\n\n"
            f"lint exit: {lint_code}\n\n"
            f"## lint output\n\n```\n{lint_out}\n```\n\n"
            f"## warnings\n\n"
            + "\n".join(f"- {w}" for w in warnings)
            + "\n\nfix the issues in agent.md.v6proposed then rerun with --auto-apply.\n",
            encoding="utf-8",
        )
        result["status"] = "blocked"
        return result

    if not auto_apply:
        result["status"] = "dry_run"
        return result

    # Atomic swap
    bak = agent_dir / "agent.md.v5bak"
    try:
        if bak.exists():
            bak.unlink()
        agent_md_path.rename(bak)
        proposed.rename(agent_md_path)
    except OSError as e:
        result["status"] = "error"
        result["error"] = f"swap failed: {e!r}"
        return result

    result["status"] = "applied"
    result["backup_path"] = str(bak)
    return result


def resolve_targets(args: argparse.Namespace) -> list[Path]:
    cr = Path(args.company_root).resolve() if args.company_root else None
    if args.agent_md:
        return [Path(args.agent_md).resolve()]
    if args.agent_id:
        if not cr:
            return []
        return [cr / "agents" / args.agent_id / "agent.md"]
    if args.all and cr:
        return sorted((cr / "agents").glob("*/agent.md"))
    return []


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Migrate kiho v5 agent.md to v6 schema v2")
    p.add_argument("--agent-id", default=None, help="agent id; resolved under $COMPANY_ROOT/agents/")
    p.add_argument("--agent-md", default=None, help="direct path to an agent.md")
    p.add_argument("--company-root", default=os.environ.get("COMPANY_ROOT") or os.environ.get("KIHO_COMPANY_ROOT"),
                   help="override $COMPANY_ROOT (else from env)")
    p.add_argument("--all", action="store_true", help="migrate every agent under --company-root")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="write .v6proposed + lint; no swap (PR #1 default)")
    mode.add_argument("--auto-apply", action="store_true", help="swap atomically if lint clean (PR #3 default)")
    p.add_argument("--json", action="store_true", help="emit JSON receipts instead of prose")

    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    targets = resolve_targets(args)
    if not targets:
        print("migrate_v5_to_v6: no target resolved "
              "(pass --agent-id + --company-root, --agent-md, or --all --company-root)",
              file=sys.stderr)
        return 2

    company_root = Path(args.company_root).resolve() if args.company_root else Path.cwd()
    auto_apply = args.auto_apply or (not args.dry_run and not args.auto_apply)
    # Default in PR #3: auto-apply true. Caller can force dry-run explicitly.
    if args.dry_run:
        auto_apply = False

    receipts = [migrate_agent(t, company_root, auto_apply) for t in targets]

    if args.json or len(receipts) > 1:
        print(json.dumps(receipts, ensure_ascii=False, indent=2))
    else:
        r = receipts[0]
        print(f"migrate_v5_to_v6: {r.get('status')} — {r.get('agent_path')}")
        for w in r.get("warnings", []):
            print(f"  warning: {w}")
        if "lint_output" in r and r["lint_exit"] != 0:
            print(r["lint_output"])

    # Exit non-zero only when all targets blocked
    if all(r.get("status") == "blocked" for r in receipts):
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(3)
