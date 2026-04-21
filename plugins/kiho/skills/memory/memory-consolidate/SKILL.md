---
name: memory-consolidate
description: Agent self-consolidation of memory files. Reads all four memory types (observations, reflections, lessons, todos), merges duplicates, promotes observations to reflections and reflections to lessons where evidence warrants, archives stale todos, and compacts the files. Not automated — the agent explicitly decides when to run consolidation, typically at session end or when memory files exceed 50 entries. Use when an agent says "consolidate my memory", "clean up notes", or when the CEO triggers it during the DONE phase of the Ralph loop.
metadata:
  trust-tier: T2
  version: 1.1.0
  lifecycle: active
  kiho:
    capability: update
    topic_tags: [reflection, curation]
    data_classes: ["observations", "reflections", "lessons", "soul-overrides"]
---
# memory-consolidate

Performs a single pass of memory maintenance: dedup, promote, archive. This is the agent's opportunity to refine raw experience into durable knowledge. Run explicitly, never automatically.

## Contents
- [Inputs](#inputs)
- [Consolidation pass](#consolidation-pass)
- [Duplicate detection](#duplicate-detection)
- [Promotion rules](#promotion-rules)
- [Todo archival](#todo-archival)
- [Output](#output)
- [Anti-patterns](#anti-patterns)

## Inputs

```
agent_id: <agent-name>
tier: project | company  (default: project)
dry_run: true | false  (default: false — set true to preview changes without applying)
```

## Consolidation pass

Read all four memory files for the agent. Execute these operations in order:

### 1. Dedup observations

Scan `observations.md` for entries with >80% content overlap (word-level Jaccard similarity). For each duplicate cluster:
- Keep the entry with the highest confidence
- Merge unique tags from all duplicates into the kept entry
- Remove the others
- Log: "Merged N duplicate observations into mem-<id>"

### 2. Promote observations to reflections

Scan observations for clusters of 3+ entries sharing 2+ tags. If the agent can articulate a pattern across the cluster:
- Write a new reflection entry to `reflections.md` with:
  - Content: the articulated pattern
  - Confidence: mean of supporting observations' confidence
  - Tags: union of the cluster's tags
  - Source: "consolidation from [mem-<id1>, mem-<id2>, mem-<id3>]"
- Mark supporting observations with tag `promoted: <reflection-entry-id>`
- Do not delete the observations — they remain as evidence

### 3. Promote reflections to lessons

Scan reflections for entries with confidence >= 0.85 that have been confirmed by subsequent observations (same tags appearing in newer observations). If the reflection holds up:
- Write a new lesson entry to `lessons.md`
- Content: actionable guideline form ("Always X when Y", "Never X without Y")
- Confidence: reflection confidence + 0.05 (capped at 0.98)
- Source: "consolidation from [mem-<reflection-id>]"
- Mark the reflection with tag `promoted: <lesson-entry-id>`

### 4. Dedup reflections and lessons

Apply the same >80% overlap dedup to reflections and lessons. Keep highest confidence, merge tags.

### 5. Archive stale todos

Scan `todos.md` for entries where:
- `created_at` is more than 14 days ago AND no recent observation references the todo's topic
- OR the todo's completion criterion has been met (check against recent observations/reflections)

Move archived todos to an `## Archived` section at the bottom of `todos.md` (do not delete — they may be useful for pattern analysis).

### 6. Compact

After all operations, rewrite each file with entries sorted by `created_at` descending. Ensure sequential `entry_id` numbering is preserved (do not renumber — IDs are referenced by source fields in other entries).

## Duplicate detection

Use word-level Jaccard similarity:
```
similarity = |words_A ∩ words_B| / |words_A ∪ words_B|
```

Threshold: 0.80 for observations, 0.85 for reflections and lessons (stricter because they are more curated).

Stop words (a, the, is, are, was, were, etc.) are excluded from the comparison.

## Promotion rules

| From | To | Minimum evidence | Confidence rule |
|---|---|---|---|
| observation | reflection | 3 observations sharing 2+ tags | mean(obs confidence) |
| reflection | lesson | 1 reflection with conf >= 0.85 + 2 confirming observations | reflection.conf + 0.05, max 0.98 |

Promotion is conservative. When in doubt, do not promote. False lessons are worse than missed promotions.

## Todo archival

A todo is stale when:
- It is older than 14 days with no evidence of activity on its topic
- OR the agent's recent observations show the todo's goal was achieved

Archived todos retain their entry_id and metadata. They are moved (within the same file) under an `## Archived` heading at the bottom.

## Trait-drift detection

After the consolidation pass completes, check for behavioral drift against the agent's soul personality:

### Procedure

1. Read the agent's soul definition from their `.md` file (the `## Soul` section with Big Five trait scores)
2. Scan the agent's recent reflections (created in the last 7 days or last 20 entries, whichever is larger)
3. For each Big Five trait, evaluate whether the agent's recent behavioral patterns contradict the base trait score:
   - **Openness**: Are reflections showing rigid/routine behavior despite a high openness score? Or creative/exploratory behavior despite a low score?
   - **Conscientiousness**: Are reflections showing sloppy/disorganized work despite a high score? Or excessive perfectionism despite a low score?
   - **Extraversion**: Are reflections showing withdrawal/isolation despite a high score? Or over-communication despite a low score?
   - **Agreeableness**: Are reflections showing confrontational patterns despite a high score? Or excessive deference despite a low score?
   - **Neuroticism**: Are reflections showing recklessness despite a high score? Or excessive anxiety despite a low score?
4. If a behavioral pattern contradicts a soul trait by >2 points on the 1-10 scale, write a pending drift entry via `storage-broker` (sk-040) op=put with `namespace="state/agents/<agent-id>/soul-overrides"`, `kind="generic"`, `access_pattern="append-only"`, `durability="project"`, payload `{section: "personality", operation: "replace", target_trait: <trait-name>, base_score: <N>, observed_behavior: <description>, suggested_adjustment: <±N>, evidence_refs: [<reflection_ids>], status: "pending"}`. Broker resolves tier → jsonl; `soul-apply-override` drains via `where={status: pending}`. The pre-v5.20 md queue at `agents/<id>/memory/soul-overrides.md` is retired — v5.20 coordinated flip.

### Drift entry payload shape

```json
{"section": "personality", "operation": "replace", "target_trait": "openness", "base_score": 4, "observed_behavior": "consistent experimental choices across 5 tasks", "suggested_adjustment": "+2", "evidence_refs": ["mem-eng-01-038"], "status": "pending"}
```

### Rules

- Only write a drift entry when the contradiction is supported by 3+ reflections showing the same pattern — a single anomaly is not drift
- Never modify the agent's actual soul definition directly — `soul-overrides.md` is an advisory log for the CEO and HR to review
- Cap drift entries at 1 per trait per consolidation run (avoid spamming overrides)
- Include drift detection results in the consolidation output under `trait_drift_detected`

## Output

```json
{
  "status": "ok",
  "observations_merged": 3,
  "observations_promoted": 1,
  "reflections_promoted": 0,
  "reflections_merged": 1,
  "lessons_merged": 0,
  "todos_archived": 2,
  "kb_graduation_candidates": ["mem-eng-01-lesson-008"],
  "trait_drift_detected": [
    { "trait": "conscientiousness", "base": 8, "suggested_adjustment": -2, "evidence_count": 4 }
  ],
  "dry_run": false
}
```

## Anti-patterns

- Never auto-run consolidation. The agent decides when. Typical triggers: session end, memory file > 50 entries, or CEO's DONE phase.
- Never delete observations that support promotions. They are evidence.
- Never promote with fewer than the minimum evidence threshold. Quality over quantity.
- Never renumber entry_ids. Other entries reference them via source fields.
- Never consolidate another agent's memory. Each agent consolidates their own.
