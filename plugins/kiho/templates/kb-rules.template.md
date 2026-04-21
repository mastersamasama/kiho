# KB rules — {{project_name}}

This file defines the durable rules for how the project KB is used. kb-manager reads this before every write and rejects proposals that violate a rule. `kb-lint` check #10 scans for rule violations across all existing pages.

Hand-editing this file is allowed. Changes take effect on the next kb-manager invocation. **Any change should be committed to git** if the project uses git — rules are as important as code.

## Must-follow (enforced by kb-manager on every write)

1. **Every `decisions/` page must cite at least one source.** The source must be either a committee transcript path under `raw/decisions/` or a raw source file under `raw/sources/`. A decision without provenance is ungrounded and will be rejected.
2. **Entity pages must have `status` in frontmatter.** Values: `active` | `deprecated` | `archived`. Status `active` is the default for new entities.
3. **Concept pages must define exactly one idea.** A concept page that describes two ideas (e.g., "retries and caching") gets split into two pages by kb-manager. Lint check #5 catches these.
4. **Any convention that conflicts with the company KB must be marked `local_override: true`** in frontmatter, with a `local_override_reason` field explaining why. kb-manager flags unmarked conflicts as contradictions.
5. **Questions pages must reference at least two pages they contradict or relate to.** A question with no anchors is just a TODO, not a KB question.
6. **Pages with `confidence < 0.60` must link to an open `questions/` page** in their frontmatter (`uncertainty_link:`). Uncertain claims should trigger follow-up work.
7. **Titles must be under 80 characters.** Longer titles break index.md rendering.
8. **Page IDs follow the pattern `<type>-<slug>` or `ADR-NNNN-<slug>` for decisions.** kb-manager generates these automatically on `kb-add`; do not hand-craft.

## Conventions (strongly recommended, not hard-enforced)

- Entity names use kebab-case and match the actual service/module name in code where possible.
- Concept names are kebab-case nouns (not verbs).
- Decision IDs follow `ADR-NNNN-<slug>` with zero-padded 4-digit number.
- Tags are kebab-case, concrete (`retry-policy`, not `retries`).
- Sources in `provenance[]` include both `kind` and `ref`. Accepted kinds: `committee_decision`, `git_commit`, `user_message`, `prior_kb_fact`, `web_source`, `deepwiki`, `cloned_repo`.
- Page bodies start with a one-sentence summary that could stand alone as a definition.

## Naming

- Files use lowercase kebab-case: `billing-webhook.md`, not `BillingWebhook.md` or `billing_webhook.md`.
- Entities may include a suffix for disambiguation: `auth-service-v2.md` when multiple versions coexist (old version goes to `archived` status, not deleted).
- Decision files: `ADR-0007-queue-backend.md`.
- Question files: `Q-<slug>.md`, e.g. `Q-rate-limit-policy.md`.

## Review cadence

- kb-lint runs automatically: at end of every ingest batch; at start of every `/kiho evolve`; as the final step in CEO's Ralph loop DONE phase.
- The user can explicitly run `/kiho kb-lint` to force a full check.

## Amendment process

To change a rule, convene a committee with topic "Amend KB rules". The committee must produce a decision page explaining the change. On close, the Clerk invokes `kb-update` on this file with the new rule. This file's version history lives in git (if the repo uses git).
