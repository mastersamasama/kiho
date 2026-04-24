---
name: consolidate-skill-library
description: Skill-library consolidation. Scans `$COMPANY_ROOT/skills/*/SKILL.md`, detects pair-wise feature-overlap ≥ 0.70 (merge candidates routed through `skill-improve`), zero-invocation skills older than `settings.skill_library.stale_days` with no reverse dependents (deprecate candidates routed through `skill-deprecate`), and skills with ≥ 3 improvements in 90 days ("mature" tag propose). Invoked by CEO DONE step 10b when `days_since_last_skill_consolidation >= settings.skill_library.consolidate_cadence_days` (default 30) OR `new_skills_since_last >= settings.skill_library.consolidate_cadence_new_skill_count` (default 5). Uses `bin/embedding_util.py` for overlap scoring and `bin/kiho_rdeps.py` for dependent-count. READ-only by itself; all writes delegate to skill-improve / skill-deprecate.
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: draft
  kiho:
    capability: read
    topic_tags: [curation, lifecycle, authoring]
    data_classes: ["skill-definitions"]
    storage_fit:
      reads: ["$COMPANY_ROOT/skills/**/SKILL.md", "$COMPANY_ROOT/skills/INDEX.md", "$COMPANY_ROOT/company/skill-performance.jsonl", "$COMPANY_ROOT/settings.md"]
      writes: []
---
# consolidate-skill-library

Periodic skill-library hygiene sweep. Three parallel passes over
`$COMPANY_ROOT/skills/*/SKILL.md`:

1. **Merge pass** — pair-wise feature overlap ≥ 0.70 → propose `skill-improve`
   to merge the lesser-used skill into the more-used one.
2. **Deprecate pass** — zero invocations in last `stale_days` AND no reverse
   dependents → propose `skill-deprecate` (soft deprecate, lifecycle flip).
3. **Mature-tag pass** — 3+ improvements in last 90 days → propose adding
   `lifecycle: mature` tag (informational; surfaces stability for
   design-agent ranking).

All write actions delegate out — this skill is the analyzer, not the
mutator.

## When to use

Invoke from:

- CEO DONE step 10b cadence gate
- `/kiho evolve` when user requests library-wide review
- HR-lead after a wave of new skills (5+ authored in short time)

Do NOT invoke:

- On a skill library with < 10 entries (not enough signal)
- Mid-LOOP (DONE-only)

## BCP 14

MUST / MUST NOT / SHOULD — per RFC 2119 + RFC 8174.

## Inputs

```
company_root: <path>
overlap_threshold: <float>        # default 0.70
stale_days: <int>                 # default from settings.skill_library.stale_days (default 60)
mature_improvement_window_days: <int>  # default 90
mature_improvement_count: <int>   # default 3
max_proposals_per_pass: <int>     # default 3 per pass (conservative)
dry_run: <bool>                   # default true
```

## Procedure

### Phase 1 — Load inventory

1. Enumerate `$COMPANY_ROOT/skills/*/SKILL.md`.
2. Parse frontmatter: `name`, `description`, `lifecycle`, `metadata.version`,
   `metadata.kiho.capability`, `metadata.kiho.topic_tags`, `supersedes`,
   `deprecated`.
3. Read `$COMPANY_ROOT/company/skill-performance.jsonl` (if present) for
   `invocations`, `last_invoked`, `success_rate`, `median_duration_ms`,
   `user_correction_rate` per skill.
4. Read `$COMPANY_ROOT/skills/<id>/versions/` listings to count improvements
   in the window.
5. Build an in-memory index of all skills with computed fields.

### Phase 2 — Merge pass

1. For each pair `(A, B)` with `A.id < B.id`:
   - Compute `sim = text_similarity(A.description + A.body, B.description + B.body)`
   - If `sim >= overlap_threshold`:
     - Determine dominant skill: higher `invocations`, then higher
       `success_rate`, then earlier `created_at`
     - Other → `merge_candidate`
     - Rationale: "Feature overlap {sim:.2f}; {winner.id} dominant in usage."
2. Limit to top `max_proposals_per_pass` by `sim`.
3. Emit `merge_proposals[]` — caller invokes `skill-improve` with the
   proposed merge diff (skill-improve Phase 2 handles the patch).

### Phase 3 — Deprecate pass

1. For each skill:
   - If `invocations_last_stale_days == 0`
     AND `bin/kiho_rdeps.py <skill_id>` returns zero dependents
     AND skill is not `_meta/` infrastructure
     AND `lifecycle != deprecated` already:
     → emit a `deprecate_proposal`.
2. Limit to `max_proposals_per_pass`.
3. Caller invokes `skill-deprecate` on approval.

### Phase 4 — Mature-tag pass

1. For each skill:
   - Count entries in `versions/` with `created_at` within
     `mature_improvement_window_days`
   - If count >= `mature_improvement_count` AND current
     `metadata.lifecycle != mature`:
     → emit a `mature_tag_proposal` (adds `lifecycle: mature` marker).
2. This is a LIGHT-weight mutation — skill stays active; only the tag
   changes. Route via `skill-improve` with a metadata-only diff.

### Phase 5 — Update consolidation ledger

Append to `$COMPANY_ROOT/company/consolidation-ledger.jsonl`:

```json
{"ts": "<iso>", "action": "skill_merge_proposed|skill_deprecate_proposed|skill_mature_tagged|applied|skipped",
 "skill_id": "...", "counterpart_id": "...|null", "similarity": <float|null>,
 "decision_by": "<user|auto>"}
```

## Response shape

```json
{
  "status": "ok | error",
  "backend": "sentence-transformers | sklearn-tfidf | stdlib-tfidf",
  "inventory_size": <int>,
  "merge_proposals": [
    {"winner_id": "...", "loser_id": "...", "sim": 0.78, "rationale": "..."}
  ],
  "deprecate_proposals": [
    {"skill_id": "...", "days_since_last_invoke": 75, "rationale": "..."}
  ],
  "mature_tag_proposals": [
    {"skill_id": "...", "improvements_in_window": 4}
  ],
  "applied": <int>,
  "review_required": <int>
}
```

## Anti-patterns

- MUST NOT deprecate `_meta/` infrastructure skills (skill-derive,
  skill-improve, skill-find, kiho-setup, etc.). They have zero-invocation
  idle windows by design.
- MUST NOT merge skills across different `capability` verbs (e.g., merging
  a `create` skill into a `read` skill is a type error).
- MUST NOT tag a skill `mature` while there's an open critic verdict
  flagging it for evolve.
- Do NOT bypass kb-manager / skill-improve / skill-deprecate — they own
  version bumping, changelog writes, and reverse-dependency update.

## Grounding

v6 plan §3.8 — "Skill library consolidation: pair-wise feature overlap
≥ 0.70 merge via skill-improve; zero invocations ≥ stale_days + no
dependents → propose deprecate; ≥ 3 improvements in 90 days → mature tag."
