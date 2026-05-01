# Lint sidecar research — Biome + Oxlint custom-rule API survey

**Date:** 2026-05-01
**Author:** kiho v6.6.0 turn-5 cleanup task B
**Scope:** Decide whether to extend the Layer 2 lint sidecar (currently ESLint-only) to natively support Biome and Oxlint, OR ship a tool-agnostic stop-gap. Output drives the templates shipped under `plugins/kiho/templates/`.

---

## TL;DR

| Tool | Custom-rule API status | Verdict for kiho's three rules | Template shipped |
|---|---|---|---|
| **ESLint** (flat or legacy) | stable, mature | full implementation possible (existing path) | `eslint-kiho-config.template.cjs` (unchanged) |
| **Biome v2.x** | **stable for diagnostic-only** GritQL plugin | three rules implementable as `.grit` files; no autofix yet | `biome-kiho.template.json` + 3x `.grit` files |
| **Oxlint v1.62** | **alpha** ESLint-v9-compatible JS plugin API | implementable IF kiho publishes `eslint-plugin-kiho`; otherwise no path | `oxlint-kiho.template.json` (skeleton, references future plugin) |
| **No toolchain / stop-gap** | n/a | three regex grep patterns cover all three rules at file-line granularity | `lint-fallback-grep.sh` + `.ps1` |

**Recommended adoption matrix for downstream projects:**
- Project already on **Biome** → ship the three `.grit` files. Zero npm dependency. Works today on Biome v2.0+.
- Project already on **Oxlint** → wait for `eslint-plugin-kiho` to be published (kiho roadmap), then load via `jsPlugins`. In the interim, run the grep-fallback script in CI.
- Project on **ESLint** → unchanged from v6.5; existing template.
- Project on **none of the above** OR **Stage 0 rollout** → grep-fallback as a CI step. ~15 lines of regex, exits non-zero on any of the three patterns.

---

## 1. Biome plugin / custom-rule API status

### 1.1 What's shipped (as of Biome v2.4.13, released 2026-04-23)

Biome v2.0 (2025-06-17) introduced "Linter Plugins" via the GritQL pattern language. The plugin is a `.grit` file containing one or more pattern queries; each match calls `register_diagnostic(span, message, severity)`.

**Authoritative quote** ([1] Biome docs, "Linter Plugins"):

> Biome Linter supports GritQL plugins. Currently, these plugins allow you to match specific code patterns and register customized diagnostic messages for them.

**Capability boundaries** ([1], [2]):
- Target languages: JavaScript / TypeScript / JSX / TSX (default) and CSS (`language css;` directive). No HTML, JSON, GraphQL plugin language yet.
- API surface: exactly one host function — `register_diagnostic(span, message, severity?)`. No autofix API. No suggestion API. No access to scope analysis or type info.
- Distribution: intentionally unspecified. Plugins are local `.grit` files referenced by relative path in `biome.json`'s `"plugins": ["./path/to/x.grit"]` array. No npm registry channel.
- Suppressions: standard `// biome-ignore lint/plugin:...` works on plugin diagnostics.

**Maturity assessment** ([3] Biome v2 announcement blog):

> Biome 2.0 comes with our first iteration of Linter Plugins. These plugins are still limited in scope: They only allow you to match code snippets and report diagnostics on them. ... It's a first step, but we have plenty of ideas for making them more powerful.

Translation: **stable diagnostic API**, not breaking between v2.0 → v2.4. Future expansions (autofix, distribution) are additive. Safe to ship `.grit` files today.

### 1.2 Can the three kiho rules be expressed as GritQL?

**Rule 1 — `no-literal-theme-import`** (ban `import { palette, macaron, acColors }` outside `theme/**`)

Biome's recipe page already documents the `no-restricted-imports` pattern almost verbatim ([2] GritQL Plugin Recipes):

```grit
`import $bindings from $source` where {
  $bindings <: contains or { `palette`, `macaron`, `acColors` },
  register_diagnostic(
    span = $bindings,
    message = "Import literal theme palette outside theme module — use useTheme()",
    severity = "warn"
  )
}
```

