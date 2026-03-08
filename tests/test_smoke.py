from importlib.metadata import version

from typer.testing import CliRunner

from wordmark.cli import app


def test_version_command_matches_installed_package_version() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == version("wordmark")
