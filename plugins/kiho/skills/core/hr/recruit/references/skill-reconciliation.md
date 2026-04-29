# Phase 3.5 detail — cross-candidate skill reconciliation

This reference documents how recruit converges 4 candidates' skill proposals
into a conflict-free skill set in `$COMPANY_ROOT/skills/`.

## Why this phase exists

Without Phase 3.5, four candidates authoring in parallel produce:

- candidate A → `sk-visual-qa-playwright`
- candidate B → `sk-visual-regression-testing`
- candidate C → `sk-ui-invariant-checks`
- candidate D → `sk-screenshot-compare`

All four overlap 0.60-0.80. The library ends up with 4 near-duplicate skills
and future recruits cannot cleanly pick. Phase 3.5 converges them ONCE
before interviews.

## Invariants

- Every candidate's `skills[]` **MUST** reference only IDs present in
  `$COMPANY_ROOT/skills/INDEX.md` after Phase 3.5 completes.
- No skill marked `deprecated: true` may be in a candidate's `skills[]`
  unless paired with `superseded_by:` pointing to a present skill.
- Phase 3.5 honors the SAME `max_skills_authored_per_recruit` budget as
  Phase 2 — budget is shared, not per-phase.

## Step-by-step

### 3.5.1 UNION

```python
proposed = {}
for candidate in candidates_1_to_4:
    for wanted in candidate.skills_wanted:
        proposed.setdefault(wanted.id_hint, []).append((candidate, wanted))
```

A single id_hint key may appear in multiple candidates' lists with the same
or divergent `feature_list` values. This is intentional — the union is not
deduplicated yet.

### 3.5.2 Classify against existing library

For each unique id_hint:

```
existing = load($COMPANY_ROOT/skills/<id>/SKILL.md) or None

if existing:
    coverage = feature_coverage(merged_wanted_features, existing.features)
    if coverage >= 0.80:  action = RESOLVED_REUSE
    elif coverage < 0.40: action = CONFLICT_NARROW     # existing too narrow
    else:                 action = PARTIAL_REUSE        # IMPROVE candidate
else:
    neighbor = semantic_neighbor_exists(merged_wanted_features_desc)
    if neighbor is not None:
        action = NAMING_CONFLICT    # use neighbor.id or fold into it
    else:
        action = AUTHOR_NEW
```

where `merged_wanted_features = ⋃ w.feature_list for each w in proposed[id_hint]`
and `merged_wanted_features_desc = " ".join(merged_wanted_features)`.

**Concrete helper — `semantic_neighbor_exists` (v6.0.1 Fix P3).**
Replaces the prior `find_semantic_neighbor` pseudocode with a real call
into the unified-search skill:

```python
# Phase 3.5.2 — semantic neighbor detection
def semantic_neighbor_exists(wanted_desc: str) -> tuple[str, float] | None:
    """Returns (skill_id, score) if a semantic neighbor exists in library >= 0.70.

    Guarded on `$COMPANY_ROOT/skills/unified-search/SKILL.md` existing —
    on fresh installs or where unified-search is not yet scaffolded, returns
    None and the caller falls through to AUTHOR_NEW (legacy behavior).
    """
    unified_search_path = Path(os.environ["COMPANY_ROOT"]) / "skills" / "unified-search" / "SKILL.md"
    if not unified_search_path.exists():
        return None
    results = unified_search(
        query=wanted_desc,
        scope=["skills"],
        limit=5,
        min_score=0.70,
    )
    if results and results[0].score >= 0.70:
        return (results[0].skill_id, results[0].score)
    return None
```

### 3.5.3 DEDUPE across candidates

Compare every pair `(wanted_A, wanted_B)` from DIFFERENT candidates:

```
for (i, j) in pairs(candidates):
    for w_a in candidates[i].skills_wanted:
        for w_b in candidates[j].skills_wanted:
            if w_a.id_hint != w_b.id_hint:
                overlap = feature_overlap(w_a.feature_list, w_b.feature_list)
                if overlap >= 0.70:
                    MERGE(w_a, w_b)
```

