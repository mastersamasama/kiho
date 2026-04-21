"""Recompute capability-matrix.md from agent performance data.

Reads agent-performance.jsonl and skill-invocations.jsonl, applies the
proficiency formula, and writes the updated capability-matrix.md.
Also updates the agent_count in org-registry.md frontmatter.

Usage:
    python org_sync.py <project_root>

Dependencies: stdlib only (json, math, pathlib, sys, datetime).

Exit codes (0/1/2/3 per v5.15.2 Pattern 9):
    0 — success (capability matrix recomputed OR no agents to recompute)
    1 — policy violation (registry exists but no parseable agents — corrupt state)
    2 — usage error (missing project_root argument, bad path)
    3 — internal error (unexpected exception during computation)
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file and return a list of parsed objects."""
    entries: list[dict[str, Any]] = []
    if not path.exists():
        return entries
    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Warning: skipping malformed line {line_num} in {path}")
    return entries


def compute_proficiency(success_rate: float, tasks: int) -> int:
    """Apply the proficiency formula: floor(1 + 4 * min(success_rate * log2(tasks+1) / 5, 1.0))."""
    if tasks == 0:
        return 1
    volume_factor = math.log2(tasks + 1) / 5.0
    raw = 1.0 + 4.0 * min(success_rate * volume_factor, 1.0)
    return max(1, min(5, math.floor(raw)))


def extract_agents_from_registry(registry_path: Path) -> list[str]:
    """Parse org-registry.md and return a list of active agent IDs."""
    if not registry_path.exists():
        return []
    text = registry_path.read_text(encoding="utf-8")
    # Match agent IDs in various formats:
    #   - **Agent:** ceo-01
    #   - **Lead:** eng-lead-01 (agents/...)
    #   - eng-backend-ic-01 — role (active)
    #   - **<role-label>:** <id> (agents/...) -- active   (any shared-service label)
    agents: list[str] = []
    for match in re.finditer(
        r"\*\*[A-Za-z][A-Za-z0-9 _-]*:\*\*\s+([a-z][a-z0-9-]*-\d+)\b",
        text,
    ):
        agents.append(match.group(1))
    # Also match direct reports and team members: "  - eng-backend-ic-01"
    for match in re.finditer(
        r"^\s+-\s+([a-z][a-z0-9-]+-\d+)\b",
        text,
        re.MULTILINE,
    ):
        agent_id = match.group(1)
        if agent_id not in agents:
            agents.append(agent_id)
    return agents


