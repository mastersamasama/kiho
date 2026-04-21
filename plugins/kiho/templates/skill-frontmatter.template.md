# Skill frontmatter template (2026, v5.15)

Canonical frontmatter for a kiho skill. Copy, remove optional fields you don't need, fill in the rest. **Structured to match the agentskills.io open standard**: 6 canonical top-level fields, kiho extensions nested under `metadata:`. v5.15 introduces a `metadata.kiho:` sub-block for forward-only dependency declarations.

```yaml
---
# ===== CANONICAL (agentskills.io open standard) =====
# These 6 fields are the top-level contract. Everything else goes under metadata.

name: {{skill-name-kebab-case-max-64-chars}}

description: |
  {{Use this skill whenever the user wants to <concrete action list>. This
  includes <action 1>, <action 2>, ... <action 8>. If the user mentions
  <literal trigger phrase 1> or <literal trigger phrase 2>, use this skill.
  Must trigger whenever <context 1> or <context 2>.}}

# license: MIT                      # optional — SPDX identifier

# compatibility: |                  # optional — environment requirements (1-500 chars)
#   Requires Python 3.11+, git, tiktoken. Runs on Linux, macOS, Windows.

# allowed-tools: Bash(git add *) Bash(git commit -m *)  # optional — narrow scope only; never Bash(*)

metadata:
  # ----- kiho lifecycle -----
  version: 0.1.0
  lifecycle: draft                  # draft | active | deprecated

  # ----- kiho facets (v5.16: Primitives 2 + 3) -----
  # capability and topic_tags are the two most important discoverability
  # facets. Gate 20 enforces capability from the closed 8-verb set;
  # Gate 21 enforces topic_tags from the controlled vocabulary. Free-form
  # tags or out-of-set verbs block skill-create.
  kiho:
    # Closed 8-verb set (v5.16): create | read | update | delete |
    # evaluate | orchestrate | communicate | decide. One verb only.
    # See kiho-plugin/references/capability-taxonomy.md for definitions.
    capability: {{one-of-8-verbs}}

    # Controlled vocabulary (v5.16): pick 1-3 tags from
    # kiho-plugin/references/topic-vocabulary.md. Free-form tags are rejected.
    topic_tags: [{{tag1}}, {{tag2}}]

    # ----- composition and lineage (v5.15) -----
    # Forward-only dependency declarations. Reverse lookups are computed on
    # demand via `bin/kiho_rdeps.py` — do not maintain a reverse index on
    # disk. Grounding: kiho v5.15 H5, npm/cargo/Bazel convention.
    requires: []                    # hard deps — skill fails if missing (e.g., [sk-013, sk-016])
    mentions: []                    # soft refs — body links but doesn't require (e.g., [sk-024])
    reads: []                       # KB page paths this skill reads (e.g., [kb/policy/retention.md])
    supersedes: []                  # skills this one replaces (filled by skill-deprecate)
    deprecated: false               # set to true by skill-deprecate
    # superseded-by: sk-NNN         # set by skill-deprecate; omit when active

  # ----- skill-create audit block (populated at generation time) -----
  created_by: skill-create
  created_at: {{iso_timestamp}}
  validation_gates_passed: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
  security_risk_tier: low           # low | medium | high | trifecta
  lethal_trifecta_check: passed
  # Phase 1 (binary 8-rule scorer)
  iterative_description_score: 1.0
  iterative_description_loops: 0
  # Phase 2 (train/test iterative rewriter, v5.13)
  train_accuracy: 0.92
  test_accuracy: 0.88
  overfitting_warning: false
  # Gate 11 (transcript review, v5.13)
  gate_11_min_mean: 4.3
  gate_11_scenario_count: 3

  # ----- legacy deprecation metadata (pre-v5.15) -----
  # As of v5.15, deprecation state lives under metadata.kiho.deprecated and
  # metadata.kiho.superseded-by (see above). The fields below are retained
  # for backwards reading but new skills should not populate them.
  # deprecated_at: 2026-06-01
  # removal_target: 2026-08-01

# ===== CLAUDE CODE EXTENSIONS (optional top-level, Claude-Code-specific) =====
# These are Claude Code extensions to the agentskills.io standard.
# They're fine to use at the top level for skills running in Claude Code.

# argument-hint: "[issue-number]"   # shows in /<skill-name> autocomplete
# user-invocable: true              # default true; set false for knowledge-only skills
# disable-model-invocation: false   # default false; set true for side-effect-heavy workflows
# model: claude-opus-4-6            # override session model (rare)
# effort: high                      # low | medium | high | max
# context: fork                     # run body in isolated subagent (rare)
# agent: Explore                    # required if context: fork
# shell: bash                       # bash | powershell (for !`cmd` inline blocks)
# paths:                            # activate only for matching file types
#   - "*.py"
#   - "src/**/*.ts"
# hooks:
#   pre-invocation:
#     - type: validate
#       script: scripts/validate_inputs.py
---
```

