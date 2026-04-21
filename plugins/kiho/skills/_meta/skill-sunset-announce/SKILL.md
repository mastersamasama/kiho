---
name: skill-sunset-announce
description: Use this skill immediately after skill-deprecate marks a skill for retirement. Produces a Tier-1 markdown announcement with migration steps, replacement skill reference, sunset iteration, and list of affected consumers. Fan-outs severity=action memos to every consumer agent's inbox so they know to migrate. Registers a migration action in the actions JSONL with per-consumer ownership and due iteration. Updates the capability matrix to reflect the deprecation. Does not itself retire the skill — skill-deprecate owns that — but ensures the retirement is visible and actionable rather than silent.
argument-hint: "deprecated_skill=<id> replacement_skill=<id>"
metadata:
  trust-tier: T3
  kiho:
    capability: communicate
    topic_tags: [lifecycle]
    data_classes: ["skill-definitions", "changelog", "capability-matrix"]
---
# skill-sunset-announce

Pairs with `skill-deprecate` (sk-032). Deprecation without announcement strands every agent that still calls the retired skill — they discover the retirement by failing, not by migrating. This skill is the announcement half: it writes a Tier-1 markdown announcement, fan-outs action-severity memos to every affected consumer, and registers migration actions so the CEO digest keeps asking "is consumer X migrated yet?" until they are.

## Why a separate skill

