#!/usr/bin/env python3
"""
propose_spec.py — Step B of skill-architect: decision-tree spec proposer.

Reads signals.json (output of extract_signals.py) and emits a full skill_spec
proposal with per-field rationales + confidence score. Output drives Step C
(sibling observation) and Step D (LLM critic) and ultimately Step E (user
confirmation).

Decision rules per references/signal-taxonomy.md.

Exit codes (0/1/2/3 per v5.15.2 Pattern 9):
    0 — proposal emitted (even if low-confidence; user reviews at Step E)
    1 — policy violation (signals too ambiguous: max capability < 0.30 AND no domain match)
    2 — usage error (missing/unreadable signals input)
    3 — internal error

Usage:
    propose_spec.py --signals <signals.json>
    propose_spec.py --signals - < signals.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[4]


def derive_name(intent: str, signals: dict[str, Any]) -> str:
    """Heuristic kebab-case name from intent's primary verb + noun."""
    tokens = signals.get("tokens", [])

    cap = max(signals.get("capability_scores", {"unknown": 0}),
              key=lambda k: signals["capability_scores"][k])

    domain_evidence = signals.get("domain_evidence", {})
    domain_match = signals.get("domain_match", "")
    primary_nouns = domain_evidence.get(domain_match, [])

    verb_short = {
        "create": "create", "read": "find", "update": "sync",
        "delete": "deprecate", "evaluate": "audit",
        "orchestrate": "orchestrate", "communicate": "notify",
        "decide": "decide",
    }.get(cap, cap)

    if primary_nouns:
        primary = primary_nouns[0].split()[-1]
        return f"{primary}-{verb_short}"[:64]

    nouns = [t for t in tokens if len(t) > 3 and t not in {
        "the", "and", "for", "with", "that", "from", "into", "this",
        "skill", "after", "when", "use",
    }]
    if nouns:
        return f"{nouns[0]}-{verb_short}"[:64]
    return f"new-{verb_short}"[:64]


def derive_script_names(signals: dict[str, Any]) -> list[str]:
    """Heuristic script filename from arithmetic/data verbs."""
    if not signals.get("scripts_recommended"):
        return []
    evidence = signals.get("scripts_evidence", [])
    verbs = []
    for e in evidence:
        if ":" in e:
            cls, word = e.split(":", 1)
            word = word.strip()
            if cls.strip() in ("arithmetic", "data_shape"):
                verbs.append(word)
    if verbs:
        return [f"{verbs[0]}.py"]
    return ["main.py"]


def derive_reference_names(signals: dict[str, Any]) -> list[str]:
    """Heuristic reference filename from reference-data nouns."""
    if not signals.get("references_recommended"):
        return []
    evidence = signals.get("references_evidence", [])
    nouns: list[str] = []
    for e in evidence:
        if ":" in e:
            cls, word = e.split(":", 1)
            word = word.strip()
            if cls.strip() == "reference_data":
                nouns.append(word)
    if nouns:
        primary = nouns[0].rstrip("s")
        return [f"{primary}.md"]
    return ["procedure.md"]


