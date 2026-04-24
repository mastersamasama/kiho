#!/usr/bin/env python3
"""PreToolUse gate: chain-aware Write/Edit authorization.

Unifies the two v5.22 hooks (`pre_write_agent.py`, `pre_write_kb.py`) into a
single chain-aware gate that reads `references/approval-chains.toml` at
runtime. A Write or Edit whose `file_path` matches ANY chain's
`terminal_path_pattern` must carry the chain's `certificate_marker` in the
content; otherwise the hook exits 2 with a chain-specific blocking message.

Adding a new approval chain is now ≤ 20 lines of TOML with ZERO Python
changes — this script reads the registry each invocation (cheap; TOML is
small) so new chains auto-apply at the next tool call.

Backwards-compat: the three v5.22-era chains (`recruit-hiring`, `kb-writes`)
stay in place in the registry with their original patterns and markers, so
existing recruit and kb-manager flows continue to pass through without
regression.

Stdin JSON (PreToolUse schema): {
  "tool_name": "Write" | "Edit",
  "tool_input": { "file_path": "...", "content": "..." | "new_string": "..." },
  ...
}

Exit codes:
  0 — allow (no chain matches the path, OR chain matches and marker present)
  2 — block (chain matches but marker missing — stderr shown to Claude)

Introduced by decision: approval-chains-2026-04-23 (v5.23 planning).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN_ROOT = HERE.parent
sys.path.insert(0, str(BIN_ROOT))

try:
    import approval_chain  # type: ignore  # noqa: E402
except Exception as exc:
    # Fail OPEN on registry load failure: better to allow a write than to
    # block all writes if the registry is corrupt. The audit script catches
    # missing-cert writes on DONE, so drift is still detected even if the
    # hook is inactive.
    print(
        f"[kiho approval-chain gate] registry unavailable ({exc}); hook disabled",
        file=sys.stderr,
    )
    sys.exit(0)


BLOCK_MESSAGE_TEMPLATE = """\
[kiho v5.23 chain gate] Direct {tool_name} to {file_path} is blocked.

This path is governed by the `{chain_id}` approval chain:

  {description}

The chain requires a `{certificate_marker}` line in the file content as proof
the chain ran (as an HTML comment at the top or bottom of the file). Without
it, this write bypasses:

  {stage_summary}

Routing:
  - governing skill: {governing_skill}
  - invoke via the governing skill, which emits the file with the marker.

If you are the governing agent and the prerequisite stages have completed,
include the marker as an HTML comment, e.g.:

    <!-- {certificate_marker}
           chain_id: {chain_id}
           stages_complete: {stage_ids_csv}
           emitted_at: <iso_ts>
    -->

The DONE-step audit (`bin/ceo_behavior_audit.py`) cross-checks that every
certificate-bearing write has matching `approval_stage_granted` ledger
entries for every stage — fake markers are caught.

Registry: ${{CLAUDE_PLUGIN_ROOT}}/references/approval-chains.toml
"""


def build_block_message(chain, tool_name: str, file_path: str) -> str:
    stage_summary = "\n  ".join(
        f"- {s.stage_id} (approver: {s.approver_role})" for s in chain.stages
    )
    stage_ids_csv = ", ".join(s.stage_id for s in chain.stages)
    return BLOCK_MESSAGE_TEMPLATE.format(
        tool_name=tool_name,
        file_path=file_path,
        chain_id=chain.id,
        description=chain.description,
        certificate_marker=chain.certificate_marker,
        stage_summary=stage_summary,
        governing_skill=chain.governing_skill,
        stage_ids_csv=stage_ids_csv,
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return 0

    try:
        chain = approval_chain.get_chain_for_path(file_path)
    except Exception as exc:
        print(
            f"[kiho approval-chain gate] registry read failed ({exc}); hook disabled",
            file=sys.stderr,
        )
        return 0

    if chain is None:
        return 0

    content = tool_input.get("content") or tool_input.get("new_string") or ""
    if chain.certificate_marker in content:
        return 0

    sys.stderr.write(build_block_message(chain, tool_name or "Write", file_path))
    return 2


if __name__ == "__main__":
    sys.exit(main())
