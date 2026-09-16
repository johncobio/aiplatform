"""llama.cpp backend: CPU inference from a GGUF file via llama-cpp-python."""

import logging
from pathlib import Path

from llm_service.backends.base import Generation
from llm_service.model_store import ensure_model
from llm_service.schemas import Message
from llm_service.settings import Settings

log = logging.getLogger(__name__)


class LlamaCppBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_name = settings.model_name
        self._llm = None

    def load(self) -> None:
        from llama_cpp import Llama  # heavy import; only when this backend is used

        if self.settings.model_path:
            path = Path(self.settings.model_path)
            if not path.is_file():
                raise FileNotFoundError(f"LLM_MODEL_PATH does not exist: {path}")
        elif self.settings.model_url:
            path = ensure_model(self.settings.model_url, Path(self.settings.model_dir))
        else:
            raise ValueError("llamacpp backend needs LLM_MODEL_PATH or LLM_MODEL_URL")

        log.info("loading model %s from %s", self.model_name, path)
        self._llm = Llama(
            model_path=str(path),
            n_ctx=self.settings.context_length,
            n_threads=self.settings.threads,
            n_batch=512,
            verbose=False,
        )

    def generate(self, messages: list[Message], max_tokens: int, temperature: float) -> Generation:
        if self._llm is None:
            raise RuntimeError("model not loaded")
        out = self._llm.create_chat_completion(
            messages=[m.model_dump() for m in messages],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = out["choices"][0]
        usage = out.get("usage", {})
        return Generation(
            text=choice["message"].get("content") or "",
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            finish_reason=choice.get("finish_reason") or "stop",
        )
