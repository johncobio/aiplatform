"""Deterministic backend for tests and CI: no weights, instant load."""

import time

from llm_service.backends.base import Generation
from llm_service.schemas import Message


class MockBackend:
    def __init__(self, model_name: str = "mock-model", latency_seconds: float = 0.0) -> None:
        self.model_name = model_name
        self.latency_seconds = latency_seconds

    def load(self) -> None:
        return None

    def generate(self, messages: list[Message], max_tokens: int, temperature: float) -> Generation:
        if self.latency_seconds:
            time.sleep(self.latency_seconds)
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        words = last_user.split()
        reply_words = ["echo:"] + words[:max_tokens]
        prompt_tokens = sum(len(m.content.split()) for m in messages)
        return Generation(
            text=" ".join(reply_words),
            prompt_tokens=prompt_tokens,
            completion_tokens=len(reply_words),
            finish_reason="length" if len(words) > max_tokens else "stop",
        )
