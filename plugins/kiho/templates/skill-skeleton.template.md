---
slug: {{skill_slug_e_g_sk_playwright_visual_regression}}
topic: "{{one_phrase_topic_e_g_Playwright_visual_regression_testing}}"
role_context: "{{short_description_of_who_will_use_this_skill}}"
status: in-progress
pages_read: 0
extracted_concepts: []
seed_urls:
  - {{first_seed_url}}
last_updated: {{iso_timestamp}}
research_deep_version: 1
---

# {{topic}}

<!--
  This file is a LIVING SKELETON maintained by `research-deep`. It is overwritten
  atomically after every BFS iteration as new concepts are extracted from the doc
  tree. Do NOT edit by hand — changes will be clobbered on the next read.

  On termination, `skill-learn op=synthesize` consolidates this skeleton into a
  canonical SKILL.md at `.kiho/state/drafts/<slug>/SKILL.md` and the skeleton
  moves to `.kiho/state/skill-skeletons/_archive/`.
-->

## Overview
<!-- written on first read; refined on every subsequent read -->
{{one_paragraph_summary_of_what_this_skill_does_and_when_to_use_it}}

## When to use
<!-- bullet list of triggers; appended per read; each bullet tagged with source URL -->
- [{{source_url_1}}] {{trigger_phrase_or_situation}}

## Preconditions
<!-- what must be true before this skill applies; appended per read -->
- [{{source_url_x}}] {{precondition}}

## Procedure
<!-- numbered steps; each tagged with source URL; reorganized on consolidation -->
1. [{{source_url_x}}] {{step_description}}

## Configuration
<!-- important config knobs / options; appended per read -->
- [{{source_url_x}}] `{{option_name}}` — {{one_line_description}}

## Pitfalls and gotchas
<!-- known failure modes, debugging tips, anti-patterns -->
- [{{source_url_x}}] {{pitfall}}

## Examples
<!-- code blocks; each tagged with source URL; deduped on consolidation -->

```{{language}}
// from {{source_url_x}}
{{example_code}}
```

## Sources
<!-- all URLs read, with extraction timestamp and concept count -->
| URL | Read at | Concepts extracted |
|---|---|---|
| {{url}} | {{iso}} | {{n}} |

## Extraction log
<!--
  Mirror of .kiho/state/research-queue/<slug>.jsonl for at-a-glance auditing.
  One line per read or skip.
-->
- [{{iso}}] READ {{url}} depth={{d}} new_concepts={{n}}
- [{{iso}}] SKIP {{url}} reason={{reason}}
