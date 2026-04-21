# Canonical layouts per domain

The closed set of layout templates kiho enforces via `skill-parity`. **v5.18.1 reorganization**: per-domain *rules with signal-driven defaults*, not per-skill enumeration. Every skill **MUST** match its domain rule's `default_layout` OR satisfy a documented `signal_override` clause OR declare a `parity_exception:` with one-line rationale.

> The key words **MUST**, **MUST NOT**, **SHOULD** are interpreted per BCP 14 (RFC 2119, RFC 8174).

## Non-Goals

- **Not extensible without committee vote.** Adding a new canonical layout (or a new domain rule) requires CEO-committee approval. Vocabulary discipline per v5.16 controlled-set.
- **Not a content spec.** Defines file shape, not file content. Body content is `skill-create` + `skill-critic` territory.
- **Not a frontmatter shape spec.** That lives in `templates/skill-frontmatter.template.md`. This file declares which `references/` and `scripts/` files exist per skill.
- **Not a per-skill enrollment list.** The pre-v5.18.1 per-skill table drifted (8+ stale entries within 30 days). Rules survive sibling churn; lists do not.
- **Not authoritative for the script.** `parity_diff.py:DEFAULT_DOMAIN_LAYOUT` is the authoritative mapping at runtime. This file is the human-readable rationale; the script is the executable contract. They MUST stay in sync via committee vote.

## Five canonical layout templates

### 1. `standard` — body-only skill

```
skills/<domain>/<skill-name>/
└── SKILL.md
```

Validation:
- `references/` directory: ABSENT or empty
- `scripts/` directory: ABSENT or empty
- `assets/` directory: ABSENT
- `config.toml` / `config.yaml`: ABSENT

### 2. `meta-with-scripts` — skill ships scripts, no narrative reference

```
skills/<domain>/<skill-name>/
├── SKILL.md
├── config.toml      (optional; canonical for kiho-itself; v5.19.3+ migrated from config.yaml)
└── scripts/
    └── *.py         (1+ scripts following 0/1/2/3 exit-code convention)
```

Validation:
- `scripts/` directory: PRESENT with ≥ 1 `.py` file
- Each `.py`: includes "Exit codes:" docstring block
- `references/` directory: ABSENT or empty

### 3. `meta-with-refs` — skill ships narrative references, no scripts

```
skills/<domain>/<skill-name>/
├── SKILL.md
└── references/
    └── *.md         (1+ reference markdown files; each ≥ 6/9 patterns)
```

Validation:
- `references/` directory: PRESENT with ≥ 1 `.md` file
- Each reference: scores ≥ 6/9 on `pattern_compliance_audit.py`
- `scripts/` directory: ABSENT or empty

### 4. `meta-with-both` — skill ships scripts AND references

```
skills/_meta/<skill-name>/
├── SKILL.md
├── scripts/
│   └── *.py
└── references/
    └── *.md
```

Validation:
- `scripts/` directory: PRESENT with ≥ 1 `.py` file
- `references/` directory: PRESENT with ≥ 1 `.md` file
- Optional: `agents/<sub-agent>.md` — sub-agent definitions (e.g., skill-create's analyzer/comparator; skill-architect's critic)

### 5. `parity-exception` — explicit opt-out

Validation:
- Frontmatter MUST include `metadata.kiho.parity_exception: <rationale ≥ 10 chars>`
- Logged to `_meta/parity-exceptions.md` for periodic review
- Exception expires after 12 months unless re-ratified by CEO-committee

## Per-domain rules (signal-driven defaults)

Each rule has a `default_layout` that applies absent contrary signals + zero or more `signal_override` clauses that swap the default when intent signals match. Architect's Step C consults this file via `parity_diff.py --telemetry-driven` to surface drift between declared and observed canonicals.

### Domain `_meta/skill-create`, `_meta/skill-spec`, `_meta/skill-factory`, `_meta/skill-structural-gate`

```yaml
domain: _meta/<heavy-meta-skill>
default_layout: meta-with-both
signal_overrides: []  # heavy meta skills always carry both
```

Rationale: every skill in this cluster is a factory primitive — it produces artifacts, validates artifacts, or orchestrates other primitives. All require both deterministic scripts AND human-readable references explaining the rules. As of 2026-04-17 `skill-structural-gate` replaces the former `skill-graph` + `skill-parity` pair; both old names remain as deprecation shims (layout `standard`, see `_meta/deprecated-shim` below).

