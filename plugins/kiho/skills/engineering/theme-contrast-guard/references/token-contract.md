# `tokens.contract.ts` — schema spec

The token contract is a sibling file to your project's `tokens.ts`. It annotates each colour token with its **role** (foreground / background / border / decorative) and optionally restricts which backgrounds a foreground token is **paired with**. `bin/contrast_audit.py` reads it to produce a precise WCAG matrix scan.

Without a contract file the audit falls back to a name-based heuristic (`bg|surface|paper` → `bg`, `text|ink|fg` → `fg`, etc.). The heuristic is good enough to ship Layer 1 on day 1 with no project change, but it produces false-positive failures for semantic tokens (e.g. `transfer` only ever rendered on the primary `bg`, never on `tabPillActive`). Adopt the contract to drive false positives to ~0.

## Schema

```ts
// One of seven roles. Decorative roles (glow, shadow, scrim) are excluded
// from the contrast matrix entirely.
export type ColorRole =
  | "fg"        // foreground text — pairs against every `bg` (cross-product)
  | "bg"        // primary background surface
  | "fg-on"     // foreground intended for a SPECIFIC bg only — REQUIRES pairsWith
  | "border"    // 1px UI lines / dividers — 3.0:1 minimum (WCAG 1.4.11)
  | "glow"      // decorative drop-shadow / ambient glow — excluded
  | "shadow"    // box-shadow colour — excluded
  | "scrim";    // modal overlay / glassmorphism backdrop — excluded

export interface TokenSpec {
  /** Hex (`#1A1A1F`, `#FFF`) or rgba (`rgba(26, 26, 31, 0.06)`). */
  value: string;
  role: ColorRole;
  /**
   * Restricts which `bg` tokens this fg/border is evaluated against.
   * Only applies when role is "fg-on", "fg", or "border".
   * Names refer to other token keys in the SAME theme bundle.
   */
  pairsWith?: string[];
}

// Top-level export — keys are theme bundle names matching tokens.ts:
//   moeTokens / proTokens   →   "moe" / "pro"
export const TOKEN_CONTRACTS: Record<string, Record<string, TokenSpec>> = {
  moe: { /* ... */ },
  pro: { /* ... */ },
};
```

## Worked example — annotating a macaron palette

The 33Ledger Cyber-Moe theme has these key tokens. Below is how each maps to a contract entry.

```ts
import type { TokenSpec, ColorRole } from "kiho-plugin/templates/tokens.contract.template";

