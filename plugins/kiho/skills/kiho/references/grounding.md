# Grounding — kiho entry skill

The design choices encoded in `skills/kiho/SKILL.md` are not arbitrary. Each of the following citations underwrites one load-bearing rule. Read this when you need to defend a rule in a committee, explain it to a new agent, or decide whether a proposed change contradicts prior-art.

## Single-entry CLI pattern

> **Kubernetes `kubectl` Command structure:** *"kubectl uses the syntax `kubectl [command] [TYPE] [NAME] [flags]`... Commands describe the operation you want to perform."*

One binary, many subcommands. Validated at multi-million-skill scale. https://kubernetes.io/docs/reference/kubectl/

Applies to: A2 (rejecting multiple top-level commands).

## Ralph-style autonomous loop

> **Geoffrey Litt, "Ralph: an AI-first autonomous loop for LLM agents" (2025):** *"iterate until done, user-blocked, or budget-exhausted."*

The CEO's loop discipline follows this verbatim. https://geoffreylitt.com/ralph

Applies to: the three Ralph-loop exit conditions in `SKILL.md` §Loop discipline.

## CEO-only user interaction

> **Claude Code docs §AskUserQuestion scoping:** *"AskUserQuestion is only available in the main conversation; sub-agents cannot invoke it."*

kiho's CEO-only invariant is a direct consequence of tool-scoping, not a style choice.

Applies to: A4 (rejecting CEO-in-subagent), the "CEO owns AskUserQuestion" MUST in the startup sequence.

## Delegate-over-inline pattern

> **Anthropic Engineering, "Harness design for long-running application development" (Mar 24 2026) §Generator/evaluator separation:** *"When we asked agents to evaluate work they had produced, they tend to respond by confidently praising the work … Tuning a standalone evaluator to be skeptical turns out to be far more tractable."*

kiho delegates every request; the CEO never does the work inline. https://www.anthropic.com/engineering/harness-design-long-running-apps

Applies to: A1 (rejecting inline execution), the "delegate every request" MUST.

## Depth cap 3 + fanout cap 5

Empirical ceilings on Claude Code sub-agent usefulness — deeper stacks lose coherence, wider fanouts exceed attention budget. Grounded in kiho v4 design + Claude Code `--max-subagents` documentation.

Applies to: the depth/fanout invariant; the agent-assignments-by-mode table.
