"""Separate public guest routes from direct, IAM-authorized operator invocations."""

import hashlib
import ipaddress
import json
import os
import re
import secrets
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from .demo_form import compare_versions

ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
SHA = re.compile(r"[a-f0-9]{64}")
DEMO_SECONDS = 15 * 60


class RequestError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def public_ipv4(value):
    try:
        address = ipaddress.IPv4Address(value)
        if address.is_global and not address.is_multicast:
            return str(address)
    except (ValueError, TypeError):
        pass
    raise RequestError(422, "Use a network with a public IPv4 address for this demo.")


def preview_endpoint(value):
    try:
        parsed = urlsplit(value)
        if parsed.geturl() == f"http://{public_ipv4(parsed.hostname)}:8000":
            return parsed.geturl()
    except (ValueError, TypeError, AttributeError, RequestError):
        pass
    raise RequestError(422, "Expected the preview's public IPv4 URL on port 8000.")


def response(status, value, content_type="application/json"):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": content_type,
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; connect-src 'self'; "
                "style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; "
                "form-action 'none'"
            ),
        },
        "body": json.dumps(value) if content_type == "application/json" else value,
    }


def static_asset(event, context):
    path = event.get("rawPath")
    if (
        event.get("version") == "2.0"
        and context.get("http", {}).get("method") == "GET"
        and path in ASSETS
    ):
        filename, media_type = ASSETS[path]
        return response(200, Path(__file__).with_name(filename).read_text(), media_type)
    return None


def guest_input(event, field):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded") or not isinstance(raw, str) or len(raw) > 2048:
        raise RequestError(422, "Send a short JSON request.")
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if not isinstance(data, dict) or set(data) != {field} or not isinstance(data[field], str):
        raise RequestError(422, f"Send one {field} field.")
    return data[field]


