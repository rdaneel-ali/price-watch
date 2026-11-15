# CLAUDE.md

Working agreements for Claude Code in this repo. This file is public. Keep private details (account IDs, ARNs, emails, budgets, internal doc locations) in `CLAUDE.local.md`, which is gitignored.

## Project

Price Watch: track the best current price for an item across source URLs, using AI to read each page. Python, managed with uv. Admin CLI (`pw`) first; a read-only HTTP API later.

## Guardrails

- One goal per session. Ask clarifying questions first. Keep changes small and reviewable.
- Never commit, push, or create a PR unless the user says so.
- Commit messages: one line, `Verb: short desc` (Add, Update, Fix, Cut). No body.
- Never create, change or delete cloud resources without the user's explicit OK.
- Do not add infrastructure code to this repo.
- Never put secrets, account IDs, ARNs, personal data or private repo names in tracked files.
- Never read, print or ask for the OpenRouter key. Code reads `OPENROUTER_API_KEY` from the environment; in development it comes from a gitignored `.env`.
- Plans and specs live in a private docs repo, not here.

## Workflow

1. Read `.github/copilot-instructions.md` before writing or reviewing code.
2. Write tests first where practical. Tests use no AWS and no network; mock httpx with `httpx.MockTransport`.
3. Before a commit, all of these must be green: `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run pytest`.
4. Review the diff for correctness bugs and the rules above. Fix blocking issues; keep nits out.
5. Open a PR only when the user says so.

## Pull requests

Keep the body tight and free of sensitive details.

```
## Summary
- What was added, changed, fixed or implemented (bullets)

## Testing
- What was run and the result
```

## Coding standards

Keep it simple. Do not over-engineer. See `.github/copilot-instructions.md`.
