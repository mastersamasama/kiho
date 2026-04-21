# Security scan (skill-create Step 8, Gate 9)

Enforces OWASP Agentic Skills Top 10 (2026) on every new skill. Runs as Gate 9 of the 10-gate validation pipeline. Full risk model in `references/skill-authoring-standards.md` §"Security". This reference is the skill-create implementation of that spec.

## Contents
- [The 6 mechanical checks](#the-6-mechanical-checks)
- [Secret detection patterns](#secret-detection-patterns)
- [Input validation rules](#input-validation-rules)
- [allowed-tools scope check](#allowed-tools-scope-check)
- [Tool wrapper check](#tool-wrapper-check)
- [Lethal Trifecta evaluation](#lethal-trifecta-evaluation)
- [Risk tier mapping](#risk-tier-mapping)
- [Remediation playbook](#remediation-playbook)

## The 6 mechanical checks

Each check is a hard fail — if the check fails, the skill is rejected and returned to Step 5 (body draft) for revision.

| # | Check | Scope | Failure action |
|---|---|---|---|
| 1 | Secret detection | body + scripts + references + templates + evals | reject; require env vars or keychain |
| 2 | Input validation in scripts | all `scripts/*.py` | reject; require pathlib.Path allowlist / subprocess sanitization |
| 3 | `allowed-tools` scope | frontmatter | reject wildcards; require narrow scope |
| 4 | Tool wrapper check | body | reject skills < 20 lines of non-boilerplate |
| 5 | Fail-closed defaults | scripts | reject scripts that proceed on unknown state |
| 6 | Audit-trail logging | scripts making external calls | reject scripts that log response bodies |

Plus the **Lethal Trifecta** evaluation (described separately below).

## Secret detection patterns

Scan every file in the skill directory (SKILL.md body, scripts, references, templates, evals) for these regex patterns:

```
(?i)\b(api[_-]?key|password|passwd|pwd|secret|token|access[_-]?key|private[_-]?key)\s*[:=]\s*["'][^"']{8,}["']
(?i)\b(AWS|OPENAI|ANTHROPIC|GITHUB|STRIPE|TWILIO|SENDGRID)_[A-Z_]*\s*[:=]\s*["'][^"']{16,}["']
\b[A-Za-z0-9+/]{40,}={0,2}\b                    # long base64-ish strings
\b[a-f0-9]{32,}\b                               # long hex strings (often API keys)
(?i)-----BEGIN (RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----
(?i)xox[aboprs]-[0-9a-zA-Z-]+                   # Slack tokens
(?i)sk-[a-zA-Z0-9]{48,}                         # OpenAI-style tokens
(?i)ghp_[a-zA-Z0-9]{36}                         # GitHub personal access tokens
```

**Whitelisted patterns** (not secrets):
- `SKILL.md` field markers (frontmatter syntax `name: xxx`)
- Variable names in example code blocks (e.g., `api_key = os.environ["OPENAI_API_KEY"]`)
- Example values clearly marked (e.g., `YOUR_API_KEY_HERE`, `<redacted>`)

**Action on hit:** reject; require the caller to rewrite to use environment variables or the OS keychain (see `skills/_meta/skill-create/references/description-improvement.md` for the "credentials never in KB" rule from v5.10).

## Input validation rules

For any `scripts/*.py` in the skill:

**Rule A: No untrusted shell command construction.**
```python
# REJECT
os.system(user_input)                     # command injection
subprocess.run(user_input, shell=True)    # command injection
subprocess.Popen(user_input, shell=True)  # command injection

# ACCEPT
subprocess.run(["ls", user_input], check=True)  # args as list, no shell
subprocess.run(shlex.split(user_cmd))           # if user_cmd is validated
```

**Rule B: No untrusted path traversal.**
```python
# REJECT
open(user_path).read()                    # no validation
Path(user_path).read_text()               # no validation

# ACCEPT
base = Path("/allowed/directory").resolve()
target = (base / user_path).resolve()
if not target.is_relative_to(base):
    raise ValueError("path outside allowed directory")
target.read_text()
```

**Rule C: No eval / exec of fetched content.**
```python
# REJECT
eval(fetched_content)
exec(fetched_content)
__import__(module_name_from_user)

# ACCEPT
json.loads(fetched_content)
yaml.safe_load(fetched_content)
```

**Rule D: Bare `open()` without error handling is flagged (warning, not hard fail).** Scripts must catch `FileNotFoundError` and `PermissionError` explicitly, or use context managers with try/except.

**Detection:** regex scan for the bad patterns above in every `.py` file. A hit is a hard fail; the skill is returned to Step 6 (scripts).

## allowed-tools scope check

If the skill's frontmatter declares `allowed-tools`:

```yaml
# REJECT — wildcard grants
allowed-tools: Bash(*)
allowed-tools: Edit(*)
allowed-tools: WebFetch(*)

# ACCEPT — narrow scope
allowed-tools: Bash(git status) Bash(git diff *) Bash(git add *) Bash(git commit -m *)
allowed-tools: Edit(src/**) Read(**)
```

**Parse rule:** split on whitespace; each token must be `ToolName(...)` where the parenthesized expression is specific enough to describe the operation. A `*` inside the parens is OK if it's constrained to a subcommand (`Bash(git add *)` is fine; `Bash(*)` is not).

**Wildcard detection:**
```
\b(Bash|Edit|Write|WebFetch|WebSearch|Agent)\s*\(\s*\*\s*\)
```

Hit → hard fail. Revise the frontmatter to narrow the scope.

## Tool wrapper check

A skill that just wraps a tool call is CATALOG spam — it doesn't add domain knowledge, orchestration, or multi-step coordination.

**Heuristic:** count non-boilerplate lines in the SKILL.md body (excluding YAML frontmatter, contents TOC, section headings, blank lines, and simple "see references/X" pointers). If the count is < 20, the skill is a thin wrapper.

**Exception:** skills marked `user-invocable: false` with a declared knowledge-only purpose may be shorter — they exist as reference content, not as tool coordinators.

**Action on hit:** reject; either expand the skill's body to actually add value, or delete it and document the tool usage inline in a parent skill.

## Lethal Trifecta evaluation

Simon Willison's 2026 analysis: a skill is **dangerous** when it simultaneously has all three capabilities:

1. **Private data access** — reads `~/.config`, `~/.ssh`, SSH keys, API tokens, browser cookies, OS keychain, git credentials
2. **Untrusted content exposure** — ingests user input, external files, web pages, email bodies, git commit messages from forks
3. **Network egress** — network calls, webhooks, curl, email sending, MCP with remote endpoints

**Detection per axis:**

| Axis | Signals in SKILL.md body or scripts |
|---|---|
| Private data | mentions `~/.config`, `~/.ssh`, `keychain`, `credentials`, `api.keyring`, `ssh-keygen`, `gpg`, imports `keyring`, `cryptography.hazmat`, reads `~/.netrc`, `~/.aws/credentials` |
| Untrusted content | accepts URL or file path from `sys.argv`, `input()`, fetches pages, reads git history from forks, parses email, reads downloaded archives |
| Network egress | uses `requests`, `urllib`, `httpx`, `WebFetch`, `WebSearch`, `curl` via subprocess, SMTP, webhook POSTs, MCP calls to remote endpoints |

**Evaluation:**

```python
axes = {
    "private_data": detect_private_data_access(skill_dir),
    "untrusted_content": detect_untrusted_input(skill_dir),
    "network_egress": detect_network_egress(skill_dir),
}
axes_active = sum(axes.values())
```

## Risk tier mapping

| axes_active | Risk tier | Disposition |
|---|---|---|
| 0 | low | allowed |
| 1 | low | allowed |
| 2 | medium | allowed with warning; log which 2 axes are active in audit block |
| 3 | **trifecta** | **blocked** unless skill has `disable-model-invocation: true` |

If blocked and the caller wants to proceed:
- **Option A (preferred):** revise the skill to remove one capability. Break the trifecta.
- **Option B:** add `disable-model-invocation: true` to frontmatter. This allows the skill to exist but only users can invoke it — Claude cannot auto-trigger.
- **Option C:** escalate to CEO for user approval. CEO surfaces the risk profile via `AskUserQuestion`; user explicitly approves the trifecta for a specific use case.

Record the risk tier in the audit block:

```yaml
security_risk_tier: low | medium | high | trifecta
lethal_trifecta_check: passed | warning | blocked
lethal_trifecta_axes: []   # list of active axes if >= 2
```

## Remediation playbook

When a check fails, the script or body needs a targeted fix:

| Failure | Fix |
|---|---|
| Secret detected | Replace with `os.environ["<VAR>"]` or keychain read. Delete the value from git history if already committed. |
| Shell injection in script | Switch to `subprocess.run([...], shell=False)` with args as a list |
| Path traversal in script | Use `Path(base).resolve()` + `is_relative_to` check |
| `eval()` on fetched content | Switch to `json.loads()` or `yaml.safe_load()` |
| `allowed-tools: Bash(*)` | Narrow to specific invocations: `Bash(git add *) Bash(git commit -m *)` |
| Tool wrapper (<20 lines) | Expand the body with domain knowledge OR delete the skill |
| Trifecta with all 3 axes | Remove one capability (prefer) OR add `disable-model-invocation: true` OR escalate to CEO |

After each fix, re-run Gate 9. Up to 3 revision loops total across all gates.
