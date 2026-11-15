import pytest

from price_watch.cli import build_parser, main


def test_main_prints_help_and_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "pw" in capsys.readouterr().out


def test_parser_program_name() -> None:
    assert build_parser().prog == "pw"
