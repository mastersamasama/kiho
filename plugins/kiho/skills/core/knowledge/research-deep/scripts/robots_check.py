#!/usr/bin/env python3
"""Check robots.txt compliance for research-deep seed URLs.

Used by research-deep before fetching any seed URL. Fails open (allowed=True)
if robots.txt is unreachable — research-deep logs the failure but proceeds.
Fails closed (allowed=False) if robots.txt explicitly disallows the path.

Usage:
    robots_check.py <url> [<url>...]

Output: JSON array, one entry per URL, with allowed/crawl_delay/error fields.

Exit codes:
    0 — all URLs allowed
    1 — at least one URL disallowed
    2 — usage error
"""

import json
import sys
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

# Match the User-Agent advertised by research-deep in WebFetch calls.
USER_AGENT = "kiho-research-deep/0.4 (+https://github.com/wky/kiho)"


def check_allowed(url: str) -> dict:
    """Fetch robots.txt for url's host, return compliance info."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return {
            "url": url,
            "robots_url": None,
            "allowed": False,
            "crawl_delay_s": None,
            "error": "invalid URL: missing scheme or host",
        }

    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)

    try:
        rp.read()
    except Exception as e:
        # Fail open: if robots.txt is unreachable, assume allowed but record.
        return {
            "url": url,
            "robots_url": robots_url,
            "allowed": True,
            "crawl_delay_s": None,
            "error": f"robots.txt unreachable: {e}",
            "fail_mode": "open",
        }

    try:
        allowed = rp.can_fetch(USER_AGENT, url)
    except Exception as e:
        return {
            "url": url,
            "robots_url": robots_url,
            "allowed": False,
            "crawl_delay_s": None,
            "error": f"robots.txt parse error: {e}",
            "fail_mode": "closed",
        }

    crawl_delay = None
    try:
        raw_delay = rp.crawl_delay(USER_AGENT)
        if raw_delay is not None:
            crawl_delay = float(raw_delay)
    except Exception:
        # Non-fatal; some robots.txt don't declare crawl_delay.
        pass

    return {
        "url": url,
        "robots_url": robots_url,
        "allowed": allowed,
        "crawl_delay_s": crawl_delay,
        "error": None,
        "fail_mode": None,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: robots_check.py <url> [<url>...]", file=sys.stderr)
        return 2

    results = [check_allowed(u) for u in argv[1:]]
    any_disallowed = any(not r["allowed"] for r in results)

    summary = {
        "user_agent": USER_AGENT,
        "url_count": len(results),
        "allowed_count": sum(1 for r in results if r["allowed"]),
        "disallowed_count": sum(1 for r in results if not r["allowed"]),
        "results": results,
    }
    print(json.dumps(summary, indent=2))
    return 1 if any_disallowed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
