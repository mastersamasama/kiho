---
committee_id: {{committee_id}}
owner_agent: {{owner_agent}}
scope: {{scope}}
topic: "{{topic}}"
created_at: {{created_at}}
closed_at: {{closed_at}}
status: open
rounds_used: 0
max_rounds: {{max_rounds}}
members:
  - {{member_1}}
  - {{member_2}}
  - {{member_3}}
question: "{{question}}"
reversibility_tag: {{reversibility_tag}}
knowledge_update: {{knowledge_update}}
kb_page_id: null
---

# Committee — {{slug}}

## Topic
{{topic}}

## Members
| Agent | Role | Department |
|---|---|---|
| {{member_1}} | {{role_1}} | {{dept_1}} |
| {{member_2}} | {{role_2}} | {{dept_2}} |
| {{member_3}} | {{role_3}} | {{dept_3}} |

## Status
- **Created:** {{created_at}}
- **Status:** open
- **Rounds completed:** 0 / {{max_rounds}}
- **Close rule:** unanimous + no unresolved challenges + aggregate confidence >= 0.90

## Artifacts
- Transcript: `transcript.md`
- Decision: `decision.md` (written by clerk on close)
- Dissent: `dissent.md` (written by clerk if minority positions exist)

## Notes
(Committee runner appends round summaries here as the committee progresses.)
