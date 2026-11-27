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
    assert client.get("/api/benchmarks").status_code == 200
    assert len(client.get("/api/operatives").json()["operatives"]) == 5
    products = client.get("/api/laptops")
    assert products.status_code == 200
    sku = products.json()["items"][0]["sku_id"]
    assert client.post("/sessions", json={"session_id": "legacy-session-123"}).status_code == 201

    session = new_session(client)
    sid = session["session_id"]
    assert "handoff_code" not in session
    assert client.get(f"/api/sessions/{sid}").status_code == 200
    pick_and_day(client, sid, sku)

    mission = client.post(f"/api/sessions/{sid}/run-mission", json={"mission_id": "student_notes", "airplane_mode": True})
    assert mission.status_code == 201
    assert mission.json()["badge"] == "DEMO / NOT VERIFIED"
    assert mission.json()["simulated"] is True

    foreground = client.post(f"/api/sessions/{sid}/foreground-challenge", json={"completed_steps": 3, "elapsed_ms": 18000})
    assert foreground.status_code == 201
    assert foreground.json()["hardware_benchmark"] is False
    assert client.get(f"/api/sessions/{sid}/foreground-challenge").status_code == 200
    assert client.get(f"/api/sessions/{sid}/foreground-test/results").status_code == 200

    assert client.get(f"/api/sessions/{sid}/reality-reveal").status_code == 200
    receipt = client.get(f"/api/sessions/{sid}/proof-receipt")
    assert receipt.status_code == 200
    assert receipt.json()["badge"] == "DEMO / NOT VERIFIED"
    assert client.get(f"/api/sessions/{sid}/loadout").status_code == 200
    assert client.get(f"/api/sessions/{sid}/recommendations").status_code == 200
    assert client.post(f"/api/sessions/{sid}/recommendations", json={"priority": "Portability"}).status_code == 200
    sku_ids = [row["sku_id"] for row in products.json()["items"] if row["brand"] == products.json()["items"][0]["brand"]][:2]
    assert client.get("/api/comparisons", params=[("sku_ids", sku_ids[0]), ("sku_ids", sku_ids[1])]).status_code == 200
    assert client.get("/api/comparisons", params=[("sku_ids", sku_ids[0]), ("sku_ids", "UNKNOWN")]).status_code == 404

    assert client.post(f"/api/sessions/{sid}/complete").status_code == 200
    handoff = client.post(f"/api/sessions/{sid}/handoff", json={"preferred_contact": "associate"})
    assert handoff.status_code == 200
    code = handoff.json()["handoff_code"]
    assert len(code) >= 40
    qr = client.get(f"/api/sessions/{sid}/handoff/qr", params={"code": code})
    assert qr.status_code == 200 and "<svg" in qr.text