def build_proficiency_table(
    agents: list[str],
    performance: list[dict[str, Any]],
    invocations: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Build a {agent_id: {domain: proficiency}} mapping."""
    # Aggregate task counts and successes per agent per domain
    stats: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"tasks": 0, "successes": 0})
    )

    for entry in performance:
        aid = entry.get("agent_id", "")
        domain = entry.get("skill_domain", "unknown")
        stats[aid][domain]["tasks"] += 1
        if entry.get("success", False):
            stats[aid][domain]["successes"] += 1

    for entry in invocations:
        aid = entry.get("agent_id", "")
        # Map skill_name to a domain (use skill_name as domain if no mapping)
        domain = entry.get("skill_domain", entry.get("skill_name", "unknown"))
        stats[aid][domain]["tasks"] += 1
        if entry.get("success", False):
            stats[aid][domain]["successes"] += 1

    # Collect all domains across all agents
    all_domains: set[str] = set()
    for aid in agents:
        all_domains.update(stats.get(aid, {}).keys())
    if not all_domains:
        all_domains = {"general"}

    # Compute proficiency
    table: dict[str, dict[str, int]] = {}
    sorted_domains = sorted(all_domains)
    for aid in agents:
        row: dict[str, int] = {}
        for domain in sorted_domains:
            s = stats.get(aid, {}).get(domain, {"tasks": 0, "successes": 0})
            tasks = s["tasks"]
            successes = s["successes"]
            success_rate = successes / tasks if tasks > 0 else 0.0
            row[domain] = compute_proficiency(success_rate, tasks)
        table[aid] = row

    return table


def write_capability_matrix(
    matrix_path: Path,
    project_slug: str,
    table: dict[str, dict[str, int]],
) -> None:
    """Write capability-matrix.md with frontmatter and markdown table.

    Also writes a JSONL sibling at capability-matrix.jsonl for fast
    RACI-style keyed queries (v5.20). Md remains the reviewable source
    of truth; JSONL is a derived view and is idempotently regenerated
    from the same in-memory table on every org_sync run.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not table:
        domains = ["general"]
    else:
        first_agent = next(iter(table))
        domains = sorted(table[first_agent].keys())

    lines: list[str] = [
        "---",
        f"project_slug: {project_slug}",
        f"last_recomputed: {now}",
        "schema_version: 1",
        "---",
        "",
        "# Capability Matrix",
        "",
    ]

    # Header row
    header = "| Agent | " + " | ".join(domains) + " |"
    separator = "|---" + "|---" * len(domains) + "|"
    lines.append(header)
    lines.append(separator)

    # Data rows
    for aid in sorted(table.keys()):
        row = table[aid]
        values = " | ".join(str(row.get(d, 1)) for d in domains)
        lines.append(f"| {aid} | {values} |")

    lines.append("")
    matrix_path.write_text("\n".join(lines), encoding="utf-8")

    # JSONL sibling for RACI queries (v5.20). One row per (agent, domain)
    # so broker.query can filter where={"domain": X, "proficiency": {"$ge": 2}}.
    jsonl_path = matrix_path.with_suffix(".jsonl")
    jsonl_lines: list[str] = []
    for aid in sorted(table.keys()):
        for domain in domains:
            row = {
                "id": f"{aid}__{domain}",
                "kind": "generic",
                "scope": "project",
                "owner": "kiho",
                "tier": "jsonl",
                "created_at": now,
                "updated_at": now,
                "source": {"skill": "org-sync", "generated_from": str(matrix_path)},
                "payload": {
                    "agent_id": aid,
                    "domain": domain,
                    "proficiency": table[aid].get(domain, 1),
                    "project_slug": project_slug,
                },
            }
            jsonl_lines.append(json.dumps(row, ensure_ascii=False, sort_keys=False))
    jsonl_path.write_text(
        "\n".join(jsonl_lines) + ("\n" if jsonl_lines else ""),
        encoding="utf-8",
    )


def update_registry_agent_count(registry_path: Path, count: int) -> None:
    """Update the agent_count field in org-registry.md frontmatter."""
    if not registry_path.exists():
        return
    text = registry_path.read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = re.sub(r"^agent_count:\s*\d+", f"agent_count: {count}", text, flags=re.MULTILINE)
    text = re.sub(
        r"^last_modified:\s*\S+",
        f"last_modified: {now}",
        text,
        flags=re.MULTILINE,
    )
    registry_path.write_text(text, encoding="utf-8")


def main() -> int:
    """Entry point: recompute capability matrix from JSONL data. Returns exit code."""
    if len(sys.argv) < 2:
        print("Usage: python org_sync.py <project_root>", file=sys.stderr)
        return 2

    project_root = Path(sys.argv[1])
    if not project_root.exists():
        print(f"error: project_root {project_root} does not exist", file=sys.stderr)
        return 2

    state_dir = project_root / ".kiho" / "state"

    registry_path = state_dir / "org-registry.md"
    matrix_path = state_dir / "capability-matrix.md"
    performance_path = state_dir / "agent-performance.jsonl"
    invocations_path = state_dir / "skill-invocations.jsonl"

    # Extract project slug from registry frontmatter
    project_slug = "unknown"
    if registry_path.exists():
        text = registry_path.read_text(encoding="utf-8")
        slug_match = re.search(r"^project_slug:\s*(.+)$", text, re.MULTILINE)
        if slug_match:
            project_slug = slug_match.group(1).strip()

    # Load data
    agents = extract_agents_from_registry(registry_path)
    performance = load_jsonl(performance_path)
    invocations = load_jsonl(invocations_path)

    if not agents:
        if registry_path.exists():
            # Registry file is there but no agents parseable — corrupt state
            print(
                "policy violation: org-registry.md exists but has no parseable agents",
                file=sys.stderr,
            )
            return 1
        # No registry yet — normal empty-state, nothing to recompute
        print("No agents found in org-registry.md. Nothing to recompute.")
        return 0

    # Compute and write
    table = build_proficiency_table(agents, performance, invocations)
    write_capability_matrix(matrix_path, project_slug, table)
    update_registry_agent_count(registry_path, len(agents))

    print(f"Capability matrix recomputed for {len(agents)} agents.")
    print(f"  Domains: {sorted(next(iter(table.values())).keys()) if table else []}")
    print(f"  Written to: {matrix_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        sys.exit(3)
