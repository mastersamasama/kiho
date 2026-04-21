#!/usr/bin/env python3
"""Count tokens in a SKILL.md body for Gate 3 budget enforcement.

Prefers tiktoken (cl100k_base) when installed. Falls back to a
word-count * 1.3 estimate when tiktoken is unavailable.

Gate 3 budget:
    pass  : < 4000 tokens
    warn  : 4000 - 5000 tokens
    reject: > 6000 tokens
    hard  : > 8000 tokens (likely needs to split into multiple skills)

Usage:
    count_tokens.py <file-path>
    count_tokens.py -                 # read from stdin

Exit codes:
    0 — pass or warn (< 6000 tokens)
    1 — reject (>= 6000 tokens)
    2 — usage error
"""

import json
import sys
from pathlib import Path

WARN_MIN = 4000
WARN_MAX = 5000
REJECT_MIN = 6000
HARD_LIMIT = 8000


def count_tokens(text: str) -> tuple[int, str]:
    """Return (token_count, method_used)."""
    try:
        import tiktoken  # type: ignore
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)), "tiktoken_cl100k_base"
    except ImportError:
        # Fallback heuristic: ~1.3 tokens per word for English prose;
        # higher for code-dense content. This is deliberately conservative.
        word_count = len(text.split())
        return int(word_count * 1.3), "word_count_x_1.3_estimate"


def classify(token_count: int) -> dict:
    """Apply the Gate 3 budget table."""
    if token_count >= HARD_LIMIT:
        return {
            "verdict": "hard_reject",
            "reason": f"{token_count} tokens >= hard limit {HARD_LIMIT}",
            "action": "split this skill into multiple narrower skills",
        }
    if token_count >= REJECT_MIN:
        return {
            "verdict": "reject",
            "reason": f"{token_count} tokens >= reject threshold {REJECT_MIN}",
            "action": "move detail into references/ subdirectory or prune the body",
        }
    if token_count >= WARN_MIN:
        return {
            "verdict": "warn",
            "reason": f"{token_count} tokens in [{WARN_MIN}, {WARN_MAX}] — approaching budget",
            "action": "consider moving one section to references/ before reject threshold",
        }
    return {
        "verdict": "pass",
        "reason": f"{token_count} tokens < {WARN_MIN}",
        "action": "continue",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: count_tokens.py <file-path-or-'-'>", file=sys.stderr)
        return 2

    arg = argv[1]
    try:
        text = sys.stdin.read() if arg == "-" else Path(arg).read_text(encoding="utf-8")
    except OSError as e:
        print(f"error reading input: {e}", file=sys.stderr)
        return 2

    token_count, method = count_tokens(text)
    verdict = classify(token_count)

    result = {
        "token_count": token_count,
        "method": method,
        "verdict": verdict["verdict"],
        "reason": verdict["reason"],
        "action": verdict["action"],
        "thresholds": {
            "warn_min": WARN_MIN,
            "warn_max": WARN_MAX,
            "reject_min": REJECT_MIN,
            "hard_limit": HARD_LIMIT,
        },
    }
    print(json.dumps(result, indent=2))
    return 1 if verdict["verdict"] in ("reject", "hard_reject") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
