# kiho plugin — instructions for the main agent

You are running in a project that has the **kiho** plugin installed. kiho is a single-entry multi-agent orchestration harness. Users interact with it via `/kiho`.

Version milestone narration and historical design notes live in `CHANGELOG.md`. This file is for load-bearing operating rules only.

## Non-Goals

kiho is defined as much by what it refuses to be as by what it is. These are things that could reasonably be goals but are explicitly not:

- **Not a runtime database as source of truth.** Canonical state for **committee-reviewable artifacts** (souls, SKILL.md, references, KB wiki) is Tier-1 markdown; processing artifacts live in Tier-2 (JSONL/YAML/TOML/JSON) and agentic memory in Tier-3 (on-demand sqlite/embeddings). The data shape chooses the tier — see `references/storage-architecture.md` and `references/react-storage-doctrine.md`. Tier-3 on-demand sqlite or other structured storage is allowed per-task under guardrails; no Postgres, no long-running vector store, no DAG scheduler database.
- **Not an MCP server.** kiho does not ship its own MCP server. It consumes MCPs (Playwright, Chrome DevTools) when delegated by the CEO but does not host or daemonize anything.
- **Not a pre-loaded embedding index.** kiho loads no model at startup and maintains no global vector store. Skill discovery, similarity, and reverse-lookup default to deterministic text scans. Agents **MAY** construct a Tier-3 on-demand embedding or sqlite-FTS cache per task, under the guardrails in `references/storage-architecture.md`.
- **Not a runtime dependency resolver.** `metadata.kiho.requires` is a contract enforced at evolution time (deprecation blocks), not at invocation time. The main-agent harness does not check requires lists before running a skill.
- **Not a multi-user platform.** Only the CEO agent running in the main conversation calls `AskUserQuestion`. No per-user routing, no concurrent sessions, no multi-tenancy.
- **Not a container orchestrator.** "Department" and "team" are metaphors for agent hierarchy, not processes. No Docker, no Kubernetes, no deployment manifests.
- **Not a zero-interaction autonomous system.** CEO-only user interaction means kiho CAN pause and ask questions — and should, when uncertain. The Ralph loop keeps working until it needs a human, not until it finishes.

## What kiho IS

kiho is a **single-entry, CEO-led** multi-agent orchestration harness. Every interaction routes through a Ralph-style autonomous loop run by a CEO persona. Storage is **ReAct-style per data class**: each artifact picks its tier from `references/storage-architecture.md` (invariants) using the practical row assignments in `references/data-storage-matrix.md` and per-category tech picks in `references/storage-tech-stack.md`. Tier-1 markdown for committee-reviewable state (souls, SKILL.md, references, KB wiki); Tier-2 JSONL/YAML/TOML/JSON for processing artifacts (telemetry, config, registries); Tier-3 on-demand sqlite/embeddings for agentic working memory with explicit eviction. Markdown is not the default; the data shape chooses the tier. Every user question is mediated by the single CEO agent.

**If the user has invoked `/kiho`** (or one of its sub-modes), you are about to take on the **CEO persona** defined in `agents/kiho-ceo.md`. Load that file, follow its instructions, and run the Ralph-style autonomous loop described there. Only the CEO is authorized to call `AskUserQuestion`; every sub-agent must return structured output to you and you decide when to escalate.

**If the user has NOT invoked `/kiho`**, kiho is dormant. Do not preemptively run committees, modify `.kiho/` state, or invoke kiho skills unless the user explicitly asks.

## Invariants you must respect

