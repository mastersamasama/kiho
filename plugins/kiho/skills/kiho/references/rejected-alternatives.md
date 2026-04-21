# Rejected alternatives — kiho entry skill

Read this when you are tempted to redesign the entry surface: add a second top-level command, inline the work instead of delegating, drop the flag-based mode selector, or push the CEO loop into a subagent. Each of these was considered and rejected; the reasons below exist so you do not have to re-derive them.

## A1 — Inline execution instead of delegation

**What it would look like.** `/kiho` directly runs the requested task in the main conversation without loading the CEO persona or spawning sub-agents.

**Rejected because.** Collapses the whole multi-agent harness into a single-agent loop. Loses RACI, committee debate, KB updates, and persona separation. Every kiho value proposition (soul, capability matrix, self-improvement) assumes delegation. Defeats the plugin's purpose.

**Source.** CLAUDE.md Invariants §"Delegate every request"; v4 CEO persona design.

## A2 — Multiple top-level slash commands per mode

**What it would look like.** `/kiho-feature`, `/kiho-bugfix`, `/kiho-vibe`, etc. — one command per mode instead of a single `/kiho` with flags.

**Rejected because.** Expanded discovery surface: users must remember 8+ commands. Claude Code's 1%/8k-char skill budget pays the description cost 8 times. The v5.14 `budget_preflight.py` (Gate 15) would flag this as budget-exceeded within two additions. (This budget applies across every skill in the plugin. See `skill-create/SKILL.md` Gate 15 for the per-skill 1,536-char cap and aggregate ceiling.) CLAUDE.md invariant "Single entry point" is explicit.

**Source.** CLAUDE.md §"Invariants" — "`/kiho` is the only skill users should need to remember"; Claude Code skills docs §"description budget".

## A3 — Automatic mode detection with no CLI flags

**What it would look like.** Always parse raw text and guess the mode via heuristics or a classifier call.

**Rejected because.** Ambiguous inputs ("fix the auth bug" — bugfix or vibe?) lose deterministic control. Users need a way to force a mode when the classifier guesses wrong. The current design uses flags as the deterministic path and falls back to classification only for `unclassified` input — a superset of "always classify" that preserves user agency.

**Source.** Mode parsing table design; kiho-ceo.md INITIALIZE step 3.

## A4 — Running the CEO loop in a sub-agent instead of the main conversation

**What it would look like.** `/kiho` spawns a sub-agent that carries the CEO persona and runs the Ralph loop there; the main conversation only proxies.

**Rejected because.** Only the main conversation can call `AskUserQuestion`. Putting the CEO in a sub-agent means every user question needs a bubble-up protocol, doubling latency and adding a failure mode (malformed escalations). The main-conversation CEO is a direct consequence of Claude Code's tool-scoping rules.

**Source.** Claude Code docs §"AskUserQuestion is main-conversation-only"; CLAUDE.md §"CEO-only user interaction".

## A5 — Splitting the harness SKILL.md between a flat shim and a nested canonical

**What it would look like.** Keep the flat `skills/kiho/SKILL.md` as a thin delegation shim and a nested `skills/core/harness/kiho/SKILL.md` as the authoritative harness, synchronized manually on frontmatter.

**Rejected because.** The flat shim was originally introduced as a workaround for Claude Code's non-recursive skill auto-discovery. Once the nested file was made the source of truth, every invocation paid a `Read` tool call before any work began, and two files had to stay in lockstep on description and argument-hint. Skill-creator's progressive-disclosure model puts the executing instructions in SKILL.md's body and the reference material in bundled resources; splitting the body across two SKILL.md files inverts that. Consolidation into the single flat file, with a deprecation stub left at the nested path so the directory (and its config.toml) stays valid, was adopted v5.22.

**Source.** skill-creator SKILL.md §"Progressive Disclosure"; plan `drifting-wondering-treasure.md`.
