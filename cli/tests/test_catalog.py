import pytest

from aiplatform.config.catalog import CATALOG, get_model
from aiplatform.errors import ConfigError


def test_every_entry_has_positive_memory_and_artifact():
    for spec in CATALOG.values():
        assert spec.min_memory_bytes > 0
        assert spec.artifact_url or spec.requires_gpu


def test_get_model_known():
    spec = get_model("qwen2.5-0.5b-instruct")
    assert spec.backend == "llamacpp"
    assert spec.artifact_url.endswith(".gguf")


def test_get_model_unknown_lists_available():
    with pytest.raises(ConfigError, match="qwen2.5-0.5b-instruct"):
        get_model("nope")


def test_large_model_requires_gpu():
    assert get_model("llama-3.1-8b-instruct").requires_gpu is True
