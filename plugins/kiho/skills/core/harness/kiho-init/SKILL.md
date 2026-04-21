---
name: kiho-init
description: Use this skill when the user runs /kiho kb-init to bootstrap a knowledge base from a PRD or an existing codebase. The CEO recruits a research team via HR, reads the PRD or scans the codebase, runs kb-ingest-raw for each identified entity and concept, and seeds the project KB with initial decisions, conventions, and open questions. Different from kiho-setup (which creates empty structure) — kiho-init populates it with real content.
argument-hint: "[path-to-prd-or-scan-target]"
metadata:
  trust-tier: T3
  kiho:
    capability: create
    topic_tags: [bootstrap, ingestion]
    data_classes: ["ceo-ledger", "plan"]
---
# kiho-init

Populate a fresh KB with real content. `kiho-setup` creates the empty structure; `kiho-init` fills it with initial knowledge distilled from a PRD or a codebase scan.

> **v5.21 cycle-aware.** Atomic invocation remains supported, BUT the recommended path for fresh-project KB bootstrap is now `cycle-runner open --template-id kb-bootstrap`. The cycle template orchestrates the same scope → research-cascade → wiki-draft → lint → promote sequence with proper budget enforcement, replay support, and cancellation. This skill becomes a legacy entry point that does not benefit from cycle-runner's audit trail; new projects SHOULD use the cycle path.

## When to use

- User runs `/kiho kb-init` on a fresh project
- User runs `/kiho kb-init <path-to-prd.md>` to seed from a PRD
- CEO detects an empty project KB during the first feature turn and decides to bootstrap before proceeding

## Inputs

```
PAYLOAD:
  prd_path: <optional absolute path to PRD-like document>
  scan_target: <optional absolute path to code directory to scan>
  (if neither is provided, scan the current working directory)
  scope: project | company
```

## Procedure

### 1. Verify the KB is scaffolded

Read `<TIER_ROOT>/knowledge-base.md`. If missing, call `kiho-setup` first (this skill does not scaffold empty structure — that's kiho-setup's job).

### 2. Assemble the research team

The CEO (caller) convenes a small research team via HR:

- **Research lead** — pre-existing `kiho-researcher` agent, assigned to follow the research cascade
- **Domain analyst** — recruited via quick-hire recruitment cycle if the PRD references a domain with no existing expertise (e.g., "payments compliance", "healthcare records"). HR runs a 2-candidate quick-hire and picks one.
- **Codebase scout** — if `scan_target` is set, this agent walks the directory and reports entities (services, modules, vendors detected)
- **Lead clerk** — a `kiho-clerk` agent responsible for ingesting each finding into the KB via kb-manager

Team size: 2-4 members. Any more violates the fanout cap.

### 3. Read the source material

- If `prd_path`: read the PRD in full. Identify sections, requirements, user stories, constraints, open questions.
- If `scan_target`: glob/grep the target for `package.json`, `Cargo.toml`, `pyproject.toml`, `README.md`, service names, module boundaries. Build a list of detected entities.
- If neither: read `<project>/README.md` and `<project>/package.json` (or equivalent) for a minimal seed.

Write each source to `<project>/.kiho/kb/raw/sources/<slug>.md` so kb-ingest-raw has a raw source to cite.

### 4. Decompose into ingest tasks

From the source material, build a plan-like list of ingest tasks:
- One entity page per distinct service/module/vendor
- One concept page per pattern or technology referenced (e.g., `oauth2`, `idempotency-keys`, `event-sourcing`)
- One decision page per committee-approved choice already in the PRD (e.g., "we'll use Postgres")
- Open questions for every ambiguity the PRD doesn't resolve

### 5. Execute ingest tasks sequentially

For each task in the ingest list:
- Call `kiho-kb-manager` with op=`ingest-raw`, passing the raw source path and the hints for affected entities/concepts
- Wait for the receipt
- If kb-manager flags a contradiction (e.g., two PRD sections disagree), note the question page in the running plan for CEO attention
- Append to `ceo-ledger.jsonl` after each task

This is pipeline-style: one ingest at a time, no parallel writes (kb-manager's atomicity model is per-request).

### 6. Seed derived indexes

kb-manager rebuilds derived indexes after every ingest. After all ingests complete, run one final `kb-lint` pass to catch any drift.

### 7. Emit a summary to the CEO

Return a receipt:

```markdown
## kiho-init receipt
status: ok
prd_path: <path>
team_members: [kiho-researcher, <analyst>, <scout>, kiho-clerk]
ingest_tasks_total: 12
ingest_tasks_succeeded: 12
ingest_tasks_flagged: 0
entities_seeded: 8
concepts_seeded: 5
decisions_seeded: 3
open_questions: 2
kb_state_after:
  total_pages: 18
  indexes_consistent: true
  lint_issues: 0
next_suggested_action: >
  KB is ready. Recommend running /kiho feature <next-spec> to start
  delivering from the seeded plan. Two open questions may need
  user resolution before proceeding on specs 03 and 05.
```

## The minimum viable KB

A kiho-init run on a fresh project should produce at minimum:
- 3-5 entity pages (the main services/modules)
- 2-3 concept pages (core patterns the project uses)
- 1 decision page (the top-level architectural choice if identifiable)
- 0-3 open questions (ambiguities CEO should clarify with user later)
- Populated index.md, log.md, tags.md

Under that floor, the ingest is too thin to bootstrap useful kb-search results. If the source material is insufficient to produce the minimum, return `status: partial` with `reason: insufficient_source_material` and recommend the user provide a richer PRD.

## Anti-patterns

- Do not call kiho-init on a non-empty KB without explicit `--force` flag (not currently supported; reject instead).
- Do not overwrite existing pages. If an ingest task would create a page that already exists, route through kb-manager's normal dedupe decision tree.
- Do not ingest the entire codebase. Ingest the high-level structural entities only; details come later through committees and spec work.
- Do not skip the research team assembly step. Bootstrapping in parallel (multiple agents writing at once) will produce contradictions and voice inconsistency.
- Do not promote anything to company tier during kiho-init. Promotion is explicit and requires a later decision.
