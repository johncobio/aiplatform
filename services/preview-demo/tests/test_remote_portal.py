import copy
import json
from argparse import Namespace
from decimal import Decimal

import pytest

from preview_demo import remote_ctl
from preview_demo.terraform_runner import RunnerError
from remote_portal import handler
from remote_portal.handler import DynamoStore, Portal


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def get(self, key):
        return copy.deepcopy(self.rows.get(key))

    def put(self, row, expected=None):
        key = row["key"]
        current = self.rows.get(key)
        if (current or {}).get("revision") != expected:
            return False
        self.rows[key] = copy.deepcopy(row)
        return True


def test_lambda_can_serve_static_pages_without_initializing_dynamodb(monkeypatch):
    def unexpected():
        pytest.fail("Static routes should not initialize a table client.")

    monkeypatch.setattr(handler, "live_portal", unexpected)
    response = handler.lambda_handler(
        {"version": "2.0", "rawPath": "/", "requestContext": {"http": {"method": "GET"}}},
        None,
    )
    assert response["statusCode"] == 200
    assert "Request an AWS preview" in response["body"]


def test_portal_probe_retries_raw_read_timeout_and_gateway_error():
    attempts = iter(
        [
            TimeoutError("read timed out"),
            (503, b""),
            (200, b"Request an AWS preview"),
            (200, b"/api/request"),
            (401, b'{"error":"Open your private invite link."}'),
        ]
    )
    seen = []

    def fetch(url):
        seen.append(url.rsplit("/", 1)[-1])
        result = next(attempts)
        if isinstance(result, Exception):
            raise result
        return result

    remote_ctl.probe_portal(
        "https://test.execute-api.us-east-2.amazonaws.com", fetch=fetch, pause=lambda _seconds: None
    )
    assert seen == ["", "", "", "app.js", "request"]


def guest(portal, token, method="GET", body=None, ip="8.8.8.8", path="/api/request"):
    response = portal.handle(
        {
            "version": "2.0",
            "rawPath": path,
            "requestContext": {"http": {"method": method, "sourceIp": ip}},
            "headers": {"authorization": f"Bearer {token}", "x-forwarded-for": "1.1.1.1"},
            "body": json.dumps(body) if body is not None else None,
            "action": "invite",  # Top-level HTTP event must never enter the operator path.
        }
    )
    return response["statusCode"], json.loads(response["body"])


def test_instant_invite_opens_without_review_and_never_becomes_a_plan():
    clock = [1000]
    portal = Portal(MemoryStore(), clock=lambda: clock[0])
    issued = portal.handle({"action": "invite", "instant": True})["result"]
    token = issued["token"]
    receipt = issued["receipt"]
    clock[0] += 10 * 60  # Preparation time does not consume the preview window.
    assert guest(portal, token)[1]["status"] == "demo_ready"
    assert "error" in portal.handle({"action": "start", "receipt": receipt})
    assert guest(portal, token, "POST", {"request": "Deploy version 2 for 15 minutes."})[0] == 409
    assert guest(portal, token, "POST", {"email": "not-an-email"}, path="/api/demo") == (
        200,
        {"version1": True, "version2": False},
    )
    assert guest(portal, token, "POST", {"email": "student@example.com"}, path="/api/demo") == (
        200,
        {"version1": True, "version2": True},
    )
    assert (
        guest(portal, token, "POST", {"email": "not-an-email"}, ip="1.1.1.1", path="/api/demo")[0]
        == 403
    )
    assert "email" not in json.dumps(portal.store.rows)
    clock[0] += 15 * 60
    assert guest(portal, token)[1]["status"] == "expired"
    assert guest(portal, token, "POST", {"email": "not-an-email"}, path="/api/demo")[0] == 410


def test_regular_invite_cannot_open_instant_demo():
    portal = Portal(MemoryStore())
    token = portal.handle({"action": "invite"})["result"]["token"]
    assert guest(portal, token, "POST", {"email": "not-an-email"}, path="/api/demo")[0] == 403


