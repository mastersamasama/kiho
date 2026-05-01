#!/usr/bin/env python3
"""Theme contrast audit — WCAG matrix scan for kiho-using projects' design tokens.

Written for kiho v6.5 as Layer 1 (design-time) + Layer 4-a (CI static) of the
4-layer theme-contrast-guard defence. Reads a project's `tokens.ts` (and optional
sibling `tokens.contract.ts`), enumerates every fg x bg pair per theme bundle,
computes the WCAG 2.1 contrast ratio, and emits findings for any pair below the
configured threshold.

Threshold strategy (user-locked in plan §C2):
  - body fg x bg               >= 4.5  (AA  — WCAG 2.1 SC 1.4.3)
  - hero fg x bg               >= 7.0  (AAA — WCAG 2.1 SC 1.4.6)
  - large text or border       >= 3.0  (WCAG 2.1 SC 1.4.11)
  - small-text RN font dp 1:1 = pt (mobile approximation)

Role taxonomy (matrix-eligible vs matrix-excluded):
  matrix-eligible:    fg, fg-on, bg, border
  matrix-excluded:    glow, shadow, scrim          (decorative chrome)
                      hairline                     (1px UI lines designer-accepted
                                                    below 3:1 — sub-pixel rendering
                                                    means SC 1.4.11 cannot apply
                                                    cleanly anyway)
                      decorative                   (chip-on-chip, accent-on-accent,
                                                    neon-PnL hue glyphs that DO NOT
                                                    carry information beyond an
                                                    adjacent body-text label —
                                                    explicit designer waiver)

Hero tokens are detected via either:
  - --hero-tokens flag (comma-separated token names), default `heroNumber,netWorth`
  - or convention: token name contains hero|primary|featured (case-insensitive)

Exit codes:
  0 — clean (no findings)
  1 — warn (below-threshold pairs exist but only inside `pairsWith` whitelist
            — i.e. designer explicitly limited the scope; surface for review)
  2 — fail (--strict and any below-threshold pair OR cross-product violation)
  3 — crash (parse error, missing tokens, ratio compute error)

Usage:
  python contrast_audit.py --tokens <path> --threshold mixed \\
         --themes moe,pro --json-out -                       # JSON to stdout
  python contrast_audit.py --tokens <path> --md-out report.md --strict
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ---------------------------------------------------------------------------
# WCAG 2.x contrast ratio (no deps)
# Reference: https://www.w3.org/WAI/GL/wiki/Relative_luminance
# ---------------------------------------------------------------------------

_HEX3_RE = re.compile(r"^#([0-9a-fA-F]{3})$")
_HEX6_RE = re.compile(r"^#([0-9a-fA-F]{6})$")
_HEX8_RE = re.compile(r"^#([0-9a-fA-F]{8})$")  # #rrggbbaa
_RGB_RE = re.compile(
    r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+)\s*)?\)$",
    re.IGNORECASE,
)


def parse_color(s: str) -> tuple[int, int, int, float] | None:
    """Parse `#rgb`, `#rrggbb`, `#rrggbbaa`, `rgb(r,g,b)`, `rgba(r,g,b,a)`.

    Returns (r, g, b, alpha 0..1) or None if unparseable. Alpha-aware so that
    semi-transparent borders/scrims can be flagged: contrast against fully
    opaque backgrounds is still computed against the un-blended channel — the
    skill's policy is that low-alpha tokens for borders are fine at 3.0:1
    against the primary bg they overlay (Layer 1 cannot model arbitrary
    composition; that's Layer 3's job).
    """
    s = s.strip()
    m = _HEX3_RE.match(s)
    if m:
        h = m.group(1)
        return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), 1.0)
    m = _HEX6_RE.match(s)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = _HEX8_RE.match(s)
    if m:
        h = m.group(1)
        return (
            int(h[0:2], 16),
            int(h[2:4], 16),
            int(h[4:6], 16),
            int(h[6:8], 16) / 255.0,
        )
    m = _RGB_RE.match(s)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        return (r, g, b, a)
    return None


def _channel(c: int) -> float:
    v = c / 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(r: int, g: int, b: int) -> float:
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    l1 = luminance(*c1)
    l2 = luminance(*c2)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def _composite_on(fg: tuple[int, int, int, float],
                  bg: tuple[int, int, int, float]) -> tuple[int, int, int]:
    """Alpha-composite fg over fully opaque bg. Used so semi-transparent fg
    tokens (e.g. borders at rgba(26,26,31,0.06)) report a realistic ratio
    against their target bg rather than the un-blended channel."""
    a = fg[3]
    if a >= 1.0:
        return (fg[0], fg[1], fg[2])
    r = round(fg[0] * a + bg[0] * (1 - a))
    g = round(fg[1] * a + bg[1] * (1 - a))
    b = round(fg[2] * a + bg[2] * (1 - a))
    return (r, g, b)


# ---------------------------------------------------------------------------
# Token parsing — read tokens.ts as text, no Node toolchain
# ---------------------------------------------------------------------------

# Match a JS/TS object property: name ("name" | name) : "value" or 'value'
_PROP_RE = re.compile(
    r"""(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*
        (?:
            "(?P<dq>[^"]+)"
          | '(?P<sq>[^']+)'
        )""",
    re.VERBOSE,
)

# Theme bundle export — `export const moeTokens: ColorTokens = { ... };` or
# `themeTokens.moe = { ... }` style.
_THEME_BUNDLE_RE = re.compile(
    r"export\s+const\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)Tokens\s*"
    r"(?::\s*[A-Za-z_][A-Za-z0-9_<>]*)?\s*=\s*\{(?P<body>.*?)\}\s*;",
    re.DOTALL,
)

# tokens.contract.ts theme-level walking is handled via the brace-balanced
# _iter_top_level_objects parser below; per-token regex match follows here.
# Inside contract body: `tokenKey: { value: "...", role: "fg", pairsWith: ["x","y"] }`
_CONTRACT_TOKEN_RE = re.compile(
    r"""(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*\{
        \s*value\s*:\s*["'](?P<value>[^"']+)["']\s*,
        \s*role\s*:\s*["'](?P<role>fg|bg|fg-on|border|hairline|decorative|glow|shadow|scrim)["']
        (?:\s*,\s*pairsWith\s*:\s*\[(?P<pairs>[^\]]*)\])?
        \s*,?\s*\}""",
    re.VERBOSE,
)

# Heuristic role classification when no contract file exists.
# Order matters: EXCLUDE first (so glow/shadow/scrim/overlay/glass never become
# either fg or bg), then BORDER, then BG (surfaces), then FG (everything text-y).
# `overlay` + `glass` default to `scrim` because they semantically are modal
# scrims / glassmorphism backdrops, not primary surfaces — projects that DO
# render text on `glass` should override via tokens.contract.ts to mark it `bg`.
_EXCLUDE_HINT = re.compile(r"\b(glow|shadow|scrim|overlay|glass)\b", re.I)
_BORDER_HINT = re.compile(r"\b(border|line|hairline|divider)\b", re.I)
_BG_HINT = re.compile(r"\b(bg|background|surface|paper|cream|tabPillActive)\b", re.I)
_FG_HINT = re.compile(r"\b(text|ink|fg|accent|tabLabel|gain|loss|income|expense|transfer|muted)\b", re.I)
_HERO_NAME_HINT = re.compile(r"\b(hero|primary|featured|netWorth)\b", re.I)


@dataclass
class TokenSpec:
    name: str
    value: str
    # "fg" | "bg" | "fg-on" | "border" | "hairline" | "decorative"
    # | "glow" | "shadow" | "scrim" | "unknown"
    role: str
    pairs_with: list[str] = field(default_factory=list)


@dataclass
class ThemeBundle:
    name: str
    tokens: dict[str, TokenSpec] = field(default_factory=dict)


@dataclass
class Finding:
    theme: str
    fg: str
    bg: str
    fg_value: str
    bg_value: str
    ratio: float
    required: float
    severity: str       # "fail" | "warn"
    rule: str
    note: str = ""


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _strip_comments(src: str) -> str:
    """Strip // line comments and /* ... */ block comments — naive but enough
    for token files which aren't user-controlled hostile input."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    src = re.sub(r"(?m)//[^\n]*$", "", src)
    return src


def parse_tokens_file(path: Path) -> dict[str, ThemeBundle]:
    """Extract theme bundles from a tokens.ts. Returns {theme_name: ThemeBundle}.

    Recognises pattern `export const <name>Tokens = { ... };` where `<name>`
    is the theme name (e.g. moeTokens -> "moe"). Inside the body, each
    `key: "value"` or `key: 'value'` is a candidate token. Values that don't
    parse as colors are skipped silently.
    """
    src = _strip_comments(path.read_text(encoding="utf-8"))
    bundles: dict[str, ThemeBundle] = {}
    for m in _THEME_BUNDLE_RE.finditer(src):
        theme = m.group("name")
        body = m.group("body")
        bundle = ThemeBundle(name=theme)
        for prop in _PROP_RE.finditer(body):
            key = prop.group("key")
            value = prop.group("dq") or prop.group("sq")
            if value is None:
                continue
            if parse_color(value) is None:
                # Could be an alias reference like macaron.cream — skip;
                # contract file or expanded variant would resolve it.
                continue
            role = _classify_role(key)
            bundle.tokens[key] = TokenSpec(name=key, value=value, role=role)
        if bundle.tokens:
            bundles[theme] = bundle
    return bundles


def parse_contract_file(path: Path) -> dict[str, ThemeBundle]:
    """Extract role + pairsWith annotations from a sibling tokens.contract.ts.

    Best-effort: requires the file follow the template shape from
    `templates/tokens.contract.template.ts` (top-level `TOKEN_CONTRACTS = { theme: {...}, ... }`).
    """
    if not path.exists():
        return {}
    src = _strip_comments(path.read_text(encoding="utf-8"))
    # Anchor on TOKEN_CONTRACTS block so we don't accidentally match unrelated objects
    block_match = re.search(
        r"TOKEN_CONTRACTS\s*=\s*\{(?P<body>.*)\}\s*as\s+const",
        src, re.DOTALL,
    )
    if not block_match:
        # Try without `as const` tail
        block_match = re.search(
            r"TOKEN_CONTRACTS\s*=\s*\{(?P<body>.*)\}\s*;?\s*$",
            src, re.DOTALL | re.MULTILINE,
        )
    if not block_match:
        return {}
    body = block_match.group("body")
    bundles: dict[str, ThemeBundle] = {}
    # Walk top-level theme keys via brace-balance
    for theme_name, theme_body in _iter_top_level_objects(body):
        bundle = ThemeBundle(name=theme_name)
        for tm in _CONTRACT_TOKEN_RE.finditer(theme_body):
            pairs_raw = tm.group("pairs") or ""
            pairs = [p.strip().strip('"').strip("'") for p in pairs_raw.split(",") if p.strip()]
            bundle.tokens[tm.group("key")] = TokenSpec(
                name=tm.group("key"),
                value=tm.group("value"),
                role=tm.group("role"),
                pairs_with=pairs,
            )
        if bundle.tokens:
            bundles[theme_name] = bundle
    return bundles


def _iter_top_level_objects(body: str):
    """Yield (key, inner_body) for each top-level `key: { ... }` in a brace-balanced
    JS object body."""
    i, n = 0, len(body)
    while i < n:
        m = re.match(r"\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*\{", body[i:])
        if not m:
            i += 1
            continue
        key = m.group("key")
        start = i + m.end()
        depth = 1
        j = start
        while j < n and depth > 0:
            if body[j] == "{":
                depth += 1
            elif body[j] == "}":
                depth -= 1
            j += 1
        inner = body[start:j - 1]
        yield key, inner
        i = j


def _classify_role(name: str) -> str:
    if _EXCLUDE_HINT.search(name):
        return "glow"  # excluded role
    if _BORDER_HINT.search(name):
        return "border"
    if _BG_HINT.search(name):
        return "bg"
    if _FG_HINT.search(name):
        return "fg"
    return "unknown"


def merge_contract(tokens: dict[str, ThemeBundle],
                   contract: dict[str, ThemeBundle]) -> dict[str, ThemeBundle]:
    """Overlay contract annotations onto raw token bundles. Contract values
    win for role + pairs_with; raw tokens win for value (the contract may
    omit hex when role is the only annotation needed)."""
    if not contract:
        return tokens
    out: dict[str, ThemeBundle] = {}
    for theme_name, bundle in tokens.items():
        ann = contract.get(theme_name)
        new_bundle = ThemeBundle(name=theme_name)
        for key, spec in bundle.tokens.items():
            if ann and key in ann.tokens:
                annotated = ann.tokens[key]
                new_bundle.tokens[key] = TokenSpec(
                    name=key,
                    value=spec.value or annotated.value,
                    role=annotated.role,
                    pairs_with=list(annotated.pairs_with),
                )
            else:
                new_bundle.tokens[key] = spec
        # Add any contract-only tokens not in tokens.ts (rare but legal)
        if ann:
            for key, annotated in ann.tokens.items():
                if key not in new_bundle.tokens:
                    new_bundle.tokens[key] = TokenSpec(
                        name=key,
                        value=annotated.value,
                        role=annotated.role,
                        pairs_with=list(annotated.pairs_with),
                    )
        out[theme_name] = new_bundle
    return out


# ---------------------------------------------------------------------------
# Pairing + ratio
# ---------------------------------------------------------------------------

def is_hero(name: str, hero_tokens: set[str]) -> bool:
    if name in hero_tokens:
        return True
    return bool(_HERO_NAME_HINT.search(name))


def required_ratio(fg: TokenSpec, bg: TokenSpec, threshold_mode: str,
                   hero_tokens: set[str]) -> tuple[float, str, str]:
    """Return (required_ratio, rule_id, kind) for this pair under the mode.

    threshold_mode: "AA" | "AAA" | "mixed"
    """
    if fg.role == "border" or bg.role == "border":
        return (3.0, "WCAG 2.1 SC 1.4.11", "border")
    if is_hero(fg.name, hero_tokens):
        # AAA in mixed; still AAA when explicitly --threshold AAA
        if threshold_mode in ("mixed", "AAA"):
            return (7.0, "WCAG 2.1 SC 1.4.6", "hero")
        return (4.5, "WCAG 2.1 SC 1.4.3", "body")
    # Body default
    if threshold_mode == "AAA":
        return (7.0, "WCAG 2.1 SC 1.4.6", "body")
    return (4.5, "WCAG 2.1 SC 1.4.3", "body")


def compute_findings(bundles: dict[str, ThemeBundle], threshold_mode: str,
                     hero_tokens: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for theme_name, bundle in bundles.items():
        bgs = {k: v for k, v in bundle.tokens.items() if v.role == "bg"}
        fgs = {k: v for k, v in bundle.tokens.items()
               if v.role in ("fg", "fg-on", "border")}
        for fg_name, fg in fgs.items():
            # Resolve target bgs
            if fg.pairs_with:
                target_bgs = {k: bgs[k] for k in fg.pairs_with if k in bgs}
                pair_mode = "explicit"
            elif fg.role == "fg-on":
                # fg-on without pairsWith is a contract bug — treat as warn
                target_bgs = {}
                pair_mode = "explicit"
            else:
                target_bgs = bgs
                pair_mode = "cross"
            for bg_name, bg in target_bgs.items():
                fg_color = parse_color(fg.value)
                bg_color = parse_color(bg.value)
                if fg_color is None or bg_color is None:
                    continue
                # Composite semi-transparent fg over opaque bg
                if fg_color[3] < 1.0:
                    fg_rgb = _composite_on(fg_color, bg_color)
                else:
                    fg_rgb = fg_color[:3]
                if bg_color[3] < 1.0:
                    # Layer 1 cannot resolve bg-of-bg; assume it composites
                    # over white for Moe-ish themes / over black for Pro-ish.
                    fallback_rgb: int = 255 if luminance(*bg_color[:3]) > 0.18 else 0
                    fallback: tuple[int, int, int, float] = (
                        fallback_rgb, fallback_rgb, fallback_rgb, 1.0,
                    )
                    bg_rgb = _composite_on(bg_color, fallback)
                else:
                    bg_rgb = bg_color[:3]
                ratio = contrast(fg_rgb, bg_rgb)
                req, rule, kind = required_ratio(fg, bg, threshold_mode, hero_tokens)
                if ratio + 1e-6 < req:
                    severity = "warn" if pair_mode == "explicit" else "fail"
                    findings.append(Finding(
                        theme=theme_name,
                        fg=fg_name,
                        bg=bg_name,
                        fg_value=fg.value,
                        bg_value=bg.value,
                        ratio=round(ratio, 2),
                        required=req,
                        severity=severity,
                        rule=rule,
                        note=f"{kind}/{pair_mode}",
                    ))
    return findings


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def render_json(findings: list[Finding], meta: dict) -> str:
    payload = {
        "meta": meta,
        "summary": {
            "total": len(findings),
            "fail": sum(1 for f in findings if f.severity == "fail"),
            "warn": sum(1 for f in findings if f.severity == "warn"),
        },
        "findings": [asdict(f) for f in findings],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_md(findings: list[Finding], meta: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Contrast audit — {meta.get('tokens_path', '')}")
    lines.append("")
    lines.append(f"- Threshold mode: `{meta.get('threshold_mode')}`")
    lines.append(f"- Themes: {', '.join(meta.get('themes', []))}")
    lines.append(f"- Hero tokens: {', '.join(sorted(meta.get('hero_tokens', [])))}")
    lines.append(f"- Contract file: `{meta.get('contract_path') or '(not present)'}`")
    lines.append("")
    if not findings:
        lines.append("**Status: CLEAN.** All pairs meet threshold.")
        return "\n".join(lines) + "\n"
    fails = [f for f in findings if f.severity == "fail"]
    warns = [f for f in findings if f.severity == "warn"]
    lines.append(f"**Status:** {len(fails)} fail / {len(warns)} warn")
    lines.append("")
    lines.append("| Theme | fg | bg | ratio | required | severity | rule | note |")
    lines.append("|---|---|---|---:|---:|---|---|---|")
    for f in findings:
        lines.append(
            f"| {f.theme} | `{f.fg}` ({f.fg_value}) | `{f.bg}` ({f.bg_value}) "
            f"| {f.ratio} | {f.required} | {f.severity} | {f.rule} | {f.note} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _emit(target: str, content: str) -> None:
    if target == "-":
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")
    else:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DEFAULT_HERO_TOKENS = {"heroNumber", "netWorth"}


def main() -> int:
    ap = argparse.ArgumentParser(description="kiho v6.5 theme contrast audit")
    ap.add_argument("--tokens", required=True, type=Path,
                    help="path to tokens.ts (or tokens.contract.ts)")
    ap.add_argument("--threshold", default="mixed", choices=["AA", "AAA", "mixed"],
                    help="AA=4.5 body / AAA=7.0 body / mixed=4.5 body + 7.0 hero")
    ap.add_argument("--themes", default="",
                    help="comma-separated theme names to include (default: all)")
    ap.add_argument("--json-out", default=None,
                    help="path or '-' for stdout")
    ap.add_argument("--md-out", default=None,
                    help="path or '-' for stdout")
    ap.add_argument("--strict", action="store_true",
                    help="exit 2 on any below-threshold pair (incl. warn)")
    ap.add_argument("--hero-tokens", default="",
                    help=f"comma-separated hero token names "
                         f"(default: {','.join(sorted(DEFAULT_HERO_TOKENS))})")
    args = ap.parse_args()

    tokens_path: Path = args.tokens
    if not tokens_path.exists():
        print(f"contrast_audit: tokens file not found: {tokens_path}", file=sys.stderr)
        return 3

    # If user passes a tokens.contract.ts directly, look for a sibling tokens.ts
    if tokens_path.name.endswith(".contract.ts"):
        contract_path = tokens_path
        sibling = tokens_path.with_name(tokens_path.name.replace(".contract.ts", ".ts"))
        tokens_path = sibling if sibling.exists() else tokens_path
    else:
        contract_path = tokens_path.with_name(
            tokens_path.stem + ".contract" + tokens_path.suffix
        )

    try:
        bundles = parse_tokens_file(tokens_path)
    except Exception as e:  # noqa: BLE001
        print(f"contrast_audit: failed to parse tokens: {e}", file=sys.stderr)
        return 3

    if not bundles:
        print(f"contrast_audit: no theme bundles found in {tokens_path}",
              file=sys.stderr)
        return 3

    contract = parse_contract_file(contract_path) if contract_path.exists() else {}
    bundles = merge_contract(bundles, contract)

    # Filter themes
    selected: list[str] = []
    if args.themes:
        selected = [t.strip() for t in args.themes.split(",") if t.strip()]
        bundles = {k: v for k, v in bundles.items() if k in selected}
        if not bundles:
            print(
                f"contrast_audit: none of the requested themes "
                f"({selected}) found in {tokens_path}",
                file=sys.stderr,
            )
            return 3
    else:
        selected = list(bundles.keys())

    hero_tokens: set[str]
    if args.hero_tokens:
        hero_tokens = {t.strip() for t in args.hero_tokens.split(",") if t.strip()}
    else:
        hero_tokens = set(DEFAULT_HERO_TOKENS)

    findings = compute_findings(bundles, args.threshold, hero_tokens)

    meta = {
        "tokens_path": str(tokens_path),
        "contract_path": str(contract_path) if contract_path.exists() else None,
        "threshold_mode": args.threshold,
        "themes": selected,
        "hero_tokens": sorted(hero_tokens),
        "tool": "kiho/contrast_audit.py",
        "tool_version": "v6.5.0",
    }

    if args.json_out:
        _emit(args.json_out, render_json(findings, meta))
    if args.md_out:
        _emit(args.md_out, render_md(findings, meta))
    if not args.json_out and not args.md_out:
        # Default: human summary to stdout
        sys.stdout.write(render_md(findings, meta))

    fails = [f for f in findings if f.severity == "fail"]
    warns = [f for f in findings if f.severity == "warn"]
    if args.strict and (fails or warns):
        return 2
    if fails:
        return 2
    if warns:
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(3)
    except Exception as e:  # noqa: BLE001
        print(f"contrast_audit: crash: {e}", file=sys.stderr)
        sys.exit(3)
