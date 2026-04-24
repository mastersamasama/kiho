# Data storage matrix — per-class authoritative spec

- Version: 1.0 (2026-04-18; v5.19 Phase 2)
- Status: canonical — every skill `metadata.kiho.data_classes:` frontmatter entry MUST cite a row here
- Companion: `references/storage-architecture.md` (three-tier invariants) + `references/storage-tech-stack.md` (per-category tech decisions) + `_meta-runtime/phase1-committee-minutes.md` (vote log)

> Key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** per BCP 14 (RFC 2119 and RFC 8174).

## Non-Goals

- **Not a re-statement of `storage-architecture.md`.** Tier invariants (T1/T2/T3 MUSTs) remain authoritative. This file assigns specific data classes to specific tiers with specific technologies.
- **Not a committee-rules rewrite.** Changes to matrix rows follow the same CEO-committee process as additions to capability-taxonomy.md or topic-vocabulary.md.
- **Not a migration schedule.** Lazy migration via `skill-improve` on touch. Existing skills that don't yet declare `data_classes:` are grandfathered for 180 days (warn 60d, error 180d).
- **Not complete.** Gaps (GAP rows) are documented honestly. Adding a new data class requires a matrix PR + committee vote.

## Row schema

Each row uses compact YAML-like blocks. Omitted fields are N/A for that class.

```
### <class-slug>
tier:           T1 | T2 | T3
scope:          company | project | both | plugin-global
format:         <tech from storage-tech-stack.md §N>
path:           <glob patterns; use <project> and $COMPANY_ROOT placeholders>
gatekeeper:     kb-manager | org_sync | CEO-direct | <named-script> | skill-author
read:           grep | keyed | structured | FTS | similarity | rendered-view
write:          per-commit | per-session | per-iteration | per-invocation | per-finding
shape:          free-prose | frontmatter+prose | uniform-typed | mixed
cardinality:    small (<50) | medium (50–10k) | large (10k+)
eviction:       (T3 only) TTL | session-scope | importance-decay
regeneration:   (T2/T3) <concrete command or function>
review:         committee | occasional | machine-only
tech-stack:     <§ reference to storage-tech-stack.md>
notes:          (short)
```

**Status tag** at row top: `FIT` (no change needed), `MIGRATING` (lazy migration underway), `NEW` (v5.19 addition), `GAP` (referenced but unimplemented — do not cite yet), `DEFERRED` (explicit no-decision with revisit triggers).

---

## 1. Canonical doctrine

Narrative prose, committee-reviewable. Markdown wins by design. All these stay T1.

### agent-souls — FIT
```
tier:           T1
scope:          both
format:         markdown + YAML frontmatter
path:           agents/*.md  |  <project>/.kiho/agents/<id>/agent.md  |  $COMPANY_ROOT/agents/<id>/agent.md
gatekeeper:     CEO (soul-apply-override)
read:           grep + one-shot agent load
write:          per-committee-decision
shape:          frontmatter+prose (12 soul sections)
cardinality:    small
review:         committee
tech-stack:     n/a (markdown is canonical for this shape)
```

### skill-definitions — FIT
```
tier:           T1
scope:          plugin-global
format:         markdown + YAML frontmatter
path:           skills/**/SKILL.md
gatekeeper:     skill-author + evolution-scan
read:           grep + facet-walk (Tier-3 FTS index per storage-tech-stack §8)
write:          per-commit / per-skill-improve
shape:          frontmatter+prose
cardinality:    medium (44 today, 200+ long-term)
review:         committee (DRAFT→ACTIVE promotion)
tech-stack:     n/a; derived index in §8 below
```

### references-doctrine — FIT
```
tier:           T1
scope:          plugin-global
format:         markdown
path:           references/*.md  |  skills/**/references/*.md
gatekeeper:     author + pattern-audit (≥6/9)
read:           grep + one-shot agent load
write:          per-commit
shape:          free-prose (doctrine)
cardinality:    small
review:         committee
```

### templates — FIT
```
tier:           T1
scope:          plugin-global
format:         markdown + YAML frontmatter
path:           templates/*.md  |  skills/**/templates/*.md
gatekeeper:     author
read:           grep
write:          per-commit
cardinality:    small
review:         committee
```

### catalog-routing-block — FIT
```
tier:           T1 (file) + T2 (routing-block YAML fenced within)
scope:          plugin-global
format:         markdown + fenced-YAML routing block
path:           skills/CATALOG.md  |  skills/*/CATALOG.md
gatekeeper:     bin/catalog_gen.py + bin/routing_gen.py (committee-approved generators)
read:           grep + parsed routing block
write:          per-commit (prose sections) | regenerated (routing block)
shape:          mixed
cardinality:    small (domain index)
regeneration:   `python bin/catalog_gen.py && python bin/routing_gen.py`
review:         committee
notes:          proof of concept that mixed T1+T2 works cleanly
```

### claude-md — FIT
```
tier:           T1
scope:          plugin-global
format:         markdown
path:           CLAUDE.md
read:           one-shot main-agent load
write:          per-commit
shape:          free-prose
review:         committee
```

### changelog — FIT
```
tier:           T1
scope:          plugin-global
format:         markdown
path:           CHANGELOG.md
write:          per-version-milestone
review:         occasional
```

### kb-wiki-articles — FIT
```
tier:           T1
scope:          both
format:         markdown + YAML frontmatter (Karpathy protocol)
path:           <project>/.kiho/kb/wiki/**/*.md  |  $COMPANY_ROOT/company/wiki/**/*.md
gatekeeper:     kb-manager (sole writer)
read:           grep + wikilink traversal + 12 rendered views
write:          per-finding (drafts → lint → atomic-move)
shape:          frontmatter+prose
cardinality:    medium per project; large across company
review:         committee
regeneration:   index views (backlinks/tags/graph/etc.) regenerated by kb-manager
notes:          see `references/karpathy-wiki-protocol.md`
```

