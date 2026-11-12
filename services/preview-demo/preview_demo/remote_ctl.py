"""Operator bridge between the hosted request portal and the saved Terraform plan."""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import urlopen

from .intent import interpret
from .terraform_runner import REPO, RunnerError, Workspace
from .workflow import DemoError, parse_request

REGION = "us-east-2"
FUNCTION = "aiplatform-remote-preview"
BASE = REPO / ".aiplatform/remote-preview-runner"


def portal_origin(value: str) -> str:
    url = urlsplit(value)
    domain = r"[a-z0-9]+\.execute-api\.us-east-2\.amazonaws\.com"
    if (
        url.scheme != "https"
        or not re.fullmatch(domain, url.netloc)
        or url.path not in ("", "/")
        or url.query
        or url.fragment
    ):
        raise RunnerError("Use the portal's Ohio API Gateway HTTPS URL without an invite.")
    return f"https://{url.netloc}"


def fetch_portal(url):
    try:
        with urlopen(url, timeout=12) as result:
            return result.status, result.read(16_384)
    except HTTPError as error:
        return error.code, error.read(16_384)


def probe_portal(url, *, fetch=fetch_portal, pause=time.sleep):
    origin = portal_origin(url)
    checks = (
        ("/", 200, b"Request an AWS preview"),
        ("/app.js", 200, b"/api/request"),
        ("/api/request", 401, b"Open your private invite link."),
    )
    for path, expected, marker in checks:
        for attempt in range(5):
            try:
                code, body = fetch(origin + path)
            except OSError as error:
                reason = f"{type(error).__name__}: {error}"
            else:
                if code == expected and marker in body:
                    break
                reason = f"unexpected HTTP {code} response"
                if code < 500 and code not in (403, 404, 429):
                    raise RunnerError(f"Portal probe {path}: {reason}.")
            if attempt == 4:
                raise RunnerError(f"Portal probe {path} did not recover: {reason}.")
            pause(2)


class Operator:
    def __init__(self, function: str):
        self.function = function

    @staticmethod
    def aws(*args: str) -> str:
        result = subprocess.run(
            ["aws", *args, "--region", REGION, "--no-cli-pager", "--output", "json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=35,
        )
        return result.stdout

    def request(self, action, **values):
        event = json.dumps({"action": action, **values})
        with TemporaryDirectory(prefix="preview-portal-") as temp:
            payload = Path(temp) / "payload.json"
            payload.write_text(event)
            response = Path(temp) / "response.json"
            result = json.loads(
                self.aws(
                    "lambda",
                    "invoke",
                    "--function-name",
                    self.function,
                    "--cli-binary-format",
                    "raw-in-base64-out",
                    "--payload",
                    f"fileb://{payload}",
                    str(response),
                )
            )
            if result.get("FunctionError"):
                raise RunnerError("The portal function returned an internal error.")
            data = json.loads(response.read_text())
        if "error" in data:
            raise RunnerError(data["error"])
        return data["result"]


def workspace_command(operator, args):
    receipt = args.receipt
    row = None if args.command == "destroy" else operator.request("inspect", receipt=receipt)
    if args.command == "inspect":
        print(
            json.dumps(
                {
                    key: row[key]
                    for key in ("status", "request", "version", "minutes")
                    if key in row
                },
                indent=2,
            )
        )
        return
    with Workspace("academy", base=BASE) as workspace:
        binding = workspace.path / "portal-binding"
        bound_to = binding.read_text() if binding.is_file() else None
        if args.command == "plan":
            if bound_to and bound_to != receipt:
                raise RunnerError("The preview slot is assigned to a different invite.")
            if row["status"] != "requested":
                raise RunnerError("Only a submitted request can be planned.")
            try:
                spec = (
                    interpret(row["request"])
                    if args.model_intent
                    else parse_request(row["request"])
                )
            except DemoError as error:
                if error.status != 503:
                    operator.request("reject", receipt=receipt)
                raise
            account = json.loads(operator.aws("sts", "get-caller-identity"))["Account"]
            digest, changes = workspace.plan(spec, row["source_ip"] + "/32", account)
            binding.write_text(receipt)
            operator.request(
                "plan", receipt=receipt, approval=digest, version=spec.version, minutes=spec.minutes
            )
            print(f"Version {spec.version} · {spec.minutes} minutes · guest IPv4 only")
            print("\n".join(changes))
            print(f"Approval SHA256: {digest}")
            return
        if bound_to != receipt:
            raise RunnerError("This workspace is not bound to that invite.")
        if args.command == "destroy":
            workspace.destroy()
            if not args.without_portal:
                operator.request("close", receipt=receipt)
            binding.unlink()
            print(
                "Preview destroyed; portal status was not updated."
                if args.without_portal
                else "Preview destroyed; request closed."
            )
            return
        if row["status"] != "planned" or not (
            args.approve == row["approval"] == workspace.digest()
        ):
            raise RunnerError("Approval does not match this invite's saved plan.")
        operator.request("start", receipt=receipt, approval=args.approve)
        try:
            result = workspace.apply(args.approve)
            operator.request("available", receipt=receipt, endpoint=result["endpoint"])
        except Exception:
            try:
                operator.request("fail", receipt=receipt)
            except (RunnerError, OSError, ValueError, subprocess.SubprocessError):
                print(
                    "Could not update portal failure status. Check the workspace.", file=sys.stderr
                )
            raise
        print("AWS endpoint sent to the guest. Ask them to confirm the form opens.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--function", default=FUNCTION)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("invite", "probe"):
        commands.add_parser(command).add_argument("portal_url")
    for command in ("inspect", "plan", "apply", "destroy"):
        sub = commands.add_parser(command)
        sub.add_argument("receipt")
        if command == "plan":
            sub.add_argument("--model-intent", action="store_true")
        if command == "apply":
            sub.add_argument("--approve", required=True)
        if command == "destroy":
            sub.add_argument(
                "--without-portal",
                action="store_true",
                help="Recover only the bound Terraform workspace",
            )
    args = parser.parse_args()
    operator = Operator(args.function)
    try:
        if args.command == "probe":
            probe_portal(args.portal_url)
            print("Verified HTTPS page, JavaScript, and unauthenticated request denial.")
        elif args.command == "invite":
            origin = portal_origin(args.portal_url)
            result = operator.request("invite")
            print(f"Tester link: {origin}/#{result['token']}")
            print(f"Private operator receipt: {result['receipt']}")
        else:
            workspace_command(operator, args)
    except (RunnerError, DemoError, OSError, ValueError, subprocess.SubprocessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(f"AWS CLI command failed (exit {error.returncode}).", file=sys.stderr)
        else:
            print(str(error), file=sys.stderr)
        if args.command == "apply":
            print(
                "Check the workspace and run destroy for this receipt if apply started.",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
