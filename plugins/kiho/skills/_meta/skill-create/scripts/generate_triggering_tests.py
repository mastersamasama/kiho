#!/usr/bin/env python3
"""Generate a 20-prompt triggering corpus for a new skill.

Produces exactly 10 should-trigger prompts and 10 should-not-trigger prompts
from the skill's intent, use cases, and trigger phrases. The corpus is
consumed by improve_description.py (as train/test data) and by Step 9 of
skill-create (as eval cases for triggering_accuracy test).

Design choices:

  * Deterministic. Same input → same 20 prompts. Seed from input hash so
    re-runs produce comparable output. This is deliberate: the test set must
    be stable across iterations of improve_description.py for train/test
    split to work correctly.

  * Templated. The LLM running skill-create can pre-generate richer prompts
    via its own reasoning, but this script provides a structural baseline
    that always produces a valid 10+10 corpus even without LLM calls. Think
    of it as scaffolding, not the ground truth.

  * Should-not-trigger prompts are "adjacent but out of scope" — they use
    the same verbs or domain nouns as the skill but target a different
    operation or domain. This catches over-broad descriptions.

Usage:
    generate_triggering_tests.py <input.json>

input.json schema:
    {
      "intent": "extract text from scanned PDFs",
      "use_cases": ["OCR", "layout preservation", "table extraction"],
      "trigger_phrases": ["scan PDF", "OCR document", "read scanned file"],
      "domain": "engineering"      # optional, for out-of-scope generation
    }

Exit codes:
    0 — corpus generated successfully
    2 — usage or input error
"""

import hashlib
import json
import random
import re
import sys
from pathlib import Path

N_POSITIVE = 10
N_NEGATIVE = 10


# Prompt templates for "should trigger" cases. Each takes {intent}, {uc}
# (use case), or {trigger} (trigger phrase) as a placeholder. They're
# designed to cover varied natural phrasings a real user might type.

POSITIVE_TEMPLATES = [
    # Direct invocation
    "{trigger}",
    "Can you {intent}?",
    "I need to {intent}.",
    "Please {intent} for me.",
    # Use-case framing
    "How do I {uc}?",
    "Help me with {uc}.",
    "What's the best way to {uc}?",
    # Context framing
    "I'm working on a project that needs to {intent}.",
    "My task is to {intent} — where do I start?",
    "I want to {uc} — is there a tool for that?",
    # Casual paraphrase
    "Any way to {intent}?",
    "Got a workflow for {uc}?",
    # Typo / informal
    "i want to {intent}",
    "pls help me {uc}",
]

# Templates for "should NOT trigger" cases. These reuse some terms from the
# skill's domain but target a different operation or scope.

NEGATIVE_TEMPLATES = [
    # Similar verb, wrong object
    "Can you {verb} the {other_thing}?",
    "Help me {verb} a {other_thing}.",
    # Same domain, unrelated operation
    "What is {domain_noun}?",
    "Explain how {domain_noun} works.",
    "Write documentation for {other_thing}.",
    # Superficial keyword overlap
    "Delete all the {domain_noun}s.",
    "List my {other_thing}s.",
    "Count the {other_thing}s.",
    # Meta / out-of-scope
    "Tell me a joke.",
    "What's the weather today?",
    "Who won the game last night?",
    # Adjacent domain
    "Help me write an email.",
    "Review my resume.",
    "Schedule a meeting.",
]

# Domain-specific "other things" for negative prompts — used to construct
# superficially-similar but out-of-scope prompts. Chosen to be clearly
# distinct from common skill domains.

DOMAIN_ADJACENT = {
    "_meta":       ["meeting agenda", "presentation slide", "blog post", "newsletter"],
    "core":        ["spreadsheet row", "calendar entry", "contact list", "shopping list"],
    "kb":          ["physical book", "filing cabinet", "library card", "magazine subscription"],
    "memory":      ["photo album", "music playlist", "video clip", "voice memo"],
    "engineering": ["recipe ingredient", "hardware receipt", "furniture assembly instructions", "clothing tag"],
    "unknown":     ["random object", "coffee order", "parking ticket", "grocery item"],
}


def _seed_from_inputs(intent: str, use_cases: list[str]) -> int:
    """Deterministic seed so re-runs produce the same corpus."""
    material = intent + "|" + "|".join(use_cases)
    h = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFFFFFF


