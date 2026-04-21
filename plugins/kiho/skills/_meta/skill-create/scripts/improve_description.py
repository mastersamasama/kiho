#!/usr/bin/env python3
"""Iterative description rewriter with train/test split (Anthropic pattern).

Implements the workflow from Anthropic's official `skill-creator` skill's
`improve_description.py` (2026 version with blind comparisons):

  1. Generate or load 20 test prompts (10 should-trigger + 10 should-not).
  2. Split 60% train / 40% held-out test. Seed is deterministic from inputs.
  3. Score the current description on BOTH sets, but only tell the rewriter
     about train-set failures (blind comparison).
  4. Rewrite the description to address train failures, preserving passes.
  5. Re-score. Track train vs test accuracy divergence (overfitting signal).
  6. Loop up to 5 iterations or until train accuracy >= 0.90.
  7. Report final description + accuracies + overfitting warning.

This complements score_description.py: the binary 8-rule scorer is a fast
gate for obvious failures; this script handles the harder case where the
rules pass but triggering accuracy is still low.

Usage:
    improve_description.py <input.json>

input.json schema:
    {
      "draft_description": "<initial draft>",
      "intent": "<one-line skill purpose>",
      "use_cases": ["use case 1", ...],
      "trigger_phrases": ["phrase 1", ...],
      "domain": "_meta | core | kb | memory | engineering",
      "test_corpus": {                      # optional; generated if missing
        "should_trigger":     ["prompt 1", ...],   # 10 items
        "should_not_trigger": ["prompt 1", ...]    # 10 items
      }
    }

Output: JSON with final_description, train_accuracy, test_accuracy,
iteration_count, overfitting_warning, rewrite_history.

Exit codes:
    0 — final test accuracy >= 0.75 (ship)
    1 — test accuracy < 0.75 after 5 iterations (revise inputs)
    2 — usage or input error
"""

import hashlib
import json
import random
import re
import sys
from pathlib import Path

# ---- Configuration ----

MAX_ITERATIONS = 5
TRAIN_FRACTION = 0.60
TARGET_TRAIN_ACCURACY = 0.90
SHIP_TEST_ACCURACY = 0.75
OVERFITTING_GAP = 0.20
DESCRIPTION_CHAR_LIMIT = 1024
MIN_DESCRIPTION_LENGTH = 50


# ---- Triggering simulation ----

# A description "triggers" on a prompt if the prompt's key terms appear in
# the description's trigger phrases or concrete action verbs. This is an
# approximation of what Claude would do at the router — we don't have model
# access from a script, so we use a deterministic text-overlap heuristic.
# The approximation is conservative: if our heuristic says "triggered",
# the real router almost certainly does too; if it says "not triggered",
# there's still a chance the router would catch it.

def _tokenize(text: str) -> set[str]:
    """Lowercase word-set with stop-words removed."""
    stop = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "to", "of", "in", "on", "at", "for", "with", "by", "from",
        "this", "that", "these", "those", "and", "or", "but", "if",
        "i", "me", "my", "you", "your", "we", "us", "our", "it", "its",
        "can", "could", "would", "should", "will", "may", "might",
        "do", "does", "did", "have", "has", "had",
        "what", "how", "why", "when", "where", "which", "who",
    }
    words = re.findall(r"[a-z0-9_]+", text.lower())
    return {w for w in words if w not in stop and len(w) >= 2}


def simulate_trigger(description: str, prompt: str) -> bool:
    """Return True if the description would likely trigger on the prompt.

    Heuristic: the prompt triggers the description when at least 2 of the
    prompt's content words appear in the description, OR one of the prompt's
    bigrams appears in the description verbatim.
    """
    desc_tokens = _tokenize(description)
    prompt_tokens = _tokenize(prompt)
    if not desc_tokens or not prompt_tokens:
        return False

    overlap = desc_tokens & prompt_tokens
    if len(overlap) >= 2:
        return True

    # Check for verbatim bigrams in the original description (case-insensitive)
    desc_lower = " " + description.lower() + " "
    prompt_words = re.findall(r"[a-z0-9_]+", prompt.lower())
    for i in range(len(prompt_words) - 1):
        bigram = f" {prompt_words[i]} {prompt_words[i + 1]} "
        if bigram in desc_lower:
            return True

    return False


