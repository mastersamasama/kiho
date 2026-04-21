---
project_slug: {{project_slug}}
agent_count: {{agent_count}}
last_modified: {{iso_timestamp}}
schema_version: 1
---

# Org Registry — {{project_slug}}

## CEO
- **Agent:** ceo-01
- **Definition:** agents/kiho-ceo.md
- **Status:** active

## Departments

### {{department_1_name}}
- **Lead:** {{dept1_lead_id}} ({{dept1_lead_definition}})
- **Status:** active
- **Teams:**
  (none yet)
- **Direct reports:**
  (none yet)

### {{department_2_name}}
- **Lead:** {{dept2_lead_id}} ({{dept2_lead_definition}})
- **Status:** active
- **Teams:**
  (none yet)
- **Direct reports:**
  (none yet)

### {{department_3_name}}
- **Lead:** {{dept3_lead_id}} ({{dept3_lead_definition}})
- **Status:** active
- **Teams:**
  (none yet)
- **Direct reports:**
  (none yet)

## Shared Services
- **kb-manager:** kb-manager-01 (agents/kiho-kb-manager.md) — active
- **researcher:** researcher-01 (agents/kiho-researcher.md) — active

## Change Log
| Timestamp | Event | Details |
|---|---|---|
| {{iso_timestamp}} | bootstrap | Initial org created with {{department_count}} departments |
