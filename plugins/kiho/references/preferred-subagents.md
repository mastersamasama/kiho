# Preferred sub-agents for CEO (v5.22)

When the CEO reaches for `Agent(subagent_type: ...)`, prefer the specialized
kiho agent over `general-purpose`. Silent substitution of `general-purpose`
for a specialized agent is a MINOR drift flag in `bin/ceo_behavior_audit.py`
(pattern: ledger declares one target, actual Agent call uses another).

This cheat sheet is read at INITIALIZE step 5b on every turn.

## Intent → preferred subagent_type

| Intent | Preferred `subagent_type` | Anti-pattern to avoid |
|---|---|---|
| Research — facts, market data, SDK docs, library comparisons | `kiho:kiho-researcher` | `general-purpose` + `WebSearch` on main thread (skips trusted-source registry and the KB → web → deepwiki → clone cascade) |
| KB operations — search / add / update / lint / promote | `kiho:kiho-kb-manager` | Direct `Write`/`Edit` to `.kiho/kb/wiki/*.md` (v5.22 hook blocks this) |
| Recruiting a new agent | `recruit` skill (which internally uses `kiho:kiho-recruiter` / `kiho:kiho-hr-lead`) | Direct `Write` to `$COMPANY_ROOT/agents/<id>/agent.md` (v5.22 hook blocks this) |
| Committee transcript extraction | `kiho:kiho-clerk` | CEO summarizes the committee itself — bias risk; clerk exists for impartiality |
| Hiring auditor reviews (persona-assigned) | `kiho:kiho-auditor` with persona in `{skeptic, pragmatist, overlap_hunter, cost_hawk}` | CEO gives a single assessment — misses the four-persona coverage |
| Cross-department comms / help-wanted / incident broadcasts | `kiho:kiho-comms` | CEO manually fans out to each dept lead one-by-one |
| Capacity planning / RACI-aware scheduling | `kiho:kiho-scheduler` | CEO over-books an agent without consulting the capacity matrix |
| Quarterly performance review | `kiho:kiho-perf-reviewer` | CEO self-assesses — no auditor independence |
| Spec stage ritual (requirements → design → tasks) | `kiho:kiho-spec` (or dept lead when narrower) | Running the stage ritual inline in the main thread |
| Generic multi-step exploration with no kiho specialist fit | `general-purpose` | (OK, but MUST log `fallback_to_general_purpose: true, reason: <1-sentence>` in the ledger entry) |

## Fallback discipline

If none of the specialized agents match the task, `general-purpose` is
acceptable — but the ledger entry for that delegation MUST carry a `reason:`
field explaining why no kiho specialist fit. Example:

```json
{
  "action": "delegate",
  "target": "general-purpose",
  "payload": {
    "reason": "task requires interleaved Read + Bash across unknown paths; no kiho specialist has both tool sets",
    "brief_path": "..."
  }
}
```

Without the `reason` field, `bin/ceo_behavior_audit.py` classifies the
delegate as MINOR drift (pattern: `delegate_target_unknown` variant — silent
fallback). Not blocking, just visible.

## Why this matters

The web3-quant-engine session 1-6 audit found the single most common drift
pattern was: CEO wrote `target: kiho-researcher` in the ledger but actually
spawned `general-purpose`. Two root causes:

1. **Memory.** `kiho:kiho-researcher` is a longer string than
   `general-purpose` and the model kept reaching for the shorter, safer name.
2. **No prompt.** Nothing in INITIALIZE told the CEO to prefer the specialist.

Making the specialist-vs-fallback choice explicit at step 5b fixes both: the
CEO sees this list every turn, so the specialist is top-of-mind; and the
`reason:` requirement for `general-purpose` creates a small friction that
pushes toward the specialist when either would work.

## Keeping this list current

When a new kiho agent is added to the org, add a row here. When an existing
agent's canonical name changes, update here and verify
`bin/ceo_behavior_audit.py`'s `KNOWN_SUBAGENTS` set is in sync. Drift between
this file and the audit script's known-set is itself a code-review concern
(the script should not MAJOR-flag an agent that this file endorses).
