---
name: skill-cousin-prompt
description: Use this skill to flag a SKILL.md draft that diverges from its semantic siblings (skills in the same parent domain) on deterministic structural axes — section parity, frontmatter shape, body length, and description style. Returns a JSON verdict with per-axis divergence scores, a one-line summary, and a recommendation. Invoked as Step 9 of the skill-factory SOP via a request bundle written to `_meta-runtime/cousin-prompt-requests/`, or standalone for ad-hoc divergence checks before catalog promotion. Triggers on "compare against siblings", "cousin check", "skill-cousin-prompt", or when skill-factory needs the Step 9 divergence verdict. Read-only — never mutates the target.
version: 1.0.0
lifecycle: active
metadata:
  trust-tier: T3
  kiho:
    capability: evaluate
    topic_tags: [validation, authoring]
    data_classes: ["skill-definitions"]
---
# skill-cousin-prompt

Deterministic divergence check for SKILL.md drafts against their semantic siblings. Catches the failure mode skill-critic misses: a draft that scores well on absolute quality axes but breaks the conventions every other skill in its parent domain follows. Read-only — never mutates the target.

> **v5.21 cycle-aware.** This skill MAY be invoked atomically (`scripts/cousin_check.py --skill-path <path>`) OR via the request bundle pattern when invoked from `bin/skill_factory.py` Step 9. There is no cycle template that uses this skill as a phase entry today; it lives entirely inside the skill-factory SOP. Atomic invocation remains supported.