- **Single entry point.** `/kiho` is the only skill users should need to remember. Do not invent new top-level slash commands for kiho operations.
- **CEO-only user interaction.** Only the CEO agent running in the main conversation may call `AskUserQuestion`. Sub-agents (committees, departments, kb-manager, researchers) must return structured `escalate_to_user` outputs that bubble up to CEO.
- **kb-manager is the sole KB gateway.** All KB reads and writes go through the `kiho-kb-manager` sub-agent. Do not read `<project>/.kiho/kb/wiki/` or `$COMPANY_ROOT/company/wiki/` directly during committee or delegation work; use the `kb-search` sub-skill.
- **Depth cap 3, fanout cap 5.** Never spawn subagents deeper than CEO → Dept Leader → Team/IC. Never more than 5 children per parent.
- **Three-tier storage.** Canonical state for committee-reviewable artifacts is Tier-1 markdown; processing artifacts (JSONL telemetry, YAML config, JSON events, `.skill_id` sidecars) are Tier-2; agentic memory (on-demand sqlite, embedding cache, scratch files) is Tier-3. Full normative spec in `references/storage-architecture.md`; per-invocation ReAct decision tree in `references/react-storage-doctrine.md`. Every Tier-2 artifact **MUST** be regenerable from Tier-1 + observations (or be primary append-only telemetry); every Tier-3 write **MUST** carry an eviction policy.
- **No PostToolUse hooks for state.** Agents fetch session context on demand via the `session-context` skill.
- **Ralph discipline.** During a `/kiho` turn, the CEO must not stop before the plan is empty, budget is exhausted, or a user question is pending. Single turn, one loop, many iterations.
- **User confirmation is non-bypassable.** The skill-factory Step E (per-field accept / override / reject for `--from-intent` proposals) and every CEO escalation to the user **MUST** get explicit user accept. Confidence-1.0 proposals do not short-circuit the gate. Trust-tier doctrine: autonomous shipping is forbidden.

## Working concepts

These are the normative artifacts the CEO and sub-agents reference during a turn. Historical context for each (why it was added, what it replaced) lives in `CHANGELOG.md`.

- **Skill domains.** Skills live under `skills/{_meta,core,kb,memory,engineering}/`. Top-level domain index is `skills/CATALOG.md` with a `routing:` YAML block; per-domain sub-catalogs carry the skill listings. Each skill has a `.skill_id` sidecar (Tier-2) for stable identity.
- **Capability taxonomy.** Every skill's `metadata.kiho.capability` **MUST** be one of the 8 verbs in `references/capability-taxonomy.md` (`create | read | update | delete | evaluate | orchestrate | communicate | decide`). Additions go through CEO-committee vote.
- **Core abilities (sibling vocabulary).** Cycle template phases additionally declare `core_ability` from a closed 7-verb set in `references/core-abilities-registry.md` (`research | decide | build | validate | deploy | monitor | communicate`). The two taxonomies are intentional siblings: capability classifies *what a skill does*; core-ability classifies *what a phase exercises*. A skill registered under one core-ability **MAY** carry any compatible capability verb. Cycle-runner refuses to open a cycle whose phase declares a `core_ability` that doesn't list the phase's `entry_skill`.
- **Topic vocabulary.** Every skill's `metadata.kiho.topic_tags` entries **MUST** come from `references/topic-vocabulary.md` (controlled 18-tag set). Additions go through CEO-committee vote.
- **Trust tiers.** Every skill carries `metadata.trust-tier: T1|T2|T3|T4`. T1 = unvetted (skill-create default), T2 = community (automatic after ≥3 agents × ≥2 sessions), T3 = trusted (CEO committee), T4 = fully-trusted (CEO + user approval). Any skill that changes >10% of bytes, or (for script-bearing skills) any script change at all, auto-downgrades to T1 and must re-pass the factory gates + committee.
- **Agent soul.** Every agent has a `## Soul` section specified in `references/soul-architecture.md`. Soul drifts over time via `memory-reflect` → `soul-overrides.md` → `soul-apply-override`. Each agent has a `skills:` frontmatter listing their pre-loaded skill portfolio.
- **Three-tier memory.** Core (soul in agent .md, Tier-1), working (session context, Tier-2/3), archival (`.kiho/agents/<name>/memory/`, Tier-1 for committee-blessed notes). Reflections trigger every 5 tasks or when observation importance exceeds 15.
- **Live org registry.** `.kiho/state/org-registry.md` (Tier-1, machine-generated by committee-approved `org-sync`) replaces static `org.json`. `.kiho/state/capability-matrix.md` tracks per-agent skill proficiency (1-5 scale) and feeds RACI assignment.
- **RACI.** Every plan.md task gets `RACI: R=<agent> | A=<lead> | C=<cross-dept> | I=ceo-01`.
- **Self-improvement.** Committee-gated: proposing agent + peer reviewer + CEO vote on skill improvements.
- **Telemetry.** `skill-invocations.jsonl` and `agent-performance.jsonl` (Tier-2 append-only) feed capability matrix, reflection triggers, and recomposition checks.
- **Cycles.** Lifecycles (talent-acquisition, kb-bootstrap, skill-evolution, incident-lifecycle, decision-cycle, value-alignment, research-discovery) are modeled as declarative TOML templates under `references/cycle-templates/`, executed by the `cycle-runner` kernel skill. The CEO loop reads `<project>/.kiho/state/cycles/INDEX.md` at INITIALIZE, advances open cycles via `cycle-runner advance` in LOOP, and regenerates the master index in DONE. Per-cycle SSoT is `cycles/<id>/index.toml`; all transitions append to `cycles/<id>/handoffs.jsonl`. See `references/cycle-architecture.md` and `agents/kiho-ceo.md` steps INITIALIZE-18, LOOP-c, DONE-11.
- **Skill factory.** `bin/skill_factory.py` chains the 10-step SOP (spec → graph → parity → generate → critic → optimize → verify → citation → cousin-prompt → stale-path). Phase 1 steps 1-3, 8, 10 wired deterministically; Phase 2 steps 4-7, 9 emit subagent-request bundles that the CEO invokes via Task tool, then re-enters the factory with `--<step>-output <path>` to merge responses. Poka-yoke prevention-upstream discipline, not inspection-at-end. Single CEO bulk decision per batch; verdicts in `_meta-runtime/factory-verdicts.jsonl` (Tier-2 SOT) with optional rendered view at `_meta-runtime/batch-report-<id>.md` via `bin/render_batch_report.py`.

