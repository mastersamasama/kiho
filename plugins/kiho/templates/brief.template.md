---
brief_id: {{brief_id}}
author: kiho-ceo
target: {{target_agent_or_dept}}
mode: {{mode}}
created_at: {{iso_timestamp}}
reversibility: reversible | slow-reversible | irreversible
confidence_required: 0.90
related_plan_item: {{plan_item_id}}
budget:
  tokens: {{tokens}}
  tool_calls: {{calls}}
  wall_clock_min: {{minutes}}
---

# Brief — {{short_title}}

## Goal
{{one-paragraph goal, derived from the user's request and the plan item}}

## Context
(relevant prior KB entries, recent ledger activity, user preferences — CEO fills this in by running kb-search and session-context first)

## Constraints
- {{constraint 1}}
- {{constraint 2}}

## Success criteria
- {{criterion 1}}
- {{criterion 2}}

## Assigned
- Target: {{target}}
- Expected deliverable: {{deliverable description}}
- Expected structured return: `{ status, confidence, output_path, summary, contradictions_flagged, new_questions, skills_spawned }`

## Open questions for the assignee
(things CEO wants the subagent to think about, not things to ask the user — those bubble up)

## Escalation path
- If confidence < 0.90 AND reversible: convene a mini-committee for second opinion
- If confidence < 0.90 AND irreversible: return `status: escalate_to_user` with structured options
- If stuck: return `status: blocked` with the specific unblocker needed
