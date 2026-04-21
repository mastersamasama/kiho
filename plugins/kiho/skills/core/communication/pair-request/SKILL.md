---
name: pair-request
description: Use this skill when two agents need to collaborate on the same brief across multiple iterations with shared scratchpad state. Heavier than help-wanted (which is one-iteration peer assist); lighter than committee (which is multi-round formal deliberation). Opens a Tier-3 sqlite scratchpad scoped to the current turn so both agents read+write the same working state without polluting their individual memory streams. Triggers on "pair with <agent>", "let's work on this together", "co-implement", or when help-wanted's claimer requests scope extension. Auto-evicts the scratchpad at CEO DONE per Tier-3 invariants.
metadata:
  trust-tier: T2
  kiho:
    capability: orchestrate
    topic_tags: [coordination, ingestion]
    data_classes: [scratch-per-script]
---
# pair-request

Two-agent collaboration with shared working state. Designed for the cases where neither help-wanted (one-shot) nor a committee (formal vote) fits — typically a refactor that needs a coder + a reviewer, or a research dive that needs a domain expert + a kb-aware writer.

## When to use

- Two agents will iterate on the same artifact within this turn (≥ 2 iterations)
- Help-wanted resolved with a claim AND the claimer says "this is bigger than 1 iteration"
- Cross-dept collab where the seam itself is the work (eg PM + Eng on a spec)

Do **NOT** invoke when:

- One-iteration assist suffices — use `help-wanted`
- Three or more agents need to weigh in — that's a committee
- The work needs to outlive the current turn — pair-request is turn-scoped; persist conclusions via `kb-add` or `memory-write` before DONE

## Inputs

```
brief_path: <path to the shared brief>            # required
participants: [<agent_id>, <agent_id>]            # required; exactly 2
roles: { driver: <agent_id>, navigator: <agent_id> }  # optional; defaults to participants[0]/[1]
expected_iterations: <int>                          # default 3, max 5
```

## Procedure

1. **Open a Tier-3 scratchpad.** Call `storage-broker` op=`put`:
   ```
   namespace: scratch/pair/<turn_id>/<pair_id>
   kind: scratch
   access_pattern: read-write
   durability: session                # T3 invariant — evicted at DONE
   format: sqlite                     # broker chooses sqlite for shared multi-reader/writer access
   eviction: session-scope
   body: { participants, brief_path, opened_at }
   ```
   The broker creates `<project>/.kiho/state/tier3/pair-<pair_id>.sqlite` with two tables: `scratch_messages` (id, ts, author, body) and `scratch_artifacts` (id, ts, author, kind, body). Both agents append; nobody updates or deletes.

2. **Notify both participants** with a single `memo-send severity=action` to each, body:
   ```
   subject: "Pair request: <brief_path>"
   body: |
     Driver: <driver_id>
     Navigator: <navigator_id>
     Brief: <brief_path>
     Scratchpad: scratch/pair/<turn_id>/<pair_id>
     Expected iterations: <N>
     Roles can swap mid-pair via scratch_messages with role=swap.
   ```

3. **Each iteration during the pair.** The driver:
   - Reads the brief + the scratchpad's recent messages
   - Performs one tool call (Read / Edit / Bash / etc) to advance the work
   - Appends to `scratch_messages` with their reasoning
   - Appends any new artifact (diff, plan, draft) to `scratch_artifacts`

   The navigator:
   - Reviews the driver's tool call result
   - Appends a critique or approval to `scratch_messages`
   - May propose a counter-direction with `kind=counter` in scratch_artifacts (driver decides whether to adopt)

4. **Role swap (optional).** Either participant can write a `scratch_message` with `role: swap`. The role assignment flips on the next iteration. Free-form pair work; no committee-style voting.

5. **Convergence or escalation.** After `expected_iterations` (or earlier on agreement):
   - If converged, both agents call `memory-write type=reflection` to their own memories citing the scratchpad ID; the driver also writes the final artifact to wherever the brief targets (KB, code, design doc) via the appropriate skill
   - If diverged, escalate to a 3-person committee with both pair members + a neutral arbiter from `kiho-judge` or dept-lead

6. **Close the cycle.** Append a final `scratch_messages` with `kind: close` and outcome (`converged | diverged | timed_out`). The scratchpad sqlite stays on disk for the rest of this turn (other agents MAY read for context); CEO DONE step 8 evicts it.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: pair-request
STATUS: ok | error
PAIR_ID: pair-<id>
PARTICIPANTS: [<driver>, <navigator>]
SCRATCHPAD_REF: sqlite://scratch/pair/<turn_id>/<pair_id>
EXPECTED_ITERATIONS: <N>
NEXT_ACTION: "Both participants read the brief and scratchpad; driver leads iteration 1"
```

## Invariants

- **Exactly two participants.** Three is a committee; one is solo work. Pair = 2.
- **Scratchpad is session-scope.** No agent may rely on it surviving past CEO DONE. If something matters beyond this turn, persist it through the right canonical channel (KB / memory / code).
- **Driver/navigator is fluid.** The roles guide attention but are not enforced by the skill — agents can swap freely as long as it's logged.
- **No cross-pair scratchpad reads.** Pair A cannot read Pair B's scratchpad; if cross-pair coordination is needed, use memo-send between drivers.

## Non-Goals

- Not a code editor. Pair-request coordinates the work; tool calls (Edit/Bash/Read) still happen through normal Claude Code surfaces.
- Not a permanent archive. Use `kb-add` or `memory-write` for permanence.
- Not a 1:1. The 1-on-1 ceremony is lead↔IC coaching; pair-request is peer↔peer execution.
- Not a chat. Brevity in scratch_messages — one paragraph or less per append.

## Anti-patterns

- Never spawn a pair from inside a committee deliberation. Committees have their own structured rounds; pair-request would shadow-resolve dissent.
- Never extend `expected_iterations` mid-pair. If you need more, close this pair and open a new one (or escalate to committee).
- Never use scratch_messages for blame. Pairs work through disagreement on the artifact, not on each other.
- Never let the scratchpad outlive the turn. The skill enforces this by writing eviction metadata at open; honor it.

## Grounding

- `references/storage-architecture.md` — Tier-3 invariants enforced for the scratchpad.
- `skills/core/storage/storage-broker/SKILL.md` — the put op called in step 1.
- `references/react-storage-doctrine.md` — why pair scratchpad is sqlite (multi-reader+writer, structured) not markdown.
- `skills/core/communication/help-wanted/SKILL.md` — sibling skill for one-iteration assist.
- `skills/core/planning/committee/SKILL.md` — escalation target when a pair diverges.