def test_associate_login_lookup_claim_compare_checklist_and_complete(client):
    session = new_session(client)
    sid = session["session_id"]
    sku_ids = [row["sku_id"] for row in client.get("/api/laptops").json()["items"][:3]]
    pick_and_day(client, sid, sku_ids[0])
    login = client.post("/api/associate/login", json={"demo_login": True})
    assert login.status_code == 200
    handoff = client.post(f"/api/sessions/{sid}/handoff").json()
    code = handoff["handoff_code"]
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/associate/dashboard", headers=headers).json()["sessions"] == []
    lookup = client.get(f"/api/associate/lookup/{code}", headers=headers)
    assert lookup.status_code == 200
    assert lookup.json()["persona"] == "Student"
    assert lookup.json()["budget_ceiling"] == 200000

    first_claim = client.post(f"/api/associate/sessions/{sid}/claim", headers=headers, json={"handoff_code": code})
    second_claim = client.post(f"/api/associate/sessions/{sid}/claim", headers=headers, json={"handoff_code": code})
    assert first_claim.status_code == 200 and first_claim.json()["already_claimed"] is False
    assert second_claim.status_code == 200 and second_claim.json()["already_claimed"] is True
    assert client.get("/api/associate/dashboard", headers=headers).json()["metrics"]["sessions"] == 1
    assert client.post("/api/associate/compare", headers=headers, json={"sku_ids": sku_ids}).status_code == 200
    checklist = client.patch(f"/api/associate/sessions/{sid}/checklist", headers=headers, json={"states": {"power_on": True}})
    assert checklist.status_code == 200 and checklist.json()["states"]["power_on"] is True
    complete = client.post(f"/api/associate/sessions/{sid}/complete", headers=headers, json={"action": "trial", "selected_sku_id": sku_ids[1]})
    assert complete.status_code == 201

    other_store = client.post("/api/associate/login", json={"demo_login": True, "store_id": "OTHER"}).json()
    conflict = client.post(f"/api/associate/sessions/{sid}/claim", headers={"Authorization": f"Bearer {other_store['access_token']}"}, json={"handoff_code": code})
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
    assert client.get(f"/api/sessions/{sid}/handoff/qr").status_code == 404
    assert client.get("/api/associate/dashboard").status_code == 401
    assert client.post("/api/associate/login", json={"store_id": "BAD", "pin": "0000"}).status_code == 401

    login = client.post("/api/associate/login", json={"demo_login": True}).json()
    token = login["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/associate/lookup/ARENA-0000", headers=headers).status_code == 404
    assert client.post(f"/api/associate/sessions/{sid}/claim", headers=headers, json={"handoff_code": "x" * 43}).status_code == 404
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
        assert result.json()["badge"] == "DEMO / NOT VERIFIED"


def test_handoff_expiry_rate_limit_and_benchmark_admin_gates(client, monkeypatch):
    session = new_session(client)
    sid = session["session_id"]
    handoff = client.post(f"/api/sessions/{sid}/handoff").json()
    code = handoff["handoff_code"]
    with database.connect() as conn:
        conn.execute("UPDATE shopper_sessions SET handoff_expires_at = ? WHERE session_id = ?", ("2000-01-01T00:00:00Z", sid))
    assert client.get(f"/api/sessions/{sid}/handoff/qr", params={"code": code}).status_code == 404
    login = client.post("/api/associate/login", json={"demo_login": True}).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    assert client.get(f"/api/associate/lookup/{code}", headers=headers).status_code == 404
    assert client.post("/api/benchmarks/CPU_MULTITASKING_V1/approve").status_code == 401
    benchmark_payload = {"result_id":"result-id-1234567890","benchmark_session_id":"bench-session-123456","test_id":"CPU_MULTITASKING_V1","sku_id":"ASUS-ZENBOOK-S14-2024-32GB-1TB","test_date":"2026-11-27","device_name":"test device","os_version":"test os","runtime_version":"1.0","power_mode":"balanced","ac_power":True,"model_id":"test-model","model_hash":"a"*64,"input_hash":"b"*64,"prompt_hash":"c"*64,"execution_provider":"CPU","metric_value":10,"result_status":"COMPLETED","verification_status":"VERIFIED","run_index":1,"measurement_timestamp":"2026-11-27T10:00:00Z","evidence":{"signature":"invalid"}}
    assert client.post("/api/benchmarks/results", json=benchmark_payload).status_code == 401
    monkeypatch.setenv("ARENA_BENCHMARK_INGEST_TOKEN", "admin-secret-for-test")
    admin = {"Authorization": "Bearer admin-secret-for-test"}
    assert client.post("/api/benchmarks/CPU_MULTITASKING_V1/approve", headers=admin).status_code == 409
    assert client.post("/api/benchmarks/not-a-test/approve", headers=admin).status_code == 404
    live_session = new_session(client)
    live_code = client.post(f"/api/sessions/{live_session['session_id']}/handoff").json()["handoff_code"]
    for _ in range(7):
        assert client.get(f"/api/associate/lookup/{live_code}", headers=headers).status_code == 200
    assert client.get(f"/api/associate/lookup/{live_code}", headers=headers).status_code == 429

