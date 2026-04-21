---
name: memory-prune
description: Use this skill at the end of each kiho turn (CEO DONE step) to compact agent archival memory by archiving low-importance observations and completed-todos beyond their retention window. Implements references/memory-pruning-policy.md — observation files capped at 100 entries with importance-decay over 60 days; reflection entries that have been promoted to lessons are archived; lessons.md and soul-overrides.md are never touched. Triggers on "prune memory", "compact agent memory", "memory cleanup", or from the CEO DONE step. Supports --dry-run for safe preview, --agent <id> for per-agent scope, and --all for org-wide. Never deletes lessons, reflections that haven't been promoted, or soul-overrides.
metadata:
  trust-tier: T2
  kiho:
    capability: delete
    topic_tags: [reflection, lifecycle]
    data_classes: [observations, reflections, lessons, todos]
---
# memory-prune

The compaction skill for Tier-1 archival memory. Without it, agent memory files grow monotonically until CEO context injection (last-5-lessons / non-archived-todos in INITIALIZE step 9) becomes useless. memory-prune is the one place in kiho that is allowed to *destructively* shrink memory — and even then it is bounded by `references/memory-pruning-policy.md`.

## When to use

- **CEO DONE step (every turn).** Run with `--agent ceo-01 --dry-run` first; if any agent has size/age threshold breached, escalate to a real prune.
- **Operator-initiated cleanup.** `/kiho evolve --audit=memory-pressure` in the future will batch-prune across all agents.
- **Pre-recompute of capability matrix.** After major personnel changes (recruit / depart), prune dropped agents' files before `org-sync` rebuilds.

Do **NOT** invoke when:

- A user has asked for "what did we decide about X" — that's `memory-query`, not prune.
- Disk space is tight — that's not the right reason. memory-prune optimizes context quality, not bytes.
- An agent has just finished a high-stakes task — let the observations land, prune later.

## Inputs

```
agent_id: <id>      (or "all" for every agent in .kiho/agents/)
scope:    project | company | both   (default: both)
dry_run:  true | false                (default: true)
include_archive_view: true | false    (default: false; show what would land in archive)
```

## Procedure

1. **Resolve targets.** If `agent_id == "all"`, enumerate every directory under `<project>/.kiho/agents/` and `$COMPANY_ROOT/agents/`. Otherwise resolve the named agent.

2. **For each target, check thresholds** per `references/memory-pruning-policy.md`:
   - `observations.md` size > 100 entries OR oldest entry > 90 days old
   - `reflections.md` size > 50 entries
   - `todos.md` has any entry with `status: completed` AND `completed_at > 30 days ago`
   - `onboarding.md` has any entry > 180 days old
   - `rejection-feedback.md` has any entry > 365 days old
   - `shift-handoffs.md` has any entry > 30 days old

3. **Apply pruning rules** (NEVER touch `lessons.md` or `soul-overrides.md`):

   **observations.md** — In age order, move entries with `importance < 5` to `memory/archive/observations-<YYYY-WW>.md` until live file ≤ 100 entries. Then run importance-decay: `new_importance = original_importance * exp(-age_days / 60)`. Drop entries with `new_importance < 1` (delete, not archive — only operation that drops without archive).

   **reflections.md** — Move entries that have a `promoted_to: <lesson-id>` field to `memory/archive/reflections-<YYYY-WW>.md`.

   **todos.md** — Move `status: completed AND completed_at > 30 days ago` entries to `memory/archive/todos-<YYYY-WW>.md`.

   **onboarding.md / rejection-feedback.md** — Move entries past their retention to `memory/archive/<type>-<YYYY-WW>.md`.

   **shift-handoffs.md** — Synthesize entries > 30 days old into a one-line summary, append to AGENT.md, then delete.

4. **Optional: compression pass on observations** (only when `--with-compression` flag set). For each agent, find clusters of ≥5 observations within a 7-day window sharing the same primary tag and `importance < 5`. Replace them with a synthesis entry citing source IDs. Move originals to archive.

5. **Write a prune log.** Append to `<project>/.kiho/state/memory-prune.jsonl` (storage-broker tier T2):
   ```
   { "ts": "<iso>", "agent_id": "<id>", "scope": "<project|company>",
     "archived": {"observations": <N>, "reflections": <N>, "todos": <N>, ...},
     "dropped": {"observations": <N>},   # only this is destructive
     "compressed_clusters": <N>,
     "dry_run": <bool> }
   ```

6. **Return a structured summary.**

## Safety invariants

- **lessons.md and soul-overrides.md are NEVER touched.** Lessons are committee-blessed wisdom; soul overrides are governance artifacts. Both retained indefinitely.
- **dry-run is the default.** Operators MUST explicitly pass `--dry-run=false` to actually prune.
- **Importance-decay deletion is the only destructive op.** Recoverable only via git history; the skill commits a checkpoint before applying when invoked from CEO DONE.
- **Cross-agent writes prohibited.** memory-prune touches only the named agent's own files. There is no "prune all agents from CEO context" shortcut — `--all` enumerates targets and runs them sequentially with per-agent scope.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: memory-prune
STATUS: ok | error
AGENT_ID: <id> | "all"
DRY_RUN: <bool>
AGENTS_TOUCHED: <count>
ARCHIVED:
  observations: <N>
  reflections: <N>
  todos: <N>
  onboarding-notes: <N>
  rejection-feedback: <N>
  shift-handoffs: <N>
DROPPED:
  observations_below_decay_floor: <N>
COMPRESSED_CLUSTERS: <N>
LOG_REF: jsonl://state/memory-prune#L<n>
```

## Anti-patterns

- Never prune lessons.md. Even if it has 500 entries, that's a CEO+committee judgment call, not a prune-skill call.
- Never bypass dry-run for `--all`. Always preview before org-wide prune.
- Never compress entries with `importance >= 5`. Those are load-bearing observations the agent will refer back to.
- Never run more than once per CEO DONE step. Pruning has costs; idempotency is for re-runs across turns, not within.
- Never count pruning as a content change. The prune log is informational — committee review is for cases where pruning seems to have removed something important.

## Grounding

- `references/memory-pruning-policy.md` — canonical rules for what gets archived vs dropped.
- `references/storage-architecture.md` — Tier-1 archival memory invariants.
- `skills/memory/memory-write/SKILL.md` — the per-type retention table this skill enforces.
- `skills/memory/memory-consolidate/SKILL.md` — sibling skill that does pre-prune consolidation; promotes observations to reflections so prune knows what's load-bearing.
- `agents/kiho-ceo.md` DONE step 4 — the canonical invocation point.
