from importlib.metadata import version

from typer.testing import CliRunner

from wordmark.cli import app
from wordmark import uno_engine


def test_version_command_matches_installed_package_version() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == version("wordmark")


def test_packaged_uno_helper_resolves_to_script() -> None:
    with uno_engine._helper_script_path() as helper:  # noqa: SLF001 - packaging regression guard
        assert helper.name == "uno_replace.py"
        assert helper.exists()