### Domain `_meta/deprecated-shim` (skill-architect, skill-graph, skill-parity as of 2026-04-17)

```yaml
domain: _meta/<deprecated-shim>
default_layout: standard
signal_overrides: []
parity_exception_rationale: "deprecation shim — body reduced to one-paragraph redirect; scripts/ and references/ are migrated to the superseding skill"
```

Rationale: deprecation shims carry only the redirect body. The scripts and references live in the `superseded-by` skill. Parity scans **MAY** flag shims as divergent versus their pre-deprecation heavy-meta layout; the lazy-graduation policy treats this as acceptable drift because the shim is intentionally minimal.

### Domain `_meta/skill-find`

```yaml
domain: _meta/skill-find
default_layout: parity-exception
parity_exception_rationale: "single-purpose retrieval scripted via facet_walk.py; no narrative reference required"
```

### Domain `_meta/skill-improve`, `_meta/skill-derive`, `_meta/skill-deprecate`, `_meta/skill-learn`

```yaml
domain: _meta/<lifecycle-skill>
default_layout: meta-with-refs
signal_overrides:
  - condition: "operation requires deterministic computation (e.g., diff scoring)"
    layout: meta-with-both
    examples: [skill-improve (planned: scripts/diff_score.py)]
```

Rationale: lifecycle skills mostly orchestrate via prose + decision trees; scripts are an opt-in optimization, not the core.

**Graduation status (Apr 16 2026, v5.18.3.1):**

| Skill | Declared layout (`parity_diff.py`) | Status |
|---|---|---|
| `skill-deprecate` | `meta-with-refs` | **graduated** — ships `references/consumer-review-rules.md`; points at `skill-create/references/deprecation-shim.md` for shim format |
| `skill-learn` | `meta-with-refs` | already graduated — ships `references/synthesize-procedure.md` |
| `skill-improve` | `standard` | graduation pending — candidate references: diff-scoring procedure, committee-proposal format |
| `skill-derive` | `standard` | graduation pending — candidate references: parent-skill-composition rules |

Per-skill graduations are individual CEO-committee decisions; the rule above is the target, not the current state for `skill-improve` / `skill-derive`.

### Domain `_meta/evolution-scan`, `_meta/soul-apply-override`

```yaml
domain: _meta/<scan-or-mutate>
default_layout: standard
signal_overrides:
  - condition: "scan produces a structured report consumed by other skills"
    layout: meta-with-scripts
    examples: []  # none currently; would apply if evolution-scan grows a scoring script
```

### Domain `core/harness` ⚠️  Telemetry drift detected

```yaml
domain: core/harness
declared_default_layout: meta-with-scripts
observed_modal_layout: standard  # via parity_diff.py --telemetry-driven (Apr 2026: 4 of 5 siblings)
divergence: declared canonical does NOT match observed mode

signal_overrides:
  - condition: "pure dispatcher / router / config holder (no arithmetic, no scale signal)"
    layout: standard
    examples: [kiho-spec, kiho-setup, kiho-init]
    architect_signals_that_force_this:
      - capability == orchestrate
      - scripts_score < 0.30
      - state_artifact signals absent
  - condition: "computes over data files OR holds runtime config OR is the single writer of state"
    layout: meta-with-scripts
    examples: [kiho (config.toml is canonical, v5.19.3+), org-sync (recompute_proficiency.py)]
    architect_signals_that_force_this:
      - capability == update
      - scripts_score >= 0.50
      - state_artifact signals present (registry, matrix, ledger)
      - side_effect signals present (writer, single writer, append)
```

CEO-committee action item: the declared canonical is currently meta-with-scripts but only 1 of 5 siblings (org-sync) actually ships scripts. Either (a) demote declared canonical to `standard` with `meta-with-scripts` as a signal-override (recommended; matches observed reality), or (b) backfill scripts into kiho-spec/setup/init (not justified — they are dispatchers).

### Domain `core/hr`

