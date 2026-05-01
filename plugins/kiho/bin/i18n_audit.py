#!/usr/bin/env python3
"""kiho v6.5 i18n quality audit — deterministic 5-check framework.

Audits a kiho-using project's translation health:
  1. Locale parity — flatten each locale JSON to a key-set; diff vs canonical.
  2. Placeholder integrity — `{var}` and ICU `{count, plural, ...}` set parity
     across locales (allow reordering; require equality).
  3. Untranslated keys — non-canonical locale value == canonical value, minus
     allowlisted brands / proper-noun keys.
  4. Hard-coded user-visible strings — regex scan code-glob for JSX text,
     accessibilityLabel literals, Alert.alert(...) literals, ActionSheet
     options literals. Skip __tests__/, *.test.*, *.fixture.* paths.
  5. Dead-key detection — JSON keys never referenced via `t('key')` and not
     covered by a `// i18n-keep prefix=...` escape hatch.

Style mirrors `bin/ceo_behavior_audit.py`: argparse, JSON or markdown out,
deterministic exit-code matrix.

Exit codes (per plan zany-greeting-cookie §B4):
  0 — clean
  1 — warn (dead-keys only; never fails CI by default)
  2 — fail (parity break / placeholder mismatch / hard-coded strings)
  3 — crash (uncaught exception or invalid input)

`--strict-warn` promotes warns to fails (returns 2 instead of 1).

Stdlib only — no PyYAML, no requests. Python 3.11+ for tomllib.

Usage:
  python i18n_audit.py \\
    --project-root /path/to/project \\
    --locales-dir apps/mobile/src/i18n/locales \\
    --code-glob "apps/mobile/src/**/*.{ts,tsx}" \\
    --canonical en \\
    --config .kiho/config/i18n-allowlist.toml \\
    --json-out i18n-audit.json \\
    --md-out i18n-audit.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[import-not-found]  # py311+ stdlib
except ImportError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore[import-not-found]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

EXIT_CLEAN = 0
EXIT_WARN = 1
EXIT_FAIL = 2
EXIT_CRASH = 3

# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    check: str          # parity | placeholder | untranslated | hardcoded | dead
    severity: str       # fail | warn | info
    locale: str
    key: str
    evidence: str       # "file:line" or "key1,key2,..."
    suggestion: str = ""


@dataclass
class AuditState:
    findings: list[Finding] = field(default_factory=list)

    def add(self, **kw: Any) -> None:
        self.findings.append(Finding(**kw))


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


def load_config(path: Path | None) -> dict[str, Any]:
    """Load i18n-allowlist.toml. Returns sane defaults if path is None/missing."""
    defaults: dict[str, Any] = {
        "canonical": "en",
        "brands": {"values": [], "keys": {"match": []}},
        "hardcoded": {"allow_paths": {"patterns": [
            "**/__tests__/**", "**/*.test.ts", "**/*.test.tsx",
            "**/*.fixture.ts", "**/*.fixture.tsx",
        ]}},
        "deadkey": {
            "allow_keys": {"prefixes": []},
            "amnesty": {"keys": []},
        },
    }
    if not path or not path.exists():
        return defaults
    if tomllib is None:
        raise RuntimeError("Python 3.11+ tomllib required to load TOML config")
    with path.open("rb") as f:
        data = tomllib.load(f)
    # Shallow merge defaults with user data
    merged = defaults.copy()
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return merged


# ---------------------------------------------------------------------------
# JSON flattening
# ---------------------------------------------------------------------------


def flatten(obj: Any, prefix: str = "") -> dict[str, str]:
    """Recursively flatten a nested JSON dict into dotted keys.

    Lists are joined into a single comma-separated string for placeholder
    inspection (uncommon in i18n payloads but tolerated).
    """
    out: dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            child_key = f"{prefix}.{k}" if prefix else k
            out.update(flatten(v, child_key))
    elif isinstance(obj, list):
        out[prefix] = ",".join(str(x) for x in obj)
    elif obj is None:
        out[prefix] = ""
    else:
        out[prefix] = str(obj)
    return out


def load_locales(locales_dir: Path) -> dict[str, dict[str, str]]:
    """Return {locale_name: flat_keymap}. Each *.json file under locales_dir
    is treated as one locale; its stem is the locale name."""
    out: dict[str, dict[str, str]] = {}
    if not locales_dir.exists():
        return out
    for path in sorted(locales_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out[path.stem] = flatten(data)
    return out


# ---------------------------------------------------------------------------
# Placeholder extraction
# ---------------------------------------------------------------------------

# Match {var} but NOT escaped {{...}}; also match the OUTER {x, plural, ...}
# ICU shape — we only compare top-level placeholder names.
PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")
ICU_TOP_RE = re.compile(r"\{\s*(\w+)\s*,\s*(plural|select|selectordinal)\b")


def extract_placeholders(value: str) -> set[str]:
    """Return the set of top-level placeholder names in an i18n string.

    Handles three shapes:
      - simple `{name}` → adds "name"
      - ICU `{count, plural, one {# foo} other {# bar}}` → adds "count:plural"
      - escaped `{{literal}}` → ignored
    """
    if not value:
        return set()
    placeholders: set[str] = set()

    # ICU constructs first — they contain nested {...} we must not double-count.
    icu_matches = list(ICU_TOP_RE.finditer(value))
    icu_spans: list[tuple[int, int]] = []
    for m in icu_matches:
        name, kind = m.group(1), m.group(2)
        placeholders.add(f"{name}:{kind}")
        # Find the matching closing brace for this ICU expression
        start = m.start()
        depth = 0
        end = start
        for i in range(start, len(value)):
            ch = value[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        icu_spans.append((start, end))

    # Simple {var} placeholders — skip anything inside an ICU span
    for m in PLACEHOLDER_RE.finditer(value):
        s = m.start()
        if any(span_s <= s < span_e for span_s, span_e in icu_spans):
            continue
        body = m.group(1).strip()
        # Skip ICU sub-pieces like "one {...}" — those start with a keyword,
        # but at top level we filtered those out above.
        if "," in body or body in ("one", "other", "few", "many", "two", "zero"):
            continue
        # Skip leading "#" — ICU number marker (shouldn't reach here, defensive)
        if body.startswith("#"):
            continue
        # Skip escaped {{...}} (the regex already disallows nested braces)
        placeholders.add(body)
    return placeholders


# ---------------------------------------------------------------------------
# Check 1 — locale parity
# ---------------------------------------------------------------------------


def check_parity(
    locales: dict[str, dict[str, str]], canonical: str, state: AuditState
) -> None:
    canon = locales.get(canonical)
    if canon is None:
        state.add(
            check="parity", severity="fail", locale=canonical, key="<root>",
            evidence=f"canonical locale '{canonical}.json' not found",
            suggestion=f"create {canonical}.json or pass --canonical with a valid locale",
        )
        return
    canon_keys = set(canon.keys())
    for loc, kv in locales.items():
        if loc == canonical:
            continue
        loc_keys = set(kv.keys())
        missing = sorted(canon_keys - loc_keys)
        extra = sorted(loc_keys - canon_keys)
        for k in missing:
            state.add(
                check="parity", severity="fail", locale=loc, key=k,
                evidence=f"present in {canonical}.json, absent in {loc}.json",
                suggestion=f"add '{k}' to {loc}.json (translate from canonical)",
            )
        for k in extra:
            state.add(
                check="parity", severity="fail", locale=loc, key=k,
                evidence=f"present in {loc}.json, absent in {canonical}.json",
                suggestion=f"remove '{k}' from {loc}.json or add it to {canonical}.json",
            )


# ---------------------------------------------------------------------------
# Check 2 — placeholder integrity
# ---------------------------------------------------------------------------


def check_placeholder(
    locales: dict[str, dict[str, str]], canonical: str, state: AuditState
) -> None:
    canon = locales.get(canonical) or {}
    for key, c_val in canon.items():
        c_set = extract_placeholders(c_val)
        if not c_set:
            continue
        for loc, kv in locales.items():
            if loc == canonical:
                continue
            if key not in kv:
                continue  # parity check already flagged
            l_set = extract_placeholders(kv[key])
            if l_set != c_set:
                missing = sorted(c_set - l_set)
                surplus = sorted(l_set - c_set)
                bits = []
                if missing:
                    bits.append(f"missing {missing}")
                if surplus:
                    bits.append(f"surplus {surplus}")
                state.add(
                    check="placeholder", severity="fail", locale=loc, key=key,
                    evidence=f"canonical={sorted(c_set)} vs {loc}={sorted(l_set)}; {'; '.join(bits)}",
                    suggestion=f"align placeholder set with {canonical}.json (set equality required, order free)",
                )


# ---------------------------------------------------------------------------
# Check 3 — untranslated keys
# ---------------------------------------------------------------------------


def _glob_match(pattern: str, key: str) -> bool:
    """Lightweight glob-ish match for allowlist['brands']['keys']['match']:
    supports '*' wildcard only, anchored at start by default.
    """
    rx = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
    return re.match(rx, key) is not None


def check_untranslated(
    locales: dict[str, dict[str, str]],
    canonical: str,
    config: dict[str, Any],
    state: AuditState,
) -> None:
    canon = locales.get(canonical) or {}
    brand_values = set(config.get("brands", {}).get("values", []) or [])
    brand_key_patterns = (
        config.get("brands", {}).get("keys", {}).get("match", []) or []
    )

    for loc, kv in locales.items():
        if loc == canonical:
            continue
        for key, c_val in canon.items():
            if key not in kv:
                continue
            if not c_val:
                continue
            if kv[key] != c_val:
                continue
            # Equal value — apply allowlists
            if c_val.strip() in brand_values:
                continue
            if any(_glob_match(p, key) for p in brand_key_patterns):
                continue
            # Pure punctuation / numbers / single-char are typically fine
            stripped = c_val.strip()
            if not stripped or re.fullmatch(r"[\W\d_]+", stripped):
                continue
            state.add(
                check="untranslated", severity="warn", locale=loc, key=key,
                evidence=f"{loc}.json value identical to {canonical}.json: {c_val!r}",
                suggestion=(
                    f"translate '{key}' for {loc}, OR add value to "
                    f"[brands].values, OR add key pattern to [brands.keys].match"
                ),
            )


# ---------------------------------------------------------------------------
# Code-glob expansion (stdlib only)
# ---------------------------------------------------------------------------


def expand_code_glob(project_root: Path, glob_pattern: str) -> list[Path]:
    """Expand a glob pattern that may contain {a,b} brace alternatives.

    pathlib.Path.glob does NOT understand braces, so we expand them manually
    into N patterns, then glob each.
    """
    patterns = _expand_braces(glob_pattern)
    out: list[Path] = []
    seen: set[Path] = set()
    for pat in patterns:
        for p in project_root.glob(pat):
            if p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
    return sorted(out)


def _expand_braces(pattern: str) -> list[str]:
    m = re.search(r"\{([^{}]+)\}", pattern)
    if not m:
        return [pattern]
    head, tail = pattern[: m.start()], pattern[m.end():]
    alts = m.group(1).split(",")
    out: list[str] = []
    for alt in alts:
        out.extend(_expand_braces(head + alt + tail))
    return out


def _path_matches_any(path: Path, patterns: list[str], project_root: Path) -> bool:
    """Test if path matches any glob pattern (relative to project_root)."""
    try:
        rel = path.relative_to(project_root).as_posix()
    except ValueError:
        rel = path.as_posix()
    for pat in patterns:
        # Normalize and convert to regex
        rx = _glob_to_regex(pat)
        if re.search(rx, rel):
            return True
    return False


def _glob_to_regex(pat: str) -> str:
    """Convert glob (with **, *, ?, {a,b}) to a regex string."""
    parts = _expand_braces(pat)
    if len(parts) > 1:
        return "(?:" + "|".join(_glob_to_regex(p) for p in parts) + ")"
    pat = parts[0]
    out = []
    i = 0
    while i < len(pat):
        c = pat[i]
        if c == "*":
            if i + 1 < len(pat) and pat[i + 1] == "*":
                out.append(".*")
                i += 2
                if i < len(pat) and pat[i] == "/":
                    i += 1
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == ".":
            out.append(r"\.")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Check 4 — hard-coded user-visible strings
# ---------------------------------------------------------------------------

# 4a: <Text>literal</Text> (and variants like <Text style={...}>literal</Text>)
HARDCODED_JSX_TEXT_RE = re.compile(
    r"<Text\b[^>]*>\s*([A-Z][A-Za-z][^<{}\n]{1,80})\s*</Text>",
)
# 4b: accessibilityLabel="literal" or accessibilityLabel={"literal"}
HARDCODED_A11Y_RE = re.compile(
    r'accessibilityLabel\s*=\s*\{?\s*["\']([^"\'\n]{2,120})["\']\s*\}?'
)
# 4c: Alert.alert("title", ...) or Alert.alert("title", "message", ...)
HARDCODED_ALERT_RE = re.compile(
    r'Alert\.alert\s*\(\s*["\']([^"\'\n]{2,120})["\']'
    r'(?:\s*,\s*["\']([^"\'\n]{2,200})["\'])?'
)
# 4c.1 (v6.5.1): split-finding variant of HARDCODED_ALERT_RE — emits a separate
# finding for the title literal AND the body literal so each can be tracked /
# i18n-keyed independently. Catches Alert.alert("Title","Body", ...) pairs
# where BOTH operands are string literals (not t() calls or variables).
ALERT_LITERAL_RE = re.compile(
    r'Alert\.alert\(\s*["\']([^"\'\n]+)["\']\s*,\s*["\']([^"\'\n]+)["\']'
)
# 4d: ActionSheetIOS.showActionSheetWithOptions({ options: [...literals...] })
ACTIONSHEET_BLOCK_RE = re.compile(
    r"ActionSheetIOS\.showActionSheetWithOptions\s*\(\s*\{[^}]*options\s*:\s*\[([^\]]*)\]",
    re.DOTALL,
)
ACTIONSHEET_LITERAL_RE = re.compile(r'["\']([^"\']{2,80})["\']')

# Heuristic: if a literal looks like dev-only console output (starts with
# "[debug]", "TODO", etc.) skip.
DEV_LOG_PREFIX_RE = re.compile(r"^\s*(?:\[(?:debug|dev|todo|fixme)\]|TODO|FIXME)", re.IGNORECASE)


def check_hardcoded(
    project_root: Path,
    code_glob: str,
    config: dict[str, Any],
    state: AuditState,
) -> None:
    allow_patterns = (
        config.get("hardcoded", {}).get("allow_paths", {}).get("patterns", []) or []
    )
    files = expand_code_glob(project_root, code_glob)
    for path in files:
        if _path_matches_any(path, allow_patterns, project_root):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(project_root).as_posix()
        _scan_jsx_text(text, rel, state)
        _scan_a11y(text, rel, state)
        _scan_alert(text, rel, state)
        _scan_actionsheet(text, rel, state)


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _scan_jsx_text(text: str, rel: str, state: AuditState) -> None:
    for m in HARDCODED_JSX_TEXT_RE.finditer(text):
        literal = m.group(1).strip()
        if not literal or DEV_LOG_PREFIX_RE.match(literal):
            continue
        # Skip pure numbers / symbols — already filtered by the leading [A-Z]
        line = _line_of(text, m.start())
        state.add(
            check="hardcoded", severity="fail", locale="-", key="<jsx-text>",
            evidence=f"{rel}:{line}",
            suggestion=f"replace `<Text>{literal}</Text>` with `<Text>{{t('<group>.<KEY>')}}</Text>` (literal: {literal!r})",
        )


def _scan_a11y(text: str, rel: str, state: AuditState) -> None:
    for m in HARDCODED_A11Y_RE.finditer(text):
        literal = m.group(1).strip()
        if not literal:
            continue
        line = _line_of(text, m.start())
        state.add(
            check="hardcoded", severity="fail", locale="-", key="<a11y-label>",
            evidence=f"{rel}:{line}",
            suggestion=f"replace accessibilityLabel={literal!r} with accessibilityLabel={{t('<group>.A11Y_<KEY>')}}",
        )


def _scan_alert(text: str, rel: str, state: AuditState) -> None:
    for m in HARDCODED_ALERT_RE.finditer(text):
        title = m.group(1).strip()
        msg = (m.group(2) or "").strip()
        line = _line_of(text, m.start())
        literal = f"{title!r}" + (f" / {msg!r}" if msg else "")
        state.add(
            check="hardcoded", severity="fail", locale="-", key="<alert>",
            evidence=f"{rel}:{line}",
            suggestion=f"replace Alert.alert({literal}) with Alert.alert(t('alerts.TITLE'), t('alerts.MESSAGE'))",
        )
    # v6.5.1: split-finding sweep — emit one finding per literal operand
    # (title + body) when BOTH are string literals. Lets callers track each
    # piece independently in their i18n key inventory.
    seen_offsets: set[int] = set()
    for m in ALERT_LITERAL_RE.finditer(text):
        if m.start() in seen_offsets:
            continue
        seen_offsets.add(m.start())
        title = m.group(1).strip()
        body = m.group(2).strip()
        line = _line_of(text, m.start())
        if title and not DEV_LOG_PREFIX_RE.match(title):
            state.add(
                check="hardcoded", severity="fail", locale="-",
                key="<alert-title>",
                evidence=f"{rel}:{line}",
                suggestion=f"replace Alert.alert title literal {title!r} with t('alerts.<KEY>_TITLE')",
            )
        if body and not DEV_LOG_PREFIX_RE.match(body):
            state.add(
                check="hardcoded", severity="fail", locale="-",
                key="<alert-body>",
                evidence=f"{rel}:{line}",
                suggestion=f"replace Alert.alert body literal {body!r} with t('alerts.<KEY>_BODY')",
            )


def _scan_actionsheet(text: str, rel: str, state: AuditState) -> None:
    for block_m in ACTIONSHEET_BLOCK_RE.finditer(text):
        body = block_m.group(1)
        line = _line_of(text, block_m.start())
        for lit in ACTIONSHEET_LITERAL_RE.finditer(body):
            literal = lit.group(1).strip()
            if not literal or DEV_LOG_PREFIX_RE.match(literal):
                continue
            state.add(
                check="hardcoded", severity="fail", locale="-",
                key="<actionsheet-option>",
                evidence=f"{rel}:{line}",
                suggestion=f"move ActionSheet option {literal!r} to t('actionsheet.<KEY>')",
            )


# ---------------------------------------------------------------------------
# Check 5 — dead-key detection
# ---------------------------------------------------------------------------

T_CALL_RE = re.compile(r"""\bt\s*\(\s*['"`]([^'"`]+)['"`]""")
KEEP_PREFIX_RE = re.compile(r"//\s*i18n-keep\s+prefix=([\w.\-]+)")
KEEP_FULL_RE = re.compile(r"//\s*i18n-keep\s+(?!prefix=)([\w.\-]+)")


def check_dead_keys(
    project_root: Path,
    code_glob: str,
    locales: dict[str, dict[str, str]],
    canonical: str,
    config: dict[str, Any],
    state: AuditState,
) -> None:
    canon = locales.get(canonical) or {}
    if not canon:
        return
    files = expand_code_glob(project_root, code_glob)
    referenced: set[str] = set()
    keep_prefixes: set[str] = set()
    keep_full: set[str] = set()
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in T_CALL_RE.finditer(text):
            referenced.add(m.group(1))
        for m in KEEP_PREFIX_RE.finditer(text):
            keep_prefixes.add(m.group(1))
        for m in KEEP_FULL_RE.finditer(text):
            keep_full.add(m.group(1))

    cfg_prefixes = set(
        config.get("deadkey", {}).get("allow_keys", {}).get("prefixes", []) or []
    )
    keep_prefixes |= cfg_prefixes
    amnesty = set(config.get("deadkey", {}).get("amnesty", {}).get("keys", []) or [])

    for key in sorted(canon.keys()):
        if key in referenced:
            continue
        if key in keep_full:
            continue
        if key in amnesty:
            continue
        if any(key.startswith(p) for p in keep_prefixes):
            continue
        state.add(
            check="dead", severity="warn", locale=canonical, key=key,
            evidence="no t('...') reference and no // i18n-keep escape hatch",
            suggestion=(
                f"remove '{key}' from {canonical}.json (and sibling locales), "
                f"OR add `// i18n-keep {key}` near the dynamic call site, "
                f"OR add prefix to [deadkey.allow_keys].prefixes in i18n-allowlist.toml"
            ),
        )


