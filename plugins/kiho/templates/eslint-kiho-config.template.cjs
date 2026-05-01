// kiho theme-contrast-guard — ESLint sidecar config (Layer 2)
//
// Drop into project root as `.eslintrc.cjs`, OR merge the `plugins` and
// `rules` blocks into your existing ESLint config.
//
// The three rules below enforce that all colour goes through your theme
// token system, so `bin/contrast_audit.py` (Layer 1) and the runtime
// warner (Layer 3) have a complete picture.
//
// IMPORTANT: the actual rule implementations live in
//   `kiho-plugin/eslint-rules/` (separate sprint — NOT shipped in kiho v6.5).
// This template documents the integration shape so projects can adopt the
// rule names today and the runtime when published.
//
// Install (when published):
//   pnpm add -D eslint-plugin-kiho
//
// Local dev install (against a checked-out kiho-plugin):
//   pnpm add -D file:../kiho-plugin/eslint-plugin-kiho
//   # or `link:` workspace if your monorepo supports it.

module.exports = {
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },

  plugins: ['kiho'],

  rules: {
    // ---------------------------------------------------------------------
    // 1. no-literal-theme-import
    // ---------------------------------------------------------------------
    // Bans `import { palette, macaron, acColors }` (or any token name in
    // `forbidden`) outside of the theme module + chart-library overrides.
    // Forces consumers to go through `useTheme()` / `useThemeColor()`.
    //
    // Migration: start as 'warn' so the IDE highlights but doesn't block
    // commits; tighten to 'error' once Phase 2 codemod has cleared the
    // long tail.
    'kiho/no-literal-theme-import': ['warn', {
      forbidden: ['palette', 'macaron', 'acColors'],
      // Globs of files that ARE allowed to import the literal palettes —
      // typically the theme module itself and chart-library wrappers
      // (where the chart lib's API requires raw hex).
      allowedPaths: [
        '**/theme/**',
        '**/charts/**',
        '**/__tests__/**',
        '**/*.fixture.{ts,tsx}',
      ],
    }],

    // ---------------------------------------------------------------------
    // 2. no-color-scheme-in-app
    // ---------------------------------------------------------------------
    // Bans `import { useColorScheme } from 'react-native'` outside the
    // theme provider. KB rule CV-USE-IN-APP-DARK: dark-mode logic must
    // funnel through ThemeProvider so Layer 1 / 3 / 4 see the active
    // theme; ad-hoc useColorScheme() callers evade all three.
    //
    // Migration: 'warn' during Phase 1; 'error' after Phase 2.
    'kiho/no-color-scheme-in-app': ['warn', {
      allowedPaths: [
        '**/theme/ThemeProvider.{ts,tsx}',
        '**/theme/useThemeColor.{ts,tsx}',
      ],
    }],

    // ---------------------------------------------------------------------
    // 3. no-hex-in-jsx-style
    // ---------------------------------------------------------------------
    // Bans literal `#xxx`, `rgb(`, `rgba(` inside `style={...}` props in
    // JSX. The autofix suggests the closest semantic token from a project-
    // local mapping (configured via the `mapping` option, project-owned).
    'kiho/no-hex-in-jsx-style': ['warn', {
      // Optional: a project-supplied { '#1A1A1F': 'tokens.text', ... } map
      // enables one-shot autofix. Without it the rule reports only.
      mapping: null,
    }],
  },

  // Per-file overrides — relax in tests + the theme module itself
  overrides: [
    {
      files: ['**/__tests__/**', '**/*.test.{ts,tsx}', '**/*.spec.{ts,tsx}'],
      rules: {
        'kiho/no-hex-in-jsx-style': 'off',
        'kiho/no-literal-theme-import': 'off',
      },
    },
    {
      files: ['**/theme/**/*.{ts,tsx}'],
      rules: {
        'kiho/no-literal-theme-import': 'off',
        'kiho/no-color-scheme-in-app': 'off',
      },
    },
  ],
};
