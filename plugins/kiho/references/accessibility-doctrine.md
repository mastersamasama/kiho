# Accessibility doctrine — kiho v6.5+

This is the public-facing doctrine doc for accessibility on kiho-using projects. Where `references/content-routing.md` codifies how knowledge flows between lanes, this doc codifies what kiho considers the floor for shipping a UI.

The doctrine is **opinionated**. It is also conservative — every rule below maps to a published WCAG 2.1 success criterion at AA or AAA level, and every rule has a tool that catches violations before they ship.

## Why this matters

- **Users with low vision** (≈12% of the global population, much higher in 50+ demographics) cannot read body text below 4.5:1 contrast reliably under typical lighting.
- **Outdoor-mobile usage** — finance / dashboard apps are read in sunlight; even fully sighted users see effective contrast halved by glare. AAA-on-hero is a robust margin.
- **Dark-mode regressions** are the #1 silent ship in any theme migration. A code review that spends 30 minutes on light mode and 2 minutes on dark mode WILL miss them. Tooling has to close that gap.
- **Non-text contrast** (form-field outlines, focus rings, chip borders) was a WCAG 2.1 addition in 2018 and is still routinely missed by toolkits that only check text. Layer 1 + Layer 4 catch this.

This doctrine treats accessibility as **engineering correctness**, not a checkbox at the end of a sprint.

## The four layers and their WCAG mapping

kiho v6.5 enforces accessibility via four defence layers. Each layer maps to one or more WCAG success criteria.

| Layer | Tool | WCAG SC mapped | What it asserts |
|---|---|---|---|
| 1 — Design-time | `bin/contrast_audit.py` | 1.4.3, 1.4.6, 1.4.11 | Every fg × bg pair in `tokens.ts` clears its threshold. |
| 2 — Lint-time | `eslint-plugin-kiho` (sidecar) | 1.4.3 (precondition) | No inline hex; all colour goes through the theme token system, so Layer 1's audit is sufficient. |
| 3 — Runtime dev | `runtime-contrast-warner.ts` | 1.4.3, 1.4.6 | Dynamic colour composition (state, props, conditionals) doesn't drop below threshold. |
| 4 — CI | Playwright + axe-core | 1.4.3, 1.4.6, 1.4.11 | Real DOM in real layout in real themes still passes. |

Each layer is necessary but not sufficient on its own:

- **Layer 1 alone** misses dynamic composition (state-driven colour, prop overrides).
- **Layer 2 alone** ensures tokens are used but not that the tokens are valid.
- **Layer 3 alone** catches what users see but only on screens a developer renders in dev.
- **Layer 4 alone** is comprehensive but slow and tests only the narrow set of e2e-covered screens.

## The success criteria, plain-language

### WCAG 2.1 SC 1.4.3 — Contrast (Minimum) [AA]

> The visual presentation of text and images of text has a contrast ratio of at least 4.5:1, except for: large text (3:1), incidental text in inactive UI components or pure decoration, and logos.

kiho enforcement: **every `fg` token must clear 4.5:1 against every `bg` token it can legally pair with.** Heuristic: if you don't constrain via `pairsWith`, the audit assumes cross-product.

### WCAG 2.1 SC 1.4.6 — Contrast (Enhanced) [AAA]

> The visual presentation of text and images of text has a contrast ratio of at least 7:1, except for: large text (4.5:1), incidental text, and logos.

kiho enforcement: **hero numbers (the largest single number on a finance/dashboard screen) MUST clear 7:1.** This is user-locked policy in v6.5, applied via `--hero-tokens` flag or convention regex. Body text is NOT required to clear AAA — that is a project choice.

### WCAG 2.1 SC 1.4.11 — Non-text Contrast [AA]

> The visual presentation of [user interface components and graphical objects] has a contrast ratio of at least 3:1 against adjacent color(s).

kiho enforcement: **every `border` token must clear 3.0:1 against every `bg` it rides on.** Includes 1px hairline dividers, focus rings, chip outlines. Decorative shadows and glows are excluded — they don't convey state or boundaries.

## Doctrinal stances

These are kiho positions, not WCAG mandates. They are higher than the floor.

1. **Hero numbers are AAA, always.** A finance app's hero number is the protagonist of the screen. AA is technically allowed but kiho-using projects ship AAA on these.
2. **Glassmorphism is a luxury, not a default.** A `glass` token rendered as a primary surface is excluded from Layer 1 by default (role: `scrim`). If your project IS rendering text directly on glass, you are budgeting for an AAA-equivalent design problem and should document the trade-off.
3. **Theme swap perf is part of accessibility.** A theme toggle that re-renders the entire tree at 30fps is unusable for users with motion sensitivity. Phase 3 of the migration playbook includes a context split because perf IS accessibility.
4. **`useColorScheme()` is a hazard outside the theme module.** It bypasses the theme system, evades Layer 1, evades Layer 2, evades Layer 3. The `kiho/no-color-scheme-in-app` ESLint rule exists to prevent this.
5. **A project that adopts kiho gets contrast for free.** No project should have to write a custom audit script. `bin/contrast_audit.py` is pure stdlib so it runs anywhere CI runs Python.

## What this doctrine does NOT cover (yet)

- **Keyboard / focus order** — out of scope for v6.5; covered by general RN-Web accessibility guidance.
- **Screen reader semantics** — `accessibilityRole` / `accessibilityLabel` audit is a separate skill.
- **Motion / vestibular** — `prefers-reduced-motion` handling is project-level.
- **Form-field labelling** — covered by axe-core in Layer 4 implicitly, but not first-class.
- **Colour-only state** — "red = error" without an icon is a separate audit dimension.

These are tracked as future skill candidates. They are NOT permission to ship without addressing them — your project should still do them, just without kiho-supplied automation in v6.5.

## Cross-references

- `skills/engineering/theme-contrast-guard/SKILL.md` — the contrast guard skill itself.
- `skills/engineering/theme-contrast-guard/references/contrast-thresholds.md` — exact threshold table.
- `skills/engineering/theme-contrast-guard/references/migration-playbook.md` — Phase 0 → Phase 3 rollout.
- `references/content-routing.md` — KB / state / memory routing for audit reports.
- WCAG 2.1: https://www.w3.org/TR/WCAG21/
- WebAIM contrast formula: https://webaim.org/articles/contrast/
- React Native accessibility guide: https://reactnative.dev/docs/accessibility
