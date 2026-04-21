# kiho

**Spec-driven multi-agent orchestration for Claude Code, with a Ralph-style autonomous CEO.**

kiho is a single-entry harness: one slash command, `/kiho`, hands control to a CEO agent that runs a Ralph-style autonomous loop over your project's `plan.md`, delegates to department leads, committees, researchers, and a sole kb-manager, and keeps going until the plan is empty, the budget is exhausted, or it needs to ask you a question.

```
/kiho <request-or-prd-path>
```

One user-facing skill. Everything else routes automatically.

---

## What it does

- **Turns a PRD into shipped code.** You paste a PRD; the CEO decomposes it into specs, runs each through the kiro spec flow (requirements → design → tasks, each gated by your approval), convenes committees for architecture calls, recruits specialists on demand, and keeps going until the work is done.
- **Preserves kiro's stage gates.** User approval of requirements, design, and tasks is non-bypassable. The harness enriches content within those gates; it never bypasses them.
- **Maintains a two-tier knowledge base.** A dedicated `kb-manager` agent owns a project KB at `<project>/.kiho/kb/` and a company KB at `$COMPANY_ROOT/` (configured on first run). All KB reads and writes route through `kb-manager`. Structure follows Karpathy's llm-wiki pattern with 3 root files and 12 derived indexes per tier.
- **Evolves its own skills.** The skill-factory chain (intake → generate → critic → verify → cousin-prompt → stale-path) produces new skills under committee gate. Every new or modified skill is auto-registered in the KB.
- **Never stops before finished.** The CEO runs a Ralph loop inside a single `/kiho` turn. It only pauses for `AskUserQuestion`, and it only ends when the plan is empty.

---

## Architecture invariants (v5.21)

The full normative spec is in `CLAUDE.md`. Highlights:

- **Single entry point.** `/kiho` is the only user-facing slash command.
- **CEO-only user interaction.** Only the CEO running in the main conversation calls `AskUserQuestion`. Every sub-agent returns structured output that bubbles up.
- **kb-manager is the sole KB gateway.** All KB reads/writes go through the `kiho-kb-manager` sub-agent via `kb-search`, `kb-add`, `kb-update`, `kb-delete`, `kb-lint`, `kb-promote`, `kb-ingest-raw`, `kb-init`.
- **Depth cap 3, fanout cap 5.** CEO → Dept Leader → Team/IC. Never more than 5 children per parent.
- **Three-tier storage.** Tier-1 markdown for committee-reviewable artifacts (souls, SKILL.md, references, KB wiki). Tier-2 JSONL/YAML/TOML/JSON for processing artifacts (telemetry, config, registries, sidecars). Tier-3 on-demand sqlite/embeddings for agentic working memory with explicit eviction. Normative spec in `references/storage-architecture.md`; per-invocation ReAct tree in `references/react-storage-doctrine.md`.
- **No PostToolUse hooks for state.** Agents fetch session context on demand via the `session-context` skill.
- **User confirmation is non-bypassable.** Skill-factory Step E (per-field accept/override/reject) and every CEO escalation to the user get explicit accept. Confidence-1.0 proposals do not short-circuit the gate.
- **Trust-tier doctrine.** Every skill carries `metadata.trust-tier: T1|T2|T3|T4`. Autonomous shipping is forbidden; promotion to T3/T4 requires committee + (for T4) user approval.
- **Closed vocabularies.** Skills declare one `metadata.kiho.capability` verb from the closed 8-verb set (`references/capability-taxonomy.md`) and tags from the 18-tag `topic-vocabulary.md`. Cycle templates declare one `core_ability` from the sibling 7-verb `core-abilities-registry.md`.
- **Cycles as code.** Seven lifecycle templates (talent-acquisition, skill-evolution, kb-bootstrap, incident-lifecycle, decision-cycle, value-alignment, research-discovery) live under `references/cycle-templates/`. The `cycle-runner` kernel skill executes them; CEO reads `<project>/.kiho/state/cycles/INDEX.md` at INITIALIZE and advances open cycles mid-loop.

---

## Modes

