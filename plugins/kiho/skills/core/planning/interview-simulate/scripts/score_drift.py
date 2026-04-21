#!/usr/bin/env python3
"""Compute persona drift from N candidate replay responses.

Used by interview-simulate in mode=full for drift tests. Drift is the mean
pairwise distance across N replays of the same test scenario. Low drift means
the candidate's persona is stable across reruns; high drift means the soul is
not load-bearing and the candidate is improvising.

This script uses Jaccard token distance by default (no external deps). If
sentence-transformers is installed, it uses MiniLM embeddings + cosine
distance. The two methods produce directionally comparable but numerically
different scores; the threshold tables below are calibrated for Jaccard.

Usage:
    score_drift.py <json-file>

The JSON file must contain:
    {"responses": ["text 1", "text 2", "text 3"], "consumer_tier": "ic|lead"}

Exit codes:
    0 — drift <= threshold for the consumer tier
    1 — drift above threshold (fail gate)
    2 — usage or input error
"""

import json
import re
import sys
from itertools import combinations
from pathlib import Path

# Calibrated for Jaccard distance on typical IC responses (256-1024 tokens).
THRESHOLDS = {
    "ic":    0.20,  # IC roles — tolerable variance
    "lead":  0.15,  # leads/specialists — tighter persona
    "ceo":   0.10,  # CEO — hardest bar
}

WARN_ZONE = 0.35    # drift in (threshold, WARN_ZONE) is a soft warning
HARD_FAIL = 0.35    # drift > HARD_FAIL always fails regardless of tier


# ---- Tokenization and distance ----

def tokenize(text: str) -> set:
    """Lowercase word-set. Keeps alphanumeric + underscores."""
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def jaccard_distance(a: set, b: set) -> float:
    """1 - |a ∩ b| / |a ∪ b|. Returns 0.0 for two empty sets."""
    if not a and not b:
        return 0.0
    return 1.0 - len(a & b) / len(a | b)


def compute_jaccard_drift(responses: list[str]) -> tuple[float, list[float]]:
    """Mean pairwise Jaccard distance. Returns (mean, per-pair-distances)."""
    if len(responses) < 2:
        return 0.0, []
    token_sets = [tokenize(r) for r in responses]
    pair_dists = [
        jaccard_distance(a, b)
        for a, b in combinations(token_sets, 2)
    ]
    mean = sum(pair_dists) / len(pair_dists)
    return mean, pair_dists


def compute_embedding_drift(responses: list[str]) -> tuple[float, list[float]] | None:
    """Use sentence-transformers if available; return None otherwise."""
    try:
        from sentence_transformers import SentenceTransformer, util  # type: ignore
    except ImportError:
        return None
    if len(responses) < 2:
        return 0.0, []
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(responses, convert_to_tensor=True)
    pair_dists = []
    for i, j in combinations(range(len(responses)), 2):
        cos_sim = float(util.cos_sim(embeddings[i], embeddings[j]))
        # Convert similarity to distance in [0, 1]
        dist = max(0.0, 1.0 - cos_sim)
        pair_dists.append(dist)
    mean = sum(pair_dists) / len(pair_dists)
    return mean, pair_dists


# ---- Main ----

def verdict(drift: float, tier: str) -> dict:
    """Apply threshold table. Returns structured verdict."""
    threshold = THRESHOLDS.get(tier, THRESHOLDS["ic"])
    if drift > HARD_FAIL:
        return {
            "status": "hard_fail",
            "reason": f"drift {drift:.3f} exceeds HARD_FAIL ({HARD_FAIL})",
            "action": "return to design-agent Step 2; persona is unstable",
        }
    if drift > threshold and drift <= WARN_ZONE:
        return {
            "status": "warn",
            "reason": f"drift {drift:.3f} in ({threshold}, {WARN_ZONE}]",
            "action": "tighten exemplars in Soul Section 11; consider re-run",
        }
    if drift > threshold:
        return {
            "status": "fail",
            "reason": f"drift {drift:.3f} above tier threshold {threshold}",
            "action": f"above {tier} threshold; revise or relax tier",
        }
    return {
        "status": "pass",
        "reason": f"drift {drift:.3f} within {tier} threshold {threshold}",
        "action": "continue to deployment",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: score_drift.py <json-file>", file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"error reading input: {e}", file=sys.stderr)
        return 2

    responses = data.get("responses", [])
    tier = data.get("consumer_tier", "ic")
    if not isinstance(responses, list) or len(responses) < 2:
        print("error: responses must be a list of >= 2 strings", file=sys.stderr)
        return 2

    # Prefer embedding-based when available, fall back to Jaccard.
    embed_result = compute_embedding_drift(responses)
    if embed_result is not None:
        drift, pair_dists = embed_result
        method = "embedding-cosine"
    else:
        drift, pair_dists = compute_jaccard_drift(responses)
        method = "jaccard"

    verdict_info = verdict(drift, tier)

    result = {
        "drift": round(drift, 4),
        "method": method,
        "tier": tier,
        "threshold": THRESHOLDS.get(tier, THRESHOLDS["ic"]),
        "n_replays": len(responses),
        "pairwise_distances": [round(d, 4) for d in pair_dists],
        "status": verdict_info["status"],
        "reason": verdict_info["reason"],
        "action": verdict_info["action"],
    }
    print(json.dumps(result, indent=2))
    return 0 if verdict_info["status"] in ("pass", "warn") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