**Caveat — file-path scoping:** GritQL has no built-in `allowedPaths`/`include`/`exclude` per-pattern. To exempt `theme/**` and chart-library wrappers, use Biome's top-level `overrides[].include` to disable the plugin in those subtrees. This is less expressive than the ESLint rule's per-file `allowedPaths` option, but adequate.

**Rule 2 — `no-color-scheme-in-app`** (ban `useColorScheme` from `react-native` outside `theme/ThemeProvider.tsx`)

```grit
`import { $imports } from "react-native"` where {
  $imports <: contains `useColorScheme`,
  register_diagnostic(
    span = $imports,
    message = "useColorScheme outside ThemeProvider — funnel through theme module",
    severity = "warn"
  )
}
```

Same `overrides[].include` exemption pattern for the ThemeProvider file.

**Rule 3 — `no-hex-in-jsx-style`** (ban literal `#xxx` / `rgb(...)` / `rgba(...)` inside `style={...}` JSX prop)

GritQL's recipe page covers a strict superset of this: "No inline style props" + "Ban hardcoded colors" combined. Direct synthesis:

```grit
`style={$value}` where {
  $value <: contains or {
    r"#[0-9a-fA-F]{3,8}",
    r"rgba?\(.*\)",
    r"hsla?\(.*\)"
  } as $hex,
  register_diagnostic(
    span = $hex,
    message = "Literal color in style prop — use semantic theme token",
    severity = "warn"
  )
}
```

**Caveat — autofix not available.** The ESLint version's optional `mapping` autofix (`#1A1A1F` → `tokens.text`) cannot be ported. Diagnostic-only.

### 1.3 Verdict on Biome

**Status: stable / production-ready for diagnostic-only plugins.** All three rules implementable as `.grit` files today with zero npm dependency. Ship.

---

## 2. Oxlint plugin / custom-rule API status

### 2.1 What's shipped (as of Oxlint v1.62.0, released 2026-04-27)

Oxlint's JS Plugin system is **explicitly labeled alpha** in the official docs ([4] Oxlint "JS Plugins"):

> JS plugins are currently in alpha, and remain under active development. All APIs should behave identically to ESLint. If you find any differences in behavior, that's a bug — please report it.

**Capability** ([4], [5]):
- ESLint v9+ compatible plugin API. Same `create(context)` / visitor pattern. `context.report({ node, message })` works.
- Alternative `createOnce()` API for performance (compatible with both ESLint and Oxlint via `eslintCompatPlugin()` wrapper from `@oxlint/plugins`).
- Loads via `jsPlugins: ["./plugin.js"]` or `jsPlugins: ["eslint-plugin-foo"]` (npm specifier).
- Plugin aliases supported (avoid name clash with native Oxlint plugins).
- Suggestions and quick-fixes supported through the LSP.

**What's NOT supported yet** ([4]):
- Custom file formats / parsers (Svelte, Vue, Angular custom syntax — only the `<script>` block is linted).
- Type-aware rules in plugins.
- ESLint APIs removed in v9 or earlier.

### 2.2 Can the three kiho rules be implemented for Oxlint?

**In principle, yes** — because Oxlint's plugin API is ESLint-compatible. If kiho publishes `eslint-plugin-kiho` to npm with the three rules implemented as standard ESLint visitor objects, Oxlint can consume the exact same package via:

```jsonc
{
  "jsPlugins": ["eslint-plugin-kiho"],
  "rules": {
    "kiho/no-literal-theme-import": "warn",
    "kiho/no-color-scheme-in-app": "warn",
    "kiho/no-hex-in-jsx-style": "warn"
  }
}
```

**Blocker — `eslint-plugin-kiho` does not exist yet.** The current kiho v6.5 ESLint template explicitly states:

> IMPORTANT: the actual rule implementations live in `kiho-plugin/eslint-rules/` (separate sprint — NOT shipped in kiho v6.5).

