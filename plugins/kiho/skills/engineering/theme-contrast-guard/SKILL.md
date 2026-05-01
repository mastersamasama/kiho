---
id: sk-088
name: theme-contrast-guard
title: WCAG contrast guardian for kiho-using projects' theme systems
description: 4-layer defence — design-time pair matrix audit, lint-time ESLint sidecar, runtime dev warner, CI Playwright/axe. AA body / AAA hero. Surfaces via /kiho evolve --audit=contrast.
domain: engineering
capability: evaluate
topic_tags: [theming, accessibility, wcag, dark-mode]
trust_tier: T1
status: active
soul_version: v5
created: 2026-05-01
---

# theme-contrast-guard

Public-facing kiho skill that any /kiho project can opt into. Catches WCAG SC 1.4.3 (contrast minimum), 1.4.6 (contrast enhanced), and 1.4.11 (non-text contrast) violations across an app's theme tokens, lint surface, runtime render, and CI before they ship to users.

The skill enforces the **user-locked thresholds** from kiho v6.5:

| Element | Ratio | WCAG SC |
|---|---:|---|
| Body text (default) | 4.5:1 | 1.4.3 (AA) |
| Hero numbers (e.g. `netWorth`, `heroNumber`) | 7.0:1 | 1.4.6 (AAA) |
| Large text (≥18pt or ≥14pt-bold) | 3.0:1 | 1.4.3 (AA Large) |
| Borders / dividers / non-text UI | 3.0:1 | 1.4.11 |

Small-text mobile policy: RN font size dp 1:1 = pt (mobile-rendering approximation, accepted in WCAG 2.x mobile guidance).

## When to invoke

- **`/kiho evolve --audit=contrast`** — explicit audit on demand. Runs Layer 1 + emits report to `<project>/.kiho/audit/contrast/<iso-date>.md`.
- **INITIALIZE auto-detect** — if `<project>/apps/*/src/theme/` exists and contains `tokens.ts`, the kiho-eng-lead's INITIALIZE step auto-registers this skill into the per-project skill set.
- **CI direct call** — Layer 4-a runner from a GitHub Action / pre-commit hook (no agent in the loop).

## The 4-layer defence

The skill is one piece in a 4-layer stack. Each layer catches what the others miss; none is sufficient alone.

| # | Layer | Fires at | Catches | Misses |
|---|---|---|---|---|
| 1 | **Design-time pair matrix** (`bin/contrast_audit.py`) | PR diff touches `theme/tokens.ts` or `tokens.contract.ts` | All static fg×bg combinations per theme bundle below threshold | Dynamic colour composition; runtime tints; ad-hoc hex in JSX |
| 2 | **Lint-time ESLint sidecar** | IDE save / pre-commit | Inline hex/rgba in `style={...}`; `palette.*` / `macaron.*` literal imports outside `theme/`; `useColorScheme()` outside `ThemeProvider.tsx` | Tokens that ARE in theme but pair-up to low contrast |
| 3 | **Runtime dev warner** (`runtime-contrast-warner.template.ts`) | `__DEV__` render of `<Text>` | Dynamic `<Text>` colour against nearest non-transparent bg ancestor below 4.5 — including conditional / computed / state-driven colours | Non-text components; backgrounds rendered without nested text |
| 4 | **CI Playwright/axe** | PR | Real DOM contrast scan in light + dark mode across hero screens; layout-time violations after composition | Layer 1+2+3 should already have caught most; this is final-line backstop |

**Cost ladder:** Layer 1 ~1s, Layer 2 IDE-instant, Layer 3 dev-only zero-prod-cost, Layer 4 ~30s/PR.

## Inputs / Outputs

**Inputs:**
- `--tokens <path>` — required. Path to `tokens.ts` or `tokens.contract.ts`.
- `--threshold <AA|AAA|mixed>` — default `mixed` (4.5 body + 7.0 hero + 3.0 border).
- `--themes moe,pro` — comma-separated theme bundle names.
- `--hero-tokens netWorth,heroNumber` — token names to evaluate at AAA.
- `--strict` — exit 2 on any below-threshold pair (incl. warn).
- `--json-out <path|->` / `--md-out <path|->` — output sinks.

**Outputs:**
- JSON or markdown report listing every below-threshold pair with theme, fg name + value, bg name + value, computed ratio, required ratio, severity (`fail` for cross-product violations / `warn` for explicit-pairing-only violations), and the WCAG SC rule that applies.
- Exit codes: `0` clean, `1` warn-only, `2` fail (or `--strict` with any finding), `3` crash (parse error / missing tokens).

## Token contract requirement

Layer 1 works in two modes:

1. **Heuristic mode (default, no contract file)** — token role inferred from name: `bg|surface|background|paper|cream|tabPillActive` → `bg`; `text|ink|fg|accent|gain|loss|income|expense|transfer|muted|tabLabel` → `fg`; `border|line|hairline|divider` → `border`; `glow|shadow|scrim|overlay|glass` → excluded. Useful for first-day adoption — no project change required. **Trade-off:** semantic tokens (e.g. `transfer` is only rendered on the primary `bg`, never on `tabPillActive`) are evaluated against the full cross-product → false-positive failures the project must deduplicate manually.

