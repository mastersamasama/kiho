# Capability gap resolution (design-agent Step 4d)

Detailed procedure for Step 4d. The SKILL.md body carries only the cascade overview + decision rule; this reference holds the per-class procedures, authority table, gate outcomes, and worked examples. Plugin-level canonical spec is at `references/capability-gap-resolution.md` (same-name shared reference loaded across multiple skills).

## Contents
- [Gap classification](#gap-classification)
- [Derivable → skill-derive](#derivable--skill-derive)
- [Researchable → routing decision (v5.11)](#researchable--routing-decision-v511)
- [MCP → CEO escalation](#mcp--ceo-escalation)
- [Unfillable → deficit record](#unfillable--deficit-record)
- [Security rules](#security-rules)
- [Authority boundaries](#authority-boundaries)
- [Gate outcomes](#gate-outcomes)

## Gap classification

Each gap gets classified into one of four buckets. Multiple gaps in a single candidate are handled independently.

| Class | Definition | Resolver |
|---|---|---|
| **Derivable** | Missing skill; CATALOG has a candidate parent with ≥ 2 overlapping topic tags | `skill-derive` |
| **Researchable** | Missing skill; no parent; trusted-source-registry has coverage OR caller has clear intent | `research-deep` + `skill-learn op=synthesize` OR `skill-create` direct |
| **MCP** | Missing tool, `mcp__`-prefixed, must be installed (not a markdown file) | escalate to CEO → user install approval |
| **Unfillable** | Missing skill; no parent; no trusted-source coverage; no MCP available | deployment deficit, revise soul to drop the dependency |

**Classification algorithm:**

```
for each gap g in {gaps from Step 4} + {gaps from Step 4b}:
    if g.type == "tool" and g.name starts with "mcp__":
        g.class = MCP
    elif g.type == "skill" and catalog_has_compatible_parent(g, CATALOG.md):
        g.class = Derivable
    elif g.type == "skill" and (trusted_sources_has_topic(g.topic_tags)
                                 or has_clear_intent(g)):
        g.class = Researchable
    elif g.type == "skill":
        g.class = Unfillable
    else:
        g.class = Unfillable
```

`catalog_has_compatible_parent` returns true if any active skill in CATALOG.md has ≥ 2 overlapping topic tags with the gap AND is not itself DRAFT.

`trusted_sources_has_topic` queries the trusted-source registry for sources tagged with any of the gap's topic tags. If empty, research-deep is unlikely to succeed and the cascade jumps to Unfillable.

`has_clear_intent` returns true if the gap description has explicit use cases and trigger phrases drawn from the consumer's Soul Section 6. This enables the skill-create direct sub-path without external doc traversal.

## Derivable → skill-derive

1. Identify the strongest candidate parent (highest tag overlap + highest use_count from `skill-invocations.jsonl`).
2. Invoke `skill-derive(parents=[<parent-id>], new_role=<gap-description>, requestor=design-agent)`.
3. On success, the DRAFT skill lands at `.kiho/state/drafts/sk-<slug>/`. Call `kb-add` with `lifecycle: draft, parent_of_derivation: <parent-id>`.
4. Add the new `sk-<slug>` to the candidate's `skills:` frontmatter.
5. Re-run Step 4. Pass → continue to Step 5. Fail → roll back to Step 2 with a note.

## Researchable → routing decision (v5.11)

Two sub-paths depending on whether external doc traversal is required:

**Sub-path A — research-deep + skill-learn op=synthesize:** when external docs exist and must be crawled to build the skill content (e.g., "Playwright visual regression" — the content lives in playwright.dev and must be extracted).

**Sub-path B — skill-create direct:** when the skill is a well-known pattern with clear intent, trigger phrases, and use cases, AND no external doc traversal is needed (e.g., the consumer agent's Soul already describes the pattern in Section 6, or the caller has explicit intent from a brief).

### Decision rule

```
if requirements.has_clear_intent AND requirements.has_use_cases
   AND requirements.trigger_phrases.length >= 3
   AND NOT trusted_source_registry.requires_external_docs_for_topic(gap):
    use sub-path B (skill-create direct)
else:
    use sub-path A (research-deep + synthesize)
```

| Signal | Sub-path |
|---|---|
| Gap topic has trusted-source registry coverage (playwright.dev, react.dev, ...) | A (research-deep) |
| Gap topic requires external best-practice synthesis from authoritative docs | A |
| Gap is a well-known orchestration pattern with clear intent in the consuming agent's soul | B (skill-create) |
| Gap is a procedural pattern with explicit use cases in the brief | B |
| Caller is kiho-ceo or a dept lead with an explicit brief | B |
| No clear intent + no registry coverage | **Unfillable** (both sub-paths require inputs) |

### Sub-path A procedure

1. Query the trusted-source registry: `kb-search` for entities with `topic_tags_any: [<gap tags>]`, `trust_level_in: [official, community]`, `source_type_in: [api-docs, best-practices]`. Sort by trust DESC, success_count DESC.
2. Take the top 1–3 URLs as seeds. If the registry is empty for this topic, **reclassify as Unfillable** (do NOT fall back to sub-path B — that requires explicit intent, not blind guessing).
3. Invoke `research-deep` with:
   ```
   topic:         <gap description>
   seed_urls:     [<from step 2>]
   role_context:  <candidate's role + goal from Step 0>
   budget_pages:  50 (or per-topic override from trusted-source entry)
   budget_depth:  3
   budget_min:    15
   auth_mode:     ask
   requestor:     design-agent
   ```
4. research-deep runs BFS link-graph traversal per `references/deep-research-protocol.md` and produces a living skeleton at `.kiho/state/skill-skeletons/<slug>.md`.
5. **If research-deep returns `escalate_to_user: auth-needed`** → bubble the escalation up through design-agent's return. CEO handles it (Playwright interactive login). After approval + cookie capture, design-agent re-runs Step 4d from the beginning with the credential now in OS keychain.
6. **If research-deep returns `status: ok | partial`** → invoke `skill-learn op=synthesize`:
   ```
   op:                    synthesize
   skeleton_path:         <from research-deep response>
   topic:                 <gap>
   role_context:          <same>
   source_urls:           <from skeleton Sources>
   trusted_sources_used:  <from research-deep response>
   ```
7. synthesize produces a DRAFT skill at `.kiho/state/drafts/sk-<slug>/`. It always writes DRAFT. Dedup check runs first — if duplicate, use the existing skill.
8. Call `kb-add` with `lifecycle: draft, synthesized_from_research: true, source_urls: [...]`.
9. Add `sk-<slug>` to candidate's `skills:` frontmatter.
10. Re-run Step 4. Pass → continue. Fail → roll back to Step 2.

### Sub-path B procedure

1. Extract the skill intent from the gap description + candidate's soul (specifically Section 6 Behavioral rules that referenced the missing skill). Derive:
   - `intent`: one-line phrase from the failing rule
   - `domain`: inferred from the candidate's department
   - `consumer_agents`: [<candidate-name>]
   - `trigger_phrases`: 3+ phrases drawn from the behavioral rule + use cases in the soul
   - `use_cases`: derived from the candidate's responsibilities section
   - `scripts_needed` / `references_needed`: inferred from complexity
2. Invoke `skill-create` with the extracted inputs.
3. On `status: ok`, the new DRAFT skill lands at `.kiho/state/drafts/sk-<slug>/SKILL.md` with:
   - Full 10-gate validation already passed (skill-create enforces them)
   - Eval suite already generated
   - `kb-add` already called
4. Add `sk-<slug>` to candidate's `skills:` frontmatter.
5. Re-run Step 4 and Step 4b. Pass → continue. Fail → roll back to Step 2.

**Failure handling:**
- `status: duplicate` → use the existing skill instead; update candidate's `skills:` list with the existing ID.
- `status: description_irrecoverable` → the intent was too vague; roll back to Step 2 with a note to sharpen the rule that surfaced the gap, OR reclassify to Unfillable.
- `status: security_blocked` → the drafted skill triggered the Lethal Trifecta; escalate to CEO with the risk tier.
- `status: revision_limit_exceeded` → abort design-agent with full gate failure trace.

## MCP → CEO escalation

1. Invoke `research` (short cascade, `max_steps: 2`) with query `"<mcp-name> MCP server manifest installation"`.
2. Fetch the manifest. Extract: package name, version, permissions declared, signature, publisher, install command, required config keys.
3. Return `escalate_to_user` from design-agent with:
   ```json
   {
     "status": "escalate_to_user",
     "reason": "install-mcp",
     "mcp_name": "<mcp-name>",
     "manifest_url": "<url>",
     "publisher": "<org>",
     "permissions_claimed": ["<perm>", ...],
     "signature": "<ed25519:... or null>",
     "risk_tier": "low | medium | high",
     "install_command": "<command>",
     "rationale": "Required by <candidate-name> for <purpose>. Current gap on Step 4b.",
     "alternatives": ["<alt 1>", "<alt 2>"]
   }
   ```
4. CEO handles the escalation via `AskUserQuestion` with options: Install (user runs the command, then re-invokes `/kiho`) / Use alternative / Defer. **Kiho never runs the install command itself.**
5. If the user installs and re-invokes, design-agent re-runs from Step 0. Step 4b now passes; continue normally.
6. If the user picks an alternative or defers, the candidate brief is revised accordingly and design-agent re-runs from Step 0 with the adjusted scope.

## Unfillable → deficit record

1. Append an entry to `.kiho/agents/<candidate-name>/deployment-notes.md`:
   ```markdown
   ## Known capability deficit (<iso-date>)
   - Missing: <gap description>
   - Reason: <no parent / no trusted source / no MCP>
   - Consequence: <what the agent cannot do>
   - Escalation: run `/kiho evolve <topic>` when the ecosystem catches up
   ```
2. Return to Step 2 with instructions to revise the soul: remove rules that reference the missing capability AND narrow the role goal so it doesn't advertise the missing capability.
3. Record `design_score.deficits: [<gap>]` in frontmatter so the deployment audit trail is explicit.
4. Continue to Step 5.

## Security rules

These rules are non-negotiable. Full spec in the plugin-level `references/capability-gap-resolution.md` §"Security rules".

1. **No auto-install, ever.** Kiho does not touch the user's MCP config. Every MCP install goes through CEO → user.
2. **Synthesized skills start DRAFT.** Never ACTIVE from op=synthesize. Promotion requires interview-simulate pass on the consuming agent + CEO committee approval.
3. **Manifest review before install prompts.** The escalation payload must include the fetched manifest; blind "install X" prompts to the user are forbidden.
4. **No credentials in KB or state files.** OS keychain only for auth cookies.
5. **First-run sandbox validation.** On first use of a newly-installed MCP, `interview-simulate(mode: light)` validates the tool actually works as declared. Failing first-run flags the MCP as `trust_level: unverified`.

## Authority boundaries

| Action | design-agent | CEO | User |
|---|---|---|---|
| Classify gap | ✓ | — | — |
| Call `skill-derive` | ✓ | — | — |
| Call `research-deep` | ✓ | — | — |
| Call `skill-create` | ✓ | — | — |
| Call `skill-learn op=synthesize` | ✓ | — | — |
| `kb-add` DRAFT skill | ✓ (via kb-manager) | — | — |
| Promote DRAFT → ACTIVE | — | ✓ (committee gate) | — |
| Call `AskUserQuestion` | — | ✓ | — |
| Fetch MCP manifest | ✓ (via research) | — | — |
| Run MCP install command | — | — | ✓ |
| Approve auth escalation | — | ✓ (proposes) | ✓ (approves) |

**Hard rule:** design-agent never calls `AskUserQuestion` directly (CEO-only invariant). All user prompts go through `escalate_to_user` structured returns that CEO converts into questions.

## Gate outcomes

| Status | Meaning | Next action |
|---|---|---|
| `gap_resolved` | All gaps closed; Step 4 / 4b re-run passes | continue to Step 5 |
| `gap_deferred_draft` | Gaps closed via DRAFT skills; candidate continues; Step 7 validates DRAFTs on the candidate | continue to Step 5 |
| `gap_deferred_mcp` | At least one gap requires CEO escalation | abort design-agent, return `escalate_to_user` |
| `gap_unfillable` | Gap cannot be resolved; soul revised to drop the dependency | continue to Step 5 with `design_score.deficits` recorded |
| `gap_recursive_fail` | Resolution produced a skill that still fails Step 4 or Step 4b | abort with `revision_limit_exceeded`; escalate |