# ---------------------------------------------------------------------------
# Clarity heuristic v2 (stub — future work)
# ---------------------------------------------------------------------------


def _check_clarity_v2(*args: Any, **kw: Any) -> list[Finding]:  # noqa: ARG001 — v2 stub
    """v2 hook for glossary-driven clarity audit (e.g., 沖正→撤銷 guidance).

    Intentionally returns no findings in v6.5 ship. Wire-up will read
    `references/i18n-known-jargon.md` + project glossary.toml and emit
    info-severity suggestions only. TODO: implement in v6.6.
    """
    del args, kw  # silence unused-warning until v6.6 wires the call sites
    return []


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def to_summary(findings: list[Finding]) -> dict[str, Any]:
    by_sev = {"fail": 0, "warn": 0, "info": 0}
    for f in findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
    return {
        "version": 1,
        "summary": {"total_findings": len(findings), "by_severity": by_sev},
        "findings": [asdict(f) for f in findings],
    }


def to_markdown(findings: list[Finding]) -> str:
    lines: list[str] = []
    by_sev = {"fail": 0, "warn": 0, "info": 0}
    for f in findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
    lines.append("# kiho i18n audit report")
    lines.append("")
    lines.append(
        f"- **fail**: {by_sev['fail']}  "
        f"  **warn**: {by_sev['warn']}  "
        f"  **info**: {by_sev['info']}  "
        f"  **total**: {len(findings)}"
    )
    lines.append("")
    if not findings:
        lines.append("All checks clean.")
        return "\n".join(lines) + "\n"

    for sev in ("fail", "warn", "info"):
        bucket = [f for f in findings if f.severity == sev]
        if not bucket:
            continue
        lines.append(f"## {sev.upper()} ({len(bucket)})")
        lines.append("")
        # Group by check
        by_check: dict[str, list[Finding]] = {}
        for f in bucket:
            by_check.setdefault(f.check, []).append(f)
        for check, items in by_check.items():
            lines.append(f"### {check} — {len(items)} finding(s)")
            lines.append("")
            for f in items:
                lines.append(f"- **{f.locale} / `{f.key}`**")
                lines.append(f"  - evidence: `{f.evidence}`")
                if f.suggestion:
                    lines.append(f"  - suggestion: {f.suggestion}")
            lines.append("")
    return "\n".join(lines) + "\n"


