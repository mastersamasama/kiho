#!/usr/bin/env python3
"""
kiho_frontmatter.py — canonical frontmatter schema + helpers (v5.20).

Single shared library for every kiho artifact that carries YAML frontmatter
(KB wiki articles, agent memory, experience-pool rows, committee decisions,
skill definitions, batch reports, evolution history, receipts, incidents,
retrospectives, etc.). Before v5.20, KB / memory / experience-pool each
rolled their own frontmatter parser with overlapping-but-divergent fields.
This helper unifies the required keys and lets each kind add optional ones.

Design:
    * stdlib-only YAML subset parser (same approach as skill_catalog_index.py)
      — kiho refuses to add PyYAML as a runtime dep. The subset supports
      scalars, lists, and shallow mappings; deeper nesting must be encoded
      as a TOML sidecar or JSONL payload, not frontmatter.
    * forward-compatible: unknown keys are preserved on round-trip.
    * kind-aware validation via KIND_SCHEMAS; per-kind required fields.

Canonical schema (every frontmatter carries these):
    id             stable slug or uuid for the row
    kind           one of KIND_SCHEMAS keys
    created_at     ISO-8601 UTC
    updated_at     ISO-8601 UTC
    owner          agent slug or "ceo" or "kiho"
    scope          session | project | company
    tier           md | jsonl | sqlite  (resolved tier for this record)

Optional but standardized:
    tags           [topic/* entries from topic-vocabulary.md]
    links          [{rel, ref}]  — ref may be a storage-broker Ref dict
    confidence     float 0..1
    ttl            ISO-8601 UTC or null
    supersedes     prior id or null
    source         {skill, run_id, turn}

Usage:
    from bin.kiho_frontmatter import read, write, validate, merge_defaults
    meta, body = read(path)
    errors = validate(meta, kind="kb-article")
    if not errors:
        meta = merge_defaults("kb-article", meta)
        write(path, meta, body)

Exit codes (when used as CLI `kiho_frontmatter.py validate <path> ...`):
    0 — all files pass validation
    1 — one or more files fail
    2 — usage error
    3 — internal error

Grounding:
    * references/storage-architecture.md (three-tier invariants)
    * references/data-storage-matrix.md (per-data-class rows)
    * references/react-storage-doctrine.md (agent-side decision tree)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path
from typing import Any

FRONTMATTER_DELIM = "---"

# --- canonical schema -------------------------------------------------------

REQUIRED_COMMON = ("id", "kind", "created_at", "updated_at", "owner", "scope", "tier")

OPTIONAL_COMMON = (
    "tags",
    "links",
    "confidence",
    "ttl",
    "supersedes",
    "source",
)

VALID_SCOPES = {"session", "project", "company"}
VALID_TIERS = {"md", "jsonl", "sqlite", "mem"}

# Each kind declares extra required fields plus whether the row is
# committee-reviewable. Committee-reviewable rows MUST live at tier="md".
# Attempting to write a reviewable kind to jsonl/sqlite is rejected by
# validate() — this is the main guard the storage-broker relies on.
KIND_SCHEMAS: dict[str, dict[str, Any]] = {
    # Tier-1 committee-reviewable kinds
    "soul":            {"required": ("author_agent",), "reviewable": True},
    "skill-md":        {"required": ("capability", "topic_tags"), "reviewable": True},
    "kb-article":      {"required": ("page_type", "title"), "reviewable": True},
    "decision":        {"required": ("decider", "reversibility"), "reviewable": True},
    "brief":           {"required": ("from_agent", "to_agent"), "reviewable": True},
    "announcement":    {"required": ("subject",), "reviewable": True},
    "incident":        {"required": ("severity", "trigger_event"), "reviewable": True},
    "postmortem":      {"required": ("incident_id", "root_cause"), "reviewable": True},
    "retrospective":   {"required": ("turn_id",), "reviewable": True},
    "values-flag":     {"required": ("agent_id", "soul_clause_ref"), "reviewable": True},
    "committee-transcript": {"required": ("committee_id", "topic"), "reviewable": True},
    # Tier-2 processing / telemetry kinds
    "memo":            {"required": ("from_agent", "to_agent", "severity"), "reviewable": False},
    "receipt":         {"required": ("brief_id", "agent_id", "accept"), "reviewable": False},
    "standup":         {"required": ("agent_id", "iteration_id"), "reviewable": False},
    "one-on-one":      {"required": ("lead_id", "ic_id"), "reviewable": False},
    "memory":          {"required": ("entry_kind",), "reviewable": False},
    "experience":      {"required": ("entry_kind",), "reviewable": False},
    "evolution":       {"required": ("skill_id", "action"), "reviewable": False},
    "batch-report":    {"required": ("batch_id",), "reviewable": False},
    "integration":     {"required": ("integration_id", "type"), "reviewable": False},
    "feedback-request": {"required": ("turn_id",), "reviewable": False},
    "feedback-response": {"required": ("turn_id",), "reviewable": False},
    "learning-queue":  {"required": ("topic",), "reviewable": False},
    "progression":     {"required": ("agent_id", "action"), "reviewable": False},
    # research-cache is committee-reviewable (cited in committee decisions)
    # but authored by research skill, not kb-manager; md tier enforced.
    "research-cache":  {"required": ("query", "cascade_step_used"), "reviewable": True},
    # Generic fallback — use sparingly; validate() will warn.
    "generic":         {"required": (), "reviewable": False},
}


# --- stdlib YAML subset parser ---------------------------------------------

_LIST_SCALAR = re.compile(r"^\s*-\s+(.*)$")
_MAP_PAIR = re.compile(r"^([A-Za-z_][\w\-]*)\s*:\s*(.*)$")


def _coerce(v: str) -> Any:
    s = v.strip()
    if s == "" or s == "null" or s == "~":
        return None
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    if s.startswith(("'", '"')) and s.endswith(s[0]) and len(s) >= 2:
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_coerce(x) for x in _split_top_level(inner)]
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1].strip()
        if not inner:
            return {}
        out: dict[str, Any] = {}
        for part in _split_top_level(inner):
            if ":" in part:
                k, vv = part.split(":", 1)
                out[k.strip()] = _coerce(vv)
        return out
    # number?
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def _split_top_level(s: str) -> list[str]:
    out: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in s:
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf).strip())
    return out


def _parse_yaml_subset(text: str) -> dict[str, Any]:
    """Parse the stdlib YAML subset we permit in frontmatter. Does not
    support deep nesting or multiline strings; emit TOML sidecars for those.
    """
    out: dict[str, Any] = {}
    current_list: list[Any] | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m_list = _LIST_SCALAR.match(raw)
        if m_list and current_list is not None:
            current_list.append(_coerce(m_list.group(1)))
            continue
        m = _MAP_PAIR.match(raw)
        if m:
            key = m.group(1)
            rhs = m.group(2)
            if rhs == "":
                current_list = []
                out[key] = current_list
            else:
                out[key] = _coerce(rhs)
                current_list = None
    return out


def _emit_yaml_subset(meta: dict[str, Any]) -> str:
    """Round-trip the subset. Preserves key order of the input dict."""
    lines: list[str] = []
    for k, v in meta.items():
        if v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            elif all(isinstance(x, (str, int, float, bool)) or x is None for x in v):
                lines.append(f"{k}: [{', '.join(_emit_scalar(x) for x in v)}]")
            else:
                lines.append(f"{k}:")
                for item in v:
                    if isinstance(item, dict):
                        parts = [f"{kk}: {_emit_scalar(vv)}" for kk, vv in item.items()]
                        lines.append(f"  - {{{', '.join(parts)}}}")
                    else:
                        lines.append(f"  - {_emit_scalar(item)}")
        elif isinstance(v, dict):
            parts = [f"{kk}: {_emit_scalar(vv)}" for kk, vv in v.items()]
            lines.append(f"{k}: {{{', '.join(parts)}}}")
        else:
            lines.append(f"{k}: {_emit_scalar(v)}")
    return "\n".join(lines)


def _emit_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        if any(c in v for c in ",:[]{}#") or not v:
            return '"' + v.replace('"', '\\"') + '"'
        return v
    return str(v)


# --- public API -------------------------------------------------------------


def read(path: Path | str) -> tuple[dict[str, Any], str]:
    """Read a markdown file with YAML frontmatter. Returns (meta, body).
    If the file has no frontmatter, returns ({}, full_text)."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if not text.startswith(FRONTMATTER_DELIM + "\n") and not text.startswith(FRONTMATTER_DELIM + "\r\n"):
        return {}, text
    rest = text.split("\n", 1)[1]
    end = rest.find("\n" + FRONTMATTER_DELIM)
    if end < 0:
        return {}, text
    fm_block = rest[:end]
    body = rest[end + len("\n" + FRONTMATTER_DELIM):]
    if body.startswith("\n"):
        body = body[1:]
    return _parse_yaml_subset(fm_block), body


