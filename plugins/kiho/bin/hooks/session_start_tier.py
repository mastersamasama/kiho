#!/usr/bin/env python3
"""SessionStart hook: remind CEO to declare tier on first /kiho turn.

This hook runs once at session start. It emits a short reminder to stderr that
Claude Code surfaces to the model: when the user invokes /kiho (with or without
--tier), the CEO's first visible line must be `TIER: <minimal|normal|careful>`
followed by a one-line rationale, and the first ledger entry of the turn must
be `action: tier_declared`.

The hook is intentionally non-blocking — it always exits 0. It's a nudge, not a
gate. The gate for tier enforcement lives in the CEO persona (agents/kiho-ceo.md
§INITIALIZE) and is audited by bin/ceo_behavior_audit.py.

Stdin JSON (SessionStart schema): { "session_id": "...", "hook_event_name":
"SessionStart", ... }. We don't use any of it — the hook is stateless.
"""
from __future__ import annotations

import sys

REMINDER = """\
[kiho v5.22] If the user invokes /kiho (any form) in this session, declare the
operating tier as the very first visible line of the CEO response:

    TIER: minimal | normal | careful
    (one-line rationale)

Then log `action: tier_declared, value: <tier>` as the first ledger entry of
the turn, BEFORE any delegation. Default is `normal` unless the user passed
`--tier=...`. See skills/kiho/SKILL.md §"Tier discipline (v5.22)" for the
minimal/normal/careful discipline table.
"""


def main() -> int:
    # Drain stdin to avoid a broken pipe on some platforms; we don't read it.
    try:
        sys.stdin.read()
    except OSError:
        pass
    sys.stderr.write(REMINDER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