## Where things live

- Plugin source: `C:\Users\wky\.claude\kiho-plugin\`
- Skill catalog: `skills/CATALOG.md`
- Project runtime state: `<project>/.kiho/`
- Company runtime state: `$COMPANY_ROOT/` (from `skills/core/harness/kiho/config.toml`; default `D:/Tools/kiho/`)
- Kiro (first-skill copy): `skills/engineering/engineering-kiro/kiro/` inside the plugin
- CEO persona: `agents/kiho-ceo.md`
- kb-manager: `agents/kiho-kb-manager.md`
- Historical narration: `CHANGELOG.md`

## When a user types something ambiguous

If the user clearly wants an action covered by a kiho mode, suggest `/kiho <mode> <description>` rather than handling the work yourself. If unsure, ask them whether to run it through kiho. Do not implicitly trigger the kiho CEO on every user message.

## References

- `references/react-storage-doctrine.md` — (v5.20) per-invocation ReAct storage broker; the 4-question decision tree agents run before calling `storage-broker` (sk-040). Data-class rows stay authoritative for well-known classes; the doctrine covers the long tail.
- `references/storage-architecture.md` — three-tier storage spec (canonical / processing / agentic memory)
- `references/data-storage-matrix.md` — authoritative per-data-class row assignments (v5.19+); skills cite row slugs via `metadata.kiho.data_classes:` frontmatter
- `references/storage-tech-stack.md` — per-category tech decisions (TOML / JSONL / sqlite FTS5 / …) with vote records at `_meta-runtime/phase1-committee-minutes.md`
- `references/ralph-loop-philosophy.md` — how the CEO loop works
- `references/karpathy-wiki-protocol.md` — the KB maintenance protocol
- `references/skill-authoring-standards.md` — rules for every skill kiho creates
- `references/skill-authoring-patterns.md` — 9 documentation patterns every reference file must score ≥6/9 on
- `references/research-cascade-protocol.md` — KB → web → deepwiki → clone → ask-user
- `references/committee-rules.md` — unanimous close, 3 rounds, 0.90 confidence
- `references/soul-architecture.md` — agent soul document specification
- `references/org-tracking-protocol.md` — live org registry + capability matrix
- `references/raci-assignment-protocol.md` — RACI annotation rules
- `references/capability-taxonomy.md` — closed 8-verb capability vocabulary
- `references/topic-vocabulary.md` — controlled 18-tag topic vocabulary
- `references/cycle-architecture.md` — (v5.21) cycle-runner kernel design rationale, 5-layer architecture, migration story from v5.20 loose composition
- `references/core-abilities-registry.md` — (v5.21) closed 7-verb core ability set the cycle-runner orchestrates against; atomic skills register under one verb each
- `references/cycle-templates/` — (v5.21) declarative TOML lifecycle templates (talent-acquisition, skill-evolution, kb-bootstrap, incident-lifecycle, decision-cycle, value-alignment, research-discovery)
- `skills/_meta/cycle-runner/SKILL.md` — (v5.21) the orchestrator skill itself; see `skills/_meta/cycle-runner/references/template-dsl.md` for the TOML schema and `skills/_meta/cycle-runner/references/orchestrator-protocol.md` for the per-advance execution model (both live inside the cycle-runner skill directory, not at the top-level `references/`)
- `CHANGELOG.md` — version milestone narration (v5 through v5.21)
