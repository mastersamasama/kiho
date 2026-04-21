---
name: kiho-plan
description: Use this skill when the kiho CEO needs to decompose a user request — especially a PRD or large feature description — into a prioritized plan.md list of actionable items. Produces a Ralph-style @fix_plan.md populated with P0-P3 priority items, dependency links, and category tags. Trigger when /kiho receives a PRD file, when /kiho feature arrives with a multi-part description, or when the CEO's plan.md is empty at INITIALIZE and needs bootstrapping from the raw request.
argument-hint: "<prd-text-or-path>"
metadata:
  trust-tier: T2
  kiho:
    capability: orchestrate
    topic_tags: [deliberation, orchestration]
    data_classes: ["plan"]
---
# kiho-plan

Decompose a raw user request (especially a PRD) into a prioritized plan.md. Only the CEO should call this skill; sub-agents never decompose plans.

## When to call

- `/kiho <path-to-PRD.md>` — CEO read the PRD, now needs to break it into specs.
- `/kiho feature "<complex multi-part desc>"` — the description implies multiple specs.
- CEO initializes a Ralph loop and `plan.md` is empty — this is the bootstrap step.

## Inputs

- `raw_input`: either the PRD content (already read by CEO) OR a single-paragraph feature description
- `mode`: feature | bugfix | refactor (informs how fine-grained the decomposition is)
- `existing_plan` (optional): current `plan.md` content, if the caller wants to merge new items with existing ones

## Procedure

1. **Read the raw input.** If the input is a PRD, identify distinct capabilities/features/sections. If the input is a short description, you may decide the whole thing is a single plan item.
2. **Call `research` op=kb-search** with the raw input as query, scoped to both project and company tiers. This finds prior decisions, existing entities, and related concepts so your plan can reference them.
3. **Check `org.json`** — some items may need recruitment (e.g., "build a design system" with no design-system-ic). Note recruitment dependencies.
4. **Decompose.** For each distinct piece of work produce an item with:
   - `item_id` — `<category>-<nn>-<short-slug>` (e.g., `feature-01-auth`, `bugfix-03-webhook`)
   - `priority` — P0 (must ship first, blocking) / P1 (must ship in this turn) / P2 (nice to have) / P3 (defer)
   - `one_line` — imperative description under 100 chars
   - `category` — feature | bugfix | refactor | recruit | kb-bootstrap | contradiction-resolution
   - `estimated_complexity` — trivial | small | medium | large | epic
   - `dependencies` — list of item_ids that must complete first
5. **Topological sort** by dependencies, then stable-sort by priority.
6. **Write the decomposition** to `<project>/.kiho/state/plan.md` using the standard plan.md format. If merging with existing plan, preserve In progress / Blocked / Completed sections and add new items to Pending.
7. **Return a receipt** listing item count, priority distribution, and any recruitment dependencies the CEO needs to schedule first.

## Output shape

```markdown
## kiho-plan receipt
status: ok
input_type: prd | description
item_count: 8
priority_distribution: {P0: 2, P1: 4, P2: 2, P3: 0}
recruitment_needed: [design-system-ic, senior-qa]
blocking_questions: []  # things the PRD was ambiguous about
items:
  - feature-01-auth (P0, medium, no deps)
  - feature-02-ledger-core (P0, large, no deps)
  - feature-03-transactions (P1, large, deps: [feature-02-ledger-core])
  ...
```

## Decomposition heuristics

**Every plan item must be independently deliverable.** If item A and item B have to ship together to work at all, they are one item.

**Prefer finer granularity for P0/P1.** A P0 item should be ≤ 3 days of work for a senior engineer. If it's bigger, split it.

**Use P2/P3 for nice-to-haves and speculative items.** The CEO will defer these or drop them if budget runs short.

**Recruitment items are pre-work.** If a feature needs a specialist that doesn't exist, create a `recruit-<dept>-<role>` item at higher priority than the features that depend on it.

**kb-bootstrap items come first.** If the project has no KB, create a P0 item `kb-init` before any feature work. The subsequent features benefit from the seeded KB.

## What NOT to do

- Do not write to `plan.md` if the caller passed `dry_run: true`; return the decomposition structure only.
- Do not attempt to execute items — that's the CEO's Ralph loop, not this skill's job.
- Do not ask the user questions; return `blocking_questions` in the receipt and let the CEO decide whether to ASK_USER.
- Do not decompose so finely that you produce > 25 items from a single turn's request. If you would, return a receipt with `overflow_warning: true` and propose a "subset for this turn" of ≤ 15 items.
- Do not skip the kb-search step. Prior context dramatically improves decomposition quality.
