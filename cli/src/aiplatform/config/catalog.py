"""Model catalog: what the platform knows how to serve, and what it needs.

The catalog turns a friendly `model:` name into an artifact plus minimum
resources so configuration errors surface at validation time, not at 2am.
"""

from dataclasses import dataclass

from aiplatform.config.quantity import parse_memory
from aiplatform.errors import ConfigError


@dataclass(frozen=True)
class ModelSpec:
    name: str
    backend: str  # "llamacpp" (CPU, GGUF) | "vllm" (GPU, V6)
    parameters_b: float
    min_memory_bytes: int
    artifact_url: str = ""  # GGUF download URL for llamacpp
    context_length: int = 4096
    requires_gpu: bool = False
    hf_repo: str = ""  # model repo id for vLLM

    @property
    def filename(self) -> str:
        return self.artifact_url.rsplit("/", 1)[-1]


_HF = "https://huggingface.co"

CATALOG: dict[str, ModelSpec] = {
    "qwen2.5-0.5b-instruct": ModelSpec(
        name="qwen2.5-0.5b-instruct",
        backend="llamacpp",
        parameters_b=0.5,
        min_memory_bytes=parse_memory("1Gi"),
        artifact_url=f"{_HF}/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/"
        "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        context_length=4096,
    ),
    "qwen2.5-1.5b-instruct": ModelSpec(
        name="qwen2.5-1.5b-instruct",
        backend="llamacpp",
        parameters_b=1.5,
        min_memory_bytes=parse_memory("2560Mi"),
        artifact_url=f"{_HF}/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
        "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        context_length=4096,
    ),
    "llama-3.1-8b-instruct": ModelSpec(
        name="llama-3.1-8b-instruct",
        backend="vllm",
        parameters_b=8,
        min_memory_bytes=parse_memory("16Gi"),
        requires_gpu=True,
        hf_repo="meta-llama/Llama-3.1-8B-Instruct",
        context_length=8192,
    ),
}


def get_model(name: str) -> ModelSpec:
    try:
        return CATALOG[name]
    except KeyError:
        available = ", ".join(sorted(CATALOG))
        raise ConfigError(f"unknown model {name!r}; available: {available}") from None
