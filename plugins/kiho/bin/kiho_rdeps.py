#!/usr/bin/env python3
"""
kiho_rdeps.py — on-demand reverse-dependency scanner (v5.15).

Given a skill target (slug, sk-ID, or SKILL.md path), walks every forward
edge in the kiho tree and reports who depends on it. Forward-edge sources:

1. Hard requires — metadata.kiho.requires: [... target ...] in other skills
2. Soft mentions — metadata.kiho.mentions: [... target ...] in other skills
3. Agent portfolios — skills: [... target ...] in agents/*.md frontmatter
4. Catalog parent_of — parent_of: [... target ...] in CATALOG.md routing block
5. Wiki-link body mentions — [[target]] in SKILL.md body prose
6. KB back-references — target appears in .kiho/kb/wiki/skill-solutions.md
   (best-effort; file is per-project runtime state, may not exist)

Zero on-disk cache. Each invocation walks the tree fresh. Matches the
industry-standard pattern from pnpm why, cargo tree --invert, go mod why,
and bazel rdeps — all compute reverse edges on demand from the forward
graph.

Grounding: kiho v5.15 H5.
- https://pnpm.io/cli/why
- https://doc.rust-lang.org/cargo/commands/cargo-tree.html
- https://bazel.build/query/language
- https://kube.rs/controllers/relations/

Usage:
    kiho_rdeps.py <target>
        [--skills-root skills/]
        [--agents-root agents/]
        [--catalog skills/CATALOG.md]
        [--kb-root .kiho/kb/wiki/]
        [--plugin-root .]

Exit codes:
    0 — target resolves and report written to stdout
    1 — target does not resolve to any known skill
    2 — usage error or required path missing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_catalog_entries(catalog_path: Path) -> list[dict]:
    """Parse the markdown table rows in CATALOG.md. Each row has columns
    | sk-ID | name | path | description |. Return a list of dicts."""
    if not catalog_path.exists():
        return []
    text = catalog_path.read_text(encoding="utf-8")
    rows: list[dict] = []
    # Match rows like: | `sk-013` | **kb-add** | `kb/kb-add/` | desc... |
    pattern = re.compile(
        r"^\|\s*`?(sk-[\w-]+)`?\s*\|\s*\*?\*?([\w-]+)\*?\*?\s*\|\s*`?([^|`]+?)`?\s*\|\s*(.*?)\s*\|\s*$",
        re.MULTILINE,
    )
    for m in pattern.finditer(text):
        rows.append(
            {
                "id": m.group(1).strip(),
                "name": m.group(2).strip(),
                "path": m.group(3).strip().rstrip("/"),
                "description": m.group(4).strip(),
            }
        )
    return rows


def extract_catalog_parent_of(catalog_path: Path) -> dict[str, list[str]]:
    """Extract the routing block's parent_of: [...] lists per domain.
    Returns {domain: [sk-id, ...]}."""
    if not catalog_path.exists():
        return {}
    text = catalog_path.read_text(encoding="utf-8")
    block_m = re.search(r"```yaml\s*\n\s*routing:\s*\n(.*?)\n```", text, re.DOTALL)
    if not block_m:
        return {}
    body = block_m.group(1)
    result: dict[str, list[str]] = {}
    current_domain = ""
    for line in body.splitlines():
        dm = re.match(r"^  (\w[\w_-]*)\s*:\s*$", line)
        if dm:
            current_domain = dm.group(1)
            continue
        pm = re.match(r"^    parent_of\s*:\s*\[(.*?)\]\s*$", line)
        if pm and current_domain:
            items = [i.strip() for i in pm.group(1).split(",") if i.strip()]
            result[current_domain] = items
    return result


def resolve_target(
    target: str,
    skills_root: Path,
    catalog_rows: list[dict],
) -> dict | None:
    """Given a user-supplied target (slug, sk-ID, or path), return a dict
    with canonical `name`, `id` (may be None), and `aliases` (all strings
    we should search for). Returns None if target does not resolve."""
    aliases: set[str] = set()
    name: str | None = None
    sk_id: str | None = None

    # Try CATALOG.md lookup first.
    target_norm = target.strip().strip("/").replace("\\", "/")
    for row in catalog_rows:
        if target == row["id"] or target == row["name"]:
            name = row["name"]
            sk_id = row["id"]
            aliases.update([row["id"], row["name"]])
            break
        if target_norm.endswith(row["path"].replace("\\", "/")):
            name = row["name"]
            sk_id = row["id"]
            aliases.update([row["id"], row["name"]])
            break

    # Fall back: walk skills_root and match against directory names or
    # frontmatter name fields.
    if name is None:
        for skill_md in skills_root.rglob("SKILL.md"):
            dir_name = skill_md.parent.name
            if dir_name == target:
                name = dir_name
                aliases.add(dir_name)
                # Try to extract a name from frontmatter.
                try:
                    text = skill_md.read_text(encoding="utf-8")
                    nm = re.search(r"^name\s*:\s*(.*)$", text, re.MULTILINE)
                    if nm:
                        fmn = nm.group(1).strip().strip('"').strip("'")
                        aliases.add(fmn)
                except OSError:
                    pass
                break
            # Path match.
            try:
                if skill_md.resolve() == Path(target).resolve():
                    name = dir_name
                    aliases.add(dir_name)
                    break
            except OSError:
                continue

    if name is None:
        return None

    return {"name": name, "id": sk_id, "aliases": sorted(aliases)}


def scan_requires_field(
    skills_root: Path,
    aliases: set[str],
    field: str,
) -> list[dict]:
    """Grep every SKILL.md frontmatter for `{field}: [...]` containing any
    of the given aliases. Used for both hard `requires` and soft `mentions`.
    Returns a list of consumer dicts."""
    hits: list[dict] = []
    for skill_md in sorted(skills_root.rglob("SKILL.md")):
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        front_m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not front_m:
            continue
        front = front_m.group(1)
        # Find `<field>: [...]` anywhere in the frontmatter; the metadata
        # block is nested YAML but we only need the inline array form which
        # kiho v5.15 prescribes.
        for fm in re.finditer(
            rf"^\s*{re.escape(field)}\s*:\s*\[(.*?)\]\s*$",
            front,
            re.MULTILINE,
        ):
            items = [
                i.strip().strip('"').strip("'")
                for i in fm.group(1).split(",")
                if i.strip()
            ]
            if any(a in items for a in aliases):
                line_num = front[: fm.start()].count("\n") + 1
                hits.append(
                    {
                        "consumer_dir": skill_md.parent.name,
                        "file": str(skill_md),
                        "line": line_num,
                        "matched_items": [i for i in items if i in aliases],
                    }
                )
    return hits


def scan_agent_portfolios(
    agents_root: Path,
    aliases: set[str],
) -> list[dict]:
    """Scan agents/*.md frontmatter for `skills: [...]` arrays containing
    any of the given aliases."""
    hits: list[dict] = []
    if not agents_root.exists():
        return hits
    for agent_md in sorted(agents_root.glob("*.md")):
        try:
            text = agent_md.read_text(encoding="utf-8")
        except OSError:
            continue
        front_m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not front_m:
            continue
        front = front_m.group(1)
        for sm in re.finditer(
            r"^\s*skills\s*:\s*\[(.*?)\]\s*$", front, re.MULTILINE
        ):
            items = [i.strip() for i in sm.group(1).split(",") if i.strip()]
            matched = [i for i in items if i in aliases]
            if matched:
                line_num = front[: sm.start()].count("\n") + 1
                hits.append(
                    {
                        "agent": agent_md.stem,
                        "file": str(agent_md),
                        "line": line_num,
                        "matched_items": matched,
                    }
                )
    return hits


def scan_catalog_parent_of_refs(
    parent_of: dict[str, list[str]],
    aliases: set[str],
) -> list[dict]:
    hits: list[dict] = []
    for domain, ids in parent_of.items():
        matched = [i for i in ids if i in aliases]
        if matched:
            hits.append({"domain": domain, "matched_items": matched})
    return hits


def scan_body_wikilinks(
    skills_root: Path,
    aliases: set[str],
    target_name: str,
) -> list[dict]:
    """Scan SKILL.md bodies (everything after the second `---`) for
    wiki-style [[name]] links or bare name mentions near prose."""
    hits: list[dict] = []
    patterns = [re.compile(rf"\[\[{re.escape(a)}\]\]") for a in aliases]
    for skill_md in sorted(skills_root.rglob("SKILL.md")):
        if skill_md.parent.name == target_name:
            continue  # don't match a skill's self-references
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        # Skip frontmatter.
        front_end = text.find("\n---", 4)
        body = text[front_end + 4 :] if front_end != -1 else text
        for pat in patterns:
            for m in pat.finditer(body):
                line_num = body[: m.start()].count("\n") + 1
                hits.append(
                    {
                        "consumer_dir": skill_md.parent.name,
                        "file": str(skill_md),
                        "line": line_num,
                        "match": m.group(0),
                    }
                )
    return hits


def scan_kb_backrefs(kb_root: Path, aliases: set[str]) -> list[dict]:
    """Best-effort scan of skill-solutions.md and other kb pages for any
    mention of the aliases. Returns an empty list if kb_root missing."""
    hits: list[dict] = []
    if not kb_root.exists():
        return hits
    for md in sorted(kb_root.rglob("*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        for alias in aliases:
            for m in re.finditer(re.escape(alias), text):
                line_num = text[: m.start()].count("\n") + 1
                hits.append(
                    {
                        "file": str(md),
                        "line": line_num,
                        "match": alias,
                    }
                )
                break  # one hit per alias per file is enough
    return hits


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("target", help="skill slug, sk-ID, or SKILL.md path")
    p.add_argument("--plugin-root", default=".", help="plugin root directory")
    p.add_argument("--skills-root", default=None, help="override skills/ root")
    p.add_argument("--agents-root", default=None, help="override agents/ root")
    p.add_argument("--catalog", default=None, help="override CATALOG.md path")
    p.add_argument(
        "--kb-root",
        default=None,
        help="optional .kiho/kb/wiki/ root for back-ref scan",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    plugin_root = Path(args.plugin_root)
    skills_root = Path(args.skills_root) if args.skills_root else plugin_root / "skills"
    agents_root = Path(args.agents_root) if args.agents_root else plugin_root / "agents"
    catalog_path = Path(args.catalog) if args.catalog else skills_root / "CATALOG.md"
    kb_root = Path(args.kb_root) if args.kb_root else None

    if not skills_root.exists():
        sys.stderr.write(f"skills root not found: {skills_root}\n")
        return 2

    catalog_rows = parse_catalog_entries(catalog_path)
    parent_of = extract_catalog_parent_of(catalog_path)

    resolved = resolve_target(args.target, skills_root, catalog_rows)
    if resolved is None:
        sys.stderr.write(f"target not found: {args.target}\n")
        return 1

    aliases = set(resolved["aliases"])

    hard = scan_requires_field(skills_root, aliases, "requires")
    soft = scan_requires_field(skills_root, aliases, "mentions")
    agents = scan_agent_portfolios(agents_root, aliases)
    catalog = scan_catalog_parent_of_refs(parent_of, aliases)
    wikilinks = scan_body_wikilinks(skills_root, aliases, resolved["name"])
    kb = scan_kb_backrefs(kb_root, aliases) if kb_root else []

    result = {
        "target": args.target,
        "resolved": resolved,
        "counts": {
            "hard_requires": len(hard),
            "soft_mentions": len(soft),
            "agent_portfolios": len(agents),
            "catalog_entries": len(catalog),
            "body_wikilinks": len(wikilinks),
            "kb_backrefs": len(kb),
        },
        "consumers": {
            "hard_requires": hard,
            "soft_mentions": soft,
            "agent_portfolios": agents,
            "catalog_entries": catalog,
            "body_wikilinks": wikilinks,
            "kb_backrefs": kb,
        },
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
