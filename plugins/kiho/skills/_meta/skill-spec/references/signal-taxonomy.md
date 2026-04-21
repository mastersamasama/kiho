# skill-architect signal taxonomy (v5.18)

The closed set of intent → structural-choice signals consumed by `extract_signals.py` and `propose_spec.py`. Hand-curated initial vocabulary; CEO-committee vote to extend.

> Key words **MUST**, **MUST NOT**, **SHOULD**, **MAY** per BCP 14 (RFC 2119, RFC 8174).

## Non-Goals

- **Not extensible by ad-hoc author edit.** Every taxonomy change goes through CEO-committee vote with telemetry justification (override rate threshold).
- **Not embedding-based.** Hand-curated keyword matching; embeddings explicitly rejected per CLAUDE.md §"Not an embedding-based retrieval system".
- **Not a complete NLU.** Catches typical kiho intent shapes; edge cases escalate to LLM critic (Step D) and ultimately user confirmation (Step E).
- **Not domain-agnostic.** Vocabulary tuned to kiho's specific domain space (skill authoring, agent orchestration, KB management). External domains require separate taxonomy.

## Signal categories (5)

### 1. Capability verb signals → `metadata.kiho.capability`

Each closed-set verb has a list of natural-language signal words. Match count × 0.3 (capped 1.0) gives capability score.

| Verb | Signal words | Notes |
|---|---|---|
| `create` | produce, generate, draft, build, instantiate, initialize, author, compose, scaffold, bootstrap, make | new artifact production |
| `read` | find, get, list, show, inspect, query, lookup, fetch, search, retrieve, view, display | no mutation |
| `update` | modify, edit, sync, synchronize, refresh, recompute, mutate, patch, transform, update, adjust, change | mutates existing state |
| `delete` | remove, deprecate, archive, retire, prune, delete, expire, cleanup, purge | removes state |
| `evaluate` | validate, audit, score, check, verify, assess, lint, evaluate, grade, review, inspect | judges quality / correctness |
| `orchestrate` | coordinate, chain, dispatch, route, manage, orchestrate, batch, pipeline, flow, sequence | combines multiple operations |
| `communicate` | notify, escalate, present, report, surface, communicate, broadcast, publish, alert | external-facing output |
| `decide` | vote, decide, judge, deliberate, arbitrate, choose, rule, determine | committee-style decision |

**Resolution rule**: capability with highest score wins. Ties broken by user override at Step E. If max score < 0.30, flag as `user_input_needed`.

### 2. Scripts-needed signals → `scripts_required` non-empty

| Signal class | Examples | Weight |
|---|---|---|
| arithmetic verb | compute, recompute, calculate, sum, aggregate, score, count, average | +0.25 |
| data-shape verb | parse, transform, filter, sort, dedupe, validate, normalize | +0.20 |
| scale word | hundreds, thousands, JSONL, batch, bulk, all entries, full catalog | +0.30 |
| determinism marker | reproducible, deterministic, audit, idempotent, atomic, hash | +0.25 |
| file-format mention | .jsonl, .json, .yaml, .md (multiple), .csv, .toml | +0.20 |
| side-effect verb | write, append, "update file", "atomic write", emit | +0.15 |

**Resolution rule**: total ≥ 0.50 → `scripts_recommended: true`. Confidence = min(1.0, total / 0.85).

**Edge case — config-only skills.** Some skills (kiho itself) carry `config.toml` (TOML-migrated in v5.19.3; previously `config.yaml`) instead of scripts. If intent mentions "config", "settings", "configuration" + no arithmetic verbs → propose `scripts_required: []` + `has_config_yaml: true` (the parity-diff field keeps the legacy key name and accepts either `config.toml` or `config.yaml`). This is the `meta-with-scripts` layout's config-only variant.

### 3. References-needed signals → `references_required` non-empty

| Signal class | Examples | Weight |
|---|---|---|
| multi-step marker | "first ... then ... finally", "step 1", "phase", numbered procedure | +0.30 |
| narrative-explanation marker | rationale, why, trade-offs, principles, philosophy, design-decision | +0.25 |
| reference-data marker | tables, formulas, schemas, vocabularies, taxonomies, rubrics, templates | +0.30 |
| body-length signal | "detailed procedure", "comprehensive guide", "full spec", "deep dive" | +0.15 |
| domain-knowledge marker | "see X for full spec", "per RFC", "per ISO", "per Anthropic", "per arXiv" | +0.20 |

