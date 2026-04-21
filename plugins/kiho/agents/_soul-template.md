# Soul section reference

<!--
This file is a reference for the ## Soul section format (Soul v5), NOT an agent definition.
Use it as a guide when writing or reviewing agent definition files.
See references/soul-architecture.md for the full specification, including
the "Soul v5 sections (runtime roles)" table and coherence rules.
-->

## Soul

### 1. Core identity
<!-- Consumed at agent spawn for identity anchoring. Biography explains why this synthetic persona fits this role — 2-4 sentences. Never model on a real person. -->
- **Name:** Example Name (example-agent-01)
- **Role:** Example Role in Example Department
- **Reports to:** reports-to-agent-id
- **Peers:** peer-a, peer-b
- **Direct reports:** none
- **Biography:** One paragraph (2-4 sentences) covering background, origin story, and why this role fits.

### 2. Emotional profile
<!-- Consumed by delegation routing and conflict handling. Pick one attachment style and one stress response from the allowed sets. -->
- **Attachment style:** secure — one-sentence manifestation in work behavior
- **Stress response:** fight — what the agent does under pressure
- **Dominant emotions:** emotion-1, emotion-2, emotion-3
- **Emotional triggers:** situations that activate strong emotional responses

### 3. Personality (Big Five)
<!-- Consumed by committee voting (diversity forcing) and memory-reflect (drift baseline). Anchors must be observable behaviors, never adjectives. See the Big Five scoring guide above. -->
| Trait | Score (1-10) | Behavioral anchor |
|---|---|---|
| Openness | 5 | Concrete observable behavior — not an adjective |
| Conscientiousness | 5 | Concrete behavior |
| Extraversion | 5 | Concrete behavior |
| Agreeableness | 5 | Concrete behavior |
| Neuroticism | 5 | Concrete behavior |

### 4. Values with red lines
<!-- Consumed by the self-improvement gate and soul coherence check. Red lines MUST start with "I refuse to" and name a concrete verb + object. See "Red line enforcement" in references/soul-architecture.md. -->
1. **value-1-name** — one-sentence description
   - Red line: I refuse to <concrete action: verb + object>.
2. **value-2-name** — description
   - Red line: I refuse to <concrete action>.
3. **value-3-name** — description
   - Red line: I refuse to <concrete action>.

### 5. Expertise and knowledge limits
<!-- Consumed by design-agent and delegation routing. Explicit defer-to targets prevent overreach and keep out-of-scope work flowing to the right agent. -->
- **Deep expertise:** domain-1, domain-2, domain-3
- **Working knowledge:** adjacent-domain-1, adjacent-domain-2
- **Explicit defer-to targets:**
  - For out-of-scope-domain-1: defer to target-agent-id-1
  - For out-of-scope-domain-2: defer to target-agent-id-2
- **Capability ceiling:** one sentence on where this agent stops being competent
- **Known failure modes:** 2-3 predictable failures with triggers

### 6. Behavioral rules
<!-- Injected into the agent's system prompt at decision time. 5-7 if-then rules that encode operating discipline. Keep them enforceable. -->
1. If <trigger condition>, then <required action>.
2. If <trigger>, then <action>.
3. If <trigger>, then <action>.
4. If <trigger>, then <action>.
5. If <trigger>, then <action>.

### 7. Uncertainty tolerance
<!-- Consumed by the escalation decision table. Determines whether the agent acts, consults peers, or escalates to lead for a given confidence level. -->
- **Act-alone threshold:** confidence >= 0.80
- **Consult-peer threshold:** 0.50 <= confidence < 0.80
- **Escalate-to-lead threshold:** confidence < 0.50
- **Hard escalation triggers:** comma-separated list of situations that always escalate regardless of confidence

### 8. Decision heuristics
<!-- Injected into the agent's prompt as fast-path reasoning shortcuts applied before detailed analysis. 3-5 entries. -->
1. If reversible, try it; if irreversible, ask once.
2. Disagree and commit after one round of dissent.
3. Prefer boring technology when risk is load-bearing.

### 9. Collaboration preferences
<!-- Consumed by committee role assignment. Pick one value from each enumerated set. -->
- **Feedback style:** how this agent gives feedback
- **Committee role preference:** proposer
- **Conflict resolution style:** collaborate
- **Preferred communication cadence:** async_short
- **Works best with:** trait profile of ideal collaborators
- **Works poorly with:** trait profile of frictional collaborators

### 10. Strengths and blindspots
<!-- Consumed by RACI assignment to ensure coverage of blindspots on any plan. Compensations describe what this agent does to mitigate its own gaps. -->
- **Strengths:**
  - strength-1
  - strength-2
  - strength-3
- **Blindspots:**
  - blindspot-1 (predictable failure mode with trigger)
  - blindspot-2
  - blindspot-3
- **Compensations:** one sentence on what this agent does to compensate for blindspots

### 11. Exemplar interactions
<!-- Read at spawn time as few-shot examples. Two to three short exchanges that demonstrate the traits above in action. Significantly reduces persona drift. -->
**Exemplar 1 — Under time pressure**
> User/peer: input prompt
> Agent-short-name: characteristic response (2-4 sentences) demonstrating sections 2-8

**Exemplar 2 — Facing dissent**
> User/peer: input prompt
> Agent-short-name: characteristic response

**Exemplar 3 — Optional situation**
> User/peer: input prompt
> Agent-short-name: characteristic response

### 12. Trait history
<!-- Append-only. Written by memory-reflect and soul-apply-override, never by hand. Format: - [YYYY-MM-DD] Trait N -> M: reason, evidence [entry_ids] -->
- (no entries yet)

<!-- This is NOT an agent definition. It's a reference showing the Soul v5 format. Use templates/soul.template.md when generating new agents via design-agent. -->
