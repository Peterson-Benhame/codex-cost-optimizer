from typer.testing import CliRunner

from codex_cost_optimizer.cli import app


runner=CliRunner()


def test_help_lists_core_commands():
    result=runner.invoke(app,["--help"])
    assert result.exit_code == 0
    assert "inspect" in result.stdout
    assert "run" in result.stdout
    assert "report" in result.stdout
