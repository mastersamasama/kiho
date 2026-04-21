#!/usr/bin/env python3
"""
skill_catalog_index.py — Tier-3 session-scope sqlite index over SKILL.md metadata.

First shipping Tier-3 artifact (kiho v5.19 Phase 4 pilot). Builds a
per-turn sqlite database from `skills/**/SKILL.md` frontmatter, exposes
keyed lookups and FTS5 queries for the 32+ consumer scripts under
`skills/_meta/skill-create/scripts/`, `skills/_meta/skill-find/scripts/`,
and `bin/kiho_rdeps.py`.

Invariants (per references/storage-architecture.md):
    * T3-MUST-1 — eviction policy declared upfront: session-scope.
    * T3-MUST-2 — idempotent-safe reads: rebuild from Tier-1 is always
      correct (slower but bit-identical).
    * T3-MUST-NOT-1 — no bypass of kb-manager for KB content.

Tech choice: sqlite (stdlib) + FTS5 virtual table. Per
`references/storage-tech-stack.md` §8 committee vote (0.85 confidence).

Default path:
    <project>/.kiho/state/tier3/skill-catalog.sqlite

Lifecycle:
    * CEO INITIALIZE calls `build(force=False)`. If the file is missing,
      stale (any SKILL.md mtime > recorded disk_mtime), or hash mismatches,
      the index is rebuilt from scratch. Otherwise the existing file is
      reused.
    * Turn-end: CEO or operator runs `--evict` to delete the file. Any
      stale file on disk is also acceptable — next INITIALIZE will rebuild.

Usage:
    skill_catalog_index.py build         [--plugin-root .] [--force]
    skill_catalog_index.py query-facet   --capability CAP --domain DOM ...
    skill_catalog_index.py query-fts     "query string"
    skill_catalog_index.py evict
    skill_catalog_index.py parity-test   (compares indexed results to re-parse)

Exit codes (v5.15.2 convention):
    0 — success
    1 — policy violation (parity-test failure; stale index refused)
    2 — usage error (bad arguments, missing paths)
    3 — internal error

Grounding:
    * references/storage-architecture.md §Tier-3 guardrails
    * references/data-storage-matrix.md §8 skill-catalog-index
    * references/storage-tech-stack.md §8 SQLite FTS5 T3 session-scope
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

# Best-effort telemetry. Missing storage_telemetry.py MUST NOT break the pilot.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import storage_telemetry as _tel  # type: ignore
except ImportError:  # pragma: no cover
    _tel = None  # type: ignore


def _emit(op: str, plugin_root: Path, **fields) -> None:
    if _tel is None:
        return
    try:
        _tel.record(op=op, plugin_root=plugin_root, extra=fields)
    except Exception:  # pragma: no cover — telemetry is best-effort
        pass


# --- frontmatter helpers (stdlib-only YAML subset) --------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _get_field(block: str, key: str) -> str | None:
    """Return the value of a top-level `key: value` line in a frontmatter block.

    Handles inline values only. For nested fields (metadata.kiho.*), use
    _get_kiho_field.
    """
    m = re.search(
        rf"^\s*{re.escape(key)}\s*:\s*(.+?)\s*$",
        block,
        re.MULTILINE,
    )
    return m.group(1).strip() if m else None


def _get_kiho_field(block: str, field: str) -> str | None:
    """Return the value of metadata.kiho.<field>: line. Supports inline-list."""
    # Match "kiho:" section start, then indented `<field>: value` within
    # a reasonable window. This is a regex hack, not a real YAML parser,
    # but it's deterministic and sufficient for kiho's frontmatter shape.
    m = re.search(
        rf"^\s*kiho\s*:\s*\n((?:[ \t]+.+\n)+)",
        block + "\n",
        re.MULTILINE,
    )
    if not m:
        return None
    kiho_block = m.group(1)
    m2 = re.search(
        rf"^[ \t]*{re.escape(field)}\s*:\s*(.+?)\s*$",
        kiho_block,
        re.MULTILINE,
    )
    return m2.group(1).strip() if m2 else None


def _parse_list_value(raw: str | None) -> list[str]:
    """Parse YAML-ish inline-list or comma-separated values into a list of strings."""
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    items: list[str] = []
    for part in raw.split(","):
        p = part.strip().strip("'").strip('"')
        if p:
            items.append(p)
    return items


def extract_skill_metadata(path: Path, skills_root: Path) -> dict | None:
    """Return a normalized metadata dict for one SKILL.md, or None on failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    block = m.group(1)

    name = _get_field(block, "name") or path.parent.name
    description = _get_field(block, "description") or ""
    version = _get_field(block, "version") or ""
    lifecycle = _get_field(block, "lifecycle") or ""

    capability = _get_kiho_field(block, "capability") or ""
    topic_tags_raw = _get_kiho_field(block, "topic_tags")
    topic_tags = _parse_list_value(topic_tags_raw)
    requires = _parse_list_value(_get_kiho_field(block, "requires"))
    mentions = _parse_list_value(_get_kiho_field(block, "mentions"))
    solves = _get_kiho_field(block, "solves") or ""

    rel = path.relative_to(skills_root).as_posix()
    parts = rel.split("/")
    # parts looks like: <domain>/<sub_domain>/<slug>/SKILL.md
    # OR:               <domain>/<slug>/SKILL.md
    domain = parts[0] if len(parts) >= 2 else ""
    if len(parts) >= 4:
        sub_domain = parts[1]
    else:
        sub_domain = ""

    # Stable skill_id: prefer name (agentskills.io canonical); fallback to relative path.
    skill_id = name.strip() or rel

    try:
        disk_mtime = int(path.stat().st_mtime)
    except OSError:
        disk_mtime = 0

    return {
        "skill_id": skill_id,
        "name": name,
        "domain": domain,
        "sub_domain": sub_domain,
        "description": description.strip().strip('"').strip("'"),
        "capability": capability,
        "requires": ",".join(requires),
        "mentions": ",".join(mentions),
        "topic_tags": ",".join(topic_tags),
        "version": version,
        "solves": solves,
        "lifecycle": lifecycle,
        "path": rel,
        "disk_mtime": disk_mtime,
    }


