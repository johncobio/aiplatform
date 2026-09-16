"""`python -m llm_service` runs the server with settings from the environment."""

import uvicorn

from llm_service.settings import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "llm_service.app:create_app",
        factory=True,
        host="0.0.0.0",  # noqa: S104 - container-internal bind; the platform controls exposure
        port=settings.port,
        log_config=None,  # our JSON logging is configured in create_app
        access_log=False,  # we log requests ourselves with request ids
    )


if __name__ == "__main__":
    main()