def propose(signals: dict[str, Any]) -> dict[str, Any]:
    cap_scores = signals.get("capability_scores", {})
    if not cap_scores:
        return {"status": "ambiguous", "reason": "no capability scores"}

    capability = max(cap_scores, key=lambda k: cap_scores[k])
    cap_confidence = cap_scores[capability]

    sorted_caps = sorted(cap_scores.items(), key=lambda x: -x[1])
    if (len(sorted_caps) >= 2
            and sorted_caps[0][1] - sorted_caps[1][1] < 0.05
            and sorted_caps[0][1] > 0):
        capability_flag = "user_input_needed"
        cap_alts = [c for c, _ in sorted_caps[:3]]
    else:
        capability_flag = "confirm"
        cap_alts = []

    scripts_rec = signals.get("scripts_recommended", False)
    refs_rec = signals.get("references_recommended", False)

    if scripts_rec and refs_rec:
        layout = "meta-with-both"
    elif scripts_rec:
        layout = "meta-with-scripts"
    elif refs_rec:
        layout = "meta-with-refs"
    else:
        layout = "standard"

    layout_confidence = (signals.get("scripts_score", 0) + signals.get("references_score", 0)) / 2.0
    if not scripts_rec and not refs_rec:
        layout_confidence = max(0.5, 1.0 - layout_confidence)

    topic_scores = signals.get("topic_scores", {})
    sorted_tags = sorted(topic_scores.items(), key=lambda x: -x[1])
    proposed_tags = [t for t, s in sorted_tags[:2] if s > 0.4]
    if not proposed_tags and sorted_tags and sorted_tags[0][1] > 0:
        proposed_tags = [sorted_tags[0][0]]

    domain = signals.get("domain_match", "")
    if not domain:
        return {
            "status": "ambiguous",
            "reason": "no domain match — escalate to user",
            "evidence": signals.get("domain_match_counts", {}),
        }

    name = derive_name(signals.get("intent_text", ""), signals)
    intent_text = signals.get("intent_text", "")
    description_seed = intent_text[:1024] if len(intent_text) >= 200 else intent_text

    if len(description_seed) < 200:
        description_seed = description_seed + " " * (200 - len(description_seed))

    proposal: dict[str, Any] = {
        "status": "proposed",
        "spec": {
            "name": name,
            "parent_domain": domain,
            "capability": capability,
            "topic_tags": proposed_tags,
            "description_seed": description_seed.strip(),
            "scripts_required": derive_script_names(signals),
            "references_required": derive_reference_names(signals),
            "parity_layout": layout,
        },
        "rationales": {
            "name": f"derived from primary noun + verb '{capability}'",
            "parent_domain": (
                f"keyword evidence: {signals.get('domain_evidence', {}).get(domain, [])[:3]}"
            ),
            "capability": (
                f"top score {cap_confidence:.2f} via "
                f"{signals.get('capability_evidence', {}).get(capability, [])[:3]}"
            ),
            "topic_tags": (
                f"top scores {[(t, round(topic_scores.get(t, 0), 2)) for t in proposed_tags]}"
            ),
            "scripts_required": (
                f"signals score {signals.get('scripts_score', 0):.2f} "
                f"({'recommended' if scripts_rec else 'not recommended'}); "
                f"evidence: {signals.get('scripts_evidence', [])[:3]}"
            ),
            "references_required": (
                f"signals score {signals.get('references_score', 0):.2f} "
                f"({'recommended' if refs_rec else 'not recommended'}); "
                f"evidence: {signals.get('references_evidence', [])[:3]}"
            ),
            "parity_layout": (
                f"derived from scripts={scripts_rec} + references={refs_rec}"
            ),
        },
        "confidence": {
            "capability": round(cap_confidence, 2),
            "layout": round(min(1.0, layout_confidence), 2),
            "overall": round((cap_confidence + min(1.0, layout_confidence)) / 2.0, 2),
        },
        "flags": {
            "capability": capability_flag,
            "capability_alternates": cap_alts,
            "topic_tags_underspecified": len(proposed_tags) == 0,
            "needs_critic": (
                cap_confidence < 0.85
                or layout_confidence < 0.85
                or capability_flag == "user_input_needed"
            ),
        },
    }
    return proposal


def main() -> int:
    ap = argparse.ArgumentParser(description="skill-architect Step B — decision-tree spec proposer")
    ap.add_argument("--signals", required=True,
                    help="path to signals.json from extract_signals.py, or '-' for stdin")
    args = ap.parse_args()

    try:
        if args.signals == "-":
            text = sys.stdin.read()
        else:
            p = Path(args.signals)
            if not p.is_file():
                print(json.dumps({"status": "usage_error", "message": f"file not found: {p}"}), file=sys.stderr)
                return 2
            text = p.read_text(encoding="utf-8")

        signals = json.loads(text)
        proposal = propose(signals)
        if proposal.get("status") == "ambiguous":
            print(json.dumps(proposal, indent=2))
            return 1

        print(json.dumps(proposal, indent=2))
        return 0

    except SystemExit:
        raise
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