| Command | What happens |
|---|---|
| `/kiho <desc>` | CEO infers the right mode and runs it |
| `/kiho <path/to/PRD.md>` | CEO decomposes the PRD into specs and processes them sequentially |
| `/kiho feature <desc>` | Full spec-driven flow with committee per stage |
| `/kiho --bugfix <desc>` | Lightweight spec flow, Engineering-led |
| `/kiho --refactor <desc>` | Lightweight requirements + tasks, Engineering-led |
| `/kiho --vibe <desc>` | CEO delegates directly to an IC; skips spec ceremony |
| `/kiho --debate <topic>` | Cross-department committee; CEO presents result |
| `/kiho --resume <name>` | Resume from `.kiho/state/plan.md` |
| `/kiho kb-init` | Recruit research + domain teams to bootstrap the KB from a PRD or codebase |
| `/kiho evolve [<skill>]` | Run the skill-factory evolution loop |

---

## Install

1. Install the plugin via the Claude Code marketplace or copy this directory into your plugin cache.
2. Run `/kiho-setup`. On first run it asks where the **company knowledge base** should live (recommended: `D:/Tools/kiho/` on Windows, `~/kiho/` on Unix) and writes the answer to `skills/core/harness/kiho/config.toml`.
3. Run `/kiho` on any project. kiho scaffolds `<project>/.kiho/` with the state tree and the project KB.

---

## How it works (high-level)

- **Entry point** is the `kiho` skill, which loads the CEO persona defined in `agents/kiho-ceo.md` into the main conversation so only the CEO calls `AskUserQuestion`.
- **State** lives in markdown + JSONL + YAML/TOML under `<project>/.kiho/`. No MCP server, no database, no PostToolUse hooks.
- **The CEO Ralph loop**: INITIALIZE → LOOP (EXAMINE → PLAN THIS ITEM → DELEGATE → VERIFY → INTEGRATE → UPDATE plan.md → repeat) → DONE. KB writes happen every iteration, not just at session end.
- **Committees** use a five-phase round protocol (research → suggest → combine → challenge → choose) with unanimous + no-unresolved-challenges close at aggregate confidence ≥ 0.90, max 3 rounds, escalate to CEO.
- **Research cascade**: KB → web → deepwiki → clone-as-reference → ask-user. Cost-ascending fallback; results cached.
- **Skill evolution**: skill-factory orchestrates the 10-step SOP (spec → graph → parity → generate → critic → optimize → verify → citation → cousin-prompt → stale-path); Phase 1 steps 1-3, 8, 10 run deterministically in Python; Phase 2 steps 4-7, 9 emit subagent bundles the CEO invokes.

---

## Design references

Architecture draws from:

- Karpathy's llm-wiki (KB philosophy) and autoresearch (loop philosophy)
- HKUDS/OpenSpace (skill evolution)
- Geoffrey Huntley's Ralph Wiggum loop (autonomous orchestration)
- Anthropic official agent-skill authoring best practices
- Toyota jidoka + Shingo poka-yoke (factory architecture: prevention-upstream over inspection-at-end)
- MemGPT / Letta and Karpathy's agentic-memory writings (Tier-3 on-demand storage)

Offline excerpts and full design notes are bundled under `references/`. Version milestone narration lives in `CHANGELOG.md`.

---

## Documentation map

- `CLAUDE.md` — operating rules and invariants (load-bearing; every turn starts here)
- `CHANGELOG.md` — v5.0 through v5.21 milestone narration
- `agents/kiho-ceo.md` — CEO persona + Ralph loop steps
- `skills/CATALOG.md` — top-level skill routing table
- `references/storage-architecture.md` — three-tier storage normative spec
- `references/cycle-architecture.md` — cycle-runner kernel design
- `references/capability-taxonomy.md` + `references/core-abilities-registry.md` + `references/topic-vocabulary.md` — closed vocabularies
- `references/committee-rules.md` — committee close rule, rounds, escalation table
- `references/soul-architecture.md` — 12-section agent soul spec
- `references/ralph-loop-philosophy.md` — why the CEO loop works the way it does
