import json
import select
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest

from preview_demo.previewctl import verify_form
from preview_demo.terraform_runner import RunnerError

SAMPLE = (
    Path(__file__).resolve().parents[3] / "infra/terraform/environments/preview-academy/sample.py"
)


@pytest.mark.parametrize(("version", "expected"), [(1, b"Accepted"), (2, b"Rejected")])
def test_cloud_sample_serves_correct_version(version, expected):
    with subprocess.Popen(
        [sys.executable, str(SAMPLE), str(version), "127.0.0.1", "0"],
        stdout=subprocess.PIPE,
        text=True,
    ) as server:
        try:
            readable, _, _ = select.select([server.stdout], [], [], 5)
            assert readable, "sample did not start"
            ready = server.stdout.readline()
            assert f"Ready: version {version}" in ready
            port = int(ready.split()[-1])
            url = f"http://127.0.0.1:{port}"
            with urlopen(f"{url}/readyz", timeout=3) as response:
                assert json.load(response) == {"ready": True, "version": version}
            with urlopen(
                url, data=urlencode({"email": "not-an-email"}).encode(), timeout=3
            ) as form:
                assert expected in form.read()
            verify_form("127.0.0.1", version, port=port)
            with pytest.raises(RunnerError, match="form"):
                verify_form("127.0.0.1", 3 - version, port=port)
        finally:
            server.terminate()
