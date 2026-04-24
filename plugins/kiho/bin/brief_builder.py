#!/usr/bin/env python3
"""
brief_builder.py — kiho v6 subagent-brief helper.

Every CEO subagent brief gets a "Company output constraints" prefix derived
from $COMPANY_ROOT/settings.md (merged over plugin config). This module owns
the formatting so callers (CEO, committee, recruit, kb-manager) don't
re-implement the merge / formatting each time.

Two entry points:

  1. Python import:
        from brief_builder import build_company_output_constraints, load_settings
        block = build_company_output_constraints(settings)

  2. CLI (Bash-callable from CEO):
        python bin/brief_builder.py build-constraints --settings <path>
        python bin/brief_builder.py build-constraints                 # auto-find
        python bin/brief_builder.py read-language --settings <path>   # just echo value

Output of `build-constraints` is a plain-text markdown block safe to prepend
to a brief. On missing settings or unreadable file: exits 0 with an empty
block (caller preserves v5 no-op behavior).

Exit codes:
  0  — always (errors produce empty output + stderr note)
  2  — invocation error (bad args)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

try:
    import tomllib  # type: ignore
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:  # pragma: no cover
        tomllib = None


# ---------------------------------------------------------------------------
# Settings loading + merge
# ---------------------------------------------------------------------------


def _read_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file. Empty dict on any error."""
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = text[3:end].lstrip("\n")
    if yaml is None:
        return _naive_yaml(fm_text)
    try:
        return yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return {}


def _naive_yaml(text: str) -> dict:
    """Ultra-minimal fallback when PyYAML is absent. Supports top-level
    scalars and a `tone:` sub-block with 2 keys — enough for the constraints
    block. Everything else returns defaults."""
    out: dict = {}
    current_section = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current_section = line[:-1].strip()
            out[current_section] = {}
            continue
        if line.startswith("  ") and current_section:
            k, _, v = line.strip().partition(":")
            val = v.strip().strip('"').strip("'")
            if val.lower() in ("true", "false"):
                val = val.lower() == "true"
            if isinstance(out.get(current_section), dict):
                out[current_section][k.strip()] = val  # type: ignore[index]
            continue
        if ":" in line and not line.startswith(" "):
            current_section = None
            k, _, v = line.partition(":")
            val = v.strip().strip('"').strip("'")
            if val.lower() in ("true", "false"):
                val = val.lower() == "true"
            out[k.strip()] = val
    return out


def _read_plugin_config() -> dict:
    """Read plugin config.toml fallback — best-effort only."""
    here = Path(__file__).resolve()
    config = here.parent.parent / "skills" / "core" / "harness" / "kiho" / "config.toml"
    if not config.is_file() or tomllib is None:
        return {}
    try:
        with open(config, "rb") as fp:
            return tomllib.load(fp)
    except Exception:
        return {}


def load_settings(settings_path: str | None = None) -> dict:
    """Load $COMPANY_ROOT/settings.md frontmatter merged over plugin config.

    Precedence (highest wins):
      1. settings_path or env $COMPANY_ROOT/settings.md
      2. plugin config.toml [tone] fallback
    """
    plugin = _read_plugin_config()
    tone_fallback = plugin.get("tone") or {}
    merged: dict = {
        "official_language": tone_fallback.get("official_language_fallback") or None,
        "tone": {
            "formality": tone_fallback.get("formality_fallback") or None,
            "emoji_in_agent_output": tone_fallback.get(
                "emoji_in_agent_output_fallback", False
            ),
        },
    }

    path: Path | None = None
    if settings_path:
        path = Path(settings_path)
    else:
        cr = os.environ.get("COMPANY_ROOT") or os.environ.get("KIHO_COMPANY_ROOT")
        if cr:
            cand = Path(cr) / "settings.md"
            if cand.is_file():
                path = cand
    if path is None:
        return merged

    fm = _read_frontmatter(path)
    if "official_language" in fm and fm["official_language"]:
        merged["official_language"] = fm["official_language"]
    if "tone" in fm and isinstance(fm["tone"], dict):
        if fm["tone"].get("formality"):
            merged["tone"]["formality"] = fm["tone"]["formality"]
        if "emoji_in_agent_output" in fm["tone"]:
            merged["tone"]["emoji_in_agent_output"] = bool(
                fm["tone"]["emoji_in_agent_output"]
            )
    return merged


# ---------------------------------------------------------------------------
# Constraints block builder (the function specified in the v6 plan §3.7)
# ---------------------------------------------------------------------------


def build_company_output_constraints(settings: dict) -> str:
    """Return the 'Company output constraints' section prefix for subagent briefs.

    When `settings.official_language` is set, appends 'Output language: <value>'.
    When `settings.tone.formality` is set, appends 'Tone: <value>'.
    When `settings.tone.emoji_in_agent_output` is false, appends 'Emoji: forbidden'.

    Returns an empty string if no constraints apply (caller preserves v5 no-op).
    """
    lines: list[str] = []
    lang = settings.get("official_language")
    tone = settings.get("tone") or {}
    formality = tone.get("formality")
    emoji = tone.get("emoji_in_agent_output")

    if lang:
        lines.append(f"- Output language: {lang}")
    if formality:
        lines.append(f"- Tone: {formality}")
    if emoji is False:
        lines.append("- Emoji: forbidden")
    elif emoji is True:
        lines.append("- Emoji: allowed")

    if not lines:
        return ""

    block = [
        "## Company output constraints",
        "",
        "These values are derived from `$COMPANY_ROOT/settings.md` and apply to",
        "every response you produce during this delegation:",
        "",
        *lines,
        "",
        "Respect them unless a hard invariant forbids it (in which case explain).",
        "",
    ]
    return "\n".join(block)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_build_constraints(args: argparse.Namespace) -> int:
    settings = load_settings(args.settings)
    block = build_company_output_constraints(settings)
    sys.stdout.write(block)
    return 0


def _cmd_read_language(args: argparse.Namespace) -> int:
    settings = load_settings(args.settings)
    sys.stdout.write((settings.get("official_language") or "") + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="kiho v6 brief builder helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    bc = sub.add_parser("build-constraints", help="emit Company output constraints block")
    bc.add_argument("--settings", default=None, help="path to $COMPANY_ROOT/settings.md")
    bc.set_defaults(func=_cmd_build_constraints)

    rl = sub.add_parser("read-language", help="emit resolved official_language")
    rl.add_argument("--settings", default=None, help="path to $COMPANY_ROOT/settings.md")
    rl.set_defaults(func=_cmd_read_language)

    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