export const TOKEN_CONTRACTS = {
  moe: {
    // ---- Surfaces ----
    bg:           { value: "#FFF8EE", role: "bg" },
    surface:      { value: "#FFFFFF", role: "bg" },
    surfaceAlt:   { value: "#F6EDDE", role: "bg" },

    // ---- Foreground text ----
    text:         { value: "#1A1A1F", role: "fg" },        // pairs against ALL bgs
    textMuted:    { value: "#6B6860", role: "fg" },        // pairs against ALL bgs
    accentInk:    { value: "#5C8AA8", role: "fg" },

    // ---- Borders (3.0:1 against any bg they ride on) ----
    border:       { value: "rgba(26, 26, 31, 0.06)", role: "border", pairsWith: ["bg", "surface"] },
    borderStrong: { value: "rgba(26, 26, 31, 0.12)", role: "border", pairsWith: ["bg", "surface"] },

    // ---- Category tints (fg-on: only legal on their matching tint surface) ----
    mint:         { value: "#D8F3E4", role: "bg" },
    mintInk:      { value: "#2E8B6A", role: "fg-on", pairsWith: ["mint"] },
    peach:        { value: "#FCE3D4", role: "bg" },
    peachInk:     { value: "#C26A4A", role: "fg-on", pairsWith: ["peach"] },
    lavender:     { value: "#E9E4F7", role: "bg" },
    lavenderInk:  { value: "#6B5CA8", role: "fg-on", pairsWith: ["lavender"] },
    butter:       { value: "#FCEFC7", role: "bg" },
    butterInk:    { value: "#A8812B", role: "fg-on", pairsWith: ["butter"] },

    // ---- Decorative (excluded from matrix) ----
    overlay:      { value: "rgba(26, 26, 31, 0.45)", role: "scrim" },
    glass:        { value: "rgba(255, 255, 255, 0.72)", role: "scrim" },
    gainGlow:     { value: "rgba(75, 227, 160, 0.45)", role: "glow" },
    lossGlow:     { value: "rgba(155, 140, 232, 0.40)", role: "glow" },

    // ---- PnL accents — these ARE foreground (chip text, deltas) ----
    gain:         { value: "#4BE3A0", role: "fg-on", pairsWith: ["bg", "surface"] },
    loss:         { value: "#9B8CE8", role: "fg-on", pairsWith: ["bg", "surface"] },

    // ---- Transfer — only used as text on bg / surface ----
    transfer:     { value: "#6B5CA8", role: "fg-on", pairsWith: ["bg", "surface"] },

    // ---- Tabs (active pill) ----
    tabPillActive:  { value: "#E8F0F6", role: "bg" },
    tabLabelActive: { value: "#5C8AA8", role: "fg-on", pairsWith: ["tabPillActive"] },
  },

  pro: {
    bg:           { value: "#000000", role: "bg" },
    surface:      { value: "#0B0D10", role: "bg" },
    surfaceAlt:   { value: "#14171C", role: "bg" },
    text:         { value: "#F0EEEA", role: "fg" },
    textMuted:    { value: "#7A7F8A", role: "fg" },
    border:       { value: "rgba(255, 255, 255, 0.06)", role: "border", pairsWith: ["bg", "surface", "surfaceAlt"] },
    borderStrong: { value: "rgba(255, 255, 255, 0.12)", role: "border", pairsWith: ["bg", "surface", "surfaceAlt"] },
    accent:       { value: "#6BFFC0", role: "fg-on", pairsWith: ["bg", "surface", "surfaceAlt"] },
    transfer:     { value: "#8AB4FF", role: "fg-on", pairsWith: ["bg", "surface"] },
    tabPillActive:  { value: "rgba(107, 255, 192, 0.14)", role: "bg" },
    tabLabelActive: { value: "#6BFFC0", role: "fg-on", pairsWith: ["tabPillActive"] },
  },
} as const satisfies Record<string, Record<string, TokenSpec>>;
```

## How `pairsWith` constrains the matrix

For a token whose role is `fg` (no `pairsWith`):
> Audit evaluates this fg against the **cross-product** of all `bg` tokens in the same theme. Below-threshold pair = `severity: "fail"`.

For a token whose role is `fg-on` or `fg` **with `pairsWith`** set:
> Audit evaluates this fg only against bgs whose names are in the `pairsWith` list. Below-threshold pair (if any of the legal pairings still fail) = `severity: "warn"` — the contract narrowed the scope, but the surviving pair still violates and needs a value adjustment.

For a token whose role is `border`:
> Required ratio is 3.0:1 (WCAG 1.4.11) regardless of body/hero classification.

For decorative roles (`glow`, `shadow`, `scrim`):
> Excluded entirely. They are not text and not foreground UI elements.

## Migration tip — incremental adoption

Layer 1 reads tokens.ts first, then overlays the contract on top. **Tokens absent from the contract** still appear in the matrix using the heuristic role. So you can adopt the contract one token group at a time:

1. **Day 1:** add `tokens.contract.ts` with only the surface bgs and the primary `text` / `textMuted`. Rest stays heuristic.
2. **Day 2:** add the category tint pairs (the most likely false-positive source). Audit becomes substantially cleaner.
3. **Week 1:** all tokens covered. False positive rate ~ 0.

The contract is **additive only** — never remove tokens from `tokens.ts` to satisfy the audit. The audit is a check, not a constraint on what tokens may exist.

## Common gotchas

- **Use exact key names from `tokens.ts`.** The matcher is whole-word, case-sensitive. `mintInk` ≠ `MintInk`.
- **`pairsWith` names refer to keys in the same theme bundle**, not to literal hex values. To pair against `bg`, write `pairsWith: ["bg"]`, not `pairsWith: ["#FFF8EE"]`.
- **`fg-on` without `pairsWith` is a contract bug** — the audit will skip the token silently. Always set `pairsWith` on `fg-on`.
- **Borders at low alpha** are alpha-composited over their `pairsWith` bg before the ratio is computed. Don't pre-flatten the colour.
- **Don't list `gainGlow` or `lossGlow` as `fg`** even though their hex looks colourful — they are drop-shadow tints, never rendered as text. Mark them `glow`.
