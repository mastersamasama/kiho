#requires -Version 5.1
<#
.SYNOPSIS
  kiho theme-contrast-guard - Layer 2 lint fallback (Windows PowerShell)

.DESCRIPTION
  Stop-gap until the chosen toolchain has a working kiho plugin:
    - ESLint:  needs eslint-plugin-kiho published (kiho roadmap)
    - Biome:   today, prefer biome-kiho.template.json + .grit files
    - Oxlint:  alpha plugin API, also waits on eslint-plugin-kiho

  Three regex patterns mirror the three SKILL.md rules:
    1. no-literal-theme-import   -> import { palette | macaron | acColors }
    2. no-color-scheme-in-app    -> useColorScheme from 'react-native'
    3. no-hex-in-jsx-style       -> #xxx / rgb / rgba inside style={...}

.PARAMETER Sources
  One or more source directories to scan.

.EXAMPLE
  pwsh -File lint-fallback-grep.ps1 apps\mobile\src
  pwsh -File lint-fallback-grep.ps1 apps\mobile\src apps\web\src

.NOTES
  Exit codes:
    0 - clean
    1 - at least one violation
    2 - bad invocation

  Excluded path segments (hardcoded - edit if your tree differs):
    \theme\, \charts\, \__tests__\, \node_modules\, \dist\, \build\, \.git\
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true, Position=0, ValueFromRemainingArguments=$true)]
  [string[]] $Sources
)

$ErrorActionPreference = 'Stop'

if (-not $Sources -or $Sources.Count -lt 1) {
  Write-Error "usage: lint-fallback-grep.ps1 <src-dir> [<src-dir2> ...]"
  exit 2
}

$excludeSegments = @('\theme\', '\charts\', '\__tests__\', '\node_modules\', '\dist\', '\build\', '\.git\')
$includeExt = @('.ts', '.tsx', '.js', '.jsx')

$rules = @(
  @{
    Name    = 'kiho/no-literal-theme-import'
    Pattern = '^\s*import\s.*\b(palette|macaron|acColors)\b.*from'
  },
  @{
    Name    = 'kiho/no-color-scheme-in-app'
    # Either order: useColorScheme + 'react-native' OR react-native + useColorScheme on same line
    Pattern = "useColorScheme.*from.*['""]react-native['""]|from\s*['""]react-native['""].*useColorScheme"
  },
  @{
    Name    = 'kiho/no-hex-in-jsx-style'
    Pattern = 'style=\{[^}]*(#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\()'
  }
)

$totalViolations = 0

foreach ($src in $Sources) {
  if (-not (Test-Path -LiteralPath $src -PathType Container)) {
    Write-Warning "'$src' is not a directory - skipping"
    continue
  }

  $files = Get-ChildItem -LiteralPath $src -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
      # Extension allowlist
      if ($includeExt -notcontains $_.Extension) { return $false }
      # Exclude path-segment denylist (avoid $_ scope clash by capturing FullName upfront)
      $path = $_.FullName
      foreach ($seg in $excludeSegments) {
        if ($path -like "*$seg*") { return $false }
      }
      return $true
    }

  foreach ($rule in $rules) {
    $hits = $files | Select-String -Pattern $rule.Pattern -AllMatches -ErrorAction SilentlyContinue
    if ($hits) {
      $count = ($hits | Measure-Object).Count
      Write-Host ""
      Write-Host "[kiho-fallback] rule: $($rule.Name) - $count hit(s)"
      foreach ($h in $hits) {
        Write-Host ("{0}:{1}:{2}" -f $h.Path, $h.LineNumber, $h.Line.Trim())
      }
      $totalViolations += $count
    }
  }
}

Write-Host ""
if ($totalViolations -gt 0) {
  Write-Host "[kiho-fallback] FAIL - $totalViolations violation(s) across the three rules."
  Write-Host "[kiho-fallback] This is a stop-gap. Once eslint-plugin-kiho is published,"
  Write-Host "[kiho-fallback] swap to the full ESLint / Biome / Oxlint sidecar template."
  exit 1
}

Write-Host "[kiho-fallback] OK - no violations."
exit 0