---

## 2. Typed config — TOML migration

Per storage-tech-stack §1: TOML wins. Migrations lazy on touch.

### kiho-config — FIT
```
tier:           T2
scope:          plugin-global
format:         TOML
path:           skills/core/harness/kiho/config.toml
gatekeeper:     committee (schema); kiho-setup (initial population)
read:           keyed via tomllib (Python 3.11+ stdlib) or `tomli` fallback on 3.10
write:          per-commit (hand-edit) + per-setup
shape:          uniform-typed
cardinality:    small
regeneration:   n/a (authored)
review:         committee
tech-stack:     §1
notes:          Migrated from config.yaml 2026-04-19 (v5.19.3 Tier-C) via `bin/yaml_to_toml.py`.
                Comment placement hand-touched after automated conversion (TOML requires
                top-level scalars before any [table] header, which rearranges section
                comments). Phase 4 pilot MAY add a [paths.tier3] stanza here for the
                sqlite path.
```

### canonical-rubric — FIT (v5.19.5+)
```
tier:           T2
scope:          plugin-global
format:         TOML (migrated v5.19.5 from YAML)
path:           skills/core/planning/interview-simulate/assets/canonical-rubric.toml
legacy-path:    skills/core/planning/interview-simulate/assets/canonical-rubric.yaml
                (retained one cycle as safety net; delete in v5.19.6)
gatekeeper:     committee-approved asset
read:           keyed
write:          per-committee-revision
shape:          uniform-typed (multi-level nesting: dimensions.<name>.scale, weight_presets.<preset>)
cardinality:    small
review:         committee
tech-stack:     §1
migration-note: hand-rewritten (bin/yaml_to_toml.py narrow schema does not
                support multi-level nesting); semantic round-trip verified via
                tomli.loads == yaml.safe_load on the v5.19.4 YAML file.
```

### recruit-role-specs — MIGRATING
```
tier:           T2 (structured fields) / T1 (prose rationale) hybrid
scope:          project
format:         TOML OR markdown + TOML frontmatter (author discretion per §1)
path:           <project>/.kiho/state/recruit/<slug>/role-spec.{toml,md}
gatekeeper:     recruit skill
read:           keyed
write:          per-recruit-launch
shape:          uniform-typed (+ optional narrative body)
cardinality:    small
review:         committee (hire decision)
tech-stack:     §1 (author picks TOML if prose <30%, markdown+TOML-frontmatter otherwise)
```

### soul-overrides — FIT
```
tier:           T1
scope:          both
format:         markdown + YAML frontmatter (today) — MAY migrate to markdown + TOML frontmatter per §1
path:           <project>/.kiho/agents/<id>/memory/soul-overrides.md
                $COMPANY_ROOT/agents/<id>/memory/soul-overrides.md
gatekeeper:     CEO + memory-reflect
read:           one-shot on soul-apply-override
write:          per-drift-event
shape:          frontmatter+prose (rationale is narrative)
cardinality:    small
review:         committee
tech-stack:     §1 for frontmatter-encoding pick
```

### values-flags — NEW (v5.21+)
```
tier:           T1
scope:          project
format:         markdown ruling signed by CEO (one file per flag)
path:           <project>/.kiho/state/values-flags/<flag_id>.md
gatekeeper:     values-flag (writer) / committee (advisory) / CEO (signs ruling)
read:           one-shot on flag resolution; aggregated quarterly by values-alignment-audit
write:          per-conflict-event (red-line clash, soul/values mismatch)
shape:          frontmatter + prose ruling (rationale is narrative)
cardinality:    small (rare; one per genuine value conflict)
eviction:       never (audit trail; aggregate by values-alignment-audit)
review:         committee (advisory) + CEO (sign)
tech-stack:     §1 (markdown reviewable kind; storage-broker enforces)
notes:          soul-mutating rulings trigger soul-apply-override with non-bypassable
                user-accept gate. values-alignment-audit aggregates files quarterly.
```

---

## 3. Live registry

Per storage-tech-stack §3: Markdown T1 canonical + in-memory dict T3 session-scope. **No sqlite here.**

### capability-matrix — NEW-PATTERN
```
tier:           T1 canonical + T3 in-memory dict (session-scope)
scope:          project
format:         markdown table (rendered view) — canonical; Python dict at T3 (session)
path:           <project>/.kiho/state/capability-matrix.md
gatekeeper:     bin/org_sync.py (committee-approved generator)
read:           grep (.md) OR dict lookup (T3 if built for the turn)
write:          per-session by org_sync from JSONL telemetry
shape:          uniform-typed (agent × domain → proficiency 1–5) + narrative change log
cardinality:    small (14 × 8 today; linear growth)
eviction:       (T3 dict) session-scope, discarded at turn end
regeneration:   `build_from_md()` OR `replay_from_jsonl(skill-invocations.jsonl, agent-performance.jsonl)`
review:         occasional
tech-stack:     §3
notes:          Phase 1 committee rejected sqlite for this class; capability-matrix is NOT a Phase 4 pilot
```

### org-registry — FIT
```
tier:           T1 canonical + T3 in-memory dict (session-scope) — same pattern
scope:          project
format:         markdown table + change-log narrative
path:           <project>/.kiho/state/org-registry.md
gatekeeper:     bin/org_sync.py
read:           grep (.md) OR dict lookup (T3)
write:          per-committee-change
shape:          mixed (structured table + narrative log)
cardinality:    small
review:         committee
tech-stack:     §3
```

### management-journals — FIT
```
tier:           T1
scope:          both
format:         markdown + YAML frontmatter
path:           <project>/.kiho/state/management-journals/<leader-id>.md
                $COMPANY_ROOT/agents/<name>/management-journal.md
gatekeeper:     department lead (append)
read:           grep
write:          per-delegation-decision
shape:          frontmatter+prose (narrative-dominant; structured sections inside)
cardinality:    small per leader
review:         committee
```