**Resolution rule**: total ≥ 0.50 → `references_recommended: true`.

**Reference filename derivation**: from intent, extract reference-data nouns (rubric, schema, template, taxonomy, ...). Each becomes a `references/<noun>.md`. If user mentions multiple data classes, propose multiple references.

### 4. Parity-layout proposal (joint of scripts + references)

| scripts_recommended | references_recommended | Proposed `parity_layout` |
|---|---|---|
| false | false | `standard` |
| true | false | `meta-with-scripts` |
| false | true | `meta-with-refs` |
| true | true | `meta-with-both` |
| (all signal scores < 0.30) | | `parity-exception` (escalate; user explains structural novelty) |

**Confidence**: average of scripts + references confidences.

### 5. Topic-tag signals → `metadata.kiho.topic_tags`

The 18-tag controlled vocabulary lives in `references/topic-vocabulary.md`. For each tag, signal words derive from the tag's own definition and aliases.

| Tag | Signal words (illustrative; full list in vocab file) |
|---|---|
| `authoring` | create, author, draft, generate, factory |
| `lifecycle` | deprecate, retire, archive, lifecycle, version |
| `validation` | validate, check, audit, lint, verify |
| `discovery` | find, search, retrieve, lookup, query |
| `orchestration` | orchestrate, chain, batch, pipeline, dispatch |
| `state-management` | sync, registry, matrix, recompute, state, store |
| `observability` | inspect, telemetry, observe, monitor, trace |
| `hiring` | recruit, hire, candidate, interview, agent design |
| `persona` | soul, persona, drift, override, personality |
| `knowledge` | research, doc, crawl, knowledge, kb, wiki |
| `deliberation` | committee, vote, debate, deliberate, decide |
| `experience` | learn, capture, extract, lesson, observation |
| `bootstrap` | setup, init, initialize, bootstrap, install |
| `retention` | promote, archive, retain, expire, prune |
| `meta-operations` | meta, factory, harness, orchestrator |
| `committee voting` | vote, ballot, majority, unanimous |
| `interview simulation` | interview, simulate, candidate test |
| `experience pool` | pool, share, federated, cross-project |

**Resolution rule**: top 2 by score (if both > 0.4) → propose 2 tags. If only 1 above threshold → propose 1. If 0 → flag `user_input_needed`.

**MUST NOT** propose tags outside the controlled vocabulary. Architect cannot expand vocabulary; only CEO-committee can.

### 6. Parent-domain signals → `parent_domain`

Each domain has keyword markers; matching count determines proposed domain.

| Domain | Keyword markers |
|---|---|
| `_meta` | skill, factory, validator, audit, generator, lifecycle |
| `core/harness` | kiho, orchestrate, runtime, config, sync, registry |
| `core/hr` | hire, recruit, agent design, interview, candidate |
| `core/inspection` | inspect, debug, view state, trace, dump |
| `core/knowledge` | research, doc, crawl, knowledge, deepwiki |
| `core/planning` | plan, committee, deliberate, simulate, vote |
| `kb` | knowledge base, wiki, lint, promote, ingest, page |
| `memory` | observation, reflection, lesson, drift, todo, journal |
| `engineering` | spec, requirement, design, task, EARS, kiro |

**Resolution rule**: domain with highest match count wins. If multiple domains tie or all score < 1, escalate to user.

### 7. Name-derivation rule → `name`

Heuristic: extract the verb-phrase from intent, kebab-case it, drop common stopwords.

Examples:
- "synchronize org registry after workforce changes" → `org-sync` (verb=synchronize, primary noun=org)
- "audit catalog for stale lifecycle entries" → `lifecycle-audit` (verb=audit, primary modifier=lifecycle)
- "convert raw documents into KB pages" → `kb-ingest-raw` (existing skill matched; collision)

**MUST** check name collision via skill-spec's existing collision check; if collision, propose alternates by appending suffix or using a synonym verb.

## Signal extraction process (consumed by `extract_signals.py`)

