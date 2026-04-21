# Pattern compliance baseline

Snapshot of P1-P9 compliance across the kiho skill catalog. Produced by
`skills/_meta/skill-create/scripts/pattern_compliance_audit.py --all --baseline`.

Pass threshold is 6/applicable per `references/skill-authoring-patterns.md`
§Review checklist. Lazy-graduation policy applies: skills graduate when
touched, not in a mass proactive pass.

| Skill | Path | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | W2U | Score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `skill-architect` *(deprecated shim → skill-spec)* | `skills/_meta/skill-architect/SKILL.md` | — | — | — | — | — | — | — | — | — | — | **shim** |
| `skill-factory` | `skills/_meta/skill-factory/SKILL.md` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | **8/8** |
| `skill-graph` *(deprecated shim → skill-structural-gate)* | `skills/_meta/skill-graph/SKILL.md` | — | — | — | — | — | — | — | — | — | — | **shim** |
| `skill-parity` *(deprecated shim → skill-structural-gate)* | `skills/_meta/skill-parity/SKILL.md` | — | — | — | — | — | — | — | — | — | — | **shim** |
| `skill-spec` | `skills/_meta/skill-spec/SKILL.md` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | **8/8** |
| `skill-structural-gate` | `skills/_meta/skill-structural-gate/SKILL.md` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | **8/8** *(provisional — needs audit)* |
| `org-sync` | `skills/core/harness/org-sync/SKILL.md` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | **8/8** |
| `skill-create` | `skills/_meta/skill-create/SKILL.md` | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | — | ✓ | ✓ | **7/8** |
| `kiho` | `skills/core/harness/kiho/SKILL.md` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | ✓ | **7/7** |
| `recruit` | `skills/core/hr/recruit/SKILL.md` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | ✓ | **7/7** |
| `skill-deprecate` | `skills/_meta/skill-deprecate/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ✓ | ✗ | **1/8** |
| `skill-find` | `skills/_meta/skill-find/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ✓ | ✗ | **1/8** |
| `skill-improve` | `skills/_meta/skill-improve/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ✓ | ✗ | **1/8** |
| `session-context` | `skills/core/inspection/session-context/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ✓ | ✓ | **1/8** |
| `research-deep` | `skills/core/knowledge/research-deep/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ✓ | ✓ | **1/8** |
| `interview-simulate` | `skills/core/planning/interview-simulate/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ✓ | ✗ | **1/8** |
| `kb-lint` | `skills/kb/kb-lint/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ✓ | ✗ | **1/8** |
| `evolution-scan` | `skills/_meta/evolution-scan/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `skill-derive` | `skills/_meta/skill-derive/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `skill-learn` | `skills/_meta/skill-learn/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `soul-apply-override` | `skills/_meta/soul-apply-override/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kiho-init` | `skills/core/harness/kiho-init/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✓ | **0/7** |
| `kiho-setup` | `skills/core/harness/kiho-setup/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kiho-spec` | `skills/core/harness/kiho-spec/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `design-agent` | `skills/core/hr/design-agent/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kiho-inspect` | `skills/core/inspection/kiho-inspect/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `state-read` | `skills/core/inspection/state-read/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `experience-pool` | `skills/core/knowledge/experience-pool/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `research` | `skills/core/knowledge/research/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `committee` | `skills/core/planning/committee/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kiho-plan` | `skills/core/planning/kiho-plan/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `engineering-kiro` | `skills/engineering/engineering-kiro/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kiro` | `skills/engineering/engineering-kiro/kiro/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kb-add` | `skills/kb/kb-add/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kb-delete` | `skills/kb/kb-delete/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kb-ingest-raw` | `skills/kb/kb-ingest-raw/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kb-init` | `skills/kb/kb-init/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kb-promote` | `skills/kb/kb-promote/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kb-search` | `skills/kb/kb-search/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `kb-update` | `skills/kb/kb-update/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `memory-consolidate` | `skills/memory/memory-consolidate/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `memory-cross-agent-learn` | `skills/memory/memory-cross-agent-learn/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `memory-read` | `skills/memory/memory-read/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `memory-reflect` | `skills/memory/memory-reflect/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |
| `memory-write` | `skills/memory/memory-write/SKILL.md` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | — | ✗ | **0/7** |

## Summary

- Total skills audited: **44**
- Full compliance (passed == applicable): **8**
- Meets 6/applicable threshold: **9**
- Below threshold (lazy-graduation targets): **35**

Legend: ✓ = pattern present and compliant, ✗ = pattern missing or non-compliant,
— = pattern not applicable (e.g., P8 for skills that introduce no gates, P9 for
skills that ship no scripts). W2U = `## When to use` section present.

