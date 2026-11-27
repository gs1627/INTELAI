import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import db as database
from backend.app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "arena-test.db")
    database.init_db()
    with TestClient(app) as test_client:
        yield test_client


def new_session(client):
    response = client.post("/api/sessions", json={})
    assert response.status_code == 201
    return response.json()


def pick_and_day(client, session_id, sku_id):
    assert client.patch(f"/api/sessions/{session_id}/blind-pick", json={"sku_id": sku_id, "visual_reason": "Selected by appearance"}).status_code == 200
    assert client.patch(f"/api/sessions/{session_id}/day", json={
        "persona": "Student", "budget_ceiling": 200000,
        "non_negotiable": "Battery life", "top_priority": "Battery life", "required_apps": [],
    }).status_code == 200


def test_customer_complete_flow_and_all_customer_endpoints(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/system/status").status_code == 200
    assert len(client.get("/api/operatives").json()["operatives"]) == 5
    products = client.get("/api/laptops")
    assert products.status_code == 200
    sku = products.json()["items"][0]["sku_id"]
    assert client.post("/sessions", json={"session_id": "legacy-session-123"}).status_code == 201

    session = new_session(client)
    sid = session["session_id"]
    assert client.get(f"/api/sessions/{sid}").status_code == 200
    pick_and_day(client, sid, sku)

    mission = client.post(f"/api/sessions/{sid}/run-mission", json={"mission_id": "student_notes", "airplane_mode": True})
    assert mission.status_code == 201
    assert mission.json()["badge"] == "DEMO / RECORDED PROOF"
    assert mission.json()["simulated"] is True

    foreground = client.post(f"/api/sessions/{sid}/foreground-challenge", json={"completed_steps": 3, "elapsed_ms": 18000})
    assert foreground.status_code == 201
    assert foreground.json()["hardware_benchmark"] is False
    assert client.get(f"/api/sessions/{sid}/foreground-challenge").status_code == 200
    assert client.get(f"/api/sessions/{sid}/foreground-test/results").status_code == 200

    assert client.get(f"/api/sessions/{sid}/reality-reveal").status_code == 200
    receipt = client.get(f"/api/sessions/{sid}/proof-receipt")
    assert receipt.status_code == 200
    assert receipt.json()["badge"] == "DEMO / RECORDED PROOF"
    assert client.get(f"/api/sessions/{sid}/loadout").status_code == 200
    assert client.get(f"/api/sessions/{sid}/recommendations").status_code == 200
    assert client.post(f"/api/sessions/{sid}/recommendations", json={"priority": "Portability"}).status_code == 200

    assert client.post(f"/api/sessions/{sid}/complete").status_code == 200
    handoff = client.post(f"/api/sessions/{sid}/handoff", json={"preferred_contact": "associate"})
    assert handoff.status_code == 200
    assert handoff.json()["qr_payload"]["code"] == session["handoff_code"]
    qr = client.get(f"/api/sessions/{sid}/handoff/qr")
    assert qr.status_code == 200 and "<svg" in qr.text


def test_associate_login_lookup_claim_compare_checklist_and_complete(client):
    session = new_session(client)
    sid = session["session_id"]
    sku_ids = [row["sku_id"] for row in client.get("/api/laptops").json()["items"][:3]]
    pick_and_day(client, sid, sku_ids[0])
    assert client.post(f"/api/sessions/{sid}/handoff").status_code == 200

    login = client.post("/api/associate/login", json={"demo_login": True})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/associate/dashboard", headers=headers).status_code == 200
    lookup = client.get(f"/api/associate/lookup/{session['handoff_code']}", headers=headers)
    assert lookup.status_code == 200
    assert lookup.json()["persona"] == "Student"
    assert lookup.json()["budget_ceiling"] == 200000

    first_claim = client.post(f"/api/associate/sessions/{sid}/claim", headers=headers)
    second_claim = client.post(f"/api/associate/sessions/{sid}/claim", headers=headers)
    assert first_claim.status_code == 200 and first_claim.json()["already_claimed"] is False
    assert second_claim.status_code == 200 and second_claim.json()["already_claimed"] is True
    assert client.post("/api/associate/compare", headers=headers, json={"sku_ids": sku_ids}).status_code == 200
    checklist = client.patch(f"/api/associate/sessions/{sid}/checklist", headers=headers, json={"states": {"power_on": True}})
    assert checklist.status_code == 200 and checklist.json()["states"]["power_on"] is True
    complete = client.post(f"/api/associate/sessions/{sid}/complete", headers=headers, json={"action": "trial", "selected_sku_id": sku_ids[1]})
    assert complete.status_code == 201

    other_store = client.post("/api/associate/login", json={"demo_login": True, "store_id": "OTHER"}).json()
    conflict = client.post(f"/api/associate/sessions/{sid}/claim", headers={"Authorization": f"Bearer {other_store['access_token']}"})
    assert conflict.status_code == 409


def test_validation_missing_sessions_invalid_tokens_and_expiry(client):
    sid = "missing-session-id"
    assert client.get(f"/api/sessions/{sid}").status_code == 404
    assert client.patch(f"/api/sessions/{sid}/day", json={"persona": "Student", "budget_ceiling": 100000, "non_negotiable": "Battery", "top_priority": "Battery"}).status_code == 404
    assert client.post(f"/api/sessions/{sid}/run-mission", json={"mission_id": "missing"}).status_code == 404
    assert client.post("/api/sessions", json={"unexpected": True}).status_code == 422

    session = new_session(client)
    sid = session["session_id"]
    assert client.patch(f"/api/sessions/{sid}/blind-pick", json={"sku_id": "UNKNOWN-SKU"}).status_code == 404
    assert client.patch(f"/api/sessions/{sid}/day", json={"persona": "not-real", "budget_ceiling": 20, "top_priority": ""}).status_code == 422
    assert client.get(f"/api/sessions/{sid}/reality-reveal").status_code == 409
    assert client.get(f"/api/sessions/{sid}/loadout").status_code == 409
    assert client.post(f"/api/sessions/{sid}/handoff/qr").status_code == 405
    assert client.get(f"/api/sessions/{sid}/handoff/qr").status_code == 409
    assert client.get("/api/associate/dashboard").status_code == 401
    assert client.post("/api/associate/login", json={"store_id": "BAD", "pin": "0000"}).status_code == 401

    login = client.post("/api/associate/login", json={"demo_login": True}).json()
    token = login["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/associate/lookup/ARENA-0000", headers=headers).status_code == 404
    assert client.post(f"/api/associate/sessions/{sid}/claim", headers=headers).status_code == 409
    assert client.get("/api/associate/dashboard", headers={"Authorization": "Bearer invalid"}).status_code == 401
    expires = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds").replace("+00:00", "Z")
    digest = hashlib.sha256(token.encode()).hexdigest()
    with database.connect() as conn:
        conn.execute("UPDATE associate_tokens SET expires_at = ? WHERE token_hash = ?", (expires, digest))
    assert client.get("/api/associate/dashboard", headers=headers).status_code == 401


def test_state_survives_new_client_and_runner_failure_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "persistent.db")
    database.init_db()
    with TestClient(app) as first:
        session = new_session(first)
        sku = first.get("/api/laptops").json()["items"][0]["sku_id"]
        pick_and_day(first, session["session_id"], sku)
    with TestClient(app) as refreshed:
        state = refreshed.get(f"/api/sessions/{session['session_id']}").json()
        assert state["blind_pick_sku_id"] == sku
        assert state["persona"] == "Student"

    monkeypatch.setenv("LOCAL_RUNNER_URL", "http://127.0.0.1:1")
    with TestClient(app) as test_client:
        result = test_client.post(f"/api/sessions/{session['session_id']}/run-mission", json={"mission_id": "unavailable-runner"})
        assert result.status_code == 201
        assert result.json()["simulated"] is True
        assert result.json()["badge"] == "DEMO / RECORDED PROOF"
