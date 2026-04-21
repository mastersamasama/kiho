#!/usr/bin/env python3
"""Score a kiho skill description against the 8 effectiveness rules.

Used by skill-create Step 4 (description iterative improvement). The LLM
authors a draft description, runs this script via Bash to get deterministic
scores + diagnoses, then revises based on the failed rules.

Usage:
    score_description.py <description-file-or-literal>
    echo "description text" | score_description.py -

Exit codes:
    0 — score >= 0.85 (passes effectiveness gate)
    1 — score < 0.85 (needs iteration)
    2 — usage error
"""

import json
import re
import sys
from pathlib import Path

# ---- Rule parameters (kiho-specific, tuned 2026) ----

# Heuristic verb list for "concrete action" detection. Matches verb stems, so
# "extract" matches "extract", "extracts", "extracting", "extracted".
CONCRETE_VERBS = {
    "extract", "merge", "split", "create", "fill", "encrypt", "decrypt",
    "read", "write", "parse", "generate", "compile", "validate", "transform",
    "filter", "rotate", "convert", "upload", "download", "render", "compose",
    "resolve", "normalize", "deduplicate", "index", "search", "query", "fetch",
    "retrieve", "register", "deploy", "verify", "audit", "review", "synthesize",
    "capture", "derive", "improve", "spawn", "delegate", "orchestrate", "escalate",
    "detect", "diagnose", "mitigate", "rollback", "promote", "demote", "archive",
    "restore", "backup", "package", "publish", "subscribe", "broadcast", "route",
    "classify", "tag", "annotate", "summarize", "analyze", "measure", "score",
    "rank", "sort", "dedupe", "diff", "patch", "merge", "rebase", "squash",
    "refactor", "decompose", "compose", "mock", "stub", "seed", "scaffold",
}

# Phrases that make the description pushy enough to overcome Claude's
# undertrigger tendency.
#
# "Pushy" here means modal adverbs + direct trigger phrasing like
# "Use this skill whenever ..." — NOT imperative verbs directed at the
# reader. The rule is about making the triggering condition unambiguous
# to the router, not about the grammatical mood of the sentence.
#
# The description should remain in third person (Rule 4 enforces that
# separately). These phrases are third-person-compatible: "Use this
# skill whenever the user ..." is still third person — "the user" is
# the subject, not "you".
#
# Anti-examples (NOT what this rule rewards):
#   - "Extract text from PDFs" (imperative verb, no trigger signal)
#   - "You can extract text" (second person)
#   - "Can be useful for PDFs" (hedged, not pushy)
#
# Good examples:
#   - "Use this skill whenever the user mentions PDFs..."
#   - "Must trigger when the user asks to..."
#   - "Always invoke when the user wants to..."
PUSHY_PHRASES = [
    "whenever", "always use", "must use", "must trigger", "make sure to use",
    "use this skill whenever", "automatically invoke", "triggers on",
    "must invoke", "always invoke", "use when", "must be used",
]

# Phrases that indicate explicit trigger conditions.
TRIGGER_PHRASES = [
    "if the user", "when the user", "use when", "triggers on",
    "use whenever", "whenever the user", "must trigger", "invoked when",
    "user mentions", "user asks", "user wants",
]

# Verbs that are too vague to be load-bearing.
VAGUE_VERBS = {
    "handle", "manage", "process", "work with", "deal with",
    "take care of", "help with", "assist with", "support",
}

# Meta-commentary markers that bloat descriptions without adding trigger signal.
META_MARKERS = [
    "this skill is designed",
    "this skill helps",
    "this skill allows",
    "this skill enables",
    "the purpose of this skill",
    "this skill is for",
    "this skill can",
]

# First-person pronouns (wrong voice).
FIRST_PERSON = [" i ", " me ", " my ", " mine ", " we ", " us ", " our ", " ours "]

# Second-person pronouns (wrong voice).
SECOND_PERSON = [" you ", " your ", " yours ", " yourself "]


