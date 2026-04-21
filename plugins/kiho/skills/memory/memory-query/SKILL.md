---
name: memory-query
description: Use this skill as the single supported read path when any agent needs to look up prior context — prior decisions for a topic, lessons other agents have learned, earlier research findings, committee transcripts relevant to the current task, or the ceo-ledger trail. Replaces ad-hoc greps across KB, memory, research cache, and ledger. Accepts an intent classifier (prior-art, decision-trail, lesson, why-did-X, who-did) and scope filter; returns a ranked citation list with evidence Refs the caller can click through. Internally dispatches via storage-broker to the relevant namespaces, ranks by recency * confidence * intent-match, dedupes by supersedes chain, and falls back to lazy sqlite FTS when shallow scan recall is insufficient. Read-only; never mutates any record.
argument-hint: "intent=<prior-art|decision-trail|lesson|why-did-X|who-did> topic=<text>"
metadata:
  trust-tier: T2
  kiho:
    capability: read
    topic_tags: [retrieval, reflection]
    data_classes: ["observations", "reflections", "lessons", "todos", "ceo-ledger", "kb-wiki-articles", "committee-transcript", "research-cache"]
---
# memory-query

The single supported unified read path for prior context inside kiho. Before v5.20 every skill that wanted to find "what did we already decide / learn / research about X" invented its own grep over KB wiki, agent memory, cross-agent-learnings, ceo-ledger, research cache, and committee transcripts, and reinvented its own ranking. `memory-query` consolidates that read path behind one intent-classified dispatcher, so callers ask a question by **shape of intent** and get back a ranked citation list they can click through.

This skill is a **pure reader**. It never writes. It never mutates supersedes chains. It never promotes anything into the KB. Writes go through the skill that owns each namespace (`kb-add`, `memory-reflect`, `ceo-ledger-append`, etc.); `memory-query` just routes through `storage-broker` (sk-040) and ranks.

## Inputs

```
PAYLOAD:
  intent: prior-art | decision-trail | lesson | why-did-X | who-did
  topic: <free-text — what the caller is asking about>
  scope:
    agents:     [<agent-name>, ...]   # optional, filter to these agents' memory
    topics:     [<topic-tag>, ...]    # optional, controlled-vocab filter
    time_range: {from: <iso>, to: <iso>}   # optional
    project:    <project | company | both> # default: both
  depth: shallow | deep           # default: shallow
  k: <int, default 8, max 50>
  include_payload: <bool, default false>   # true = inline snippet body, false = ref-only
```

`depth=shallow` is a one-pass scan over the routed namespaces via the broker's default (jsonl-scan / md-scan) path. `depth=deep` additionally fires a `storage-broker op=fts-query` which, for corpora over 1k rows, triggers the lazy Tier-3 sqlite FTS cache described in `references/react-storage-doctrine.md`.

## Intent → namespace routing

| Intent          | Namespaces dispatched (in rank priority)                                                        |
|-----------------|-------------------------------------------------------------------------------------------------|
| `prior-art`     | KB wiki (via `kb-search`) + agent lessons (`.kiho/agents/*/memory/lessons.md`) + experience-pool |
| `decision-trail`| Committee transcripts (`.kiho/committees/*/transcript.md`) + ceo-ledger + evolution-history      |
| `why-did-X`     | Committee transcripts + ceo-ledger + evolution-history (same as decision-trail, reason-weighted) |
| `lesson`        | `.kiho/state/cross-agent-learnings.jsonl` + per-agent `memory/lessons.md`                        |
| `who-did`       | `.kiho/state/org-registry.md` + `skill-invocations.jsonl` + `capability-matrix.md`               |

KB dispatch is **always delegated** — `memory-query` calls `kb-search` and never reads `wiki/*.md` directly. This preserves the kb-manager gateway invariant.

## Procedure

