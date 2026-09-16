"""Minimal HTTP helpers (stdlib only) for health checks."""

import logging
import time
import urllib.error
import urllib.request

from aiplatform.errors import StepError

log = logging.getLogger(__name__)


def probe(url: str, timeout: float = 3.0) -> tuple[int, str]:
    """GET `url`, returning (status, body). Network errors return status 0."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - http(s) only
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return 0, ""


def wait_for_http(url: str, timeout: float, interval: float = 2.0, label: str = "") -> float:
    """Poll `url` until it returns 200 or `timeout` seconds pass. Returns seconds waited."""
    started = time.monotonic()
    last = (0, "")
    while time.monotonic() - started < timeout:
        last = probe(url)
        if last[0] == 200:
            return time.monotonic() - started
        log.debug("%s not ready (status=%s), retrying", label or url, last[0])
        time.sleep(interval)
    body = last[1].strip()[:200]
    raise StepError(
        f"{label or url} did not become healthy within {timeout:.0f}s "
        f"(last status {last[0]}{': ' + body if body else ''})"
    )
