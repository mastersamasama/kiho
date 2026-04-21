#!/usr/bin/env python3
"""
render_proposal.py — Step E renderer: turn an architect proposal into a
human-friendly markdown confirmation table.

Reads the JSON output of propose_spec.py (optionally merged with critic
output via skill_factory orchestrator) and emits a markdown document the
CEO can scan in <30s with per-field accept/override actions.

Exit codes (0/1/2/3 per v5.15.2 Pattern 9):
    0 — markdown rendered to stdout
    1 — proposal status is ambiguous; renders escalation table instead
    2 — usage error (missing/unreadable proposal input)
    3 — internal error

Usage:
    render_proposal.py --proposal proposal.json
    render_proposal.py --proposal - < proposal.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CONFIDENCE_BADGE = {
    "high": "🟢 high",
    "medium": "🟡 medium",
    "low": "🔴 low",
}

FIELD_ORDER = [
    "name",
    "parent_domain",
    "capability",
    "topic_tags",
    "description_seed",
    "scripts_required",
    "references_required",
    "parity_layout",
]


def confidence_badge(score: float | None) -> str:
    if score is None:
        return "n/a"
    if score >= 0.85:
        return CONFIDENCE_BADGE["high"]
    if score >= 0.60:
        return CONFIDENCE_BADGE["medium"]
    return CONFIDENCE_BADGE["low"]


def format_value(value: Any, max_chars: int = 80) -> str:
    if value is None:
        return "_(none)_"
    if isinstance(value, list):
        if not value:
            return "`[]`"
        return ", ".join(f"`{v}`" for v in value)
    if isinstance(value, str):
        s = value.strip()
        if len(s) > max_chars:
            return f"`{s[:max_chars - 1]}…`"
        return f"`{s}`" if s else "_(empty)_"
    return f"`{value}`"


def render_ambiguous(proposal: dict[str, Any]) -> str:
    lines = [
        "# Skill-architect — escalation needed",
        "",
        f"**Status**: `ambiguous`",
        f"**Reason**: {proposal.get('reason', 'unspecified')}",
        "",
        "## Tied candidates",
        "",
    ]
    evidence = proposal.get("evidence") or proposal.get("domain_match_counts") or {}
    if evidence:
        lines.append("| Candidate | Match count |")
        lines.append("|---|---|")
        for k, v in sorted(evidence.items(), key=lambda x: -x[1] if isinstance(x[1], (int, float)) else 0):
            lines.append(f"| `{k}` | {v} |")
    else:
        lines.append("_(no candidates surfaced — provide a richer intent description)_")
    lines.extend([
        "",
        "## CEO action required",
        "",
        "Reply with one of:",
        "",
        "- `pick: <candidate>` — disambiguate to a specific candidate",
        "- `restart: <new intent>` — provide a refined intent description",
        "- `manual` — supply a hand-authored skill_spec via `--regen <path>` instead of `--from-intent`",
        "",
    ])
    return "\n".join(lines)


def render(proposal: dict[str, Any]) -> str:
    if proposal.get("status") == "ambiguous":
        return render_ambiguous(proposal)

    spec = proposal.get("spec", {})
    rationales = proposal.get("rationales", {})
    confidence = proposal.get("confidence", {})
    flags = proposal.get("flags", {})

    overall = confidence.get("overall", 0.0)
    needs_critic = flags.get("needs_critic", False)

    lines = [
        "# Skill-architect proposal — review and confirm",
        "",
        f"**Overall confidence**: {confidence_badge(overall)} ({overall:.2f})",
        f"**Critic invocation**: {'⚠️  recommended (low confidence or sibling divergence)' if needs_critic else '✅ not required (high confidence + sibling consensus)'}",
        "",
        "## Proposed skill_spec",
        "",
        "| Field | Proposed | Confidence | Rationale |",
        "|---|---|---|---|",
    ]

    field_confidence_map = {
        "capability": confidence.get("capability"),
        "parity_layout": confidence.get("layout"),
    }

    for field in FIELD_ORDER:
        if field not in spec:
            continue
        value_str = format_value(spec.get(field))
        f_conf = field_confidence_map.get(field, overall)
        conf_str = confidence_badge(f_conf) if f_conf is not None else "—"
        rationale = rationales.get(field, "—")
        if len(rationale) > 110:
            rationale = rationale[:108] + "…"
        lines.append(f"| `{field}` | {value_str} | {conf_str} | {rationale} |")

    cap_alts = flags.get("capability_alternates", [])
    if cap_alts:
        lines.extend([
            "",
            "## ⚠️  Capability tie surfaced",
            "",
            f"Top candidates within 0.05 of each other: {', '.join(f'`{c}`' for c in cap_alts)}.",
            "Pick one explicitly via `override capability=<verb>` in your reply.",
            "",
        ])

    if flags.get("topic_tags_underspecified"):
        lines.extend([
            "",
            "## ⚠️  Topic tags underspecified",
            "",
            "No tag scored above the 0.40 threshold. Suggest adding 1-2 tags from `references/topic-vocabulary.md` via `override topic_tags=[tag1,tag2]`.",
            "",
        ])

    if needs_critic:
        lines.extend([
            "",
            "## ⚠️  Critic invocation recommended",
            "",
            "Confidence < 0.85 OR sibling divergence > 0.30. Before accepting, consider invoking the critic subagent:",
            "",
            "1. Run `bin/skill_factory.py --critic-prepare <intent>` to write the critic-request bundle to `_meta-runtime/critic-requests/`.",
            "2. Spawn the critic via Task tool with `subagent_type: skill-architect-critic` and the bundle as input.",
            "3. Re-render this table with `render_proposal.py --proposal <merged_with_critic>`.",
            "",
        ])

    lines.extend([
        "",
        "## CEO confirmation actions",
        "",
        "Reply with one of:",
        "",
        "- `accept all` — flow to skill-spec dry-run (Step 1) with this exact spec",
        "- `accept all but: <field>=<value>[, <field>=<value>...]` — single or multi-field override; re-validate downstream",
        "- `invoke critic` — defer decision; spawn the Step D critic subagent first",
        "- `reject; my intent is different` — restart Step 0 with a refined intent",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="skill-architect Step E — markdown-table renderer")
    ap.add_argument("--proposal", required=True,
                    help="path to proposal.json from propose_spec.py, or '-' for stdin")
    args = ap.parse_args()

    try:
        if args.proposal == "-":
            text = sys.stdin.read()
        else:
            p = Path(args.proposal)
            if not p.is_file():
                print(json.dumps({"status": "usage_error", "message": f"file not found: {p}"}), file=sys.stderr)
                return 2
            text = p.read_text(encoding="utf-8")

        proposal = json.loads(text)
        markdown = render(proposal)
        print(markdown)
        return 1 if proposal.get("status") == "ambiguous" else 0

    except SystemExit:
        raise
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
