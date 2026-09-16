"""Proposal providers: Claude (Messages API, structured output) or a JSON file.

The provider only produces a Proposal; every safety decision happens in the
guardrail pipeline afterwards, so a provider can be swapped or faked freely.
"""

import json
import logging
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from aiplatform.agent.models import Proposal
from aiplatform.errors import AgentError

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the infrastructure agent for `aiplatform`, an internal developer \
platform that deploys LLM workloads to Kubernetes with Terraform, Helm and Argo CD.

You propose file changes; you never apply them. Every proposal goes through terraform \
fmt/validate/plan, Checkov, OPA policies, a cost estimate against a budget, and a human \
review on a pull request. Propose the smallest change that satisfies the request.

Rules:
- Only change files under services/*/aiplatform.yaml, deploy/workloads/, \
deploy/environments/, deploy/helm/llm-workload/values.yaml or infra/terraform/. Never \
touch .github/, policy/, secrets, or CI configuration.
- Respect the platform policy limits and price table in the context; state the estimated \
monthly cost in the rationale and how it fits the budget.
- Use models from the catalog only. GPU models require engine vllm and cannot run on kind.
- Prefer Graviton instance types; never add NAT gateways or open 0.0.0.0/0 ingress.
- Return complete file contents (not diffs) for every file you write.
"""


class Provider(Protocol):
    name: str

    def propose(self, request: str, context: str) -> Proposal: ...


class FileProvider:
    """Reads a Proposal from JSON: tests, demos, or a hand-written plan reviewed offline."""

    name = "file"

    def __init__(self, path: Path) -> None:
        self.path = path

    def propose(self, request: str, context: str) -> Proposal:
        try:
            return Proposal.model_validate(json.loads(self.path.read_text()))
        except (OSError, ValueError, ValidationError) as e:
            raise AgentError(f"invalid proposal file {self.path}: {e}") from None


class ClaudeProvider:
    """Asks Claude for a structured Proposal via the Anthropic Messages API."""

    name = "claude"

    def __init__(self, client=None, model: str = "claude-opus-5", effort: str = "high") -> None:
        if client is None:
            import anthropic  # resolved from ANTHROPIC_API_KEY or an `ant auth login` profile

            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.effort = effort

    def propose(self, request: str, context: str) -> Proposal:
        import anthropic

        user = (
            f"Request from the platform user:\n\n{request}\n\n"
            f"<repository-context>\n{context}\n</repository-context>"
        )
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user}],
                output_format=Proposal,
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
            )
        except anthropic.AuthenticationError:
            raise AgentError(
                "no Anthropic credentials: set ANTHROPIC_API_KEY or run `ant auth login`, "
                "or use --from-file"
            ) from None
        except anthropic.RateLimitError as e:
            raise AgentError(f"rate limited by the Anthropic API: {e.message}") from None
        except anthropic.APIStatusError as e:
            raise AgentError(f"Anthropic API error {e.status_code}: {e.message}") from None
        except anthropic.APIConnectionError as e:
            raise AgentError(f"cannot reach the Anthropic API: {e}") from None
        if response.stop_reason == "refusal":
            raise AgentError("the model declined to propose changes for this request")
        if response.stop_reason == "max_tokens":
            raise AgentError("proposal was truncated (max_tokens); narrow the request")
        proposal = response.parsed_output
        if proposal is None:
            raise AgentError("the model returned no structured proposal")
        usage = getattr(response, "usage", None)
        if usage is not None:
            log.info("claude usage input=%s output=%s", usage.input_tokens, usage.output_tokens)
        return proposal