`skill-deprecate` owns the decision: should this skill retire, and if so when. `skill-sunset-announce` owns the propagation: does every consumer know, and is the replacement documented well enough that they can migrate without asking. Conflating the two meant that deprecations either happened silently (no propagation) or blocked on propagation (couldn't deprecate until every consumer migrated, which creates deadlocks when a retired skill is only used occasionally). Splitting them lets deprecation be a policy decision and sunset-announce be an operational rollout.

## Inputs

```
PAYLOAD:
  deprecated_skill: <skill_id>        # required — e.g., "sk-017"
  replacement_skill: <skill_id>       # required — what consumers should migrate to
  sunset_iteration: <id>              # required — ralph iteration after which deprecated_skill will be removed
  migration_steps_md: <markdown>      # required — 3-8 numbered steps, runnable verbatim
  affected_consumers: [<agent_id>]    # optional — if missing, skill runs kiho_rdeps to discover
  incompatibility_notes: <markdown>   # optional — semantics that change between old and new
  ceo_decision_ref: <ref>             # required — the skill-deprecate committee ruling that authorized this
```

## Procedure

1. **Resolve consumers.** If `affected_consumers` is non-empty, use it verbatim. Otherwise call `kiho_rdeps` (reverse-dependency query) on `deprecated_skill` to discover every agent whose soul `skills:` frontmatter lists the deprecated skill OR whose recent `skill-invocations.jsonl` rows show an invocation within the last 90 days. Dedupe the union.

2. **Draft the announcement.** Build a Tier-1 markdown page:
   ```markdown
   # Sunset: <deprecated_skill> → <replacement_skill>

   **Status:** scheduled for removal at iteration <sunset_iteration>
   **Authorized by:** <ceo_decision_ref>
   **Affected consumers:** <count> (list below)

   ## Why
   <one paragraph — cite the deprecation rationale from ceo_decision_ref>

   ## Migration steps
   <migration_steps_md verbatim>

   ## Incompatibility notes
   <incompatibility_notes, or "None — drop-in replacement.">

   ## Affected consumers
   - <agent_id_1>
   - <agent_id_2>
   - ...

   ## Timeline
   - Announced: <iso-today>
   - Migration window opens: immediately
   - Sunset iteration: <sunset_iteration>
   - Removal: <sunset_iteration + 1>
   ```

3. **Write the announcement.** Call `storage-broker` op=`put`:
   ```
   namespace: state/announcements
   kind: announcement
   access_pattern: snapshot
   durability: project
   human_legible: true
   body: <announcement markdown above>
   metadata:
     deprecated_skill: <id>
     replacement_skill: <id>
     sunset_iteration: <id>
   ```
   Broker resolves this to a Tier-1 md file because `human_legible: true` and `access_pattern: snapshot` together force md selection per the storage-tech-stack matrix. The returned ref is `md://state/announcements/<slug>.md`.

4. **Fan-out memos.** For each consumer in step 1's resolved list, call `memo-send`:
   ```
   to: <consumer>
   severity: action
   subject: "Migrate <deprecated_skill> → <replacement_skill> by <sunset_iteration>"
   body: |
     The skill you rely on is being retired. See the full announcement:
     <announcement_ref>

     Key points:
     - Replacement: <replacement_skill>
     - Sunset iteration: <sunset_iteration>
     - Migration steps: <first line of migration_steps_md>

     Your migration action is tracked at <action_ref>.
   ```
   Severity `action` (not `fyi`) because consumers will literally break at sunset if they ignore it. The memo links both the announcement and the per-consumer action row from step 5.

5. **Register migration actions.** For each consumer, call `storage-broker` op=`put` to `state/actions`:
   ```
   namespace: state/actions
   kind: action
   body:
     action_id: <uuid>
     owner: <consumer>
     source: skill-sunset-announce
     deprecated_skill: <id>
     replacement_skill: <id>
     due_iteration: <sunset_iteration>
     status: open
     verification: "invocation of <replacement_skill> from <consumer> OR explicit waiver from ceo-01"
     announcement_ref: <ref>
   ```
   The CEO digest pulls open actions each turn, so this keeps the pressure on without any polling by this skill. Auto-closes when either verification condition is met (detected by a nightly ralph pass, not by this skill).

6. **Refresh capability matrix.** Trigger `org-sync` to regenerate `.kiho/state/capability-matrix.md`. The deprecated skill's column gets a `deprecated_at: <sunset_iteration>` marker so routing decisions that would otherwise select it can prefer the replacement during the migration window.

7. **Return the receipt.** Shape below.

## Response shape

```markdown
## Receipt <REQUEST_ID>
OPERATION: skill-sunset-announce
STATUS: ok | error
DEPRECATED_SKILL: <id>
REPLACEMENT_SKILL: <id>
ANNOUNCEMENT_REF: md://state/announcements/<slug>.md
AFFECTED_CONSUMERS: <count>
MEMOS_SENT:
  - to: <consumer>
    memo_ref: memo://inbox/<consumer>/<id>
ACTIONS_REGISTERED:
  - owner: <consumer>
    action_ref: jsonl://state/actions#L<n>
    due_iteration: <id>
ORG_SYNC_REF: <ref>
NOTES: <optional — e.g., "affected_consumers discovered via kiho_rdeps; 3 agents had no recent invocations but appeared in soul frontmatter">
```

## Invariants

- **Tier-1 md forced.** The announcement goes to Tier-1, not Tier-2. Consumers, CEO digests, and audit passes all need to be able to read it verbatim without replaying JSONL. `storage-broker` is called with `human_legible: true, access_pattern: snapshot` to force this; callers cannot downgrade.
- **Fan-out memos required.** A sunset without per-consumer memos is a silent deprecation. If step 4 fails for any consumer, the whole skill returns `status: error` and does not write the announcement — partial propagation is worse than none.
- **No user-facing prompt.** This skill does not call `AskUserQuestion`. If the CEO wants to tell the user a skill is sunsetting, that's a CEO decision made after this skill returns.
- **Actions track to sunset_iteration, not to now.** Owners get the full migration window. If `sunset_iteration` is less than 3 iterations out, the skill warns in NOTES and the CEO may push the iteration out via a committee.
- **Never modify the deprecated skill itself.** This skill announces; `skill-deprecate` marks; neither retires. Retirement is a separate step after sunset_iteration passes.

## Non-Goals

- Not a deprecation decision. `skill-deprecate` owns the judgment call; this skill assumes the judgment has already been made and runs the rollout.
- Not a user-facing announcement. Users are not told about internal skill sunsets unless the CEO surfaces it; this skill only informs agents.
- Not a retirement executor. The physical removal of the skill directory is a separate pass, run manually or via a nightly ralph housekeeping skill, only after sunset_iteration.
- Not a consumer migrator. This skill tells consumers to migrate; the consumers (or their leads) do the migration. Auto-rewriting consumer invocations is out of scope and would violate the user-accept gate for soul/skill changes.

## Grounding

- `references/storage-architecture.md` — Tier-1 md vs. Tier-2 JSONL routing rules used in step 3.
- `references/storage-tech-stack.md` — the `human_legible + snapshot` → md resolution.
- `references/react-storage-doctrine.md` — storage-broker mediation.
- `skills/core/storage/storage-broker/SKILL.md` — put op contracts used in steps 3 and 5.
- `skills/core/communication/memo-send/SKILL.md` — fan-out memos in step 4.
- `skills/_meta/skill-deprecate/SKILL.md` — the decision this skill pairs with.
- `references/org-tracking-protocol.md` — capability-matrix refresh invariants for step 6.
