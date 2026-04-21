# Private T+1 consultation protocol

During any committee phase, a member may consult a specialist agent privately. The consultation is not visible to other committee members until the consulting member cites it in their next transcript message.

## When to consult

- The member encounters a technical question outside their expertise
- The member needs fresh research on a specific sub-topic
- The member wants a second opinion before committing to a position

## Consultation flow

### Initiation

The member writes a consultation request to `.meta/consultations/<iso-timestamp>.md`:

```markdown
---
requester: <agent-id>
consultant: <target-agent-name>
committee_id: <committee-id>
round: <current-round>
phase: <current-phase>
created_at: <iso-timestamp>
status: pending
---

# Consultation request

## Question
<specific question, scoped narrowly>

## Context
<relevant committee context — topic, current positions, specific challenge prompting this consultation>

## Constraints
- Response must be under 500 words
- Cite sources for factual claims
- Do not take a position on the committee topic — answer the specific question only
```

### Specialist response

The consulting member spawns a T+1 sub-agent (one level deeper in the hierarchy) with:
- The consultation request as its brief
- Read access to the project KB via `kb-search`
- Read access to the committee transcript (for context)
- No write access to the transcript (the specialist is not a committee member)

The specialist writes their response to the same consultation file:

```markdown
## Response

**answered_at:** <iso-timestamp>
**confidence:** <0.0-1.0>

<response body — concise, factual, cited>

**sources:**
- <source 1>
- <source 2>
```

Update the consultation file's `status` to `completed`.

### Citation in transcript

The consulting member reads the response and incorporates it into their next transcript message. Cite the consultation explicitly:

```markdown
**reasoning:** ... Based on a private consultation with kiho-researcher (see .meta/consultations/2026-04-11T14:30:00Z.md), the SOC2 compliance concern is resolved: Firebase obtained certification in March 2026. ...
```

Other members can request access to the consultation file if they want to verify the claim. The file is not secret — it is merely not broadcast to avoid noise in the transcript.

## Constraints

- **One consultation per phase per member.** A member may not spawn multiple consultations in a single phase. If more research is needed, wait for the next round's research phase.
- **Depth limit respected.** The T+1 sub-agent counts toward the depth cap (CEO → Leader → IC). If the member is already at depth 2, they cannot spawn a consultation. Instead, include the question in their transcript message and let the committee runner handle it.
- **No committee-topic positions.** The specialist answers the specific question. They do not express a preference on the committee's main topic.
- **Time budget.** Consultations must complete before the member's next phase message. If the specialist times out, the member proceeds without the consultation and notes "consultation pending" in their message.
