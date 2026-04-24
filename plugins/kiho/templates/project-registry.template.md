---
# kiho v6 project registry
#
# Location: $COMPANY_ROOT/project-registry.md
# Purpose:  lint seed for bin/agent_md_lint.py to detect project-coupling leaks
#           in agent.md files. Any string listed here that appears in an agent's
#           role_generic, role_specialties, soul §1 biography, or soul §4
#           red-line object will fail the lint.
#
# Scaffolded automatically by kiho-setup on first v6 turn. kiho-setup seeds
# this with projects it detects (scanning $CLAUDE_PROJECTS for directories
# that contain `.kiho/`). Safe to edit by hand.
---

# Known projects (for agent.md lint)

One project identifier per line below, lowercase, whitespace-trimmed. These
strings are matched case-insensitively against agent.md content by
`bin/agent_md_lint.py`.

Seeded projects:

- 33ledger
- kiho-plugin

<!--
Add your own projects here, one per line. Examples:

- acme-corp-api
- my-side-project
- client-xyz-dashboard

When an agent works on a project, `experience[].project` gets the project ID
and `current_state.active_project` gets updated — that's the CORRECT place
for project-specific information. The lint only blocks project names from
appearing in PORTABLE fields (role_generic, specialties, biography, red-line
object) so the agent stays reusable across projects.
-->
