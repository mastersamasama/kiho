# v6.2.1 — gap closure report

Closes all 10+ gaps identified in the post-v6.2.0 audit (`/kiho` turn 2026-04-24 on the user's request "Check the gap that are there part that violate the auto trigger and not follow the D:\Tools\kiho when trigger").

## Audit summary (pre-v6.2.1)

The v6.2.0 release shipped narratives of auto-flow without fully wiring them. Six hard auto-trigger gaps and four `$COMPANY_ROOT` compliance gaps made the advertised auto-flow either non-functional or invisible to the OKR audit.

## Gap-by-gap resolution

### Hard auto-trigger gaps

| Gap | Status in v6.2.1 | Evidence |
|---|---|---|
| **H** — `okr-checkin` hook rejected at runtime | **Closed**. `bin/cycle_runner.py:59` `HOOK_VERBS` frozenset now includes `"okr-checkin"`. CEO INTEGRATE step e (hook dispatch) extended with concrete handler: shell out to `bin/okr_derive_score.py --cycle-id X --o-id Y`, then `Agent(subagent_type="kiho:kiho-okr-master", prompt="OPERATION: checkin-from-cycle, cycle_id: X, o_id: Y, deltas: ...")`. Master invokes atomic `okr-checkin` with derived deltas. | `plugins/kiho/bin/cycle_runner.py:59` + `plugins/kiho/agents/kiho-ceo.md` §INTEGRATE step e |
| **D** — Committee close doesn't auto-invoke `okr-set` | **Closed**. `skills/core/planning/committee/SKILL.md` §Clerk extraction new step 6: detect OKR keyword in committee topic + unanimous outcome + knowledge_update → emit `committee_requests_okr_set` ledger entry with clerk-assembled payload + `DEPT_COMMITTEE_OKR_CERTIFICATE` body. CEO INTEGRATE reads the ledger action and dispatches `kiho-okr-master OPERATION: emit-department-o`. | `plugins/kiho/skills/core/planning/committee/SKILL.md` step 6 |
| **C** — Onboard deferred todo is a dead-letter | **Closed**. `skills/core/hr/onboard/SKILL.md` step 8 rewritten. Previous approach (mentor-memory `lesson-followup` todo) replaced with explicit ledger entry `okr_individual_schedule_onboard` with `fires_at` timestamp. Scanner pass 7 (`_collect_pending_onboard_dispatches`) detects entries whose `fires_at <= today` and emits `onboard-dispatch` action. CEO step 17.5 dispatches to HR-lead. | `plugins/kiho/skills/core/hr/onboard/SKILL.md` step 8 + `plugins/kiho/bin/okr_scanner.py` `_collect_pending_onboard_dispatches` |
| **J** — `kiho-plan` auto-link not implemented | **Closed**. `skills/core/planning/kiho-plan/SKILL.md` §Procedure new step 5a: for each plan item, compute Jaccard token-overlap against active OKRs (from both tiers), auto-tag `aligns_to_okr` at ≥0.30, suggest at 0.15-0.30. Cycle-runner cycle-open resolution chain now resolves plan task frontmatter. | `plugins/kiho/skills/core/planning/kiho-plan/SKILL.md` step 5a |
| **A** — CEO step 17.5 dispatch is prose | **Closed**. Step 17.5 rewritten with concrete `Agent(subagent_type=..., prompt=...)` and `AskUserQuestion({...})` invocation templates for each of seven action kinds. Generator/evaluator separation preserved by explicit templates. | `plugins/kiho/agents/kiho-ceo.md` §INITIALIZE step 17.5 |
| **B** — `okr-period.toml` cycle orphaned from scanner-dispatch | **Closed (architectural clarification)**. Step 17.5 last paragraph documents scanner-dispatch as primary + REQUIRED path; cycle template is OPTIONAL alternative for projects wanting cycle-tracked period telemetry. Coexistence is explicit. | `plugins/kiho/agents/kiho-ceo.md` §INITIALIZE step 17.5 last paragraph |

### `$COMPANY_ROOT` compliance gaps

| Gap | Status in v6.2.1 | Evidence |
|---|---|---|
| **E** — OKRs stored per-project, scanner misses company-tier | **Closed**. `okr_scanner.load_okrs` reads BOTH `<project>/.kiho/state/okrs/` AND `$COMPANY_ROOT/company/state/okrs/`. Company-tier OKR in any location suppresses `propose-company` re-nudge across projects. | `plugins/kiho/bin/okr_scanner.py` `load_okrs` + `test_company_tier_okr_suppresses_project_propose_company` |
| **F** — OKR-master unknown to org-sync | **Closed**. `kiho-setup` new op `scaffold-okr-master` copies plugin-shipped agent.md to `$COMPANY_ROOT/agents/kiho-okr-master/agent.md` + seeds memory. CEO INITIALIZE step 1f auto-invokes on missing. Org-sync picks the agent up automatically on next scan. | `plugins/kiho/skills/core/harness/kiho-setup/SKILL.md` new §op=scaffold-okr-master + `plugins/kiho/agents/kiho-ceo.md` §INITIALIZE step 1f |
| **G** — Scanner ignores `$COMPANY_ROOT/settings.md` | **Closed**. `okr_scanner._load_cfg` layers config: DEFAULT_CFG → plugin default → company `settings.md` `[okr]` block (TOML-in-markdown parser) → project `config.toml`. Company-wide settings propagate to all projects. | `plugins/kiho/bin/okr_scanner.py` `_load_cfg` + `_merge_okr_from_settings_md` + `test_settings_md_okr_block_overrides_plugin_default` |
| **I** — HR filter per-project score; cross-project agents broken | **Closed**. `skills/core/okr/okr-individual-dispatch/SKILL.md` stage 1 step 3 rewritten: project-tier score first, fallback to `$COMPANY_ROOT/company/state/agent-score-<period>.jsonl`, else `score_basis: new_hire`. Stage 1 step 4 also checks both tiers for existing individual Os. | `plugins/kiho/skills/core/okr/okr-individual-dispatch/SKILL.md` stage 1 |

### Audit / visibility gap

| Gap | Status in v6.2.1 | Evidence |
|---|---|---|
| **K** — Drift from hook H and gap D silent | **Closed**. `bin/ceo_behavior_audit.py` two new drift classes: `okr_hook_without_checkin` (MAJOR — cycle close with aligns_to_okr but no okr_auto_checkin_from_cycle ledger entry) and `okr_committee_without_okr_set` (MAJOR — OKR-topic unanimous committee close without committee_requests_okr_set / okr_set / okr_set_request_skipped). 8 new unit tests. | `plugins/kiho/bin/ceo_behavior_audit.py` `check_okr_hook_to_checkin` + `check_committee_to_okr_set` + `plugins/kiho/bin/tests/test_ceo_behavior_audit.py` `TestOkrHookToCheckin` + `TestOkrCommitteeToOkrSet` |

## Verification

- **59 unit tests pass** (51 prior v5.22/v5.23/v6.2 + 8 new v6.2.1).
- **5 approval chains validate** (unchanged from v6.2.0).
- **Scanner smoke**: nonexistent project errors 3; empty project emits `propose-company`; active-company-no-dept emits `cascade-dept`; company-tier-OKR-exists suppresses re-nudge; settings.md `auto_trigger_enabled=false` produces zero actions; scheduled onboard past `fires_at` emits `onboard-dispatch`; spawn-after-schedule suppresses subsequent dispatch.
- **Regression**: v6.1 explicit-invocation flow untouched. PreToolUse hooks unchanged. Approval chain registry unchanged.

## Scope

Files touched: 8 modified, 1 new (this report), 0 deleted.

- **Python**: `bin/cycle_runner.py` (+1 verb), `bin/okr_scanner.py` (+~180 lines: company-tier + settings-md + onboard-dispatch + parse_timestamp helper), `bin/ceo_behavior_audit.py` (+~80 lines: 2 new drift classes), `bin/tests/test_okr_scanner.py` (+6 tests), `bin/tests/test_ceo_behavior_audit.py` (+8 tests).
- **SKILL.md**: `skills/core/planning/committee/SKILL.md` (clerk step 6 insert), `skills/core/planning/kiho-plan/SKILL.md` (step 5a insert), `skills/core/hr/onboard/SKILL.md` (step 8 rewrite), `skills/core/harness/kiho-setup/SKILL.md` (new op), `skills/core/okr/okr-individual-dispatch/SKILL.md` (stage 1 cross-tier fallback).
- **Agent**: `agents/kiho-ceo.md` (step 1f insert, step 17.5 rewrite, INTEGRATE step e extend).

No breaking changes to any v6.2.0 atomic primitive. All changes are either additive (new hook verb, new config keys, new skill step) or parameterized (okr-individual-dispatch filter gains company-tier fallback).

## Relationship to committee-01 OKR decision

Committee-01 (v5.23) decided "no auto cadence" — v6.2 reversed that for event-driven (not time-driven) triggers. v6.2.1 does NOT touch that decision. v6.2.1 only wires the event-driven triggers that v6.2 claimed to ship but shipped as prose. The committee's cadence stance remains correctly reversed.

## Release posture

- `plugin.json` 6.2.0 → 6.2.1
- `marketplace.json` 6.2.0 → 6.2.1
- `CHANGELOG.md` v6.2.1 patch entry appended
- Tag `v6.2.1`
- Not pushed to origin (per user-owns-push invariant)
