# Memory seed templates (design-agent Step 7 stubs, recruit Phase 6 fill)

Design-agent Step 7 creates `$COMPANY_ROOT/agents/<id>/memory/` and writes
**stub** `lessons.md`, `todos.md`, `observations.md` files that are
non-empty (lint R5) but are overwritten by recruit Phase 6 with real seed
content from the interview.

This reference documents both the stubs (Step 7) and the real seeds
(Phase 6).

## Step 7 stubs

Each file gets this stub:

```markdown
<!-- SEED_STUB: pre-interview placeholder; recruit Phase 6 overwrites -->

(to be populated at hire close)
```

The `.last-reflect` file is seeded with epoch 0:

```
1970-01-01T00:00:00Z
```

This ensures:
- Lint R5 passes (files exist, size > 0)
- First `memory-reflect` on the agent fires (epoch 0 < now - `reflection_task_interval`)
- Phase 6 can distinguish stub from real content (SEED_STUB marker)

## Phase 6 real seeds

See `skills/core/hr/recruit/references/memory-seed-on-hire.md` for the full
templates. Summary:

### lessons.md — minimum 3 entries

```markdown
# Lessons — <agent_id>

## L-000 hire rationale
- trigger: hire_commit
- confidence: <rubric_avg_normalized>
- observation: "You were hired for <role_generic>. Your rubric_avg was
  <score>; you beat <n> other candidates on <dims>."
- lesson: "Your distinguishing strength is <top_dim>. Lean on it."
- tags: [self-identity, hire-rationale]

## L-001 improvement target — <weakest_dim>
- observation: "In Round <N> you scored <weak_score> on <dim>. Specifically,
  <weakness_text>."
- lesson: "When facing <trigger_pattern>, pause and <correction>."
- tags: [growth, <weakest_dim>]

## L-002 auditor dissent (per dissenting auditor)
- observation: "The <persona> auditor dissented, citing <rationale>."
- lesson: "When working with <persona>-style reviewers, proactively
  address <blindspot>."
- tags: [auditor-dissent, blindspot]
```

### todos.md — minimum 3 entries

```markdown
# Todos — <agent_id>

## TODO-001 first-assignment orientation
- priority: high
- description: "Read $COMPANY_ROOT/company/wiki/index.md and entries tagged
  <capability_keywords>. Then read v5 soul-architecture reference."
- acceptance: "Cite 3 company-wiki entries in your first reflection."

## TODO-002 first memory-reflect
- priority: medium
- description: "Run memory-reflect to consolidate observations after first
  5 completed tasks."
- acceptance: "lessons.md grows by >= 1 entry."

## TODO-003 work-sample residual — <subtask>
- priority: medium
- description: "The work-sample surfaced <specific_residual>."
- acceptance: "<concrete deliverable>."
```

### observations.md — minimum 5 entries (per interview round)

```markdown
# Observations — <agent_id>

## O-000 (Round 1 — domain)
- ts: <interview_iso>
- importance: <rubric_normalized>
- observation: "<first-person paraphrase of candidate's response>"
- tags: [interview, domain, <domain_area>]

## O-001 (Round 2 — tools)
...
```

## Overwrite safety

Phase 6 checks for the `<!-- SEED_STUB:` marker before overwriting. If a
memory file lacks the marker, Phase 6 treats it as pre-existing content
(e.g., from a failed prior recruit that was resumed) and APPENDS rather
than overwriting. This avoids losing any real content that may have been
written between Step 7 and Phase 6.

## Path conventions

```
$COMPANY_ROOT/agents/<id>/memory/lessons.md        # semantic, τ 180d
$COMPANY_ROOT/agents/<id>/memory/todos.md          # no retention limit
$COMPANY_ROOT/agents/<id>/memory/observations.md   # episodic, τ 14d
$COMPANY_ROOT/agents/<id>/memory/.last-reflect     # ISO timestamp
```

Memory schemas are unchanged from v5 (see `memory-write` SKILL.md,
`memory-reflect` SKILL.md). v6 only enforces that they're non-empty at
hire time.
