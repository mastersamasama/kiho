#!/usr/bin/env python3
"""
kiho_storage.py — ReAct storage broker backing library (v5.20).

The `storage-broker` skill (`skills/core/storage/storage-broker/SKILL.md`)
is the ReAct front-door an agent talks to when it needs to decide where
a record lives. This module is the deterministic backing library the
skill calls. The skill supplies the access-pattern hints; this module
picks the tier, places the data, and returns a citation Ref the caller
can use later.

Core API:
    put(namespace, key, payload, *,
        access_pattern, durability, size_hint=None, query_keys=None,
        human_legible=False, kind="generic", scope="project",
        owner="kiho", plugin_root=None) -> Ref
    get(ref_or_namespace, key=None, *, plugin_root=None) -> dict | str | None
    query(namespace, *, where=None, fts=None, order_by=None,
          limit=50, plugin_root=None) -> list[dict]
    evict(namespace, *, older_than_days=None, keep_last=None,
          plugin_root=None) -> int

Tier-selection policy (matches references/react-storage-doctrine.md):

    +-------------------------+-------------------+
    | signal                  | resolved tier     |
    +-------------------------+-------------------+
    | human_legible=True      | md (committee)    |
    | durability=session      | mem (scratch)     |
    | access=append-only AND  |                   |
    |   size_hint<=1000 rows  | jsonl             |
    | access=query-heavy OR   |                   |
    |   size_hint>1000 rows   | sqlite (lazy FTS) |
    | default                 | jsonl             |
    +-------------------------+-------------------+

    Reviewable kinds (soul, skill-md, kb-article, decision, brief,
    announcement, incident, postmortem, retrospective, values-flag,
    committee-transcript) are FORCED to md via kiho_frontmatter.validate.
    Broker MUST NOT override that.

Paths:
    Ref.tier == "md"     → <plugin_root>/<namespace>/<key>.md
    Ref.tier == "jsonl"  → <plugin_root>/<namespace>.jsonl  (append)
    Ref.tier == "sqlite" → <plugin_root>/.cache/<namespace>.sqlite (built
                           lazily from the same <namespace>.jsonl; rebuilt
                           when row_count or mtime diverges)
    Ref.tier == "mem"    → in-process dict keyed by (namespace, key);
                           lost at process exit.

plugin_root defaults: when None, uses the current working directory.
The caller (typically a kiho sub-agent) is responsible for pointing
plugin_root at the right project directory (usually `<project>/.kiho/`).

Invariants enforced here:
    * Reviewable-kind guardrail via kiho_frontmatter.validate.
    * No long-running server, no daemon. sqlite connections are opened
      per call and closed before return.
    * FTS5 index is lazy: built on first query when row_count > 1000 OR
      the caller explicitly passes fts=<query>.
    * `evict` is the only destructive op. md writes go to atomic-rename
      temp files; jsonl uses O_APPEND.

Exit codes (when used as CLI):
    0 — success
    1 — policy violation
    2 — usage error
    3 — internal error

Grounding:
    * references/react-storage-doctrine.md
    * references/storage-architecture.md
    * references/data-storage-matrix.md
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kiho_frontmatter as _fm  # type: ignore


# --- Ref --------------------------------------------------------------------


@dataclass
class Ref:
    """Citation returned by put(). Callers persist it instead of raw paths."""
    tier: str          # md | jsonl | sqlite | mem
    namespace: str
    key: str
    path: str          # resolved filesystem path or "<mem>" for mem tier
    row_id: str        # stable within namespace
    etag: str          # cheap cache-busting hash (short)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Ref":
        return cls(
            tier=str(d["tier"]),
            namespace=str(d["namespace"]),
            key=str(d["key"]),
            path=str(d["path"]),
            row_id=str(d["row_id"]),
            etag=str(d["etag"]),
        )


# --- tier selection ---------------------------------------------------------


APPEND_ONLY = "append-only"
QUERY_HEAVY = "query-heavy"
READ_HEAVY = "read-heavy"
EPHEMERAL = "ephemeral"

VALID_ACCESS = {APPEND_ONLY, QUERY_HEAVY, READ_HEAVY, EPHEMERAL}
VALID_DURABILITY = {"session", "project", "company"}

SQLITE_ROW_THRESHOLD = 1000


def _select_tier(
    *,
    access_pattern: str,
    durability: str,
    size_hint: int | None,
    human_legible: bool,
    kind: str,
) -> str:
    if access_pattern not in VALID_ACCESS:
        raise ValueError(
            f"access_pattern must be one of {sorted(VALID_ACCESS)}; got {access_pattern!r}"
        )
    if durability not in VALID_DURABILITY:
        raise ValueError(
            f"durability must be one of {sorted(VALID_DURABILITY)}; got {durability!r}"
        )
    # Reviewable kinds are forced to md; kiho_frontmatter.validate double-checks.
    if kind in _fm.KIND_SCHEMAS and _fm.KIND_SCHEMAS[kind]["reviewable"]:
        return "md"
    if human_legible:
        return "md"
    if durability == "session" or access_pattern == EPHEMERAL:
        return "mem"
    if access_pattern == QUERY_HEAVY:
        return "sqlite"
    if size_hint is not None and size_hint > SQLITE_ROW_THRESHOLD:
        return "sqlite"
    # append-only + small-to-medium row count, or read-heavy with jsonl-friendly shape
    return "jsonl"


# --- mem backend ------------------------------------------------------------

_MEM_STORE: dict[tuple[str, str], dict[str, Any]] = {}


# --- path helpers -----------------------------------------------------------


def _plugin_root(plugin_root: Path | str | None) -> Path:
    return Path(plugin_root) if plugin_root else Path.cwd()


def _jsonl_path(root: Path, namespace: str) -> Path:
    return root / f"{namespace}.jsonl"


def _md_path(root: Path, namespace: str, key: str) -> Path:
    safe_key = key.replace("/", "__").replace("\\", "__")
    return root / namespace / f"{safe_key}.md"


def _sqlite_path(root: Path, namespace: str) -> Path:
    safe_ns = namespace.replace("/", "__")
    return root / ".cache" / f"{safe_ns}.sqlite"


def _etag(data: str | bytes) -> str:
    import hashlib
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:12]


# --- put --------------------------------------------------------------------


def put(
    namespace: str,
    key: str | None,
    payload: dict[str, Any] | str,
    *,
    access_pattern: str = APPEND_ONLY,
    durability: str = "project",
    size_hint: int | None = None,
    query_keys: list[str] | None = None,
    human_legible: bool = False,
    kind: str = "generic",
    scope: str = "project",
    owner: str = "kiho",
    body: str = "",
    plugin_root: Path | str | None = None,
) -> Ref:
    """Write a record. Returns a Ref usable by get/query/evict later.

    For kind=generic or tier=jsonl/sqlite, `payload` is a dict. For tier=md
    the caller may provide `body` separately; the dict becomes frontmatter.
    """
    tier = _select_tier(
        access_pattern=access_pattern,
        durability=durability,
        size_hint=size_hint,
        human_legible=human_legible,
        kind=kind,
    )
    if isinstance(payload, str) and not body:
        body = payload
        payload_dict: dict[str, Any] = {}
    elif isinstance(payload, dict):
        payload_dict = dict(payload)
    else:
        raise TypeError(f"payload must be dict or str; got {type(payload).__name__}")

    row_id = key or payload_dict.get("id") or str(uuid.uuid4())
    meta: dict[str, Any] = {
        "id": row_id,
        "kind": kind,
        "scope": scope,
        "owner": owner,
        "tier": tier,
    }
    # caller-supplied canonical fields win
    for k in _fm.REQUIRED_COMMON + _fm.OPTIONAL_COMMON:
        if k in payload_dict:
            meta[k] = payload_dict[k]
    # kind-required fields come from payload but get promoted into meta so
    # validate() sees them (and jsonl_row captures them at top level).
    for k in _fm.KIND_SCHEMAS.get(kind, {}).get("required", ()):
        if k in payload_dict and k not in meta:
            meta[k] = payload_dict[k]
    meta = _fm.merge_defaults(kind, meta)
    # query_keys are advisory for downstream indexing consumers; we
    # record them in meta when present so FTS rebuilders can prefer them.
    if query_keys:
        meta["query_keys"] = list(query_keys)

    errors = _fm.validate(meta, kind=kind)
    if errors:
        raise ValueError(f"frontmatter validation failed for kind={kind}: {errors}")

    root = _plugin_root(plugin_root)

    if tier == "md":
        path = _md_path(root, namespace, row_id)
        body_final = body if body else _render_body_from_payload(payload_dict)
        # merge non-canonical payload keys into frontmatter for md writes
        for k, v in payload_dict.items():
            if k not in meta and k not in _fm.REQUIRED_COMMON:
                meta[k] = v
        _fm.write(path, meta, body_final)
        return Ref(tier=tier, namespace=namespace, key=row_id,
                   path=str(path), row_id=row_id, etag=_etag(body_final))

    if tier == "jsonl":
        path = _jsonl_path(root, namespace)
        path.parent.mkdir(parents=True, exist_ok=True)
        row = _fm.jsonl_row(kind, meta, payload_dict)
        line = json.dumps(row, ensure_ascii=False, sort_keys=False)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return Ref(tier=tier, namespace=namespace, key=row_id,
                   path=str(path), row_id=row_id, etag=_etag(line))

    if tier == "sqlite":
        # sqlite tier uses the same jsonl as the spool; FTS5 view is built
        # lazily on query. This preserves T2-regenerability: the jsonl is
        # authoritative, the sqlite file is derived.
        spool = _jsonl_path(root, namespace)
        spool.parent.mkdir(parents=True, exist_ok=True)
        row = _fm.jsonl_row(kind, meta, payload_dict)
        line = json.dumps(row, ensure_ascii=False, sort_keys=False)
        with spool.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        # Invalidate any prior FTS index so next query rebuilds.
        idx = _sqlite_path(root, namespace)
        if idx.exists():
            try:
                idx.unlink()
            except OSError:  # pragma: no cover
                pass
        return Ref(tier=tier, namespace=namespace, key=row_id,
                   path=str(spool), row_id=row_id, etag=_etag(line))

    # tier == "mem"
    _MEM_STORE[(namespace, row_id)] = {"meta": meta, "payload": payload_dict, "body": body}
    return Ref(tier=tier, namespace=namespace, key=row_id,
               path="<mem>", row_id=row_id, etag=_etag(row_id))


def _render_body_from_payload(payload: dict[str, Any]) -> str:
    if not payload:
        return ""
    # Keep body minimal — md callers typically supply body directly.
    lines = [f"- **{k}**: {v}" for k, v in payload.items() if k != "id"]
    return "\n".join(lines) + "\n"


# --- get --------------------------------------------------------------------


def get(
    ref_or_namespace: Ref | dict[str, Any] | str,
    key: str | None = None,
    *,
    plugin_root: Path | str | None = None,
) -> dict[str, Any] | None:
    """Retrieve a single record by Ref (or namespace+key).

    Returns {"meta": ..., "payload": ..., "body": ...} or None if missing.
    For jsonl/sqlite tiers this returns the LATEST matching row (scan from
    end). For mem tier, direct dict lookup. For md tier, parsed frontmatter
    + body.
    """
    ref: Ref
    if isinstance(ref_or_namespace, Ref):
        ref = ref_or_namespace
    elif isinstance(ref_or_namespace, dict):
        ref = Ref.from_dict(ref_or_namespace)
    elif isinstance(ref_or_namespace, str) and key is not None:
        # caller didn't keep a Ref; infer tier by probing md first then jsonl
        root = _plugin_root(plugin_root)
        md_p = _md_path(root, ref_or_namespace, key)
        if md_p.exists():
            meta, body = _fm.read(md_p)
            return {"meta": meta, "payload": {}, "body": body}
        jl_p = _jsonl_path(root, ref_or_namespace)
        if jl_p.exists():
            last = _scan_jsonl_last(jl_p, key)
            if last:
                return {"meta": _strip_payload(last), "payload": last.get("payload", {}), "body": ""}
        if (ref_or_namespace, key) in _MEM_STORE:
            return dict(_MEM_STORE[(ref_or_namespace, key)])
        return None
    else:
        raise TypeError("get() requires a Ref or (namespace, key)")

    if ref.tier == "mem":
        stored = _MEM_STORE.get((ref.namespace, ref.row_id))
        return dict(stored) if stored else None
    if ref.tier == "md":
        p = Path(ref.path)
        if not p.exists():
            return None
        meta, body = _fm.read(p)
        return {"meta": meta, "payload": {}, "body": body}
    # jsonl / sqlite share the same spool
    p = Path(ref.path)
    if not p.exists():
        return None
    last = _scan_jsonl_last(p, ref.row_id)
    if not last:
        return None
    return {"meta": _strip_payload(last), "payload": last.get("payload", {}), "body": ""}


def _scan_jsonl_last(path: Path, row_id: str) -> dict[str, Any] | None:
    found: dict[str, Any] | None = None
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("id") == row_id:
                found = row
    return found


def _strip_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k != "payload"}


# --- query ------------------------------------------------------------------


def query(
    namespace: str,
    *,
    where: dict[str, Any] | None = None,
    fts: str | None = None,
    order_by: str | None = None,
    limit: int = 50,
    plugin_root: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Scan or FTS-query records in a namespace.

    * `where` is a dict of exact-match equality filters applied against row
      top-level fields (not payload subfields — flatten first if you need that).
    * `fts` triggers lazy sqlite FTS5 index build over the spool jsonl. The
      FTS virtual column is the JSON-serialized row body (payload + meta).
    * `order_by` is one of {"created_at", "updated_at", "confidence"} with
      optional " desc"/" asc" suffix; default is recency (updated_at desc).
    * `limit` caps the result count; defaults to 50.
    """
    root = _plugin_root(plugin_root)
    spool = _jsonl_path(root, namespace)
    rows: list[dict[str, Any]] = []
    if fts:
        rows = _fts_query(root, namespace, fts, limit=limit)
    elif spool.exists():
        rows = _scan_jsonl(spool)
    # apply where filter
    if where:
        def matches(r: dict[str, Any]) -> bool:
            return all(r.get(k) == v for k, v in where.items())
        rows = [r for r in rows if matches(r)]
    # apply order_by
    if order_by:
        key_name, _, direction = order_by.partition(" ")
        rev = (direction.lower() != "asc")
        rows.sort(key=lambda r: r.get(key_name) or "", reverse=rev)
    else:
        rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    return rows[:limit]