Until that sprint completes, neither ESLint nor Oxlint has a real loadable plugin. The current ESLint template documents the integration shape; the same approach applies to Oxlint.

### 2.3 Verdict on Oxlint

**Status: alpha API, but unblocked from kiho's side IF and ONLY IF the eslint-plugin-kiho npm package is published.** We ship a config-skeleton template (`oxlint-kiho.template.json`) that references the future plugin, mirroring the existing ESLint template's documentation pattern. **Until that day, Oxlint users should run the grep-fallback in CI.**

---

## 3. Why ship grep-fallback as well

Three reasons:

1. **Phase 0 / Phase 1 rollout** (per `migration-playbook.md`) explicitly defers Layer 2 lint until Phase 2. Projects in Phase 0–1 want SOME signal on the three rules before they install any plugin. A 30-line grep script gives them that signal in CI as a non-blocking warn.

2. **`eslint-plugin-kiho` is not yet published.** Until the rule code ships, ESLint users with the template have a config but no rules. Oxlint users have neither. grep-fallback is the only "works today" option for non-Biome projects.

3. **Toolchain heterogeneity in monorepos.** A project may have Biome at root + Oxlint in one workspace + ESLint in another. The fallback CI step is a tool-agnostic backstop that catches drift the per-tool plugins might miss.

The grep-fallback is **explicitly a stop-gap.** Once `eslint-plugin-kiho` ships AND the project's chosen tool reaches stable plugin support, the grep step is removed. The fallback README documents this exit criterion.

---

## 4. Recommended sidecar topology

```
                        ┌──────────────────────────┐
                        │  kiho three lint rules   │
                        │  (specified in SKILL.md) │
                        └────────────┬─────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
   ┌────▼────┐                  ┌────▼────┐                  ┌────▼─────┐
   │ ESLint  │                  │  Biome  │                  │  Oxlint  │
   │ plugin  │                  │ GritQL  │                  │ JS plugin│
   │         │                  │  .grit  │                  │ (alpha)  │
   └────┬────┘                  └────┬────┘                  └────┬─────┘
        │                            │                            │
   eslint-plugin-kiho           biome-kiho.template.json     oxlint-kiho.template.json
   (future sprint)            + 3x .grit files (today)        (skeleton — needs
                                                                eslint-plugin-kiho)
        │                            │                            │
        └────────────────────────────┼────────────────────────────┘
                                     │
                       ┌─────────────▼──────────────┐
                       │   grep-fallback (today)    │
                       │   POSIX .sh + Windows .ps1 │
                       │   stop-gap for ALL paths   │
                       └────────────────────────────┘
```

**Key design choice:** the three tools are NOT mutually exclusive — a project on Biome may ALSO run ESLint for `react-hooks/exhaustive-deps` (which Biome lacks). kiho's templates compose; users pick whichever subset of paths apply to their toolchain.

**Trade-off matrix:**

| Concern | ESLint plugin | Biome GritQL | Oxlint plugin | grep-fallback |
|---|---|---|---|---|
| IDE integration | excellent (every editor) | good (Biome ext) | good (Oxlint ext) | none — CI only |
| Speed | slow (~10s/k files) | very fast (Rust) | extremely fast (Rust + JS bridge) | fastest (~0.1s) |
| Autofix | yes | no (today) | yes (when plugin published) | no |
| Per-file allowedPaths | yes | overrides[].include | yes | shell glob |
| Diagnostic precision | column-accurate | column-accurate | column-accurate | line-accurate |
| Distribution maturity | stable | stable | alpha | n/a |
| Today (2026-05-01) availability | needs eslint-plugin-kiho | works today via .grit | needs eslint-plugin-kiho | works today |

---

## 5. Migration paths per toolchain

### 5.1 Project on Biome

```bash
# Copy the three .grit files into your repo
cp .kiho-plugin/plugins/kiho/templates/grit/*.grit .biome/kiho/

# Merge plugins[] into biome.json
# (or copy biome-kiho.template.json as a starting point)
```

