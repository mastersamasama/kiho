# Skill ranking (v6 §3.10 — performance amplification)

When `design-agent` Phase 2.3 or Phase 3.5.5 has multiple existing skills that could cover a candidate's need, rank them with a performance-weighted score and route the top match to USE, the middle to IMPROVE, and the bottom (under a hard floor) to DEPRECATE.

## Data source

Reads `$COMPANY_ROOT/company/skill-performance.jsonl` — emitted by `bin/kiho_telemetry_rollup.py --company-root` at CEO DONE step 10 over a 30-day window.

Each row:

```json
{
  "skill_id": "sk-XXX",
  "invocations": 42,
  "success_rate": 0.88,
  "median_duration_ms": 12000,
  "user_correction_rate": 0.08,
  "last_invoked": "2026-04-18T09:14:22Z",
  "window_days": 30
}
```

Skills absent from the file (never invoked in window) score 0 and fall into the bottom bucket automatically.

## Formula

```
score(skill) = w_s × success_rate
             + w_c × (1 − user_correction_rate)
             + w_f × freshness
```

where:

```
freshness = max(0, 1 − days_since_last_invocation / 90)
```

Weights come from `settings.performance.rank_weights` (must sum to 1.0). Defaults:

| weight | default | key |
|---|---|---|
| `w_s` | 0.5 | `success_rate` |
| `w_c` | 0.3 | `inverse_correction_rate` |
| `w_f` | 0.2 | `freshness` |

## Routing

Given ranked candidates covering the same need:

| Rank slot | Action | Notes |
|---|---|---|
| Top | **USE** | Reference in the candidate's `skills[]` |
| Middle | **IMPROVE** | Flag for `skill-improve` in the next evolution cycle |
| Bottom where `score < 0.4` AND no reverse dependents (`bin/kiho_rdeps.py` returns 0) | **DEPRECATE** | Propose in next `consolidate-skill-library` run |

Skills in Bottom rank WITH dependents are kept (downgrading would break the dependent chain) — only logged as "underperforming but retained (N dependents)".

## Tie-break

When `|score(A) − score(B)| < 0.05`:

1. Prefer higher `invocations` (more evidence)
2. Prefer more recent `last_invoked`
3. Prefer non-`deprecated` lifecycle
4. Prefer `mature` lifecycle over `draft`
5. Lexicographic `skill_id` as last resort

## Cold-start behavior

Less than 5 invocations in window → treat score as `success_rate` alone (no penalty for low volume; avoid cold-start bias pushing new skills to deprecate).

## Example

Three candidates for "screenshot diff":

| skill_id | invocations | success_rate | correction_rate | days_since_last | freshness | score |
|---|---|---|---|---|---|---|
| sk-screenshot-diff | 24 | 0.92 | 0.04 | 2 | 0.978 | 0.5×0.92 + 0.3×0.96 + 0.2×0.978 = 0.944 |
| sk-visual-diff-basic | 6 | 0.67 | 0.17 | 45 | 0.500 | 0.5×0.67 + 0.3×0.83 + 0.2×0.500 = 0.684 |
| sk-pixel-compare-legacy | 1 | 0.0 | 1.0 | 120 | 0.000 | 0.5×0.0 + 0.3×0.0 + 0.2×0.0 = 0.000 |

Routing: sk-screenshot-diff → USE; sk-visual-diff-basic → IMPROVE; sk-pixel-compare-legacy → DEPRECATE (score < 0.4, check dependents).

## Consumer integration

- **design-agent Phase 2.3** (validate each skill): when multiple candidates appear via `skill-find`, invoke ranking. Add `rank_score`, `rank_bucket`, `rank_peer_skill_ids` to the recipe output.
- **design-agent Phase 3.5.5** (skill reconciliation): same routing applied to candidate-proposed skills.
- **consolidate-skill-library**: uses the same scoring for its merge/deprecate pass — a skill in the bottom bucket in THREE consecutive cycles becomes a hard deprecate candidate.

## Anti-patterns

- Don't rank without performance data — skills with 0 invocations score 0 but that doesn't mean bad quality. Apply cold-start rule.
- Don't deprecate top-ranked skills just because a slightly-better variant exists — merge via `skill-improve` instead.
- Don't manually tweak `rank_weights` per-skill; the weights are company-wide. If a class of skills needs different treatment, propose a new settings field.