2. **Contract mode (recommended)** — project adds a sibling `tokens.contract.ts` annotating each token with `role` and optional `pairsWith`. Audit then evaluates only legal pairings. False positives drop to ~0; surface coverage rises to 100%.

See `references/token-contract.md` for the schema spec and worked examples. The drop-in template is at `templates/tokens.contract.template.ts`.

**Migration tip:** projects can adopt incrementally. The heuristic falls back gracefully when contract is missing, and contract entries can be added one token at a time — uncovered tokens simply use the heuristic.

## Worked examples — one per layer

### Example 1: Layer 1 fires — Moe theme adds new `mintInk` text on `creamDeep`

```bash
$ python bin/contrast_audit.py \
    --tokens apps/mobile/src/theme/tokens.ts \
    --threshold mixed --themes moe,pro --json-out -
{
  "summary": {"total": 1, "fail": 1, "warn": 0},
  "findings": [{
    "theme": "moe", "fg": "mintInk", "bg": "creamDeep",
    "fg_value": "#2E8B6A", "bg_value": "#F6EDDE",
    "ratio": 3.21, "required": 4.5,
    "severity": "fail", "rule": "WCAG 2.1 SC 1.4.3",
    "note": "body/cross"
  }]
}
```

Resolution paths:
- If `mintInk` is intentionally only used on `mint` surfaces, add `pairsWith: ["mint"]` to its contract entry — this finding becomes a `warn` and clears once the cross-product is no longer evaluated.
- Otherwise, deepen `mintInk` until ratio ≥ 4.5 (e.g. `#0F8A6A` lifts to 5.2:1 on `creamDeep`).

### Example 2: Layer 2 fires — developer types a literal hex in JSX

```tsx
// File: apps/mobile/src/screens/HomeScreen.tsx
<Text style={{ color: '#9B9B9B', fontSize: 13 }}>{label}</Text>
//                       ~~~~~~~ ESLint: kiho/no-hex-in-jsx-style
//                                — replace with tokens.textMuted
```

Resolution: import `useTheme()` and use the semantic token:
```tsx
const { tokens } = useTheme();
<Text style={{ color: tokens.textMuted, fontSize: 13 }}>{label}</Text>
```

### Example 3: Layer 3 fires — runtime composition produces low contrast

```ts
// __DEV__ console after first paint:
[contrast] HomeScreen.HeaderTitle  color=#7A7F8A on bg=#0B0D10 ratio=4.32 (required 4.5)
```

This pair is legal at the token level (both `textMuted` and `surface` from `proTokens`) but fails marginally — Layer 1 didn't catch it because the `pro` token spec listed `textMuted` against `bg = #000000` (ratio ≥ 4.5). The runtime warner caught the actual rendered surface (`#0B0D10`).

Resolution: bump `oled.textMuted` from `#7A7F8A` to `#8C909B` (ratio 4.78:1 on `surface`).

### Example 4: Layer 4 fires — Playwright/axe DOM scan

```
$ npx playwright test e2e/contrast.spec.ts
[FAIL] HomeScreen (themeMode=light) — 2 axe-core color-contrast violations:
  - <span class="r-color-7"> "Pending sync" 3.92:1 (required 4.5:1)
  - <button class="r-bg-12"> "Reverse" border 2.11:1 (required 3.0:1)
```

This catches the case where Layer 1+2+3 all passed in isolation but a downstream component (e.g. `<Banner>` overrides bg via prop) ends up rendering a token pair that wasn't covered by the contract.

## Cross-references

- `references/token-contract.md` — `tokens.contract.ts` schema spec + how to annotate macaron palettes.
- `references/contrast-thresholds.md` — exact threshold table with WCAG SC rationale.
- `references/migration-playbook.md` — generic Phase 0 → Phase 3 rollout for any /kiho project.
- Top-level `references/accessibility-doctrine.md` — public-facing doctrine doc; how the 4 layers map to WCAG SCs.
- `templates/tokens.contract.template.ts` — drop-in TypeScript file projects copy.
- `templates/eslint-kiho-config.template.cjs` — Layer 2 ESLint sidecar config.
- `templates/runtime-contrast-warner.template.ts` — Layer 3 runtime warner.

## Invariants

- The script is **pure Python 3.11 stdlib** — no Node toolchain, no third-party libs. Runs in any kiho project's CI without `pnpm install`.
- The script never modifies project files.
- The script never reads outside the `--tokens` path's parent dir (and a sibling `*.contract.ts`).
- Hero-token detection is conservative: a token is hero only if its name is in `--hero-tokens` OR matches the convention regex (`hero|primary|featured`). This avoids accidentally flagging `accentInk` as needing AAA.

## Returning to the caller

When invoked via `/kiho evolve --audit=contrast`, return a structured JSON block to the CEO:

```json
{
  "skill": "theme-contrast-guard",
  "status": "fail",
  "report_path": ".kiho/audit/contrast/2026-05-01.md",
  "summary": {"total": 3, "fail": 2, "warn": 1},
  "lane_routing": {
    "ledger": "state_decision (Lane A) — 2 below-threshold pairs identified",
    "kb": null,
    "memory": null
  }
}
```

Per content-routing doctrine: a per-turn audit report is Lane A (state). If the audit produces a reusable principle (e.g. "Pro theme's `textMuted` needs ≥ 4.78:1 against the OLED `surface`") that is Lane B (KB) and should be split out via the kb-manager.
