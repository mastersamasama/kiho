# Worked examples — `/kiho` dispatch

Read this when you want to see how a particular invocation shape is classified into (mode, payload) before the CEO's Ralph loop takes over. Each example shows the literal invocation and the internal routing envelope the CEO produces.

## 1 — implicit feature mode from a plain description

Invocation:

```
/kiho build a dark-mode toggle for the settings page
```

Expected routing (CEO's internal classification):

```json
{
  "mode": "feature",
  "payload": "build a dark-mode toggle for the settings page",
  "next_action": "load CEO persona, create spec, delegate to Engineering"
}
```

The mode-parsing table has no literal rule for this input — it falls through to `unclassified`. The CEO then reads `.kiho/state/plan.md` + the last 10 session-context entries and upgrades `unclassified` to `feature` because the payload has no mode flag, no matching file path, and describes a user-visible capability rather than a bugfix or refactor.

## 2 — PRD file path

Invocation:

```
/kiho C:/projects/acme/PRDs/onboarding-v2.md
```

Expected routing:

```json
{
  "mode": "feature-from-prd",
  "payload": "C:/projects/acme/PRDs/onboarding-v2.md",
  "next_action": "read PRD, classify subsystems, spawn PM then Engineering cascade"
}
```

Detection rule: the argument resolves to an existing file path. The CEO ingests the PRD, decomposes it into subsystems, and runs the full feature cascade.

## 3 — vibe mode skips spec creation

Invocation:

```
/kiho --vibe fix typo in README
```

Expected routing:

```json
{
  "mode": "vibe",
  "payload": "fix typo in README",
  "next_action": "skip spec, delegate directly to an IC"
}
```

Vibe is the explicit opt-out from spec ceremony. It still routes through the CEO — the CEO just skips `kiho-spec` and picks a single IC from the capability matrix. Reserve vibe for single-file edits under an hour.

## 4 — resume a paused spec

Invocation:

```
/kiho --resume dark-mode-toggle
```

Expected routing:

```json
{
  "mode": "resume",
  "payload": "dark-mode-toggle",
  "next_action": "read .kiho/state/dark-mode-toggle/partial.md, rehydrate Ralph loop state, continue from last checkpoint"
}
```

The prior turn must have written `partial.md` (Route D of the failure playbook). If that file is absent, the CEO routes to Route C and asks the user which spec they meant.
