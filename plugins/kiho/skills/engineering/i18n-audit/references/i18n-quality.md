# i18n quality — heuristic catalogue (sk-087 internal reference)

This file documents the deterministic heuristics implemented in `bin/i18n_audit.py`. It is the source-of-truth spec the audit script implements; if a behaviour drifts from this document, the bug is in the script.

## Brand allowlist schema

Projects supply a TOML allowlist at `<project>/.kiho/config/i18n-allowlist.toml`. The audit reads it via stdlib `tomllib`. Schema:

```toml
canonical = "en"     # canonical locale name (overridable via --canonical)

[brands]
# String values that may appear identical across locales (proper nouns)
values = ["iCloud", "Claude", "OpenAI", "Groq", "33Ledger", "Apple Pay", "Touch ID"]

[brands.keys]
# Key glob patterns whose en/locale identical-value is intentional.
# '*' matches any character span. Anchored at start AND end implicitly.
match = ["settings.ai.PROVIDER_*", "settings.sync.ICLOUD", "onboarding.SYNC_ICLOUD"]

[hardcoded.allow_paths]
# File paths exempt from hardcoded-string check (relative to project-root,
# matched against the posix-style relative path). Supports **, *, ?, {a,b}.
patterns = ["**/__tests__/**", "**/*.test.{ts,tsx}", "**/*.fixture.{ts,tsx}"]

[deadkey.allow_keys]
# Keys still in JSON but used dynamically (e.g. `t(`events.KIND_${k}`)`).
# Any locale key whose dotted path starts with one of these prefixes is
# treated as referenced.
prefixes = ["events.KIND_"]

[deadkey.amnesty]
# One-time grandfathered list. The auto-bootstrap mode (future v2) emits
# this section with the current dead-key set so projects can adopt
# strict-warn without a big-bang cleanup.
keys = []
```

If the file is missing, defaults apply: empty brand sets, default test-path patterns, empty dead-key allowlist.

## Placeholder regex spec

Two regex families, run in order:

```python
ICU_TOP_RE     = r"\{\s*(\w+)\s*,\s*(plural|select|selectordinal)\b"
PLACEHOLDER_RE = r"\{([^{}]+)\}"
```

### Algorithm

1. Find every ICU construct (`{count, plural, ...}` / `{gender, select, ...}` / `{n, selectordinal, ...}`) using `ICU_TOP_RE`. For each match:
   - Walk the string from the match's `{` forward, brace-counting until depth returns to 0; record the span.
   - Add `"{name}:{kind}"` to the placeholder set (e.g. `count:plural`).
2. Find every simple `{var}` using `PLACEHOLDER_RE`. Skip:
   - any match whose start offset lies inside an ICU span,
   - any body containing `,` (it's an ICU body fragment),
   - any body equal to a CLDR plural keyword (`one`, `other`, `few`, `many`, `two`, `zero`),
   - any body starting with `#` (ICU number marker).
3. Compare locale placeholder set vs canonical placeholder set. **Set equality** required (order-free).

### Why this shape?

- Set equality, not list equality: translators legitimately reorder placeholders (e.g. SOV vs SVO grammars).
- ICU `{count:plural}` ≠ plain `{count}`: collapsing an ICU plural to `{count}` is a real bug — the CLDR rules are dropped, so the displayed string skips singular/plural rendering.
- Number marker `#` and CLDR keywords are filtered to avoid double-counting ICU internals.

## Dead-key escape-hatch syntax

Place near the dynamic call site:

```ts
// i18n-keep prefix=events.KIND_      // keep all keys under this prefix
// i18n-keep onboarding.SLIDE_4_TITLE // keep this exact key
```

The audit also accepts a per-project allowlist:

```toml
[deadkey.allow_keys]
prefixes = ["events.KIND_", "transactions.TYPE_"]
```

Either path satisfies the check; you do not need both.

## Test-path allowlist defaults

If `i18n-allowlist.toml` is absent or omits `[hardcoded.allow_paths]`, these patterns apply:

```
**/__tests__/**
**/*.test.ts
**/*.test.tsx
**/*.fixture.ts
**/*.fixture.tsx
```

User-supplied patterns REPLACE these defaults (no merge), so re-include the defaults in your TOML if you customise.

## Hard-coded string detection regex catalogue

Four orthogonal regex passes per source file:

### Pattern A — JSX `<Text>literal</Text>`

```
<Text\b[^>]*>\s*([A-Z][A-Za-z][^<{}\n]{1,80})\s*</Text>
```

Anchored on uppercase first letter to skip whitespace-only / numeric-only / interpolated children. Tolerates attributes (e.g. `<Text style={s}>`).

**False positives gated out:**
- Pure `{interpolated}` content (`{` excluded from charset)
- Multi-line content (`\n` excluded)
- Strings starting with `[debug]` / `TODO` / `FIXME` (dev-log prefix)

### Pattern B — `accessibilityLabel="literal"`

```
accessibilityLabel\s*=\s*\{?\s*["']([^"'\n]{2,120})["']\s*\}?
```

Catches both `accessibilityLabel="..."` and `accessibilityLabel={"..."}` forms.

### Pattern C — `Alert.alert("title", "message")`

```
Alert\.alert\s*\(\s*["']([^"'\n]{2,120})["'](?:\s*,\s*["']([^"'\n]{2,200})["'])?
```

Captures both title (group 1, required) and optional message (group 2).

### Pattern D — `ActionSheetIOS.showActionSheetWithOptions({ options: [...] })`

Two-phase: outer block regex extracts the `options: [...]` array, inner regex extracts string literals from inside. Multi-line tolerant.

```python
ACTIONSHEET_BLOCK_RE   = r"ActionSheetIOS\.showActionSheetWithOptions\s*\(\s*\{[^}]*options\s*:\s*\[([^\]]*)\]"
ACTIONSHEET_LITERAL_RE = r'["\']([^"\']{2,80})["\']'
```

### Allowlisted prefixes

A literal matching `DEV_LOG_PREFIX_RE = r"^\s*(?:\[(?:debug|dev|todo|fixme)\]|TODO|FIXME)"` is skipped — it's almost certainly dev-only output.

### Known false-positive examples

- `<Text>{count}</Text>` — interpolated, charset rejects `{`.
- `accessibilityLabel="abc"` where `abc` is a CSS-style token — current rule flags this; suppress via `[hardcoded.allow_paths]` if you isolate token files.
- `Alert.alert(t('alerts.X'), t('alerts.Y'))` — both args are `t(...)` calls, not string literals; regex requires bare `"..."` and won't match.

## Code-glob expansion

The script implements brace expansion (`{a,b}`) and ripgrep-style `**` globbing in pure stdlib (no `pathspec` dep). See `_expand_braces()` and `_glob_to_regex()` in `bin/i18n_audit.py`.

Known limitations:
- Brace expansion is single-level (no nested `{a,{b,c}}`).
- `?` matches single non-slash char only.
- Path matching is anchored to `project_root` and uses POSIX separators.

## v2 clarity heuristic (preview, not shipped in v6.5)

The v2 hook (`_check_clarity_v2`) is a stub. Planned shape:

1. Read `<project>/.kiho/config/glossary.toml` if present.
2. Cross-check locale strings against `references/i18n-known-jargon.md` (advisory list of high-register accounting / medical / legal terms).
3. Emit `severity: info` findings only — never blocks CI. Suggestions take the form "consider X (formal: Y) for clarity" and require explicit project opt-in via `glossary.adopt_advisory = true`.

The advisory list is opt-in: projects pick which categories to honour.
