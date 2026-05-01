# Fixture — vendor official docs routing

Manual-review fixture for the v6.6.2 vendor-official-docs invariant. There is no
RN/jest runner in kiho-plugin (the codebase is Python + Markdown), so this file
is a human-readable evaluation harness rather than executable assertions.

## How to use

Run `kiho-researcher` (or the `research` skill) against each `query` row below.
Inspect the agent's response and confirm:

1. The response cites the row's `expected_official_docs_root` (or a deeper
   path under that host) as the primary source.
2. At least one verbatim quote in the response can be traced back to that
   host via `WebFetch`.
3. The response NOTES field flags `vendor_official_docs_used: <vendor>`.
4. Citations do NOT include random-blog or third-party tutorial sites for
   facts that should come from the vendor (model ids, endpoint paths,
   pricing, rate limits, deprecation dates).

A row "passes" only when all four conditions hold. A row "fails" if the
agent answers from cached training data without a vendor-doc citation,
or cites a non-vendor host as authoritative.

## Cases

| # | Query | Vendor | Expected official_docs_root |
|---|---|---|---|
| 1 | What is the model id for DeepSeek's reasoner-class model and what does the API endpoint look like? | deepseek | https://api-docs.deepseek.com/ |
| 2 | List the current GPT-4 family model ids supported by OpenAI's chat completions API. | openai | https://platform.openai.com/docs/ |
| 3 | What is the latest claude-3 model id Anthropic recommends for production messages-API use? | anthropic | https://docs.anthropic.com/ |
| 4 | What request shape does the Gemini generativelanguage API expect for a multimodal call? | google-gemini | https://ai.google.dev/api/ |
| 5 | What is the Moonshot Kimi-k2 endpoint path and authentication header format? | moonshot | https://platform.moonshot.cn/docs/ |
| 6 | Which GLM-4 variants does Zhipu's bigmodel API expose, and what is the base URL? | zhipu | https://open.bigmodel.cn/dev/api/ |
| 7 | What is React Native's recommended way to handle keyboard avoidance on iOS in current docs? | react-native | https://reactnative.dev/docs/ |
| 8 | How does NativeWind v4 wire up Tailwind classnames for React Native components? | nativewind | https://www.nativewind.dev/ |

## Negative case (sanity check)

A non-vendor query should NOT trigger Step 0 routing — confirm the agent runs
the standard cascade (Step 1 KB onward) without consulting
`vendor-official-docs.md`:

| # | Query | Expected behaviour |
|---|---|---|
| 9 | Summarise our project's recent kb-manager refactor commits. | Step 1 KB hits, no vendor-docs fetch |

## Reviewer scorecard

For each row 1-8, fill:

```
row: <#>
queried_official_docs: yes | no
verbatim_quote_present: yes | no
non_vendor_blog_cited_for_vendor_fact: yes | no
verdict: pass | fail
notes: <free text>
```

Eight rows must score `pass` for the v6.6.2 invariant to be considered
working in the field. A single `fail` is a regression — file under
`_proposals/v6.6.2-vendor-official-docs/regressions/` with the failing
query and the agent's response.