def _scan_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _fts_query(root: Path, namespace: str, fts: str, *, limit: int) -> list[dict[str, Any]]:
    """Build a lazy sqlite FTS5 index over the namespace's jsonl, then query."""
    spool = _jsonl_path(root, namespace)
    if not spool.exists():
        return []
    idx = _sqlite_path(root, namespace)
    idx.parent.mkdir(parents=True, exist_ok=True)
    need_rebuild = not idx.exists() or idx.stat().st_mtime < spool.stat().st_mtime
    if need_rebuild:
        if idx.exists():
            try:
                idx.unlink()
            except OSError:  # pragma: no cover
                pass
        conn = sqlite3.connect(idx)
        try:
            conn.execute("CREATE VIRTUAL TABLE rows USING fts5(id UNINDEXED, body)")
            rows = _scan_jsonl(spool)
            conn.executemany(
                "INSERT INTO rows(id, body) VALUES (?, ?)",
                [(r.get("id", ""), json.dumps(r, ensure_ascii=False)) for r in rows],
            )
            conn.commit()
        finally:
            conn.close()
    conn = sqlite3.connect(idx)
    try:
        cur = conn.execute(
            "SELECT body FROM rows WHERE rows MATCH ? LIMIT ?", (fts, limit)
        )
        return [json.loads(r[0]) for r in cur.fetchall()]
    finally:
        conn.close()


