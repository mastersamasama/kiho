#!/usr/bin/env python3
"""
yaml_to_toml.py — narrow-schema YAML→TOML converter (v5.19 Tier-C).

Converts a YAML file matching the narrow kiho config schema
(scalar keys + one level of nested mappings + simple lists +
inline comments) into idiomatic TOML. Stdlib-only; does NOT
depend on PyYAML, tomllib (3.11+), or tomli_w.

Scope (the "narrow schema" this converter supports):

    # comment                       →  # comment
    key: value                      →  key = <typed-literal>
    key: "quoted"                   →  key = "quoted"
    key:                            →  [key]
      subkey: value                 →  subkey = <typed-literal>
    key: [a, b, c]                  →  key = [a, b, c]
    key:
      - a                           →  key = ["a", "b"]
      - b

Unsupported (the converter exits 1 on any of these):

    * Multi-document streams (`---` after frontmatter)
    * Anchors / aliases (`&name`, `*name`)
    * Multi-line string blocks (`|`, `>`)
    * Nested maps deeper than 2 levels
    * Mixed list-of-maps at top level
    * Merge keys (`<<:`)

Known limitation — comment placement:

    TOML requires all top-level scalars / arrays to appear BEFORE any
    `[table]` header (TOML spec §"Table"). YAML has no such constraint,
    so a file that interleaves scalar sections and nested-map sections
    will have its `[table]` blocks deferred to the tail on emit. Any
    section-header comment (e.g., `# ---- Section Title ----`) preceding
    a nested map will stay at its source position while its content moves.
    The converter does NOT attempt to re-associate orphaned comment blocks.
    Convention after running: review the output and hand-touch comment
    placement once. The converter's job is structural correctness; comment
    cosmetics are a second-pass concern.

This intentional narrowness follows YAGNI: kiho's in-scope
MIGRATING configs (config.yaml [done v5.19.3], canonical-rubric [done v5.19.5
via hand-rewrite — multi-level nesting exceeded the narrow schema],
soul-overrides) fit (or fell just outside) the narrow schema. Anything
outside scope gets a loud exit 1 rather than a subtly-wrong conversion.

Usage:
    yaml_to_toml.py convert --in <path.yaml> [--out <path.toml>]
                            [--in-place] [--dry-run]

    --in <path>       source YAML file (required)
    --out <path>      destination TOML file; default: <in>.toml
    --in-place        write <in>.toml then delete <in> (use after review)
    --dry-run         print TOML to stdout, write nothing

Exit codes (v5.15.2 convention):
    0 — conversion succeeded (or dry-run OK)
    1 — input uses unsupported YAML features (narrow-schema violation)
    2 — usage error (missing file, bad flags)
    3 — internal error (unexpected exception)

Grounding:
    * references/storage-tech-stack.md §1 (typed config → TOML)
    * references/data-storage-matrix.md §2 (MIGRATING rows)
    * skills/_meta/skill-improve — invokes this as the migration hook
      when touching a MIGRATING class file with a frontmatter-only diff
    * YAGNI: no full YAML parser; no full TOML emitter.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# --- narrow YAML parse ------------------------------------------------------

# Line classifications:
#   blank       — whitespace only
#   comment     — "# ..."
#   key-scalar  — "key: <value>" at top-level indent
#   key-list    — "key: [a, b]" inline list
#   key-open    — "key:" (opens a dict block or a list block)
#   list-item   — "- <value>" at indent > 0

_BLANK_RE = re.compile(r"^\s*$")
_COMMENT_RE = re.compile(r"^(\s*)#(.*)$")
_KEY_SCALAR_RE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):\s*(.+?)\s*(#.*)?$")
_KEY_INLINE_LIST_RE = re.compile(
    r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):\s*\[(.*?)\]\s*(#.*)?$"
)
_KEY_OPEN_RE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):\s*(#.*)?$")
_LIST_ITEM_RE = re.compile(r"^(\s*)-\s+(.+?)\s*(#.*)?$")


class NarrowYamlError(ValueError):
    """Raised when the input uses a YAML feature outside the narrow schema."""


def _indent_of(line: str) -> int:
    i = 0
    while i < len(line) and line[i] == " ":
        i += 1
    return i


def _strip_inline_quotes(s: str) -> tuple[str, bool]:
    """Return (unquoted, was_quoted). Handles both single and double quotes."""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1], True
    return s, False


def _parse_scalar(value: str) -> Any:
    """Turn a YAML scalar literal into a Python value."""
    raw, quoted = _strip_inline_quotes(value)
    if quoted:
        return raw
    if raw == "" or raw.lower() == "null" or raw == "~":
        return None
    if raw.lower() in ("true", "yes"):
        return True
    if raw.lower() in ("false", "no"):
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw  # bare string


def _parse_inline_list(body: str) -> list[Any]:
    if not body.strip():
        return []
    parts = [p.strip() for p in body.split(",")]
    return [_parse_scalar(p) for p in parts]


# --- AST ---

# The converter preserves comment + blank lines, so we keep an ordered
# list of nodes rather than a pure dict. Each node is a dataclass-like
# dict:
#   {"kind": "comment", "text": "..."}
#   {"kind": "blank"}
#   {"kind": "scalar", "key": "name", "value": <py>, "trailing": "# ..."}
#   {"kind": "list",   "key": "name", "items": [<py>, ...], "trailing": "..."}
#   {"kind": "table",  "key": "name", "children": [<nodes>]}


def parse_narrow_yaml(text: str) -> list[dict]:
    lines = text.splitlines()
    nodes: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if _BLANK_RE.match(line):
            nodes.append({"kind": "blank"})
            i += 1
            continue

        cm = _COMMENT_RE.match(line)
        if cm:
            nodes.append({"kind": "comment", "text": cm.group(2)})
            i += 1
            continue

        indent = _indent_of(line)
        if indent != 0:
            raise NarrowYamlError(
                f"line {i + 1}: unexpected indent on top-level line; "
                "narrow schema requires top-level keys at column 0"
            )

        # Inline list
        lm = _KEY_INLINE_LIST_RE.match(line)
        if lm:
            key = lm.group(2)
            items = _parse_inline_list(lm.group(3))
            trailing = (lm.group(4) or "").strip()
            nodes.append({
                "kind": "list",
                "key": key,
                "items": items,
                "trailing": trailing,
            })
            i += 1
            continue

        # Key with inline scalar
        sm = _KEY_SCALAR_RE.match(line)
        if sm and not _KEY_OPEN_RE.fullmatch(line):
            key = sm.group(2)
            value = _parse_scalar(sm.group(3))
            trailing = (sm.group(4) or "").strip()
            nodes.append({
                "kind": "scalar",
                "key": key,
                "value": value,
                "trailing": trailing,
            })
            i += 1
            continue

        # Key-open: either a block list (`- item`) or a nested map
        om = _KEY_OPEN_RE.match(line)
        if om:
            key = om.group(2)
            trailing = (om.group(3) or "").strip()
            # Look ahead at next non-blank/non-comment line
            j = i + 1
            saw_list = False
            saw_map = False
            while j < len(lines):
                nxt = lines[j]
                if _BLANK_RE.match(nxt) or _COMMENT_RE.match(nxt):
                    j += 1
                    continue
                if _LIST_ITEM_RE.match(nxt):
                    saw_list = True
                elif _KEY_SCALAR_RE.match(nxt) or _KEY_OPEN_RE.match(nxt):
                    saw_map = True
                break

            if not saw_list and not saw_map:
                # Empty block — treat as empty string scalar
                nodes.append({
                    "kind": "scalar",
                    "key": key,
                    "value": "",
                    "trailing": trailing,
                })
                i += 1
                continue

            if saw_list:
                items: list[Any] = []
                j = i + 1
                while j < len(lines):
                    nxt = lines[j]
                    if _BLANK_RE.match(nxt) or _COMMENT_RE.match(nxt):
                        j += 1
                        continue
                    lim = _LIST_ITEM_RE.match(nxt)
                    if lim and _indent_of(nxt) > 0:
                        items.append(_parse_scalar(lim.group(2)))
                        j += 1
                        continue
                    break
                nodes.append({
                    "kind": "list",
                    "key": key,
                    "items": items,
                    "trailing": trailing,
                })
                i = j
                continue

            # Nested map (one level deep)
            children: list[dict] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if _BLANK_RE.match(nxt):
                    children.append({"kind": "blank"})
                    j += 1
                    continue
                cm2 = _COMMENT_RE.match(nxt)
                if cm2:
                    children.append({"kind": "comment", "text": cm2.group(2)})
                    j += 1
                    continue
                nxt_indent = _indent_of(nxt)
                if nxt_indent == 0:
                    break
                # At this point we're inside the nested map. Only inline
                # scalars are supported at this depth (1-level nest only).
                child_sm = _KEY_SCALAR_RE.match(nxt)
                if not child_sm:
                    child_om = _KEY_OPEN_RE.match(nxt)
                    if child_om:
                        raise NarrowYamlError(
                            f"line {j + 1}: narrow schema supports only "
                            f"one level of nesting; found nested map under "
                            f"'{key}'"
                        )
                    raise NarrowYamlError(
                        f"line {j + 1}: unrecognized line under nested "
                        f"map '{key}'"
                    )
                child_key = child_sm.group(2)
                child_value = _parse_scalar(child_sm.group(3))
                child_trailing = (child_sm.group(4) or "").strip()
                children.append({
                    "kind": "scalar",
                    "key": child_key,
                    "value": child_value,
                    "trailing": child_trailing,
                })
                j += 1

            nodes.append({
                "kind": "table",
                "key": key,
                "children": children,
                "trailing": trailing,
            })
            i = j
            continue

        raise NarrowYamlError(
            f"line {i + 1}: cannot classify line: {line!r}"
        )

    return nodes


# --- narrow TOML emit -------------------------------------------------------

def _emit_scalar(value: Any) -> str:
    if value is None:
        # TOML has no explicit null; represent as empty string key for safety.
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        # TOML basic string: double-quoted with limited escapes.
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'
    raise NarrowYamlError(f"cannot emit scalar of type {type(value).__name__}")


def _emit_list(items: list[Any]) -> str:
    if not items:
        return "[]"
    parts = [_emit_scalar(x) for x in items]
    return "[" + ", ".join(parts) + "]"


def emit_toml(nodes: list[dict]) -> str:
    """Render AST to TOML text. Comments / blanks preserved in order.

    Nested tables become `[key]` headers. All scalar + list rows belong
    to the table header most recently opened above them (or the
    top-level if no header has been opened).
    """
    lines: list[str] = []
    # First pass: emit top-level scalars and lists in order, deferring
    # tables to the end (TOML requires that top-level bare keys appear
    # BEFORE the first `[table]` header).
    deferred_tables: list[dict] = []
    for node in nodes:
        if node["kind"] == "table":
            deferred_tables.append(node)
            continue
        if node["kind"] == "blank":
            lines.append("")
            continue
        if node["kind"] == "comment":
            lines.append("#" + node["text"])
            continue
        if node["kind"] == "scalar":
            line = f"{node['key']} = {_emit_scalar(node['value'])}"
            if node.get("trailing"):
                line += "  " + node["trailing"]
            lines.append(line)
            continue
        if node["kind"] == "list":
            line = f"{node['key']} = {_emit_list(node['items'])}"
            if node.get("trailing"):
                line += "  " + node["trailing"]
            lines.append(line)
            continue
        raise NarrowYamlError(f"unknown node kind: {node['kind']}")

    # Deferred tables at the tail.
    for tbl in deferred_tables:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(f"[{tbl['key']}]")
        if tbl.get("trailing"):
            lines[-1] += "  " + tbl["trailing"]
        for child in tbl["children"]:
            if child["kind"] == "blank":
                lines.append("")
                continue
            if child["kind"] == "comment":
                lines.append("#" + child["text"])
                continue
            if child["kind"] == "scalar":
                line = f"{child['key']} = {_emit_scalar(child['value'])}"
                if child.get("trailing"):
                    line += "  " + child["trailing"]
                lines.append(line)
                continue
            raise NarrowYamlError(
                f"unsupported child in table '{tbl['key']}': {child['kind']}"
            )

    return "\n".join(lines) + "\n"


# --- CLI --------------------------------------------------------------------

def convert_file(
    src: Path,
    dst: Path | None,
    *,
    dry_run: bool,
    in_place: bool,
) -> tuple[str, Path]:
    """Run the full pipeline. Returns (toml_text, dst_path_used)."""
    text = src.read_text(encoding="utf-8")
    nodes = parse_narrow_yaml(text)
    toml_text = emit_toml(nodes)

    out_path = dst if dst is not None else src.with_suffix(".toml")
    if not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(toml_text, encoding="utf-8")
        if in_place and src.resolve() != out_path.resolve():
            src.unlink()
    return toml_text, out_path


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Convert a narrow-schema YAML file to idiomatic TOML. "
            "See module docstring for the supported subset."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("convert", help="Convert one YAML file to TOML")
    c.add_argument("--in", dest="src", required=True)
    c.add_argument("--out", dest="dst", default=None)
    c.add_argument("--in-place", action="store_true",
                   help="After writing <out>, delete the source YAML.")
    c.add_argument("--dry-run", action="store_true",
                   help="Print TOML to stdout; write nothing.")

    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    if args.cmd != "convert":
        print(
            json.dumps({"status": "error", "error": "unknown subcommand"}),
            file=sys.stderr,
        )
        return 2

    src = Path(args.src).resolve()
    if not src.is_file():
        print(
            json.dumps({
                "status": "error",
                "error": f"source not a file: {src}",
            }),
            file=sys.stderr,
        )
        return 2

    dst = Path(args.dst).resolve() if args.dst else None

    try:
        toml_text, out_path = convert_file(
            src,
            dst,
            dry_run=args.dry_run,
            in_place=args.in_place,
        )
    except NarrowYamlError as exc:
        print(
            json.dumps({
                "status": "unsupported",
                "error": str(exc),
                "source": str(src),
            }),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # pragma: no cover — defensive
        print(
            json.dumps({"status": "error", "error": repr(exc)}),
            file=sys.stderr,
        )
        return 3

    if args.dry_run:
        sys.stdout.write(toml_text)
        return 0

    print(json.dumps({
        "status": "ok",
        "source": str(src),
        "output": str(out_path),
        "bytes": len(toml_text.encode("utf-8")),
        "deleted_source": args.in_place,
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
