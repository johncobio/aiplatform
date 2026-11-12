"""Operator-only Terraform commands. The web app does not import this module."""

import fcntl
import hashlib
import ipaddress
import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

from .workflow import Spec

REPO = Path(__file__).resolve().parents[3]
LOG = logging.getLogger(__name__)
INGRESS = "aws_vpc_security_group_ingress_rule.preview"
EXPECTED = {
    "local": {"terraform_data.preview"},
    "academy": {
        "aws_instance.academy_demo",
        "aws_security_group.preview",
        INGRESS,
    },
}


class RunnerError(Exception):
    """A failure the operator can act on."""


def public_unicast(cidr: str | None) -> ipaddress.IPv4Network:
    try:
        network = ipaddress.IPv4Network(cidr or "")
        address = network.network_address
        if network.prefixlen == 32 and address.is_global and not address.is_multicast:
            return network
    except ValueError:
        pass
    raise RunnerError("Academy requires your current public IPv4 /32.")


class Workspace:
    def __init__(self, target: str, *, base: Path = REPO / ".aiplatform/preview-terraform"):
        if target not in EXPECTED:
            raise RunnerError("Unknown Terraform target.")
        self.target = target
        self.path = base / target
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.saved_plan = self.path / "preview.tfplan"
        self.pending = self.path / "apply.pending"
        self._lock = None

    def __enter__(self):
        lock = (self.path / "operator.lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            lock.close()
            raise RunnerError("Another operator command is already running.") from error
        self._lock = lock
        return self

    def __exit__(self, *_exc):
        self._lock.close()

    def run(self, stage: str, *args: str) -> str:
        # A shell, user-supplied Terraform flags, workspace overrides and CLI config
        # do not participate in the deployment contract.
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("TF_")
            and (self.target == "academy" or not key.startswith("AWS_"))
        }
        config = self.path / "cli.tfrc"
        config.write_text("")
        env.update(
            TF_IN_AUTOMATION="1", TF_WORKSPACE="default", TF_CLI_CONFIG_FILE=str(config.resolve())
        )
        started = time.monotonic()
        LOG.info("%s: %s started", self.target, stage)
        try:
            result = subprocess.run(
                ["terraform", *args],
                cwd=self.path,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RunnerError(f"{stage}: could not complete terraform: {error}") from error
        if result.returncode:
            details = (result.stderr.strip() or result.stdout.strip())[-3500:]
            raise RunnerError(f"{stage}: Terraform exited {result.returncode}.\n{details}")
        LOG.info("%s: %s finished in %.2fs", self.target, stage, time.monotonic() - started)
        return result.stdout

    def has_resources(self) -> bool:
        if any(self.path.glob("terraform.tfstate.d/*/terraform.tfstate")):
            raise RunnerError("Unexpected non-default Terraform state. Preserve it for recovery.")
        state = self.path / "terraform.tfstate"
        if not state.exists():
            return False
        try:
            return any(
                resource["mode"] == "managed" and resource["instances"]
                for resource in json.loads(state.read_text())["resources"]
            )
        except (ValueError, KeyError, TypeError) as error:
            raise RunnerError(
                "Could not read Terraform state. Preserve it for recovery."
            ) from error

    def plan(
        self, spec: Spec, cidr: str | None = None, account: str | None = None
    ) -> tuple[str, list[str]]:
        if self.has_resources():
            raise RunnerError("This slot already owns resources. Run destroy before a new plan.")
        self.check_no_pending()
        values = {f"preview_{key}": value for key, value in asdict(spec).items()}
        if self.target == "academy":
            if not re.fullmatch(r"[0-9]{12}", account or ""):
                raise RunnerError("Academy requires the intended lab account ID from STS.")
            values["operator_cidr"] = str(public_unicast(cidr))
            values["expected_account_id"] = account
        elif cidr is not None or account is not None:
            raise RunnerError("The local target does not use a CIDR or AWS account.")
        self.saved_plan.unlink(missing_ok=True)
        source = REPO / "infra/terraform/environments" / f"preview-{self.target}"
        for pattern in ("*.tf", "*.tftpl", "sample.py", ".terraform.lock.hcl"):
            for path in source.glob(pattern):
                shutil.copyfile(path, self.path / path.name)
        (self.path / "preview.auto.tfvars.json").write_text(json.dumps(values))
        lock_flag = ["-lockfile=readonly"] if self.target == "academy" else []
        self.run("init", "init", "-input=false", "-no-color", *lock_flag)
        self.run("validate", "validate", "-no-color")
        try:
            self.run("plan", "plan", "-input=false", "-no-color", f"-out={self.saved_plan.name}")
            changes = self.inspect_plan(self.saved_plan, "create")
        except Exception:
            self.saved_plan.unlink(missing_ok=True)
            raise
        return self.digest(), changes

    def inspect_plan(self, plan: Path, action: str) -> list[str]:
        details = json.loads(self.run("inspect plan", "show", "-json", plan.name))
        changes = {}
        for change in details.get("resource_changes", []):
            if change["mode"] != "managed" or change["change"]["actions"] == ["no-op"]:
                continue
            address = change["address"]
            if address not in EXPECTED[self.target] or change["change"]["actions"] != [action]:
                raise RunnerError(f"Unexpected planned action for {address}. Plan rejected.")
            if action == "create" and address == INGRESS:
                rule = change["change"]["after"]
                cidr = details.get("variables", {}).get("operator_cidr", {}).get("value")
                if (
                    rule.get("cidr_ipv4") != str(public_unicast(cidr))
                    or rule.get("ip_protocol") != "tcp"
                    or rule.get("from_port") != 8000
                    or rule.get("to_port") != 8000
                ):
                    raise RunnerError("Unexpected planned ingress. Plan rejected.")
            changes[address] = action
        if action == "create" and changes.keys() != EXPECTED[self.target]:
            raise RunnerError("Plan did not create the complete approved pattern.")
        return [f"{address}: {change}" for address, change in sorted(changes.items())]

    def digest(self) -> str:
        if not self.saved_plan.is_file():
            raise RunnerError("No saved plan. Run plan and review its summary first.")
        return hashlib.sha256(self.saved_plan.read_bytes()).hexdigest()

    def apply(self, approval: str) -> dict:
        if self.has_resources():
            raise RunnerError("This slot already owns resources. Run destroy before applying.")
        self.check_no_pending()
        if approval != self.digest():
            raise RunnerError("Approval does not match the saved plan. Review a fresh plan.")
        self.inspect_plan(self.saved_plan, "create")
        self.pending.touch(exist_ok=False)
        self.run("apply", "apply", "-input=false", "-no-color", self.saved_plan.name)
        if not self.has_resources():
            raise RunnerError("Apply completed without managed state. Preserve the workspace.")
        self.pending.unlink()
        self.saved_plan.unlink()
        return self.output()

    def output(self) -> dict:
        return json.loads(self.run("output", "output", "-json", "preview"))

    def destroy(self) -> None:
        self.saved_plan.unlink(missing_ok=True)
        if not self.has_resources():
            self.check_no_pending()
            return
        cleanup = self.path / "cleanup.tfplan"
        try:
            self.run(
                "destroy plan",
                "plan",
                "-destroy",
                "-input=false",
                "-no-color",
                f"-out={cleanup.name}",
            )
            self.inspect_plan(cleanup, "delete")
            self.run("destroy apply", "apply", "-input=false", "-no-color", cleanup.name)
            if self.has_resources():
                raise RunnerError("Managed state remains after destroy. Inspect before retrying.")
            self.pending.unlink(missing_ok=True)
        finally:
            cleanup.unlink(missing_ok=True)

    def check_no_pending(self) -> None:
        if self.pending.exists():
            raise RunnerError(
                "An unresolved apply may have created resources. Preserve the workspace "
                "and follow the recovery steps in docs/final/PREVIEW_AWS.md."
            )
