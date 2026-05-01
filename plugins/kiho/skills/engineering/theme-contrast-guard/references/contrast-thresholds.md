# Contrast thresholds — kiho v6.5 user-locked

This is the canonical reference for what ratio applies to which token pair. Everything in `bin/contrast_audit.py`'s `required_ratio()` derives from this table; the runtime warner and the ESLint rules quote the same numbers.

## Threshold table

| # | Pair kind | Required | WCAG SC | Notes |
|---|---|---:|---|---|
| 1 | Body fg × bg | **4.5:1** | 1.4.3 (AA) | Default for any token whose role is `fg` and that is not classified as hero. |
| 2 | Hero number fg × bg | **7.0:1** | 1.4.6 (AAA) | User-locked: every hero number (44pt-class display, e.g. `netWorth`) gets the AAA bump. |
| 3 | Large text (≥18pt OR ≥14pt-bold) | **3.0:1** | 1.4.3 (AA Large) | Mobile-RN approximation: dp 1:1 = pt. |
| 4 | Border / divider / hairline | **3.0:1** | 1.4.11 | Non-text contrast. Includes 1px UI lines, focus rings, chip outlines. |
| 5 | Decorative (glow / shadow / scrim) | n/a | — | Not evaluated. Excluded from matrix. |

## Threshold modes

`bin/contrast_audit.py --threshold` accepts three modes:

- **`mixed`** (default, recommended) — body 4.5, hero 7.0, border 3.0. Matches user-locked policy.
- **`AA`** — body 4.5, hero 4.5 (NOT bumped), border 3.0. Use for projects without explicit hero designations.
- **`AAA`** — body 7.0, hero 7.0, border 3.0. Stricter; rare projects pass without contrast tuning.

The `--threshold` flag does NOT relax border below 3.0 — the WCAG 1.4.11 floor is a hard kiho invariant.

## Hero-token detection

A token is treated as `hero` (and hence required to clear 7.0:1 in `mixed` or `AAA` modes) if EITHER:

1. **Explicit list:** the token name is in the comma-separated `--hero-tokens` flag. Default value is `heroNumber,netWorth`. Projects override per-need:
   ```bash
   python contrast_audit.py --tokens ... --hero-tokens "netWorth,kpiNumber,vaultBalance"
   ```

2. **Convention regex:** the token name contains any of `hero`, `primary`, `featured`, or `netWorth` (case-insensitive, word boundary). This catches new components added between updates of the explicit list.

If you DO NOT want a `primary*` token treated as hero (e.g. `purplePrimary` is a chip-bg, not a hero number), exclude it via the `pairsWith` constraint and the contract — the audit will only evaluate it against the bgs you nominate, which automatically dodges the heroship question.

## Why these numbers — quick rationale

- **4.5:1 for body** is the WCAG 2.x AA floor for normal text (≤17pt, or ≤13pt-bold). Below this, users with low-vision (20/40 corrected) cannot read body copy reliably.
- **7.0:1 for hero numbers** is the AAA enhancement, locked because hero numbers are the highest-attention single element on a finance/dashboard screen — the user reads these glance-only, often outdoors, often on a low-brightness OLED screen. AA is technically allowed but kiho v6.5 policy is "if it's the protagonist of the screen, it gets AAA".
- **3.0:1 for large text** comes from the same SC 1.4.3 — at ≥18pt or ≥14pt-bold, glyph stroke is wide enough that AA-level contrast is satisfied by a 3.0 ratio.
- **3.0:1 for borders** comes from SC 1.4.11 — non-text UI elements that convey meaning (form-field outlines, focus rings, chip borders) must be distinguishable from their background by 3.0 to be perceivable to low-vision users.

## Edge cases

- **Borders at very low alpha** (e.g. `rgba(26, 26, 31, 0.06)`) are alpha-composited over the bg they ride on before ratio is computed. A `border: rgba(0,0,0,0.06)` against `bg: #FFF8EE` composites to `#F0EEE5`, which contrasts only ~1.13:1 against the bg — that's a real failure, not a false positive. Either bump alpha or change the colour.
- **Glassmorphism `glass` tokens** (e.g. `rgba(255,255,255,0.72)`) are flagged `scrim` and excluded. They are typically rendered as a backdrop layer over a captured frame, NOT as a flat bg with text on top. If your project IS rendering text directly on `glass`, override its role to `bg` in the contract — and budget for AAA (translucent surfaces are tough).
- **OLED `bg = #000000`** automatically clears any non-near-black foreground; the more interesting checks are `surface = #0B0D10` and `surfaceAlt = #14171C`. The audit checks every `fg × bg` pair, so a token that passes against `#000000` but fails against `#0B0D10` will still be flagged.
- **Pure white on pure white** (cream paper-white pairing wave-11d bug, see `tokens.ts:84-90`) collapses to ~1.05:1. The audit catches this immediately if both surfaces are role=`bg` and someone tries to use one of them as `fg` (which the heuristic would do for a token named `paper`).

## Cross-references

- `references/token-contract.md` — schema for `tokens.contract.ts`.
- `references/migration-playbook.md` — how to roll out the threshold across a real codebase without setting CI on fire.
- WCAG 2.1 SC 1.4.3 (Contrast Minimum): https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html
- WCAG 2.1 SC 1.4.6 (Contrast Enhanced): https://www.w3.org/WAI/WCAG21/Understanding/contrast-enhanced.html
- WCAG 2.1 SC 1.4.11 (Non-text Contrast): https://www.w3.org/WAI/WCAG21/Understanding/non-text-contrast.html
- WebAIM contrast formula reference: https://webaim.org/articles/contrast/
