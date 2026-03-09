from click.testing import CliRunner

from arena_interface.cli import cli


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ArenaController host CLI" in result.output
    assert "--tcp-nodelay / --no-tcp-nodelay" in result.output
    assert "bench" in result.output
