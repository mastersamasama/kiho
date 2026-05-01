# Vendor official documentation registry

Authoritative source mapping for vendor API/SDK queries. When a researcher
agent needs facts about any of these vendors, the cascade MUST hit the
listed URL FIRST before considering web search / cached training data.

## Schema
- `vendor`: canonical short name
- `topics`: query keywords that route to this vendor
- `official_docs_root`: trusted-source URL (https only)
- `last_verified`: ISO date the URL was confirmed reachable

## Registry

| Vendor | Topics | Official docs root | Last verified |
|---|---|---|---|
| deepseek | deepseek api, deepseek model, deepseek-chat, deepseek-reasoner, deepseek-v4 | https://api-docs.deepseek.com/ | 2026-05-01 |
| openai | openai api, gpt-4, gpt-4o, openai sdk, chat completions | https://platform.openai.com/docs/ | 2026-05-01 |
| anthropic | anthropic api, claude api, claude-3, messages api | https://docs.anthropic.com/ | 2026-05-01 |
| google-gemini | gemini api, generativelanguage, gemini-1.5, gemini-2 | https://ai.google.dev/api/ | 2026-05-01 |
| moonshot | kimi api, moonshot, kimi-k2 | https://platform.moonshot.cn/docs/ | 2026-05-01 |
| zhipu | glm api, zhipuai, glm-4, bigmodel | https://open.bigmodel.cn/dev/api/ | 2026-05-01 |
| react-native | react native api, expo, metro | https://reactnative.dev/docs/ | — |
| nativewind | nativewind, tailwind native | https://www.nativewind.dev/ | — |

## Update protocol

When adding a new vendor:
1. Verify the URL returns 200 + valid HTML/markdown via WebFetch
2. Add row above with today's date as last_verified
3. Re-run any pending vendor-API research with the new authoritative source

When `last_verified` is older than 90 days for a vendor in active use,
researcher SHOULD re-fetch the root page once to confirm not 404 / not
moved before relying on cached descendants.