# --- evict ------------------------------------------------------------------


def evict(
    namespace: str,
    *,
    older_than_days: int | None = None,
    keep_last: int | None = None,
    plugin_root: Path | str | None = None,
) -> int:
    """Compact a namespace's jsonl spool. Returns rows removed.

    * `older_than_days`: drop rows whose updated_at (or created_at) is
      older than now - N days.
    * `keep_last`: keep only the most recent N rows.

    Md-tier namespaces are NOT evicted here — their retention is governed
    by kb-manager / skill-deprecate / committee decisions.
    """
    root = _plugin_root(plugin_root)
    spool = _jsonl_path(root, namespace)
    if not spool.exists():
        return 0
    rows = _scan_jsonl(spool)
    before = len(rows)
    if older_than_days is not None:
        cutoff = time.time() - older_than_days * 86400
        def ts(r: dict[str, Any]) -> float:
            try:
                import datetime as dt
                return dt.datetime.strptime(
                    (r.get("updated_at") or r.get("created_at") or ""),
                    "%Y-%m-%dT%H:%M:%SZ",
                ).replace(tzinfo=dt.timezone.utc).timestamp()
            except (ValueError, TypeError):
                return time.time()  # can't parse → keep
        rows = [r for r in rows if ts(r) >= cutoff]
    if keep_last is not None:
        rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        rows = rows[:keep_last]
        rows.reverse()  # restore chronological order
    tmp = spool.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")
    os.replace(tmp, spool)
    # invalidate sqlite cache
    idx = _sqlite_path(root, namespace)
    if idx.exists():
        try:
            idx.unlink()
        except OSError:  # pragma: no cover
            pass
    return before - len(rows)


