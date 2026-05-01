#!/usr/bin/env bash
# kiho theme-contrast-guard — Layer 2 lint fallback (POSIX)
#
# Stop-gap until the chosen toolchain has a working kiho plugin:
#   - ESLint:  needs eslint-plugin-kiho published (kiho roadmap)
#   - Biome:   today, prefer biome-kiho.template.json + .grit files
#   - Oxlint:  alpha plugin API, also waits on eslint-plugin-kiho
#
# Three regex patterns mirror the three SKILL.md rules:
#   1. no-literal-theme-import   -> import { palette | macaron | acColors }
#   2. no-color-scheme-in-app    -> useColorScheme from 'react-native'
#   3. no-hex-in-jsx-style       -> #xxx / rgb / rgba inside style={...}
#
# Usage:
#   bash lint-fallback-grep.sh apps/mobile/src
#   bash lint-fallback-grep.sh apps/mobile/src apps/web/src
#
# Exit codes:
#   0 — clean
#   1 — at least one violation
#   2 — bad invocation
#
# Excluded paths (hardcoded — edit if your tree differs):
#   **/theme/**, **/charts/**, **/__tests__/**, **/node_modules/**

set -u

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <src-dir> [<src-dir2> ...]" >&2
  exit 2
fi

# Pick a grep that supports -E -r --include and PCRE-ish character classes.
# `grep -E` is POSIX; everything used below is portable BSD/GNU grep.

EXCLUDES=(
  "--exclude-dir=node_modules"
  "--exclude-dir=theme"
  "--exclude-dir=charts"
  "--exclude-dir=__tests__"
  "--exclude-dir=.git"
  "--exclude-dir=dist"
  "--exclude-dir=build"
)

# Glob: only TS/TSX/JS/JSX. Keeps the script fast and avoids JSON/MD noise.
INCLUDES=(
  "--include=*.ts"
  "--include=*.tsx"
  "--include=*.js"
  "--include=*.jsx"
)

violations=0

emit_section() {
  local name="$1"
  local count="$2"
  printf '\n[kiho-fallback] rule: %s — %d hit(s)\n' "$name" "$count"
}

for src in "$@"; do
  if [ ! -d "$src" ]; then
    echo "warn: '$src' is not a directory — skipping" >&2
    continue
  fi

  # ---------------------------------------------------------------------
  # Rule 1: no-literal-theme-import
  # Match: import ... { palette | macaron | acColors } ... from ...
  # ---------------------------------------------------------------------
  pat1='^[[:space:]]*import[[:space:]].*\b(palette|macaron|acColors)\b.*from'
  hits1=$(grep -E -r -n "${EXCLUDES[@]}" "${INCLUDES[@]}" "$pat1" "$src" 2>/dev/null || true)
  if [ -n "$hits1" ]; then
    n=$(printf '%s\n' "$hits1" | wc -l | tr -d ' ')
    emit_section "kiho/no-literal-theme-import" "$n"
    printf '%s\n' "$hits1"
    violations=$((violations + n))
  fi

  # ---------------------------------------------------------------------
  # Rule 2: no-color-scheme-in-app
  # Match: useColorScheme imported from 'react-native'
  # Note: false positive on require() not handled here; comment-only suppression
  # uses standard `// kiho-skip` (the future plugin will honour it).
  # ---------------------------------------------------------------------
  # Single quote escape: '"'"' switches out of single-quoted string, inserts a
  # literal ', then re-enters. Result: the regex character class contains
  # both ' and " so it matches either quote style around `react-native`.
  pat2='useColorScheme.*from.*['"'"'"]react-native['"'"'"]|from[[:space:]]*['"'"'"]react-native['"'"'"].*useColorScheme'
  hits2=$(grep -E -r -n "${EXCLUDES[@]}" "${INCLUDES[@]}" "$pat2" "$src" 2>/dev/null || true)
  if [ -n "$hits2" ]; then
    n=$(printf '%s\n' "$hits2" | wc -l | tr -d ' ')
    emit_section "kiho/no-color-scheme-in-app" "$n"
    printf '%s\n' "$hits2"
    violations=$((violations + n))
  fi

  # ---------------------------------------------------------------------
  # Rule 3: no-hex-in-jsx-style
  # Match: a hex literal or rgb()/rgba()/hsl()/hsla() inside a `style={...}`
  # prop on the SAME line. Multi-line style objects can slip past — the
  # plugin path is the long-term fix.
  # ---------------------------------------------------------------------
  pat3='style=\{[^}]*(#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\()'
  hits3=$(grep -E -r -n "${EXCLUDES[@]}" "${INCLUDES[@]}" "$pat3" "$src" 2>/dev/null || true)
  if [ -n "$hits3" ]; then
    n=$(printf '%s\n' "$hits3" | wc -l | tr -d ' ')
    emit_section "kiho/no-hex-in-jsx-style" "$n"
    printf '%s\n' "$hits3"
    violations=$((violations + n))
  fi
done

echo
if [ "$violations" -gt 0 ]; then
  echo "[kiho-fallback] FAIL — $violations violation(s) across the three rules."
  echo "[kiho-fallback] This is a stop-gap. Once eslint-plugin-kiho is published,"
  echo "[kiho-fallback] swap to the full ESLint / Biome / Oxlint sidecar template."
  exit 1
fi

echo "[kiho-fallback] OK — no violations."
exit 0
