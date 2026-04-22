#!/usr/bin/env python3
"""PreToolUse gate: block direct Writes to agent.md files.

Enforces kiho v5.22 invariant "Never write to $COMPANY_ROOT/agents/*/agent.md directly."
The recruit skill (quick-hire or careful-hire) is the only sanctioned path. Recruit
emits agent.md with a RECRUIT_CERTIFICATE marker at the top of the file as an HTML
comment — this hook lets that Write through. Any other Write to an agent.md path is
blocked with stderr feedback so Claude re-routes through `recruit`.

Defense in depth: the audit script `bin/ceo_behavior_audit.py` verifies that Writes
bearing a RECRUIT_CERTIFICATE also have the supporting role-spec / interview-simulate
artifacts on disk. A bare marker without artifacts is still flagged as drift.

Stdin JSON (PreToolUse schema): {
  "tool_name": "Write",
  "tool_input": { "file_path": "...", "content": "..." },
  ...
}

Exit codes:
  0 — allow
  2 — block (stderr is shown to Claude as the reason)
"""
from __future__ import annotations

import json
import re
import sys

AGENT_PATH_RE = re.compile(
    r".*[/\\](kiho[/\\]agents|agents)[/\\][^/\\]+[/\\]agent\.md$",
    re.IGNORECASE,
)
CERT_MARKER = "RECRUIT_CERTIFICATE:"

BLOCK_MESSAGE = """\
[kiho v5.22 gate] Direct Write to agent.md is blocked.

New agents MUST pass through the `recruit` skill:
  - quick-hire: 2 candidates + mini-committee (for straightforward roles)
  - careful-hire: 4 candidates x 6 rounds x 4 auditors + full committee (for
    lead/senior/safety-critical roles)

Why: direct Write bypasses role-spec, interview-simulate, rubric, and auditor
review — the four mechanisms that catch bad agent design.

If you have already completed the recruit skill this turn and this Write is the
final materialization, include the provenance marker at the top of the file as
an HTML comment, for example:

    <!-- RECRUIT_CERTIFICATE:
           kind: quick-hire
           role_spec: _meta-runtime/role-specs/<slug>/role-spec.md
           interview_score: 3.85
           committee_status: approved
           emitted_at: <iso_ts>
    -->

Otherwise: abort this Write and invoke `recruit` first. The recruit skill
produces the agent.md itself, with the marker included.

The audit script `bin/ceo_behavior_audit.py` verifies on DONE that the marker
is backed by real role-spec / interview artifacts — fake markers are caught.
"""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not AGENT_PATH_RE.match(file_path):
        return 0

    content = tool_input.get("content") or ""
    if CERT_MARKER in content:
        return 0

    sys.stderr.write(BLOCK_MESSAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main())
