# Migration playbook — Phase 0 → Phase 3

A generic four-phase rollout for any /kiho project adopting the contrast guard. The phases minimise developer pain by ratcheting strictness only after the codebase is clean — no CI-on-fire moments, no rolled-back commits.

This playbook is **project-agnostic**. The kiho v6.5 reference implementation is 33Ledger; substitute your project name, theme directory, and timeline as appropriate.

## Phase 0 — Instrumentation (1 day, zero behaviour change)

**Goal:** make Layer 1 + Layer 3 visible without changing any rendered output.

Steps:

1. **Add `tokens.contract.ts`** next to your existing `tokens.ts`. Copy `templates/tokens.contract.template.ts` from the kiho-plugin and fill in entries for AT LEAST the surface bgs and the primary `text` / `textMuted` foregrounds. The rest can stay heuristic.
2. **Wire the runtime warner** in `__DEV__` only. Copy `templates/runtime-contrast-warner.template.ts` to `apps/<x>/src/theme/runtime-contrast-warner.ts`. In `ThemeProvider.tsx`, on mount:
   ```ts
   if (__DEV__) installContrastWarner({ threshold: 4.5 });
   ```
3. **Run Layer 1 once locally** to capture baseline drift:
   ```bash
   python <kiho>/bin/contrast_audit.py \
     --tokens apps/<x>/src/theme/tokens.ts \
     --threshold mixed --themes <theme1>,<theme2> \
     --md-out .kiho/audit/contrast/baseline.md
   ```
4. **Do NOT add to CI yet.** Stash the baseline as a "known issues" doc and discuss with the design partner before fixing.

**Exit criteria:** baseline report exists; runtime warner logs visible in dev console; no production behaviour changed.

## Phase 1 — Layer 1 + Layer 4 land (warn-only) (2-3 days)

**Goal:** Layer 1 in CI as warn-only; Layer 4 (Playwright/axe) capturing real DOM contrast on the hottest 5 screens × 2 modes.

Steps:

1. **Add Layer 1 to CI** as a non-blocking step:
   ```yaml
   - name: Theme contrast audit
     run: |
       python .kiho-plugin/plugins/kiho/bin/contrast_audit.py \
         --tokens apps/mobile/src/theme/tokens.ts \
         --threshold mixed --themes <themes> \
         --md-out contrast-audit.md \
         --json-out contrast-audit.json
     continue-on-error: true   # warn-only this phase
   ```
2. **Add Playwright/axe smoke** for ~5 hero screens × light + dark = 10 runs. Budget ~30s per PR.
3. **Triage the baseline.** Each finding gets one of:
   - **Real bug** → fix the token value (designer in the loop).
   - **Pairing constraint** → add `pairsWith` in `tokens.contract.ts` so the audit no longer evaluates this fg against this bg.
   - **Decorative** → mark role as `glow` / `shadow` / `scrim`.
4. **Iterate until clean.** Re-run audit after each token change. Aim: zero `fail`, ≤ a documented short list of `warn` (explicit pairs you accepted).

**Exit criteria:** Layer 1 audit exits 0 in CI on every PR; Playwright/axe stays green.

## Phase 2 — Layer 2 lint roll-out (1 week)

**Goal:** Layer 2 sidecar enforces no inline hex / no `palette.*` literal imports / no `useColorScheme` outside the theme module. Codemod handles the bulk of the existing violations.

Since v6.6.0, kiho ships four toolchain paths — pick the one that matches your project (or run grep-fallback while the chosen plugin matures). The three rules are identical across paths; only the host integration differs.

### Step 1 — Drop in the sidecar (pick ONE path per repo)

#### Path A — ESLint (current ecosystem default; needs `eslint-plugin-kiho` published)

```bash
# Copy the config template
cp .kiho-plugin/plugins/kiho/templates/eslint-kiho-config.template.cjs ./.eslintrc.cjs
pnpm add -D eslint-plugin-kiho   # when published; until then, run Path D in parallel
```

Inventory:
```bash
pnpm eslint . --rule 'kiho/no-literal-theme-import:error' \
              --rule 'kiho/no-color-scheme-in-app:error' \
              --rule 'kiho/no-hex-in-jsx-style:error' \
              | tee eslint-baseline.txt
```

#### Path B — Biome v2 (works today; no npm dep)

```bash
# Copy GritQL plugin files
mkdir -p .biome/kiho
cp .kiho-plugin/plugins/kiho/templates/grit/*.grit .biome/kiho/

# Merge plugins[] block from biome-kiho.template.json into your biome.json
# (or use it as the starting point if you have no biome.json yet)
```

Inventory:
```bash
pnpm biome lint . | tee biome-baseline.txt
```

Caveat: GritQL plugin API is diagnostic-only as of Biome v2.4.x — no autofix. Plan a manual codemod pass.

#### Path C — Oxlint (alpha plugin API; needs `eslint-plugin-kiho` published)

```bash
# Copy the config template
cp .kiho-plugin/plugins/kiho/templates/oxlint-kiho.template.json ./.oxlintrc.json
pnpm add -D eslint-plugin-kiho   # when published; until then, run Path D in parallel
```

Inventory:
```bash
pnpm oxlint . | tee oxlint-baseline.txt
```

#### Path D — grep-fallback (toolchain-agnostic stop-gap, works today)

POSIX (Linux / macOS / Git Bash on Windows):
```bash
bash .kiho-plugin/plugins/kiho/templates/lint-fallback-grep.sh apps/mobile/src \
  | tee grep-baseline.txt
```

