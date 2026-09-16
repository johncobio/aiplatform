from dataclasses import dataclass
from typing import Protocol

from llm_service.schemas import Message


@dataclass(frozen=True)
class Generation:
    text: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str = "stop"


class Backend(Protocol):
    """A model runtime. `load` may be slow and runs once at startup."""

    model_name: str

    def load(self) -> None: ...

    def generate(
        self, messages: list[Message], max_tokens: int, temperature: float
    ) -> Generation: ...