### integrations-registry — NEW (v5.21+)
```
tier:           T1
scope:          both
format:         markdown + YAML frontmatter; one file per integration (multi-file
                directory model — chosen over single-table for per-entry trust review,
                grep-friendly per-integration audit, and clean append/dedup semantics)
path:           <project>/.kiho/state/integrations/registry/<integration_id>.md
                $COMPANY_ROOT/integrations/registry/<integration_id>.md (company-tier)
partner:        <project>/.kiho/state/integrations/debt.jsonl (T2 JSONL; one row per
                registered-but-never-called integration; cleared by integration-audit
                on first telemetry hit; not a separate matrix row — same data class,
                stored alongside as the unused-flag side-channel)
gatekeeper:     integration-register (writer; storage-broker forces Tier-1 md via
                reviewable-kind enforcement) / integration-audit (reader; flags drift)
read:           grep on session start; CEO INITIALIZE may auto-load summary
write:          per-integration-discovery (MCP server detected, native tool added);
                immutable post-write (no in-place mutation; deprecate via committee)
shape:          frontmatter (id, type, owner_agent, trust_level, auth_mode,
                failure_mode, registered_at, tools[]) + prose body (purpose, trust
                rationale, auth, failure mode, notes)
cardinality:    small per project (≤30 typically; long-tail OK in dir model)
eviction:       integration-audit flags drift; CEO deprecates manually via committee
                (no auto-evict; debt.jsonl entries clear lazily as use is detected)
review:         per-entry committee review at first registration (trust_level gate);
                occasional bulk audit at CEO session start
tech-stack:     §3 (one md per entry, not the §3 markdown-table form used for
                org-registry / capability-matrix)
notes:          Tracks MCP servers, native tools, CLI integrations. integration-audit
                emits memos to CEO for stale entries; CEO decides what to deprecate.
                See `templates/integration-entry.template.md` for the per-entry skeleton.
```

---

## 4. Telemetry — JSONL canonical

Per storage-tech-stack §2: Keep all 5 streams as JSONL. DuckDB optional overlay on read.

### skill-invocations — FIT
```
tier:           T2
scope:          project
format:         JSONL (stdlib json)
path:           <project>/.kiho/state/skill-invocations.jsonl
gatekeeper:     CEO-direct (append via session context)
read:           aggregate (Python loop today; DuckDB overlay when installed)
write:          per-invocation (append-only)
shape:          uniform-typed
cardinality:    large (unbounded; prune/archive by age if >1M rows)
regeneration:   n/a (primary observation; not regenerable; protected by append-only)
review:         machine-only
tech-stack:     §2
```

### agent-performance — FIT
(identical pattern; path: `<project>/.kiho/state/agent-performance.jsonl`; write: per-task)

### ceo-ledger — FIT
(identical pattern; path: `<project>/.kiho/state/ceo-ledger.jsonl`; write: per-Ralph-phase; read: last-20 by CEO INITIALIZE)

### gate-observations — FIT
(identical pattern; path: `<project>/.kiho/state/gate-observations.jsonl`; write: per-gate-trigger)

### cross-agent-learnings — FIT (project tier)
```
tier:           T2
scope:          project (company rollup via §10 matrix row)
format:         JSONL
path:           <project>/.kiho/state/cross-agent-learnings.jsonl
gatekeeper:     CEO + memory-cross-agent-learn
read:           structured (filter by target_agent)
write:          per-lesson-published
shape:          uniform-typed
cardinality:    medium
review:         machine-only
tech-stack:     §2 (write path) + §9 (promotion to company tier)
```

### skill-factory-verdicts — NEW (v5.20+)
```
tier:           T2
scope:          plugin-global
format:         JSONL (one row per skill per factory invocation)
path:           _meta-runtime/factory-verdicts.jsonl
gatekeeper:     bin/skill_factory.py (sole writer; CEO consumes via render_batch_report.py)
read:           aggregate (jq, Python loop, optional DuckDB overlay)
write:          per-invocation (append-only; one row per skill in batch)
shape:          uniform-typed
                fields: ts, batch_id, skill_id, skill_path, verdict (green|yellow|red),
                step_results: {step: status},
                fail_reason?, ceo_decision?, phase
cardinality:    large (unbounded; prune by age >180d)
regeneration:   primary observation (factory verdicts are not regenerable; protected by append-only)
review:         machine-only; CEO renders human view via bin/render_batch_report.py --batch-id <id>
tech-stack:     §2 (JSONL canonical telemetry stream)
notes:          Replaces the v5.17–v5.19 batch-report-<id>.md as source of truth.
                Markdown batch-report retained as a *rendered view* (see bin/render_batch_report.py).
                Enables CEO trend queries like
                `jq '[.[] | select(.verdict=="red")] | group_by(.step_results."step3") | map({step3: .[0].step_results."step3", count: length})' factory-verdicts.jsonl`.
```

### skill-critic-verdicts — NEW (v5.20+)
```
tier:           T2
scope:          plugin-global
format:         JSONL (one row per critic invocation)
path:           _meta-runtime/critic-verdicts.jsonl
gatekeeper:     skills/_meta/skill-critic/scripts/critic_score.py (sole writer)
read:           aggregate (jq, Python loop)
write:          per-invocation (append-only)
shape:          uniform-typed
                fields: ts, skill_id, skill_path, overall_score, threshold, pass,
                hard_fail, axes: {axis_name: {score, weight, detail}}, warnings,
                invocation_source ("factory-step5"|"manual"|"evolve-trigger")
cardinality:    large (unbounded; prune by age >180d)
regeneration:   primary observation
review:         machine-only; supports evolution-scan --audit=critic-drift lens
tech-stack:     §2
notes:          Replaces individual _meta-runtime/critic-requests/*.json files (those become
                debug-only; the aggregate JSONL is the source of truth).
                Drives Wave 1.2 evolve-trigger-from-critic loop and Wave 1.3 telemetry rollup.
```