**Concrete helper — `feature_overlap` (v6.0.1 Fix P3).**
Replaces the prior `jaccard(...)` pseudocode with embedding-based similarity
so near-synonym feature strings ("touch target 44px", "tap target minimum
size") merge correctly where literal Jaccard would fail:

```python
# Phase 3.5.3 — cross-candidate feature overlap
def feature_overlap(a_features: list[str], b_features: list[str]) -> float:
    """Returns similarity in [0,1] between two candidate skill feature lists.

    Calls `bin/embedding_util.py text_similarity` under the hood — same
    engine used by design-agent Step 2.3 external-catalog matching and by
    consolidate-skill-library clustering. On import failure (no numpy /
    no embedding model), falls back to literal Jaccard (legacy behavior).
    """
    a_text = " ".join(a_features)
    b_text = " ".join(b_features)
    try:
        return embedding_util.text_similarity(a_text, b_text)
    except ImportError:
        # Fallback to Jaccard if embedding stack is unavailable
        a_set, b_set = set(a_features), set(b_features)
        if not a_set and not b_set:
            return 0.0
        return len(a_set & b_set) / len(a_set | b_set)
```

`MERGE` operation:
1. Pick the "better" id_hint — prefer the one whose candidate had higher
   rubric_avg in Phase 3.3 self-gates; tie-break by alphabetical order for
   stability.
2. Fold `feature_list_merged = w_a.features ∪ w_b.features`.
3. Record in `.kiho/state/recruit/<slug>/reconciliation-ledger.jsonl`:
   ```json
   {"op": "merge", "kept": "sk-visual-qa", "dropped": "sk-visual-regression",
    "reason": "jaccard 0.74", "candidates_affected": [1, 3]}
   ```
4. Rewrite both candidates' `skills_wanted` to use the kept ID with merged
   features.

### 3.5.4 DEPRECATE existing

For each existing skill ID in the library (not just in candidates'
proposals), check if the candidates' collective proposal obsoletes it:

```
for existing_id in INDEX.md:
    existing = load(existing_id)
    if existing.lifecycle in {"draft", "active"} \
       and not existing.deprecated \
       and not any_agent_depends_on(existing_id):

        combined_coverage = feature_coverage(
            merged_candidate_features_for_domain(existing.domain),
            existing.features
        )

        quality_score = read_skill_performance_rollup(existing_id)
        # See settings.performance.rank_weights; default:
        #   0.5 * success_rate + 0.3 * (1 - correction_rate) + 0.2 * freshness

        if combined_coverage >= 0.95 and quality_score <= 0.60:
            DEPRECATE(existing_id, superseded_by=<new_or_merged_id>)
```

`DEPRECATE` invokes `kiho-kb-manager op=kb-update`:

```yaml
# on the existing SKILL.md frontmatter:
deprecated: true
superseded_by: <new_id>
deprecated_reason: "replaced by v6 recruit <slug>; combined candidate coverage 0.97 vs quality 0.54"
deprecated_at: <iso>
```

Existing agents whose `skills[]` still point to the deprecated ID are
**NOT** silently re-pointed — `memory-reflect` on those agents will surface
the deprecation next time they run. This is a deliberate slow migration to
avoid surprise behavior changes.

### 3.5.5 IMPROVE existing

For each `PARTIAL_REUSE` action from 3.5.2:

```
skill-improve(
  skill_id: <existing_id>,
  proposed_delta: {
    new_features: merged_wanted_features \ existing.features,
    rationale: aggregated_candidate_rationales,
    driver: "v6-recruit-phase-3.5"
  },
  committee_mode: "light",
  authorized_by: "kiho-hr-lead"
)
```

On approval: semver bump on the existing SKILL.md; all candidates'
`skills_wanted` now reference the improved version (same ID, bumped
version embedded in the SKILL.md).

On rejection: demote to `AUTHOR_NEW` — the candidates fork under a new ID.

### 3.5.6 AUTHOR truly-new

For all remaining `AUTHOR_NEW` proposals, reuse Phase 2.4 pipeline:

```
kiho-researcher → skill-derive → kb-manager kb-add
```

Budget check: `Phase 2 authorings + 3.5 authorings ≤ max_skills_authored_per_recruit`.

If budget exhausted: ASK_USER via CEO with the overflow list, allowing user
to (a) raise the cap once, (b) drop least-important skills, (c) abort.

### 3.5.7 RESOLVE candidate agent.md files

For each candidate:

```python
final_ids = []
for wanted in candidate.skills_wanted:
    final_id = reconciliation_result(wanted)   # from 3.5.2-3.5.6
    assert (COMPANY_ROOT / "skills" / final_id / "SKILL.md").exists()
    final_ids.append(final_id)

candidate.agent_md["skills"] = final_ids
rewrite(candidate.agent_md_path)
```

Hard fail if any ID does not resolve. Phase 3.5 must leave every candidate
with a 100% resolved skills list.

### 3.5.8 INDEX.md update

Invoke `kiho-kb-manager op=kb-update` on `$COMPANY_ROOT/skills/INDEX.md`
with:
- rows added for `AUTHOR_NEW` skills
- rows bumped for `IMPROVE` (version column)
- rows marked deprecated with `superseded_by` column

## Reconciliation ledger format

`.kiho/state/recruit/<slug>/reconciliation-ledger.jsonl` — append-only:

```json
{"ts": "<iso>", "op": "union",       "candidate_count": 4, "unique_ids": 11}
{"ts": "<iso>", "op": "classify",    "id": "sk-visual-qa-invariants",   "action": "AUTHOR_NEW"}
{"ts": "<iso>", "op": "classify",    "id": "sk-screenshot-diff",        "action": "AUTHOR_NEW"}
{"ts": "<iso>", "op": "merge",       "kept": "sk-visual-qa-invariants", "dropped": "sk-ui-invariant-checks", "jaccard": 0.74, "candidates_affected": [1, 3]}
{"ts": "<iso>", "op": "improve",     "id": "sk-a11y-tap-targets",       "features_added": ["touch-target-44px-floor"], "approved": true}
{"ts": "<iso>", "op": "deprecate",   "id": "sk-legacy-screenshot",      "superseded_by": "sk-screenshot-diff", "coverage": 0.97, "quality_score": 0.54}
{"ts": "<iso>", "op": "author",      "id": "sk-screenshot-diff",        "via": "skill-derive", "budget_used": 1}
{"ts": "<iso>", "op": "resolve_all", "candidate_1_skills": ["sk-visual-qa-invariants", "sk-screenshot-diff", "sk-a11y-tap-targets"], ...}
```

Ledger is load-bearing for audit and for debugging post-hire library state.

## Failure routes

| Situation | Route |
|---|---|
| Semantic-neighbor check flags conflicts that design-agent didn't anticipate | ASK_USER with the conflict map; user picks keep/merge/author-new per row |
| Budget exhausted during 3.5.6 AUTHOR_NEW | ASK_USER with overflow list (raise cap / drop / abort) |
| skill-improve committee rejects a PARTIAL_REUSE delta | demote to AUTHOR_NEW; check budget |
| DEPRECATE candidate has active dependents (agents) | Skip the deprecation; log `deprecate_blocked_has_dependents`; do not re-point agents |
| Any candidate still has unresolved IDs after 3.5.7 | Hard fail → `status: reconciliation_failed`; abort hire |

## Interaction with settings

- `settings.skill_library.auto_consolidate_research == false`: skip
  `DEPRECATE` (3.5.4) and `IMPROVE` (3.5.5) steps entirely; only AUTHOR_NEW
  and RESOLVED_REUSE paths run.
- `settings.performance.rank_skills_by_performance == true`: use the
  weighted quality score; false → default to a fixed 0.5 quality score.

## Worked example — 3 candidates want overlapping visual-QA skills

**Union (3.5.1):**
- candidate 1: `{sk-visual-qa-invariants, sk-screenshot-diff}`
- candidate 2: `{sk-ui-invariant-checks, sk-a11y-tap-targets}`
- candidate 3: `{sk-visual-qa-playwright, sk-screenshot-diff}`
- candidate 4: `{sk-visual-qa-invariants, sk-a11y-tap-targets, sk-ui-flow-qa}`

**Classify (3.5.2):** none exist yet — all AUTHOR_NEW.

**Dedupe (3.5.3):**
- `sk-visual-qa-invariants` (c1, c4) ↔ `sk-ui-invariant-checks` (c2):
  jaccard 0.78 → MERGE; keep `sk-visual-qa-invariants`.
- `sk-visual-qa-invariants` ↔ `sk-visual-qa-playwright` (c3): jaccard 0.71
  → MERGE; keep `sk-visual-qa-invariants` (broader).
- `sk-screenshot-diff` (c1, c3): same ID — trivial union; features merged.
- `sk-a11y-tap-targets` (c2, c4): same ID — trivial union.
- `sk-ui-flow-qa` (c4): no overlap ≥ 0.70 with any; stays.

**Author (3.5.6):** 4 new skills needed:
`sk-visual-qa-invariants`, `sk-screenshot-diff`, `sk-a11y-tap-targets`,
`sk-ui-flow-qa`. Budget: `max_skills_authored_per_recruit = 3` → overflow.
ASK_USER: user raises cap to 4 for this recruit.

**Resolve (3.5.7):** all four candidates now have resolved IDs:
- c1: `[sk-visual-qa-invariants, sk-screenshot-diff]`
- c2: `[sk-visual-qa-invariants, sk-a11y-tap-targets]`
- c3: `[sk-visual-qa-invariants, sk-screenshot-diff]`
- c4: `[sk-visual-qa-invariants, sk-a11y-tap-targets, sk-ui-flow-qa]`

Note: c1 and c3 now have identical skill lists. Their differentiator comes
from persona/soul traits (seniority, philosophy) — the whole point of
diversity axes.

## Anti-patterns

- **MUST NOT** DEPRECATE a skill with active dependents. Always check
  `agents/*/agent.md` skills[] first.
- **MUST NOT** MERGE across domains. `sk-visual-qa-invariants` and
  `sk-rust-invariants` share the word "invariants" but merging them would
  destroy the library.
- **MUST NOT** let one candidate's skill list disappear entirely after
  reconciliation. Every candidate must leave Phase 3.5 with a non-empty
  `skills[]`.
- Do not re-point existing agents to deprecated skills' replacements
  silently. Let memory-reflect surface it on their next turn.
