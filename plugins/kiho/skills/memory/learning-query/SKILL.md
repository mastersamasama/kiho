---
name: learning-query
description: Use this skill at the start of any non-trivial task to pull prior lessons other agents have learned about the topic — before kicking off fresh research. Complements memory-cross-agent-learn, which pushes lessons; this skill lets an agent explicitly ask what has been learned. Scans cross-agent-learnings JSONL, relevant KB articles, and archival memory lessons. Returns a ranked list with agent source, confidence, evidence pointer. Warms a session-scope sqlite FTS cache when the corpus grows beyond 1000 rows — transparent to caller. Always verify returned lessons before acting — pull is best-effort, not authoritative.
argument-hint: "topic=<text> k=<n>"
metadata:
  trust-tier: T2
  kiho:
    capability: read
    topic_tags: [retrieval, reflection]
    data_classes: ["lessons", "cross-agent-learnings", "kb-wiki-articles"]
---
# learning-query

The pull-side counterpart to `memory-cross-agent-learn`. That skill broadcasts; this one is how an agent explicitly asks "what has the org already learned about this?"

## Contents
- [Why a pull path exists](#why-a-pull-path-exists)
- [Inputs](#inputs)
- [Procedure](#procedure)
- [Ranking](#ranking)
- [Dedup by supersedes chain](#dedup-by-supersedes-chain)
- [Response shapes](#response-shapes)
- [Invariants](#invariants)
- [Non-Goals](#non-goals)
- [Grounding](#grounding)

## Why a pull path exists

Push propagation (`memory-cross-agent-learn`) is great for fresh lessons but decays fast: the target agent might not be running when the lesson is broadcast, the brief-injection window is narrow, and team-scoped lessons don't reach agents who join later. Without a pull surface, an agent picking up a task has no ergonomic way to ask "has anyone already hit this wall?" — and the frequent answer is "yes, three weeks ago, and it cost us an hour."

This skill closes that loop. Pull is best-effort — a lesson returned here is a **prior**, not a verdict. The caller must verify before acting.

## Inputs

```
PAYLOAD:
  topic: <free-text — matched against lesson summaries, tags, KB article titles>
  k: <int, default 5> — max lessons returned
  filter:
    agent: <agent_id to restrict source>        # optional
    domain: <eng|kb|ops|...>                    # optional
    since: <iso-date — drop older lessons>      # optional
    min_confidence: <0..1, default 0.60>
  scope: project | company | both  # default both
```

If `topic` is empty, refuse with `status: empty_topic`. A wildcard lesson dump is not a supported op — for that, use `memory-read` directly on the lessons namespace.

## Procedure

1. **Plan the read** — decide namespaces based on `scope`:
   - `state/cross-agent-learnings` (the jsonl queue, both consumed and unconsumed)
   - `agents/<any>/memory/lessons` (per-agent archival lessons)
   - `kb/wiki` (promoted lessons that graduated into the KB)
2. **Route via `memory-query`** — this skill does not touch raw files. It calls `memory-query` with the topic and the namespace list. `memory-query` in turn calls `storage-broker.query()` and routes through `kiho-kb-manager` for wiki reads, preserving the KB gatekeeper invariant.
3. **Broker size-check** — if `storage-broker` reports `size_hint > 1000` for the cross-agent-learnings spool, it will lazily build/refresh a session-scope sqlite FTS cache and serve subsequent hits from FTS. This is transparent to the caller; no flag, no flip.
4. **Rank** — score each hit (see [Ranking](#ranking)) and keep the top `k * 2` before dedup.
5. **Dedup by supersedes chain** — collapse lessons that were superseded; see [Dedup](#dedup-by-supersedes-chain).
6. **Return** — `[{agent_id, summary, evidence_ref, confidence, source_namespace, ts}]` sorted by final score.

## Ranking

Score per hit = `0.55 * recency_factor + 0.30 * confidence + 0.15 * tag_overlap`.

- **recency_factor** — exponential decay with a 90-day half-life; clipped to `[0, 1]`.
- **confidence** — the lesson's own recorded confidence at propagation time.
- **tag_overlap** — Jaccard similarity between the caller's topic tokens and the lesson's `lesson_tags`.

Ties break on recency. Hits below `min_confidence` are dropped before ranking.

## Dedup by supersedes chain

Lessons form a `supersedes:` chain: `lesson-2026-04-10-002` may declare `supersedes: [lesson-2026-03-28-011]`. When both appear in a result set:

1. Walk the chain forward from every hit, collecting the full set of IDs in each chain.
2. For each chain, keep only the terminal (newest, non-superseded) lesson.
3. Note the collapsed chain length in the returned record's `supersedes_depth` field so the caller can see "this is the 3rd iteration of a lesson" and weigh it higher.

## Response shapes

```markdown
## Receipt <REQUEST_ID>
OPERATION: learning-query
STATUS: ok | empty_topic | no_hits | error
TOPIC: <verbatim>
HITS: <n>
CACHE_TIER_USED: jsonl-scan | sqlite-fts
LESSONS:
  - agent_id: eng-lead-01
    summary: "Always run kb-lint after a bulk wiki rename..."
    evidence_ref: agents/eng-lead-01/memory/lessons/2026-03-28-011.md
    confidence: 0.82
    source_namespace: agents/<agent>/memory/lessons
    supersedes_depth: 2
    ts: 2026-04-10T09:12:00Z
  - ...
NOTES: <e.g. "3 candidates dropped below min_confidence; 1 supersedes chain collapsed">
```

Empty-hit shape:

```markdown
## Receipt <REQUEST_ID>
OPERATION: learning-query
STATUS: no_hits
TOPIC: <verbatim>
NAMESPACES_SCANNED: [state/cross-agent-learnings, agents/*/memory/lessons, kb/wiki]
HINT: "No prior lessons. Consider running `research` before fresh work to populate."
```

## Invariants

- **Read-only.** Never mutates lessons, never marks queue entries `consumed`, never touches the KB.
- **Best-effort, not authoritative.** A returned lesson is a prior; the caller must verify. If a lesson is acted on and proves wrong, record the correction via `memory-write` with a `supersedes:` pointer — don't silently delete.
- **KB gatekeeper respected.** All wiki reads route through `kiho-kb-manager` via `memory-query`. Never open wiki files directly.
- **Session-scope cache only.** The sqlite FTS cache is Tier-3 and dies with the session; never persist it as an artifact.
- **No cross-scope leak.** `local:*`-tagged lessons never return on `scope: company` queries.

## Non-Goals

- **Not a search-everything oracle.** This skill only reads lesson-shaped artifacts. For general doc retrieval, use `research` or `kb-search`.
- **Not a lesson-promotion tool.** Promoting a hit into the KB is `memory-consolidate`'s job, not this one.
- **Not a dedup-on-write pass.** Dedup here is read-side only; write-side dedup lives in `memory-cross-agent-learn`.
- **Not a replacement for the push path.** Agents should still broadcast lessons; pull is the safety net, not the default channel.

## Grounding

- `skills/memory/memory-cross-agent-learn/SKILL.md` — the push-side counterpart
- `skills/memory/memory-query/SKILL.md` — the unified cross-namespace read path this skill delegates to
- `skills/core/storage/storage-broker/SKILL.md` — backs the lazy sqlite FTS cache
- `references/react-storage-doctrine.md` — when sqlite is warmed vs. jsonl-scanned
- `references/storage-architecture.md` — Tier-3 eviction rules for the session cache
- `agents/kiho-kb-manager.md` — the KB gatekeeper this skill routes through
