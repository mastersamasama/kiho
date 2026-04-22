# Replay scenario: session 1 — Web3 quant research

**Source incident**: web3-quant-engine session 1 (2026-03…) where CEO was asked
to "research how to do quant in the web3 industry." CEO spawned 5
`general-purpose` subagents but logged them as `kiho-researcher-x5`. KB was
empty on a fresh project; kb-search was silently skipped. Several KB entries
were then Written directly by the CEO rather than routed through
`kiho-kb-manager`.

This scenario tests that v5.22 gates catch all three of those failures.

## Input

```
/kiho research for how to do quant in the web3 industry; produce a KB with
at least 3 rubric-backed entries covering protocol landscape, risk
management, and execution tooling.
```

## Expected CEO behavior under v5.22

1. **Tier declaration.** Response begins with `TIER: normal` and ledger entry 1
   is `action: tier_declared, value: normal`.
2. **Ledger epoch marker.** If no `ledger_epoch: v5.22_active` has been written
   on this project yet, ledger entry 2 is `action: ledger_epoch_marker,
   payload: { epoch: v5.22_active }`.
3. **KB seed check (REQUIRED step 7).** A ledger entry around seq 6–9 of kind
   `kb_empty_acknowledged` or `kb_no_match` — never silent skip.
4. **CEO self-reflect (REQUIRED step 14).** Ledger entry of kind
   `ceo_reflect_complete` with a non-zero `age_at_trigger_s` (or epoch-0 on
   first turn).
5. **Specialized researcher used.** At least 3 ledger entries of kind
   `action: delegate, target: kiho:kiho-researcher`. Actual Agent tool calls
   (inferable from the session transcript if available) use
   `subagent_type: "kiho:kiho-researcher"`, not `"general-purpose"`.
6. **No fanout syntax.** No ledger entry with `target` matching `*-x<N>`
   pattern. Audit script flags these as MAJOR narrative drift.
7. **KB writes via kb-manager.** Any `action: kb_add` has corresponding wiki
   files written with a `KB_MANAGER_CERTIFICATE:` marker. Raw Write attempts
   to `.kiho/kb/wiki/` fire the v5.22 PreToolUse hook and are blocked.
8. **DONE audit clean.** Last 2 ledger entries include
   `action: self_audit_clean` and `action: done`. No `⚠️` prefix in user
   summary.

## Failure signals (what v5.21 would do)

Under v5.21 the same scenario would produce:

- Ledger step 7 silently skipped (no kb_empty_acknowledged)
- Ledger step 14 silently skipped (no ceo_reflect_complete; .last-reflect
  directory absent)
- `target: kiho-researcher-x5` in the ledger with 5 general-purpose Agent
  calls actually happening
- Direct `Write` to `.kiho/kb/wiki/*.md` (no hook to catch it)
- No self-audit at DONE; summary appears clean even though ledger was full of
  drift

## How to run (manual, until the harness skill is automated)

1. In a fresh scratch project, invoke the prompt above via `/kiho`.
2. After the CEO's DONE summary, run:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/skills/_meta/ceo-replay-harness/runner.py \
       --scenario ${CLAUDE_PLUGIN_ROOT}/skills/_meta/ceo-replay-harness/scenarios/session1-replay.md \
       --ledger <project>/.kiho/state/ceo-ledger.jsonl
   ```
3. The runner prints PASS / FAIL per expectation above and exits non-zero on
   any FAIL.

## Automated run (v5.23+, deferred)

Full headless replay requires a test harness that can drive Claude Code's
main agent without a live user session. That doesn't exist as a first-class
tool today. The manual flow + the runner's expectation checker is the
minimum viable test. A future harness can wrap the runner once headless
CEO invocation is feasible.
