#!/usr/bin/env python3
"""
extract_signals.py — Step A of skill-architect: deterministic signal extraction
from raw intent text.

Tokenizes intent and matches against the closed signal taxonomy from
skills/_meta/skill-architect/references/signal-taxonomy.md to produce a
structured signals.json. Output drives propose_spec.py (Step B).

Exit codes (0/1/2/3 per v5.15.2 Pattern 9):
    0 — success (signals extracted, even if all scores low)
    1 — policy violation (intent too short < 20 chars OR > 8000 chars)
    2 — usage error (missing --intent, unreadable input)
    3 — internal error

Usage:
    extract_signals.py --intent "<text>"
    extract_signals.py --intent-file <path>
    extract_signals.py --intent - < input.txt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[4]

CAPABILITY_VERBS = {
    "create": ["produce", "generate", "draft", "build", "instantiate", "initialize",
               "author", "compose", "scaffold", "bootstrap", "make"],
    "read": ["find", "get", "list", "show", "inspect", "query", "lookup", "fetch",
             "search", "retrieve", "view", "display"],
    "update": ["modify", "edit", "sync", "synchronize", "synchronizes", "refresh", "recompute",
               "mutate", "patch", "transform", "update", "adjust", "change"],
    "delete": ["remove", "deprecate", "archive", "retire", "prune", "delete",
               "expire", "cleanup", "purge"],
    "evaluate": ["validate", "audit", "score", "check", "verify", "assess", "lint",
                 "evaluate", "grade", "review"],
    "orchestrate": ["coordinate", "chain", "dispatch", "route", "manage",
                    "orchestrate", "batch", "pipeline", "flow", "sequence"],
    "communicate": ["notify", "escalate", "present", "report", "surface",
                    "communicate", "broadcast", "publish", "alert"],
    "decide": ["vote", "decide", "judge", "deliberate", "arbitrate", "choose",
               "rule", "determine"],
}

SCRIPTS_SIGNALS = {
    "arithmetic": (["compute", "recompute", "calculate", "sum", "aggregate",
                    "score", "count", "average", "tally"], 0.25),
    "data_shape": (["parse", "transform", "filter", "sort", "dedupe", "validate",
                    "normalize", "extract", "tokenize"], 0.20),
    "scale": (["hundreds", "thousands", "jsonl", "batch", "bulk", "all entries",
               "full catalog", "every", "across"], 0.30),
    "determinism": (["reproducible", "deterministic", "audit", "idempotent",
                     "atomic", "hash", "checksum"], 0.25),
    "file_format": ([".jsonl", ".json", ".yaml", ".csv", ".toml", ".md"], 0.20),
    "side_effect": (["write", "append", "atomic write", "emit", "save",
                     "writer", "writes", "single writer", "single source"], 0.20),
    "state_artifact": (["registry", "matrix", "ledger", "manifest", "snapshot",
                        "live", "table", "index", "performance data",
                        "performance", "telemetry"], 0.20),
    "outcome_implementation": (["synchronize", "synchronizes", "syncs", "sync",
                                "refresh", "refreshes", "reconcile", "reconciles",
                                "propagate", "propagates"], 0.20),
}

REFERENCES_SIGNALS = {
    "multi_step": (["first", "then", "finally", "step 1", "step 2", "phase",
                    "stage", "round"], 0.30),
    "narrative": (["rationale", "why", "trade-off", "trade-offs", "principle",
                   "principles", "philosophy", "design-decision", "design decision"], 0.25),
    "reference_data": (["table", "tables", "formula", "schema", "vocabulary",
                        "vocabularies", "taxonomy", "rubric", "template",
                        "templates"], 0.30),
    "body_length": (["detailed procedure", "comprehensive guide", "full spec",
                     "deep dive", "thorough"], 0.15),
    "domain_knowledge": (["see ", "per rfc", "per iso", "per anthropic",
                          "per arxiv", "per shingo", "per deming"], 0.20),
}

TOPIC_TAGS = {
    "authoring": ["create", "author", "draft", "generate", "factory"],
    "lifecycle": ["deprecate", "retire", "archive", "lifecycle", "version", "graduation"],
    "validation": ["validate", "check", "audit", "lint", "verify", "assess"],
    "discovery": ["find", "search", "retrieve", "lookup", "query", "discovery"],
    "orchestration": ["orchestrate", "chain", "batch", "pipeline", "dispatch", "manage"],
    "state-management": ["sync", "synchronize", "registry", "matrix", "recompute",
                         "state", "store"],
    "observability": ["inspect", "telemetry", "observe", "monitor", "trace",
                      "debug", "log"],
    "hiring": ["recruit", "hire", "candidate", "interview", "agent design"],
    "persona": ["soul", "persona", "drift", "override", "personality"],
    "knowledge": ["research", "doc", "crawl", "knowledge", "kb", "wiki"],
    "deliberation": ["committee", "vote", "debate", "deliberate", "decide"],
    "experience": ["learn", "capture", "extract", "lesson", "observation"],
    "bootstrap": ["setup", "init", "initialize", "bootstrap", "install"],
    "retention": ["promote", "archive", "retain", "expire", "prune"],
    "meta-operations": ["meta", "factory", "harness", "orchestrator"],
    "committee voting": ["vote", "ballot", "majority", "unanimous"],
    "interview simulation": ["interview", "simulate", "candidate test"],
    "experience pool": ["pool", "share", "federated", "cross-project"],
}

DOMAIN_KEYWORDS = {
    "_meta": ["skill", "factory", "validator", "audit", "generator", "lifecycle",
              "architect", "spec"],
    "core/harness": ["kiho", "orchestrate", "runtime", "config", "sync", "synchronize",
                     "registry", "matrix", "harness"],
    "core/hr": ["hire", "recruit", "agent design", "interview", "candidate", "hr"],
    "core/inspection": ["inspect", "debug", "view state", "trace", "dump",
                        "session context"],
    "core/knowledge": ["research", "deep doc", "crawl", "knowledge", "deepwiki"],
    "core/planning": ["plan", "committee", "deliberate", "simulate", "vote"],
    "kb": ["knowledge base", "wiki", "lint", "promote", "ingest", "page"],
    "memory": ["observation", "reflection", "lesson", "drift", "todo", "journal"],
    "engineering": ["spec", "requirement", "design", "task", "ears", "kiro"],
}


def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s.\-]", " ", text)
    return [t for t in text.split() if t]


def stem_variants(word: str) -> set[str]:
    """Return possible stem variants of a word (covers -s, -es, -ed, -ing, -ies → -y)."""
    out = {word}
    if len(word) < 4:
        return out
    if word.endswith("ies"):
        out.add(word[:-3] + "y")
    if word.endswith("ied"):
        out.add(word[:-3] + "y")
    if word.endswith("ing"):
        out.add(word[:-3])
        out.add(word[:-3] + "e")
    if word.endswith("ed"):
        out.add(word[:-2])
        out.add(word[:-1])
    if word.endswith("es"):
        out.add(word[:-2])
        out.add(word[:-1])
    if word.endswith("s") and not word.endswith("ss"):
        out.add(word[:-1])
    return out


def count_word_matches(tokens: list[str], words: list[str]) -> tuple[int, list[str]]:
    matched: list[str] = []
    text_joined = " ".join(tokens)
    token_variants: set[str] = set()
    for t in tokens:
        token_variants |= stem_variants(t)
    for w in words:
        if " " in w:
            if w in text_joined:
                matched.append(w)
        else:
            w_variants = stem_variants(w)
            if w_variants & token_variants:
                matched.append(w)
    return len(matched), matched


CONSUMER_CONTEXT_MARKERS = [
    "use when", "used when", "after", "called by", "invoked by", "consumed by",
    "downstream of", "triggered by", "in response to", "when the",
]


def consumer_context_filter(intent: str, matched_words: list[str]) -> tuple[list[str], list[str]]:
    """Split matched_words into (actor_matches, consumer_matches).

    A match is a 'consumer mention' if every occurrence of the word in the intent
    text appears within ~5 tokens after a consumer-context marker phrase
    (e.g., 'use when the recruit skill ...'). Such matches are suppressed from
    topic-tag scoring to avoid the recruit→hiring false-positive class.
    """
    if not matched_words:
        return [], []
    text = intent.lower()
    actor: list[str] = []
    consumer: list[str] = []
    for w in matched_words:
        w_low = w.lower()
        positions = [i for i in range(len(text)) if text.startswith(w_low, i)]
        if not positions:
            actor.append(w)
            continue
        all_consumer = True
        for pos in positions:
            window_start = max(0, pos - 60)
            preceding = text[window_start:pos]
            if not any(marker in preceding for marker in CONSUMER_CONTEXT_MARKERS):
                all_consumer = False
                break
        if all_consumer:
            consumer.append(w)
        else:
            actor.append(w)
    return actor, consumer


def extract_signals(intent: str) -> dict[str, Any]:
    tokens = tokenize(intent)

    capability_scores: dict[str, float] = {}
    capability_evidence: dict[str, list[str]] = {}
    for verb, signal_words in CAPABILITY_VERBS.items():
        count, matched = count_word_matches(tokens, signal_words)
        capability_scores[verb] = min(1.0, count * 0.3)
        capability_evidence[verb] = matched

    scripts_score = 0.0
    scripts_evidence: list[str] = []
    for cls, (words, weight) in SCRIPTS_SIGNALS.items():
        count, matched = count_word_matches(tokens, words)
        if count > 0:
            scripts_score += weight
            scripts_evidence.extend([f"{cls}: {m}" for m in matched])
    scripts_score = min(1.0, scripts_score)

    references_score = 0.0
    references_evidence: list[str] = []
    for cls, (words, weight) in REFERENCES_SIGNALS.items():
        count, matched = count_word_matches(tokens, words)
        if count > 0:
            references_score += weight
            references_evidence.extend([f"{cls}: {m}" for m in matched])
    references_score = min(1.0, references_score)

    topic_scores: dict[str, float] = {}
    topic_evidence: dict[str, list[str]] = {}
    topic_consumer_suppressed: dict[str, list[str]] = {}
    for tag, signal_words in TOPIC_TAGS.items():
        count, matched = count_word_matches(tokens, signal_words)
        actor_matches, consumer_matches = consumer_context_filter(intent, matched)
        effective_count = len(actor_matches)
        topic_scores[tag] = min(1.0, effective_count * 0.4)
        topic_evidence[tag] = actor_matches
        if consumer_matches:
            topic_consumer_suppressed[tag] = consumer_matches

    domain_match_counts: dict[str, int] = {}
    domain_evidence: dict[str, list[str]] = {}
    for domain, signal_words in DOMAIN_KEYWORDS.items():
        count, matched = count_word_matches(tokens, signal_words)
        domain_match_counts[domain] = count
        domain_evidence[domain] = matched
    sorted_domains = sorted(domain_match_counts.items(), key=lambda x: -x[1])
    top_score = sorted_domains[0][1]
    top_domains = [d for d, c in sorted_domains if c == top_score and c > 0]
    if not top_domains:
        domain_match = ""
        tied_candidates: list[str] = []
    elif len(top_domains) > 1:
        domain_match = ""
        tied_candidates = top_domains
    else:
        domain_match = top_domains[0]
        tied_candidates = []

    return {
        "intent_text": intent,
        "intent_length": len(intent),
        "tokens": tokens,
        "capability_scores": capability_scores,
        "capability_evidence": {k: v for k, v in capability_evidence.items() if v},
        "scripts_recommended": scripts_score >= 0.50,
        "scripts_score": round(scripts_score, 3),
        "scripts_evidence": scripts_evidence,
        "references_recommended": references_score >= 0.50,
        "references_score": round(references_score, 3),
        "references_evidence": references_evidence,
        "topic_scores": {k: round(v, 3) for k, v in topic_scores.items()},
        "topic_evidence": {k: v for k, v in topic_evidence.items() if v},
        "topic_consumer_suppressed": topic_consumer_suppressed,
        "domain_match": domain_match,
        "domain_match_counts": domain_match_counts,
        "domain_tied_candidates": tied_candidates,
        "domain_evidence": {k: v for k, v in domain_evidence.items() if v},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="skill-architect Step A — signal extraction")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--intent", help="raw intent text")
    grp.add_argument("--intent-file", type=Path, help="path to file containing intent")
    args = ap.parse_args()

    try:
        if args.intent_file:
            if str(args.intent_file) == "-":
                intent = sys.stdin.read().strip()
            elif args.intent_file.is_file():
                intent = args.intent_file.read_text(encoding="utf-8").strip()
            else:
                print(json.dumps({"status": "usage_error", "message": f"file not found: {args.intent_file}"}), file=sys.stderr)
                return 2
        else:
            intent = args.intent
            if intent == "-":
                intent = sys.stdin.read().strip()

        if not (20 <= len(intent) <= 8000):
            print(json.dumps({"status": "policy_violation",
                              "message": f"intent length {len(intent)} out of bounds [20, 8000]"}),
                  file=sys.stderr)
            return 1

        signals = extract_signals(intent)
        print(json.dumps(signals, indent=2))
        return 0

    except SystemExit:
        raise
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