## Why this structure

The agentskills.io open standard (2026) defines only 6 top-level frontmatter fields: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`. By nesting kiho-specific extensions under `metadata:`, we stay compatible with the standard — a skill shipped by kiho can be consumed by any agentskills.io-compliant runtime, and a skill shipped by another org using the canonical format can be imported into kiho without frontmatter rewrites.

**What changed from v5.11:** previously, `version`, `lifecycle`, `topic_tags`, and the audit block were all top-level fields. v5.13 moves them under `metadata:` to restore standard compliance. This is a breaking change to the skill file format but is **not** a behavioral change — `kb-add`, `skill-create`, and `catalog_gen.py` all read the fields by path regardless of nesting, and the migration is a one-time mechanical rewrite.

**Claude Code extensions** (argument-hint, disable-model-invocation, context: fork, paths, shell, hooks, etc.) are NOT in the agentskills.io standard but are documented at `code.claude.com/docs/en/skills` as Claude Code-specific extensions. They're fine to use at top level when the skill runs in Claude Code specifically.

## Field usage notes

**`allowed-tools` narrowing examples:**

```yaml
# Good — narrow to specific git operations
allowed-tools: Bash(git status) Bash(git diff *) Bash(git add *) Bash(git commit -m *)

# Bad — wildcard grant
allowed-tools: Bash(*)
```

**`context: fork` when to use:**

- The skill's body is long and loading it into the main context would pollute other work
- The skill handles sensitive content that should not leak into the main context
- The skill is a self-contained multi-step procedure with no need to share state

Don't use `context: fork` for fast, lightweight skills — the fork overhead is larger than the saving.

**`paths` examples:**

```yaml
# Python-only skill
paths: ["*.py", "**/*.py", "pyproject.toml"]

# React frontend skill
paths: ["*.tsx", "*.jsx", "**/components/**"]

# Documentation-only skill
paths: ["*.md", "docs/**"]
```

When `paths` is set, the skill is loaded into the system prompt only when the current working file matches. This reduces token cost for skills with narrow applicability.

**`metadata.kiho.requires` vs `metadata.kiho.mentions` (v5.15):**

The two dep fields have different semantics and different consumers.

- **`requires`** — hard dependency. If the listed skill is absent from the catalog, the declaring skill's procedure cannot execute. Used by `skill-deprecate` as the **blocking** consumer class: a skill cannot be deprecated while any other skill declares it under `requires`. Used by `kb-lint` to flag stale references when a hard dep points at a deprecated target.
- **`mentions`** — soft reference. The declaring skill's body links to the referenced skill (e.g., "see also `skill-find`") but does not execute it or require its presence. Used by `kiho_rdeps` in the soft-consumer report. Used by `kb-lint` for advisory drift detection, not blocking.

Neither field is runtime-enforced at invocation time. kiho still does not prevent a skill from being invoked when a required skill is missing — the consumer is responsible for checking. What the fields DO enforce is the **deprecation cascade**: when you run `skill-deprecate` on a skill with hard-required consumers, the deprecation is blocked until the consumers are migrated. This makes dependencies real at evolution time, even if they are not real at invocation time.

**`metadata.kiho.reads` (v5.15):**

Lists KB page paths (`kb/<tier>/<path>.md`) that the skill reads during its procedure. Enables `skill-improve` Step 0 to warn when a proposed diff touches a section referenced by a consumer's `reads` path. Not runtime-enforced.

**`metadata.kiho.supersedes` / `deprecated` / `superseded-by` (v5.15):**

Managed by `skill-deprecate` — authors do not populate these by hand. A normal active skill carries `deprecated: false` and omits `supersedes` and `superseded-by`. When `skill-deprecate` runs, it flips `deprecated: true`, sets `superseded-by: <replacement-slug>`, and may append to `supersedes: [<old-slug>]` on the replacement skill. See `skills/_meta/skill-create/references/deprecation-shim.md`.

**No top-level `requires:` field.** Under no circumstances may a skill declare `requires:` at the top level of its frontmatter. The only canonical place for dependencies is under `metadata.kiho.requires`. This is mandated by kiho v5.15 per the agentskills.io spec rejection of top-level dependency fields (Claude Code issue #27113 closed "not planned"; agentskills RFC #252 signature field rejected on the same basis). Fields outside `metadata.kiho.*` are considered spec violations and are rejected by Gate 2.
