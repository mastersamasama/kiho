---
name: ceo-replay-harness
description: Minimal regression harness for v5.22 CEO behavior gates. Reads a replay scenario file (e.g., `scenarios/session1-replay.md` beside this skill) containing expected ledger markers, then checks a project's actual `ceo-ledger.jsonl` against those expectations and prints PASS/FAIL. Use after shipping any change to kiho-ceo.md, recruit/SKILL.md, or the v5.22 hooks to confirm no gate regressed.
metadata:
  trust-tier: T2
  version: 0.1.0
  lifecycle: active
  kiho:
    capability: evaluate
    topic_tags: [testing]
    data_classes: ["ceo-ledger"]
---
# ceo-replay-harness

A small checker that takes (a) a scenario file with expected ledger markers
and (b) a real `ceo-ledger.jsonl` produced by running that scenario in a live
`/kiho` turn, and validates the ledger against the expectations. Intended for
kiho maintainers; not user-facing.

## What it is

`runner.py` parses the "Expected CEO behavior under v5.22" section of a
scenario file for bullet points that encode a check (currently via keyword
match: `tier_declared`, `kb_empty_acknowledged`, `ceo_reflect_complete`,
`self_audit_clean`, plus presence/absence of specific `target:` patterns).
For each check it scans the ledger and prints PASS or FAIL.

## What it is NOT

- **Not a headless CEO driver.** It cannot invoke `/kiho` autonomously — there
  is no supported way to drive Claude Code's main-conversation agent
  headlessly today. The harness consumes ledgers produced by a human-driven
  `/kiho` turn.
- **Not a fuzz tester.** Only the scenarios explicitly written under
  `_meta-runtime/tests/` are covered.
- **Not a unit-test replacement.** `bin/tests/test_ceo_behavior_audit.py`
  covers the audit script's logic with synthetic ledgers. This harness covers
  end-to-end flow against live ledgers.

## Usage

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/_meta/ceo-replay-harness/runner.py \
    --scenario ${CLAUDE_PLUGIN_ROOT}/skills/_meta/ceo-replay-harness/scenarios/session1-replay.md \
    --ledger <project>/.kiho/state/ceo-ledger.jsonl
```

Exit 0 on all PASS, 1 on any FAIL. Output format is line-per-check with the
scenario file name and the check name for easy grepping.

## Adding a scenario

1. Copy an existing scenario in `scenarios/` (beside this SKILL.md) and adjust
   the Input section to describe a new prompt.
2. Under "Expected CEO behavior under v5.22", use the existing keyword
   vocabulary (`tier_declared`, `kb_empty_acknowledged`, etc.) so the runner
   picks it up. New keywords require updating `runner.py`.
3. Run the scenario manually, capture the ledger, run the runner. Commit both
   the scenario and any runner additions in the same PR.

## Triggers

Invoke this skill when:

- Any change to `plugins/kiho/agents/kiho-ceo.md`, `skills/core/hr/recruit/
  SKILL.md`, or `hooks/hooks.json` lands — verify the gates still fire.
- Adding a new v5.22 invariant — write a matching replay scenario alongside.

## Response shape

The runner prints to stdout; no structured return. Integrators should treat
the exit code as the result.

## Limitations

- Keyword matching is literal. Renaming a ledger action (e.g.,
  `kb_empty_acknowledged` → `kb_empty_ack`) requires updating the runner's
  regex table.
- The runner does not verify tool-call transcripts — only ledger entries.
  Claim-vs-reality checking (ledger says `kiho-researcher`, actual call was
  `general-purpose`) lives in `bin/ceo_behavior_audit.py`, which this harness
  shells out to for critical recruit scenarios.
