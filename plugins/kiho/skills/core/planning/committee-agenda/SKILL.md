---
name: committee-agenda
description: Use this skill as the first step of any committee deliberation. Bundles prior decisions on related topics, open action items, relevant KB articles, relevant memos, and a suggested agenda into a pre-read artifact for committee members. Cuts committee bootstrap cost so rounds spend time deliberating rather than recapitulating context. Read-only; holds no decision authority. Produced before the committee convenes; consumed by every member at kickoff. Stored as Tier-1 markdown so post-hoc review can verify what context the committee had. For recurring committees the agenda caches the prior session's open items and auto-renews them.
argument-hint: "committee_id=<id> topic=<text>"
metadata:
  trust-tier: T2
  kiho:
    capability: orchestrate
    topic_tags: [deliberation, retrieval]
    data_classes: ["committee-transcript", "committee-records-jsonl", "kb-wiki-articles"]
---
# committee-agenda

A committee without a pre-read spends its first round recapping. Three rounds is the kiho cap (see `references/committee-rules.md`); a round spent on recap is a round not spent on deliberation. This skill bundles everything a committee needs to hit round 1 already aligned on facts.

## Why a pre-read

Committees are expensive. Five agents times three rounds is fifteen LLM passes — and the unanimous-close rule means any one misaligned member drags the group back. Pre-alignment on *facts* (what was decided before, what is still open, what the KB says) frees the rounds to debate *values and tradeoffs*, which is what committees are actually for.

The agenda is read-only and carries no decision authority. It is a scaffold, not a verdict. The committee may ignore every agenda item and pursue something else; the agenda's only job is to make sure no one walks in cold.

## Inputs

```
PAYLOAD:
  committee_id: <id>              # required — e.g., "skill-promote-2026-W16"
  topic: <text>                   # required — one-line framing
  last_session_ref: <md://...>    # optional — for recurring committees
  open_questions: [<line>, ...]   # optional — CEO-provided seed questions
  members: [<agent_id>, ...]      # optional — default: resolved from committee_id
  scope_tags: [<tag>, ...]        # optional — defaults to tags mined from topic
```

Scope tags come from the topic vocabulary in `references/topic-vocabulary.md`. If the caller omits them, the skill extracts candidate tags from the topic text and uses the top three.

## Procedure

### 1. Query prior decisions

Call `memory-query` for decisions matching the topic:

```
memory-query
  query: <topic>
  filters:
    kind: decision
    topic_tags_any: <scope_tags>
  max_results: 10
  window: last 180 days
```

Rank by recency and relevance; keep only items whose subject is a fair match (no fishing expeditions). If `last_session_ref` is set, always include its decisions regardless of rank.

### 2. Query open actions

Call `storage-broker` op=`query`:

```
OPERATION: query
PAYLOAD:
  namespace: state/actions
  where:
    status: open
    topic_tags_any: <scope_tags>
  max_results: 20
  sort_by: [due_iteration ASC]
```

Open actions are live debt; a committee that proposes new work without seeing existing debt is prone to double-booking owners.

### 3. Retrieve KB context

Call `kb-search` (through kb-manager, the sole KB gateway):

```
kb-search
  query: <topic>
  filters:
    topic_tags_any: <scope_tags>
  max_results: 5
```

Prefer high-confidence articles (trust_level official or community). Capture `page_path`, one-line summary, and confidence — do not inline the full article body into the agenda.

### 4. Inspect member inboxes

For each `member`, call `memo-inbox-read` filtered to the topic:

```
memo-inbox-read agent=<member> filters={topic_tags_any: <scope_tags>, unread: true, max: 5}
```

Any unread memo that touches the committee topic is pre-read material. Include subject and ref, not body.

### 5. Assemble the bundle

Build the markdown bundle with the structure below. Do not synthesize opinions; the agenda is read-only. Each section lists items with refs; the committee reads the bodies if it needs them.

### 6. Persist the agenda

Call `storage-broker` op=`put`:

```
OPERATION: put
PAYLOAD:
  namespace: state/committees/<committee_id>/agendas
  kind: generic
  access_pattern: read-mostly
  durability: project
  human_legible: true
  body: <the pre-read markdown>
```

Namespace per committee keeps recurring ones self-contained; ref is `md://state/committees/<committee_id>/agendas/<iso>.md`.

### 7. Return the ref — do not notify members directly; the convener distributes the ref at kickoff.

## Pre-read structure

```markdown
# Agenda — <committee_id>
**Topic:** <topic>
**Members:** <list>
**Scope tags:** <list>
**Prepared:** <iso>
**Prior session:** <last_session_ref or "none">

## Prior decisions
- <date> — <subject> — <decision one-liner> — <ref>

## Open actions in scope
- owner=<agent_id> due=<iter> — <description> — <ref>

## Relevant KB articles
- <title> (confidence=<n>, trust=<level>) — <page_path>

## Relevant memos (per-member unread hits)
- <member>: <subject> — <memo_ref>

## Agenda items (suggested, non-binding)
1. Confirm scope and acceptance criteria.
2. Review open actions; flag collisions with anticipated new work.
3. Deliberate: <CEO-seeded or topic-derived questions>.
4. Decide and assign owners.
5. Emit decision memo and update actions.
```

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: committee-agenda
STATUS: ok | error
COMMITTEE_ID: <id>
AGENDA_REF: md://state/committees/<id>/agendas/<iso>.md
COUNTS:
  prior_decisions: <n>
  open_actions: <n>
  kb_articles: <n>
  member_memos: <n>
SCOPE_TAGS: [<tag>, ...]
PRIOR_SESSION_REF: <md://... or null>
NOTES: <optional>
```

## Invariants

- **Read-only.** The agenda never decides. It gathers refs and lists them.
- **No author voice.** No recommendations, no ranking that implies a vote, no "we should". Bullets are facts or seed questions.
- **Refs, not bodies.** The agenda inlines one-line summaries and refs; members follow the ref for detail, avoiding duplicated KB content that could drift.
- **Fresh per session.** Even for recurring committees, regenerate the agenda each session. Caching the structure is fine; caching the contents is not.
- **Bounded.** Each section caps at the limits above. Beyond them the topic is too wide; the CEO should split the committee.

## Non-Goals

- **Not a decision log.** Decisions are written by the committee to the ceo-ledger and decision memos; this skill only surfaces past ones.
- **Not meeting minutes.** The clerk records transcript, rounds, and close. This skill runs before the session and stops there.
- **Not a notifier.** Does not memo or ping members. Distribution of the agenda ref is the convener's job.
- **Not a KB writer.** Does not promote anything to the KB; only reads from it.

## Grounding

- `references/committee-rules.md` — unanimous close, 3-round cap, 0.90 confidence rule that motivate pre-alignment.
- `references/react-storage-doctrine.md` — why storage-broker owns the tier pick for the agenda artifact.
- `references/storage-architecture.md` — Tier-1 vs Tier-2 selection; agendas are read-mostly markdown, hence Tier-1.
- `references/topic-vocabulary.md` — the controlled tag set used to resolve scope.
- `skills/core/memory/memory-query/SKILL.md` — prior-decision query in step 1.
- `skills/core/storage/storage-broker/SKILL.md` — query and put ops used in steps 2 and 6.
- `skills/core/knowledge/kb-search/SKILL.md` — KB query in step 3.
- `skills/core/communication/memo-inbox-read/SKILL.md` — per-member inbox check in step 4.