# ---- Scoring rules ----

def _padded_lower(desc: str) -> str:
    """Lowercase with leading+trailing space for reliable word-boundary matching."""
    return " " + desc.lower().replace("\n", " ").replace("\t", " ") + " "


def _verb_forms(verb: str) -> list[str]:
    """Generate plausible inflected forms of an English verb stem.

    Handles:
      - base         : extract
      - -s           : extracts
      - -ed          : extracted
      - -ing         : extracting
      - silent-e drop: merge  -> merging, merged
      - consonant db : split  -> splitting, splitted
      - y -> ies     : verify -> verifies, verified
    """
    forms = {verb, verb + "s", verb + "ed", verb + "ing"}
    # silent-e drop: merge -> merg+ing = merging
    if verb.endswith("e"):
        forms.add(verb[:-1] + "ing")
        forms.add(verb[:-1] + "ed")
    # consonant doubling: split -> split+t+ing = splitting
    if (
        len(verb) >= 3
        and verb[-1] in "bdfgklmnprtv"
        and verb[-2] in "aeiou"
        and verb[-3] not in "aeiou"
    ):
        forms.add(verb + verb[-1] + "ing")
        forms.add(verb + verb[-1] + "ed")
    # y -> ies: verify -> verifies
    if verb.endswith("y") and len(verb) > 1 and verb[-2] not in "aeiou":
        forms.add(verb[:-1] + "ies")
        forms.add(verb[:-1] + "ied")
    return sorted(forms, key=len, reverse=True)  # longest first for regex alternation


# Pre-compile a single alternation regex covering all CONCRETE_VERBS + forms.
_ALL_VERB_FORMS = set()
for _v in CONCRETE_VERBS:
    _ALL_VERB_FORMS.update(_verb_forms(_v))
_VERB_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(_ALL_VERB_FORMS, key=len, reverse=True)) + r")\b"
)


def rule_1_concrete_actions(desc: str) -> tuple[bool, str]:
    """Enumerates >= 5 distinct concrete action verbs (any inflected form)."""
    lower = _padded_lower(desc)
    hits = set(_VERB_PATTERN.findall(lower))
    # Map hits back to stems for dedup (merging/merged/merges → merge).
    stems = set()
    for verb in CONCRETE_VERBS:
        forms = _verb_forms(verb)
        if any(form in hits for form in forms):
            stems.add(verb)
    passed = len(stems) >= 5
    if passed:
        return True, f"found {len(stems)} distinct action verbs"
    return False, (
        f"only {len(stems)} distinct action verbs (need >= 5); "
        f"add verbs like extract, merge, validate, generate, deploy"
    )


def rule_2_trigger_phrases(desc: str) -> tuple[bool, str]:
    """Contains at least one explicit trigger phrase."""
    lower = _padded_lower(desc)
    found = [p for p in TRIGGER_PHRASES if p in lower]
    if found:
        return True, f"trigger phrases present: {found[:3]}"
    return False, (
        "no explicit trigger phrase; add 'use when X', 'if the user Y', "
        "'triggers on Z', or 'whenever the user W'"
    )


def rule_3_pushy_language(desc: str) -> tuple[bool, str]:
    """Uses pushy language (modal adverbs in trigger phrasing) to combat undertrigger.

    NOT a test for imperative verbs — third-person is enforced by Rule 4.
    See the PUSHY_PHRASES docstring for rationale and examples.
    """
    lower = _padded_lower(desc)
    found = [p for p in PUSHY_PHRASES if p in lower]
    if found:
        return True, f"pushy markers present: {found[:3]}"
    return False, (
        "no pushy trigger phrasing; add 'whenever the user ...', "
        "'must trigger when ...', 'always invoke when ...' (keep third-person)"
    )


