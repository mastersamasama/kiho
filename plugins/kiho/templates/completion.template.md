# Completion criteria — this /kiho turn

<!--
CEO writes this at the INITIALIZE step of every /kiho invocation. It captures:
- What the user asked for (the raw request)
- What MUST be true for this turn to count as "done"
- Any hard limits specific to this turn (budget, reversible-only, etc.)

The CEO's Ralph loop only ends when either:
(a) plan.md is empty AND every criterion below is met, OR
(b) the user must be asked (AskUserQuestion), OR
(c) a hard limit is exceeded

This file is rewritten on every /kiho turn — the previous contents are
archived by appending to .kiho/state/completion-archive.md before overwrite.
-->

## User request
{{raw_user_request}}

## Mode
{{mode}}

## Success criteria
(to be filled in by CEO during INITIALIZE)
- [ ] criterion 1
- [ ] criterion 2

## Hard limits for this turn
- max_ralph_iterations: {{max_iters}}
- budget_tokens: {{budget_tokens}}
- budget_tool_calls: {{budget_calls}}
- wall_clock_min: {{wall_clock_min}}
- reversible_only: {{reversible_only}}
- preapproved_keywords: {{preapproved_list}}

## Started at
{{iso_timestamp}}
