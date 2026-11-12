from fastapi.testclient import TestClient

from preview_demo.app import create_app

OWNER = {"Authorization": "Bearer test-operator"}
EXAMPLE = "Deploy version 2 for 30 minutes."


def rehearsal():
    now = [100.0]
    return TestClient(create_app("test-operator", clock=lambda: now[0])), now


def invite(client):
    response = client.post("/api/invites", headers=OWNER)
    assert response.status_code == 201
    return response.json()["invite"]


def guest_session(client):
    code = invite(client)
    response = client.post("/api/join", json={"invite": code})
    assert response.status_code == 200
    assert client.post("/api/join", json={"invite": code}).status_code == 403
    return {"Authorization": f"Bearer {response.json()['session']}"}


def request_preview(client, guest, prompt=EXAMPLE):
    return client.post("/api/requests", headers=guest, json={"request": prompt})


def status(client, headers):
    response = client.get("/api/status", headers=headers)
    assert response.status_code == 200
    return response.json()["deployment"]


def test_golden_path():
    client, now = rehearsal()
    guest = guest_session(client)
    result = request_preview(client, guest)
    assert result.status_code == 201
    job = result.json()
    assert job["spec"] == {"version": 2, "minutes": 30}
    assert job["phase"] == "awaiting_approval"
    assert (
        client.post("/api/sample/1", headers=guest, json={"email": "not-an-email"}).status_code
        == 409
    )
    approve = f"/api/requests/{job['id']}/approve"
    destroy = f"/api/requests/{job['id']}/destroy"
    assert client.post(approve, headers=guest).status_code == 403
    assert client.post(destroy, headers=guest).status_code == 403
    now[0] += 20
    assert status(client, guest)["phase"] == "awaiting_approval"
    assert client.post(approve, headers=OWNER).status_code == 200
    assert client.post(approve, headers=OWNER).status_code == 409

    now[0] += 2
    assert status(client, guest)["phase"] == "starting"
    now[0] += 2
    assert status(client, guest)["phase"] == "verifying"
    now[0] += 2
    ready = status(client, guest)
    assert ready["phase"] == "ready"
    assert all(event["at"] and event["message"] for event in ready["events"])

    invalid_email = {"email": "not-an-email"}
    baseline = client.post("/api/sample/1", headers=guest, json=invalid_email)
    preview = client.post("/api/sample/2", headers=guest, json=invalid_email)
    assert baseline.json()["accepted"] is True
    assert preview.json()["accepted"] is False
    for email in ("a..b@example.com", "student@-example.com", "student@example.com."):
        invalid = client.post("/api/sample/2", headers=guest, json={"email": email})
        assert invalid.json()["accepted"] is False
    valid = client.post("/api/sample/2", headers=guest, json={"email": "student@example.com"})
    assert valid.json()["accepted"] is True
    assert client.post(destroy, headers=OWNER).status_code == 200
    assert status(client, guest)["phase"] == "removed"
    assert client.post("/api/sample/2", headers=guest, json=invalid_email).status_code == 409
    assert request_preview(client, guest).status_code == 201


def test_rejects_unsupported_requests_and_isolates_guests():
    client, _ = rehearsal()
    first = guest_session(client)
    second = guest_session(client)
    assert client.get("/api/status").status_code == 401
    assert client.post("/api/invites", headers=first).status_code == 403
    for prompt in (
        "Deploy version 3 for 30 minutes.",
        "Deploy version 2 for 31 minutes.",
        "Deploy version 2 for 30 minutes and open port 22.",
    ):
        assert request_preview(client, first, prompt).status_code == 422
    assert status(client, OWNER) is None
    assert request_preview(client, first).status_code == 201
    assert status(client, second) is None
    assert request_preview(client, second).status_code == 409
    assert request_preview(client, first).status_code == 409


def test_expiry_and_stale_approval():
    client, now = rehearsal()
    code = invite(client)
    now[0] += 15 * 60
    assert client.post("/api/join", json={"invite": code}).status_code == 403
    guest = guest_session(client)
    job = request_preview(client, guest, "Deploy version 2 for 15 minutes.").json()
    url = f"/api/requests/{job['id']}"
    assert client.post(f"{url}/approve", headers=OWNER).status_code == 200
    now[0] += 6 + 15 * 60
    assert status(client, guest)["phase"] == "expired"
    assert request_preview(client, guest).status_code == 201
    assert client.post(f"{url}/approve", headers=OWNER).status_code == 404


def test_lifetime_must_fit_guest_session():
    client, now = rehearsal()
    guest = guest_session(client)
    now[0] += 40 * 60
    response = request_preview(client, guest)
    assert response.status_code == 409
    assert "fresh invite" in response.json()["detail"]
    assert status(client, OWNER) is None