### evolution-scan-audits — NEW (v5.20+)
```
tier:           T2
scope:          plugin-global
format:         JSONL (one row per audit invocation; per-skill detail rows nested)
path:           _meta-runtime/storage-audit.jsonl
gatekeeper:     skills/_meta/evolution-scan/scripts/storage_fit_scan.py (sole writer)
read:           aggregate (jq, Python loop)
write:          per-invocation (append-only; one row per audit run with embedded per-skill list)
shape:          uniform-typed
                fields: ts, audit_run_id, audit_lens (storage-fit|critic-drift),
                total_skills, tally: {ALIGNED, UNDECLARED, DRIFT, MATRIX_GAP, ERROR},
                matrix_rows, grace_days, beyond_grace, elapsed_days,
                per_skill: [{skill_id, verdict, declared, detail}]
cardinality:    medium (one row per audit run; ~weekly cadence)
regeneration:   primary observation; markdown batch-report rendered from this row
review:         machine-only; CEO consumes summary via render
tech-stack:     §2
notes:          Replaces _meta-runtime/batch-report-storage-audit-*.md as source of truth
                (markdown report retained as rendered view). Enables CEO query
                "how many DRIFT verdicts across the last 3 audit runs?" without manual file parsing.
```

### cycle-events — NEW (v5.21+)
```
tier:           T2
scope:          plugin-global
format:         JSONL (one row per cycle-runner advance + open + close + hook event)
path:           _meta-runtime/cycle-events.jsonl
gatekeeper:     bin/cycle_runner.py (sole writer)
read:           aggregate (jq, Python loop, kiho_telemetry_rollup.py)
write:          per-invocation (append-only)
shape:          uniform-typed
                fields: ts, cycle_id, template_id, template_version, op, phase_before, phase_after,
                transitioned, iter_in_phase, blocker_reason, escalation, budget, duration_ms,
                hook_failures (optional)
cardinality:    large (unbounded; prune by age >180d)
regeneration:   primary observation
review:         machine-only
tech-stack:     §2
notes:          Org-wide cycle telemetry stream. Drives v5.21 cycle health monitoring via
                kiho_telemetry_rollup.py extension. CEO query "which template has highest
                blocker rate?" reduces to jq aggregation here.
```

---

## 5. Committee records — NEW (Phase 4 alternate pilot)

Per storage-tech-stack §4. Queued for Wave 2 per Phase 1 pilot vote.

### committee-transcript — NEW
```
tier:           T1 (source of truth for live committee prose)
scope:          project
format:         markdown (committee clerk appends)
path:           <project>/.kiho/committees/<committee-id>/transcript.md
gatekeeper:     committee clerk role (to be formalized)
read:           grep
write:          per-round
shape:          free-prose (time-stamped appends)
cardinality:    medium
review:         committee
tech-stack:     §4
```

### committee-records-jsonl — NEW
```
tier:           T2 (parsed from transcript.md; regenerable)
scope:          project
format:         JSONL
path:           <project>/.kiho/committees/<committee-id>/records.jsonl
gatekeeper:     bin/kiho_clerk.py extract-rounds (deterministic parser; shipped v5.19.2)
read:           structured
write:          per-round (parsed)
shape:          uniform-typed — one row per message + one close row per transcript
                fields: committee_id, chartered_at, round, phase, author, confidence, position,
                optional rationale; close row adds outcome, final_confidence, rounds_used, decision
cardinality:    medium
regeneration:   `python bin/kiho_clerk.py extract-rounds --transcript <transcript.md> --out <records.jsonl>`
review:         occasional
tech-stack:     §4
notes:          transcript.md format specified in `references/committee-rules.md`
                §"Transcript format" (v5.19.2). Parser idempotent; byte-identical
                output on re-run. Exit codes 0/1/2/3 per v5.15.2.
```

