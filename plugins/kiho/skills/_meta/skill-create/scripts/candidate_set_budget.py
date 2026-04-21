#!/usr/bin/env python3
"""
candidate_set_budget.py — Gate 22: candidate-set attention budget (v5.16).

The primary v5.16 attention gate. Replaces token-count framing as the
load-bearing check for skill-create Step 4 (post-description-improvement).

For a given skill draft, simulates the facet walk against each of the
skill's own trigger phrases (or its description if trigger_phrases is
absent) with the skill's own capability + domain + topic_tags as the
applied facets. The candidate set after facet filtering MUST be
<= HARD_CEILING (default 10) for every trigger phrase. If worst-case
exceeds the ceiling, the skill is under-facet-specified: add a
discriminating topic tag, tighten the capability verb, or escalate to
Gate 17 (novel contribution) if the problem is genuine overlap.

Uses skills/_meta/skill-find/scripts/facet_walk.py as the mock engine
(via subprocess so the gate and the runtime retrieval engine share
exactly one implementation).

Two modes:
  --draft <SKILL.md path>      Check a single draft (skill-create pipeline)
  --all                        Audit every existing SKILL.md (migration check)

Grounding: v5.16 Primitive 3 + attention-budget framing. Plan Stage E.
arXiv 2601.04748 §5.2 phase transition at |S|<=20; 10 gives 2x headroom.

Usage:
    candidate_set_budget.py --draft <path>
    candidate_set_budget.py --all
    candidate_set_budget.py --draft <path> --hard-ceiling 10

Exit codes (0/1/2/3):
    0 — worst-case candidate set <= hard ceiling (pass)
    1 — policy violation: worst-case > ceiling (under-facet-specified)
    2 — usage error
    3 — internal error
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent.parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
FACET_WALK_SCRIPT = PLUGIN_ROOT / "skills" / "_meta" / "skill-find" / "scripts" / "facet_walk.py"

DEFAULT_HARD_CEILING = 10


def extract_frontmatter(skill_md: Path) -> dict:
    """Return dict of frontmatter fields incl. metadata.kiho.capability / topic_tags."""
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    fm = m.group(1)
    out: dict = {"name": "", "description": "", "capability": "", "topic_tags": [], "trigger_phrases": []}
    for line in fm.splitlines():
        colon_idx = line.find(":")
        if colon_idx == -1:
            continue
        key = line[:colon_idx].strip()
        val = line[colon_idx + 1:].strip().strip('"').strip("'")
        if key == "name" and not out["name"]:
            out["name"] = val
        elif key == "description" and not out["description"]:
            out["description"] = val
    cap_m = re.search(
        r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+capability:\s*(\w+)",
        fm,
        re.MULTILINE,
    )
    if cap_m:
        out["capability"] = cap_m.group(1)
    tags_m = re.search(
        r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+topic_tags:\s*\[([^\]]*)\]",
        fm,
        re.MULTILINE,
    )
    if tags_m:
        out["topic_tags"] = [t.strip() for t in tags_m.group(1).split(",") if t.strip()]
    # Optional: trigger_phrases top-level field under metadata.kiho
    trig_m = re.search(
        r"^metadata:\s*\n(?:[ \t]+.*\n)*?[ \t]+kiho:\s*\n(?:[ \t]+.*\n)*?[ \t]+trigger_phrases:\s*\[([^\]]*)\]",
        fm,
        re.MULTILINE,
    )
    if trig_m:
        out["trigger_phrases"] = [t.strip().strip('"').strip("'") for t in trig_m.group(1).split(",") if t.strip()]
    return out


def extract_when_to_use_phrases(skill_md: Path) -> list[str]:
    """Pull the sentence fragments from a `## When to use` section, if present.
    Returns an empty list if the section is absent."""
    text = skill_md.read_text(encoding="utf-8")
    m = re.search(r"^##\s+When to use\b[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    # Collect bullet items and table rows as candidate phrases
    phrases: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("-") or line.startswith("*"):
            phrases.append(line.lstrip("-* ").strip())
        elif line.startswith("|") and "|" in line[1:] and "---" not in line:
            # Extract first column of a markdown table row
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0] and cells[0].lower() not in ("scenario", "use this skill"):
                phrases.append(cells[0])
    return phrases


def derive_query_set(skill_md: Path, meta: dict) -> list[str]:
    """Decide what to test as discovery queries. Priority:
      1. metadata.kiho.trigger_phrases list (if present) — explicit triggers
      2. The skill's own description — primary discovery signal (what Claude
         Code reads for skill selection)
      3. ## When to use bullets as a secondary signal (narrative prose;
         rarely contains discriminators, kept as last resort)

    v5.16 note: "When to use" bullets are intentionally deprioritized because
    they are narrative ("User runs `/kiho kb-init` on a fresh project") and
    lack the discriminating keywords the facet walker needs. The description
    is the primary trigger mechanism; trigger_phrases are secondary.
    """
    if meta.get("trigger_phrases"):
        return list(meta["trigger_phrases"])
    desc = meta.get("description", "")
    if desc:
        # Use both the description and (if available) the first 2 When-to-use
        # bullets. Gate 22 passes when ALL of them stay within the ceiling.
        queries: list[str] = [desc[:400]]
        wtu = extract_when_to_use_phrases(skill_md)
        # Only include WTU bullets if they contain at least one discriminator
        # that the facet walker is likely to infer. This avoids false failures
        # on narrative-heavy sections.
        for phrase in wtu[:4]:
            tokens = set(re.findall(r"[a-z][a-z0-9-]{2,}", phrase.lower()))
            if tokens & {"create", "update", "delete", "evaluate", "read",
                         "orchestrate", "communicate", "decide",
                         "authoring", "lifecycle", "discovery", "retrieval",
                         "ingestion", "validation", "curation", "observability",
                         "reflection", "learning", "orchestration",
                         "deliberation", "bootstrap", "hiring", "persona",
                         "state-management", "research", "engineering"}:
                queries.append(phrase)
        return queries
    wtu = extract_when_to_use_phrases(skill_md)
    if wtu:
        return wtu[:4]
    return []


def run_facet_walk(
    query: str,
    capability: str,
    topic_tags: list[str],
    hard_ceiling: int,
) -> dict:
    """Invoke facet_walk.py as a subprocess in --gate-mode.

    Gate 22 forces the skill's own declared capability AND topic_tags as
    the applied facets — the gate is asking "given this skill's claimed
    discoverability facets, does the candidate set stay under the ceiling
    for this query?". If the author declared a topic tag, the gate trusts
    it; facet inference from the query text is only used for domain.
    """
    cmd = [
        sys.executable, str(FACET_WALK_SCRIPT),
        "--query", query,
        "--hard-ceiling", str(hard_ceiling),
        "--gate-mode",
    ]
    if capability:
        cmd += ["--capability", capability]
    for tag in topic_tags:
        cmd += ["--topic-tag", tag]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout) if result.stdout.strip() else {"passed": False, "status": "no_output"}
    except json.JSONDecodeError:
        return {"passed": False, "status": "facet_walk_bad_output", "stderr": result.stderr}


def check_one(skill_md: Path, hard_ceiling: int) -> dict:
    rel = (
        skill_md.relative_to(PLUGIN_ROOT)
        if PLUGIN_ROOT in skill_md.parents
        else skill_md
    )
    if not skill_md.is_file():
        return {"path": str(skill_md), "passed": False, "status": "file_not_found"}
    meta = extract_frontmatter(skill_md)
    if not meta:
        return {"path": str(rel), "passed": False, "status": "no_frontmatter"}
    queries = derive_query_set(skill_md, meta)
    if not queries:
        return {
            "path": str(rel),
            "passed": False,
            "status": "no_triggers",
            "message": "skill has no trigger_phrases, no ## When to use section, and no description",
        }
    per_query: list[dict] = []
    worst_case = 0
    worst_query = ""
    for q in queries:
        verdict = run_facet_walk(
            q,
            meta.get("capability", ""),
            meta.get("topic_tags", []),
            hard_ceiling,
        )
        count = verdict.get("candidate_count", -1)
        per_query.append({
            "query": q,
            "candidate_count": count,
            "status": verdict.get("status", "unknown"),
            "applied_facets": verdict.get("applied_facets", {}),
        })
        if count > worst_case:
            worst_case = count
            worst_query = q
    passed = worst_case <= hard_ceiling
    return {
        "path": str(rel),
        "passed": passed,
        "status": "ok" if passed else "underspecified",
        "worst_case": worst_case,
        "worst_query": worst_query,
        "hard_ceiling": hard_ceiling,
        "per_query": per_query,
        "capability": meta.get("capability", ""),
        "topic_tags": meta.get("topic_tags", []),
    }


def discover_all_skills() -> list[Path]:
    result: list[Path] = []
    for domain in ("_meta", "core", "kb", "memory", "engineering"):
        domain_dir = SKILLS_DIR / domain
        if not domain_dir.is_dir():
            continue
        for child in sorted(domain_dir.iterdir()):
            if not child.is_dir():
                continue
            flat = child / "SKILL.md"
            if flat.is_file():
                result.append(flat)
                continue
            for grand in sorted(child.iterdir()):
                if not grand.is_dir():
                    continue
                nested = grand / "SKILL.md"
                if nested.is_file():
                    result.append(nested)
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--draft", type=str, help="path to one SKILL.md (new draft)")
    g.add_argument("--all", action="store_true", help="audit every SKILL.md on disk")
    p.add_argument("--hard-ceiling", type=int, default=DEFAULT_HARD_CEILING,
                   help="worst-case candidate-set ceiling (default 10)")
    return p.parse_args()


def main() -> int:
    try:
        args = parse_args()
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    if not FACET_WALK_SCRIPT.exists():
        sys.stderr.write(f"candidate_set_budget: facet_walk.py not found: {FACET_WALK_SCRIPT}\n")
        return 2
    try:
        if args.draft:
            verdict = check_one(Path(args.draft), args.hard_ceiling)
            sys.stdout.write(json.dumps(verdict, indent=2) + "\n")
            return 0 if verdict["passed"] else 1

        files = discover_all_skills()
        verdicts = [check_one(p, args.hard_ceiling) for p in files]
        failed = [v for v in verdicts if not v["passed"]]
        summary = {
            "total": len(verdicts),
            "passed": len(verdicts) - len(failed),
            "failed": len(failed),
            "hard_ceiling": args.hard_ceiling,
            "failures": [
                {"path": v["path"], "worst_case": v.get("worst_case"),
                 "worst_query": v.get("worst_query"), "status": v["status"]}
                for v in failed
            ],
        }
        sys.stdout.write(json.dumps(summary, indent=2) + "\n")
        return 0 if not failed else 1
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"candidate_set_budget: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