Windows native PowerShell:
```powershell
pwsh -File .kiho-plugin\plugins\kiho\templates\lint-fallback-grep.ps1 apps\mobile\src `
  | Tee-Object -FilePath grep-baseline.txt
```

Use this path:
- During the Phase 0 / Phase 1 window when no plugin is installed yet.
- For mixed-toolchain monorepos (one workspace on Biome, another on Oxlint).
- As a CI-only redundancy backstop alongside any of the above plugin paths.

### Step 2 — Codemod the high-frequency mappings

Most projects find that 50-70% of violations match a small set of mappings:
```
palette.text     → tokens.text
palette.muted    → tokens.textMuted
macaron.cream    → tokens.bg
macaron.paperWhite → tokens.surface
```
A `jscodeshift` script with these four rules typically clears the long tail in one pass.

### Step 3 — Manual sweep
Manual sweep for residue: category-specific tints, chart-library palette overrides, `useColorScheme` callers. Budget 3-4 small PRs.

### Step 4 — Grandfather list
Files that should never lint:
- `theme/tokens.ts` — the token source itself
- `theme/ThemeProvider.tsx` — the only legal `useColorScheme()` caller
- `__tests__/` and `e2e/fixtures/` — test data may contain hex literals

### Step 5 — Flip to `error`
Flip the rule severities to `error` in CI once the codebase is clean. IDE remains `warn` (lower friction). For Biome the `.grit` file's `severity = "error"` line is what to flip; for Oxlint / ESLint, change `"warn"` to `"error"` in the rule entry.

**Exit criteria:** lint command exits 0 in CI; no grandfather-list violations; the grep-fallback step (if you ran one in parallel) reports zero hits.

## Phase 3 — Layer 3 hard mode + perf split (1 week)

**Goal:** runtime warner gains a strict mode (throws in dev render) for severe violations; theme context split eliminates the "every consumer re-renders on theme swap" perf cliff.

Steps:

1. **Strict mode env flag.** Update the runtime warner so when `process.env.KIHO_CONTRAST_STRICT === 'true'` (or a config flag is set), low-contrast pairs `throw` in dev render rather than `console.warn`. This forces designers to handle violations before they ship to QA.
2. **Theme context split.** Refactor `ThemeProvider.tsx` from a single `useMemo([themeMode, systemScheme])` to:
   - `<ThemeIdentityContext>` — themeName only (small subset of consumers)
   - `<ThemeTokensContext>` — resolved tokens (universal)
   - `useThemeColor(key)` selector hook backed by `useSyncExternalStore`
   - On web, additionally use CSS variables (single `data-theme` on `<html>`, subtree never re-renders)
3. **Provide a compat shim** for legacy `useTheme()` callsites until the full migration is done.
4. **Acceptance:** typecheck clean, all visual tests still pass, theme-swap re-render count drops by 80%+ on a representative screen.

**Exit criteria:** strict mode opt-in works; theme swap no longer re-renders the entire tree; `useThemeColor()` is the documented happy path.

## Cross-project reuse — what kiho-plugin contributes vs what each project owns

| Asset | Owned by kiho-plugin | Owned by project |
|---|---|---|
| `bin/contrast_audit.py` | x | (none — invoke as-is) |
| `tokens.contract.template.ts` | x (template) | x (filled-in copy in `apps/<x>/src/theme/`) |
| `runtime-contrast-warner.template.ts` | x (template) | x (filled-in copy in `apps/<x>/src/theme/`) |
| ESLint plugin code (`eslint-plugin-kiho/rules/*`) | x (separate sprint, not in v6.5/v6.6) | (none — install + configure) |
| Biome GritQL plugins (`templates/grit/*.grit`) | x (since v6.6.0) | (copy into `.biome/kiho/`) |
| Oxlint config skeleton (`templates/oxlint-kiho.template.json`) | x (since v6.6.0) | (copy + wait on `eslint-plugin-kiho`) |
| grep-fallback (`templates/lint-fallback-grep.{sh,ps1}`) | x (since v6.6.0) | (wire into CI as a non-blocking step until plugin paths mature) |
| Codemod scripts (`jscodeshift`) | (advisory examples only) | x (per-project palette mapping) |
| GitHub Action wiring | x (template) | x (project's `.github/workflows/`) |

## Anti-patterns to avoid

- **Don't suppress the audit per-token** with comments like `// audit-skip`. The audit is a check, not a constraint to be argued with — fix the token value or constrain it via `pairsWith`.
- **Don't relax the threshold below the user-locked policy** (4.5/7.0/3.0). The `--threshold AA` mode exists for projects without hero designations, NOT as a relaxation lever.
- **Don't disable the runtime warner in dev to silence noise.** If it's noisy, that's signal — fix the tokens.
- **Don't merge a PR with `continue-on-error: true` in Phase 1 if the report shows new failures vs baseline.** Warn-only is for grandfathered noise, not for shipping new violations.
- **Don't grandfather a file forever.** Phase 2 manual sweep should reduce the grandfather list to truly inert assets (test fixtures, the theme module itself). Anything else is a TODO.

## Cross-references

- `SKILL.md` — invocation & worked examples per layer.
- `references/contrast-thresholds.md` — exact ratio table.
- `references/token-contract.md` — `tokens.contract.ts` schema spec.
- Top-level `references/accessibility-doctrine.md` — kiho doctrine doc on WCAG SC mapping.
