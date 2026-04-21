#!/usr/bin/env python3
"""
cycle_runner.py — kiho v5.21+ orchestrator. The kernel.

Reads cycle templates (TOML) from references/cycle-templates/ and runs them as
state machines whose per-cycle state lives in <project>/.kiho/state/cycles/<id>/index.toml.

This script implements the protocol specified in
skills/_meta/cycle-runner/references/orchestrator-protocol.md verbatim. The DSL
grammar comes from skills/_meta/cycle-runner/references/template-dsl.md. The
7-verb core ability registry comes from references/core-abilities-registry.md.

Operations:
    open   --template-id <id> --params <json> [--cycle-id <id>] [--project-root <path>]
    advance --cycle-id <id> [--user-input <json>] [--project-root <path>]
    status --cycle-id <id> [--project-root <path>] [--format human|json]
    pause / resume / cancel --cycle-id <id> [--reason <text>]
    replay --cycle-id <id> [--detail brief|full]
    validate-template --path <path>

Exit codes (v5.15.2 convention):
    0 — operation succeeded (status=ok)
    1 — operation completed but cycle in non-OK state (blocked / noop on terminal)
    2 — usage error (bad args, missing files)
    3 — internal error (unhandled exception)
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

# Python 3.11+ has tomllib in stdlib; 3.10 needs tomli.
try:
    import tomllib as _toml
except ImportError:
    try:
        import tomli as _toml  # type: ignore[no-redef,import-not-found]
    except ImportError:
        print("FATAL: cycle_runner requires Python 3.11+ (tomllib) or 'tomli' on 3.10.", file=sys.stderr)
        sys.exit(3)

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PLUGIN_ROOT / "references" / "cycle-templates"
ABILITIES_REGISTRY = PLUGIN_ROOT / "references" / "core-abilities-registry.md"
CYCLE_EVENTS_JSONL = PLUGIN_ROOT / "_meta-runtime" / "cycle-events.jsonl"

TERMINAL_PHASES = frozenset({"closed-success", "closed-failure", "blocked", "cancelled", "paused"})
SENTINEL_ENTRY_SKILLS = frozenset({"__ceo_ask_user__", "__no_op__", "__hook_only__"})
HOOK_VERBS = frozenset({"memory-write", "kb-add", "memo-send", "incident-open", "standup-log"})
ALLOWED_DSL_NODES = (
    ast.Expression, ast.BoolOp, ast.UnaryOp, ast.Compare, ast.Constant,
    ast.Name, ast.Attribute, ast.Subscript, ast.Call,
    ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Load,
)
ALLOWED_BUILTINS = frozenset({"len", "is_null", "is_set"})

MAX_BUDGET_ITERS = 100
MAX_BUDGET_WALL_CLOCK_MIN = 180
MAX_BUDGET_PAGES = 500


# ============================================================================
# Utilities
# ============================================================================

def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_to_dt(s: str) -> _dt.datetime:
    return _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)


def _short_uuid() -> str:
    return uuid.uuid4().hex[:8]


def _atomic_write(path: Path, content: str) -> None:
    """Atomic-replace write: temp + fsync + rename."""
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


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_toml(path: Path) -> dict:
    with path.open("rb") as fp:
        return _toml.load(fp)


def _toml_dump(data: dict) -> str:
    """Minimal TOML serializer for our flat-ish index.toml structure."""
    lines: list[str] = []

    def _val(v: Any) -> str:
        if v is None:
            return '""'
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str):
            return json.dumps(v, ensure_ascii=False)
        if isinstance(v, list):
            inner = ", ".join(_val(x) for x in v)
            return f"[{inner}]"
        return json.dumps(v, ensure_ascii=False)

    def _emit_table(table: dict, prefix: str) -> None:
        scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
        subtables = {k: v for k, v in table.items() if isinstance(v, dict)}
        if scalars:
            for k, v in scalars.items():
                lines.append(f"{k} = {_val(v)}")
        for k, sub in subtables.items():
            full = f"{prefix}.{k}" if prefix else k
            lines.append("")
            lines.append(f"[{full}]")
            _emit_table(sub, full)

    # Top-level tables only
    top_scalars = {k: v for k, v in data.items() if not isinstance(v, dict)}
    if top_scalars:
        for k, v in top_scalars.items():
            lines.append(f"{k} = {_val(v)}")
    for k, table in data.items():
        if not isinstance(table, dict):
            continue
        lines.append("")
        lines.append(f"[{k}]")
        _emit_table(table, k)
    return "\n".join(lines).strip() + "\n"


# ============================================================================
# Restricted DSL evaluator
# ============================================================================

def _eval_dsl(expr: str, ctx: dict) -> bool:
    """Parse + walk a restricted-DSL boolean expression. Raises ValueError on
    forbidden constructs or unknown identifiers."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"DSL parse error: {e}")

    def _check(node: ast.AST) -> None:
        if not isinstance(node, ALLOWED_DSL_NODES):
            raise ValueError(f"DSL forbidden node: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_BUILTINS:
                raise ValueError("DSL only allows len(), is_null(), is_set() calls")
            for a in node.args:
                _check(a)
            return
        for child in ast.iter_child_nodes(node):
            _check(child)

    _check(tree)

    def _resolve(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _resolve(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            # TOML/JSON-style literals
            if node.id == "true":
                return True
            if node.id == "false":
                return False
            if node.id == "null" or node.id == "None":
                return None
            if node.id not in ctx:
                raise ValueError(f"DSL unknown name: {node.id}")
            return ctx[node.id]
        if isinstance(node, ast.Attribute):
            target = _resolve(node.value)
            if not isinstance(target, dict):
                raise ValueError(f"DSL attribute on non-dict: {node.attr}")
            if node.attr not in target:
                # Attribute access on a missing field returns None; success_condition
                # authors should use is_set() to test presence
                return None
            return target[node.attr]
        if isinstance(node, ast.Subscript):
            target = _resolve(node.value)
            key = _resolve(node.slice)
            return target[key]
        if isinstance(node, ast.Compare):
            left = _resolve(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = _resolve(comparator)
                if isinstance(op, ast.Eq) and not (left == right):
                    return False
                if isinstance(op, ast.NotEq) and not (left != right):
                    return False
                if isinstance(op, ast.Lt) and not (left < right):
                    return False
                if isinstance(op, ast.LtE) and not (left <= right):
                    return False
                if isinstance(op, ast.Gt) and not (left > right):
                    return False
                if isinstance(op, ast.GtE) and not (left >= right):
                    return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(_resolve(v) for v in node.values)
            if isinstance(node.op, ast.Or):
                return any(_resolve(v) for v in node.values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _resolve(node.operand)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("DSL invalid call")
            fname = node.func.id
            args = [_resolve(a) for a in node.args]
            if fname == "len":
                return len(args[0]) if args[0] is not None else 0
            if fname == "is_null":
                return args[0] is None
            if fname == "is_set":
                return args[0] is not None
        raise ValueError(f"DSL unsupported node: {type(node).__name__}")

    result = _resolve(tree)
    return bool(result)


# ============================================================================
# Core abilities registry parser
# ============================================================================

def load_abilities_registry() -> dict[str, set[str]]:
    """Parse references/core-abilities-registry.md to build {ability: {skill_id...}}."""
    try:
        text = ABILITIES_REGISTRY.read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict[str, set[str]] = {}
    current_verb: str = ""
    for line in text.splitlines():
        m = re.match(r"^###\s+`([a-z][a-z-]*)`\s*$", line)
        if m:
            verb_name = m.group(1) or ""
            current_verb = verb_name
            out[verb_name] = set()
            continue
        if not current_verb:
            continue
        # Match list items naming a skill: "- `skills/.../<name>/SKILL.md`" or "- `__ceo_ask_user__`" etc.
        m2 = re.match(r"^-\s+`([^`]+)`", line)
        if m2:
            ref = m2.group(1)
            # Extract skill id: last path component before SKILL.md, or sentinel as-is
            if ref.startswith("__"):
                out[current_verb].add(ref)
            elif ref.endswith("/SKILL.md"):
                # skills/core/.../<name>/SKILL.md
                slug = ref.rstrip("/").split("/")[-2]
                out[current_verb].add(slug)
            elif "/" in ref and "agents/" in ref:
                # agents/<name>.md op=...
                slug = ref.split("/")[-1].replace(".md", "")
                # allow "<agent> op=<op>" patterns
                op_match = re.search(r"op=`?([a-z-]+)`?", ref)
                if op_match:
                    out[current_verb].add(f"{slug}:{op_match.group(1)}")
                else:
                    out[current_verb].add(slug)
            else:
                out[current_verb].add(ref)
    # Sentinels are valid under any ability for __no_op__/__hook_only__; __ceo_ask_user__ only under "decide"
    return out


# ============================================================================
# Template loading + validation
# ============================================================================

def load_template(template_id: str, version: str | None = None) -> dict:
    """Load the named template TOML. `version` is reserved for future
    history-based pinning; v5.21 always uses the on-disk file regardless."""
    _ = version  # mark intentionally unused; pin-by-version comes in v5.22
    path = TEMPLATES_DIR / f"{template_id}.toml"
    if not path.is_file():
        raise FileNotFoundError(f"template not found: {path}")
    return _load_toml(path)


def validate_template(template: dict, abilities: dict[str, set[str]]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    for required in ("meta", "parameters", "index_schema", "phases", "budget"):
        if required not in template:
            errors.append(f"missing top-level table: [{required}]")
    if "phases" in template and not isinstance(template["phases"], list):
        errors.append("[[phases]] must be an array of tables")
    if errors:
        return errors, warnings

    meta = template["meta"]
    for f in ("template_id", "version", "description", "core_abilities_used"):
        if f not in meta:
            errors.append(f"meta.{f} missing")

    if not re.match(r"^\d+\.\d+\.\d+$", meta.get("version", "")):
        errors.append(f"meta.version not semver: {meta.get('version')}")

    declared_abilities = set(meta.get("core_abilities_used") or [])
    unknown_abilities = declared_abilities - set(abilities.keys())
    if unknown_abilities:
        errors.append(f"meta.core_abilities_used has unknown verbs: {sorted(unknown_abilities)}")

    budget = template["budget"]
    if budget.get("max_iters", 0) > MAX_BUDGET_ITERS:
        errors.append(f"budget.max_iters > {MAX_BUDGET_ITERS}")
    if budget.get("max_wall_clock_min", 0) > MAX_BUDGET_WALL_CLOCK_MIN:
        errors.append(f"budget.max_wall_clock_min > {MAX_BUDGET_WALL_CLOCK_MIN}")
    if budget.get("max_pages", 0) > MAX_BUDGET_PAGES:
        errors.append(f"budget.max_pages > {MAX_BUDGET_PAGES}")

    phase_ids: list[str] = []
    for phase in template.get("phases", []):
        pid = phase.get("id", "")
        if not pid or not re.match(r"^[a-z][a-z0-9-]*$", pid):
            errors.append(f"phase id invalid (kebab-case required): {pid!r}")
            continue
        if pid in TERMINAL_PHASES:
            errors.append(f"phase id collides with reserved terminal: {pid}")
        phase_ids.append(pid)

        ability = phase.get("core_ability", "")
        if ability not in abilities:
            errors.append(f"phase {pid}: unknown core_ability {ability!r}")
            continue
        entry = phase.get("entry_skill", "")
        if entry in SENTINEL_ENTRY_SKILLS:
            if entry == "__ceo_ask_user__" and ability != "decide":
                errors.append(f"phase {pid}: __ceo_ask_user__ requires core_ability=decide")
        else:
            ability_skills = abilities[ability]
            # Allow op-suffixed lookups: phase entry "kiho-kb-manager:kb-add"
            # matches registry entry "kiho-kb-manager" (the agent provides the op)
            if entry not in ability_skills:
                entry_base = entry.split(":", 1)[0]
                if entry_base not in ability_skills:
                    errors.append(
                        f"phase {pid}: entry_skill {entry!r} not registered under ability {ability!r}"
                    )
        # Validate success_condition parses
        sc = phase.get("success_condition")
        if sc:
            try:
                ast.parse(sc, mode="eval")
            except SyntaxError as e:
                errors.append(f"phase {pid}: success_condition syntax error: {e}")

    valid_targets = set(phase_ids) | TERMINAL_PHASES
    for phase in template.get("phases", []):
        pid = phase.get("id", "")
        for k in ("on_success", "on_failure"):
            target = phase.get(k)
            if target and target not in valid_targets:
                errors.append(f"phase {pid}: {k}={target!r} unknown")

    # Hooks
    hooks = template.get("lifecycle_hooks", {})
    for hook_name, hook_list in hooks.items():
        if not isinstance(hook_list, list):
            errors.append(f"lifecycle_hooks.{hook_name} must be array")
            continue
        for h in hook_list:
            verb = (h.split(maxsplit=1)[0] if isinstance(h, str) and h else "")
            if verb and verb not in HOOK_VERBS:
                errors.append(f"lifecycle_hooks.{hook_name}: unknown verb {verb!r}")

    if "phases" in template and template["phases"]:
        first_id = template["phases"][0].get("id", "")
        if first_id and first_id not in phase_ids:
            warnings.append(f"first phase {first_id!r} is not in validated id set (likely earlier error)")

    return errors, warnings


# ============================================================================
# Index schema initialization + validation
# ============================================================================

def init_index_data(index_schema: dict) -> dict:
    """Type-defaulted initialization of phase-data tables per schema."""
    out: dict[str, dict] = {}
    for table_name, fields in index_schema.items():
        tab: dict[str, Any] = {}
        for fname, ftype in (fields or {}).items():
            tab[fname] = _type_default(ftype)
        out[table_name] = tab
    return out


def _type_default(t: str) -> Any:
    if t == "string":
        return ""
    if t == "int":
        return 0
    if t == "float":
        return 0.0
    if t == "bool":
        return False
    if t.startswith("list["):
        return []
    if t.startswith("enum["):
        # First option as default
        opts = t[len("enum["):-1].split(",")
        return opts[0].strip() if opts else ""
    if "|null" in t:
        return None
    return ""


# ============================================================================
# Cycle paths
# ============================================================================

def cycle_dir(project_root: Path, cycle_id: str) -> Path:
    return project_root / ".kiho" / "state" / "cycles" / cycle_id


def index_path(project_root: Path, cycle_id: str) -> Path:
    return cycle_dir(project_root, cycle_id) / "index.toml"


def handoffs_path(project_root: Path, cycle_id: str) -> Path:
    return cycle_dir(project_root, cycle_id) / "handoffs.jsonl"


def lock_path(project_root: Path, cycle_id: str) -> Path:
    return cycle_dir(project_root, cycle_id) / ".lock"


# ============================================================================
# Template interpolation
# ============================================================================

_INTERP_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


def _interp(template_str: str, ctx: dict) -> str:
    def _sub(m: re.Match) -> str:
        path = m.group(1)
        parts = path.split(".")
        cur: Any = ctx
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return f"{{{path}}}"  # leave unresolved (caller decides)
        return str(cur)
    return _INTERP_RE.sub(_sub, template_str)


# ============================================================================
# Hook execution
# ============================================================================

def _parse_hook_kwargs(rest: str) -> dict[str, Any]:
    """Parse 'k1=v1 k2=v2 k3="quoted v3 with spaces"' into a dict."""
    out: dict[str, Any] = {}
    pos = 0
    while pos < len(rest):
        while pos < len(rest) and rest[pos].isspace():
            pos += 1
        if pos >= len(rest):
            break
        eq = rest.find("=", pos)
        if eq < 0:
            break
        key = rest[pos:eq].strip()
        pos = eq + 1
        if pos < len(rest) and rest[pos] in ("'", '"'):
            quote = rest[pos]
            pos += 1
            end = rest.find(quote, pos)
            if end < 0:
                val = rest[pos:]
                pos = len(rest)
            else:
                val = rest[pos:end]
                pos = end + 1
        else:
            sp = rest.find(" ", pos)
            if sp < 0:
                val = rest[pos:]
                pos = len(rest)
            else:
                val = rest[pos:sp]
                pos = sp + 1
        out[key] = val
    return out


def execute_hook(hook_str: str, ctx: dict, cycle_id: str) -> dict:
    """Execute one hook. Returns {verb, ok, error?}. Best-effort; never raises."""
    _ = cycle_id  # reserved for v5.22 inline hook dispatch; v5.21 defers to CEO
    try:
        rendered = _interp(hook_str, ctx)
        parts = rendered.split(maxsplit=1)
        verb = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        kwargs = _parse_hook_kwargs(rest)
        if verb not in HOOK_VERBS:
            return {"verb": verb, "ok": False, "error": "unknown_verb"}
        # v5.21 implementation strategy: log the hook intent to cycle-events
        # so it's observable, but DO NOT actually invoke the underlying skill from
        # cycle_runner itself — that would deepen the call stack and risk recursion
        # (e.g. incident-open hook firing during a cycle that's already in incident-lifecycle).
        # CEO observes hook events at INTEGRATE step and dispatches them via normal Agent path.
        # See orchestrator-protocol.md §"Hook execution sub-protocol" for the rationale.
        return {"verb": verb, "ok": True, "deferred_to_ceo": True, "kwargs": kwargs}
    except Exception as exc:
        return {"verb": "?", "ok": False, "error": repr(exc)}


# ============================================================================
# Operations
# ============================================================================

def op_open(template_id: str, params: dict, project_root: Path,
            cycle_id_override: str | None = None) -> dict:
    abilities = load_abilities_registry()
    template = load_template(template_id)
    errors, warnings = validate_template(template, abilities)
    if errors:
        return {"status": "error", "op": "open", "reason": "template_validation_failed",
                "errors": errors, "warnings": warnings}

    # Validate params against template
    p_schema = template.get("parameters", {})
    required = p_schema.get("required", []) or []
    optional = p_schema.get("optional", {}) or {}
    for r in required:
        if r not in params:
            return {"status": "error", "op": "open", "reason": f"missing required param: {r}"}
    extra = set(params.keys()) - set(required) - set(optional.keys())
    extra_warning = sorted(extra) if extra else None

    # Generate cycle id
    if cycle_id_override:
        cycle_id = cycle_id_override
    else:
        prefix = template_id[:8]
        date_str = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
        cycle_id = f"{prefix}-{date_str}-{_short_uuid()}"

    cdir = cycle_dir(project_root, cycle_id)
    if cdir.exists():
        return {"status": "error", "op": "open", "reason": f"cycle dir exists: {cdir}"}

    cdir.mkdir(parents=True, exist_ok=False)

    first_phase = template["phases"][0]["id"]
    budget = template["budget"]
    now = _utcnow_iso()

    index_data = init_index_data(template.get("index_schema", {}))
    index = {
        "meta": {
            "cycle_id": cycle_id,
            "template_id": template_id,
            "template_version": template["meta"]["version"],
            "opened_at": now,
            "opened_by": "ceo-01",
            "requestor": params.get("requestor", "user"),
            "phase": first_phase,
            "phase_entered_at": now,
            "phase_iters": 0,
            "status": "in_progress",
        },
        "budget": {
            "iters_used": 0,
            "iters_max": int(budget.get("max_iters", 30)),
            "pages_used": 0,
            "pages_max": int(budget.get("max_pages", 50)),
            "wall_clock_min_used": 0,
            "wall_clock_min_max": int(budget.get("max_wall_clock_min", 60)),
        },
        "params": dict(params),
        **index_data,
        "blockers": {},
    }

    _atomic_write(index_path(project_root, cycle_id), _toml_dump(index))
    _append_jsonl(handoffs_path(project_root, cycle_id), {
        "ts": now, "cycle_id": cycle_id, "action": "opened",
        "template_id": template_id, "template_version": template["meta"]["version"],
        "first_phase": first_phase,
    })
    _append_jsonl(CYCLE_EVENTS_JSONL, {
        "ts": now, "cycle_id": cycle_id, "template_id": template_id,
        "template_version": template["meta"]["version"], "op": "open",
        "phase_after": first_phase, "transitioned": False,
        "iter_in_phase": 0, "blocker_reason": None, "escalation": None,
        "budget": index["budget"], "duration_ms": 0,
    })

    # Fire on_open hooks
    hooks_fired = []
    for hook in template.get("lifecycle_hooks", {}).get("on_open", []):
        ctx = {"cycle_id": cycle_id, "meta": index["meta"], "index": index, "params": params}
        hooks_fired.append(execute_hook(hook, ctx, cycle_id))

    return {
        "status": "ok",
        "op": "open",
        "cycle_id": cycle_id,
        "template_id": template_id,
        "template_version": template["meta"]["version"],
        "first_phase": first_phase,
        "hooks_fired": hooks_fired,
        "extra_params_warning": extra_warning,
    }


def op_status(cycle_id: str, project_root: Path, fmt: str = "human") -> dict:
    _ = fmt  # v5.21 always returns json-shaped dict; human formatting handled by replay tool
    ip = index_path(project_root, cycle_id)
    if not ip.is_file():
        return {"status": "error", "op": "status", "reason": "cycle_not_found"}
    index = _load_toml(ip)
    return {
        "status": "ok",
        "op": "status",
        "cycle_id": cycle_id,
        "phase": index["meta"]["phase"],
        "lifecycle_status": index["meta"]["status"],
        "template_id": index["meta"]["template_id"],
        "template_version": index["meta"]["template_version"],
        "iter_in_phase": index["meta"].get("phase_iters", 0),
        "budget": index["budget"],
        "blockers": index.get("blockers", {}),
    }


def op_advance(cycle_id: str, project_root: Path, user_input: dict | None = None) -> dict:
    start_ts = _utcnow_iso()
    ip = index_path(project_root, cycle_id)
    if not ip.is_file():
        return {"status": "error", "op": "advance", "reason": "cycle_not_found"}
    index = _load_toml(ip)

    meta = index["meta"]

    # Pre-checks
    if meta["status"] in ("paused", "closed-success", "closed-failure", "cancelled"):
        return {"status": "noop", "op": "advance", "cycle_id": cycle_id,
                "reason": f"status_{meta['status']}"}
    if meta["phase"] in TERMINAL_PHASES:
        return {"status": "noop", "op": "advance", "cycle_id": cycle_id,
                "reason": f"terminal_phase_{meta['phase']}"}

    # Budget pre-check
    budget = index["budget"]
    opened_at = _iso_to_dt(meta["opened_at"])
    elapsed_min = int((_dt.datetime.now(_dt.timezone.utc) - opened_at).total_seconds() // 60)
    budget["wall_clock_min_used"] = elapsed_min
    if budget["iters_max"] > 0 and budget["iters_used"] >= budget["iters_max"]:
        return _block_cycle(index, project_root, cycle_id, "budget_iters_exhausted")
    if budget["wall_clock_min_max"] > 0 and elapsed_min >= budget["wall_clock_min_max"]:
        return _block_cycle(index, project_root, cycle_id, "budget_wall_clock_exhausted")
    if budget["pages_max"] > 0 and budget["pages_used"] >= budget["pages_max"]:
        return _block_cycle(index, project_root, cycle_id, "budget_pages_exhausted")

    # Load template
    try:
        template = load_template(meta["template_id"])
    except FileNotFoundError:
        return _block_cycle(index, project_root, cycle_id, "template_not_found")

    # Resolve current phase
    phase = next((p for p in template["phases"] if p["id"] == meta["phase"]), None)
    if phase is None:
        return _block_cycle(index, project_root, cycle_id, "phase_id_unknown")

    abilities = load_abilities_registry()
    ability_skills = abilities.get(phase.get("core_ability", ""), set())

    entry = phase.get("entry_skill", "")
    phase_before = meta["phase"]
    transitioned = False
    escalation = None
    blocker_reason = None

    # Handle entry types
    if entry == "__ceo_ask_user__":
        if user_input is None:
            # Render question + options, return escalation
            ctx = {"cycle_id": cycle_id, "meta": meta, "index": index, "params": index["params"]}
            args_template = phase.get("entry_args_template", "")
            rendered = _interp(args_template, ctx)
            escalation = {
                "rendered_args": rendered,
                "phase": phase_before,
            }
            _append_jsonl(handoffs_path(project_root, cycle_id), {
                "ts": start_ts, "cycle_id": cycle_id, "action": "escalate_to_user",
                "phase": phase_before, "rendered_args": rendered,
            })
            _append_jsonl(CYCLE_EVENTS_JSONL, {
                "ts": start_ts, "cycle_id": cycle_id, "template_id": meta["template_id"],
                "template_version": meta["template_version"], "op": "advance",
                "phase_before": phase_before, "phase_after": phase_before,
                "transitioned": False, "iter_in_phase": meta.get("phase_iters", 0),
                "blocker_reason": None, "escalation": "ceo_ask_user", "budget": budget,
                "duration_ms": 0,
            })
            # Don't increment iters for an ask
            return {"status": "ok", "op": "advance", "cycle_id": cycle_id,
                    "phase_before": phase_before, "phase_after": phase_before,
                    "transitioned": False, "escalate_to_user": escalation,
                    "blocker_reason": None, "budget": budget,
                    "next_action": "CEO calls AskUserQuestion; re-invoke advance with --user-input"}
        # User input present → write to index and let success_condition evaluate
        out_path = phase.get("output_to_index_path", "")
        if out_path and isinstance(user_input, dict):
            tab = index.setdefault(out_path, {})
            tab.update(user_input)
    elif entry in ("__no_op__", "__hook_only__"):
        # Allow user_input writes so an operator can supply confirmation fields
        # for these placeholder phases (e.g., mitigation confirmation in incident-lifecycle).
        if user_input is not None and isinstance(user_input, dict):
            out_path = phase.get("output_to_index_path", "")
            if out_path:
                tab = index.setdefault(out_path, {})
                tab.update(user_input)
    else:
        # Real atomic skill
        if entry not in ability_skills and not any(s.split(":", 1)[0] == entry for s in ability_skills):
            return _block_cycle(index, project_root, cycle_id, "ability_skill_mismatch")
        # v5.21: emit a deferred-invocation marker. The orchestrator does not invoke
        # sub-agents directly (Agent tool is a Claude Code construct; cycle_runner
        # is a Python subprocess). Instead it returns a structured "to-invoke" payload
        # the CEO loop translates into an Agent spawn. After spawn returns, CEO
        # re-invokes cycle_runner advance with --user-input carrying the skill output.
        # This keeps cycle_runner pure-Python + dispatcher-free while preserving
        # the orchestrator/skill separation.
        ctx = {"cycle_id": cycle_id, "meta": meta, "index": index, "params": index["params"]}
        rendered_args = _interp(phase.get("entry_args_template", ""), ctx)
        if user_input is None:
            escalation = {
                "kind": "skill_invocation_required",
                "phase": phase_before,
                "entry_skill": entry,
                "rendered_args": rendered_args,
                "core_ability": phase.get("core_ability"),
                "required_role": phase.get("required_role"),
            }
            _append_jsonl(handoffs_path(project_root, cycle_id), {
                "ts": start_ts, "cycle_id": cycle_id, "action": "delegate_skill",
                "phase": phase_before, "entry_skill": entry,
            })
            return {"status": "ok", "op": "advance", "cycle_id": cycle_id,
                    "phase_before": phase_before, "phase_after": phase_before,
                    "transitioned": False, "delegate_to_skill": escalation,
                    "blocker_reason": None, "budget": budget,
                    "next_action": "CEO spawns the skill; re-invoke advance with --user-input carrying skill output"}
        # Skill has run; user_input carries its structured output
        out_path = phase.get("output_to_index_path", "")
        if out_path and isinstance(user_input, dict):
            tab = index.setdefault(out_path, {})
            tab.update(user_input)
        # Bump pages if phase declares output_pages
        page_count = int(phase.get("output_pages", 0))
        if page_count:
            budget["pages_used"] += page_count

    # Evaluate success condition
    sc = phase.get("success_condition", "true")
    eval_ctx = {"index": index, "params": index["params"]}
    try:
        success = _eval_dsl(sc, eval_ctx)
    except ValueError as e:
        return _block_cycle(index, project_root, cycle_id, f"success_condition_invalid: {e}")

    phase_iters = meta.get("phase_iters", 0) + 1

    if success:
        next_phase = phase.get("on_success")
        if not next_phase:
            return _block_cycle(index, project_root, cycle_id, "phase_no_on_success_target")
        meta["phase"] = next_phase
        meta["phase_entered_at"] = _utcnow_iso()
        meta["phase_iters"] = 0
        transitioned = True
        if next_phase == "closed-success":
            meta["status"] = "closed-success"
        elif next_phase == "closed-failure":
            meta["status"] = "closed-failure"
        elif next_phase == "blocked":
            meta["status"] = "blocked"
            blocker_reason = "explicit_on_success_to_blocked"
    else:
        if phase_iters >= int(phase.get("budget_iters", 5)):
            next_phase = phase.get("on_failure", "blocked")
            meta["phase"] = next_phase
            meta["phase_entered_at"] = _utcnow_iso()
            meta["phase_iters"] = 0
            transitioned = True
            if next_phase == "blocked":
                meta["status"] = "blocked"
                blocker_reason = f"phase_{phase_before}_could_not_satisfy"
            elif next_phase == "closed-failure":
                meta["status"] = "closed-failure"
        else:
            meta["phase_iters"] = phase_iters

    budget["iters_used"] += 1

    # Fire transition hooks if terminal
    hooks_fired = []
    if meta["status"] in ("closed-success", "closed-failure"):
        hook_key = "on_close_success" if meta["status"] == "closed-success" else "on_close_failure"
        ctx = {"cycle_id": cycle_id, "meta": meta, "index": index, "params": index["params"]}
        for hook in template.get("lifecycle_hooks", {}).get(hook_key, []):
            hooks_fired.append(execute_hook(hook, ctx, cycle_id))

    # Persist index
    _atomic_write(ip, _toml_dump(index))

    # Audit trail
    end_ts = _utcnow_iso()
    duration_ms = int(
        (_dt.datetime.now(_dt.timezone.utc) - _iso_to_dt(start_ts)).total_seconds() * 1000
    )
    _append_jsonl(handoffs_path(project_root, cycle_id), {
        "ts": end_ts, "cycle_id": cycle_id,
        "from": phase_before, "to": meta["phase"],
        "transitioned": transitioned, "reason": blocker_reason or ("success_condition_true" if success else "phase_iter_increment"),
        "emitted_by": "cycle-runner",
    })
    _append_jsonl(CYCLE_EVENTS_JSONL, {
        "ts": end_ts, "cycle_id": cycle_id, "template_id": meta["template_id"],
        "template_version": meta["template_version"], "op": "advance",
        "phase_before": phase_before, "phase_after": meta["phase"],
        "transitioned": transitioned, "iter_in_phase": meta["phase_iters"],
        "blocker_reason": blocker_reason, "escalation": escalation and "deferred",
        "budget": budget, "duration_ms": duration_ms,
        "hooks_fired_count": len(hooks_fired),
    })

    return {
        "status": "ok" if not blocker_reason else "blocked",
        "op": "advance", "cycle_id": cycle_id,
        "phase_before": phase_before, "phase_after": meta["phase"],
        "transitioned": transitioned, "iter_in_phase": meta["phase_iters"],
        "budget": budget,
        "escalate_to_user": None,
        "blocker_reason": blocker_reason,
        "lifecycle_status": meta["status"],
        "hooks_fired": hooks_fired,
        "duration_ms": duration_ms,
    }


def _block_cycle(index: dict, project_root: Path, cycle_id: str, reason: str) -> dict:
    index["meta"]["status"] = "blocked"
    index.setdefault("blockers", {})["last_reason"] = reason
    index["blockers"]["last_at"] = _utcnow_iso()
    _atomic_write(index_path(project_root, cycle_id), _toml_dump(index))
    _append_jsonl(handoffs_path(project_root, cycle_id), {
        "ts": _utcnow_iso(), "cycle_id": cycle_id, "action": "blocked", "reason": reason,
    })
    _append_jsonl(CYCLE_EVENTS_JSONL, {
        "ts": _utcnow_iso(), "cycle_id": cycle_id,
        "template_id": index["meta"]["template_id"],
        "template_version": index["meta"]["template_version"],
        "op": "advance", "phase_before": index["meta"]["phase"],
        "phase_after": index["meta"]["phase"], "transitioned": False,
        "iter_in_phase": index["meta"].get("phase_iters", 0),
        "blocker_reason": reason, "escalation": None, "budget": index["budget"],
        "duration_ms": 0,
    })
    return {"status": "blocked", "op": "advance", "cycle_id": cycle_id,
            "phase_before": index["meta"]["phase"], "phase_after": index["meta"]["phase"],
            "transitioned": False, "blocker_reason": reason,
            "lifecycle_status": "blocked", "budget": index["budget"]}


def op_pause(cycle_id: str, project_root: Path, reason: str | None = None) -> dict:
    return _set_status(cycle_id, project_root, "paused", reason or "operator_pause")


def op_resume(cycle_id: str, project_root: Path, reason: str | None = None) -> dict:
    return _set_status(cycle_id, project_root, "in_progress", reason or "operator_resume")


def op_cancel(cycle_id: str, project_root: Path, reason: str | None = None) -> dict:
    res = _set_status(cycle_id, project_root, "cancelled", reason or "operator_cancel")
    # Fire on_close_failure hooks
    if res["status"] == "ok":
        ip = index_path(project_root, cycle_id)
        index = _load_toml(ip)
        try:
            template = load_template(index["meta"]["template_id"])
            ctx = {"cycle_id": cycle_id, "meta": index["meta"], "index": index, "params": index["params"]}
            hooks = []
            for hook in template.get("lifecycle_hooks", {}).get("on_close_failure", []):
                hooks.append(execute_hook(hook, ctx, cycle_id))
            res["hooks_fired"] = hooks
        except FileNotFoundError:
            pass
    return res


def _set_status(cycle_id: str, project_root: Path, new_status: str, reason: str) -> dict:
    ip = index_path(project_root, cycle_id)
    if not ip.is_file():
        return {"status": "error", "reason": "cycle_not_found"}
    index = _load_toml(ip)
    old_status = index["meta"]["status"]
    index["meta"]["status"] = new_status
    if new_status in ("paused", "cancelled"):
        index.setdefault("blockers", {})["status_change_reason"] = reason
    _atomic_write(ip, _toml_dump(index))
    _append_jsonl(handoffs_path(project_root, cycle_id), {
        "ts": _utcnow_iso(), "cycle_id": cycle_id, "action": new_status,
        "from_status": old_status, "reason": reason,
    })
    _append_jsonl(CYCLE_EVENTS_JSONL, {
        "ts": _utcnow_iso(), "cycle_id": cycle_id,
        "template_id": index["meta"]["template_id"],
        "template_version": index["meta"]["template_version"],
        "op": new_status, "phase_before": index["meta"]["phase"],
        "phase_after": index["meta"]["phase"], "transitioned": False,
        "iter_in_phase": 0, "blocker_reason": None, "escalation": None,
        "budget": index["budget"], "duration_ms": 0,
    })
    return {"status": "ok", "op": new_status, "cycle_id": cycle_id,
            "from_status": old_status, "to_status": new_status, "reason": reason}


def op_validate_template_cli(path: Path) -> dict:
    if not path.is_file():
        return {"status": "error", "reason": f"file not found: {path}"}
    template = _load_toml(path)
    abilities = load_abilities_registry()
    errors, warnings = validate_template(template, abilities)
    meta = template.get("meta", {})
    expected_id = path.stem
    if meta.get("template_id") != expected_id:
        errors.append(f"meta.template_id ({meta.get('template_id')}) != filename ({expected_id})")
    return {
        "status": "valid" if not errors else "invalid",
        "template_id": meta.get("template_id"),
        "version": meta.get("version"),
        "errors": errors,
        "warnings": warnings,
    }


# ============================================================================
# CLI
# ============================================================================

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="kiho cycle-runner: the v5.21 lifecycle orchestrator kernel.",
        epilog="See skills/_meta/cycle-runner/SKILL.md for full operation semantics.",
    )
    sub = p.add_subparsers(dest="op", required=True)

    sp = sub.add_parser("open")
    sp.add_argument("--template-id", required=True)
    sp.add_argument("--params", default="{}", help="JSON object")
    sp.add_argument("--cycle-id", help="optional override")
    sp.add_argument("--project-root", default=".")

    sa = sub.add_parser("advance")
    sa.add_argument("--cycle-id", required=True)
    sa.add_argument("--user-input", help="JSON object (for __ceo_ask_user__ phases or skill-output relay)")
    sa.add_argument("--project-root", default=".")

    ss = sub.add_parser("status")
    ss.add_argument("--cycle-id", required=True)
    ss.add_argument("--project-root", default=".")
    ss.add_argument("--format", choices=["human", "json"], default="json")

    for op in ("pause", "resume", "cancel"):
        sx = sub.add_parser(op)
        sx.add_argument("--cycle-id", required=True)
        sx.add_argument("--reason")
        sx.add_argument("--project-root", default=".")

    sr = sub.add_parser("replay")
    sr.add_argument("--cycle-id", required=True)
    sr.add_argument("--detail", choices=["brief", "full"], default="brief")
    sr.add_argument("--project-root", default=".")

    sv = sub.add_parser("validate-template")
    sv.add_argument("--path", required=True)

    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    try:
        if args.op == "open":
            params = json.loads(args.params)
            res = op_open(args.template_id, params, Path(args.project_root).resolve(), args.cycle_id)
        elif args.op == "advance":
            user_input = json.loads(args.user_input) if args.user_input else None
            res = op_advance(args.cycle_id, Path(args.project_root).resolve(), user_input)
        elif args.op == "status":
            res = op_status(args.cycle_id, Path(args.project_root).resolve(), args.format)
        elif args.op == "pause":
            res = op_pause(args.cycle_id, Path(args.project_root).resolve(), args.reason)
        elif args.op == "resume":
            res = op_resume(args.cycle_id, Path(args.project_root).resolve(), args.reason)
        elif args.op == "cancel":
            res = op_cancel(args.cycle_id, Path(args.project_root).resolve(), args.reason)
        elif args.op == "replay":
            # Delegate to bin/cycle_replay.py for human-readable timeline
            replay_script = PLUGIN_ROOT / "bin" / "cycle_replay.py"
            if not replay_script.is_file():
                res = {"status": "error", "reason": "cycle_replay.py not found; run cycle_runner directly for raw status"}
            else:
                cmd = [sys.executable, str(replay_script), "--cycle-id", args.cycle_id,
                       "--detail", args.detail, "--project-root", args.project_root]
                rc = subprocess.call(cmd)
                return rc
        elif args.op == "validate-template":
            res = op_validate_template_cli(Path(args.path))
        else:
            return 2
    except FileNotFoundError as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"status": "error", "reason": repr(exc)}), file=sys.stderr)
        return 3

    print(json.dumps(res, ensure_ascii=False, indent=2))
    status = res.get("status")
    if status in ("ok", "valid"):
        return 0
    if status in ("blocked", "noop"):
        return 1
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