```yaml
domain: core/hr
default_layout: meta-with-refs
signal_overrides:
  - condition: "hire pipeline ships templates / scoring rubrics"
    layout: meta-with-refs   # references include rubrics, not scripts
    examples: [recruit (interview-rounds.md, smoke-test.md, quality-scorecard.md), design-agent (capability-gap-resolution.md, output-format.md)]
```

Rationale: hiring is rubric-heavy + procedure-heavy → narrative references dominate. Scripts would only fit if scoring became deterministic-arithmetic, which it currently isn't.

### Domain `core/inspection`

```yaml
domain: core/inspection
default_layout: standard
signal_overrides:
  - condition: "inspection emits structured report file"
    layout: meta-with-scripts
    examples: []  # kiho-inspect could grow here
```

### Domain `core/knowledge`

```yaml
domain: core/knowledge
default_layout: meta-with-refs
signal_overrides:
  - condition: "research crawler with deterministic precondition checks"
    layout: meta-with-scripts
    examples: [research-deep (robots_check.py)]
  - condition: "pure narrative protocol"
    layout: standard
    examples: [research, experience-pool]
```

### Domain `core/planning`

```yaml
domain: core/planning
default_layout: standard
signal_overrides:
  - condition: "planning skill ships scoring script + structured rubric assets"
    layout: meta-with-both
    examples: [interview-simulate (score_drift.py + canonical-rubric.toml)]
```

### Domain `kb/*`

```yaml
domain: kb/*
default_layout: standard
signal_overrides: []
```

Rationale: KB ops are gateway calls into kiho-kb-manager — pure prose contracts.

### Domain `memory/*`

```yaml
domain: memory/*
default_layout: standard
signal_overrides: []
```

### Domain `engineering/*`

```yaml
domain: engineering/*
default_layout: parity-exception
parity_exception_rationale: "ships nested kiro/ directory (legacy first-skill copy); restructuring deferred to v5.19+"
```

## Reading rules

The architect (Step C `observe_siblings.py`) and skill-parity (`parity_diff.py`) read this file as follows:

1. **Match domain** — find the most-specific domain rule (e.g., `_meta/skill-create` before `_meta/*`).
2. **Apply default_layout** — start from the rule's `default_layout`.
3. **Check signal_overrides** — for each override, evaluate `architect_signals_that_force_this` (when present) against the architect's signal vector. First match wins.
4. **If parity-exception** — require `metadata.kiho.parity_exception` rationale on the skill's frontmatter.
5. **Surface divergence** — if observed sibling layout differs from declared (via `--telemetry-driven`), emit a CEO-committee action item but do not block.

## Promotion process

To add a new canonical layout (e.g., v5.19 introduces "meta-with-agents" for skills shipping `agents/*.md` sub-agent definitions as a first-class layout):

1. RFC drafted naming the layout, the validation rules, and the kiho consumers.
2. CEO-committee vote.
3. Update this file with the new template + per-domain rule additions.
4. Update `dry_run.py`'s VALID_PARITY_LAYOUTS set + `parity_diff.py`'s LAYOUT_DEFINITIONS + DEFAULT_DOMAIN_LAYOUT.
5. Bump skill-parity to next minor version.

To modify an existing per-domain rule (e.g., promote `core/harness` declared canonical from `meta-with-scripts` to `standard` to match observed mode):

1. Run `parity_diff.py --telemetry-driven --domain <domain>` to confirm the drift is stable (≥ 80% consensus, ≥ 5 siblings).
2. CEO-committee vote with the telemetry report attached.
3. Update this file's per-domain rule.
4. Update `parity_diff.py:DEFAULT_DOMAIN_LAYOUT` to match.
5. Run `parity_diff.py --mode catalog-audit` to verify no skills become divergent.

## Grounding

- GEPA Pareto-frontier discipline (per-domain canonical, not global) — https://arxiv.org/abs/2507.19457
- v5.16 controlled-set discipline (capability + topic vocabulary) — applied to layouts here
- v5.17 research findings §"7 missing pieces #5" — skill-parity rationale
- v5.18.1 plan §"Fix 3" — rewrite from per-skill list to per-domain rule with signal-driven defaults; Gap 2 closure
- Apr 2026 telemetry observation — `core/harness` declared canonical drifts from observed mode (4 of 5 siblings ship `standard`), surfacing the per-skill-list maintenance debt that motivated this rewrite
