"""Start one local demo process and print its private operator link."""

import argparse
import secrets
import socket

import uvicorn

from .app import create_app
from .intent import interpret


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model-intent", action="store_true", help="Use the local Ollama model")
    args = parser.parse_args()
    host = "127.0.0.1"
    token = secrets.token_urlsafe(32)
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((host, args.port))
        except (OSError, OverflowError) as error:
            parser.error(f"cannot listen on port {args.port}: {error}")
        listener.listen(128)
        port = listener.getsockname()[1]
        print(
            f"Local simulation. Private operator link: http://{host}:{port}/operator#{token}",
            flush=True,
        )
        config = uvicorn.Config(
            create_app(
                token,
                allowed_hosts=(host, "localhost"),
                interpreter=interpret if args.model_intent else None,
            ),
            access_log=False,
        )
        uvicorn.Server(config).run(sockets=[listener])


if __name__ == "__main__":
    main()
