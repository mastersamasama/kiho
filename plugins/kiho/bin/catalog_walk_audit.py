#!/usr/bin/env python3
"""
catalog_walk_audit.py — v5.16 weekly catalog health audit.

Consolidated weekly health check for the kiho catalog. Kb-manager runs
this on schedule (or on demand) to surface latent issues that don't
block skill-create but accumulate over time. Three checks:

  1. Orphan skills — ACTIVE skills with zero reverse dependencies
     (no agent portfolio, no parent_of, no mentions, no wiki-links).
     Grace period: skills <30 days old are excluded. Self-hosted meta
     skills are excluded (they're invoked dynamically, not by static
     portfolio lookup).

  2. Stale DRAFTs — drafts in .kiho/state/drafts/ older than 90 days
     (warn) or 180 days (error). Pollutes kb-manager's workload.

  3. Confusability drift — mean-pairwise description Jaccard across the
     whole catalog. Baseline Apr 2026 is 0.0146 (max 0.1049). Warn at
     0.05, error at 0.10.

Output: JSON summary + per-check findings. Runs in <5s on the current
38-skill tree.

Grounding: v5.16 plan Stage F. Replaces the demoted old Gates 23/24/25
from the initial v5.16 draft with one cron-friendly script.

Usage:
    catalog_walk_audit.py [--drafts-dir <path>]
                           [--orphan-grace-days 30]
                           [--draft-warn-days 90] [--draft-err-days 180]
                           [--confusability-warn 0.05] [--confusability-err 0.10]

Exit codes (0/1/2/3):
    0 — all checks pass (no warnings, no errors)
    1 — policy violation: at least one error-level finding
    2 — usage error
    3 — internal error

Advisory note: warnings do not fail the script (exit 0) unless
--fail-on-warn is passed. Errors always fail.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent


def _safe_telemetry(op: str, key: str, duration_ms: int, extra: dict) -> None:
    """Best-effort telemetry emit (v5.19.5 N2). Swallows ImportError and any
    record() exception; MUST NOT break the audit pipeline."""
    try:
        from storage_telemetry import record as _record
    except ImportError:
        return
    try:
        _record(
            op=op,
            key=key,
            duration_ms=duration_ms,
            plugin_root=PLUGIN_ROOT,
            extra=extra,
        )
    except Exception:  # pragma: no cover
        pass
SKILLS_DIR = PLUGIN_ROOT / "skills"
RDEPS_SCRIPT = SCRIPT_DIR / "kiho_rdeps.py"
SIMILARITY_SCRIPT = (
    PLUGIN_ROOT / "skills" / "_meta" / "skill-create" / "scripts" / "similarity_scan.py"
)

# Self-hosted meta skills that are invoked dynamically; never "orphans"
SELF_HOSTED_META = {
    "skill-create", "skill-find", "skill-improve", "skill-derive",
    "skill-learn", "skill-deprecate", "evolution-scan", "soul-apply-override",
}


def read_skill_id(skill_dir: Path) -> str:
    sid_path = skill_dir / ".skill_id"
    if sid_path.exists():
        return sid_path.read_text(encoding="utf-8").strip()
    return ""


def extract_frontmatter_field(skill_md: Path, field: str) -> str:
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        colon_idx = line.find(":")
        if colon_idx == -1:
            continue
        key = line[:colon_idx].strip()
        if key == field:
            return line[colon_idx + 1:].strip().strip('"').strip("'")
    return ""


def discover_active_skills() -> list[dict]:
    """Return ACTIVE (non-deprecated) skills as list of dicts."""
    skills: list[dict] = []
    for domain in ("_meta", "core", "kb", "memory", "engineering"):
        domain_dir = SKILLS_DIR / domain
        if not domain_dir.is_dir():
            continue
        for child in sorted(domain_dir.iterdir()):
            if not child.is_dir():
                continue
            flat = child / "SKILL.md"
            if flat.is_file():
                _collect_skill(flat, child, domain, None, skills)
                continue
            for grand in sorted(child.iterdir()):
                if not grand.is_dir():
                    continue
                nested = grand / "SKILL.md"
                if nested.is_file():
                    _collect_skill(nested, grand, domain, child.name, skills)
    return skills


def _collect_skill(
    skill_md: Path,
    skill_dir: Path,
    domain: str,
    sub_domain: str | None,
    out: list[dict],
) -> None:
    sid = read_skill_id(skill_dir)
    if not sid:
        return
    lifecycle = extract_frontmatter_field(skill_md, "lifecycle") or "active"
    if lifecycle == "deprecated":
        return
    name = extract_frontmatter_field(skill_md, "name") or skill_dir.name
    out.append({
        "id": sid,
        "name": name,
        "domain": domain,
        "sub_domain": sub_domain,
        "path": str(skill_md.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
        "skill_dir": skill_dir,
    })


def check_orphans(
    skills: list[dict],
    grace_days: int,
) -> list[dict]:
    """A skill is an orphan if kiho_rdeps reports zero consumers across
    all six forward-edge sources AND it's not self-hosted meta AND it's
    older than the grace period."""
    if not RDEPS_SCRIPT.exists():
        return [{"status": "rdeps_missing", "path": str(RDEPS_SCRIPT)}]
    orphans: list[dict] = []
    now = dt.datetime.now(dt.timezone.utc)
    for s in skills:
        if s["name"] in SELF_HOSTED_META:
            continue
        # Run kiho_rdeps on the skill's .skill_id
        result = subprocess.run(
            [sys.executable, str(RDEPS_SCRIPT), s["id"]],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            continue  # unknown error; skip
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        counts = payload.get("counts", {})
        total_refs = sum(counts.values())
        if total_refs > 0:
            continue
        # Age check via skill_dir mtime as a weak proxy for created_at
        try:
            mtime = dt.datetime.fromtimestamp(
                s["skill_dir"].stat().st_mtime, tz=dt.timezone.utc,
            )
            age_days = (now - mtime).days
        except OSError:
            age_days = 0
        if age_days < grace_days:
            continue
        orphans.append({
            "skill_id": s["id"],
            "name": s["name"],
            "path": s["path"],
            "age_days": age_days,
        })
    return orphans


def check_stale_drafts(
    drafts_dir: Path | None,
    warn_days: int,
    err_days: int,
) -> list[dict]:
    """Scan .kiho/state/drafts/*/SKILL.md for age."""
    if drafts_dir is None or not drafts_dir.is_dir():
        return []
    now = dt.datetime.now(dt.timezone.utc)
    stale: list[dict] = []
    for child in sorted(drafts_dir.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            mtime = dt.datetime.fromtimestamp(
                skill_md.stat().st_mtime, tz=dt.timezone.utc,
            )
            age_days = (now - mtime).days
        except OSError:
            continue
        if age_days >= err_days:
            stale.append({"draft": child.name, "age_days": age_days, "level": "error"})
        elif age_days >= warn_days:
            stale.append({"draft": child.name, "age_days": age_days, "level": "warn"})
    return stale


def check_confusability(warn: float, err: float) -> dict:
    """Invoke similarity_scan.py --catalog-health if present."""
    if not SIMILARITY_SCRIPT.exists():
        return {"status": "similarity_script_missing"}
    result = subprocess.run(
        [sys.executable, str(SIMILARITY_SCRIPT), "--catalog-health"],
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        return {"status": "similarity_script_error", "stderr": result.stderr[:200]}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "similarity_bad_output", "stdout": result.stdout[:200]}
    mean_jaccard = payload.get("mean_pairwise_jaccard", 0.0)
    level = "ok"
    if mean_jaccard >= err:
        level = "error"
    elif mean_jaccard >= warn:
        level = "warn"
    return {
        "mean_pairwise_jaccard": mean_jaccard,
        "level": level,
        "warn_threshold": warn,
        "err_threshold": err,
    }


# v5.19.5 N4: semantic-embedding-cache revisit-trigger accounting.
# facet_walk.py writes one JSONL line per ceiling hit; this check rolls them
# up over the last 30 days and raises warn/error thresholds. Hitting the error
# threshold means the semantic-embedding-cache deferral (storage-tech-stack.md
# §6) should be re-opened for committee review.
EMBEDDING_TRIGGER_LOG = (
    PLUGIN_ROOT / ".kiho" / "state" / "tier3" / "semantic-embedding-triggers.jsonl"
)


def check_embedding_trigger(
    warn_threshold: int, err_threshold: int, window_days: int = 30
) -> dict:
    """Count rolling-<window_days> ceiling hits; warn at >=warn, error at >=err."""
    if not EMBEDDING_TRIGGER_LOG.exists():
        return {
            "status": "no_log",
            "level": "ok",
            "rolling_hit_count": 0,
            "window_days": window_days,
            "log_path": str(EMBEDDING_TRIGGER_LOG),
        }
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=window_days)
    hit_count = 0
    total_lines = 0
    try:
        with EMBEDDING_TRIGGER_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total_lines += 1
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = obj.get("ts", "")
                try:
                    ts_norm = ts.replace("Z", "+00:00")
                    t = dt.datetime.fromisoformat(ts_norm)
                    if t.tzinfo is None:
                        t = t.replace(tzinfo=dt.timezone.utc)
                except ValueError:
                    continue
                if t >= cutoff:
                    hit_count += 1
    except OSError:
        return {"status": "log_unreadable", "level": "ok"}

    level = "ok"
    if hit_count >= err_threshold:
        level = "error"
    elif hit_count >= warn_threshold:
        level = "warn"
    return {
        "rolling_hit_count": hit_count,
        "total_log_entries": total_lines,
        "window_days": window_days,
        "warn_threshold": warn_threshold,
        "err_threshold": err_threshold,
        "level": level,
        "log_path": str(EMBEDDING_TRIGGER_LOG),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--drafts-dir", type=str, default=None,
                   help=".kiho/state/drafts path (auto-skipped if absent)")
    p.add_argument("--orphan-grace-days", type=int, default=30)
    p.add_argument("--draft-warn-days", type=int, default=90)
    p.add_argument("--draft-err-days", type=int, default=180)
    p.add_argument("--confusability-warn", type=float, default=0.05)
    p.add_argument("--confusability-err", type=float, default=0.10)
    p.add_argument("--fail-on-warn", action="store_true",
                   help="exit 1 on warn-level findings too (default: only on errors)")
    p.add_argument("--embed-trigger-warn", type=int, default=5,
                   help="warn threshold for rolling-30d semantic-embedding ceiling hits (default: 5)")
    p.add_argument("--embed-trigger-err", type=int, default=15,
                   help="error threshold for rolling-30d semantic-embedding ceiling hits (default: 15)")
    return p.parse_args()


def main() -> int:
    try:
        args = parse_args()
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2
    try:
        skills = discover_active_skills()

        _t0 = time.perf_counter()
        orphans = check_orphans(skills, args.orphan_grace_days)
        _dt_orphan = int((time.perf_counter() - _t0) * 1000)

        _t0 = time.perf_counter()
        drafts_dir = Path(args.drafts_dir) if args.drafts_dir else None
        stale = check_stale_drafts(drafts_dir, args.draft_warn_days, args.draft_err_days)
        _dt_stale = int((time.perf_counter() - _t0) * 1000)

        _t0 = time.perf_counter()
        confus = check_confusability(args.confusability_warn, args.confusability_err)
        _dt_confus = int((time.perf_counter() - _t0) * 1000)

        _t0 = time.perf_counter()
        embed_trigger = check_embedding_trigger(
            args.embed_trigger_warn, args.embed_trigger_err
        )
        _dt_embed = int((time.perf_counter() - _t0) * 1000)

        error_count = 0
        warn_count = 0
        orphan_warn = 0
        if orphans and "status" not in orphans[0]:
            orphan_warn = len(orphans)
            warn_count += orphan_warn
        stale_warn = 0
        stale_err = 0
        for s in stale:
            if s.get("level") == "error":
                error_count += 1
                stale_err += 1
            elif s.get("level") == "warn":
                warn_count += 1
                stale_warn += 1
        confus_level = confus.get("level", "ok")
        if confus_level == "error":
            error_count += 1
        elif confus_level == "warn":
            warn_count += 1
        embed_level = embed_trigger.get("level", "ok")
        if embed_level == "error":
            error_count += 1
        elif embed_level == "warn":
            warn_count += 1

        # Per-check telemetry (v5.19.5 N2)
        _safe_telemetry(
            op="catalog_audit", key="orphan",
            duration_ms=_dt_orphan,
            extra={"warn_count": orphan_warn, "error_count": 0, "total_scanned": len(skills)},
        )
        _safe_telemetry(
            op="catalog_audit", key="stale_draft",
            duration_ms=_dt_stale,
            extra={"warn_count": stale_warn, "error_count": stale_err},
        )
        _safe_telemetry(
            op="catalog_audit", key="confusability",
            duration_ms=_dt_confus,
            extra={
                "warn_count": 1 if confus_level == "warn" else 0,
                "error_count": 1 if confus_level == "error" else 0,
                "level": confus_level,
            },
        )
        _safe_telemetry(
            op="catalog_audit", key="embedding_trigger",
            duration_ms=_dt_embed,
            extra={
                "warn_count": 1 if embed_level == "warn" else 0,
                "error_count": 1 if embed_level == "error" else 0,
                "level": embed_level,
                "rolling_hit_count": embed_trigger.get("rolling_hit_count", 0),
            },
        )

        summary = {
            "total_active_skills": len(skills),
            "orphans": orphans,
            "stale_drafts": stale,
            "confusability": confus,
            "embedding_trigger": embed_trigger,
            "warn_count": warn_count,
            "error_count": error_count,
        }
        sys.stdout.write(json.dumps(summary, indent=2) + "\n")
        if error_count > 0:
            return 1
        if warn_count > 0 and args.fail_on_warn:
            return 1
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"catalog_walk_audit: internal error: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
