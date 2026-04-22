#!/usr/bin/env python3
"""PreToolUse gate: block direct Write/Edit to .kiho/kb/wiki/*.md.

Enforces kiho v5.22 invariant "kb-manager is the sole KB gateway." Karpathy-wiki
invariants (root files, tier indexes, post-write lint pipeline, backlink graph) are
only maintained by `kiho-kb-manager` via its sub-skills. Direct Writes corrupt the
indexes and the conflict-detection pipeline.

kb-manager emits wiki files with a KB_MANAGER_CERTIFICATE marker as an HTML comment
at the end of the file — this hook lets that Write through. Any other direct
Write/Edit to the wiki path is blocked.

Stdin JSON (PreToolUse schema) — see pre_write_agent.py docstring.

Exit codes:
  0 — allow
  2 — block
"""
from __future__ import annotations

import json
import re
import sys

KB_WIKI_RE = re.compile(
    r".*[/\\]\.kiho[/\\]kb[/\\]wiki[/\\].+\.md$",
    re.IGNORECASE,
)
CERT_MARKER = "KB_MANAGER_CERTIFICATE:"

BLOCK_MESSAGE = """\
[kiho v5.22 gate] Direct Write/Edit to .kiho/kb/wiki/ is blocked.

kb-manager is the sole KB gateway. Route via:
    Agent(
        subagent_type="kiho:kiho-kb-manager",
        prompt="kb-add <slug>: <content>"   # or kb-update / kb-delete
    )

Why: direct writes skip Karpathy-wiki invariants (root files, tier indexes,
post-write lint, backlink graph, conflict detection). The KB becomes quietly
inconsistent and the questions/ page doesn't get opened on contradictions.

If you ARE kiho-kb-manager completing a sanctioned Write, include the provenance
marker at the end of the file as an HTML comment, for example:

    <!-- KB_MANAGER_CERTIFICATE:
           op: add
           slug: <kebab-slug>
           tier: project | company
           emitted_by: kiho-kb-manager
           emitted_at: <iso_ts>
    -->

The audit script `bin/ceo_behavior_audit.py` cross-checks on DONE that Writes
with this marker correspond to real kb_add / kb_update ledger entries.
"""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not KB_WIKI_RE.match(file_path):
        return 0

    content = tool_input.get("content") or tool_input.get("new_string") or ""
    if CERT_MARKER in content:
        return 0

    sys.stderr.write(BLOCK_MESSAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main())
