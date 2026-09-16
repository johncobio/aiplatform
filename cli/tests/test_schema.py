import pytest
from pydantic import ValidationError

from aiplatform.config.quantity import parse_cpu, parse_memory
from aiplatform.config.schema import WorkloadConfig

VALID = {
    "name": "document-agent",
    "model": "qwen2.5-0.5b-instruct",
    "cpu": 2,
    "memory": "2Gi",
    "environment": "staging",
    "autoscaling": {"min": 1, "max": 5},
}


def test_valid_config_parses():
    cfg = WorkloadConfig.model_validate(VALID)
    assert cfg.name == "document-agent"
    assert cfg.cpu_cores == 2.0
    assert cfg.memory_bytes == 2 * 1024**3
    assert cfg.port == 8000
    assert cfg.autoscaling.min == 1


@pytest.mark.parametrize("bad_name", ["Document_Agent", "-agent", "a" * 64, "agent.v1", ""])
def test_name_must_be_dns_label(bad_name):
    with pytest.raises(ValidationError):
        WorkloadConfig.model_validate({**VALID, "name": bad_name})


def test_autoscaling_min_cannot_exceed_max():
    with pytest.raises(ValidationError, match="min"):
        WorkloadConfig.model_validate({**VALID, "autoscaling": {"min": 5, "max": 1}})


def test_unknown_model_is_rejected():
    with pytest.raises(ValidationError, match="unknown model"):
        WorkloadConfig.model_validate({**VALID, "model": "gpt-9"})


def test_memory_below_model_minimum_is_rejected():
    with pytest.raises(ValidationError, match="requires at least"):
        WorkloadConfig.model_validate({**VALID, "memory": "256Mi"})


def test_unknown_environment_is_rejected():
    with pytest.raises(ValidationError):
        WorkloadConfig.model_validate({**VALID, "environment": "prod-eu"})


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        WorkloadConfig.model_validate({**VALID, "replicas": 3})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("500m", 0.5), ("2", 2.0), (1, 1.0), (1.5, 1.5), ("250m", 0.25)],
)
def test_parse_cpu(raw, expected):
    assert parse_cpu(raw) == expected


@pytest.mark.parametrize("raw", ["0", "-1", "abc", "1.5m", 0])
def test_parse_cpu_rejects_invalid(raw):
    with pytest.raises(ValueError):
        parse_cpu(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("8Gi", 8 * 1024**3),
        ("512Mi", 512 * 1024**2),
        ("1G", 10**9),
        ("1500M", 1500 * 10**6),
        ("1024Ki", 1024**2),
    ],
)
def test_parse_memory(raw, expected):
    assert parse_memory(raw) == expected


@pytest.mark.parametrize("raw", ["8", "8GB", "Gi", "-1Gi", "0Gi", ""])
def test_parse_memory_rejects_invalid(raw):
    with pytest.raises(ValueError):
        parse_memory(raw)
