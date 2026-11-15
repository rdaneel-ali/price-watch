# Copilot instructions

Source of truth for Copilot guidance in this repo (code review and suggestions). This file is public; keep it free of secrets and private details.

## Project

Price Watch: tracks the best current price for an item across source URLs, using AI (through OpenRouter) to extract listings. Python with uv, ruff, pyright (strict), pytest, httpx, Pydantic v2, BeautifulSoup, argparse.

## Code standards

- Keep it simple. Prefer the smallest solution that is correct and readable.
- Small, modular, reusable functions. Cross-cutting concerns (logging, validation, error handling, budget checks) belong in one place.
- Prefer pure functions. Isolate side effects (I/O, time, randomness, network) at the edges so core logic is easy to test.
- Follow PEP 8 naming:
  - functions are `verb_noun` in snake_case (`parse_listing`)
  - variables are descriptive nouns (`price_cents`)
  - classes are PascalCase; constants are UPPER_SNAKE_CASE
  - no single-letter names except `i`, `j`, `k` in loops and `e` in `except`
- Money is integer cents, never floats. AI spend is integer micro-dollars. Timestamps are UTC ISO 8601 ending in `Z`.
- pyright strict. Avoid `Any`; use `object` and narrow. Type every public function.
- Helpers must not return silently wrong output: raise, or return `None`. Never count on callers to validate.
- Validate untrusted input (fetched pages, AI answers, CLI arguments, API requests) at the boundary with Pydantic. Every record carries `user_id`, and every read is scoped to its owner.
- Never log or store secrets, tokens or API keys. No hard-coded account IDs, ARNs or keys; read config from the environment.
- No infrastructure code in this repo. Flag any that appears.
- Tests: pytest. Unit-test pure logic (validation, judging, budget, best-price pick). No AWS and no network; mock httpx with `httpx.MockTransport`.
- Follow language and library best practices, checked against primary docs. Avoid anti-patterns.

## Review behavior

Review the whole change in one pass and report everything that matters up front. Each later run should find less only because earlier findings were fixed, not because the review was shallow.

- Report a finding only if you can state a concrete failure, risk, or standards violation, and where it occurs.
- Do not speculate, and do not restate the same issue in several places. Group repeats into one finding that lists the locations.
- Do not flag what ruff or pyright already enforce, or code outside the change.
- Do not re-raise an item the author has marked as deferred or explained in the PR.
- Severity:
  - **Blocking**: bug, security issue, data loss, broken test, or a violation of a rule above that affects correctness.
  - **Warning**: likely future bug, missing test for new logic, unclear naming, or a standards violation with no immediate failure.
  - **Nit**: optional polish. Keep nits few, and group them.
- For each finding give a short explanation and a suggested fix. Do not rewrite working code for taste.
