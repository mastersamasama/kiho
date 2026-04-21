# Chat format specification for transcript.md

Every committee message in `transcript.md` follows this exact format. The transcript is append-only; no edits or deletions.

## Contents
- [Message header](#message-header)
- [Message fields](#message-fields)
- [Complete example](#complete-example)
- [Parsing rules](#parsing-rules)

## Message header

```markdown
## [<agent_name>-<agent_id>] <ISO-8601-UTC>
```

- `agent_name`: the agent's name from its frontmatter (e.g., `kiho-eng-lead`)
- `agent_id`: unique instance id for this committee run (e.g., `eng-01`)
- Timestamp: full ISO-8601 in UTC with seconds (e.g., `2026-04-11T14:22:33Z`)

Example:
```markdown
## [kiho-eng-lead-eng-01] 2026-04-11T14:22:33Z
```

## Message fields

Every message body contains these fields in order. All fields are required; use `null` or `[]` for empty values.

```markdown
**message_id:** <committee_id>-R<round>-P<phase>-<agent_id>
**phase:** research | suggest | combine | challenge | choose
**position:** <one-sentence position or null for research phase>
**confidence:** <0.00-1.00 or null for research phase>
**reasoning:** <2-5 sentences>
**sources:** <bulleted list of KB page IDs, URLs, or file paths>
**challenges:** <structured challenge list or empty>
**resolved:** <structured resolved list or empty>
```

### Field details

**message_id** — unique across the entire committee. Pattern: `{committee_id}-R{round}-P{phase_num}-{agent_id}`.
- Phase numbers: research=1, suggest=2, combine=3, challenge=4, choose=5

**phase** — one of the five phase keywords, lowercase.

**position** — a single declarative sentence. Not a question. Not "it depends." For the research phase, set to `null`.

**confidence** — float between 0.00 and 1.00 inclusive. For the research phase, set to `null`. Calibrate conservatively per the rules in `references/round-phases.md`.

**reasoning** — 2-5 sentences explaining the position or research findings. Cite sources inline with `[[page-id]]` wikilinks or `[label](url)` links.

**sources** — bulleted markdown list. Each entry is a KB page ID, external URL, or relative file path. Minimum one source for research and suggest phases.

**challenges** — for the challenge phase, a structured list:
```markdown
**challenges:**
- `ch-1-1`: [blocking] Targets "Use Firebase Auth" — Firebase has no SOC2 compliance cert for our region
- `ch-1-2`: [significant] Targets "Use Firebase Auth" — vendor lock-in risk with Google ecosystem
```
For other phases, empty: `**challenges:** []`

**resolved** — for combine and choose phases, references to prior challenges that are now addressed:
```markdown
**resolved:**
- `ch-1-1`: Firebase obtained SOC2 Type II in March 2026, confirmed via [[entity-firebase-compliance]]
```
For other phases, empty: `**resolved:** []`

## Complete example

```markdown
# Transcript — 2026-04-11-auth-provider

## [kiho-eng-lead-eng-01] 2026-04-11T14:22:33Z

**message_id:** auth-provider-R1-P1-eng-01
**phase:** research
**position:** null
**confidence:** null
**reasoning:** Reviewed existing KB entries on authentication. Found [[concept-auth-patterns]] covering OAuth2 and SAML flows. Found [[entity-firebase]] and [[entity-auth0]] as previously evaluated providers. No prior decision on SSO provider exists. External research shows Firebase Auth and Auth0 as top contenders for our stack (Next.js + Node).
**sources:**
- [[concept-auth-patterns]]
- [[entity-firebase]]
- [[entity-auth0]]
- https://firebase.google.com/docs/auth
**challenges:** []
**resolved:** []

## [kiho-pm-lead-pm-01] 2026-04-11T14:23:15Z

**message_id:** auth-provider-R1-P1-pm-01
**phase:** research
**position:** null
**confidence:** null
**reasoning:** User requirements from the PRD specify SSO for enterprise customers. Key criteria: SAML support, custom domain branding, audit logging. Reviewed [[entity-user-research-sso]] showing 78% of target customers use SAML. Auth0 has a stronger enterprise feature set per their docs. Firebase Auth is simpler but enterprise features require Identity Platform upgrade.
**sources:**
- [[entity-user-research-sso]]
- https://auth0.com/docs/authenticate/protocols/saml
**challenges:** []
**resolved:** []

## [kiho-eng-lead-eng-01] 2026-04-11T14:25:00Z

**message_id:** auth-provider-R1-P2-eng-01
**phase:** suggest
**position:** Use Auth0 as the SSO provider for the enterprise authentication feature.
**confidence:** 0.72
**reasoning:** Auth0 has native SAML support, custom domain branding, and audit logging out of the box. Firebase Auth requires the paid Identity Platform tier for equivalent features. Auth0's SDK integrates cleanly with Next.js via nextjs-auth0. The cost difference is manageable at our projected user count (< 10k enterprise seats).
**sources:**
- [[entity-auth0]]
- https://github.com/auth0/nextjs-auth0
**challenges:** []
**resolved:** []
```

## Parsing rules

When the clerk extracts decisions from the transcript:

1. Split on `## [` to get individual messages
2. Parse the header for agent name, agent id, and timestamp
3. Parse each `**field:**` line as a key-value pair
4. Group messages by round (R-number in message_id) and phase (P-number)
5. Within each round, validate that all members posted exactly once per phase
6. Extract final positions from choose-phase messages of the last round
7. Compute aggregate confidence as the mean of all choose-phase confidence values

Messages that fail to parse (missing fields, malformed ids) are flagged but not discarded. The clerk notes parsing errors in the decision.md preamble.