def write_output(target: str | None, payload: str) -> None:
    if target is None:
        return
    if target == "-":
        sys.stdout.write(payload)
        if not payload.endswith("\n"):
            sys.stdout.write("\n")
        return
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    Path(target).write_text(payload, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="kiho v6.5 i18n quality audit (5 deterministic checks)",
    )
    ap.add_argument("--project-root", required=True, type=Path)
    ap.add_argument("--locales-dir", required=True,
                    help="path relative to --project-root")
    ap.add_argument("--code-glob", required=True,
                    help="glob relative to --project-root, e.g. apps/mobile/src/**/*.{ts,tsx}")
    ap.add_argument("--canonical", default="en")
    ap.add_argument("--config", type=Path, default=None,
                    help="path to i18n-allowlist.toml (optional)")
    ap.add_argument("--json-out", default=None,
                    help="path or '-' for stdout JSON")
    ap.add_argument("--md-out", default=None,
                    help="path or '-' for stdout markdown")
    ap.add_argument("--strict-warn", action="store_true",
                    help="promote warns to fails (returns 2 instead of 1)")
    args = ap.parse_args(argv)

    project_root: Path = args.project_root.resolve()
    if not project_root.is_dir():
        print(f"error: --project-root {project_root} is not a directory",
              file=sys.stderr)
        return EXIT_CRASH

    locales_dir = (project_root / args.locales_dir).resolve()
    if not locales_dir.is_dir():
        print(f"error: locales dir {locales_dir} not found", file=sys.stderr)
        return EXIT_CRASH

    try:
        config = load_config(args.config.resolve() if args.config else None)
    except Exception as e:
        print(f"error: failed to load config: {e}", file=sys.stderr)
        return EXIT_CRASH

    canonical = args.canonical or config.get("canonical", "en")

    state = AuditState()

    try:
        locales = load_locales(locales_dir)
        if not locales:
            state.add(
                check="parity", severity="fail", locale="-", key="<root>",
                evidence=f"no *.json files under {locales_dir}",
                suggestion="ensure locale files exist as <name>.json",
            )
        else:
            check_parity(locales, canonical, state)
            check_placeholder(locales, canonical, state)
            check_untranslated(locales, canonical, config, state)
            check_hardcoded(project_root, args.code_glob, config, state)
            check_dead_keys(
                project_root, args.code_glob, locales, canonical, config, state,
            )
            # v2 clarity hook — currently no-op; preserves extension surface.
            for f in _check_clarity_v2():
                state.findings.append(f)
    except Exception:
        traceback.print_exc()
        return EXIT_CRASH

    summary = to_summary(state.findings)
    md = to_markdown(state.findings)

    if args.json_out:
        write_output(args.json_out, json.dumps(summary, ensure_ascii=False, indent=2))
    if args.md_out:
        write_output(args.md_out, md)
    # If neither requested, default to JSON on stdout for ergonomics
    if not args.json_out and not args.md_out:
        sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    by_sev = summary["summary"]["by_severity"]
    if by_sev["fail"] > 0:
        return EXIT_FAIL
    if by_sev["warn"] > 0:
        return EXIT_FAIL if args.strict_warn else EXIT_WARN
    return EXIT_CLEAN


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(EXIT_CRASH)
