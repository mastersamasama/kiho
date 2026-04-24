# v5.23 OA integration — proposal directory

## Purpose

Evaluate kiho against modern Office-Automation (OA) suites — Lark/Feishu, DingTalk, Notion, Workday — and propose kiho-native solutions for the gaps where OA is objectively superior. Each gap that passes the "worth a committee" filter gets a full committee-deliberated proposal under committee discipline (unanimous close, confidence ≥ 0.90, 3-round cap, per `plugins/kiho/references/committee-rules.md`).

This directory contains **proposals only**. No SKILL.md, no agent.md, no hook JSON, no CHANGELOG edits. Implementation lands in a subsequent v5.23 execution plan after the user picks which committee recommendations to adopt.

## Layout

```
_proposals/v5.23-oa-integration/
├── README.md                   ← this file
├── 00-gap-analysis.md          ← OA ←→ kiho capability gap matrix, scored
├── 01-committee-okr/           ← OKR framework
├── 02-committee-approval/      ← multi-stage conditional approval chains
├── 03-committee-broadcast/     ← company-wide announcements
├── 04-committee-pulse/         ← lightweight pulse surveys
├── 05-committee-360review/     ← multi-peer 360 performance review
├── 06-committee-dashboard/     ← period-rollup analytics
└── 99-v5.23-roadmap.md         ← synthesis + adoption ordering
```

Each `NN-committee-*/` directory contains:

- `charter.md` — members, topic, key questions, success criteria, references
- `transcript.md` — machine-parseable deliberation record (YAML frontmatter + round blocks + close block, per committee-rules §Transcript format)
- `decision.md` — MADR-format outcome: what was decided, why, alternatives considered, consequences

## Running context

- The previous `_proposals/v5.22-gap-fix/` landed as `v5.22.0` on origin/main (PreToolUse hooks, CEO self-audit, recruit pre-emit gate, tier declaration, correction-reflection, replay harness). This is the next planning cycle against that baseline.
- All committees assume v5.22 invariants are in force: kb-manager is the sole KB gateway, agent.md writes require `RECRUIT_CERTIFICATE:`, KB wiki writes require `KB_MANAGER_CERTIFICATE:`, CEO declares `TIER:` at turn start, DONE runs `bin/ceo_behavior_audit.py`.
- The CEO running this turn declared `TIER: careful` — committees run full machinery, no shortcuts.

## Reading order

1. Start with `00-gap-analysis.md` to understand the scoring and which gaps qualified.
2. Jump to any `NN-committee-*/decision.md` for the conclusion; read `transcript.md` for the reasoning.
3. Finish with `99-v5.23-roadmap.md` for the adoption ordering and next concrete step per proposal.
