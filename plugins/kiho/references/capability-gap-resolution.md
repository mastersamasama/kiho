# Capability gap resolution (Step 4d of design-agent)

When `design-agent` is drafting a candidate agent and discovers it needs a capability — a skill, a tool, or an MCP server — that doesn't exist in the current catalog, this reference defines the cascade that closes the gap before the candidate is deployed.

## Contents
- [Why this step exists](#why-this-step-exists)
- [Trigger conditions](#trigger-conditions)
- [Gap classification](#gap-classification)
- [Resolution cascade](#resolution-cascade)
- [Security rules](#security-rules)
- [Authority boundaries](#authority-boundaries)
- [Failure modes](#failure-modes)
- [Worked examples](#worked-examples)
- [Anti-patterns](#anti-patterns)

## Why this step exists

Prior to v5.10, when `design-agent` Step 4 (soul-skill alignment) or Step 4b (tool allowlist validation) hit a missing capability, the only resolution was "prune the rule that references it and try again." The deployed agent silently lost the best-practice capability. A frontend-qa candidate that *should* do Playwright visual regression would ship without any visual-regression skill because there was no `sk-playwright-*` in the catalog.

Research (Voyager, Hermes, OWASP Agentic Skills Top 10) converges on a simple rule: **when the pipeline detects a capability gap at design time, either resolve it through a gated synthesis workflow or escalate — never silently downgrade.**

## Trigger conditions

Step 4d activates when EITHER of the following is true after Step 4c completes:

1. **Skill gap** — Step 4 (soul-skill alignment) reported one or more `missing required skills` with `alignment_score < 0.70`, AND the role description strongly implies those skills are best-practice for the role (e.g., "frontend QA" + "visual regression" → `sk-playwright-visual-regression` is a required skill).
2. **Tool/MCP gap** — Step 4b (tool allowlist validation) reported one or more behavioral rules that reference tools outside the current Claude Code environment's tool set, AND the candidate couldn't be reworked to avoid the tool without dropping a core responsibility.

Step 4d does NOT run when:
- The gap can be silently pruned because the rule was aspirational, not load-bearing.
- The gap already has a DRAFT resolution from a prior run (see "idempotency" in [Resolution cascade](#resolution-cascade)).

## Gap classification

Each gap gets classified into one of four buckets. Multiple gaps in a single candidate are handled independently.

| Class | Definition | Resolver |
|---|---|---|
| **Derivable** | Gap is a missing skill, and CATALOG.md has at least one candidate parent skill that could be specialized via `skill-derive` | `skill-derive` (design-agent authority) |
| **Researchable** | Gap is a missing skill with no parent in CATALOG. Best practices are documented publicly. | `research-deep` → `skill-learn op=synthesize` (design-agent authority, DRAFT lifecycle) |
| **MCP** | Gap is a tool/MCP that must be installed (not a markdown file). Not fillable by skill synthesis. | CEO escalation → user install approval |
| **Unfillable** | No research hit, no parent, no MCP exists. Capability is genuinely absent from the ecosystem. | Document as known deficit; revise soul to not depend on it |

**Classification algorithm:**

```
for each gap g in {gaps from Step 4} + {gaps from Step 4b}:
    if g.type == "tool" and g.name starts with "mcp__":
        g.class = MCP
    elif g.type == "skill" and catalog_has_compatible_parent(g, CATALOG.md):
        g.class = Derivable
    elif g.type == "skill" and trusted_sources_has_topic(g.topic_tags):
        g.class = Researchable
    elif g.type == "skill":
        g.class = Unfillable   # no parent, no trusted source
    else:
        g.class = Unfillable   # fall-through
```

`catalog_has_compatible_parent` returns true if any active skill in CATALOG.md has ≥ 2 overlapping topic tags with the gap AND is not itself DRAFT.

`trusted_sources_has_topic` queries the trusted-source registry for sources tagged with any of the gap's topic tags. This is the early-exit heuristic — if no trusted source covers the topic, research-deep is unlikely to succeed and we jump to Unfillable.

## Resolution cascade

### Derivable → skill-derive

1. Identify the strongest candidate parent (highest tag overlap + highest use_count from skill-invocations.jsonl).
2. Invoke `skill-derive(parents=[<parent-id>], new_role=<gap-description>, requestor=design-agent)`.
3. On success, a DRAFT skill lands at `.kiho/state/drafts/sk-<slug>/`. Call `kb-add` to register it with `lifecycle: draft, parent_of_derivation: <parent-id>`.
4. Add the new `sk-<slug>` to the candidate's `skills:` frontmatter.
5. Re-run Step 4 — alignment_score should now clear the gate. If not, roll back to Step 2 of design-agent with a note.

### Researchable → research-deep + skill-learn op=synthesize

1. Query the trusted-source registry for sources tagged with the gap's topic tags, `trust_level in [official, community]`, `source_type in [api-docs, best-practices]`. Sort by trust_level DESC, success_count DESC.
2. Take the top 1–3 URLs as seed URLs.
3. Invoke `research-deep(topic=<gap>, seed_urls=[...], role_context=<candidate's role+goal from Step 0>, budget_pages=50, budget_depth=3, budget_min=10)`.
4. research-deep runs the BFS link-graph traversal documented in `deep-research-protocol.md`. It produces:
   - A living skill-skeleton at `.kiho/state/skill-skeletons/sk-<slug>.md`
   - A state log at `.kiho/state/research-queue/<topic-slug>.jsonl`
   - A final "consolidation" marker when BFS terminates
5. On consolidation, invoke `skill-learn op=synthesize(skeleton_path=<path>, topic=<gap>, lifecycle=draft)`. synthesize reads the skeleton, finalizes it into canonical SKILL.md structure, runs dedup against CATALOG, and writes to `.kiho/state/drafts/sk-<slug>/`.
6. Call `kb-add` with `lifecycle: draft, synthesized_from_research: true, source_urls: [...]`.
7. Add `sk-<slug>` to candidate's `skills:` frontmatter.
8. Re-run Step 4. If the gate still fails, roll back to Step 2.

**Failure handling in this path:**
- If research-deep escalates `auth-needed` (seed URL requires login) → bubble up to CEO (see Authority boundaries)
- If research-deep exhausts budget without meeting novelty-termination → partial skeleton; mark the DRAFT as `speculative: true` and continue (still goes through Step 7 interview-simulate, which will catch an incomplete skill)
- If all seed URLs fail (404, blocked, stale) → reclassify the gap as Unfillable

### MCP → CEO escalation

1. Invoke `research` (short cascade, max_steps=2) with query `"<mcp-name> MCP server manifest installation"`. Goal: find the manifest URL and install command.
2. Fetch the manifest (WebFetch or trusted `mcp-registry` source).
3. Extract: package name, version, permissions declared, signature (if any), publisher, install command, required config keys.
4. Return `escalate_to_user` to design-agent's caller (usually recruit or HR):
   ```json
   {
     "status": "escalate_to_user",
     "reason": "install-mcp",
     "mcp_name": "mcp__playwright__visual-regression",
     "manifest_url": "https://...",
     "publisher": "microsoft",
     "permissions_claimed": ["browser-control", "filesystem:read", "network"],
     "risk_tier": "medium",
     "install_command": "claude-code mcp install <package>",
     "rationale": "Required by <candidate-name> for visual regression testing. Current gap on Step 4b.",
     "alternatives": ["skip visual regression coverage and adjust role scope", "use a non-MCP Python playwright skill with Bash tool"]
   }
   ```
5. The CEO receives the escalation, dedupes with any pending questions, and calls `AskUserQuestion` with three options: install / use alternative / defer.
6. If the user approves install, the CEO surfaces the install command to the user for them to run (kiho never touches the user's global MCP config itself). Then the user re-invokes `/kiho` and design-agent re-runs Step 4b, which now passes.
7. If the user picks an alternative or defers, the CEO revises the candidate brief accordingly and re-runs design-agent from Step 0 with the adjusted scope.

### Unfillable → deficit record

1. Add an entry to `.kiho/agents/<candidate-name>/deployment-notes.md`:
   ```markdown
   ## Known capability deficit (<iso-date>)
   - Missing capability: <gap description>
   - Reason unresolved: no parent skill + no trusted source coverage OR no MCP available OR <other>
   - Consequence: <what the agent cannot do because of this>
   - Escalation: recommend `/kiho evolve <topic>` when the ecosystem catches up
   ```
2. Return to Step 2 of design-agent with instructions to revise the soul's Section 6 (Behavioral rules) to remove rules that reference the missing capability, and Section 1 (Core identity + goal) to narrow the role so it doesn't advertise the missing capability.
3. Mark the candidate with frontmatter `design_score.deficits: [<gap>]` so the deployment audit trail is clear.
4. Continue to Step 5.

## Security rules

These rules are **non-negotiable** and apply regardless of confidence:

1. **No auto-install, ever.** Kiho does not modify the user's global MCP config, `package.json`, `.mcp.json`, or any other install surface. MCP install decisions always go through CEO → user.
2. **Synthesized skills start DRAFT.** Never ACTIVE from synthesis alone. DRAFT → ACTIVE requires CEO approval after an interview-simulate pass on a consuming agent.
3. **Manifest review before install.** For MCP escalations, design-agent must fetch and include the manifest in the escalation payload. Blind "install X" prompts to the user are forbidden.
4. **No credentials in KB.** If `research-deep` needs auth to a doc, credentials go through OS keychain via the auth-helper primitive. Never store in trusted-source-registry, never in KB entity pages.
5. **Signature verification when available.** For signed MCPs, the escalation payload records the signature and publisher. Unsigned MCPs are flagged `risk_tier: high` and the user prompt emphasizes the risk.
6. **Sandbox first-run.** Even after user approval, the first time an MCP is used by a kiho-created agent, interview-simulate runs in mode=light to validate the tool actually works as declared. A failing first-run flags the MCP as `trust_level: unverified` in the registry.
7. **Never auto-retry on escalation timeout.** If the user hasn't responded to an install/auth escalation in one Ralph-loop turn, the candidate is shelved (deployment-notes.md gets the pending escalation) and design-agent returns. No silent fallback to a less-safe path.

## Authority boundaries

Who can do what at each step of the cascade:

| Action | design-agent | CEO | User |
|---|---|---|---|
| Classify gap | ✓ | — | — |
| Call `skill-derive` | ✓ | — | — |
| Call `research-deep` | ✓ | — | — |
| Call `skill-learn op=synthesize` | ✓ | — | — |
| `kb-add` DRAFT skill | ✓ (via kb-manager) | — | — |
| Promote DRAFT → ACTIVE | — | ✓ (self-improvement committee) | — |
| Call `AskUserQuestion` | — | ✓ | — |
| Fetch MCP manifest | ✓ (via research skill) | — | — |
| Run MCP install command | — | — | ✓ |
| Approve signed auto-install | — | — | ✓ (future; currently always manual) |
| Decide auth scope for research-deep | — | ✓ (proposes) | ✓ (approves) |
| Promote trusted-source to `official` | — | ✓ | — |
| Block a trusted source | — | ✓ | — |

**Hard rule:** design-agent never calls `AskUserQuestion` directly (CEO-only invariant). All user prompts go through `escalate_to_user` structured returns that CEO converts into questions.

## Failure modes

| Status | Meaning | Next action |
|---|---|---|
| `gap_resolved` | All gaps closed; re-running Step 4 passes | continue pipeline to Step 5 |
| `gap_deferred_draft` | At least one gap resolved to DRAFT; candidate continues but carries the DRAFT dependency | continue; Step 7 interview-simulate validates the DRAFT on the candidate |
| `gap_deferred_mcp` | At least one gap requires CEO escalation; candidate is shelved | return `status: escalate_to_user` with the escalation payload |
| `gap_unfillable` | At least one gap cannot be resolved at all | revise soul to drop the dependency, continue with `design_score.deficits` recorded |
| `gap_recursive_fail` | Resolution produced a skill/tool that still fails Step 4 or Step 4b | abort design-agent with `revision_limit_exceeded`; escalate the full gap analysis |

## Worked examples

### Example 1 — frontend-qa needs Playwright visual regression

**Gap detected at Step 4:** `sk-playwright-visual-regression` required by rule "If a UI PR lacks visual-regression coverage, then block merge and run baseline diff" but missing from CATALOG.

**Classification:** Researchable (no parent `sk-playwright-*` in catalog, but trusted-source registry has `playwright-dev` with topic_tags including `visual-regression`).

**Resolution path:**
1. kb-search trusted-sources → returns `playwright-dev` (official, success_count: 12) and `storybook-official` (official, success_count: 5) as seed candidates.
2. research-deep invoked with seed `[https://playwright.dev/docs/test-snapshots, https://storybook.js.org/docs/writing-tests/visual-testing]`, budget_pages: 50, budget_depth: 3, role_context: "frontend-qa IC doing UI visual regression".
3. research-deep BFS traversal reads 27 pages before content-novelty termination (last 3 pages added zero new concepts). Living skeleton covers: snapshot baselines, update workflow, threshold tuning, CI integration, diff review, flakiness mitigation.
4. skill-learn op=synthesize finalizes the skeleton into `sk-playwright-visual-regression` DRAFT. Dedup clear. kb-add registers it.
5. Candidate's `skills:` list updated. Step 4 re-run → passes (alignment_score 0.78, up from 0.52).
6. Step 7 interview-simulate runs with the new DRAFT skill. Candidate successfully uses the skill in the test case. Rubric pass.
7. Step 9 deploy. Step 10 register.
8. After Step 10, the CEO self-improvement committee is notified that a new DRAFT skill is in circulation. On the next turn's INITIALIZE, CEO reviews the DRAFT + interview-simulate transcript and promotes DRAFT → ACTIVE via the self-improvement gate.

### Example 2 — frontend-qa needs Vercel browser MCP

**Gap detected at Step 4b:** rule "If a rendering issue requires DOM inspection during CI, then use Vercel browser MCP to grab a snapshot" but `mcp__vercel_browser__*` not in the current tool set.

**Classification:** MCP (mcp__-prefixed tool, not a skill file).

**Resolution path:**
1. research (short, max_steps=2) for "vercel browser MCP manifest install". Returns the official manifest URL from the MCP registry.
2. Manifest fetched: publisher `vercel`, permissions `browser-control, network, filesystem:read`, signed `ed25519:...`, install command `claude-code mcp install vercel-browser@latest`.
3. design-agent returns `escalate_to_user: install-mcp` payload to recruit.
4. Recruit bubbles to CEO. CEO dedupes (no pending install questions), calls `AskUserQuestion`:
   - "design-agent is drafting a `frontend-qa-ic` candidate and needs `mcp__vercel_browser__*` for CI DOM inspection. The MCP is from Vercel (signed ed25519), declares browser-control + network + filesystem-read. Install command: `claude-code mcp install vercel-browser@latest`. Options: Install (you run the command, then re-invoke /kiho), Alternative (drop CI DOM inspection and use Bash + playwright headless instead), Defer (continue without this capability this turn)."
5. User picks Install, runs the command, re-invokes /kiho.
6. design-agent re-runs from Step 0. Step 4b passes. Continue normally.

### Example 3 — gap on an obscure domain

**Gap detected:** rule "verify via `sk-exotic-hardware-bus-probe`" — no parent, no trusted source, no MCP.

**Classification:** Unfillable.

**Resolution path:**
1. kb-search trusted-sources → empty.
2. Try research (short cascade) to see if any trusted source *could* be added → web search returns only low-quality forum posts. No authoritative doc exists.
3. Write deployment-notes.md with the deficit.
4. Return to Step 2. Revise soul: drop the rule, narrow the role goal (e.g., from "hardware QA" to "software QA"), record `design_score.deficits: ["exotic-hardware-bus-probe: no ecosystem coverage"]`.
5. Continue to Step 5. Candidate deploys without the capability.

## Anti-patterns

- **Silently pruning rules when a skill is missing.** The whole point of Step 4d is to not do this. If you're tempted to drop a rule to make Step 4 pass, classify the gap instead.
- **Auto-promoting DRAFT skills to ACTIVE when they pass Step 7.** Step 7 passes validate the skill works for ONE candidate. Promotion to ACTIVE means it's available to all agents — that's a CEO decision, not design-agent's.
- **Shipping a candidate with an unresolved gap.** `gap_deferred_mcp` and `gap_recursive_fail` must never result in a deployed agent. Either shelve the candidate or revise the scope.
- **Using `design-agent.escalate_to_user` for non-install/non-auth reasons.** The escalation surface is narrow by design. Other issues should route through the normal revision loop.
- **Calling `research-deep` with zero seed URLs.** Always query trusted-sources first. A cold-start research-deep run is budget-expensive and often low-quality.
- **Re-running the cascade after a user "defer".** If the user deferred, that is the final answer for this turn. Do not loop.
- **Writing auth credentials into trusted-source-registry entries.** Credentials live in OS keychain only. The registry records the auth METHOD, never the value.
