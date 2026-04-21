# Clerk extraction protocol

The clerk is a neutral agent that extracts structured decisions from committee transcripts. This protocol runs after a committee closes (consensus reached) or escalates (max rounds exhausted).

## Contents
- [Trigger conditions](#trigger-conditions)
- [Extraction pipeline](#extraction-pipeline)
- [Decision document (MADR)](#decision-document-madr)
- [Dissent document](#dissent-document)
- [KB integration](#kb-integration)
- [Edge cases](#edge-cases)

## Trigger conditions

Run this protocol when:
- All members have posted their choose-phase messages for a round AND the close rule is met (unanimous + no unresolved challenges + aggregate confidence >= 0.90)
- OR the committee has completed round 3 without consensus (escalation)

The convening leader or committee runner invokes the clerk. If the convening leader has a stake in the outcome, spawn `kiho-clerk` as a separate agent to ensure neutrality.

## Extraction pipeline

### Parse messages

1. Read `transcript.md` in its entirety
2. Split on `## [` headers to isolate individual messages
3. For each message, extract:
   - `agent_name`, `agent_id` from the header
   - `timestamp` from the header
   - All structured fields: `message_id`, `phase`, `position`, `confidence`, `reasoning`, `sources`, `challenges`, `resolved`
4. Build a structured array of messages sorted by timestamp

### Cluster positions

5. From the final round's choose-phase messages, extract all unique positions
6. Group members by position (exact string match first, then semantic similarity for near-matches)
7. For each position cluster, compute:
   - `supporters`: list of agent ids
   - `aggregate_confidence`: mean of supporters' confidence values
   - `support_ratio`: number of supporters / total members

### Identify winner and dissent

8. The **winning position** is the cluster with the highest `support_ratio`. Ties break by `aggregate_confidence`.
9. All other clusters are **dissent positions**.
10. For consensus committees (close rule met), there is exactly one cluster with support_ratio = 1.0 and zero dissent.
11. For escalated committees, there may be multiple clusters.

### Collect challenge summary

12. Scan all challenge-phase messages across all rounds
13. Partition into resolved and unresolved challenges
14. For each unresolved challenge, note the severity and target position

## Decision document (MADR)

Write `decision.md` using `templates/decision.template.md`. Fill in:

```markdown
---
decision_id: ADR-<auto>-<slug>
committee_id: <from index.md>
status: accepted | proposed
date: <close timestamp>
decision_makers: [<agent-ids>]
---

# <topic as a decision title>

## Context and problem statement
<Derived from the committee topic and research-phase messages. 2-3 sentences.>

## Decision drivers
<Bulleted list extracted from research and suggest phases — the key factors that influenced the decision.>

## Considered options
<For each unique position that appeared in any suggest phase across all rounds:>
### Option N: <position statement>
- **Supporters:** <agents who held this position>
- **Confidence:** <their aggregate confidence>
- **Pros:** <from suggest/combine reasoning>
- **Cons:** <from challenge messages targeting this option>

## Decision outcome
Chosen option: "<winning position>"

Confidence: <aggregate confidence of winners>
Support: <N/N members> (unanimous | majority)

### Consequences
**Positive:**
- <derived from winning position's reasoning>

**Negative:**
- <derived from challenges against the winning position that were accepted as trade-offs>

**Risks:**
- <unresolved minor challenges>

## Links
- Committee transcript: `<relative path to transcript.md>`
- Dissent report: `<relative path to dissent.md or "none">`
- Related KB pages: <wikilinks to pages cited in sources>
```

## Dissent document

Write `dissent.md` only if minority positions exist (i.e., the committee escalated or had dissent in intermediate rounds worth recording). Use `templates/dissent.template.md`.

For each minority position:
```markdown
### Position: <statement>
- **Supporters:** <agent-ids>
- **Final confidence:** <aggregate>
- **Core rationale:** <2-3 sentences from their choose-phase reasoning>
- **Key evidence:** <sources they cited>
- **Why overruled:** <specific challenges that undermined this position, or lack of support>
```

## KB integration

If the committee's `knowledge_update` field is `true`:

1. Call `kb-add` with:
   - `page_type: decision`
   - `title`: the decision title from `decision.md`
   - `content`: the full `decision.md` body
   - `confidence`: the winning position's aggregate confidence
   - `sources`: all sources cited in the winning position's reasoning
   - `author_agent`: `kiho-clerk` (or the convening leader if acting as clerk)
   - `tags`: extracted from the topic keywords

2. If `kb-add` returns `status: conflict` (the decision contradicts an existing KB entry), note the contradiction in the committee response and include it in the escalation to CEO.

3. If `kb-add` returns `status: ok`, record the new page ID in the committee's `index.md` under `kb_page_id`.

## Edge cases

- **Single-round consensus:** The clerk still writes a full `decision.md`. No `dissent.md` needed.
- **All members at confidence < 0.70:** Flag in the decision as "low-confidence decision — schedule review in 2 weeks." Add a `questions/` page via `kb-add` with `page_type: question`.
- **Parsing failures in transcript:** Note them in a `## Parsing notes` section at the bottom of `decision.md`. Do not discard the committee results because of formatting issues.
- **Empty challenge phase:** If no challenges were raised (all members posted empty challenges), note this as a concern in the decision: "No adversarial challenges were raised — consider additional review before implementation."
