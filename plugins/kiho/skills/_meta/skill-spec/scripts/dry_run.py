#!/usr/bin/env python3
"""
dry_run.py — typed-parameter resolver + tree-diff previewer for skill authoring.

Reads a YAML skill_spec block from a file or literal, validates against the
strict schema documented in skill-spec/references/parameter-schema.md, and
emits a tree-diff preview of every artifact the run would produce. No file
writes. Used as Step 1 of the skill-factory pipeline (bin/skill_factory.py).

Validation rules (enforced strictly, no extras allowed):
- name: kebab-case, <= 64 chars, lowercase, no "anthropic" or "claude"
- parent_domain: one of the canonical domain paths
- capability: one of the closed 8-verb set (capability-taxonomy.md)
- topic_tags: each in topic-vocabulary.md
- description_seed: 200 <= len <= 1024 chars
- parity_layout: one of {standard, meta-with-scripts, meta-with-refs,
  meta-with-both, parity-exception}
- parity_exception: required iff parity_layout == parity-exception
- on_failure: jidoka-stop | escalate | rollback (default jidoka-stop)

Exit codes (0/1/2/3 per v5.15.2 Pattern 9):
    0 — success (spec valid; tree-diff emitted)
    1 — policy violation (schema/capability/vocab/parity/name/length)
    2 — usage error (missing args, unreadable input)
    3 — internal error (unexpected exception during validation)

Usage:
    dry_run.py --spec <yaml-file>
    dry_run.py --spec - < input.yaml      # stdin
    dry_run.py --spec '<inline-yaml>'

Grounding: v5.17 research findings §"7 missing pieces #1" — Backstage
parameters + dry-run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[4]

CAPABILITY_TAXONOMY_PATH = PLUGIN_ROOT / "references" / "capability-taxonomy.md"
TOPIC_VOCAB_PATH = PLUGIN_ROOT / "references" / "topic-vocabulary.md"
SKILLS_ROOT = PLUGIN_ROOT / "skills"

VALID_PARENT_DOMAINS = {
    "_meta",
    "core/harness",
    "core/hr",
    "core/inspection",
    "core/knowledge",
    "core/planning",
    "kb",
    "memory",
    "engineering",
}

VALID_PARITY_LAYOUTS = {
    "standard",
    "meta-with-scripts",
    "meta-with-refs",
    "meta-with-both",
    "parity-exception",
}

VALID_ON_FAILURE = {"jidoka-stop", "escalate", "rollback"}

REQUIRED_KEYS = {
    "name",
    "parent_domain",
    "capability",
    "topic_tags",
    "description_seed",
    "scripts_required",
    "references_required",
    "parity_layout",
}

OPTIONAL_KEYS = {"parity_exception", "batch_id", "on_failure"}

ALL_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS


def parse_yaml_loose(text: str) -> dict[str, Any]:
    """Tiny YAML subset parser: top-level keys + nested skill_spec block.

    Handles strings, lists, ints. Avoids PyYAML dependency (kiho stdlib-only).
    """
    result: dict[str, Any] = {}
    current: dict[str, Any] = result
    parents: list[dict[str, Any]] = [result]
    indents: list[int] = [-1]

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        # Pop back to correct depth
        while indents and indent <= indents[-1]:
            indents.pop()
            parents.pop()
        current = parents[-1]
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if not value:
            current[key] = {}
            parents.append(current[key])
            indents.append(indent)
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            current[key] = [
                item.strip().strip("\"'")
                for item in inner.split(",")
                if item.strip()
            ]
        elif value.isdigit():
            current[key] = int(value)
        else:
            current[key] = value.strip("\"'")

    return result


def load_capability_taxonomy() -> set[str]:
    if not CAPABILITY_TAXONOMY_PATH.exists():
        return {"create", "read", "update", "delete", "evaluate", "orchestrate", "communicate", "decide"}
    text = CAPABILITY_TAXONOMY_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"^###\s+`(\w+)`", text, re.M))


def load_topic_vocabulary() -> set[str]:
    if not TOPIC_VOCAB_PATH.exists():
        return set()
    text = TOPIC_VOCAB_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"^###\s+`([\w-]+)`", text, re.M))


def closest(target: str, candidates: set[str]) -> str:
    """Crude Levenshtein-free suggestion: prefix or substring match."""
    target = target.lower()
    for c in candidates:
        if c.startswith(target) or target.startswith(c):
            return c
    for c in candidates:
        if target in c or c in target:
            return c
    return next(iter(candidates), "")


def validate_spec(spec: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Return (status, message, errors[])."""
    errors: list[str] = []

    # Schema completeness
    extra = set(spec.keys()) - ALL_KEYS
    if extra:
        return ("schema_violation", f"unknown keys: {sorted(extra)}", [f"unknown_key: {k}" for k in extra])
    missing = REQUIRED_KEYS - set(spec.keys())
    if missing:
        return ("schema_violation", f"missing required keys: {sorted(missing)}", [f"missing_key: {k}" for k in missing])

    # Name
    name = spec["name"]
    if not isinstance(name, str) or not re.match(r"^[a-z][a-z0-9-]{1,63}$", name):
        return ("schema_violation", f"invalid name '{name}' (kebab-case, lowercase, <= 64)", ["name_format"])
    if "anthropic" in name or "claude" in name:
        return ("schema_violation", "name MUST NOT contain 'anthropic' or 'claude'", ["name_reserved"])

    # Parent domain
    if spec["parent_domain"] not in VALID_PARENT_DOMAINS:
        return ("schema_violation", f"parent_domain '{spec['parent_domain']}' not in {sorted(VALID_PARENT_DOMAINS)}", ["parent_domain_invalid"])

    # Capability
    caps = load_capability_taxonomy()
    if spec["capability"] not in caps:
        return (
            "capability_invalid",
            f"capability '{spec['capability']}' not in closed set; closest: {closest(spec['capability'], caps)}",
            ["capability_invalid"],
        )

    # Topic tags
    tags = load_topic_vocabulary()
    if tags:
        for t in spec["topic_tags"]:
            if t not in tags:
                return (
                    "topic_vocab_violation",
                    f"topic_tag '{t}' not in controlled vocabulary; closest: {closest(t, tags)}",
                    [f"topic_tag_invalid: {t}"],
                )

    # Description seed length
    seed = spec["description_seed"]
    if not isinstance(seed, str) or not (200 <= len(seed) <= 1024):
        return (
            "description_seed_length",
            f"description_seed length {len(seed) if isinstance(seed, str) else 0} out of bounds [200, 1024]",
            ["description_seed_length"],
        )

    # Parity layout
    layout = spec["parity_layout"]
    if layout not in VALID_PARITY_LAYOUTS:
        return ("parity_violation", f"parity_layout '{layout}' invalid", ["parity_layout_invalid"])
    if layout == "parity-exception" and not spec.get("parity_exception"):
        return (
            "parity_violation",
            "parity_layout=parity-exception requires parity_exception: <one-line rationale>",
            ["parity_exception_missing"],
        )

    # Name collision
    if SKILLS_ROOT.exists():
        for skill_md in SKILLS_ROOT.rglob("SKILL.md"):
            try:
                fm_match = re.search(r"^name:\s*(\S+)", skill_md.read_text(encoding="utf-8"), re.M)
                if fm_match and fm_match.group(1) == name:
                    return (
                        "name_collision",
                        f"skill '{name}' already exists at {skill_md.relative_to(PLUGIN_ROOT)}; use skill-improve instead",
                        [f"name_collision: {skill_md.relative_to(PLUGIN_ROOT)}"],
                    )
            except (OSError, UnicodeDecodeError):
                continue

    # on_failure
    if spec.get("on_failure", "jidoka-stop") not in VALID_ON_FAILURE:
        return ("schema_violation", f"on_failure '{spec.get('on_failure')}' invalid", ["on_failure_invalid"])

    return ("ok", "spec valid", [])


