# Price Watch

Describe an item in plain language, give it a target price and a list of source URLs. Once a day, Price Watch reads each source, uses AI to pull out the listings, and reports the best current price and whether it meets your target.

Status: early development. Python, managed with [uv](https://docs.astral.sh/uv/).

## Development

```sh
uv sync
git config core.hooksPath .githooks   # enables the gitleaks pre-commit hook (needs gitleaks installed)
uv run ruff check
uv run ruff format --check
uv run pyright
uv run pytest
```

Secrets such as the OpenRouter key are read from the environment (`OPENROUTER_API_KEY`). In development, put them in a gitignored `.env` file. Never commit them.

## License

MIT
