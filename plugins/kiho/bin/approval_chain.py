#!/usr/bin/env python3
"""Approval-chain registry reader + validator.

Central helper for reading `references/approval-chains.toml` and exposing the
chains to the two consumer groups defined in the v5.23 approval-chains
committee decision:

  1. PreToolUse hooks (`bin/hooks/pre_write_agent.py`, `pre_write_kb.py`)
     read `list_certificate_markers()` and `get_chain_for_path()` to decide
     whether a Write is authorized by a declared chain.

  2. Audit script (`bin/ceo_behavior_audit.py`) uses `verify_ran()` to
     cross-check that a certificate-bearing write has matching
     `approval_stage_*` ledger entries for every stage of its chain.

Stdlib-only on Python 3.11+. On 3.10, falls back to optional `tomli` package
per the existing kiho convention (`bin/agent_md_lint.py`, `bin/brief_builder.py`).

CLI:
    python bin/approval_chain.py --validate
        Parse the registry and exit 0 if schema passes, 1 otherwise.

    python bin/approval_chain.py --list-markers
        Emit one certificate marker per line (for shell-level lookup).

    python bin/approval_chain.py --chain-for-path <path>
        Print the chain id whose terminal_path_pattern matches; else "none".

Decision: approval-chains-2026-04-23
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib  # type: ignore
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:
        tomllib = None  # type: ignore

PLUGIN_ROOT_ENV = "CLAUDE_PLUGIN_ROOT"
DEFAULT_REGISTRY_REL = "references/approval-chains.toml"

REQUIRED_CHAIN_FIELDS = {
    "id",
    "certificate_marker",
    "terminal_path_pattern",
    "description",
    "governing_skill",
}
REQUIRED_STAGE_FIELDS = {"stage_id", "approver_role", "on_deny"}
VALID_ON_DENY_PREFIXES = ("abort", "rejection-feedback", "reroute-to:")


@dataclass
class Stage:
    stage_id: str
    approver_role: str
    on_deny: str
    prerequisites: list[str] = field(default_factory=list)


@dataclass
class Chain:
    id: str
    certificate_marker: str
    terminal_path_pattern: str
    description: str
    governing_skill: str
    stages: list[Stage] = field(default_factory=list)
    _compiled_re: re.Pattern[str] | None = None

    def compiled(self) -> re.Pattern[str]:
        if self._compiled_re is None:
            self._compiled_re = re.compile(self.terminal_path_pattern, re.IGNORECASE)
        return self._compiled_re

    def matches_path(self, file_path: str) -> bool:
        return bool(self.compiled().match(file_path))


def locate_registry() -> Path:
    """Return the registry path, preferring $CLAUDE_PLUGIN_ROOT if set."""
    import os

    root = os.environ.get(PLUGIN_ROOT_ENV)
    if root:
        candidate = Path(root) / DEFAULT_REGISTRY_REL
        if candidate.exists():
            return candidate
    here = Path(__file__).resolve().parent.parent
    return here / DEFAULT_REGISTRY_REL


def load_registry(path: Path | None = None) -> list[Chain]:
    """Parse approval-chains.toml. Raises ValueError on schema violation."""
    registry = path or locate_registry()
    if not registry.exists():
        raise FileNotFoundError(f"approval-chains.toml not found at {registry}")
    if tomllib is None:
        raise RuntimeError(
            "no TOML parser available; install `tomli` on Python 3.10 "
            "(3.11+ has stdlib tomllib)"
        )
    with registry.open("rb") as fh:
        raw = tomllib.load(fh)
    if raw.get("schema_version") != "1.0":
        raise ValueError(f"unsupported schema_version: {raw.get('schema_version')}")
    chains: list[Chain] = []
    for idx, row in enumerate(raw.get("chain", [])):
        missing = REQUIRED_CHAIN_FIELDS - row.keys()
        if missing:
            raise ValueError(f"chain[{idx}] missing fields: {sorted(missing)}")
        stages_raw = row.get("stages", [])
        if not stages_raw:
            raise ValueError(f"chain[{row['id']}] has no stages")
        stages: list[Stage] = []
        seen_stage_ids: set[str] = set()
        for s_idx, s_row in enumerate(stages_raw):
            s_missing = REQUIRED_STAGE_FIELDS - s_row.keys()
            if s_missing:
                raise ValueError(
                    f"chain[{row['id']}].stages[{s_idx}] missing: {sorted(s_missing)}"
                )
            if s_row["stage_id"] in seen_stage_ids:
                raise ValueError(
                    f"chain[{row['id']}] duplicate stage_id: {s_row['stage_id']}"
                )
            seen_stage_ids.add(s_row["stage_id"])
            on_deny = s_row["on_deny"]
            if not any(on_deny.startswith(p) for p in VALID_ON_DENY_PREFIXES):
                raise ValueError(
                    f"chain[{row['id']}].stages[{s_row['stage_id']}] bad on_deny: {on_deny!r}"
                )
            stages.append(
                Stage(
                    stage_id=s_row["stage_id"],
                    approver_role=s_row["approver_role"],
                    on_deny=on_deny,
                    prerequisites=list(s_row.get("prerequisites", [])),
                )
            )
        try:
            re.compile(row["terminal_path_pattern"])
        except re.error as exc:
            raise ValueError(
                f"chain[{row['id']}] terminal_path_pattern bad regex: {exc}"
            ) from exc
        chains.append(
            Chain(
                id=row["id"],
                certificate_marker=row["certificate_marker"],
                terminal_path_pattern=row["terminal_path_pattern"],
                description=row["description"],
                governing_skill=row["governing_skill"],
                stages=stages,
            )
        )
    ids_seen: set[str] = set()
    markers_seen: set[str] = set()
    for c in chains:
        if c.id in ids_seen:
            raise ValueError(f"duplicate chain id: {c.id}")
        if c.certificate_marker in markers_seen:
            raise ValueError(
                f"duplicate certificate_marker across chains: {c.certificate_marker}"
            )
        ids_seen.add(c.id)
        markers_seen.add(c.certificate_marker)
    return chains


def list_certificate_markers(chains: list[Chain] | None = None) -> list[str]:
    chains = chains or load_registry()
    return [c.certificate_marker for c in chains]


def get_chain_for_path(file_path: str, chains: list[Chain] | None = None) -> Chain | None:
    """Return the chain whose terminal_path_pattern matches, or None."""
    chains = chains or load_registry()
    for c in chains:
        if c.matches_path(file_path):
            return c
    return None


def verify_ran(chain_id: str, ledger_entries: list[dict]) -> tuple[bool, list[str]]:
    """Check that every stage of chain_id has a matching `approval_stage_granted`.

    Returns (all_ran, missing_stages). Inputs are already-parsed ledger dicts;
    callers (typically ceo_behavior_audit.py) supply the filtered entries.
    """
    chains = load_registry()
    target = next((c for c in chains if c.id == chain_id), None)
    if target is None:
        return (False, [f"unknown chain: {chain_id}"])
    granted_stages: set[str] = set()
    for entry in ledger_entries:
        if entry.get("action") != "approval_stage_granted":
            continue
        payload = entry.get("payload") or {}
        if payload.get("chain_id") != chain_id:
            continue
        stage_id = payload.get("stage_id")
        if stage_id:
            granted_stages.add(stage_id)
    expected = [s.stage_id for s in target.stages]
    missing = [s for s in expected if s not in granted_stages]
    return (not missing, missing)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Approval-chain registry helper.")
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="Path to approval-chains.toml (default: auto-locate).",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", action="store_true", help="Validate schema; exit 0 if clean.")
    group.add_argument(
        "--list-markers",
        action="store_true",
        help="Print one certificate_marker per line.",
    )
    group.add_argument(
        "--chain-for-path",
        metavar="PATH",
        help="Print the chain id whose pattern matches PATH, or 'none'.",
    )
    group.add_argument(
        "--list-chains",
        action="store_true",
        help="Print one chain id per line.",
    )
    group.add_argument(
        "--dump-json",
        action="store_true",
        help="Emit the full registry as JSON.",
    )
    args = parser.parse_args(argv)

    try:
        chains = load_registry(args.registry)
    except (FileNotFoundError, ValueError) as exc:
        print(f"approval-chains registry invalid: {exc}", file=sys.stderr)
        return 1

    if args.validate:
        print(f"ok: {len(chains)} chain(s), {sum(len(c.stages) for c in chains)} stage(s) total")
        return 0
    if args.list_markers:
        for c in chains:
            print(c.certificate_marker)
        return 0
    if args.list_chains:
        for c in chains:
            print(c.id)
        return 0
    if args.chain_for_path:
        match = get_chain_for_path(args.chain_for_path, chains)
        print(match.id if match else "none")
        return 0
    if args.dump_json:
        print(
            json.dumps(
                [
                    {
                        "id": c.id,
                        "certificate_marker": c.certificate_marker,
                        "terminal_path_pattern": c.terminal_path_pattern,
                        "description": c.description,
                        "governing_skill": c.governing_skill,
                        "stages": [
                            {
                                "stage_id": s.stage_id,
                                "approver_role": s.approver_role,
                                "on_deny": s.on_deny,
                                "prerequisites": s.prerequisites,
                            }
                            for s in c.stages
                        ],
                    }
                    for c in chains
                ],
                indent=2,
            )
        )
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
