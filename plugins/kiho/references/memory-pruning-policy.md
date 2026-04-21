# Memory pruning policy

- Version: 1.0 (2026-04-19; v5.20 Wave 2.2)
- Status: canonical — `memory-prune` skill MUST follow these rules
- Companion: `references/storage-architecture.md` (T1 archival invariants), `skills/memory/memory-write/SKILL.md` (per-type retention table)

> Key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** per BCP 14 (RFC 2119, RFC 8174).

## Why prune at all

Tier-1 archival memory grows monotonically by design — every observation, reflection, lesson, and todo accumulates in markdown files under `.kiho/agents/<name>/memory/`. Without pruning, two failure modes show up:

1. **Context dilution.** CEO INITIALIZE step 9 injects "last 5 lessons" and "non-archived todos" into delegation briefs. When `lessons.md` has 200 entries spanning a year of work, the "last 5" stops being representative — they're whichever happened to be appended most recently.
2. **Slow recall.** `memory-query` and `memory-read` grep across all entries. Bounded files keep these fast and predictable; unbounded files turn agent context fetch into a multi-hundred-millisecond scan.

Pruning is **not** deletion of important memory. It is compression — moving low-importance, time-decayed entries into an archive directory so the live file stays representative of recent + load-bearing memory.

## What gets pruned

| File | Trigger | Action |
|---|---|---|
| `observations.md` | size > 100 entries OR oldest entry > 90d | move oldest entries with `importance < 5` to `memory/archive/observations-<YYYY-WW>.md` until live file ≤ 100 entries |
| `reflections.md` | size > 50 entries | move entries that have been promoted to a lesson (entry has `promoted_to: <lesson-id>` field) to `memory/archive/reflections-<YYYY-WW>.md` |
| `lessons.md` | NEVER pruned | committee-blessed; retained indefinitely |
| `todos.md` | entry has `status: completed` AND completed > 30d ago | move to `memory/archive/todos-<YYYY-WW>.md` |
| `soul-overrides.md` | NEVER pruned | governance artifact |
| `onboarding.md` | entry > 180d | archive |
| `rejection-feedback.md` | entry > 365d | archive |
| `shift-handoffs.md` | entry > 30d | summarized into a one-line entry in AGENT.md, then deleted |

## What gets compressed

Compression is more aggressive than archival — it rewrites entries rather than moves them. Apply only to `observations.md`:

- If 5 or more observations within a 7-day window share the same primary tag AND have `importance < 5`, replace them with one synthesis entry: `"<N> observations about <tag> between <ts1> and <ts2>; representative entries: <ids>"`.
- Synthesis entry inherits the highest `importance` from the cluster + a `synthesized: true` flag.

Compression MUST cite the source entry IDs so the audit trail survives. The original entries move to archive; the synthesis stays in the live file.

## What gets dropped (importance-decay)

A scheduled importance review (run at CEO DONE) recomputes importance for every observation:

```
new_importance = original_importance * exp(-age_days / 60)
```

Observations whose `new_importance < 1` are eligible for *deletion* (not archival). This is the only destructive operation in the policy and applies only to observations — never to reflections, lessons, or any of the typed memories. The decay constant (60 days) means an importance-7 observation drops to below 1 after roughly 4 months of inactivity.

## Frequency

- **Per-agent prune**: triggered by `memory-prune --agent <id>` from CEO DONE step 4 (`memory-consolidate`) when any threshold above is exceeded
- **Org-wide prune**: triggered by `memory-prune --all` when an external operator runs `/kiho evolve --audit=memory-pressure` (lens to be added)
- **Dry-run is safe**: `--dry-run` lists what would be archived/dropped without touching disk

## Safety invariants

- **Lessons are sacred.** No pruning rule may touch `lessons.md`. If lessons grow unmanageable, the answer is committee review (which can `skill-deprecate` lessons) — not silent pruning.
- **Soul overrides are sacred.** Same rule as lessons.
- **Drop is reversible only via git.** Importance-decay deletion is final — no soft-delete tier. Operators MUST commit memory state before running prune in non-dry-run mode.
- **Archive is read-once.** `memory-query` reads only the live files by default; `--include-archive` is opt-in and slower.

## Cross-tier coordination

Pruning T1 archival memory does NOT affect:
- T2 JSONL telemetry (`skill-invocations.jsonl` etc.) — those have their own age-based compaction (handled by future `bin/jsonl_compact.py`, out of scope for Wave 2.2)
- T3 session-scope artifacts — already evicted at CEO DONE
- KB wiki entries — committee-governed via `skill-deprecate`