def write(path: Path | str, meta: dict[str, Any], body: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fm_text = _emit_yaml_subset(meta)
    p.write_text(
        FRONTMATTER_DELIM + "\n" + fm_text + "\n" + FRONTMATTER_DELIM + "\n" + body,
        encoding="utf-8",
    )


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def merge_defaults(kind: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Fill in missing canonical fields with safe defaults. Never overwrites
    existing keys. Never invents an `id` — caller must provide one."""
    out = dict(meta)
    out.setdefault("kind", kind)
    now = now_iso()
    out.setdefault("created_at", now)
    out["updated_at"] = now  # always refresh on write
    out.setdefault("owner", "kiho")
    out.setdefault("scope", "project")
    out.setdefault("tier", "md")
    return out


def validate(meta: dict[str, Any], kind: str | None = None) -> list[str]:
    """Return a list of error strings. Empty list means valid."""
    errors: list[str] = []
    k = kind or meta.get("kind")
    if not k:
        errors.append("missing required key: kind")
        return errors
    if k not in KIND_SCHEMAS:
        errors.append(f"unknown kind: {k!r} (add to KIND_SCHEMAS first)")
        return errors
    for key in REQUIRED_COMMON:
        if key not in meta or meta[key] in (None, ""):
            errors.append(f"missing required key: {key}")
    if meta.get("scope") not in VALID_SCOPES and "scope" in meta:
        errors.append(f"invalid scope: {meta.get('scope')!r} (expected one of {sorted(VALID_SCOPES)})")
    if meta.get("tier") not in VALID_TIERS and "tier" in meta:
        errors.append(f"invalid tier: {meta.get('tier')!r} (expected one of {sorted(VALID_TIERS)})")
    for key in KIND_SCHEMAS[k]["required"]:
        if key not in meta or meta[key] in (None, ""):
            errors.append(f"missing required key for kind={k}: {key}")
    # Reviewable-kind guardrail — enforced here so storage-broker
    # can rely on it without re-checking.
    if KIND_SCHEMAS[k]["reviewable"] and meta.get("tier") not in (None, "md"):
        errors.append(
            f"kind={k} is committee-reviewable; tier must be 'md' but got {meta.get('tier')!r}"
        )
    return errors


def jsonl_row(kind: str, meta: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Construct a canonical JSONL row: canonical meta fields + inline payload.
    Callers should json.dumps this dict with ensure_ascii=False, sort_keys=False
    and append a newline. Used by memo-send, standup-log, evolution-history,
    experience-pool, etc."""
    row: dict[str, Any] = {key: meta[key] for key in REQUIRED_COMMON if key in meta}
    for key in OPTIONAL_COMMON:
        if key in meta:
            row[key] = meta[key]
    for key in KIND_SCHEMAS.get(kind, {}).get("required", ()):
        if key in meta:
            row[key] = meta[key]
    if payload:
        row["payload"] = payload
    return row


# --- CLI -------------------------------------------------------------------


def _cmd_validate(args: argparse.Namespace) -> int:
    any_error = False
    for target in args.paths:
        p = Path(target)
        if not p.exists():
            print(f"{p}: not found", file=sys.stderr)
            any_error = True
            continue
        if p.is_dir():
            files = list(p.rglob("*.md"))
        else:
            files = [p]
        for f in files:
            try:
                meta, _ = read(f)
            except Exception as exc:  # pragma: no cover
                print(f"{f}: parse error: {exc}", file=sys.stderr)
                any_error = True
                continue
            if not meta:
                if args.require_frontmatter:
                    print(f"{f}: missing frontmatter")
                    any_error = True
                continue
            errs = validate(meta, kind=meta.get("kind"))
            if errs:
                for e in errs:
                    print(f"{f}: {e}")
                any_error = True
    return 1 if any_error else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kiho_frontmatter", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate frontmatter across files/dirs")
    v.add_argument("paths", nargs="+", help="files or directories to scan")
    v.add_argument("--require-frontmatter", action="store_true",
                   help="error when a .md file has no frontmatter at all")
    v.set_defaults(func=_cmd_validate)
    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # pragma: no cover
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
