# Gate 17 — novel contribution (v5.15)

Gate 17 asks one question before a draft skill is registered: *is this a genuinely novel contribution, or a near-duplicate of an existing skill the author could improve or derive from instead?*

> The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** in this document are to be interpreted as described in BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.

## Non-Goals

- **Not an LLM judge.** No model call, no sampling, no temperature. Pure computation.
- **Not an embedding search.** No vector index, no daemon, no drift across model versions.
- **Not a semantic parser.** No AST, no intent extraction from prose. arXiv 2604.02837 §4 confirms this direction is infeasible.
- **Not a replacement for Gate 14.** Gate 14 catches mis-categorization ("this skill is in the wrong domain"); Gate 17 catches redundancy ("this skill already exists under a different name"). Both run.
- **Not a retroactive auditor.** Gate 17 runs on new drafts only. Catalog-wide confusability drift is tracked via `catalog_walk_audit.py` and the `similarity_scan.py --catalog-health` metric.
- **Not a merge tool.** When Gate 17 catches a near-duplicate, the suggested action is `skill-improve` on the top match OR `skill-derive` to specialize it. Mechanical two-skill merge is an open problem in the 2024-2026 literature.
- **Not a soft suggestion.** At Jaccard ≥ 0.60 the gate blocks with exit code 1. The only escape is a CEO-committee `--force-overlap` vote.

**What this gate IS.** A deterministic Jaccard-on-shingles similarity scan against every registered skill's description, with three bands (novel / warn / block) and a JSON report surfacing the top-3 matches with shared tokens. The implementation is `skills/_meta/skill-create/scripts/similarity_scan.py` (~260 lines, zero PyPI dependencies, runs in <200ms on the current 39-skill catalog).

**Pipeline placement:**

```
Step 3 frontmatter draft
   │
   ▼
Gate 14 (catalog_fit.py) ─────► domain routing-description overlap ≥ 1 keyword
   │                             (cheap; checks "which domain", not "which skills")
   ▼
Gate 17 (similarity_scan.py) ──► Jaccard vs every existing skill's description
   │                             │
   │                             ├─ j ≥ 0.60  → BLOCK      (exit 1)  → suggested_action: improve <top-match>
   │                             ├─ 0.30–0.60 → WARN       (exit 0)  → surface top-3 in committee proposal
   │                             └─ j < 0.30  → NOVEL      (exit 0)  → proceed
   ▼
Gate 15 (budget_preflight.py)
```

