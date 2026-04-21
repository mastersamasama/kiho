# Karpathy autoresearch loop — offline reference

Offline excerpt of Andrej Karpathy's autoresearch pattern, adapted for kiho's skill evolution context. The loop is the philosophical foundation for `skills/evolution-scan/`.

## Contents
- [Core philosophy](#core-philosophy)
- [Loop structure](#loop-structure)
- [Design principles](#design-principles)
- [Adaptation for kiho](#adaptation-for-kiho)

## Core philosophy

The autoresearch loop is an autonomous improvement cycle designed for simplicity and reliability. It avoids the pitfalls of complex planning systems by constraining each iteration to:
- One change at a time
- Binary decisions (keep or discard)
- Concrete validation (run the test, check the result)
- Fixed budget (never spiral)

The loop is deliberately boring. It does not try to be clever. It does not batch optimizations. It does not plan ahead. Each iteration is independent: examine, change, test, decide. The accumulated effect of many small, validated changes is more reliable than one large, ambitious rewrite.

## Loop structure

```
EXAMINE state
  → Read the current artifact and its history
  → Read any execution evidence (logs, test results, user feedback)
  → Identify ONE specific opportunity for improvement

PICK one change
  → The change must be concrete and small
  → It must address exactly one identified issue
  → It must be expressible as a diff or a new file

COMMIT the change
  → Apply the diff or write the new file
  → Preserve the prior version (rollback safety)

RUN validation
  → Execute the test case
  → Compare actual output to expected output
  → Binary result: pass or fail

READ results
  → If pass: the change stays
  → If fail: revert the change

KEEP or DISCARD
  → No "maybe." No "try again with modifications."
  → Keep: log the success and move on
  → Discard: log the failure and move on

LOG
  → Record what was tried, why, and the outcome
  → This log feeds future EXAMINE phases

REPEAT
  → Next iteration starts fresh from EXAMINE
  → No carry-over of partial plans
  → Stop when budget is exhausted or no opportunities remain
```

## Design principles

### One-file discipline

Each iteration touches one file. If a change requires modifying multiple files, it is too large. Break it down. The one-file constraint prevents cascade failures where a bad change in file A requires compensating changes in B, C, and D.

Exception: version archival (copying the old version to `versions/`) is a mechanical operation that always accompanies the change to the main file.

### Binary decisions

Every decision point in the loop has exactly two outcomes. There is no "partially apply" or "apply with modifications." If the validation fails, the change is discarded entirely. This prevents the accumulation of untested partial improvements.

### Simplicity criterion

When choosing between two valid approaches to a change, prefer the simpler one. "Simpler" means fewer lines changed, fewer concepts introduced, and less coupling with other components. The goal is reliability, not elegance.

### Fixed budget

The loop runs for a predetermined number of iterations or tool calls. It does not self-extend. If the budget runs out mid-iteration, the current change is discarded (fail-safe). Budget prevents the loop from spiraling on a difficult problem.

### Evidence-based examination

The EXAMINE phase only identifies opportunities backed by concrete evidence:
- A test case that failed
- A session log showing the skill was triggered but produced wrong output
- A user complaint about a specific behavior
- A metric that declined

"I think this could be better" without evidence is not an opportunity. Improvements without evidence are gold-plating.

## Adaptation for kiho

kiho uses the autoresearch loop for skill evolution (`skills/evolution-scan/`). The mapping:

| Karpathy concept | kiho implementation |
|---|---|
| Artifact | SKILL.md file |
| Execution evidence | Session context + test case results + changelog |
| One change | FIX (patch), DERIVED (new variant), or CAPTURED (new skill) |
| Validation | Test case replay |
| Keep/discard | Apply diff or delete draft |
| Log | changelog.md append + ceo-ledger entry |
| Budget | max_iterations + max_tool_calls |

### What the loop does NOT do in kiho

- **Does not auto-run.** The CEO or user must explicitly invoke `/kiho evolve`.
- **Does not modify agent files.** Agent evolution is an HR function, not a loop function.
- **Does not touch the KB.** KB changes go through kb-manager. The loop only modifies skill files.
- **Does not chain iterations.** Each iteration is independent. The loop does not "build on" a prior iteration's change.
- **Does not exceed depth cap.** The evolution-scan skill runs at depth 1 (under CEO). It may call skill-improve/derive/capture at depth 2, but never deeper.