def _first_verb(text: str) -> str:
    """Return the first likely verb in a phrase; fall back to the first word."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    if not words:
        return "do"
    # Heuristic: first word is usually the verb in an imperative intent.
    return words[0]


def _first_noun(text: str) -> str:
    """Return the most-likely-noun token (non-stop, longest of last 3 words)."""
    stop = {"a", "an", "the", "to", "of", "in", "on", "at", "for", "with",
            "from", "it", "this", "that", "and", "or"}
    words = re.findall(r"[a-zA-Z]+", text.lower())
    candidates = [w for w in words[-4:] if w not in stop and len(w) >= 3]
    if candidates:
        return max(candidates, key=len)
    return words[-1] if words else "thing"


def generate_positive(rng: random.Random, intent: str, use_cases: list[str], triggers: list[str]) -> list[str]:
    """Generate N_POSITIVE should-trigger prompts."""
    if not use_cases:
        use_cases = [intent]
    if not triggers:
        triggers = [intent]

    prompts: list[str] = []
    templates = POSITIVE_TEMPLATES[:]
    rng.shuffle(templates)

    attempts = 0
    while len(prompts) < N_POSITIVE and attempts < N_POSITIVE * 4:
        template = templates[attempts % len(templates)]
        filled = template.format(
            intent=intent,
            uc=rng.choice(use_cases),
            trigger=rng.choice(triggers),
        )
        filled = filled[:1].upper() + filled[1:] if filled else filled
        if filled not in prompts:
            prompts.append(filled)
        attempts += 1

    return prompts[:N_POSITIVE]


def generate_negative(
    rng: random.Random,
    intent: str,
    use_cases: list[str],   # noqa: ARG001 — reserved for domain-term extraction
    domain: str,
) -> list[str]:
    """Generate N_NEGATIVE should-NOT-trigger prompts.

    use_cases is accepted for forward compatibility; the current template
    approach derives negative prompts from intent + domain only.
    """
    del use_cases
    adjacent = DOMAIN_ADJACENT.get(domain, DOMAIN_ADJACENT["unknown"])
    verb = _first_verb(intent)
    domain_noun = _first_noun(intent)

    prompts: list[str] = []
    templates = NEGATIVE_TEMPLATES[:]
    rng.shuffle(templates)

    attempts = 0
    while len(prompts) < N_NEGATIVE and attempts < N_NEGATIVE * 4:
        template = templates[attempts % len(templates)]
        filled = template.format(
            verb=verb,
            other_thing=rng.choice(adjacent),
            domain_noun=domain_noun,
        )
        filled = filled[:1].upper() + filled[1:] if filled else filled
        if filled not in prompts:
            prompts.append(filled)
        attempts += 1

    return prompts[:N_NEGATIVE]


def generate_corpus(intent: str, use_cases: list[str], triggers: list[str], domain: str) -> dict:
    seed = _seed_from_inputs(intent, use_cases)
    rng = random.Random(seed)
    return {
        "should_trigger":     generate_positive(rng, intent, use_cases, triggers),
        "should_not_trigger": generate_negative(rng, intent, use_cases, domain),
        "seed": seed,
        "generator": "kiho-skill-create/generate_triggering_tests.py",
        "note": (
            "Deterministic corpus derived from intent + use_cases. "
            "Re-runs with the same inputs produce the same 20 prompts. "
            "The LLM running skill-create MAY augment this corpus with "
            "richer prompts, but the test set (held out during "
            "improve_description.py) must remain stable across iterations."
        ),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: generate_triggering_tests.py <input.json>", file=sys.stderr)
        return 2

    try:
        data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"error reading input: {e}", file=sys.stderr)
        return 2

    intent = data.get("intent", "").strip()
    if not intent:
        print("error: intent is required", file=sys.stderr)
        return 2

    use_cases = data.get("use_cases", [])
    triggers = data.get("trigger_phrases", [])
    domain = data.get("domain", "unknown")

    corpus = generate_corpus(intent, use_cases, triggers, domain)

    # Invariants — the consumer (improve_description.py) assumes exactly
    # 10 + 10. Fail loudly if we couldn't fill the corpus.
    if len(corpus["should_trigger"]) != N_POSITIVE:
        print(
            f"error: only {len(corpus['should_trigger'])} positive prompts "
            f"generated (need {N_POSITIVE}); check use_cases and trigger_phrases",
            file=sys.stderr,
        )
        return 2
    if len(corpus["should_not_trigger"]) != N_NEGATIVE:
        print(
            f"error: only {len(corpus['should_not_trigger'])} negative prompts "
            f"generated (need {N_NEGATIVE})",
            file=sys.stderr,
        )
        return 2

    print(json.dumps(corpus, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
