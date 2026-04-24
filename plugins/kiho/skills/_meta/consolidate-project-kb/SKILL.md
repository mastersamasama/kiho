---
name: consolidate-project-kb
description: Scans a single project's `<project>/.kiho/kb/wiki/` tree for clusters of closely-related entries, proposes synthesis pages via `kb-manager op=kb-add`, and emits a consolidation receipt. Invoked by CEO DONE step 10b when `days_since_last_project_kb_consolidation >= settings.kb_consolidation.project_kb_cadence_turns` (default 10 turns). Uses `bin/embedding_util.py` for similarity clustering (sentence-transformers when available, TF-IDF fallback otherwise). READ-only by itself — all writes flow through kb-manager so the KB_MANAGER_CERTIFICATE hook gate stays honored. Respects `settings.promote.dry_run_before_write` (default true) — proposals surface via CEO AskUserQuestion before any synthesis page lands.
metadata:
  trust-tier: T2
  version: 1.0.0
  lifecycle: draft
  kiho:
    capability: read
    topic_tags: [curation, lifecycle]
    data_classes: ["kb-wiki-articles"]
    storage_fit:
      reads: ["<project>/.kiho/kb/wiki/**", "$COMPANY_ROOT/settings.md"]
      writes: []
---
# consolidate-project-kb

Periodic project-KB consolidation. Scans `.kiho/kb/wiki/` for clusters of
related entries, drafts a `synthesis/<topic>.md` per cluster, and hands the
draft to `kb-manager op=kb-add` for final persistence. The skill itself
performs NO direct wiki writes — kb-manager is the sole gateway.

## When to use

Invoke from:

- CEO DONE step 10b cadence gate, once per `settings.kb_consolidation.project_kb_cadence_turns` turns
- Ad-hoc `/kiho` command when user requests "tidy up project kb"

Do NOT invoke:

- On a fresh project with fewer than 6 wiki entries (nothing to cluster)
- During an unstable Ralph loop iteration — consolidation runs at DONE, never mid-LOOP

## BCP 14

MUST / MUST NOT / SHOULD — per RFC 2119 + RFC 8174.

## Inputs

```
project_root: <path>                     # project with .kiho/ tree
similarity_threshold: <float 0.60..0.85> # default 0.70; tune via settings
min_cluster_size: <int>                  # default 2 — smaller clusters ignored
scope: ["entities","concepts","decisions","conventions","synthesis","questions"]
max_proposals: <int>                     # default 5 per cycle (avoid flood)
dry_run: <bool>                          # default true; mirror settings.promote.dry_run_before_write
```

## Procedure

### Phase 1 — Gather candidates

1. Enumerate files under `<project>/.kiho/kb/wiki/` matching `scope` subdirs.
2. Skip files with frontmatter `lifecycle: deprecated`.
3. Skip files already under `synthesis/` (second-order consolidation is a
   separate future skill).

### Phase 2 — Cluster

1. Invoke `bin/embedding_util.py` via either Python import (preferred) or
   the Bash CLI: `python ${CLAUDE_PLUGIN_ROOT}/bin/embedding_util.py cluster
   <project>/.kiho/kb/wiki --threshold <val> --ext .md`.
2. Parse the JSON output for cluster members.
3. Drop clusters with size < `min_cluster_size`.
4. Limit to top `max_proposals` clusters by member count.

### Phase 3 — Draft synthesis proposals

For each retained cluster:

1. Read each member's frontmatter + body.
2. Extract a topic hint from common frontmatter tags.
3. Draft a `synthesis/<topic>.md` with:
   - Frontmatter: `page_type: synthesis`, `sources: [<list of member paths>]`, `confidence: <mean of member confidences>`, `generated_by: consolidate-project-kb`
   - Body: bulleted summary of each member, followed by a "Synthesized takeaways" section merging the common themes
4. Emit a `kb_add_proposal` with the draft content + metadata.

### Phase 4 — Route through kb-manager

For each proposal:

- **dry_run == true** (default): return the proposal in the response. The
  caller (CEO DONE) surfaces it via `AskUserQuestion` with options:
  *Approve* (→ kb-manager `kb-add`), *Skip*, *Edit*.
- **dry_run == false**: invoke `kiho:kiho-kb-manager` op=`kb-add` directly
  with the synthesis draft.

### Phase 5 — Update consolidation ledger

Append one row per proposal to `<project>/.kiho/state/consolidation-ledger.jsonl`:

```json
{"ts": "<iso>", "action": "project_kb_synth_proposed|applied|skipped",
 "cluster_size": <int>, "sources": [...], "synthesis_path": "<path|null>",
 "decision_by": "<user|auto>"}
```

## Response shape

```json
{
  "status": "ok | no_clusters | error",
  "backend": "sentence-transformers | sklearn-tfidf | stdlib-tfidf",
  "clusters_found": <int>,
  "proposals": [
    {
      "cluster_size": 3,
      "sources": ["<path1>", "<path2>", "<path3>"],
      "topic_hint": "<string>",
      "synthesis_draft_path": "<tmp path>",
      "confidence_mean": 0.85
    }
  ],
  "applied": <int>,
  "review_required": <int>,
  "next_cadence_turn": <int>
}
```

## Anti-patterns

- MUST NOT write to `.kiho/kb/wiki/` directly — kb-manager is the gateway.
  The `KB_MANAGER_CERTIFICATE:` hook would block direct writes anyway.
- MUST NOT consolidate more than `max_proposals` clusters per invocation —
  flooding AskUserQuestion undermines the value of targeted review.
- MUST NOT replace source pages. Synthesis ADDS; source pages stay unless
  `kb-promote` separately retires them.
- Do NOT re-cluster synthesis output within the same call — compounding
  synthesis lives in a future "second-order" skill.

## Grounding

v6 plan §3.8 — consolidation cycles. "Project-KB consolidation runs every
N turns on a given project; synthesis proposals route through kb-manager
for conflict/duplicate checks."
