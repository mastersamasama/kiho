---
name: decision-audit
description: Use this skill quarterly (or on-demand after a notable failure) to re-evaluate whether past high-confidence decisions still hold. Reads decision.md files from the last 30+ days where confidence >= 0.90, picks N decisions per the audit lens (random, recent-failure-adjacent, or domain-targeted), and asks the original committee plus a neutral reviewer "does this decision still hold given current evidence?". If a decision no longer holds, opens a reversal committee. Triggers on "decision audit", "review past decisions", "are our calls still right", or after a sev1 incident touches a domain with prior decisions in scope. Closes the gap where high-confidence decisions calcify and never get re-examined.
metadata:
  trust-tier: T2
  kiho:
    capability: evaluate
    topic_tags: [reflection, lifecycle]
    data_classes: [committee-records-jsonl]
---
# decision-audit

The "are we still right?" ceremony. Without it, high-confidence decisions become unchallenged dogma. With it, the organization periodically asks "given what we now know, would we make the same call?".

> **v5.21 cycle-aware.** Reachable as a future `audit` phase in `references/cycle-templates/decision-cycle.toml` (90-day post-close re-eval). The current decision-cycle template stops at `register`; the `audit` phase is added in a v5.22 template version. Atomic invocation for ad-hoc audits is the recommended path until then.

## When to use

- Quarterly cadence (CEO INITIALIZE auto-trigger every Nth turn, default = 90 days since last audit)
- After a sev1 incident closed where the postmortem hints at a stale decision
- Pre-strategic-pivot: before a major scope change, audit the decisions that brought us here

Do **NOT** invoke when:

- A specific decision is suspect — open a reversal committee directly via `committee` skill
- The audit window has < 5 high-confidence decisions — no statistical body, just review them inline
- A user is mid-flight on a feature — audit is reflection, not in-band work

## Inputs

```
window_days: <int>                # default 90
lens: random | recent-failure-adjacent | domain-targeted   # default random
sample_size: <int>                # default 5
domain: <topic-tag>               # required when lens=domain-targeted
neutral_reviewer: <agent-id>      # optional; defaults to kiho-judge
```

## Procedure

1. **Enumerate eligible decisions.** Walk `<project>/.kiho/committees/*/decision.md` files from the last `window_days`. Filter to those with `confidence >= 0.90`. If `lens=domain-targeted`, further filter to decisions whose `topic_tags` includes `domain`. If `lens=recent-failure-adjacent`, filter to decisions whose topic touches an incident closed in the last 30 days (correlate via tag intersection).

2. **Sample.** Pick `sample_size` decisions per the lens. If pool < sample_size, audit the entire pool.

3. **For each sampled decision, run a one-round re-eval committee.** Participants: original committee members (those still active) + neutral reviewer. Single round only — this is "still hold?", not full re-deliberation.

   Each participant returns one of:
   - `still-holds` — evidence unchanged or strengthened; decision stands
   - `partial-revisit` — some assumptions are stale; decision stands but with documented caveats
   - `should-reverse` — load-bearing assumption is wrong; open a reversal committee

4. **Aggregate.** A decision is `confirmed` if all participants return `still-holds`. `caveat-added` if all return `still-holds | partial-revisit` and at least one is partial. `flagged-for-reversal` if any returns `should-reverse`.

5. **Write the audit summary.** Call `storage-broker` op=`put`:
   ```
   namespace: state/decision-audits/<audit_id>
   kind: decision-audit
   access_pattern: read-mostly
   durability: project
   human_legible: true
   body: { audit_id, ts, window, lens, sample_size, results: [{decision_ref, status, dissenters, caveats}],
           reversals_opened: [<committee_id>, ...] }
   ```

6. **For each `flagged-for-reversal`, open a reversal committee.** Call `committee` skill with charter `"Reversal review: <original decision title>"` and pre-load the decision-audit summary into the committee's first-round briefing. Reversal committees follow the standard committee rules (3 rounds, unanimous close).

7. **For each `caveat-added`, append the caveat** to the original decision.md without rewriting it. The caveat is a new section: `## Caveats added by decision-audit <audit_id> on <ts>`.

8. **Memory observations** to original committee members and neutral reviewer (type=reflection, importance=6).

9. **CEO notification** via single `memo-send severity=fyi` with the audit summary; reversal committees notify CEO independently per their own protocol.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: decision-audit
STATUS: ok | error
AUDIT_ID: <id>
WINDOW_DAYS: <int>
LENS: <lens>
SAMPLED: <count>
CONFIRMED: <count>
CAVEAT_ADDED: <count>
FLAGGED_FOR_REVERSAL: <count>
REVERSAL_COMMITTEES: [<committee_id>, ...]
AUDIT_REF: md://state/decision-audits/<id>.md
```

## Invariants

- **Re-eval is one round, not three.** Decision-audit is "still hold?", not "let's re-litigate the whole thing". If full re-deliberation is needed, that's a reversal committee.
- **Original committee gets first ask.** Bringing in fresh perspective is the neutral reviewer's job; the original deciders own the still-holds judgment.
- **Caveats accumulate, never overwrite.** Each audit adds a new caveat section dated to the audit; the decision body itself is immutable until reversed.
- **Reversal committees use full committee rules.** No shortcuts on unanimous close; reversing a high-confidence decision needs the same rigor that made it.

## Non-Goals

- Not a witch-hunt. We're auditing decisions, not deciders.
- Not a substitute for postmortem. If a decision broke production, the postmortem owns root cause; decision-audit just notices the pattern.
- Not for low-confidence decisions. Sub-0.90 decisions were already provisional; if they're wrong, fix them via normal evolve flow.
- Not a roadmap re-plan. Strategy changes are CEO + user, not a committee re-eval.

## Anti-patterns

- Never sample > 10 decisions per audit. Re-eval has cost; bigger samples dilute attention.
- Never skip the neutral reviewer. Same-room dynamics make "still holds" the path of least resistance.
- Never auto-open reversal without committee. Even on "should-reverse" votes, reversal is a committee, not a unilateral CEO action.
- Never close an audit without writing memory observations. The participants must carry the outcome forward.

## Grounding

- `references/committee-rules.md` — the rules reversal committees follow.
- `skills/core/planning/committee/SKILL.md` — the committee skill invoked for reversals.
- `references/data-storage-matrix.md` row `committee-records-jsonl` — the source of truth for past decisions.
- `skills/core/ops/postmortem/SKILL.md` — the failure-adjacent lens often pairs with recent postmortems.
