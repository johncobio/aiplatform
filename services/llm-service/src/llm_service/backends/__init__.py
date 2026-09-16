from llm_service.backends.base import Backend, Generation
from llm_service.settings import Settings


def build_backend(settings: Settings) -> Backend:
    """Instantiate the backend named in settings. Imports lazily so the mock
    backend never needs llama.cpp installed."""
    if settings.backend == "mock":
        from llm_service.backends.mock import MockBackend

        return MockBackend(model_name=settings.model_name)
    if settings.backend == "llamacpp":
        from llm_service.backends.llamacpp import LlamaCppBackend

        return LlamaCppBackend(settings)
    raise ValueError(f"unknown backend {settings.backend!r}")


__all__ = ["Backend", "Generation", "build_backend"]