### committee-index-sqlite — NEW / GAP (lazy; Wave 2)
```
tier:           T2 (lazy; rebuilt when cross-committee query fires)
scope:          project
format:         sqlite
path:           <project>/.kiho/state/committee-index.sqlite
gatekeeper:     kiho_clerk build-index
read:           SQL
write:          rebuilt from all records.jsonl on cross-committee query
shape:          uniform-typed (see storage-tech-stack.md §4 schema)
eviction:       (treated as T2 lazy; optional to keep across turns)
regeneration:   scan `<project>/.kiho/committees/*/records.jsonl` → insert
review:         machine-only
tech-stack:     §4
notes:          ships in Wave 2; do NOT cite this row until implementation lands
```

---

## 6. Archival memory — FIT

Per-agent markdown + one JSONL stream. Covered by existing `memory-write`, `memory-reflect`, `memory-consolidate` skills.

### observations — FIT
```
tier:           T1
scope:          both
format:         markdown + YAML frontmatter (importance score in frontmatter)
path:           <project>/.kiho/agents/<name>/memory/observations.md
                $COMPANY_ROOT/agents/<name>/memory/observations.md
gatekeeper:     memory-write
read:           grep + one-shot agent load
write:          per-task
cardinality:    medium
review:         occasional
```

### reflections — FIT
(path: `.kiho/agents/<name>/memory/reflections.md`; write: per-5-tasks or observation-importance>15)

### lessons — FIT
```
tier:           T1
scope:          both
format:         markdown + YAML frontmatter
path:           <project>/.kiho/agents/<name>/memory/lessons.md
                $COMPANY_ROOT/agents/<name>/memory/lessons.md
gatekeeper:     memory-write (promotion requires committee)
read:           last-5 injected into delegation prompts
write:          per-committee-approved-lesson
cardinality:    medium
review:         committee
notes:          cross-project promotion via §9 matrix row
```

### todos — FIT
(path: `.kiho/agents/<name>/memory/todos.md`; write: per-agent-self)

### drift-trend — FIT
```
tier:           T2
scope:          both
format:         JSONL
path:           .kiho/agents/<name>/memory/drift-trend.jsonl
read:           structured
write:          per-drift-score
shape:          uniform-typed
review:         machine-only
```

---

## 7. Session working state — FIT

Ralph externalization. Prose + small structured files. All T1.

### plan — FIT
```
tier:           T1
scope:          project
format:         markdown + YAML frontmatter
path:           <project>/.kiho/state/plan.md
gatekeeper:     CEO (re-writes fresh each iteration)
read:           fresh every Ralph iteration
write:          per-iteration
shape:          frontmatter+prose (priority-sorted list)
cardinality:    small
review:         occasional
notes:          load-bearing — Ralph externalization core
```

### agent-md — FIT
(path: `<project>/.kiho/state/AGENT.md`; write: per-session-close)

### completion — FIT
(path: `<project>/.kiho/state/completion.md`; write: per-turn)

### continuity — FIT
(path: `<project>/.kiho/state/CONTINUITY.md`; read: SessionStart hook; write: per-session-close)

### shelved-improvements — FIT
(path: `<project>/.kiho/state/shelved-improvements.md`; write: per-rejected-proposal)

### research-cache — FIT
```
tier:           T2
scope:          project
format:         markdown + YAML frontmatter
path:           <project>/.kiho/state/research/<iso>-<slug>.md
gatekeeper:     research skill
read:           grep during research cascade
write:          per-research-task
cardinality:    medium (prune by age)
regeneration:   raw; not regenerable — archived or deleted
review:         occasional
```

### dashboard-period-md — NEW (v5.23+)
```
tier:           T2
scope:          project
format:         markdown (generated)
path:           <project>/.kiho/state/dashboards/<period>.md
gatekeeper:     bin/dashboard.py
read:           retrospective ceremony (at open); reader on demand
write:          regenerable from telemetry; on-demand via script
shape:          fixed sections (Velocity / Reliability / Hiring / Committees / Skill factory / KB / Agent scores)
cardinality:    small (≤20 per year — per-cycle + quarterly)
regeneration:   python bin/dashboard.py --project <path> --period per-cycle|quarterly ...
review:         machine-only
tech-stack:     §3 markdown canonical (generated view — idempotent modulo Generated: header)
notes:          Consumers: retrospective ceremony opens by loading the dashboard; agent-promote committee cites top/bottom 5 scores; skill-evolution committee cites factory pass/reject rates; kb-lint health check cites pages_added_rate. Introduced by committee `dashboard-analytics-2026-04-23`. Metric 7 (agent scores) soft-depends on `agent-cycle-score-jsonl` from committee 05.
```

### agent-cycle-score-jsonl — NEW (v5.23+)
```
tier:           T2
scope:          project
format:         JSONL
path:           <project>/.kiho/state/agent-score-<period>.jsonl
gatekeeper:     bin/agent_cycle_score.py
read:           bin/dashboard.py (metric 7); agent-promote committee
write:          per-period (invoked at retro / quarter close)
shape:          {period, agent, score, breakdown{invocation_rate, phase_owner_rate, committee_win_rate, kb_weight}, generated_at}
cardinality:    small (≤ org-size per period)
regeneration:   python bin/agent_cycle_score.py --project <path> --period <label>
review:         committee (promotion criteria — any score < 0.70 flagged)
tech-stack:     §4 JSONL append-only
notes:          Formula: 0.4 × invocation_rate + 0.3 × phase_owner_rate + 0.2 × committee_win_rate + 0.1 × kb_weight. Introduced by committee `perf-review-360-2026-04-23`. Weighting is speculative at ship time; recalibration committee scheduled at end of v5.23 period.
```

### okrs-period-md — NEW (v6.1+)
```
tier:           T1
scope:          project
format:         markdown + YAML frontmatter
path:           <project>/.kiho/state/okrs/<period>/O-<period>-<level>-<slug>-<n>.md
                where level ∈ {company, dept-<dept>, individual-<agent>}
                period ∈ {YYYY-QN | YYYY-HN | YYYY-<slug>}
gatekeeper:     skills/core/okr/okr-set (emit); skills/core/okr/okr-checkin + okr-close (update)
read:           retrospective ceremony; bin/dashboard.py (metric 7 fallback);
                agent-promote step 2a; cycle-runner (optional aligns_to_okr in cycle index.toml)
write:          per-period creation + per-checkin update + close
shape:          frontmatter (o_id, okr_level, period, owner, aligns_to, status, weights, certificate)
                + ## Key Results section (weighted) + ## Check-ins + optional ## Close
cardinality:    small (≤50 per period per project)
eviction:       move closed files to .kiho/state/okrs/<period>/_closed/ 30 days post close
review:         committee (department level); user-gated (company level)
tech-stack:     §3 markdown canonical
notes:          Each level has its own approval chain in references/approval-chains.toml:
                okr-company (USER_OKR_CERTIFICATE), okr-department (DEPT_COMMITTEE_OKR_CERTIFICATE),
                okr-individual (DEPT_LEAD_OKR_CERTIFICATE). PreToolUse hook enforces certificate
                presence; skill-internal pre-emit gate enforces prerequisites. Introduced by
                decision `okr-framework-2026-04-23`. User-facing primer at references/okr-guide.md.
```

### announcements — NEW (v5.23+)
```
tier:           T1
scope:          both
format:         markdown + YAML frontmatter
path:           <project>/.kiho/state/announcements/<yyyy-mm-dd>-<slug>.md
                $COMPANY_ROOT/state/announcements/<yyyy-mm-dd>-<slug>.md
gatekeeper:     memo-send (wildcard emission); kiho-comms (re-surface)
read:           shift-handoff re-surface sweep; memo-inbox-read lookup
write:          per-broadcast
shape:          frontmatter (id, emitter, audience, pinned_until, ack_required, ack_by, basis) + prose body
cardinality:    small (≤100 per project)
eviction:       archive to `.kiho/state/announcements/_archive/` 90 days after pinned_until expiry
review:         committee (durable-invariant announcements promote to rules.md via kb-manager)
tech-stack:     §3 markdown canonical (see storage-tech-stack.md)
notes:          distinct from `memo-inbox` jsonl — announcements are bulletin-board (all audience matches read), not mailbox (single recipient). Basis field required when emitter is NOT CEO and NOT a dept-lead; must cite a closed committee decision path. Introduced by committee `broadcast-announcements-2026-04-23`.
```

---

## 8. Derived indexes

### skill-catalog-index — NEW (Phase 4 pilot)
```
tier:           T3 (session-scope)
scope:          plugin-global (built per project turn)
format:         sqlite with FTS5 virtual table
path:           <project>/.kiho/state/tier3/skill-catalog-<turn-id>.sqlite
gatekeeper:     bin/skill_catalog_index.py (NEW, Phase 4)
read:           SQL + FTS5 MATCH (serves 32 scripts under skill-create + facet_walk + kiho_rdeps)
write:          rebuilt at CEO INITIALIZE
shape:          uniform-typed (skills + skills_fts5 + catalog_parent_of)
cardinality:    medium (44 → 200+)
eviction:       session-scope — deleted at CEO turn end (cleanup hook)
regeneration:   walk `skills/**/SKILL.md` → parse frontmatter → insert; deterministic; ~50ms @ 44 skills
review:         machine-only
tech-stack:     §8
notes:          FIRST Tier-3 shipping artifact; pattern reusable for Wave 2 migrations;
                schema in storage-tech-stack.md §8
```