# --- CLI --------------------------------------------------------------------


def _cmd_put(args: argparse.Namespace) -> int:
    payload = json.loads(args.payload) if args.payload else {}
    ref = put(
        namespace=args.namespace,
        key=args.key,
        payload=payload,
        access_pattern=args.access_pattern,
        durability=args.durability,
        size_hint=args.size_hint,
        human_legible=args.human_legible,
        kind=args.kind,
        scope=args.scope,
        owner=args.owner,
        body=args.body or "",
        plugin_root=args.plugin_root,
    )
    print(json.dumps(ref.to_dict(), ensure_ascii=False))
    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    rows = query(
        namespace=args.namespace,
        where=json.loads(args.where) if args.where else None,
        fts=args.fts,
        order_by=args.order_by,
        limit=args.limit,
        plugin_root=args.plugin_root,
    )
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    return 0


def _cmd_evict(args: argparse.Namespace) -> int:
    removed = evict(
        namespace=args.namespace,
        older_than_days=args.older_than_days,
        keep_last=args.keep_last,
        plugin_root=args.plugin_root,
    )
    print(json.dumps({"removed": removed}))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kiho_storage", description=__doc__)
    ap.add_argument("--plugin-root", default=None,
                    help="project root (default: cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("put", help="write a record")
    p.add_argument("--namespace", required=True)
    p.add_argument("--key", default=None)
    p.add_argument("--payload", default="{}", help="JSON dict")
    p.add_argument("--access-pattern", default=APPEND_ONLY, choices=sorted(VALID_ACCESS))
    p.add_argument("--durability", default="project", choices=sorted(VALID_DURABILITY))
    p.add_argument("--size-hint", type=int, default=None)
    p.add_argument("--human-legible", action="store_true")
    p.add_argument("--kind", default="generic")
    p.add_argument("--scope", default="project", choices=sorted(_fm.VALID_SCOPES))
    p.add_argument("--owner", default="kiho")
    p.add_argument("--body", default=None)
    p.set_defaults(func=_cmd_put)

    q = sub.add_parser("query", help="scan or FTS-query records")
    q.add_argument("--namespace", required=True)
    q.add_argument("--where", default=None, help="JSON dict of equality filters")
    q.add_argument("--fts", default=None)
    q.add_argument("--order-by", default=None)
    q.add_argument("--limit", type=int, default=50)
    q.set_defaults(func=_cmd_query)

    e = sub.add_parser("evict", help="compact a jsonl namespace")
    e.add_argument("--namespace", required=True)
    e.add_argument("--older-than-days", type=int, default=None)
    e.add_argument("--keep-last", type=int, default=None)
    e.set_defaults(func=_cmd_evict)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"policy violation: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