## Contents
- [Why this gate exists](#why-this-gate-exists)
- [Procedure](#procedure)
- [Thresholds](#thresholds)
- [Tokenization and shingle rules](#tokenization-and-shingle-rules)
- [Empirical baseline (kiho catalog, Apr 2026)](#empirical-baseline-kiho-catalog-apr-2026)
- [Worked examples](#worked-examples)
- [Common pitfalls](#common-pitfalls)
- [Troubleshooting Q&A](#troubleshooting-qa)
- [Failure routes (decision tree)](#failure-routes-decision-tree)
- [The `--force-overlap` CEO override](#the---force-overlap-ceo-override)
- [Catalog health mode](#catalog-health-mode)
- [Success metrics (post-rollout validation)](#success-metrics-post-rollout-validation)
- [Rejected alternatives](#rejected-alternatives)
- [Scale upgrade path](#scale-upgrade-path)
- [Grounding](#grounding)

## Why this gate exists

The research foundation is a single load-bearing paper:

> **arXiv 2601.04748 §5.2:** *"At small scales (|S| ≤ 20), accuracy remains above 90%, but degrades steadily beyond |S| = 30, falling to approximately 20% at |S| = 200."*
>
> **arXiv 2601.04748 §5.3:** *"At identical |S| = 20, replacing unique skills with base-competitor pairs causes an 18–30% accuracy drop. This demonstrates that semantic structure determines selection difficulty."*

Translation into kiho terms: **two similar skills hurt more than two extra unrelated skills**. The right metric to budget against is *semantic confusability*, not catalog size. kiho at 39 registered skills is already past the |S| = 30 inflection documented in §5.2 — the phase transition is already happening, silently.

Gate 14 (catalog-fit, v5.14) is a cheap single-domain check. Gate 17 is the complementary full-catalog check. The placement diagram at the top of this file shows how they compose.

## Procedure

`skill-create` Step 10.5 (after Gate 14, before Gate 15):

```
python skills/_meta/skill-create/scripts/similarity_scan.py \
    --description "$(cat .kiho/state/drafts/sk-<slug>/description.txt)" \
    --catalog-root skills \
    --exclude .kiho/state/drafts/sk-<slug>/SKILL.md
```

The `--exclude` flag prevents the draft from matching itself when it is already registered under `.kiho/state/drafts/`.

The script:

1. Walks `skills/**/SKILL.md` and loads every skill's `name` and `description` from the frontmatter block.
2. Tokenizes each description: lowercase, 3+ character tokens, stop words removed (same `STOP_WORDS` set as Gate 14's `catalog_fit.py`).
3. Builds shingles: unigrams ∪ bigrams.
4. Computes Jaccard similarity between the draft's shingle set and every existing skill's shingle set.
5. Sorts matches descending, keeps the top 3.
6. Classifies based on the best match's Jaccard value:
   - `j ≥ 0.60` → **near_duplicate** (block, exit 1)
   - `0.30 ≤ j < 0.60` → **related_review** (warn, exit 0)
   - `j < 0.30` → **novel** (pass, exit 0)
7. Emits a JSON report with status, top 3 matches, shared-token samples, unique-to-each samples, and a `suggested_action` field.

## Thresholds

| Band | Jaccard range | Status | Exit code | Suggested action |
|---|---|---|---|---|
| Block | `j ≥ 0.60` | `near_duplicate` | 1 | `improve <top-match>` |
| Warn | `0.30 ≤ j < 0.60` | `related_review` | 0 | `consider derive from <top-match>` |
| Pass | `j < 0.30` | `novel` | 0 | `create-novel` |

The defaults come from the 2024–2025 fuzzy-dedup literature. Nelhage's fuzzy-dedup writeup settles on Jaccard ≈ 0.60 as the "likely duplicate" line for short-text dedup, and 0.30 as the "unrelated" floor. LSHBloom (arXiv 2411.04257) uses the same band for internet-scale markdown dedup.

Both thresholds are tunable via CLI flags (`--block-threshold`, `--warn-threshold`). Start at the defaults. If false positives dominate the first rollout week, raise the block threshold to 0.65 rather than switching to embeddings. **Do not switch to embeddings** — that defeats the determinism + explainability goal and requires a daemon.

## Tokenization and shingle rules

Same `STOP_WORDS` set as `catalog_fit.py`. Notable removals: `use`, `used`, `using`, `user`, `agent`, `agents`, `kiho`, `skill`, `skills`, `new`, `existing`. These words appear in almost every skill description and carry zero discriminating signal.

Token regex: `[A-Za-z][A-Za-z0-9_-]{2,}`. 3-character minimum filters trivial connectives. `_` and `-` preserved so identifiers like `skill-find` and `sk_013` stay as one token.

Shingles: unigrams ∪ bigrams. A bigram is `"token1__token2"` (double underscore separator). Example for tokens `[runtime, discovery, searches]`:

- unigrams: `{runtime, discovery, searches}`
- bigrams: `{runtime__discovery, discovery__searches}`
- shingle set: `{runtime, discovery, searches, runtime__discovery, discovery__searches}`

**Why unigrams + bigrams, not pure 3-shingles?** 3-shingles are the canonical choice at long-document dedup (tens of thousands of tokens). kiho descriptions are 50–300 tokens after stop-word removal. 3-shingles would be too sparse: two closely-related descriptions could end up with zero overlapping 3-grams even when their content is near-identical. Unigrams + bigrams give the same discrimination as 3-shingles on long text plus much better recall on short text. This is the same choice made by markdown-scale dedup tools like MinHash LSH in the 2024 Milvus / Pinecone writeups.

## Empirical baseline (kiho catalog, Apr 2026)

Before setting thresholds on external literature alone, validate against the real catalog. These numbers come from running `similarity_scan.py --catalog-health` against the 39-skill Apr 2026 catalog and enumerating all 741 pairs.

### Distribution

| Jaccard range | Pair count | % of total | Interpretation |
|---|---|---|---|
| `j ≥ 0.60` (block) | **0** | 0.0% | No pair would be blocked |
| `0.30 ≤ j < 0.60` (warn) | **0** | 0.0% | No pair would warn |
| `0.20 ≤ j < 0.30` | **0** | 0.0% | — |
| `0.10 ≤ j < 0.20` | **3** | 0.4% | The "most-related" cluster |
| `0.00 ≤ j < 0.10` | **738** | 99.6% | Effectively uncorrelated |

### Summary statistics

| Metric | Value | Notes |
|---|---|---|
| Catalog size | 39 skills | Past the |S| = 30 inflection |
| Pairs evaluated | 741 | n·(n−1)/2 |
| Mean Jaccard | **0.0146** | Very low |
| Stdev | 0.0151 | Mean and stdev are the same order |
| Median | 0.0114 | Below the mean → long right tail |
| p95 | 0.0387 | Top 5% still below 0.04 |
| p99 | 0.0809 | Top 1% still below 0.10 |
| Maximum | **0.1049** | `kb-add` × `kb-ingest-raw` |

### Top 10 most-similar pairs

| Jaccard | Pair | Classification |
|---|---|---|
| 0.1049 | `kb-add` × `kb-ingest-raw` | novel (below 0.30) |
| 0.1047 | `kiho-spec` × `engineering-kiro` | novel |
| 0.1020 | `kb-delete` × `kb-update` | novel |
| 0.0980 | `session-context` × `state-read` | novel |
| 0.0940 | `kb-add` × `kb-update` | novel |
| 0.0915 | `memory-consolidate` × `memory-read` | novel |
| 0.0892 | `skill-derive` × `skill-improve` | novel |
| 0.0809 | `kiho` × `engineering-kiro` | novel |
| 0.0797 | `research` × `kb-search` | novel |
| 0.0783 | `kb-add` × `kb-delete` | novel |

### Calibration

The block threshold of 0.60 sits **5.7× above** the current maximum (0.1049). The warn threshold of 0.30 sits **2.9× above** the maximum. In concrete terms:

- **Zero existing skills** would be blocked or warned if Gate 17 were re-run against them today. There is no retroactive invalidation risk.
- The next skill that matches this pattern (a genuine near-duplicate at Jaccard ≈ 0.70) is very far from anything that currently exists — the threshold will not trip on honest evolution of the catalog.
- The top-10 list reads intuitively: every pair is semantically adjacent (sibling `kb-*` operations, `session-context`/`state-read` both reading runtime state, etc.). Gate 17's shingle-based method is aligned with human intuition at the low end of the scale.

If a future catalog addition brings maximum pairwise Jaccard above **0.30** without tripping Gate 17, that is a signal that either (a) Gate 17 had a false negative (re-audit the scan), or (b) the threshold needs to drop. Track the max quarterly via `--catalog-health` (see [Success metrics](#success-metrics-post-rollout-validation)).

**Reproducing these numbers.** The script is self-contained:

```bash
python -c "
import sys
sys.path.insert(0, 'skills/_meta/skill-create/scripts')
from similarity_scan import load_catalog_skills, jaccard
from pathlib import Path
e = load_catalog_skills(Path('skills'), set())
pairs = sorted(
    [(jaccard(a['shingles'], b['shingles']), a['name'], b['name'])
     for i, a in enumerate(e) for b in e[i+1:]],
    reverse=True
)
for j, x, y in pairs[:10]:
    print(f'{j:.4f}  {x} x {y}')
"
```

## Worked examples

### Example 1 — near-duplicate block (Jaccard 0.73)

Draft description (lightly reworded clone of `skill-find`):

> Runtime skill discovery that searches available skills across all tiers. Globs each tier's skills/*/SKILL.md, extracts frontmatter descriptions, performs lexical matching against a query, and returns a ranked list with tier, name, description, and lifecycle status. Use when an agent needs to find the right skill for a task.

Real `skill-find` description:

> Runtime skill discovery that searches available skills across all tiers. Globs each tier's skills/*/SKILL.md, extracts frontmatter descriptions, performs lexical matching against a query, and returns a ranked list with tier, name, description, and lifecycle status. Use when an agent needs to find the right skill for a task, when the CEO routes a request to a skill, or when any agent says "find a skill for", "is there a skill that", "which skill handles". Also used by the skill engine to check for duplicates before creating new skills.

Result:

```json
{
  "status": "near_duplicate",
  "top_matches": [
    {"name": "skill-find", "jaccard": 0.7324, ...}
  ],
  "suggested_action": "improve skill-find"
}
```

Exit code 1. The author is told to improve the existing `skill-find` rather than create a second one.

### Example 2 — related review warn (Jaccard 0.56)

Draft description (substantive rewording with same responsibilities):

> Runtime skill finder that looks up available skills across all tiers. Walks each tier's skills/*/SKILL.md, extracts frontmatter descriptions, performs lexical matching against a query, returns ranked results with tier, name, description, and lifecycle. Use when an agent needs to find the right skill, when CEO routes a task, or when any agent says find a skill for, is there a skill, which skill handles. Used to check duplicates before creating new skills.

Result:

```json
{
  "status": "related_review",
  "top_matches": [
    {"name": "skill-find", "jaccard": 0.5632, ...}
  ],
  "suggested_action": "consider derive from skill-find"
}
```

Exit code 0. The author is warned but not blocked. They should explicitly acknowledge the related skill in the committee proposal and explain why this is not a duplicate.

### Example 3 — novel pass (Jaccard 0.08)

Draft description:

> Profile an agent's red-line DSL for runtime enforcement by extracting IF/AND/THEN clauses from the Soul section and emitting a compiled deny-list that the CEO pre-committee gate can apply in constant time.

Result:

```json
{
  "status": "novel",
  "top_matches": [
    {"name": "soul-apply-override", "jaccard": 0.0826, ...}
  ],
  "suggested_action": "create-novel"
}
```

Exit code 0. Gate 17 passes silently.

## Common pitfalls

These are the five most likely ways to mis-use Gate 17. Each is a real failure mode observed during v5.15 smoke testing or predictable from the implementation.

### P1 — Running without `--exclude` on an already-registered draft

**Symptom:** `status: near_duplicate` with `jaccard: 1.0` against a match that *is the draft itself*.

**Cause:** the draft has already been staged under `.kiho/state/drafts/sk-<slug>/SKILL.md`, and `similarity_scan.py` walks the full `skills/` tree plus any draft tree. Without `--exclude`, the draft matches itself perfectly.

**Fix:** always invoke with `--exclude .kiho/state/drafts/sk-<slug>/SKILL.md`. skill-create Step 10.5 does this automatically; manual invocations must remember.

**Detection:** any Jaccard ≥ 0.99 against a match whose `path` starts with `.kiho/state/drafts/` is almost certainly a self-match. The script does not yet flag this as a warning.

### P2 — Short description artificially low Jaccard

**Symptom:** a draft that *feels* redundant passes with Jaccard ≈ 0.15 when human judgment says it should be blocked.

**Cause:** the draft description is <30 tokens after stop-word removal. A short shingle set has low Jaccard against any long description because the denominator (union) is dominated by the longer set. This is a known edge case in markdown-scale dedup.

**Fix:** never ship a skill description under 100 characters of natural text (≥ ~20 substantive tokens). Gate 2 frontmatter validation already enforces a 50-character minimum; Gate 17's empirical floor is higher. If Gate 17 passes on a short description but Gate 14 still flags it, trust Gate 14 and lengthen.

**Why we accept this:** short descriptions are a bad idea for triggering accuracy anyway. The v5.14 description-effectiveness rules (8 rules, 1024-char hard cap) push toward longer descriptions, and Gate 17's floor effect is aligned with that push.

### P3 — STOP_WORDS eats a distinguishing token

**Symptom:** two drafts about genuinely different topics share a surprisingly high Jaccard because their distinguishing word got filtered.

**Cause:** the `STOP_WORDS` set (inherited from `catalog_fit.py`) removes `use`, `user`, `agent`, `kiho`, `skill`, `new`, `existing` — all of which can be load-bearing in a skill description.

**Fix:** if two skills are about "user management" vs "agent management" and Gate 17 calls them similar, check the `shared_sample` and `unique_to_draft_sample` fields in the JSON output. If the distinguishing token got filtered, the correct fix is to **reword the description to use a synonym Gate 17 keeps** (e.g., "person", "role", "actor" instead of "user"). Do NOT edit the `STOP_WORDS` set — that would silently change Gate 14's behavior too.

### P4 — Assuming Gate 17 understands semantics

**Symptom:** a draft that semantically duplicates an existing skill but uses entirely different vocabulary passes with Jaccard ≈ 0.05.

**Cause:** Gate 17 is a shingle-overlap scan, not a semantic scan. It catches **lexical** near-duplicates. Two skills that describe the same operation in entirely different words (e.g., "retrieve a document" vs "fetch a file") will have near-zero Jaccard even though they mean the same thing.

**Fix:** Gate 17 is a cheap first-pass filter, not a complete check. The Gate 11 transcript review (v5.14) catches behavioral duplication that Gate 17 misses — if two skills end up producing identical Gate 11 transcripts, the `kb-search` review will surface the redundancy at registration time.

**Why we accept this:** a 100% semantic duplicate check requires an LLM judge or embedding model. Both are rejected as implementation choices in the [Rejected alternatives](#rejected-alternatives) section. Gate 17 catches the 80% case mechanically; the 20% tail falls through to human review.

### P5 — Boundary confusion at exactly 0.60 or 0.30

**Symptom:** a draft with Jaccard exactly 0.60 or exactly 0.30 — which band does it fall into?

**Answer:** the classification is **inclusive on the lower bound**:

- `j ≥ 0.60` → near_duplicate (blocked)
- `0.30 ≤ j < 0.60` → related_review (warn)
- `j < 0.30` → novel

The implementation uses Python `>=` for the block threshold and `>=` for the warn threshold, with strict `<` on the upper side. See `classify()` in `similarity_scan.py`:

```python
if best_j >= block_thr:  return "near_duplicate"
if best_j >= warn_thr:   return "related_review"
return "novel"
```

A Jaccard of exactly 0.60 blocks. A Jaccard of exactly 0.30 warns. Exact-boundary drafts are vanishingly rare (the 4-decimal computation means a tie requires exact shingle-set arithmetic) but the rule is documented for completeness.

## Troubleshooting Q&A

**Q: `top_matches` came back empty. What does that mean?**

A: Either (a) the catalog is empty (unlikely in kiho), (b) the catalog_root path is wrong, or (c) every existing skill's description tokenizes to an empty set (unlikely; would require a catalog-wide bug). Check exit code first — if it's 2, the script couldn't find the catalog. If it's 0 with empty matches, the draft has genuinely zero token overlap with anything, which usually means the description is either extraordinarily novel or under-specified. Read the draft description aloud; if it sounds substantive, the result is novel. If it sounds vague, revise and re-run.

**Q: Two matches tied at the same Jaccard — which is the "top" match?**

A: `top_matches()` in `similarity_scan.py` sorts by Jaccard descending, then by insertion order (which is alphabetical path order due to `sorted(catalog_root.rglob("SKILL.md"))`). Ties are broken deterministically but not by semantic priority. If you need to pick one for `suggested_action`, read all tied matches.

**Q: The warn band (0.30-0.60) is empty for my draft. Is that normal?**

A: Yes. The current kiho catalog has zero pairs in the warn band (see [Empirical baseline](#empirical-baseline-kiho-catalog-apr-2026)). Most drafts will either be novel (< 0.30) or near-duplicate (≥ 0.60) with very few falling in between. The warn band exists for the edge case of moderately overlapping operations on the same domain (e.g., a new KB-reading skill whose tokens partially match `kb-search` without fully duplicating it).

**Q: I want to re-run Gate 17 after revising the description. What's the workflow?**

A: After revising, re-run the full Step 3 bracket: Gate 14 → Gate 17 → Gate 15. Gate 14 may now fail if your new description drifted out of the parent domain's routing keywords; Gate 15 may now fail if the new description pushed total active description chars past the budget. Run them as a group — don't cherry-pick Gate 17.

```bash
python skills/_meta/skill-create/scripts/catalog_fit.py --description /tmp/new-desc.txt --domain <domain>
python skills/_meta/skill-create/scripts/similarity_scan.py --description /tmp/new-desc.txt --catalog-root skills --exclude .kiho/state/drafts/sk-<slug>/SKILL.md
python skills/_meta/skill-create/scripts/budget_preflight.py --new-desc-file /tmp/new-desc.txt --domain <domain>
```

**Q: `similarity_scan.py` took 4 seconds to run. Is something broken?**

A: No, but check catalog size. Current runtime on 39 skills is ~180ms. The O(n²) pairwise scan grows quadratically: at 80 skills expect ~750ms, at 150 skills expect ~3 seconds, at 200+ skills expect >5 seconds. When the runtime crosses 3 seconds, trigger the [Scale upgrade path](#scale-upgrade-path) to MinHash+LSH.

**Q: I want Gate 17 to check against deprecated skills too. Does it already?**

A: Yes. The scan walks every `SKILL.md` under `catalog_root` regardless of `metadata.lifecycle` state. A deprecated skill shim still carries its original description (the shim body changes but the frontmatter description is preserved — see `deprecation-shim.md`). So a draft that near-duplicates a deprecated skill is blocked with `suggested_action: improve <deprecated-slug>`, which the author should read as "the replacement is at `superseded-by`; improve *that* one instead." Gate 17 does not auto-rewrite the suggestion yet — future work.

**Q: Can I run Gate 17 on a skill that's already ACTIVE, just to check how it scores?**

A: Yes — use `--exclude` pointing at the skill's own `SKILL.md` path. This is useful for catalog audits after a cluster of related skills lands. Example:

```bash
python skills/_meta/skill-create/scripts/similarity_scan.py \
    --description "$(python -c "...extract description from kb-add...")" \
    --catalog-root skills \
    --exclude skills/kb/kb-add/SKILL.md
```

Result: kb-add's description compared against the 38 *other* skills. Top match is `kb-ingest-raw` at 0.10 (per [Empirical baseline](#empirical-baseline-kiho-catalog-apr-2026)).

## Failure routes (decision tree)

When Gate 17 produces a non-novel status, the author follows this decision tree. Each leaf is an actionable next step — no "think about it" escape hatches.

```
similarity_scan.py exit code
   │
   ├─ 0 + status: novel                 → PROCEED to Gate 15 (nothing more to do)
   │
   ├─ 0 + status: related_review        → READ shared_sample + unique_to_match_sample
   │                                      │
   │                                      ├─ Tokens overlap in a way I can fix by wording?
   │                                      │    → Go to Route C (tighten description, re-run)
   │                                      │
   │                                      └─ Skills genuinely serve different users/triggers?
   │                                           → Go to Route D (proceed with committee note)
   │
   ├─ 0 + status: near_duplicate_forced → READ committee session ID log
   │                                      │
   │                                      └─ PROCEED to Gate 15 (override already ratified)
   │
   └─ 1 + status: near_duplicate        → Is the draft a specialization of the top match?
                                          │
                                          ├─ YES → Go to Route B (skill-derive)
                                          │
                                          ├─ NO, draft adds new capability to an existing skill?
                                          │       → Go to Route A (skill-improve, most common)
                                          │
                                          ├─ NO, draft is legitimately distinct but vocabulary-similar?
                                          │       → Go to Route C (tighten description, re-run)
                                          │
                                          └─ Truly novel despite high Jaccard (very rare)?
                                                  → Go to Route E (CEO --force-overlap)
```

### Route A — Improve the existing skill (most common, ~80% of blocks)

Run `skill-improve` on the top-match with the draft description as the diff proposal. This is the mechanical fix when the draft is really "the existing skill but better" — it folds the new idea into the existing skill's body, bumps the version, preserves the old version in `versions/`, updates the changelog, and calls `kb-update`. No new slug is registered.

```bash
# Conceptual workflow — actual invocation via the skill-improve SKILL.md procedure
skill-improve \
    skill_path=<top-match-path> \
    failure_evidence="Gate 17 draft at <draft-path> duplicates this skill with Jaccard <j>; draft proposed these additions: <delta>" \
    test_case_delta="<optional new test case>"
```

### Route B — Derive a specialized variant (~10% of blocks)

When the draft is a legitimate specialization of the top match (narrower scope, distinct inputs, different consumer roles), run `skill-derive` instead. Example: `research-deep` is a derivation of `research` — both touch external docs, but `research-deep` adds BFS traversal and link-graph state that `research` does not. `skill-derive` preserves the parent's SKILL.md as a reference and creates a new slug with parent lineage metadata.

### Route C — Tighten the description and re-run (~8% of blocks)

When the draft is genuinely distinct but shares surface vocabulary with the top match, revise the description to use distinctive tokens and re-run the Step 3 bracket (Gate 14 → Gate 17 → Gate 15). Tactics:

- Replace generic domain verbs (`manage`, `handle`, `process`) with concrete operation names (`consolidate`, `reflect`, `broadcast`).
- Mention specific inputs and outputs the top match does not have.
- Avoid restating obvious category tokens (`skill`, `kiho`, `agent`) — they're filtered by STOP_WORDS anyway, so the re-rewrite is wasted if it only touches filtered words.
- Cite the concrete triggering phrases a user would say. Gate 17's shingle overlap does not count trigger phrases as special, but distinctive trigger phrases naturally introduce unique unigrams.

Re-run workflow:

```bash
# After revising the description file:
python skills/_meta/skill-create/scripts/catalog_fit.py \
    --description /tmp/new-desc.txt --domain <domain>
python skills/_meta/skill-create/scripts/similarity_scan.py \
    --description /tmp/new-desc.txt --catalog-root skills \
    --exclude .kiho/state/drafts/sk-<slug>/SKILL.md
python skills/_meta/skill-create/scripts/budget_preflight.py \
    --new-desc-file /tmp/new-desc.txt --domain <domain>
```

All three must pass. Do not cherry-pick — a Gate 17 re-pass could push the draft over the Gate 15 budget, and Gate 14 could fail if the revision drifted out of the domain routing vocabulary.

### Route D — Related-review with committee acknowledgement (~2% of blocks, all warns)

When Gate 17 warns (related_review), the draft is not blocked but the committee proposal must explicitly acknowledge the top-3 matches and explain why the new skill is distinct. The full JSON output is pasted into the proposal. The committee reads it and either approves or asks the author to take Route A or Route C instead. This is the lightest-weight escape hatch and appropriate for drafts that are genuinely distinct but share unavoidable domain vocabulary.

### Route E — CEO `--force-overlap` (rare, see next section)

Only used when Routes A-D are all inappropriate. See [The `--force-overlap` CEO override](#the---force-overlap-ceo-override).

## The `--force-overlap` CEO override

The `--force-overlap` flag bypasses the `near_duplicate` block, returning status `near_duplicate_forced` with exit code 0. **This is not a retry button.** It surfaces the block as a CEO committee decision point.

Rules for using `--force-overlap`:

- Only the CEO committee may authorize it, and the committee vote must be unanimous.
- The committee proposal must include the full JSON output from `similarity_scan.py` with all three top matches.
- The `suggested_action` from the scan must be explicitly rejected with written rationale.
- Every forced override logs a record to `skill-invocations.jsonl` with field `gate_17_force_overlap: true` and the approving committee session ID.
- Post-creation, the new skill is added to a biweekly confusability audit. If mean-pairwise Jaccard rises above the catalog health baseline, the CEO revisits.

The override exists because there are legitimate edge cases where two skills really do share most of their description but serve different users or different triggers. Example: `skill-improve` and `skill-deprecate` both act on existing skills, both bump version, both call `kb-update`, and their descriptions will inevitably share many tokens — yet they are semantically opposite operations. The committee is the right place to ratify that.

### When NOT to force

The override is a last resort. Every one of these situations is a hard NO — do not call the committee, do not propose a vote, do not use `--force-overlap`:

- **Do not force** when Route A (skill-improve) would solve the problem. If the draft is "the existing skill plus one more trigger phrase", that's a FIX, not a new skill.
- **Do not force** when Route B (skill-derive) would solve the problem. Specializations belong in lineage metadata, not in the base catalog.
- **Do not force** because "the reviewer is slow". Committee latency is not a reason to bypass review; it's a reason to escalate the latency problem separately.
- **Do not force** because "the description is almost right". Revise the description and re-run. The whole point of the warn/block band distinction is to give authors room to iterate before escalating.
- **Do not force** when the top match is a deprecated shim. The `suggested_action` already points to the replacement; re-run Gate 17 against the replacement or run `skill-improve` on the replacement directly.
- **Do not force** on drafts that Gate 9 (security scan) has not yet run. Security checks must land before any override decisions — a forced duplicate that later fails Gate 9 wastes committee time.
- **Do not force** because "this is temporary". There are no temporary skills in kiho. If the skill is expected to be retired in weeks, don't create it — use a throwaway `memory-observation` note instead.

The committee's job on a force request is to answer two questions: (1) are Routes A-D genuinely inapplicable? (2) does the new skill serve a meaningfully different set of users or triggers than the top match? If the answer to (1) is "no" or the answer to (2) is "no", the force request is rejected and the author takes Route A or Route C.

## Catalog health mode

`similarity_scan.py --catalog-health` scans the whole catalog and reports the mean-pairwise Jaccard across all skill descriptions. It does not compare against a draft.

```json
{
  "mode": "catalog-health",
  "catalog_root": "skills",
  "skill_count": 38,
  "mean_pairwise_jaccard": 0.015
}
```

This is informational. A rising mean-pairwise value is an early warning that the catalog is growing more confusable. The current (April 2026) baseline for the 37-skill kiho catalog is approximately 0.015 — very low, well below any confusability threshold.

v5.15 does not turn catalog health into a gate. If the mean-pairwise value climbs above 0.10 (a rough 6-7× the baseline), v5.16 may introduce a catalog-wide confusability budget. Until then, the metric is tracked only.

## Success metrics (post-rollout validation)

Gate 17 is a policy decision, not a finished implementation. Its thresholds need empirical validation after rollout, and the validation requires metrics. The metrics below are measured quarterly via the v5.16-planned `skill-invocations.jsonl` analyzer (out of scope for v5.15 but documented here so future work has a target).

| Metric | Target | Measurement | Failure mode |
|---|---|---|---|
| **False-positive rate** (blocks on genuinely novel drafts) | < 5% of blocks | Track each `near_duplicate` block; after 30 days, review whether the draft would have been better as a new skill or as an improvement. | If > 5%, raise `--block-threshold` to 0.65 and re-measure. Do NOT switch to embeddings. |
| **Block rate** (drafts blocked / total Gate 17 runs) | 5-25% of runs | `similarity_scan.py` exit code 1 / total runs, from `skill-invocations.jsonl` | If < 5%, the catalog is absorbing near-duplicates silently — check whether authors are running `skill-improve` instead of `skill-create` as a workaround. If > 25%, either the catalog is saturating or authors are sloppy — investigate before lowering the threshold. |
| **Force-override rate** (`--force-overlap` uses / total blocks) | < 10% of blocks | Count of `gate_17_force_overlap: true` records in `skill-invocations.jsonl` | If > 10%, the block threshold is too aggressive or the review routes (A-D) are too painful. Investigate Route ergonomics before relaxing the threshold. |
| **Warn-band drift** (drafts in 0.30-0.60) | < 15% of runs | Count `status: related_review` | If rising quarter-over-quarter, the catalog is growing more confusable and v5.16 should consider tightening the block threshold. |
| **Max pairwise Jaccard** (catalog health) | < 0.20 (= 2× current max) | `similarity_scan.py --catalog-health` + top-10 pair enumeration | If exceeds 0.20, a new skill snuck past review; audit. If exceeds 0.30, the warn band is at risk of filling up and the threshold calibration itself needs review. |
| **Gate 17 runtime** (wall-clock) | < 1 second at current catalog; < 3 seconds lifetime | Measure on CI, log to `skill-invocations.jsonl` | See [Scale upgrade path](#scale-upgrade-path) for the trigger. |
| **Top-10 most-similar-pair turnover** (quarterly) | ≥ 30% turnover per quarter | Diff the top-10 list quarter-over-quarter | Low turnover suggests the catalog is stagnant (fine). High turnover suggests aggressive evolution (also fine). Reversal turnover — the same pair dropping and re-entering the top-10 — suggests a skill is oscillating in version, which is a skill-improve problem, not a Gate 17 problem. |

None of these metrics are automated in v5.15. They are manually computed via ad-hoc scripts against `skill-invocations.jsonl`. Automation is a v5.16 item.

**Exit criterion for "Gate 17 is working."** After one full quarter of operation, all six green-band targets are met AND the mean-pairwise Jaccard has not risen by more than 50% from the Apr 2026 baseline (0.0146 → 0.022). If both conditions hold, Gate 17 graduates from advisory to blocking status in the v5.15.1 release. (It is already blocking at Jaccard ≥ 0.60; "graduation" here means the warn threshold becomes blocking as well, converting Route D into an automatic block.)

## Rejected alternatives

Every design choice in Gate 17 was selected against a specific set of rejected alternatives. Documenting them here so future readers can re-evaluate without re-deriving.

### A1 — LLM judge

**What it would look like:** spawn a sub-agent with both descriptions as input, ask it to classify as duplicate / specialization / unrelated. Use the verdict as the gate decision.

**Rejected because:**
- Non-deterministic across runs. The same draft evaluated twice can give different verdicts, which breaks CI reproducibility.
- Token cost. At ~2k tokens per judge call × ~40 skills to compare against = 80k tokens per Gate 17 run. v5.14's Gate 11 already uses a judge; doubling the judge budget for every new skill is too expensive.
- Explainability loss. A judge verdict says "these are similar" without showing *which tokens overlap*. Authors can't tell what to change.
- Latency. Judge calls take 10-30 seconds; Gate 17's shingle scan takes <200ms.

**Source:** Anthropic "Demystifying Evals for AI Agents" (Jan 2026) cautions against using judges for deterministic gates; reserve them for subjective evaluation where ground truth is unavailable. Gate 17 has a ground truth (Jaccard is computable).

### A2 — Embedding similarity with pre-built index

**What it would look like:** build a sentence-transformer (or similar) embedding of every skill's description. Store the vectors in a file. On every Gate 17 run, embed the draft and compute cosine similarity against all stored vectors. Block above threshold X.

**Rejected because:**
- Requires a daemon or rebuild step. kiho's "no pre-loaded embedding index" Non-Goal (CLAUDE.md §Non-Goals) rejects persistent model files at startup; Tier-3 on-demand embedding caches are permitted per-task but not a global catalog index.
- Non-deterministic across model versions. Sentence-transformers weights drift silently; the same skill scored with two model versions produces different similarity values. This breaks the "re-run on revision" workflow.
- Non-explainable. A cosine similarity of 0.89 does not tell the author *which words* drove the match.
- Dependency bloat. Sentence-transformers + PyTorch + tokenizers is >500MB of install. kiho wants to stay deployable as a plain Clone.

**Source:** K-Dense-AI/claude-skills-mcp uses sentence-transformers, but explicitly runs as an MCP daemon for this exact reason — kiho does not ship an MCP server (CLAUDE.md Non-Goal #2) and does not maintain a pre-loaded global embedding index (Non-Goal #3). kiho v5.15 research findings Q2 covers this. https://github.com/K-Dense-AI/claude-skills-mcp

### A3 — TF-IDF cosine similarity

**What it would look like:** compute a TF-IDF weighting across all catalog descriptions, then cosine-similarity the draft vector against every existing vector.

**Rejected because:**
- Worse on short text than Jaccard. TF-IDF shines when document lengths differ drastically and the IDF denominator has signal. kiho descriptions are all ~50-300 tokens — the IDF normalization washes out.
- Requires a global state (the IDF vocabulary) that drifts every time a new skill lands. A draft scored today against yesterday's IDF produces a different answer tomorrow.
- No better explainability than Jaccard. Shared tokens are still the interpretable output.
- More parameters to tune (smoothing, IDF cutoffs, sublinear weighting). Jaccard has exactly two parameters (block threshold, warn threshold).

**Source:** Nelhage fuzzy-dedup post recommends MinHash-over-Jaccard for short-document dedup at markdown scale; TF-IDF is discussed and dismissed as over-engineering. https://blog.nelhage.com/post/fuzzy-dedup/

### A4 — 3-shingles (pure trigram shingling)

**What it would look like:** instead of unigrams + bigrams, use 3-word shingles as the token set. Jaccard computed the same way.

**Rejected because:**
- Too sparse on short text. kiho descriptions are typically 50-300 tokens after stop-word removal. At 3-shingle granularity, two near-identical descriptions can end up with zero overlapping trigrams if the order changes even slightly.
- Empirical test: running 3-shingles against the Example 1 near-duplicate (Jaccard 0.73 with unigrams + bigrams) gives Jaccard 0.41 — *below* the block threshold and *above* the warn threshold, i.e., false negative for block. The test was run during v5.15 smoke testing.

**Source:** LSHBloom (arXiv 2411.04257) uses 3-shingles at internet scale (billions of documents); for markdown-scale (hundreds of documents with 50-300 tokens each), unigrams + bigrams is the documented-better choice. https://arxiv.org/html/2411.04257

### A5 — Retroactive catalog-wide confusability gate

**What it would look like:** every Gate 17 run also computes the mean-pairwise Jaccard including the new draft. Block if the new draft would push the mean-pairwise above a catalog-wide budget.

**Rejected (deferred) because:**
- Retroactively invalidates honest growth. A catalog that has been healthy for 12 months could trip the gate on a perfectly good skill because an earlier unrelated-but-similar pair was already near the budget.
- Requires an empirical budget calibration that the Apr 2026 catalog cannot provide (mean-pairwise is 0.0146; any budget would be speculative).
- The top-10 pair turnover metric in [Success metrics](#success-metrics-post-rollout-validation) is a gentler alternative that tracks catalog health without gating individual drafts.

**Deferred to v5.16** if the mean-pairwise climbs above 0.10 in production. Until then, [Catalog health mode](#catalog-health-mode) tracks it informationally.

### A6 — Static AST-based behavioral-scope extraction

**What it would look like:** parse the SKILL.md body to extract semantic operations, compare operations across skills instead of comparing descriptions.

**Rejected outright because:**

> **arXiv 2604.02837 §4:** *"Because no static analysis tool can fully characterize the behavioral scope of natural language instructions, the gap between declared and actual behavior is not detectable at authorship time."*

Three independent papers (arXiv 2604.02837, 2602.12430, 2604.03070) concur: AST/semantic extraction from natural-language skill bodies is an unsolved problem, and in the 2024-2026 literature it is explicitly recommended *against* trying. Regex for wiki-link mentions is fine (it's syntactic, not semantic) — see `bin/kiho_rdeps.py` for kiho's use of that narrow pattern. Full semantic extraction is not.

**Source:** kiho v5.15 research findings Q9, the same paper cluster that drove kiho's Gate 9 security posture.

## Scale upgrade path

**Trigger conditions (any one triggers the upgrade):**

| Signal | Threshold | Where measured |
|---|---|---|
| Gate 17 wall-clock runtime | **> 3 seconds** on a single `similarity_scan.py` invocation | `/usr/bin/time` wrapper on CI; log to `skill-invocations.jsonl` |
| Catalog size | **> 150 skills** | `find skills -name SKILL.md \| wc -l` |
| Pairs evaluated | **> 11,000 pairs** (= n·(n−1)/2 at n=150) | `similarity_scan.py --catalog-health` output |

The current Apr 2026 state: 39 skills, 741 pairs, ~180ms runtime. The upgrade trigger is ~4× the current catalog size, so kiho has significant headroom. When any trigger condition fires, ship the MinHash+LSH upgrade in the next point release.

**Upgrade recipe (pre-written so future authors don't re-derive):**

1. **Sign every catalog entry once.** Compute a 64-permutation MinHash signature from its shingle set. Use `hashlib.sha1` with salted seeds `"kiho-v5.XX|0"`..`"kiho-v5.XX|63"` — no PyPI dependencies. Store signatures in memory per-invocation (do NOT persist to disk; H5 reverse-index rule applies).

2. **Bucket signatures via LSH banding.** Use 16 bands × 4 rows per band. Any two signatures that hash into the same bucket in at least one band are *candidate matches*. This reduces the comparison set from O(n²) to O(n) in the common case.

3. **For each draft, retrieve candidates.** Compute the draft's MinHash signature once. Query the LSH bands to get the candidate set (typically 5-20 skills at n=150).

4. **Compute exact Jaccard on candidates only.** Use the same `jaccard(a, b)` function as today. The shingles() function is reused unchanged; only the *outer loop* changes from O(n²) to O(candidates).

5. **Keep the thresholds and decision tree unchanged.** MinHash Jaccard is an *estimate* of true Jaccard with ~5% error at 64 permutations. The 0.60 block threshold and 0.30 warn threshold are robust to this error (the warn band is 30 percentage points wide). If false-positive rate climbs, raise the block threshold to 0.65 rather than increasing permutation count.

6. **Add a `--exact-fallback` flag** that ignores MinHash and does full O(n²) pairwise Jaccard on demand. Useful for catalog-health mode and for post-rollout verification.

Implementation estimate: ~80 lines of Python added to `similarity_scan.py`. No new scripts. Zero PyPI dependencies. Deterministic across runs (seeded hashes).

### Do NOT on the upgrade

- **Do not** switch to embeddings. See [Rejected alternatives A2](#a2--embedding-similarity-with-pre-built-index).
- **Do not** persist the MinHash index to disk. H5 (forward-edge-only, compute-reverse-on-demand) applies to similarity as well as to reverse deps — a stale MinHash index is worse than a slow fresh scan.
- **Do not** relax the thresholds just because MinHash is approximate. The 30-point warn band is already wide enough to absorb the ~5% MinHash error.
- **Do not** introduce a separate "fast mode" that bypasses the scan for trusted authors. Every skill author goes through the same gate; there is no trust hierarchy at the similarity layer.

## Grounding

**Primary research sources (cited in this file):**
- arXiv 2601.04748 §5.2, §5.3 — phase transition at |S| ≈ 30; semantic confusability vs size
- arXiv 2603.02176 (AgentSkillOS) §2.1.1 — hierarchical routing mitigates but does not remove confusability; merge rule for *categories* with single child
- arXiv 2411.04257 (LSHBloom) — MinHash dedup at internet scale; 0.60 threshold for short-text
- arXiv 2604.02837 §4 — no static analysis can characterize behavioral scope of natural language instructions (grounds [Rejected alternative A6](#a6--static-ast-based-behavioral-scope-extraction))
- Nelhage "fuzzy dedup" — https://blog.nelhage.com/post/fuzzy-dedup/ — shingle + Jaccard explainer and threshold rationale
- Anthropic "Demystifying Evals for AI Agents" (Jan 2026) — grounds [Rejected alternative A1](#a1--llm-judge) (deterministic gates should not call judges)
- Anthropic `skills/skill-creator` (upstream reference) — has **no** pre-create similarity check; v5.15 is greenfield territory, not paving a cowpath
- K-Dense-AI/claude-skills-mcp — https://github.com/K-Dense-AI/claude-skills-mcp — embedding-based skill discovery runs as MCP daemon, not inside markdown (grounds [Rejected alternative A2](#a2--embedding-similarity-with-pre-built-index))

**Related kiho components:**
- `skills/_meta/skill-create/scripts/similarity_scan.py` — the Gate 17 implementation
- `skills/_meta/skill-create/scripts/catalog_fit.py` — sibling Gate 14 (domain-fit check, not similarity)
- `bin/kiho_rdeps.py` — on-demand reverse-dependency scanner. Related to Gate 17 the way *consumer impact* relates to *novel contribution*: Gate 17 asks "should this skill exist at all?", `kiho_rdeps` asks "who would be affected if it changed?". Both are forward-edge-only, compute-on-demand, no-persistent-reverse-index. See also `kiho-plugin/references/skill-authoring-patterns.md` for the shared design stance.
- `skills/_meta/skill-improve/SKILL.md` — the primary Route A target (called with the blocked draft as diff proposal)
- `skills/_meta/skill-derive/SKILL.md` — the Route B target for legitimate specializations
- `skills/_meta/skill-deprecate/SKILL.md` — handles the "what if the top match is itself deprecated" case; the shim's description is preserved in its frontmatter so Gate 17 still matches against the slug

**Full research report:** `kiho-plugin/references/v5.15-research-findings.md` — H1-H5 headline findings, 10 Q&A, 36 primary-source URLs.
