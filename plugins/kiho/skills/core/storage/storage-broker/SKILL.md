---
name: storage-broker
description: Use this skill whenever any kiho agent needs to write, read, query, or evict a persistent record and the tier is not already dictated by a data-storage-matrix row. The broker encodes the ReAct storage decision from references/react-storage-doctrine.md — caller passes intent signals (access_pattern, durability, size_hint, human_legible, kind), broker picks tier (md / jsonl / sqlite / mem), places the record, returns a citation Ref. Reviewable kinds (soul, skill-md, kb-article, decision, brief, announcement, incident, postmortem, retrospective, values-flag, committee-transcript) are forced to md; the broker enforces this via kiho_frontmatter.validate and cannot be bypassed.
argument-hint: "op=<put|get|query|evict> namespace=<path> ..."
metadata:
  trust-tier: T3
  kiho:
    capability: orchestrate
    topic_tags: [infrastructure, retrieval]
    data_classes: []
---
# storage-broker

The ReAct front-door for persistent storage. Pre-v5.20 every skill hardcoded its storage choice at authoring time; after v5.20 skills SHOULD delegate through this broker unless a specific matrix row names a fixed path.

## Why a broker

Three pressures converged:

1. Agents started asking "should this be md or jsonl?" per invocation — the answer depends on who reads the record, how often, and when it evicts. A skill author at commit time can't always know.
2. KB / memory / experience-pool each reinvented frontmatter parsing with divergent schemas. Unified write path + unified helper (`bin/kiho_frontmatter.py`) collapse the duplication.
3. Tier-3 sqlite and in-process scratch were listed as "on-demand" in `storage-architecture.md` but had no callable API. The broker is that API.

The broker does not replace `data-storage-matrix.md`. Well-known data classes (telemetry JSONL, KB wiki, agent souls, etc.) keep their fixed paths and gatekeepers. The broker handles the long tail: memos, receipts, standups, incidents, retros, evolution rows, feedback queues, committee agendas, ceremony transcripts, anything kiho adds in the corp-efficiency skill set that doesn't deserve its own matrix row.

## Inputs

```
OP: put | get | query | evict

PUT:
  namespace:        <path-under-plugin-root, e.g. "state/memos/ceo-01">
  key:              <optional stable id; broker generates uuid if missing>
  payload:          <dict; caller's domain data>
  body:             <optional markdown body; only used when tier resolves to md>
  access_pattern:   append-only | query-heavy | read-heavy | ephemeral
  durability:       session | project | company
  size_hint:        <approx row count; governs sqlite threshold>
  query_keys:       <optional list of payload keys worth indexing>
  human_legible:    <bool; if true, forces md tier — unless caller is wrong and
                     kind is non-reviewable, in which case md is honoured>
  kind:             <one of KIND_SCHEMAS in kiho_frontmatter.py; reviewable
                     kinds are ALWAYS md regardless of other signals>
  scope:            session | project | company
  owner:            <agent slug or "ceo" or "kiho">

GET:
  ref:              <Ref dict returned by a prior put(), OR>
  namespace + key:  <broker will probe md then jsonl then mem>

QUERY:
  namespace:        <same as put>
  where:            <optional dict of exact-match equality filters>
  fts:              <optional FTS5 query string; triggers lazy sqlite build>
  order_by:         <"created_at" | "updated_at" | "confidence" [asc|desc]>
  limit:            <int; default 50>

EVICT:
  namespace:        <same as put>
  older_than_days:  <int; drop rows older than now - N days>
  keep_last:        <int; keep only the most recent N rows>
```

## The ReAct decision

Before calling the broker, the agent walks the 4-question tree from `references/react-storage-doctrine.md`:

1. Will a human review this in the next turn? → `human_legible=True` (or pick a reviewable `kind`).
2. Does it outlive this turn? → `durability >= project`.
3. Do I need filter / sort / FTS later? → `access_pattern=query-heavy` or `size_hint > 1000`.
4. Is the source canonical elsewhere? → don't call the broker; cite instead.

The broker resolves a tier from these signals:

| signals | resolved tier |
|---|---|
| `kind` is reviewable | md |
| `human_legible=True` | md |
| `durability=session` or `access_pattern=ephemeral` | mem |
| `access_pattern=query-heavy` or `size_hint > 1000` | sqlite (lazy FTS) |
| default | jsonl (append) |

If the caller's signals are inconsistent (e.g. `kind=incident` with `access_pattern=append-only`), the broker honours the reviewable-kind guardrail and writes md. No warning — the guardrail is designed to be silent and non-bypassable.

## Procedure