def test_demo_login_can_be_disabled(client, monkeypatch):
    monkeypatch.setenv("ARENA_DEMO_AUTH_ENABLED", "false")
    assert client.post("/api/associate/login", json={"demo_login": True}).status_code == 401


def test_legacy_local_runner_contract_stays_unverified(client, monkeypatch):
    import io
    from backend.app import main as api_module

    session = new_session(client)
    monkeypatch.setenv("LOCAL_RUNNER_URL", "http://127.0.0.1:8765")
    monkeypatch.delenv("VERCEL", raising=False)
    captured = {}

    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, _limit): return b'{"status":"PARTIAL","execution":"NOT VERIFIED","engine":"UNKNOWN","detail":"No compatible model is configured."}'

    def fake_urlopen(request, timeout):
        import json
        captured["body"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(api_module.urllib.request, "urlopen", fake_urlopen)
    result = client.post(f"/api/sessions/{session['session_id']}/run-mission", json={"mission_id":"nova_campus_rush"}).json()
    assert captured["body"]["provider"] == "CPU"
    assert "fixed synthetic" in captured["body"]["prompt"]
    assert result["badge"] == "DEMO / NOT VERIFIED"
    assert result["duration_ms"] is None and result["verified_hardware"] is False


def test_signed_benchmark_ingest_approval_and_comparison(client, monkeypatch):
    import hmac
    import json
    monkeypatch.setenv("ARENA_BENCHMARK_INGEST_TOKEN", "benchmark-admin")
    monkeypatch.setenv("ARENA_RUNNER_VERIFY_KEY", "runner-test-key")
    headers = {"Authorization": "Bearer benchmark-admin"}
    sku_ids = [item["sku_id"] for item in client.get("/api/laptops").json()["items"] if item["brand"] == "ASUS"][:2]
    for run_index in range(1, 4):
        payload = {"result_id":f"signed-result-{run_index:04d}","benchmark_session_id":f"signed-session-{run_index:04d}","test_id":"NPU_AI_RELAY_V1","sku_id":sku_ids[0],"test_date":"2026-11-27","device_name":"Verified test NPU","os_version":"Windows 11","runtime_version":"OpenVINO test","power_mode":"balanced","ac_power":True,"model_id":"arena-nova-local-llm","model_hash":"a"*64,"input_hash":"b"*64,"prompt_hash":"c"*64,"execution_provider":"NPU","metric_value":float(1200+run_index),"result_status":"COMPLETED","verification_status":"VERIFIED","run_index":run_index,"measurement_timestamp":f"2026-11-27T10:00:0{run_index}Z","bios_version":"UNKNOWN","driver_version":"UNKNOWN","evidence":{"runtime_verified":True,"device_name":"Verified test NPU"}}
        signed = {**payload, "contract_version":"arena-benchmark-v1"}
        signed["evidence"] = dict(payload["evidence"])
        signature = hmac.new(b"runner-test-key", json.dumps(signed,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode(),hashlib.sha256).hexdigest()
        payload["evidence"]["signature"] = signature
        response = client.post("/api/benchmarks/results", headers=headers, json=payload)
        assert response.status_code == 201, response.text
        assert response.json()["verification_status"] == "VERIFIED"
    approved = client.post("/api/benchmarks/NPU_AI_RELAY_V1/approve", headers=headers)
    assert approved.status_code == 200 and approved.json()["verified_sessions"] == 3
    comparison = client.get("/api/comparisons", params=[("sku_ids",sku_ids[0]),("sku_ids",sku_ids[1])]).json()
    result = next(row for row in comparison["rounds"] if row["test_id"]=="NPU_AI_RELAY_V1")["results"]
    assert len(result)==1 and result[0]["sku_id"]==sku_ids[0] and result[0]["verified_runs"]==3
