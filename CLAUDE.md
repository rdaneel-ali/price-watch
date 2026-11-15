# CLAUDE.md

Working agreements for Claude Code in this repo. This file is public. Keep private details (account IDs, ARNs, emails, budgets, internal doc locations, private repo names) in `CLAUDE.local.md`, which is gitignored.

## Project

Price Watch: describe an item in plain language with a target price and a list of source URLs. Once a day it reads each source, uses AI (through OpenRouter) to pull out the listings, and reports the best current price. Python, managed with uv. An admin CLI (`pw`) comes first; a read-only HTTP API for client apps comes later.

## Guardrails

- One goal per session. Park off-topic items in a list at the end.
- Ask clarifying questions first. Confirm before any large result.
- Stop at each step marker and wait for the user.
- Keep changes small and reviewable.
- Never commit, push, or create a PR unless the user says so. The user may commit from VS Code Source Control.
- Commit messages: one line, `Verb: short desc` (e.g. `Add: listing model`, `Fix: budget rounding`). Verbs: Add, Update, Fix, Cut. The description may include a version number but never repeats the verb. No body.
- The user pastes only the last 20-30 lines of error output.
- When the session is getting long, say so and give a handoff playbook: decisions, pending, open options with recommendations, next steps. Minimal prose.
- Never create, change or delete cloud resources without the user's explicit OK.
- Do not add infrastructure code to this repo.
- Never put secrets, account IDs, ARNs, personal data or private repo names in tracked files.
- Never read, print or ask for the OpenRouter key. Code reads `OPENROUTER_API_KEY` from the environment; in development it comes from a gitignored `.env`.
- Plans and specs live in a private docs repo, never in this repo.

## Workflow

1. Read `.github/copilot-instructions.md` before writing or reviewing code.
2. Write tests first where practical (TDD). Tests use no AWS and no network; mock httpx with `httpx.MockTransport`.
3. When code is complete, run `uv run ruff check`, `uv run ruff format --check`, `uv run pyright` and `uv run pytest`. They must be green.
4. Run the code-review skill. Never auto-fix findings. Present a short report: each finding with concise options and a recommendation.
5. Iterate until the checks are green, no blocking items remain, and every warning and nit is fixed, deferred or declined. Record deferrals and declines where the review protocol says.
6. Commit and push only on the user's verbal command or approval.
7. When ready for a PR, tell the user. Create the PR only after they say so.

## Pull requests

Keep the body tight. Not a story, and nothing sensitive.

```
## Summary
- What was added, changed, fixed or implemented (bullets)

## Testing
- What was run and the result
```

## Coding standards

Keep it simple. Do not over-engineer. Follow the code standards and review calibration in `.github/copilot-instructions.md`.