class Portal:
    def __init__(self, store, *, clock=time.time):
        self.store = store
        self.clock = clock

    def handle(self, event):
        http = event.get("requestContext")
        try:
            if http is not None:
                return self.guest(event, http)
            return {"result": self.operator(event)}
        except RequestError as error:
            if http is not None:
                return response(error.status, {"error": str(error)})
            return {"error": str(error), "status": error.status}

    def guest(self, event, context):
        if event.get("version") != "2.0":
            raise RequestError(404, "Route not found.")
        method = context.get("http", {}).get("method")
        path = event.get("rawPath")
        if asset := static_asset(event, context):
            return asset
        if (method, path) not in {
            ("GET", "/api/request"),
            ("POST", "/api/request"),
            ("POST", "/api/demo"),
        }:
            raise RequestError(404, "Route not found.")
        auth = (event.get("headers") or {}).get("authorization", "")
        token = auth.removeprefix("Bearer ")
        if auth == token or not TOKEN.fullmatch(token):
            raise RequestError(401, "Open your private invite link.")
        key = hashlib.sha256(token.encode()).hexdigest()
        row = self.store.get(key)
        now = int(self.clock())
        if not row:
            raise RequestError(401, "Invite not found. Ask the operator for a new one.")
        if row["expires_at"] <= now:
            raise RequestError(410, "This invite has expired.")
        source = context.get("http", {}).get("sourceIp")
        if row.get("source_ip") and row["source_ip"] != source:
            raise RequestError(403, "Use the same network that opened this preview.")
        if path == "/api/demo":
            if row["status"] != "demo_ready":
                raise RequestError(403, "Open an instant demo invite first.")
            if row["available_until"] <= now:
                raise RequestError(410, "This demo window has ended.")
            email = guest_input(event, "email")
            if len(email) > 254:
                raise RequestError(422, "Use a sample email of at most 254 characters.")
            return response(200, compare_versions(email))
        if method == "GET":
            if row["status"] == "demo_invited":
                if row["submit_by"] <= now:
                    raise RequestError(410, "This invite has expired.")
                self.change(
                    row,
                    status="demo_ready",
                    source_ip=public_ipv4(source),
                    available_until=now + DEMO_SECONDS,
                )
            return response(200, self.guest_view(row, now))
        if row["submit_by"] <= now:
            raise RequestError(410, "This invite is no longer accepting submissions.")
        if row["status"] != "invited":
            raise RequestError(409, "This invite already has a request.")
        request = guest_input(event, "request")
        if not 0 < len(request.strip()) <= 254:
            raise RequestError(422, "Enter a request of at most 254 characters.")
        if not request.isprintable():
            raise RequestError(422, "Enter your request on one line.")
        self.change(row, status="requested", request=request.strip(), source_ip=public_ipv4(source))
        return response(201, self.guest_view(row, now))

    @staticmethod
    def guest_view(row, now):
        result = {name: row[name] for name in ("status", "version", "minutes") if name in row}
        if row["status"] == "available":
            if row["available_until"] > now:
                result["endpoint"] = row["endpoint"]
            else:
                result["status"] = "expired"
        if row["status"] == "demo_ready" and row["available_until"] <= now:
            result["status"] = "expired"
        return result

    def change(self, row, **values):
        expected = row["revision"]
        row.update(revision=expected + 1, updated_at=int(self.clock()), **values)
        if not self.store.put(row, expected):
            raise RequestError(409, "The request changed. Reload and try again.")
        return row

    def operator(self, event):
        action = event.get("action")
        now = int(self.clock())
        if action == "invite":
            token = secrets.token_urlsafe(32)
            key = hashlib.sha256(token.encode()).hexdigest()
            row = {
                "key": key,
                "revision": 0,
                "status": "demo_invited" if event.get("instant") is True else "invited",
                "submit_by": now + 1800,
                "expires_at": now + 7200,
                "updated_at": now,
            }
            if not self.store.put(row):
                raise RequestError(409, "Could not reserve an invite. Try again.")
            return {"receipt": key, "token": token}
        key = event.get("receipt", "")
        if not isinstance(key, str) or not SHA.fullmatch(key):
            raise RequestError(422, "Invalid receipt.")
        row = self.store.get(key)
        if not row:
            raise RequestError(404, "Request not found.")
        if action == "inspect":
            return row
        transitions = {
            "plan": ("requested", "planned"),
            "start": ("planned", "applying"),
            "available": ("applying", "available"),
            "fail": ("applying", "failed"),
            "reject": ("requested", "rejected"),
        }
        if action == "close":
            return row if row["status"] == "closed" else self.change(row, status="closed")
        if action not in transitions or row["status"] != transitions[action][0]:
            raise RequestError(409, "This request cannot make that transition.")
        if action in {"plan", "start"} and row["expires_at"] <= now + 35 * 60:
            raise RequestError(410, "Not enough invite lifetime remains. Create a fresh invite.")
        details = {}
        if action == "plan":
            version, minutes, approval = (
                event.get(name) for name in ("version", "minutes", "approval")
            )
            if (
                type(version) is not int
                or version not in (1, 2)
                or type(minutes) is not int
                or minutes not in (15, 30)
                or not isinstance(approval, str)
                or not SHA.fullmatch(approval)
            ):
                raise RequestError(422, "Invalid approved preview specification.")
            details = {"version": version, "minutes": minutes, "approval": approval}
        if action == "start" and event.get("approval") != row["approval"]:
            raise RequestError(409, "Approval does not match the saved plan.")
        if action == "available":
            details = {
                "endpoint": preview_endpoint(event.get("endpoint")),
                "available_until": now + int(row["minutes"]) * 60,
            }
        return self.change(row, status=transitions[action][1], **details)


class DynamoStore:
    def __init__(self, table):
        self.table = table

    def get(self, key):
        row = self.table.get_item(Key={"key": key}, ConsistentRead=True).get("Item")
        if row:
            for key in (
                "revision",
                "submit_by",
                "expires_at",
                "updated_at",
                "available_until",
                "version",
                "minutes",
            ):
                if key in row:
                    row[key] = int(row[key])
        return row

    def put(self, row, expected=None):
        options = (
            {
                "ConditionExpression": "attribute_not_exists(#key)",
                "ExpressionAttributeNames": {"#key": "key"},
            }
            if expected is None
            else {
                "ConditionExpression": "#revision = :expected",
                "ExpressionAttributeNames": {"#revision": "revision"},
                "ExpressionAttributeValues": {":expected": expected},
            }
        )
        try:
            self.table.put_item(Item=row, **options)
        except self.table.meta.client.exceptions.ConditionalCheckFailedException:
            return False
        return True


@lru_cache(maxsize=1)
def live_portal():
    import boto3  # Provided by the Lambda Python runtime.

    return Portal(DynamoStore(boto3.resource("dynamodb").Table(os.environ["REQUEST_TABLE"])))


def lambda_handler(event, _context):
    if asset := static_asset(event, event.get("requestContext") or {}):
        return asset
    return live_portal().handle(event)
