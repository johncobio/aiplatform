import pytest

from aiplatform.config.loader import load_config
from aiplatform.errors import ConfigError


def test_load_config_reads_yaml(tmp_path):
    (tmp_path / "aiplatform.yaml").write_text(
        "name: demo\nmodel: qwen2.5-0.5b-instruct\ncpu: 1\nmemory: 1Gi\nenvironment: dev\n"
    )
    cfg = load_config(tmp_path / "aiplatform.yaml")
    assert cfg.name == "demo"


def test_missing_file_is_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "aiplatform.yaml")


def test_invalid_yaml_reports_field_path(tmp_path):
    (tmp_path / "aiplatform.yaml").write_text(
        "name: demo\nmodel: qwen2.5-0.5b-instruct\ncpu: 1\nmemory: 1Gi\nenvironment: dev\n"
        "autoscaling:\n  min: 3\n  max: 1\n"
    )
    with pytest.raises(ConfigError, match="autoscaling"):
        load_config(tmp_path / "aiplatform.yaml")


def test_non_mapping_yaml_is_config_error(tmp_path):
    (tmp_path / "aiplatform.yaml").write_text("- just\n- a list\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(tmp_path / "aiplatform.yaml")
