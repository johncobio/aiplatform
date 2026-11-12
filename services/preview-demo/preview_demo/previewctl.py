"""Plan, apply, verify or destroy a fixed preview deployment."""

import argparse
import http.client
import ipaddress
import json
import logging
import sys
import time
from urllib.parse import urlencode, urlsplit

from .intent import interpret
from .terraform_runner import RunnerError, Workspace
from .workflow import DemoError, parse_request

LOG = logging.getLogger(__name__)


def verify_form(host: str, version: int, *, port: int = 8000) -> None:
    started = time.monotonic()
    cases = (
        ("not-an-email", "Rejected the input." if version == 2 else "Accepted the input."),
        ("student@example.com", "Accepted the input."),
    )
    for label, (email, expected) in zip(("invalid", "valid"), cases, strict=True):
        connection = http.client.HTTPConnection(host, port, timeout=4)
        try:
            connection.request(
                "POST",
                "/",
                body=urlencode({"email": email}),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response = connection.getresponse()
            marker = f'<p role="status">{expected}</p>'.encode()
            if response.status != 200 or marker not in response.read(8192):
                raise RunnerError(f"verify: unexpected result for the {label} form input.")
        except (OSError, http.client.HTTPException) as error:
            raise RunnerError(f"verify: {label} form request failed: {error}") from error
        finally:
            connection.close()
    LOG.info("verify: both sample form checks passed in %.2fs", time.monotonic() - started)


def verify(result: dict, seconds: float = 120) -> None:
    endpoint = urlsplit(result["endpoint"])
    try:
        host = str(ipaddress.IPv4Address(endpoint.hostname or ""))
        if endpoint.geturl() != f"http://{host}:8000":
            raise ValueError("unexpected endpoint")
    except ValueError as error:
        raise RunnerError("verify: expected an IPv4 endpoint on port 8000.") from error
    deadline = time.monotonic() + seconds
    started = time.monotonic()
    LOG.info("verify: waiting for the expected version at /readyz")
    while True:
        connection = http.client.HTTPConnection(host, 8000, timeout=4)
        try:
            connection.request("GET", "/readyz")
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError(f"HTTP {response.status}")
            payload = json.loads(response.read(2048))
            if payload == {"ready": True, "version": result["version"]}:
                LOG.info("verify: ready in %.2fs", time.monotonic() - started)
                break
            raise ValueError("readiness response did not report the expected version")
        except (OSError, ValueError, http.client.HTTPException) as error:
            if time.monotonic() >= deadline:
                raise RunnerError(
                    f"verify: {error}. Check CIDR and EC2 console boot logs."
                ) from error
        finally:
            connection.close()
        time.sleep(2)
    verify_form(host, result["version"])


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("local", "academy"), default="local")
    commands = parser.add_subparsers(dest="stage", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("request", help='Example: "Deploy version 2 for 15 minutes."')
    plan.add_argument("--operator-cidr", help="Public IPv4 /32 for the Academy demo")
    plan.add_argument("--account-id", help="Intended Academy account returned by STS")
    plan.add_argument("--model-intent", action="store_true", help="Interpret using local Ollama")
    apply = commands.add_parser("apply")
    apply.add_argument("--approve", required=True, help="SHA256 printed by the reviewed plan")
    apply.add_argument(
        "--skip-verify", action="store_true", help="Verify from the allowed IP later"
    )
    commands.add_parser("verify")
    commands.add_parser("destroy")
    args = parser.parse_args()
    try:
        with Workspace(args.target) as workspace:
            if args.stage == "plan":
                spec = interpret(args.request) if args.model_intent else parse_request(args.request)
                digest, changes = workspace.plan(spec, args.operator_cidr, args.account_id)
                print(f"{args.target}: version {spec.version} for {spec.minutes} minutes")
                if args.operator_cidr:
                    print(f"Inbound: TCP 8000 from {args.operator_cidr} only")
                for change in changes:
                    print(f"  {change}")
                print(f"Approval SHA256: {digest}")
            elif args.stage == "destroy":
                workspace.destroy()
                print("No managed resources remain in this Terraform state.")
            else:
                result = (
                    workspace.apply(args.approve) if args.stage == "apply" else workspace.output()
                )
                print(json.dumps(result, indent=2), flush=True)
                if args.target == "academy" and not getattr(args, "skip_verify", False):
                    verify(result)
                    print("Verified: remote version and both synthetic form responses.")
                elif args.target == "academy":
                    print("Applied; readiness not checked. Verify from the allowed IP.")
                else:
                    print("Local Terraform result only; no remote endpoint was created.")
    except (RunnerError, DemoError, OSError, ValueError) as error:
        print(f"{args.stage} failed: {error}", file=sys.stderr)
        if args.stage in {"apply", "verify", "destroy"}:
            print(
                f"Preserve local state. Use --target {args.target} destroy for cleanup.",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
