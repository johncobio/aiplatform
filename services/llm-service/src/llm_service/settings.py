"""Runtime configuration, read from environment variables with the LLM_ prefix."""

import os
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")

    backend: Literal["mock", "llamacpp"] = "mock"
    model_name: str = "mock-model"
    model_url: str = Field("", description="GGUF download URL (llamacpp backend)")
    model_dir: str = Field("./models", description="Where model files are cached")
    model_path: str = Field("", description="Explicit model file; overrides model_url")
    context_length: int = Field(4096, ge=256, le=131072)
    threads: int = Field(default_factory=lambda: max(1, os.cpu_count() or 1), ge=1)
    max_concurrency: int = Field(1, ge=1, description="Parallel generations; llama.cpp wants 1")
    max_tokens_limit: int = Field(1024, ge=1, description="Upper bound a client may request")
    default_max_tokens: int = Field(256, ge=1)
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    # PORT is intentionally un-prefixed: it is the conventional container variable.
    port: int = Field(default_factory=lambda: int(os.environ.get("PORT", "8000")), ge=1, le=65535)
