import pytest
from fastapi.testclient import TestClient

from llm_service.app import create_app
from llm_service.settings import Settings


@pytest.fixture
def settings():
    return Settings(backend="mock", model_name="mock-model", max_tokens_limit=64, log_format="text")


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        app.state.engine.wait_until_settled(timeout=5)
        yield c