## Contents
- [Scope](#scope)
- [Inputs](#inputs)
- [Bundle-consumer contract (skill-factory invocation)](#bundle-consumer-contract-skill-factory-invocation)
- [Divergence axes](#divergence-axes)
- [Verdict semantics](#verdict-semantics)
- [Response shape](#response-shape)
- [Anti-patterns](#anti-patterns)
- [Grounding](#grounding)

## Scope

skill-cousin-prompt is the **Step 9 gate** in the `skill-factory` 10-step SOP. It complements skill-critic (Step 5): where skill-critic asks "is this draft well-authored on its own?", cousin-prompt asks "does this draft fit the conventions of its parent domain?". A draft that passes Step 5 with a 0.95 score but uses none of its sibling's section names, frontmatter shape, or body organization is likely a **drift seed** — once it ships, future authors copy it and the catalog fragments.

The check is **deterministic by design** per the v5.16 invariant *"No LLM judge at any gate"* (skill-authoring-standards.md §v5.14 additions). All four axes compute deterministically from file structure; no LLM call, no embedding similarity (Tier-3 embeddings remain DEFERRED per `data-storage-matrix.md` §"semantic-embedding-cache"). If <2 siblings exist in the parent domain, the check skips gracefully (status `insufficient_siblings`, verdict `green`).

## Inputs

```
skill_path:    <absolute path to a SKILL.md file>
plugin_root:   <path to the kiho-plugin root; default cwd> (optional)
sibling_glob:  <override for sibling discovery; default uses skill_path's parent domain> (optional)
threshold:     <max acceptable divergence score per axis; default 0.40> (optional)
```

Sibling discovery: the parent domain is the immediate parent of the skill's domain directory. For `skills/_meta/skill-cousin-prompt/SKILL.md`, the parent domain is `skills/_meta/`; siblings are every `skills/_meta/*/SKILL.md` other than the target.

## Bundle-consumer contract (skill-factory invocation)

When `bin/skill_factory.py` invokes this skill via the Phase 2 harness, it writes a bundle JSON to `_meta-runtime/cousin-prompt-requests/cousin-prompt-request-<id>.json` and instructs the CEO (via the Task tool) to spawn a subagent of type `skill-cousin-prompt`. The subagent MUST:

1. Read the bundle file. Required keys: `step` (always 9), `target` (relative path to SKILL.md), `prior_results` (verdict-summary list from earlier steps), `request_id`.
2. Resolve `target` to an absolute path under the plugin root.
3. Run the divergence check (axes below) and produce a response JSON with the [Response shape](#response-shape) below.
4. Write the response to `_meta-runtime/cousin-prompt-requests/cousin-prompt-response-<id>.json` (the same `<id>` as the request).
5. Return control to the CEO, which re-enters the factory via:
   `bin/skill_factory.py --regen <target> --phase full --cousin-prompt-output _meta-runtime/cousin-prompt-requests/cousin-prompt-response-<id>.json`

The subagent **MUST NOT** mutate the target SKILL.md, sibling SKILL.md files, or any state outside `_meta-runtime/cousin-prompt-requests/`.

## Divergence axes

Four axes; each returns a divergence score in [0.0, 1.0] where 0.0 = identical to sibling pattern and 1.0 = maximally divergent. The verdict aggregates by `max()` (worst axis dominates), since one bad divergence is enough to drift the catalog.

| Axis | What it measures | Computation |
|---|---|---|
| 1. section_parity | Does the body have the same H2 section names as ≥50% of siblings? | divergence = 1 − (intersection / sibling-modal-set-size); siblings' modal H2 set is the union of H2 names appearing in ≥50% of siblings |
| 2. frontmatter_shape | Does the frontmatter use the same `metadata.kiho.*` keys as siblings? | divergence = (target_keys ∆ modal_keys) / modal_keys ; symmetric difference normalized by sibling modal key set size |
| 3. body_length_band | Is the body length within ±50% of the sibling median? | divergence = clamp((|target_lines − median| − 0.5·median) / median, 0.0, 1.0) |
| 4. description_style | Does the description follow the same imperative-first-clause + trigger-list pattern as siblings? | divergence = 1.0 − (matching style markers / 3) where the markers are: starts with "Use this skill to" or "<verb>s" verb-leading clause; contains ≥3 trigger phrases; ≤1024 chars |

Axis-level rationale and edge cases would live at `references/divergence-axes.md` (deferred to v1.1; the table above is the authoritative spec for v1.0).

## Verdict semantics

- **All axes ≤ threshold (default 0.40)** → `verdict: green` (no notable divergence)
- **Any axis > threshold AND ≤ 0.70** → `verdict: yellow` (drift candidate; CEO reviews)
- **Any axis > 0.70** → `verdict: red` (likely drift seed; refuse to ship without explicit override)
- **Sibling count < 2** → `verdict: green`, `status: insufficient_siblings` (cannot judge a singleton domain)
- **Target SKILL.md unreadable** → `verdict: red`, `status: target_unreadable`

## Response shape

This is the JSON the subagent writes to `_meta-runtime/cousin-prompt-requests/cousin-prompt-response-<id>.json` (and the contract `bin/skill_factory.py emit_bundle_or_merge` parses on re-entry):

```json
{
  "verdict": "green | yellow | red",
  "summary": "<one-line human-readable verdict>",
  "status": "ok | insufficient_siblings | target_unreadable",
  "skill_path": "skills/_meta/skill-cousin-prompt/SKILL.md",
  "parent_domain": "skills/_meta/",
  "sibling_count": 19,
  "axes": {
    "section_parity":    {"divergence": 0.12, "detail": "12 of 14 modal H2s present"},
    "frontmatter_shape": {"divergence": 0.00, "detail": "exact match"},
    "body_length_band":  {"divergence": 0.18, "detail": "target=192 lines, sibling median=235, band=±50%"},
    "description_style": {"divergence": 0.33, "detail": "trigger-phrase count=2 (need 3); imperative clause OK"}
  },
  "max_divergence": 0.33,
  "threshold": 0.40,
  "recommendations": [
    "Add one more trigger phrase to the description (e.g., \"check sibling drift\")."
  ]
}
```

The factory's `emit_bundle_or_merge` carries `verdict`, `summary`, and every other top-level key into the merged step verdict's `evidence` block, so a CEO running `--dry-run` sees the divergence axes inline in the batch report.

## Anti-patterns

- **MUST NOT** invoke an LLM judge for any axis. The v5.16 deterministic-gate invariant is non-negotiable. If a future need genuinely requires semantic similarity, the path is a Tier-3 embedding cache under guardrails (see `references/storage-architecture.md` §Tier-3 + the explicit DEFERRED row at `data-storage-matrix.md` §"semantic-embedding-cache"), not an inline LLM call.
- **MUST NOT** mutate the target SKILL.md or sibling files. The skill is read-only; mutations belong to skill-improve / skill-create / skill-derive.
- **MUST NOT** treat sibling count == 1 as a divergence signal. A singleton domain is structurally fine; the green-with-`insufficient_siblings` exit handles this.
- **MUST NOT** widen the parent-domain glob beyond the skill's immediate parent directory. Comparing `skills/_meta/skill-cousin-prompt/` against `skills/core/hr/recruit/` is meaningless — different domains follow different conventions on purpose.
- Do not silently swallow "target unreadable" errors. A target that fails to parse is `verdict: red` + `status: target_unreadable`, not `verdict: green` + `status: ok`. Silent green on parse failure is the v5.17 silent-stub bug this remediation explicitly closes.

## Grounding

- **Deterministic-gate invariant.** Per `references/skill-authoring-standards.md` §v5.14 additions: *"v5.16 Non-Goal: 'No LLM judge at any gate.' Only Gate 11 (transcript review) uses a judge."* skill-cousin-prompt's four axes are all deterministic structural checks; no LLM call.

- **Sibling-observation precedent.** `skills/_meta/skill-spec/scripts/observe_siblings.py` already implements parent-domain sibling discovery for the Step 0 architect (see `bin/skill_factory.py` lines 200–220 in `step_0_architect`). The same discovery primitive is reused here; this skill builds on a proven pattern, not a new one.

- **Drift-seed framing.** From `references/skill-authoring-patterns.md` (the 9-pattern documentation rubric): a skill that scores well in absolute terms but ignores its domain's conventions becomes a template that future authors copy, fragmenting the catalog. The cousin-prompt step exists precisely to catch this before a draft enters the registry.

- **Loud-yellow discipline.** Per `bin/skill_factory.py` Phase 2 docstring (post-remediation): *"Deferred steps that have not been merged are loud yellow, never silent green."* A `verdict: red` from this skill therefore translates to a red factory verdict and blocks auto-ship; the CEO must explicitly override or fix the divergence before the draft moves forward.
