"""Tests for the Wraith CLI commands (Typer CliRunner)."""

from typer.testing import CliRunner

from wraith.cli import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Wraith" in result.stdout


def test_cli_init_zsh():
    result = runner.invoke(app, ["init", "zsh"])
    assert result.exit_code == 0
    assert "_wraith_precmd" in result.stdout
    assert "WRAITH_SESSION_ID" in result.stdout


def test_cli_init_bash():
    result = runner.invoke(app, ["init", "bash"])
    assert result.exit_code == 0
    assert "_wraith_bash_precmd" in result.stdout


def test_cli_init_unsupported():
    result = runner.invoke(app, ["init", "fish"])
    assert result.exit_code != 0
    assert "Unsupported shell" in result.stdout


def test_cli_setup(tmp_path, monkeypatch):
    monkeypatch.setattr("wraith.cli.get_config_dir", lambda: tmp_path)
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    assert "Welcome to Wraith" in result.stdout


def test_cli_doctor():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Running Wraith Doctor" in result.stdout
    assert "Python Runtime" in result.stdout


def test_cli_persona_commands():
    # List
    res_list = runner.invoke(app, ["persona", "list"])
    assert res_list.exit_code == 0
    assert "poltergeist" in res_list.stdout
    assert "ancestor" in res_list.stdout

    # Use
    res_use = runner.invoke(app, ["persona", "use", "ancestor"])
    assert res_use.exit_code == 0
    assert "Switched to persona" in res_use.stdout


def test_cli_graveyard_and_ofrenda():
    res_gy = runner.invoke(app, ["graveyard"])
    assert res_gy.exit_code == 0
    assert "THE GRAVEYARD STATS" in res_gy.stdout

    res_of = runner.invoke(app, ["ofrenda"])
    assert res_of.exit_code == 0
    assert "OFRENDA DE COMANDOS" in res_of.stdout


def test_cli_export():
    res = runner.invoke(app, ["export"])
    assert res.exit_code == 0
    assert '"haunts":' in res.stdout
    assert '"whispers":' in res.stdout


def test_cli_forget():
    res = runner.invoke(app, ["forget", "--all"])
    assert res.exit_code == 0
    assert "Purged" in res.stdout
