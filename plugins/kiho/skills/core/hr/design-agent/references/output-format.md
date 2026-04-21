# Output format — design-agent produced agent files

Canonical frontmatter and body structure for every agent .md file produced by `design-agent` Step 9 (Deploy). The SKILL.md body keeps only the pointer to this reference; the details live here.

## Contents
- [Frontmatter rules](#frontmatter-rules)
- [Body structure](#body-structure)
- [Field provenance](#field-provenance)

## Frontmatter rules

```yaml
---
name:         <generated-name>                                  # from Step 1
model:        <sonnet | opus | haiku>                           # from Step 4c
description:  <trigger-heavy description, third person, WHAT + WHEN>
tools:
  - <tool-1>
  - <tool-2>
skills:       [sk-XXX, sk-YYY]
soul_version: v5
reports_to:   <agent-id>
allowed_tools: [<tool-1>, <tool-2>]                             # Claude Code convention
memory_blocks:
  persona:  { source: "## Soul body section", max_chars: 8000, editable_by: [ceo-01, hr-lead-01] }
  domain:   { source: ".kiho/agents/<name>/memory/lessons.md", max_chars: 4000, editable_by: [self, dept-lead] }
  user:     { source: ".kiho/agents/<name>/memory/user-context.md", max_chars: 2000, editable_by: [self] }
  archival: { source: ".kiho/agents/<name>/memory/{observations,reflections,todos}.md", max_chars: unbounded, editable_by: [self] }
design_score:
  coherence:           <0.0-1.0>
  alignment:           <0.0-1.0>
  alignment_tools:     <0.0-1.0>
  fit:                 <0.0-1.0>
  rubric_avg:          <1.0-5.0>
  drift:               <0.0-1.0 or null>
  model_justification: "<signals that drove the tier>"
  simulation_mode:     "light"
---
```

### Frontmatter rules

- `model`: chosen by Step 4c, not hand-picked.
- `tools`: minimal set. `Agent` only for leads. `Bash` only for engineering/QA. Never `AskUserQuestion` (CEO-only). Never `WebSearch`/`WebFetch` (go through the research skill).
- `soul_version: v5` is mandatory — older agents are migrated through a separate soul-migration skill, not by design-agent.
- `design_score` records all 8 gate results at ship time for later audit.
- `memory_blocks` declaration is load-bearing for `memory-read` routing and `memory-write` `editable_by` enforcement — do not omit.
- `allowed_tools` duplicates `tools` in the Claude Code convention format; some downstream consumers expect one, some the other.

## Body structure

```markdown
# <agent-name>

You are the kiho <role description>. <one sentence about primary responsibility>.

## Contents
- [Responsibilities](#responsibilities)
- [Working patterns](#working-patterns)
- [Soul](#soul)
- [Quality standards](#quality-standards)
- [Response shape](#response-shape)

## Responsibilities
- <bullet list of 3-5 core responsibilities drawn from Step 0 goal + deliverable>

## Working patterns
<How the agent approaches its work — patterns, preferences, tool usage guidance>

## Soul
<All 12 sections from Step 2 + Step 2b memory architecture reference, rendered per soul-architecture.md>

## Quality standards
<What "good" looks like for this agent's output — ties to the success_signal from Step 0>

## Response shape
<Structured return format matching kiho conventions — must be explicit enough that a caller can validate>
```

**Do NOT** include "Step 1, Step 2" narration in the body. Use topic-based sections.

## Field provenance

Each field traces back to a specific pipeline step. This table documents who populates what, so an auditor reading the deployed .md can verify the pipeline was followed.

| Field | Populated by step | Source |
|---|---|---|
| `name` | Step 1 | requirements dict; validated against reserved words |
| `model` | Step 4c | task profile signals from Step 0 |
| `description` | Step 2 → Step 4 (via description improvement loop) | synthesized from role + responsibilities + triggers |
| `tools` | Step 4b | intersection of behavioral rules verbs and forbidden-tool list |
| `skills` | Step 4 | soul-skill alignment formula + Step 4d resolutions |
| `soul_version` | Step 2 | always `v5` |
| `reports_to` | Step 0 | intake input |
| `allowed_tools` | Step 4b | mirrors `tools` in the Claude Code convention |
| `memory_blocks` | Step 2b | Letta-style persona/domain/user/archival block declarations |
| `design_score.coherence` | Step 3 + Step 3b | mean of 8 pairings + self-audit contribution |
| `design_score.alignment` | Step 4 | soul-skill alignment formula |
| `design_score.alignment_tools` | Step 4b | tool allowlist subscore |
| `design_score.fit` | Step 5 | team complementarity + value compat + red-line check |
| `design_score.rubric_avg` | Step 7 | aggregate mean from interview-simulate |
| `design_score.drift` | Step 7 (full mode only) | from interview-simulate drift metric |
| `design_score.model_justification` | Step 4c | the signals that drove the tier selection |
| `design_score.simulation_mode` | Step 7 | `light` for quick-hire, `full` for careful-hire |