def rule_4_third_person(desc: str) -> tuple[bool, str]:
    """No first-person or second-person pronouns."""
    lower = _padded_lower(desc)
    first_hits = [p.strip() for p in FIRST_PERSON if p in lower]
    second_hits = [p.strip() for p in SECOND_PERSON if p in lower]
    if not first_hits and not second_hits:
        return True, "third-person only"
    problems = []
    if first_hits:
        problems.append(f"first-person: {first_hits}")
    if second_hits:
        problems.append(f"second-person: {second_hits}")
    return False, f"wrong voice — {'; '.join(problems)}"


def rule_5_single_paragraph(desc: str) -> tuple[bool, str]:
    """Description is a single paragraph (no blank lines)."""
    if "\n\n" in desc:
        return False, "description spans multiple paragraphs; combine into one"
    return True, "single paragraph"


def rule_6_length(desc: str) -> tuple[bool, str]:
    """Length between 50 and 1024 characters."""
    n = len(desc)
    if 50 <= n <= 1024:
        return True, f"length {n} chars (in [50, 1024])"
    if n < 50:
        return False, f"length {n} too short (need >= 50)"
    return False, f"length {n} too long (need <= 1024)"


def rule_7_no_vague_verbs(desc: str) -> tuple[bool, str]:
    """No vague verbs like handle, manage, process, work with."""
    lower = _padded_lower(desc)
    hits = [v for v in VAGUE_VERBS if v in lower]
    if hits:
        return False, f"vague verbs detected: {hits}; replace with concrete actions"
    return True, "no vague verbs"


def rule_8_no_meta_commentary(desc: str) -> tuple[bool, str]:
    """No meta-commentary ('this skill is designed to...')."""
    lower = desc.lower()
    hits = [m for m in META_MARKERS if m in lower]
    if hits:
        return False, f"meta-commentary detected: {hits[0]!r}; describe actions directly"
    return True, "no meta-commentary"


RULES = [
    ("r1_concrete_actions",  "Enumerates >= 5 concrete action verbs",      rule_1_concrete_actions),
    ("r2_trigger_phrases",   "Contains explicit trigger phrase(s)",         rule_2_trigger_phrases),
    ("r3_pushy_language",    "Uses pushy language (whenever/must/always)",  rule_3_pushy_language),
    ("r4_third_person",      "Third person only (no I/you pronouns)",       rule_4_third_person),
    ("r5_single_paragraph",  "Single paragraph (no blank lines)",           rule_5_single_paragraph),
    ("r6_length",            "Length between 50 and 1024 characters",       rule_6_length),
    ("r7_no_vague_verbs",    "No vague verbs (handle, manage, process)",    rule_7_no_vague_verbs),
    ("r8_no_meta_commentary","No meta-commentary (this skill is designed)", rule_8_no_meta_commentary),
]

PASS_THRESHOLD = 0.85


def score_description(desc: str) -> dict:
    """Score a description; return rule results, score, and diagnoses."""
    desc = desc.strip()
    results = {}
    diagnoses = []
    for key, _, rule_fn in RULES:
        try:
            passed, detail = rule_fn(desc)
        except Exception as e:
            passed = False
            detail = f"rule error: {e}"
        results[key] = passed
        if not passed:
            diagnoses.append(f"{key}: {detail}")
    score = sum(results.values()) / len(RULES)
    return {
        "score": round(score, 3),
        "threshold": PASS_THRESHOLD,
        "passed": score >= PASS_THRESHOLD,
        "rule_count": len(RULES),
        "rules_passed": sum(results.values()),
        "results": results,
        "diagnoses": diagnoses,
        "description_length": len(desc),
    }


def _read_input(arg: str) -> str:
    """Read description from file, stdin (-), or literal string."""
    if arg == "-":
        return sys.stdin.read()
    path = Path(arg)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return arg


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "Usage: score_description.py <description-file-or-literal-or-'-'>",
            file=sys.stderr,
        )
        return 2
    try:
        desc = _read_input(argv[1])
    except OSError as e:
        print(f"error reading input: {e}", file=sys.stderr)
        return 2
    result = score_description(desc)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
