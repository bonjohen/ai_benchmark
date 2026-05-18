# OAuth Credit Routing for CLI Tools

## The Lesson

When a CLI tool supports multiple authentication methods with different billing paths, scripts that invoke it must explicitly select the intended billing path — otherwise, environment variable precedence silently routes charges to the wrong budget.

## Context

Claude CLI supports two authentication methods: API key (`ANTHROPIC_API_KEY` environment variable) and OAuth session tokens. API key usage bills against a paid API budget; OAuth usage bills against a separate session-based credit allocation. A reporting pipeline invokes Claude CLI for LLM synthesis of daily intelligence reports. The development machine has `ANTHROPIC_API_KEY` set for other projects, which Claude CLI picks up by default.

## What Happened

1. The initial `report.bat` script invoked `claude -p` to synthesize reports. It worked correctly but silently used the API key from the environment, billing against the paid API budget.
2. The cost was discovered when API credit usage spiked without corresponding API development work. The root cause was the reporting pipeline consuming credits through the API key path.
3. The fix was explicit: `report.bat` now clears `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` at the start of the script, forcing Claude CLI to fall back to OAuth session authentication.
4. A `CLAUDE_SESSION` configuration variable was added to the environment template so OAuth sessions could be managed explicitly across reporting scripts.
5. A `test_oauth.bat` verification script was created to confirm OAuth status before running expensive report generation.
6. The pattern was elevated to a global guardrail: a pre-tool-use hook in Claude Code checks for `ANTHROPIC_API_KEY` in the environment and blocks bash commands if it's set, preventing accidental API-key billing during interactive sessions too.

## Key Insights

- **Environment variable precedence is a billing hazard.** When a tool checks multiple auth sources in priority order (env var > config file > OAuth), a stale env var from another project silently overrides the intended auth method. The charges are real and hard to notice until the invoice arrives.
- **Scripts should declare their billing path explicitly.** Clearing unwanted auth variables at the top of a script is defensive but correct. It makes the billing path visible in the script source and immune to environment changes.
- **Verification before expensive operations saves money.** A 2-second OAuth status check before a 30-second LLM synthesis prevents wasted credits when the session has expired. The ratio of check cost to operation cost makes this always worthwhile.
- **Guardrails belong at multiple layers.** The script-level fix (clearing env vars) handles batch operations. The hook-level fix (blocking API key usage in Claude Code) handles interactive sessions. Neither alone covers all paths.
- **Silent billing failures are worse than loud errors.** An auth failure that crashes the script is annoying but safe. An auth "success" that bills the wrong budget is invisible and expensive. Prefer loud failure modes for billing-sensitive operations.

## Applicability

Applies to any system where multiple authentication/billing paths exist: cloud CLI tools (AWS profiles, GCP service accounts), SaaS APIs with team vs. personal keys, CI/CD pipelines with shared credentials. Does NOT apply to systems with a single auth method or where all auth methods bill the same account.

## Related Lessons

- [Two-Stage Report Generation](two-stage-report-generation.md) — The reporting pipeline that surfaced this billing issue.