`biome.json` snippet:
```jsonc
{
  "plugins": [
    "./.biome/kiho/no-literal-theme-import.grit",
    "./.biome/kiho/no-color-scheme-in-app.grit",
    "./.biome/kiho/no-hex-in-jsx-style.grit"
  ],
  "overrides": [
    { "include": ["**/theme/**", "**/charts/**", "**/__tests__/**"], "linter": { "enabled": false } }
  ]
}
```

Run: `pnpm biome lint`.

### 5.2 Project on Oxlint

**Today (eslint-plugin-kiho not yet published):** run the grep-fallback in CI as a non-blocking warn step. Track the kiho roadmap; flip to `jsPlugins` once published.

**After publication:**
```jsonc
// .oxlintrc.json
{
  "jsPlugins": ["eslint-plugin-kiho"],
  "rules": {
    "kiho/no-literal-theme-import": "warn",
    "kiho/no-color-scheme-in-app": "warn",
    "kiho/no-hex-in-jsx-style": "warn"
  }
}
```

Run: `pnpm oxlint`.

### 5.3 Project on ESLint

Unchanged from v6.5. Use `templates/eslint-kiho-config.template.cjs`. Same pre-publication grep-fallback caveat applies.

### 5.4 Project on none of the above (or in Phase 0/1 rollout)

CI step:
```yaml
- name: kiho lint fallback
  run: bash .kiho-plugin/plugins/kiho/templates/lint-fallback-grep.sh apps/mobile/src
  continue-on-error: true   # warn-only until Phase 2
```

---

## 6. Citations

[1] Biome — Linter Plugins (official docs). https://biomejs.dev/linter/plugins/  — fetched 2026-05-01. Quote on line 1.1: "Biome Linter supports GritQL plugins. Currently, these plugins allow you to match specific code patterns and register customized diagnostic messages for them."

[2] Biome — GritQL Plugin Recipes (official docs). https://biomejs.dev/recipes/gritql-plugins/ — fetched 2026-05-01. Source of the "no inline style props" + "ban hardcoded colors" + "no restricted imports" recipes used as direct templates for kiho's three rules.

[3] Biome v2 announcement — "Biotype". https://biomejs.dev/blog/biome-v2/ — published 2025-06-17. Quote: "Biome 2.0 comes with our first iteration of Linter Plugins. These plugins are still limited in scope: They only allow you to match code snippets and report diagnostics on them."

[4] Oxlint — JS Plugins (official docs). https://oxc.rs/docs/guide/usage/linter/js-plugins — fetched 2026-05-01. Quote: "JS plugins are currently in alpha, and remain under active development. All APIs should behave identically to ESLint."

[5] Oxlint — Writing JS Plugins (official docs). https://oxc.rs/docs/guide/usage/linter/writing-js-plugins — fetched 2026-05-01. Source for the `eslintCompatPlugin()` wrapper, `createOnce()` performance API, and the `before`/`after` hook semantics.

**Release version cross-check (GitHub API):**
- Biome: `@biomejs/biome@2.4.13` published 2026-04-23 (latest as of research date).
- Oxlint: `apps_v1.62.0` (oxlint v1.62.0) published 2026-04-27 (latest as of research date).

---

## 7. Decision log

- **DO ship** Biome `.grit` files now — API is stable and capability is sufficient for the three rules in diagnostic mode.
- **DO ship** Oxlint config skeleton now (referencing future `eslint-plugin-kiho`), mirroring the ESLint template pattern. Document the alpha-API caveat.
- **DO ship** grep-fallback POSIX + Windows scripts as the universal stop-gap.
- **DO NOT** fake an Oxlint plugin implementation — alpha API is unstable, and shipping JS rule code now risks rework. Defer until `eslint-plugin-kiho` is the source of truth.
- **DO NOT** lift the existing `eslint-kiho-config.template.cjs` — it remains the canonical reference for what each rule MUST detect.
- **Revisit at v6.7 / v6.8:** Biome plugin autofix, Oxlint plugin GA, and `eslint-plugin-kiho` publication. At that point the grep-fallback can be deprecated and the templates promoted to "primary path" for each toolchain.