### skill-solutions — FIT (parity-checked)
```
tier:           T1 (derived view; regenerable)
scope:          both
format:         markdown (wikilinks)
path:           <project>/.kiho/kb/wiki/skill-solutions.md
                $COMPANY_ROOT/company/wiki/skill-solutions.md
gatekeeper:     kiho-kb-manager (rebuilds after each write)
read:           grep
write:          regenerated by kb-manager per post-write protocol
shape:          wikilink table
cardinality:    medium
regeneration:   kb-manager scans all wiki pages' `skill_solutions:` frontmatter lists
review:         committee
notes:          parity verified by `bin/kb_lint_skill_solutions.py` (v5.19 pre-work)
```

### index / backlinks / tags / graph / cross-project / timeline / stale / open-questions / by-confidence / by-owner — FIT (parity-checked)
```
tier:           T1 (derived views; regenerable from frontmatter + wikilinks)
scope:          both
format:         markdown
path:           <wiki>/<index-name>.md
gatekeeper:     kiho-kb-manager (rebuilds after each write)
regeneration:   per-index logic in `agents/kiho-kb-manager.md` § "Index rebuild protocol"
review:         occasional
notes:          parity verified by `bin/kb_lint_<name>.py` (10 checkers share
                the `bin/kb_lint_common.py` scaffold). `log.md` is intentionally
                excluded — append-only log; no derivational source-of-truth.
                See `agents/kiho-kb-manager.md` §"Index rebuild protocol" for
                full rationale.
```

---

## 9. On-demand agentic memory (Tier-3)

### skill-catalog-index — see §8 (matrix row is duplicated there; authoritative there)

### semantic-embedding-cache — DEFERRED
```
tier:           T3 (would be, if materialized)
scope:          session
format:         sqlite-vec (if forced by revisit trigger)
path:           <project>/.kiho/state/tier3/embeddings-<turn-id>.sqlite
gatekeeper:     n/a (deferred)
eviction:       session-scope
regeneration:   re-embed via pinned lightweight model
tech-stack:     §6 — explicitly deferred
revisit triggers:
  - agent hits 10-candidate ceiling in facet_walk.py even after narrowing hints
  - concrete cross-session memory retrieval use-case with justification
  - catalog ≥100 skills AND mean-pairwise Jaccard >0.03
notes:          Do NOT cite this row. Class is deferred until a trigger fires.
```

### scratch-per-script — FIT (no unified doctrine)
```
tier:           T3
scope:          session
format:         script author chooses — in-memory dict | tempfile+JSON | sqlite :memory:
path:           author-declared; session-scope discard
gatekeeper:     skill author (declaration in SKILL.md § Security/Storage)
eviction:       session-scope (strict; T3-MUST-1)
regeneration:   idempotent; re-running without scratch MUST produce equivalent result (T3-MUST-2)
tech-stack:     §7 (no mandate; pattern choices listed non-normatively)
notes:          skill authors declare their scratch pattern in SKILL.md;
                audit via `evolution-scan --audit=storage-fit`
```

---

## 10. Cross-project rollup — NEW (ships alongside Phase 4)

Per storage-tech-stack §9: kb-manager wiki promotion. No new Tier-3.

### cross-project-lessons — NEW
```
tier:           T1 (company tier)
scope:          company
format:         markdown + YAML frontmatter (Karpathy wiki)
path:           $COMPANY_ROOT/company/wiki/cross-project-lessons/<slug>.md
gatekeeper:     kiho-kb-manager (sole writer)
read:           grep + wikilink + kb-search
write:          CEO DONE step 5 → kb-promote → sanitize → drafts → lint → atomic-move
shape:          frontmatter (slug, confidence, republished_count, source_projects, promotion_history) + prose
cardinality:    medium (company-wide accumulation)
regeneration:   primary observation; not regenerable from other sources
review:         committee (at promotion time; kb-manager logs each promotion)
tech-stack:     §9
notes:          dedup via cosine-0.85 at promotion (ephemeral embedding, not persistent)
                sanitization rules extend kb-manager rules.md
```

