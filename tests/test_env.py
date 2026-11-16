from pathlib import Path

from price_watch.env import load_env_file, parse_env_line


def test_parse_lines() -> None:
    assert parse_env_line("A=b") == ("A", "b")
    assert parse_env_line("export A='b c'") == ("A", "b c")
    assert parse_env_line('A="x"') == ("A", "x")
    assert parse_env_line("# c") is None
    assert parse_env_line("junk") is None


def test_load_does_not_override_existing(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("A=1\nB=2\n")
    environ = {"A": "keep"}
    load_env_file(path, environ)
    assert environ == {"A": "keep", "B": "2"}


def test_missing_file_is_fine(tmp_path: Path) -> None:
    environ: dict[str, str] = {}
    load_env_file(tmp_path / "nope", environ)
    assert environ == {}
