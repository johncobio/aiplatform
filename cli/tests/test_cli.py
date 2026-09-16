from pathlib import Path

from typer.testing import CliRunner

from aiplatform.main import app

cli = CliRunner()


def test_init_writes_config_and_validate_passes(tmp_path: Path):
    r = cli.invoke(app, ["init", "--dir", str(tmp_path), "--name", "my-agent"])
    assert r.exit_code == 0, r.output
    cfg = tmp_path / "aiplatform.yaml"
    assert cfg.exists()
    assert "name: my-agent" in cfg.read_text()

    r = cli.invoke(app, ["validate", "--dir", str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert "Configuration validated" in r.output


def test_init_refuses_to_overwrite(tmp_path: Path):
    cli.invoke(app, ["init", "--dir", str(tmp_path)])
    r = cli.invoke(app, ["init", "--dir", str(tmp_path)])
    assert r.exit_code != 0
    assert "already exists" in r.output


def test_validate_reports_errors_with_field_path(tmp_path: Path):
    (tmp_path / "aiplatform.yaml").write_text(
        "name: Bad_Name\nmodel: qwen2.5-0.5b-instruct\ncpu: 1\nmemory: 1Gi\nenvironment: dev\n"
    )
    r = cli.invoke(app, ["validate", "--dir", str(tmp_path)])
    assert r.exit_code == 2
    assert "name" in r.output


def test_unknown_target_is_rejected(tmp_path: Path):
    cli.invoke(app, ["init", "--dir", str(tmp_path)])
    r = cli.invoke(app, ["deploy", "--dir", str(tmp_path), "--target", "mars"])
    assert r.exit_code != 0
    assert "mars" in r.output