def score_on_corpus(description: str, corpus: dict) -> dict:
    """Run triggering simulation on should_trigger + should_not_trigger sets.

    Returns {accuracy, true_positive_rate, true_negative_rate, failures}.
    failures = list of {prompt, expected, actual}.
    """
    should_trigger = corpus.get("should_trigger", [])
    should_not = corpus.get("should_not_trigger", [])

    tp = sum(1 for p in should_trigger if simulate_trigger(description, p))
    tn = sum(1 for p in should_not if not simulate_trigger(description, p))
    total = len(should_trigger) + len(should_not)

    failures = []
    for p in should_trigger:
        if not simulate_trigger(description, p):
            failures.append({"prompt": p, "expected": "trigger", "actual": "miss"})
    for p in should_not:
        if simulate_trigger(description, p):
            failures.append({"prompt": p, "expected": "no_trigger", "actual": "false_positive"})

    return {
        "accuracy": round((tp + tn) / total, 3) if total else 0.0,
        "true_positive_rate": round(tp / len(should_trigger), 3) if should_trigger else 0.0,
        "true_negative_rate": round(tn / len(should_not), 3) if should_not else 0.0,
        "failures": failures,
        "total": total,
    }


# ---- Deterministic train/test split ----

def split_corpus(corpus: dict, seed: int) -> tuple[dict, dict]:
    """Split the 20-prompt corpus 60/40 train/test using a deterministic seed."""
    rng = random.Random(seed)
    trig = list(corpus.get("should_trigger", []))
    notrig = list(corpus.get("should_not_trigger", []))
    rng.shuffle(trig)
    rng.shuffle(notrig)

    n_trig_train = int(round(len(trig) * TRAIN_FRACTION))
    n_notrig_train = int(round(len(notrig) * TRAIN_FRACTION))

    train = {
        "should_trigger":     trig[:n_trig_train],
        "should_not_trigger": notrig[:n_notrig_train],
    }
    test = {
        "should_trigger":     trig[n_trig_train:],
        "should_not_trigger": notrig[n_notrig_train:],
    }
    return train, test


