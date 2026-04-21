---
name: engineering-kiro
description: Use this skill when the kiho CEO delegates spec-driven engineering work to the Engineering department. This is a thin wrapper around the upstream /kiro skill that preserves all kiro modes (feature, bugfix, refactor, vibe, debate, resume) and all three user-approval gates (requirements, design, tasks) but redirects spec output to .kiho/specs/ instead of .kiro/specs/ so kiho's state stays in one place. Also use when an engineering lead needs the kiro four-mode routing matrix, the EARS-format requirements template, or the task-as-documentation pattern.
argument-hint: "<mode> <description>"
metadata:
  trust-tier: T2
  kiho:
    capability: orchestrate
    topic_tags: [engineering, orchestration]
    data_classes: []
---
# engineering-kiro

Thin wrapper around the kiro spec-driven development skill. Preserves kiro's routing, gates, and templates; redirects state to `.kiho/specs/` for unified kiho bookkeeping.

## What this skill is

A verbatim copy of the `/kiro` skill body lives at `${CLAUDE_PLUGIN_ROOT}/skills/engineering-kiro/kiro/`. This wrapper's only job is to set a path variable and then defer to that body.

## Usage

**Path override:** before running the inner kiro flow, set:
```
SPECS_ROOT = <project>/.kiho/specs/
```

When kiro's body says to write to `.kiro/specs/<feature>/requirements.md`, translate the path to `${SPECS_ROOT}/<feature>/requirements.md` (i.e., `.kiho/specs/<feature>/requirements.md`). Apply this rewrite to every path kiro's body writes to.

**Steering location:** kiro looks for steering in `.kiro/steering/`. This wrapper also honors `.kiho/steering/` as a first-preference location. If the project has both, `.kiho/steering/` wins.

## Procedure

1. Load the full kiro body from `${CLAUDE_PLUGIN_ROOT}/skills/engineering-kiro/kiro/SKILL.md`.
2. Set `SPECS_ROOT` = `<project>/.kiho/specs/` and `STEERING_ROOT` = `<project>/.kiho/steering/` (fallback: `.kiro/steering/`).
3. Run the kiro body exactly as instructed, but apply the path rewrites above to every file operation.
4. On completion, the spec folder is at `.kiho/specs/<feature>/` with `requirements.md`, `design.md`, `tasks.md` (or `bugfix.md` for bugfix mode).
5. Return a structured output to the caller (CEO or dept leader):
   ```
   status: ok | blocked | escalate_to_user
   spec_path: .kiho/specs/<feature>/
   stages_completed: [requirements, design, tasks]
   user_gates_passed: 3
   summary: <1-paragraph>
   ```

## kb integration

At each stage completion (requirements done, design done, tasks done), call `kiho-kb-manager` op=`add` with `page_type: decision` and the stage summary. This persists each gate's outcome as a KB fact so subsequent Ralph iterations can see the decision without re-deriving it.

## Committee enhancement (kiho-specific)

Kiro's built-in review protocol is replaced by kiho's committee protocol at each stage:

- **Requirements stage**: convene a PM + Research committee to review the draft requirements before presenting to user.
- **Design stage**: convene a PM + Eng + Research committee.
- **Tasks stage**: convene an Eng + QA (HR-recruited if none exists) committee.

Committee results inform the spec draft; the user still approves each stage via the kiro user gate.

## Invariants

- Never bypass kiro's three user-approval gates. Committee enrichment happens before presenting to user, not instead of presenting.
- Never write to `.kiro/specs/` — always `.kiho/specs/`. Users with existing `.kiro/specs/` are expected to opt in via a symlink if they want to merge.
- Never re-implement kiro logic inline; always defer to the bundled verbatim copy.

## Upstream sync

The `kiro/` subfolder is a verbatim copy of `~/.claude/skills/kiro/` taken at plugin build time. To refresh: `cp -r ~/.claude/skills/kiro/* skills/engineering-kiro/kiro/`. After refresh, run the kiho smoke test to verify no behavior regression.