1. Validate inputs. Fail fast on unknown `access_pattern` / `durability` / `kind`.
2. Resolve tier via `bin/kiho_storage._select_tier`.
3. Build canonical meta via `bin/kiho_frontmatter.merge_defaults(kind, meta)`.
4. Promote kind-required fields from payload into meta so `validate()` sees them.
5. Call `kiho_frontmatter.validate(meta, kind)`. Reject on any error.
6. Place the record:
   - `md` → `<plugin_root>/<namespace>/<key>.md` via `kiho_frontmatter.write`.
   - `jsonl` → append to `<plugin_root>/<namespace>.jsonl` with `kiho_frontmatter.jsonl_row`.
   - `sqlite` → same spool as jsonl; invalidate any prior sqlite index so next query rebuilds.
   - `mem` → in-process dict `(namespace, key) → record`.
7. Return a `Ref = {tier, namespace, key, path, row_id, etag}`. Caller persists the Ref in its own artefact to cite later rather than raw paths.

For `get`: probe by Ref (preferred) or by `(namespace, key)` fall-through (md → jsonl → mem). Always returns `{meta, payload, body}` or `None`.

For `query`: scan the jsonl spool, apply `where`, sort by `order_by` (default `updated_at desc`), return up to `limit`. If `fts` is set, build the FTS5 index lazily under `<plugin_root>/.cache/<namespace>.sqlite`, then `MATCH` against the serialized row body.

For `evict`: compact the jsonl spool, remove rows older than threshold or beyond `keep_last`, invalidate sqlite cache. Md files are **not** evicted by the broker — md retention is governed by kb-manager / skill-deprecate / committee.

## Shell recipe

The backing CLI at `bin/kiho_storage.py` mirrors the op vocabulary:

```bash
# put
python bin/kiho_storage.py --plugin-root <project>/.kiho put \
  --namespace state/evolution/history \
  --kind evolution \
  --payload '{"skill_id": "kb-add", "action": "improve", "before_version": "1.0.0", "after_version": "1.1.0"}'

# query latest 20 evolutions for a specific skill
python bin/kiho_storage.py --plugin-root <project>/.kiho query \
  --namespace state/evolution/history \
  --where '{"skill_id": "kb-add"}' --limit 20

# FTS across the lot
python bin/kiho_storage.py --plugin-root <project>/.kiho query \
  --namespace state/evolution/history --fts "version"

# compact (keep last 500 rows per namespace)
python bin/kiho_storage.py --plugin-root <project>/.kiho evict \
  --namespace state/evolution/history --keep-last 500
```

## Response shapes

```
OK (put):
{
  "status": "ok",
  "ref": {"tier": "<md|jsonl|sqlite|mem>", "namespace": "...", "key": "...",
          "path": "...", "row_id": "...", "etag": "..."}
}

OK (get):
{"status": "ok", "record": {"meta": {...}, "payload": {...}, "body": "..."}}

OK (query):
{"status": "ok", "rows": [ {...}, ... ]}

OK (evict):
{"status": "ok", "removed": <int>}

ERR (policy violation):
{"status": "error", "code": "policy_violation", "detail": "<what failed>"}
```

## Invariants

- **Reviewable-kind guardrail.** The 11 reviewable kinds in `KIND_SCHEMAS` are forced to md. Callers cannot override.
- **No long-running server.** Every sqlite connection is per-call; no daemon.
- **Lazy FTS.** The sqlite index is rebuilt only when a query demands it; never at plugin load.
- **Eviction is explicit.** Only `evict` is destructive. Md is not touched by `evict`.
- **User-accept gate.** `scope=project` and `scope=company` writes require a prior user-accept turn at the `/kiho` boundary. The broker does not police this — the CEO does — but the broker will refuse a `scope=company` write that carries `owner` outside a CEO-owned allowlist (future: checked against the org-registry).
- **Depth/fanout caps.** Broker writes are file I/O. They never count toward the depth-3 / fanout-5 caps.

## Non-Goals

- **Not a message bus.** Inboxes built on top of the broker (`memo-send` → jsonl) are lazy-read at loop boundaries. No watcher, no callback, no notification.
- **Not a replacement for kb-manager.** KB wiki writes still go through `kiho-kb-manager`. The broker refuses any write that targets `<project>/.kiho/kb/wiki/**` — that namespace is kb-manager's.
- **Not a schema registry.** New reviewable kinds require a PR to `kiho_frontmatter.KIND_SCHEMAS` plus a committee vote. Non-reviewable kinds can be added via skill-improve.
- **Not an ACID transaction manager.** Writes are at-least-once. For multi-row atomicity, batch the writes in the caller and use a single `evict --keep-last` pass after.

## Grounding

- `references/react-storage-doctrine.md` — the 4-question tree this skill encodes
- `references/storage-architecture.md` — tier invariants (T1/T2/T3 MUSTs)
- `references/data-storage-matrix.md` — per-data-class rows (still authoritative for well-known classes)
- `bin/kiho_storage.py` — backing library
- `bin/kiho_frontmatter.py` — canonical schema + validate
