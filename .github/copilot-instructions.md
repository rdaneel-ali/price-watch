# Copilot instructions

Source of truth for Copilot guidance in this repo (code review and suggestions). This file is public; keep it free of secrets and private details.

## Project

Price Watch: tracks the best current price for an item across source URLs, using AI (through OpenRouter) to extract listings. Python with uv, ruff, pyright (strict), pytest, httpx, Pydantic v2.

## Code standards

- Keep it simple. Prefer the smallest solution that is correct and readable.
- Small, pure functions. Isolate side effects (I/O, time) at the edges.
- Functions are `verb_noun` (`parse_listing`); variables are descriptive nouns (`price_cents`).
- Money is integer cents. AI spend is integer micro-dollars. Timestamps are UTC ISO 8601.
- pyright strict. No `Any` without narrowing; use `object` and narrow.
- Helpers must not return silently wrong output: raise, or return `None`.
- Validate untrusted input (fetched pages, AI answers) at the boundary. Every record carries `user_id`.
- Never log or store secrets. No hard-coded account IDs, ARNs or keys; read config from the environment.
- No infrastructure code in this repo. Flag any that appears.
- Tests: pytest, no AWS, no network. Mock httpx with `httpx.MockTransport`.

## Review behavior

Review the whole change in one pass. Report a finding only with a concrete failure, risk or standards violation and where it occurs. Do not flag what ruff or pyright already enforce. Severity: blocking (bug, security, data loss, broken test), warning (likely future bug, missing test, unclear naming), nit (optional; keep few).