### experience-pool-cross-project — FIT (v5.19.5+)
```
tier:           T1 (view over cross-project-lessons)
scope:          company
format:         markdown (experience-pool skill op=render-company-pool emits it)
path:           $COMPANY_ROOT/company/wiki/experience-pool.md
gatekeeper:     kiho-kb-manager + experience-pool skill
read:           grep
write:          regenerated when underlying cross-project-lessons change
regeneration:   python bin/experience_pool_render.py --company-root $COMPANY_ROOT
                (invoked by experience-pool skill op=render-company-pool;
                writes then routed through kb-manager op=update for drafts/
                atomicity + log.md append)
review:         occasional
tech-stack:     §9
notes:          dedup: char-3-gram Jaccard >0.85 (matches kb-promote threshold);
                sort within topic: confidence desc + updated_at desc + slug asc;
                idempotent modulo generated_at timestamp
```

---

## 10b. Cycle-runner artifacts — NEW (v5.21+)

Per `references/cycle-architecture.md`. Cycle-runner is the kiho kernel; these rows are normative for every lifecycle running through it.

### cycle-templates — NEW (v5.21+)
```
tier:           T1
scope:          plugin-global
format:         TOML
path:           references/cycle-templates/*.toml
gatekeeper:     CEO-committee (template counts as a "skill artifact" for review;
                runs through skill-intake → factory → critic gate)
read:           one-shot at op=open; cached parse during advance via mtime check
write:          per-commit (PR review)
shape:          uniform-typed (per references/cycle-runner/template-dsl.md spec)
cardinality:    small (7 today; <50 long-term — adding a template is a CEO decision)
review:         committee
tech-stack:     §1 (TOML for typed config)
notes:          Each template defines a complete lifecycle as data: phases, transitions,
                success conditions, budgets, hooks. Adding a new lifecycle = adding
                a new template; no orchestrator code change. See template-dsl.md
                for grammar; cycle-architecture.md for design context.
```

### cycle-index — NEW (v5.21+)
```
tier:           T1
scope:          project (or company for HR-domain cycles like talent-acquisition)
format:         TOML
path:           <project>/.kiho/state/cycles/<cycle_id>/index.toml
                $COMPANY_ROOT/state/cycles/<cycle_id>/index.toml (HR-domain only)
gatekeeper:     bin/cycle_runner.py (sole writer; other agents MUST NOT write)
read:           CEO INITIALIZE step 18 (per-cycle); humans on debug
write:          per advance (atomic-replace via temp + rename + fsync)
shape:          frontmatter-shaped TOML; phase data conforms to template's [index_schema]
cardinality:    medium per project (open + recently-closed cycles)
regeneration:   primary observation; not regenerable; protected by atomic writes
review:         occasional (CEO when debugging stuck cycles)
tech-stack:     §1
notes:          THE single source of truth for any cycle. Other artifacts (incident.md,
                decision.md, committee transcripts, candidate transcripts) are authoritative
                for the artifact they produce, but lifecycle position lives only here.
```

### cycle-master-index — NEW (v5.21+)
```
tier:           T1 (regenerable)
scope:          project
format:         markdown
path:           <project>/.kiho/state/cycles/INDEX.md
gatekeeper:     bin/cycle_index_gen.py (committee-approved generator;
                invoked from CEO DONE step 11)
read:           CEO INITIALIZE step 18 (full org snapshot)
write:          regenerated each CEO DONE; never hand-edited
shape:          mixed (open-cycles table + recently-closed list + templates list)
cardinality:    small
regeneration:   `python bin/cycle_index_gen.py --plugin-root ${CLAUDE_PLUGIN_ROOT} --project-root <project>`
review:         occasional
tech-stack:     §3 (markdown rendered view over per-cycle TOML sources)
notes:          The CEO's one-glance org dashboard. If hand-edited, next regen overwrites it.
                Pattern matches catalog-routing-block (mixed T1+T2 source-of-truth).
```

### cycle-handoffs — NEW (v5.21+)
```
tier:           T2
scope:          project
format:         JSONL (append-only)
path:           <project>/.kiho/state/cycles/<cycle_id>/handoffs.jsonl
gatekeeper:     bin/cycle_runner.py (sole writer)
read:           bin/cycle_replay.py for timeline reconstruction; CEO on debug
write:          per-transition + per-escalation + per-hook-event (append-only)
shape:          uniform-typed
                fields: ts, cycle_id, action, from?, to?, transitioned?, reason?, emitted_by, hook_verb?
cardinality:    medium per cycle (typically 10-30 rows; capped by max_iters)
regeneration:   primary observation; not regenerable
review:         machine-only (replay tool is the human view)
tech-stack:     §2
notes:          Per-cycle audit trail. Crash-safe append. Replay tool reconstructs
                the timeline view for debugging. Combined with cycle-events.jsonl
                (org-wide stream) this gives complete observability of any cycle.
```

---

## 10c. Inboxes & pending queues — NEW (v5.21+)

Async peer-to-peer channels and lifecycle commit queues. All Tier-2 JSONL with explicit eviction.

### memo-inbox — NEW (v5.21+)
```
tier:           T2
scope:          project
format:         JSONL (one row per memo)
path:           <project>/.kiho/state/inbox/<agent_id>.jsonl
gatekeeper:     memo-send (writer) / memo-inbox-read (reader)
read:           keyed by agent_id, age-filter on read; CEO drains all inboxes at loop start
write:          per-memo (peer-to-peer; severity=info|action|blocker)
shape:          uniform-typed (ts, from_agent, subject, severity, payload_ref)
cardinality:    medium (per agent; unbounded growth without prune)
eviction:       30d for severity=info; 90d for action; never for blocker (until resolved)
review:         occasional
tech-stack:     §4
notes:          severity=blocker mirrored to committee blockers.md (Tier-1) by memo-send
                so the CEO sees blockers in the committee deliberation context too.
```

