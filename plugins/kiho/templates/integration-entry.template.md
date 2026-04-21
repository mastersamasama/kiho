---
integration_id: {{integration_id}}            # kebab-case slug, e.g. mcp-playwright
type: {{type}}                                  # mcp | native | cli
display_name: {{display_name}}                  # human name
owner_agent: {{owner_agent}}                    # agent_id responsible for correct use
trust_level: {{trust_level}}                    # vendor-official | community-vetted | unverified | forbidden
auth_mode: {{auth_mode}}                        # none | env-var | oauth | interactive | inherited
failure_mode: {{failure_mode}}                  # soft | hard | escalate
registered_at: {{iso_timestamp}}
registered_by: {{registered_by}}                # ceo-01 by default
tools:
  - {{tool_1}}
  - {{tool_2}}
---
# {{display_name}}

## Purpose
{{one-sentence_what_this_integration_does}}

## Trust rationale
{{why_this_trust_level — provenance, deployment_history, vendor_status}}

## Auth
{{how_credentials_or_env_vars_are_provided}}

## Failure mode
{{what_happens_when_the_integration_breaks — soft_degrade / hard_block / escalate_to_ceo}}

## Notes
{{optional — deployment caveats, known quirks, version pins}}