# --- sqlite schema + build --------------------------------------------------

_SCHEMA = """
CREATE TABLE skills (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    domain TEXT,
    sub_domain TEXT,
    description TEXT,
    capability TEXT,
    requires TEXT,
    mentions TEXT,
    topic_tags TEXT,
    version TEXT,
    solves TEXT,
    lifecycle TEXT,
    path TEXT,
    disk_mtime INTEGER
);

CREATE INDEX idx_capability ON skills(capability);
CREATE INDEX idx_domain ON skills(domain);
CREATE INDEX idx_lifecycle ON skills(lifecycle);

CREATE VIRTUAL TABLE skills_fts USING fts5(
    name, description, capability, topic_tags,
    content=''
);

CREATE TABLE kiho_index_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _compute_skills_hash(rows: list[dict]) -> str:
    """Deterministic hash of the skills set (id + disk_mtime)."""
    h = hashlib.sha256()
    for r in sorted(rows, key=lambda x: x["skill_id"]):
        h.update(f"{r['skill_id']}:{r['disk_mtime']}".encode("utf-8"))
    return h.hexdigest()


def _scan_all(skills_root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(skills_root.rglob("SKILL.md")):
        meta = extract_skill_metadata(path, skills_root)
        if meta is not None:
            rows.append(meta)
    return rows


def _write_db(db_path: Path, rows: list[dict], skills_root: Path) -> dict:
    """Build a fresh db at db_path. Returns a summary dict."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        with conn:
            for r in rows:
                conn.execute(
                    """
                    INSERT INTO skills (
                        skill_id, name, domain, sub_domain, description,
                        capability, requires, mentions, topic_tags,
                        version, solves, lifecycle, path, disk_mtime
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r["skill_id"], r["name"], r["domain"], r["sub_domain"],
                        r["description"], r["capability"], r["requires"],
                        r["mentions"], r["topic_tags"], r["version"],
                        r["solves"], r["lifecycle"], r["path"], r["disk_mtime"],
                    ),
                )
                conn.execute(
                    "INSERT INTO skills_fts (rowid, name, description, capability, topic_tags) "
                    "VALUES ((SELECT rowid FROM skills WHERE skill_id=?), ?, ?, ?, ?)",
                    (
                        r["skill_id"], r["name"], r["description"],
                        r["capability"], r["topic_tags"],
                    ),
                )
            conn.execute(
                "INSERT INTO kiho_index_meta (key, value) VALUES (?, ?)",
                ("skills_hash", _compute_skills_hash(rows)),
            )
            conn.execute(
                "INSERT INTO kiho_index_meta (key, value) VALUES (?, ?)",
                (
                    "built_at",
                    _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            conn.execute(
                "INSERT INTO kiho_index_meta (key, value) VALUES (?, ?)",
                ("skills_root", str(skills_root)),
            )
        return {
            "built": True,
            "skills_indexed": len(rows),
            "db_path": str(db_path),
        }
    finally:
        conn.close()


def _is_stale(db_path: Path, rows_current: list[dict]) -> bool:
    """Return True if the db does not exist or its hash differs from current skills."""
    if not db_path.exists():
        return True
    try:
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.execute(
                "SELECT value FROM kiho_index_meta WHERE key='skills_hash'"
            )
            row = cur.fetchone()
            if row is None:
                return True
            recorded = row[0]
            current = _compute_skills_hash(rows_current)
            return recorded != current
        finally:
            conn.close()
    except sqlite3.Error:
        return True


def build_index(
    plugin_root: Path,
    db_path: Path | None = None,
    force: bool = False,
) -> dict:
    """Build (or reuse) the Tier-3 skill-catalog sqlite. Returns summary dict."""
    skills_root = plugin_root / "skills"
    if db_path is None:
        db_path = plugin_root / ".kiho" / "state" / "tier3" / "skill-catalog.sqlite"
    start = time.perf_counter()
    rows = _scan_all(skills_root)
    if not force and not _is_stale(db_path, rows):
        elapsed = int((time.perf_counter() - start) * 1000)
        _emit(
            "index.reuse", plugin_root,
            key="skill-catalog", duration_ms=elapsed, skills_indexed=len(rows),
        )
        return {
            "built": False,
            "reason": "hash_match",
            "skills_indexed": len(rows),
            "db_path": str(db_path),
            "elapsed_ms": elapsed,
        }
    summary = _write_db(db_path, rows, skills_root)
    elapsed = int((time.perf_counter() - start) * 1000)
    summary["elapsed_ms"] = elapsed
    _emit(
        "index.build", plugin_root,
        key="skill-catalog", duration_ms=elapsed,
        skills_indexed=summary.get("skills_indexed"),
    )
    return summary


def evict(db_path: Path, plugin_root: Path | None = None) -> dict:
    existed = db_path.exists()
    if existed:
        db_path.unlink()
    if plugin_root is not None:
        _emit("index.evict", plugin_root, key="skill-catalog", existed=existed)
    return {"evicted": existed, "db_path": str(db_path)}


# --- query helpers ----------------------------------------------------------

def _connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(
            f"index not built at {db_path}; run `skill_catalog_index.py build` first"
        )
    return sqlite3.connect(db_path)


def query_facet(
    db_path: Path,
    capability: str | None = None,
    domain: str | None = None,
    topic_tag: str | None = None,
    lifecycle: str | None = None,
    plugin_root: Path | None = None,
) -> list[dict]:
    start = time.perf_counter()
    clauses: list[str] = []
    params: list = []
    if capability:
        clauses.append("capability = ?")
        params.append(capability)
    if domain:
        clauses.append("domain = ?")
        params.append(domain)
    if lifecycle:
        clauses.append("lifecycle = ?")
        params.append(lifecycle)
    if topic_tag:
        # topic_tags is comma-separated; LIKE match surrounded by commas
        clauses.append("(',' || topic_tags || ',') LIKE ?")
        params.append(f"%,{topic_tag},%")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT skill_id, name, domain, capability, topic_tags, path FROM skills{where} ORDER BY skill_id"
    conn = _connect(db_path)
    try:
        cur = conn.execute(sql, params)
        cols = [c[0] for c in cur.description]
        results = [dict(zip(cols, row)) for row in cur.fetchall()]
        if plugin_root is not None:
            _emit(
                "query.facet", plugin_root,
                key="skill-catalog",
                duration_ms=int((time.perf_counter() - start) * 1000),
                result_count=len(results),
                facets=len(clauses),
            )
        return results
    finally:
        conn.close()


def query_fts(
    db_path: Path, query: str, limit: int = 10, plugin_root: Path | None = None,
) -> list[dict]:
    start = time.perf_counter()
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT s.skill_id, s.name, s.description, s.path, bm25(skills_fts) AS rank
            FROM skills_fts
            JOIN skills s ON s.rowid = skills_fts.rowid
            WHERE skills_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
        cols = [c[0] for c in cur.description]
        results = [dict(zip(cols, row)) for row in cur.fetchall()]
        if plugin_root is not None:
            _emit(
                "query.fts", plugin_root,
                key="skill-catalog",
                duration_ms=int((time.perf_counter() - start) * 1000),
                result_count=len(results),
                query_len=len(query),
            )
        return results
    finally:
        conn.close()


# --- parity test ------------------------------------------------------------

def parity_test(plugin_root: Path, db_path: Path | None = None) -> dict:
    """Compare indexed queries vs re-parse ground truth.

    Builds a fresh index, then for each of a small fixed query set, compares
    (a) the indexed result and (b) a naive re-parse of all SKILL.md files.
    Must match exactly for the pilot to be considered proven.
    """
    skills_root = plugin_root / "skills"
    if db_path is None:
        db_path = plugin_root / ".kiho" / "state" / "tier3" / "skill-catalog.sqlite"
    build_summary = build_index(plugin_root, db_path=db_path, force=True)

    ground_truth_rows = _scan_all(skills_root)
    gt_capabilities: dict[str, set[str]] = {}
    gt_domains: dict[str, set[str]] = {}
    for r in ground_truth_rows:
        gt_capabilities.setdefault(r["capability"] or "", set()).add(r["skill_id"])
        gt_domains.setdefault(r["domain"] or "", set()).add(r["skill_id"])

    # Query 1: all capabilities
    capability_checks: list[dict] = []
    for cap, expected in sorted(gt_capabilities.items()):
        if not cap:
            continue
        indexed = {r["skill_id"] for r in query_facet(db_path, capability=cap)}
        capability_checks.append({
            "capability": cap,
            "expected_count": len(expected),
            "indexed_count": len(indexed),
            "match": expected == indexed,
            "missing_from_index": sorted(expected - indexed),
            "extra_in_index": sorted(indexed - expected),
        })

    # Query 2: all domains
    domain_checks: list[dict] = []
    for dom, expected in sorted(gt_domains.items()):
        if not dom:
            continue
        indexed = {r["skill_id"] for r in query_facet(db_path, domain=dom)}
        domain_checks.append({
            "domain": dom,
            "expected_count": len(expected),
            "indexed_count": len(indexed),
            "match": expected == indexed,
        })

    all_match = (
        all(c["match"] for c in capability_checks)
        and all(c["match"] for c in domain_checks)
    )
    return {
        "parity_ok": all_match,
        "build_summary": build_summary,
        "capability_checks": capability_checks,
        "domain_checks": domain_checks,
        "total_skills": len(ground_truth_rows),
    }


# --- CLI --------------------------------------------------------------------

def _plugin_root_default() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__ or "")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="Build (or reuse) the sqlite index")
    pb.add_argument("--plugin-root", default=str(_plugin_root_default()))
    pb.add_argument("--db-path", default=None)
    pb.add_argument("--force", action="store_true", help="Rebuild even if hash matches")

    pq = sub.add_parser("query-facet", help="Faceted query")
    pq.add_argument("--plugin-root", default=str(_plugin_root_default()))
    pq.add_argument("--db-path", default=None)
    pq.add_argument("--capability", default=None)
    pq.add_argument("--domain", default=None)
    pq.add_argument("--topic-tag", default=None)
    pq.add_argument("--lifecycle", default=None)

    pf = sub.add_parser("query-fts", help="Full-text search via FTS5")
    pf.add_argument("query", help="FTS5 MATCH expression")
    pf.add_argument("--plugin-root", default=str(_plugin_root_default()))
    pf.add_argument("--db-path", default=None)
    pf.add_argument("--limit", type=int, default=10)

    pe = sub.add_parser("evict", help="Delete the sqlite file (session-scope eviction)")
    pe.add_argument("--plugin-root", default=str(_plugin_root_default()))
    pe.add_argument("--db-path", default=None)

    pt = sub.add_parser("parity-test", help="Compare indexed queries vs re-parse ground truth")
    pt.add_argument("--plugin-root", default=str(_plugin_root_default()))
    pt.add_argument("--db-path", default=None)

    try:
        args = p.parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    try:
        plugin_root = Path(args.plugin_root).resolve()
        db_path = Path(args.db_path).resolve() if args.db_path else None

        if args.cmd == "build":
            summary = build_index(plugin_root, db_path=db_path, force=args.force)
            print(json.dumps(summary, indent=2))
            return 0
        if args.cmd == "query-facet":
            if db_path is None:
                db_path = plugin_root / ".kiho" / "state" / "tier3" / "skill-catalog.sqlite"
            results = query_facet(
                db_path,
                capability=args.capability,
                domain=args.domain,
                topic_tag=args.topic_tag,
                lifecycle=args.lifecycle,
                plugin_root=plugin_root,
            )
            print(json.dumps({"count": len(results), "results": results}, indent=2))
            return 0
        if args.cmd == "query-fts":
            if db_path is None:
                db_path = plugin_root / ".kiho" / "state" / "tier3" / "skill-catalog.sqlite"
            results = query_fts(
                db_path, args.query, limit=args.limit, plugin_root=plugin_root,
            )
            print(json.dumps({"count": len(results), "results": results}, indent=2))
            return 0
        if args.cmd == "evict":
            if db_path is None:
                db_path = plugin_root / ".kiho" / "state" / "tier3" / "skill-catalog.sqlite"
            r = evict(db_path, plugin_root=plugin_root)
            print(json.dumps(r, indent=2))
            return 0
        if args.cmd == "parity-test":
            summary = parity_test(plugin_root, db_path=db_path)
            print(json.dumps(summary, indent=2))
            return 0 if summary["parity_ok"] else 1

        p.print_help()
        return 2
    except FileNotFoundError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover — defensive
        print(json.dumps({"status": "error", "error": repr(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(3)