### handoff-receipts — NEW (v5.21+)
```
tier:           T2
scope:          project
format:         JSONL (one row per receipt)
path:           <project>/.kiho/state/handoffs/<turn_id>.jsonl
gatekeeper:     handoff-accept (writer) / CEO loop-boundary scan (reader)
read:           per-turn (CEO scans receipts to confirm in-flight tasks)
write:          per-delegation (sub-agent emits receipt before starting work)
shape:          uniform-typed (brief_id, accept|conditional|reject, eta_iterations,
                confidence, open_questions)
cardinality:    small (per turn; ≤fanout-cap × depth-cap = 5×3 = 15 max per turn)
eviction:       turn-scope (rotate to <project>/.kiho/state/handoffs/archive/<turn_id>.jsonl
                after CEO DONE; archive 90d then prune)
review:         per-turn
tech-stack:     §4
```

### feedback-queue — NEW (v5.21+)
```
tier:           T2
scope:          project
format:         JSONL with two channels (request + response)
path:           <project>/.kiho/state/feedback/{requests,responses}.jsonl
gatekeeper:     user-feedback-request (writer requests) / CEO (writer responses) /
                memory-reflect (reader for analysis)
read:           rate-limited drain by CEO at loop start (≤1 prompt per N turns)
write:          per-prompt-proposal (request side) + per-user-response (response side)
shape:          uniform-typed (turn_id, question_set, draft_text, severity,
                response, response_ts)
cardinality:    small (rate-limited)
eviction:       180d archive after analysis by memory-reflect
review:         occasional (review user-response patterns quarterly)
tech-stack:     §4
notes:          Preserves the CEO-only user-funnel invariant; sub-agents propose,
                CEO drains and decides what to surface in the next response.
```

### commit-ceremony-pending — NEW (v5.21+)
```
tier:           T2
scope:          project
format:         JSONL pending queue + canonical T1 evolution row written via storage-broker
path:           <project>/.kiho/state/commit-ceremony/<target_canonical_ref>/pending.jsonl
gatekeeper:     commit-ceremony (drains queue) / domain skill (writes pending entry)
read:           per-commit-ceremony-call (drain → validate → apply → broadcast)
write:          per-domain-event (soul-override drift / skill-improve patch /
                sunset-announce action)
shape:          uniform-typed (entry_id, payload_ref, validator_status, applied_at|null)
cardinality:    medium (varies per target; coalesces across days)
eviction:       on-apply (entries flipped to applied=true; full-archive at 60d to
                <project>/.kiho/state/commit-ceremony/<target_canonical_ref>/archive/)
review:         per-domain (callee owns validator + auth policy)
tech-stack:     §4
notes:          Shared engine for soul-apply-override / skill-improve / skill-sunset-announce.
                The target_canonical_ref namespace keeps queues per-target; commit-ceremony
                never interprets payloads — only orchestrates the drain-validate-apply loop.
```

---

## 11. Staging / drafts — FIT

### kb-drafts — FIT
```
tier:           T2
scope:          both
format:         markdown (staging)
path:           <project>/.kiho/kb/drafts/<REQUEST_ID>/
                $COMPANY_ROOT/company/drafts/<REQUEST_ID>/
gatekeeper:     kiho-kb-manager
lifecycle:      staged → lint → atomic-move to wiki/; warn 90d, error 180d
```

### skill-drafts — FIT
```
tier:           T2
scope:          project
format:         full SKILL.md structure (pre-promotion)
path:           <project>/.kiho/state/drafts/sk-<slug>/
gatekeeper:     skill-create / skill-learn op=synthesize / skill-derive
lifecycle:      draft → committee gate → promote to `skills/<domain>/<slug>/`
```

### skill-skeletons — FIT
```
tier:           T2
scope:          project
format:         markdown skeleton
path:           <project>/.kiho/state/skill-skeletons/<slug>.md
gatekeeper:     research-deep (emits) → skill-learn op=synthesize (consumes) → archive
```

---

## Summary counts

- **FIT** rows: 36 (no migration needed)
- **MIGRATING** rows: 1 (recruit-role-specs — lazy on next recruit-skill touch)
- **NEW** rows: 18 (committee-transcript, committee-records-jsonl, skill-catalog-index pilot, cross-project-lessons, **skill-factory-verdicts**, **skill-critic-verdicts**, **evolution-scan-audits**, **cycle-events**, **cycle-templates**, **cycle-index**, **cycle-master-index**, **cycle-handoffs**, **values-flags** (v5.21+), **integrations-registry** (v5.21+), **memo-inbox** (v5.21+), **handoff-receipts** (v5.21+), **feedback-queue** (v5.21+), **commit-ceremony-pending** (v5.21+))
- **NEW / GAP** rows: 1 (committee-index-sqlite — lazy, Wave 2; do not cite)
- **DEFERRED** rows: 1 (semantic-embedding-cache — revisit trigger instrumented v5.19.5)
- **NEW-PATTERN** rows: 1 (capability-matrix in-memory dict — reclassification, no migration)

_Last verified 2026-04-19 (post-v5.19.5; +3 NEW rows v5.20 Wave 1.1)._

## How skills cite this matrix

New skill frontmatter:
```yaml
metadata:
  kiho:
    data_classes: [agent-performance, skill-catalog-index]
```

Allowed values are the row slugs in this file. `skill-create` Gate adds validation; `evolution-scan --audit=storage-fit` flags drift. Legacy skills are grandfathered until `skill-improve` touches them (180d warn → error).

## Adding a new data class

1. Draft a row per the schema.
2. Open a matrix PR + write a committee proposal.
3. Route through CEO-committee vote (per `committee-rules.md`); unanimous close.
4. On approval, merge into this file; CHANGELOG entry.
5. Matrix-PR also updates `storage-tech-stack.md` if a new tech choice is involved.