def test_remote_handoff_and_expiry():
    time = [1000]
    portal = Portal(MemoryStore(), clock=lambda: time[0])
    invite = portal.handle({"action": "invite"})["result"]
    token, receipt = invite["token"], invite["receipt"]
    assert guest(portal, token)[1]["status"] == "invited"
    assert (
        guest(portal, token, "POST", {"request": "Test the updated form for 15 minutes."})[0] == 201
    )
    assert guest(portal, token, "POST", {"request": "Try again."})[0] == 409
    assert guest(portal, token, ip="1.1.1.1")[0] == 403
    record = portal.handle({"action": "inspect", "receipt": receipt})["result"]
    assert record["source_ip"] == "8.8.8.8"
    assert token not in json.dumps(portal.store.rows)
    assert "source_ip" not in guest(portal, token)[1]
    assert "error" in portal.handle({"action": "available", "receipt": receipt})
    portal.handle(
        {"action": "plan", "receipt": receipt, "version": 2, "minutes": 15, "approval": "a" * 64}
    )
    assert guest(portal, token)[1]["status"] == "planned"
    assert "approval" not in guest(portal, token)[1]
    assert "error" in portal.handle({"action": "start", "receipt": receipt, "approval": "b" * 64})
    assert portal.handle({"action": "start", "receipt": receipt, "approval": "a" * 64})["result"]
    assert "error" in portal.handle(
        {"action": "available", "receipt": receipt, "endpoint": "https://example.com/"}
    )
    portal.handle({"action": "available", "receipt": receipt, "endpoint": "http://1.1.1.1:8000"})
    assert guest(portal, token)[1]["endpoint"] == "http://1.1.1.1:8000"
    time[0] += 901
    assert guest(portal, token)[1]["status"] == "expired"
    assert "endpoint" not in guest(portal, token)[1]
    assert portal.handle({"action": "close", "receipt": receipt})["result"]["status"] == "closed"


def test_bad_invite_and_source_never_queue_work():
    time = [1000]
    portal = Portal(MemoryStore(), clock=lambda: time[0])
    invite = portal.handle({"action": "invite"})["result"]
    token = invite["token"]
    assert guest(portal, invite["receipt"])[0] == 401
    assert guest(portal, token, "POST", {"request": "v2"}, ip="::1")[0] == 422
    assert guest(portal, token, "POST", {"request": "v2", "action": "start"})[0] == 422
    time[0] += 1800
    assert guest(portal, token, "POST", {"request": "v2"})[0] == 410


def test_dynamo_numbers_are_serializable():
    class Table:
        def get_item(self, **_kwargs):
            return {"Item": {"revision": Decimal(1), "version": Decimal(2)}}

    assert json.dumps(DynamoStore(Table()).get("test")) == '{"revision": 1, "version": 2}'


def test_operator_never_applies_with_a_different_hash(tmp_path, monkeypatch):
    class Workspace:
        path = tmp_path

        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def digest(self):
            return "a" * 64

        def apply(self, _approval):
            pytest.fail("must not apply a mismatched approval")

    class Operator:
        def request(self, action, **_values):
            assert action == "inspect", "must not even start the remote status transition"
            return {"status": "planned", "approval": "a" * 64}

    receipt = "f" * 64
    (tmp_path / "portal-binding").write_text(receipt)
    monkeypatch.setattr(remote_ctl, "Workspace", Workspace)
    with pytest.raises(RunnerError, match="does not match"):
        remote_ctl.workspace_command(
            Operator(), Namespace(command="apply", receipt=receipt, approve="b" * 64)
        )


def test_operator_publishes_only_after_exact_apply_and_closes_on_destroy(tmp_path, monkeypatch):
    portal = Portal(MemoryStore(), clock=lambda: 1000)
    invite = portal.handle({"action": "invite"})["result"]
    assert (
        guest(portal, invite["token"], "POST", {"request": "Deploy version 2 for 15 minutes."})[0]
        == 201
    )
    calls = []

    class Workspace:
        path = tmp_path

        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def plan(self, spec, cidr, _account):
            assert (spec.version, spec.minutes, cidr) == (2, 15, "8.8.8.8/32")
            calls.append("terraform plan")
            return self.digest(), ["aws_instance.academy_demo: create"]

        def digest(self):
            return "a" * 64

        def apply(self, approval):
            assert approval == self.digest()
            assert guest(portal, invite["token"])[1]["status"] == "applying"
            calls.append("terraform apply")
            return {"endpoint": "http://1.1.1.1:8000"}

        def destroy(self):
            calls.append("terraform destroy")

    class Operator:
        def request(self, action, **values):
            return portal.handle({"action": action, **values})["result"]

        def aws(self, *_args):
            return '{"Account":"000000000000"}'

    monkeypatch.setattr(remote_ctl, "Workspace", Workspace)
    operator = Operator()
    args = {
        "receipt": invite["receipt"],
        "model_intent": False,
        "approve": "a" * 64,
        "without_portal": False,
    }
    remote_ctl.workspace_command(operator, Namespace(command="plan", **args))
    assert "endpoint" not in guest(portal, invite["token"])[1]
    remote_ctl.workspace_command(operator, Namespace(command="apply", **args))
    assert guest(portal, invite["token"])[1]["endpoint"] == "http://1.1.1.1:8000"
    remote_ctl.workspace_command(operator, Namespace(command="destroy", **args))
    assert guest(portal, invite["token"])[1]["status"] == "closed"
    assert calls == ["terraform plan", "terraform apply", "terraform destroy"]