```python
# Pseudocode
def extract_signals(intent_text):
    tokens = tokenize_lowercase(intent_text)
    
    capability_scores = {}
    for verb, signal_words in CAPABILITY_VERBS.items():
        capability_scores[verb] = min(1.0, count_matches(tokens, signal_words) * 0.3)
    
    scripts_score = sum(weight * has_match(tokens, words) 
                        for cls, (words, weight) in SCRIPTS_SIGNALS.items())
    references_score = sum(weight * has_match(tokens, words) 
                           for cls, (words, weight) in REFERENCES_SIGNALS.items())
    
    topic_scores = {tag: count_matches(tokens, words) * 0.4 
                    for tag, words in TOPIC_TAGS.items()}
    
    domain_match = max(DOMAIN_KEYWORDS, key=lambda d: count_matches(tokens, DOMAIN_KEYWORDS[d]))
    
    return {
        "capability_scores": capability_scores,
        "scripts_recommended": scripts_score >= 0.50,
        "scripts_score": scripts_score,
        "scripts_evidence": [w for w in matched_words(scripts_signals)],
        "references_recommended": references_score >= 0.50,
        "references_score": references_score,
        "references_evidence": [...],
        "topic_scores": topic_scores,
        "domain_match": domain_match,
        "domain_evidence": [...],
        "tokens": tokens,
    }
```

## Decision tree (consumed by `propose_spec.py`)

```python
def propose_spec(signals, intent_text):
    capability = max(signals["capability_scores"], key=signals["capability_scores"].get)
    
    if signals["scripts_recommended"] and signals["references_recommended"]:
        layout = "meta-with-both"
    elif signals["scripts_recommended"]:
        layout = "meta-with-scripts"
    elif signals["references_recommended"]:
        layout = "meta-with-refs"
    else:
        layout = "standard"
    
    # Per-domain layout overrides (from canonical-layouts.md)
    domain_default = lookup_domain_default(signals["domain_match"])
    if domain_default and layout != domain_default:
        # Soft conflict — flag for critic
        layout_confidence = 0.6
    else:
        layout_confidence = avg(scripts_confidence, references_confidence)
    
    # Topic tags: top 2 above threshold
    sorted_tags = sorted(signals["topic_scores"].items(), key=lambda x: -x[1])
    proposed_tags = [t for t, s in sorted_tags[:2] if s > 0.4]
    
    # Name derivation
    name = derive_name(intent_text, signals)
    
    return {
        "name": name,
        "parent_domain": signals["domain_match"],
        "capability": capability,
        "topic_tags": proposed_tags,
        "description_seed": intent_text[:1024],
        "scripts_required": derive_script_names(signals) if signals["scripts_recommended"] else [],
        "references_required": derive_reference_names(signals) if signals["references_recommended"] else [],
        "parity_layout": layout,
        "rationales": {
            "capability": f"verb match — top score {signals['capability_scores'][capability]:.2f}",
            "scripts_required": f"signals: {signals['scripts_evidence'][:3]} → score {signals['scripts_score']:.2f}",
            ...
        },
        "confidence": layout_confidence,
    }
```

## Telemetry feedback loop

Every user override at Step E logs to `_meta-runtime/architect-overrides.jsonl`:

```json
{"timestamp": "2026-04-16T12:00:00Z", "intent_hash": "abc123", "field": "scripts_required",
 "proposed": [], "overridden_to": ["recompute.py"], "rationale": "user said arithmetic over JSONL"}
```

If a signal's recommendations are overridden in > 30% of cases over 20 invocations, the signal weight is flagged for CEO-committee review (down-weight or replace).

This is **not automatic** — telemetry surfaces the issue; humans decide the weight change.

## Edge cases (escalation paths)

| Edge case | Detector | Action |
|---|---|---|
| All signals score < 0.30 | Step A | Flag `user_input_needed` for entire spec |
| Capability tie (top 2 within 0.05) | Step A | Flag `capability` field; propose top 2 |
| 0 topic tags above threshold 0.4 | Step A | Flag `topic_tags`; surface top 3 candidates |
| Layout conflicts with domain_default | Step B | Confidence drops to 0.6; Step D LLM critic fires |
| Sibling-divergence > 30% | Step C | Step D LLM critic fires |
| User overrides ≥ 5 fields | Step E | Re-prompt: "Restart from Step 0 with refined intent?" |

## Source references

- v5.18 plan §"Signal taxonomy"
- DSPy MIPROv2 grounded-instruction-proposal pattern (signal weighting analog) — https://dspy.ai/learn/optimization/optimizers/
- Anthropic skill-creator's iterative description rewriter (signal evidence pattern) — https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- Backstage Software Templates `parameters:` JSONSchema with field-level rationale — https://backstage.io/docs/features/software-templates/writing-templates
