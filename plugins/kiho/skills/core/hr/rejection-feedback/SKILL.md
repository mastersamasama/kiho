---
name: rejection-feedback
description: Use this skill at the end of every recruit cycle to write structured rejection memos for losing candidates. Without it, candidates not chosen evaporate — losing the signal "this persona scored 4.2 on accuracy but 3.1 on persona fit; recommend re-interview after 3 months of pairing on <topic>". Triggers on "send rejection feedback", "close out recruit", or auto-fires from recruit's `op=close-cycle` once the winning candidate is hired. For each non-winning candidate, writes a rejection-feedback memory entry into the candidate template library so the next recruit cycle can re-evaluate with prior context.
metadata:
  trust-tier: T2
  kiho:
    capability: communicate
    topic_tags: [coordination, lifecycle]
    data_classes: [recruit-role-specs]
---
# rejection-feedback

The "everyone gets feedback" practice. recruit ships a winner; this skill closes out the losers professionally so the org learns from the candidate pool, not just the hire.

> **v5.21 cycle-aware.** Auto-fired by recruit's existing close-out path AND also reachable as a hook in `talent-acquisition.toml`'s `on_close_success` if the cycle bypassed atomic recruit. Atomic invocation remains supported for retroactive close-outs of cycles that skipped the step.

## When to use

- Auto-fires from `recruit op=close-cycle` for every candidate where `outcome != hired`
- Manually: `/kiho rejection-feedback <recruit-cycle-id>` to retroactively close out a cycle that skipped the step

Do **NOT** invoke when:

- The recruit cycle was a `quick-hire` with only one candidate (no losers to feedback)
- The losing candidate was rejected for a hard disqualification (e.g., persona-conflict-with-charter); use `recruit op=disqualify` log instead

## Inputs

```
cycle_id: <recruit-cycle-id>            # required
candidates: [<candidate-id>, ...]       # optional; defaults to all non-winners in cycle
include_axis_breakdown: <bool>          # default true
include_re_interview_window: <int days> # default 90
```

## Procedure

1. **Resolve the cycle.** Read `state/recruit/<cycle_id>/role-spec.{toml,md}` and `state/recruit/<cycle_id>/results.{toml,md}`. Extract the per-candidate axis scores from `interview-simulate` transcripts.

2. **For each non-winning candidate, draft a structured rejection memo.** The memo MUST include:
   - **Headline rating per axis.** E.g., "Accuracy: 4.2 / 5; Persona fit: 3.1 / 5; Tool use: 3.8 / 5; Safety: 4.5 / 5."
   - **The decisive axis.** The single axis that most lowered the candidate's overall vs the winner.
   - **One concrete development suggestion.** E.g., "Recommend shadowing on async coordination patterns — the persona-fit gap concentrated on round 5 (multi-agent async work)."
   - **Re-interview window.** "Eligible to re-interview from <date + N days> if a similar role opens."

3. **Write a rejection-feedback memory entry to the candidate template's memory.** Call `memory-write`:
   ```
   agent_id: <candidate-template-id>   # not the runtime instance
   memory_type: rejection-feedback
   confidence: 0.85
   tags: [recruit, <cycle-tag>]
   source: "rejection-feedback@<cycle_id>"
   content: |
     Cycle: <cycle_id>
     Outcome: not selected (winner: <winner_id>)
     Axis breakdown: <as above>
     Decisive axis: <axis_name> (delta from winner: <float>)
     Development suggestion: <one-line>
     Re-interview eligible from: <iso-date + N days>
   ```

4. **Log the close-out.** Append a row to `state/recruit/<cycle_id>/close-out.jsonl`:
   ```
   { "ts": "<iso>", "candidate": "<id>", "outcome": "rejected_with_feedback",
     "memory_ref": "<mem://...>", "re_interview_window_days": <N> }
   ```

5. **Notify HR-lead.** Single `memo-send to=hr-lead severity=fyi` with the close-out summary (counts, not per-candidate detail). The HR lead uses this to update the recruit cycle KPI dashboard.

6. **Return refs.** Response shape below.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: rejection-feedback
STATUS: ok | error
CYCLE_ID: <id>
CANDIDATES_PROCESSED: <count>
MEMORY_REFS:
  - candidate: <id>
    ref: mem://<candidate>/rejection-feedback#L<n>
    decisive_axis: <axis>
    re_interview_eligible_from: <date>
HR_LEAD_NOTIFIED: <bool>
```

## Invariants

- **Feedback is per-candidate, not per-cycle.** A single bulk "everyone failed" memo is not feedback; it's noise. Each candidate gets a memo with their specific axis breakdown.
- **No blame, only signal.** Rejection memos describe what didn't fit the role, never what's "wrong with the candidate". The persona is fine; the role didn't match.
- **Re-interview window is real.** Future recruit cycles MUST query rejection-feedback for the candidate template before re-evaluating; double-rejection within the window without new evidence is a process bug.
- **Never write to the candidate's runtime instance memory.** Candidates are personas in templates; runtime instances die at hire-decision. The memory lands in the template library.

## Non-Goals

- Not a coaching session. The decisive axis + dev suggestion is the entire surface; we don't pair-program with rejected candidates.
- Not a re-evaluation. If the cycle conclusion was wrong, re-open the cycle, don't backfill with rejection feedback.
- Not auto-applied to disqualified candidates. Hard disqualifications (charter conflict, safety failure) have their own log; this skill is for the "close call" losers.

## Anti-patterns

- Never skip rejection-feedback for the runner-up. They were the closest miss — their feedback has the highest information value.
- Never include the winner's name in the rejection memo. "Decisive axis delta from winner" is enough; the winner's identity is recruit-cycle metadata, not feedback.
- Never set re-interview window to 0. Even a high-fit-for-different-role candidate needs a 30+ day cooling period.

## Grounding

- `skills/core/hr/recruit/SKILL.md` — the upstream cycle that produces candidates and chooses a winner.
- `skills/core/planning/interview-simulate/SKILL.md` — the per-candidate axis scoring whose transcripts this skill reads.
- `references/data-storage-matrix.md` row `recruit-role-specs` (MIGRATING) — where the cycle records live.
- `references/memory-pruning-policy.md` — rejection-feedback retention is 365 days.
