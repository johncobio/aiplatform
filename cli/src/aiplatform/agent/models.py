from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FileChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(description="Repository-relative path, e.g. services/demo/aiplatform.yaml")
    action: Literal["write", "delete"] = "write"
    content: str | None = Field(None, description="Full new file content for action=write")


class Proposal(BaseModel):
    """What the agent proposes. It is applied to a scratch branch, never to main."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="One line, imperative, suitable as a PR title")
    rationale: str = Field(description="Why these changes satisfy the request, in Markdown")
    files: list[FileChange] = Field(min_length=1)
    risks: list[str] = Field(
        default_factory=list, description="What a reviewer should double-check"
    )
