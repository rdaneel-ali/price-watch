"""Load a local `.env` file into the environment. Existing variables win."""

import os
from collections.abc import MutableMapping
from pathlib import Path


def parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, _, value = stripped.partition("=")
    key = key.removeprefix("export ").strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return (key, value) if key else None


def load_env_file(path: Path, environ: MutableMapping[str, str] = os.environ) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        parsed = parse_env_line(line)
        if parsed is not None:
            environ.setdefault(*parsed)
