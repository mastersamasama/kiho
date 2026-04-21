# Ralph Wiggum loop — philosophy excerpt

Distilled from Geoffrey Huntley's original Ralph technique and Anthropic's official Ralph Wiggum plugin. Cited offline so kiho agents have the philosophy available even without network access.

## Contents
- [The essence](#the-essence)
- [State as filesystem, not context](#state-as-filesystem-not-context)
- [Planning vs building](#planning-vs-building)
- [Binary keep-or-discard](#binary-keep-or-discard)
- [Persistence over perfection](#persistence-over-perfection)
- [kiho-specific adaptations](#kiho-specific-adaptations)

## The essence

> "Ralph is a technique. In its purest form, Ralph is a Bash loop." — Geoffrey Huntley

The technique: repeatedly feed the same prompt to an AI agent until completion. Each iteration sees the prior iteration's output through the filesystem (and git), not through conversational memory.

```bash
while :; do
  cat PROMPT.md | claude-code
done
```

The insight: models don't need to remember their last action — they need to see its *effect*. Files and git commits preserve effects deterministically. Conversational memory does not.

## State as filesystem, not context

**The agentic loop is not in Python; it's in English.**

- Context window = state machine for ONE iteration
- Markdown files = workflow definition
- Git = version control and rollback mechanism
- Filesystem = persistence layer

Ralph's canonical state files:
- `@PROMPT.md` — the instruction set (unchanged across iterations)
- `@fix_plan.md` — prioritized bullet list of outstanding work
- `@AGENT.md` — durable runtime learnings (build commands, quirks, cross-session notes)
- `@specs/*` — specification files
- `src/*` — source code under development

Each iteration reads the relevant files, picks one thing, does it, commits, exits. The next iteration sees the effect of all prior commits.

## Planning vs building

Ralph alternates between two modes, often in the same session:

**Planning mode.** Compare the current source against the specifications. Use parallel subagents to search broadly (up to 500). Identify gaps, TODOs, placeholder implementations. Write them to `@fix_plan.md`, sorted by priority. Build mode picks up from here.

**Build mode.** Read `@fix_plan.md`. Pick the N (typically 1-10) highest-priority items. For each: implement, run tests, commit. Tag with a semver patch bump if tests pass. Exit the iteration.

**Never mix the two.** Planning thinks; building acts. Mixing them produces unfocused iterations that neither plan well nor build reliably.

## Binary keep-or-discard

Every iteration's outcome is binary:
- **Keep**: the change improved the metric (passed tests, increased score, reduced bug count). Advance the git branch.
- **Discard**: the change regressed or crashed. `git reset` to the pre-iteration commit. Log the attempt. Move on.

No "maybe we'll use this later". No branching exploration. If an idea doesn't work the first time, discard it and try something different next iteration.

**Simplicity criterion**: when two changes produce equivalent metrics, prefer the simpler one. Simpler code is easier for future iterations to reason about.

## Persistence over perfection

> "Better to fail predictably than succeed unpredictably."

The core philosophy:
- Don't aim for perfect first attempts
- Let the loop refine
- Failures are data — they inform the next iteration's prompt
- Operator skill matters more than model choice — a great prompt with a mid model beats a bad prompt with a top model
- Persistence wins because the loop handles retry logic automatically

Practical implications:
- **Don't assume not implemented.** Before writing new code, search for existing implementations.
- **Preserve error traces.** Don't clean up failed attempts mid-loop; the model learns from them.
- **Keep primary context tight.** Parallelize with sub-agents for search (up to 500); serialize for build/test (one at a time).
- **Validate cheap, validate often.** Fast type checks and unit tests after each change. Slow e2e tests only at commit boundaries.

## When Ralph works well

- Well-defined tasks with clear, objective success criteria
- Tasks that benefit from iteration: tests, linters, property validation
- Greenfield projects where you can walk away for hours
- Tasks with automatic verification (exit codes, test runners, benchmarks)

## When Ralph works poorly

- Tasks requiring human judgment or design decisions
- One-shot operations that can't be retried cheaply
- Tasks with unclear success criteria ("make it feel good")
- Production debugging on live systems

## kiho-specific adaptations

kiho adopts the Ralph loop philosophy for its CEO agent, with four modifications suited to the enterprise-orchestration context:

**1. One main-agent turn, not a bash while loop.** kiho's CEO runs the Ralph loop *inside* a single `/kiho` invocation. The turn ends when the plan is empty, the budget is exhausted, or a user answer is required. No external `while :` needed; the main agent's turn is the loop.

**2. The "keep/discard" decision is split into five outcomes.** Instead of binary keep/discard, each iteration ends with one of: PROCEED (keep), RECONVENE (committee retry once), ASK_USER (escalate), BLOCK (move item to Blocked, pick next), NEXT (continue). The escalation table in `agents/kiho-ceo.md` governs which outcome fires.

**3. `@fix_plan.md` = `<project>/.kiho/state/plan.md`.** Same shape: prioritized markdown list with In progress / Pending / Blocked / Completed sections. Same discipline: rewritten fully at each iteration's UPDATE step, never mutated in place.

**4. Mid-loop KB integration.** This is kiho's key addition to Ralph. Ralph's iterations are self-contained; kiho's iterations integrate durable outputs into the KB *every* time, so later iterations see the effects of earlier ones. Without mid-loop integration, kiho's multi-iteration PRD work would re-derive decisions each time. With it, iteration N+1 benefits from iteration N's decisions automatically.

## Key Huntley quotes (for CEO reference)

- "Don't assume not implemented" → search the KB + codebase before creating
- "Ralph is deterministically bad in an undeterministic world" → acceptable variance
- "Any problem created by AI can be resolved through a different series of prompts" → tune the CEO prompt when failures repeat
- "Engineers are still needed" → kiho doesn't eliminate the human; it amplifies them
- "Ralph works best for bootstrapping greenfield projects with expectation you'll get 90% done" → kiho's target sweet spot

## Source attribution

- Huntley, Geoffrey — https://ghuntley.com/ralph/
- Anthropic official plugin — https://github.com/anthropics/claude-code/blob/main/plugins/ralph-wiggum/README.md
- "everything is a ralph loop" — https://ghuntley.com/loop/

Offline excerpt maintained in the kiho-plugin so this philosophy is available to CEO prompts without network dependency.