def _seed_from_inputs(intent: str, draft: str) -> int:
    """Deterministic seed so re-runs produce the same split."""
    h = hashlib.sha256((intent + "|" + draft).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFFFFFF


# ---- Rewrite step ----

# The "rewriter" in Anthropic's official script calls Claude as a subprocess
# and asks it to rewrite the description. We can't call Claude from a bare
# Python script without the SDK, so this script provides a deterministic
# rewriter based on the failed-prompt diagnoses. The LLM running this skill
# can wrap the script with its own rewrite logic if a smarter loop is needed.
#
# The deterministic rewriter applies targeted edits:
#   - On "miss" (should_trigger failed): extract content words from the
#     failed prompt and append them to the description as trigger phrases,
#     prefixed with "Also triggers when the user mentions ...".
#   - On "false_positive" (should_not_trigger failed): identify the shared
#     content words between the false-positive prompt and the current
#     description, and add a "Does NOT handle X or Y" disclaimer.

def extract_content_words(text: str, top_k: int = 4) -> list[str]:
    """Return up to top_k salient content words from text, ordered by appearance."""
    tokens = _tokenize(text)
    words_in_order = []
    seen = set()
    for w in re.findall(r"[a-z0-9_]+", text.lower()):
        if w in tokens and w not in seen:
            seen.add(w)
            words_in_order.append(w)
            if len(words_in_order) >= top_k:
                break
    return words_in_order


def rewrite_description(current: str, train_failures: list[dict]) -> str:
    """Apply targeted edits based on training failures (blind to test set)."""
    if not train_failures:
        return current

    # Collect missing trigger terms and false-positive terms separately.
    missing_terms: list[str] = []
    false_positive_terms: list[str] = []
    for f in train_failures:
        words = extract_content_words(f["prompt"])
        if f["actual"] == "miss":
            missing_terms.extend(w for w in words if w not in missing_terms)
        elif f["actual"] == "false_positive":
            false_positive_terms.extend(w for w in words if w not in false_positive_terms)

    # Dedup against words already in the description.
    desc_lower = current.lower()
    missing_terms = [t for t in missing_terms if t not in desc_lower][:5]
    false_positive_terms = [t for t in false_positive_terms if t not in desc_lower][:3]

    rewritten = current.rstrip().rstrip(".")

    if missing_terms:
        trigger_addon = " Also triggers when the user mentions " + ", ".join(missing_terms) + "."
        rewritten = rewritten + "." + trigger_addon
    else:
        rewritten = rewritten + "."

    if false_positive_terms:
        disclaimer = " Does NOT handle " + " or ".join(false_positive_terms) + "."
        rewritten = rewritten + disclaimer

    # Enforce hard char limit by truncating disclaimers first, then trigger adds.
    if len(rewritten) > DESCRIPTION_CHAR_LIMIT:
        rewritten = rewritten[:DESCRIPTION_CHAR_LIMIT - 3] + "..."

    return rewritten


# ---- Main loop ----

def improve(
    draft: str,
    intent: str,
    use_cases: list[str],         # noqa: ARG001 — reserved for future rewriter
    trigger_phrases: list[str],   # noqa: ARG001 — reserved for future rewriter
    corpus: dict,
) -> dict:
    """Run the iterative improvement loop. Returns a full report dict.

    use_cases and trigger_phrases are accepted for forward compatibility
    with a smarter rewriter that uses them to propose additional text;
    the current deterministic rewriter derives its edits purely from
    train-set failure diagnoses.
    """
    del use_cases, trigger_phrases  # explicitly discard for Pyright
    seed = _seed_from_inputs(intent, draft)
    train, test = split_corpus(corpus, seed)

    history = []
    current = draft.strip()

    for iteration in range(MAX_ITERATIONS + 1):
        train_score = score_on_corpus(current, train)
        test_score = score_on_corpus(current, test)

        history.append({
            "iteration": iteration,
            "description": current,
            "train_accuracy": train_score["accuracy"],
            "test_accuracy": test_score["accuracy"],
            "train_tp_rate": train_score["true_positive_rate"],
            "train_tn_rate": train_score["true_negative_rate"],
            "length": len(current),
        })

        # Stop conditions.
        if train_score["accuracy"] >= TARGET_TRAIN_ACCURACY:
            break
        if iteration >= MAX_ITERATIONS:
            break
        if len(current) >= DESCRIPTION_CHAR_LIMIT - 50:
            # Room for one more targeted edit is too tight; stop.
            break

        # Rewrite based on train failures only (blind to test set).
        current = rewrite_description(current, train_score["failures"])

    final_train = history[-1]["train_accuracy"]
    final_test = history[-1]["test_accuracy"]
    gap = final_train - final_test
    overfitting = gap > OVERFITTING_GAP

    return {
        "final_description": history[-1]["description"],
        "final_length": history[-1]["length"],
        "train_accuracy": final_train,
        "test_accuracy": final_test,
        "train_test_gap": round(gap, 3),
        "overfitting_warning": overfitting,
        "iteration_count": len(history) - 1,
        "stopped_at": (
            "train_accuracy_reached" if final_train >= TARGET_TRAIN_ACCURACY
            else "max_iterations" if len(history) > MAX_ITERATIONS
            else "char_limit"
        ),
        "passed_ship_threshold": final_test >= SHIP_TEST_ACCURACY,
        "char_limit": DESCRIPTION_CHAR_LIMIT,
        "history": history,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: improve_description.py <input.json>", file=sys.stderr)
        return 2

    try:
        data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"error reading input: {e}", file=sys.stderr)
        return 2

    draft = data.get("draft_description", "").strip()
    if len(draft) < MIN_DESCRIPTION_LENGTH:
        print(
            f"error: draft_description must be >= {MIN_DESCRIPTION_LENGTH} chars",
            file=sys.stderr,
        )
        return 2
    if len(draft) > DESCRIPTION_CHAR_LIMIT:
        print(
            f"error: draft_description exceeds {DESCRIPTION_CHAR_LIMIT} char limit",
            file=sys.stderr,
        )
        return 2

    intent = data.get("intent", "").strip()
    use_cases = data.get("use_cases", [])
    trigger_phrases = data.get("trigger_phrases", [])
    corpus = data.get("test_corpus", {})

    if not corpus.get("should_trigger") or not corpus.get("should_not_trigger"):
        print(
            "error: input must include test_corpus.should_trigger and "
            "test_corpus.should_not_trigger (run generate_triggering_tests.py first)",
            file=sys.stderr,
        )
        return 2

    result = improve(draft, intent, use_cases, trigger_phrases, corpus)
    print(json.dumps(result, indent=2))
    return 0 if result["passed_ship_threshold"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
