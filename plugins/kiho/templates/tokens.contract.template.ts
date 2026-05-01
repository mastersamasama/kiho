// kiho theme-contrast-guard — token contract template (Layer 1 input)
//
// Annotates each theme token with its WCAG role + valid pairings. The
// contrast audit script (`bin/contrast_audit.py`) reads this file to compute
// the precise WCAG matrix per theme bundle.
//
// Usage:
//   1. Copy this file to your theme directory next to tokens.ts:
//        apps/<your-app>/src/theme/tokens.contract.ts
//   2. For each token in `themeTokens.<theme>`, add an entry to TOKEN_CONTRACTS
//      under the same key. Tokens omitted from the contract fall back to a
//      name-based heuristic (which is good enough for surfaces + plain text
//      but produces false positives on category-tints / accent colours).
//   3. Run the audit:
//        python <kiho>/bin/contrast_audit.py \
//          --tokens apps/<your-app>/src/theme/tokens.ts \
//          --threshold mixed --themes moe,pro --json-out -
//   4. Iterate: each `fail` finding is either a real contrast bug (fix the
//      hex) or a missing pairsWith constraint (add it here). Each `warn`
//      finding is an explicit-pair below threshold — designer call.
//
// See `skills/engineering/theme-contrast-guard/references/token-contract.md`
// for the schema spec and worked examples.

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

export type ColorRole =
  | "fg"        // foreground text — pairs against ALL bg tokens (cross-product)
  | "bg"        // primary background surface
  | "fg-on"     // foreground intended for a SPECIFIC bg only — REQUIRES pairsWith
  | "border"    // 1px UI lines / dividers — 3.0:1 floor (WCAG 1.4.11)
  | "glow"      // decorative drop-shadow / ambient glow — excluded from matrix
  | "shadow"    // box-shadow colour — excluded from matrix
  | "scrim";    // modal overlay / glassmorphism backdrop — excluded from matrix

export interface TokenSpec {
  /** Hex (`#1A1A1F`, `#FFF`) or rgba (`rgba(26, 26, 31, 0.06)`). */
  value: string;
  role: ColorRole;
  /**
   * Restricts which `bg` tokens this fg/border is evaluated against.
   * Names refer to other token keys in the SAME theme bundle.
   * Required when role is "fg-on"; optional but recommended for "border".
   */
  pairsWith?: string[];
}

// ---------------------------------------------------------------------------
// Example annotations — adapt to your theme
// ---------------------------------------------------------------------------
//
// The example below mirrors a Cyber-Moe-style RN theme. Replace token
// names + values with the keys in YOUR `tokens.ts` `themeTokens.<theme>`.

export const TOKEN_CONTRACTS = {
  // -----------------------------------------------------------------------
  // Light theme — cream surfaces, deep ink text, soft category tints
  // -----------------------------------------------------------------------
  moe: {
    // Surfaces
    bg:           { value: "#FAF7F2", role: "bg" },
    surface:      { value: "#FFFFFF", role: "bg" },
    surfaceAlt:   { value: "#F6EDDE", role: "bg" },

    // Foreground text — pairs against all bg by default (no pairsWith)
    text:         { value: "#1A1A1F", role: "fg" },
    textMuted:    { value: "#6B6860", role: "fg" },
    accentInk:    { value: "#5C8AA8", role: "fg" },

    // Borders — 3.0:1 against the surfaces they ride on
    border:       { value: "rgba(26, 26, 31, 0.06)", role: "border", pairsWith: ["bg", "surface"] },
    borderStrong: { value: "rgba(26, 26, 31, 0.12)", role: "border", pairsWith: ["bg", "surface"] },

    // Category tints — fg-on locks them to ONE bg each, eliminating
    // false-positive cross-product failures.
    mint:         { value: "#D8F3E4", role: "bg" },
    mintInk:      { value: "#0F8A6A", role: "fg-on", pairsWith: ["mint"] },
    peach:        { value: "#FCE3D4", role: "bg" },
    peachInk:     { value: "#9C4F30", role: "fg-on", pairsWith: ["peach"] },

    // Decorative — excluded from matrix
    overlay:      { value: "rgba(26, 26, 31, 0.45)", role: "scrim" },
    glass:        { value: "rgba(255, 255, 255, 0.72)", role: "scrim" },
    gainGlow:     { value: "rgba(75, 227, 160, 0.45)", role: "glow" },
    cardShadow:   { value: "rgba(26, 26, 31, 0.06)", role: "shadow" },

    // Hero number — opt in via this key OR the `--hero-tokens` flag.
    // Required ratio jumps to 7.0:1 when running `--threshold mixed`.
    heroNumber:   { value: "#1F2235", role: "fg" },
  },

  // -----------------------------------------------------------------------
  // Dark theme — OLED black, neon accents, translucent borders
  // -----------------------------------------------------------------------
  pro: {
    bg:           { value: "#000000", role: "bg" },
    surface:      { value: "#0B0D10", role: "bg" },
    surfaceAlt:   { value: "#14171C", role: "bg" },

    text:         { value: "#F0EEEA", role: "fg" },
    // textMuted at 4.5:1 on `surface` (#0B0D10) requires careful tuning:
    // #7A7F8A clears 4.32 (fail); #8C909B clears 4.78 (pass).
    textMuted:    { value: "#8C909B", role: "fg" },

    border:       { value: "rgba(255, 255, 255, 0.06)", role: "border", pairsWith: ["bg", "surface", "surfaceAlt"] },
    borderStrong: { value: "rgba(255, 255, 255, 0.12)", role: "border", pairsWith: ["bg", "surface", "surfaceAlt"] },

    accent:       { value: "#6BFFC0", role: "fg-on", pairsWith: ["bg", "surface", "surfaceAlt"] },
    transfer:     { value: "#8AB4FF", role: "fg-on", pairsWith: ["bg", "surface"] },

    tabPillActive:  { value: "rgba(107, 255, 192, 0.14)", role: "bg" },
    tabLabelActive: { value: "#6BFFC0", role: "fg-on", pairsWith: ["tabPillActive"] },

    overlay:      { value: "rgba(0, 0, 0, 0.72)", role: "scrim" },
    glass:        { value: "rgba(20, 23, 28, 0.72)", role: "scrim" },

    heroNumber:   { value: "#F0EEEA", role: "fg" },
  },
} as const satisfies Record<string, Record<string, TokenSpec>>;