def render_tree_diff(spec: dict[str, Any]) -> str:
    skill_path = f"skills/{spec['parent_domain']}/{spec['name']}/"
    lines = [f"NEW {skill_path}", "├── SKILL.md                    (target: 7/7 patterns)"]
    if spec.get("scripts_required"):
        lines.append("├── scripts/")
        for s in spec["scripts_required"]:
            lines.append(f"│   └── {s:24s} (0/1/2/3 exit codes)")
    if spec.get("references_required"):
        lines.append("├── references/")
        for r in spec["references_required"]:
            lines.append(f"│   └── {r:24s} (≥6/9 patterns target)")
    return "\n".join(lines)


def render_catalog_impact(spec: dict[str, Any]) -> str:
    return (
        f"+ sk-NNN | {spec['name']} | {spec['parent_domain']}/{spec['name']}/\n"
        f"  Routing block: parent_of: [..., sk-NNN] under `{spec['parent_domain'].split('/')[0]}`"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else "")
    ap.add_argument("--spec", required=True, help="path to YAML file, '-' for stdin, or inline YAML")
    args = ap.parse_args()

    try:
        if args.spec == "-":
            text = sys.stdin.read()
        elif Path(args.spec).is_file():
            text = Path(args.spec).read_text(encoding="utf-8")
        else:
            text = args.spec

        parsed = parse_yaml_loose(text)
        if "skill_spec" in parsed:
            spec = parsed["skill_spec"]
        else:
            spec = parsed

        status, message, errors = validate_spec(spec)

        result: dict[str, Any] = {
            "status": status,
            "dry_run": True,
            "spec_resolved": spec if status == "ok" else None,
            "tree_diff": render_tree_diff(spec) if status == "ok" else None,
            "catalog_impact": render_catalog_impact(spec) if status == "ok" else None,
            "errors": errors,
            "warnings": [],
        }
        if status != "ok":
            result["message"] = message

        print(json.dumps(result, indent=2))
        return 0 if status == "ok" else 1

    except SystemExit:
        raise
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
