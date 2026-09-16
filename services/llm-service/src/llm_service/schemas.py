"""OpenAI-compatible request/response shapes (the subset we support)."""

import time
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")  # clients send many optional fields

    model: str | None = None
    messages: list[Message] = Field(min_length=1)
    max_tokens: int | None = Field(None, ge=1)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    stream: bool = False


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Choice(BaseModel):
    index: int = 0
    message: Message
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:24]}")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[Choice]
    usage: Usage


class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    owned_by: str = "aiplatform"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard]
