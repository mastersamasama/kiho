#!/usr/bin/env python3
"""DEPRECATED (v5.23+) — superseded by pre_write_chain_gate.py.

This script used to block direct Writes to agent.md without RECRUIT_CERTIFICATE.
Its logic is now subsumed by the chain-aware `pre_write_chain_gate.py`, which
reads the same invariant from `references/approval-chains.toml`
(`chain.id = "recruit-hiring"`).

Left as a compatibility shim for any local-dev harness still invoking the old
path. The hooks.json manifest points at pre_write_chain_gate.py since v5.23.

Per decision: approval-chains-2026-04-23.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

GATE = Path(__file__).with_name("pre_write_chain_gate.py")

if __name__ == "__main__":
    sys.exit(runpy.run_path(str(GATE), run_name="__main__").get("__exit_code__", 0) or 0)