1. **Classify intent.** If the caller passed `intent=`, use it. Otherwise infer from the topic string using cheap keyword heuristics (`"why did we"` → `why-did-X`, `"who"` → `who-did`, `"lesson" | "learned"` → `lesson`, `"decided" | "pick"` → `decision-trail`, else `prior-art`). Reject if the classifier is under 0.60 and ask the caller to disambiguate.
2. **Dispatch per namespace.** For each namespace in the intent's routing row, call `storage-broker op=query` with the scope filters. The broker decides whether the namespace is jsonl-scan, md-scan, or already-indexed sqlite. `memory-query` does not care about the physical tier.
3. **Rank.** Compute a unified score per hit: `score = recency_weight(age) * confidence * intent_match_weight`, where `recency_weight` decays exponentially with a 14-day half-life, `confidence` comes from the hit's own metadata (defaults to 0.7 if absent), and `intent_match_weight` is 1.0 for the primary namespace of the intent and 0.7 for secondary namespaces. Break ties by recency.
4. **Dedupe by supersedes chain.** If two hits share a `supersedes:` chain (e.g., a committee decision that was later overturned), keep only the tip of the chain and surface the older entry only in `superseded_by` metadata.
5. **Deep fallback.** If `depth=deep` **and** the ranked list has fewer than `k` hits after dedupe, issue a second pass as `storage-broker op=fts-query` across the same namespaces. This is the only path that can trigger lazy sqlite FTS build; shallow mode never materializes Tier-3 state.

Return the top `k` citations. Never recurse across `Ref` links — if the caller wants to chase a ref, they re-invoke `memory-query` with the new topic.

## Response shapes

```markdown
## Receipt <REQUEST_ID>
OPERATION: memory-query
STATUS: ok | empty | error
INTENT: prior-art | decision-trail | lesson | why-did-X | who-did
TOPIC: <verbatim>
DEPTH_USED: shallow | deep
NAMESPACES_SCANNED: [kb, agent-lessons, ...]
CITATIONS:
  - ref: <kb:path | file:path#line | ledger:<id> | jsonl:<path>@<line>>
    snippet: "<≤120 chars verbatim excerpt>"
    reason: "<why this hit matched — intent phrase or tag>"
    age_days: <int>
    confidence: <0..1>
    score: <0..1>
    superseded_by: <ref | null>
  - ...
NOTES: <optional: "shallow recall < k, deep fallback fired"; "kb delegated to kb-search">
```

`STATUS: empty` is a first-class outcome. It means the cascade genuinely found nothing, not an error; the caller should treat it as "no prior context" and decide whether to `research` outward.

## Invariants

- **Read-only.** `memory-query` never calls any `storage-broker` operation other than `query` / `fts-query`. Any write attempt is a bug.
- **kb-manager gateway respected.** KB namespace dispatch goes through the `kb-search` sub-skill. This skill never opens `wiki/*.md` with a `Read` tool or a direct grep.
- **Hard cap.** `k` defaults to 8, max 50. Callers asking for more should narrow scope instead.
- **No ref recursion.** A single `memory-query` call returns citations, not citation trees. If the caller wants a follow-up, they issue a new call.
- **Shallow never builds Tier-3.** Only `depth=deep` is allowed to trigger a lazy sqlite FTS build, and only when shallow recall is insufficient.
- **Supersedes tip only.** If a decision was overturned, the overturned row must not show up as the top hit; its ref belongs in `superseded_by` of the current tip.

## Non-Goals

- **Not a write path.** For lessons write `memory-reflect`; for KB write `kb-add`; for ledger write the ceo-ledger append skill. `memory-query` is read-only by construction.
- **Not a summarizer.** It returns citations plus short reason strings. How to digest them into an answer is the caller's job (a CEO, a researcher, a committee). This keeps the reader deterministic and cheap.
- **Not an oracle.** Recall is best-effort — ranking heuristics are coarse on purpose. The caller must verify any hit before acting on it; this is the same discipline `research` applies to web sources.
- **Not a replacement for kb-search.** `kb-search` remains the canonical KB reader. For pure KB-shaped queries, callers may invoke `kb-search` directly; `memory-query` is for cross-namespace lookups that span KB **and** memory **and** ledger.
- **Not a dependency resolver.** It does not chase `supersedes:` or `requires:` chains across multiple hops; it only dedupes siblings within a single chain.

## Grounding

- `skills/core/storage/storage-broker/SKILL.md` (sk-040) — the ReAct-style dispatcher every namespace read goes through. `memory-query` is one of its canonical callers.
- `references/react-storage-doctrine.md` — why queries pick tier per-call and when lazy sqlite FTS is allowed to materialize.
- `skills/kb/kb-search/SKILL.md` — the canonical KB reader; `memory-query` delegates all KB-namespace reads here and never opens wiki files directly.
- `references/storage-architecture.md` — tier invariants; Tier-2 scans for jsonl, Tier-3 eviction for any sqlite cache this skill's deep mode may trigger.
- `references/karpathy-wiki-protocol.md` — why the KB gateway is enforced and what "citation" means inside kiho.
