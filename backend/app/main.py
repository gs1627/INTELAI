from __future__ import annotations

import hashlib
import io
import json
import os
import secrets
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from .db import DB_MODE, connect, get_db, init_db, now_iso
from .schemas import (
    AssociateLogin, BlindPick, ChecklistUpdate, CompareRequest, CompleteInteraction,
    ForegroundChallenge, HandoffRequest, MissionRequest, RecommendationRequest, SessionCreate, ShopperDay,
)

init_db()
app = FastAPI(title="Intel AI PC Arena API", version="2.0.0")
cors_origins = [x.strip() for x in os.getenv("ARENA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])

PERSONA_TRADEOFFS = {
    "Student": ["Confirm the exact campus software and exam-proctoring tools run on the target OS/CPU architecture.", "The catalogue records manufacturer-listed battery capacity, not measured classroom runtime."],
    "Creator": ["Check the exact editing app, plug-ins, codec support, and GPU acceleration on the selected configuration.", "16 GB RAM can constrain large projects; some listed memory is not user-upgradeable."],
    "First Job": ["Verify employer VPN, endpoint security, and device-management compatibility before purchase.", "Pre-installed office offers and subscription terms vary by SKU and redemption date."],
    "Gamer": ["Check each game's GPU requirements, anti-cheat driver support, and thermals; this catalogue has no gaming benchmark results.", "Integrated graphics are not a substitute for a discrete gaming GPU."],
    "Everyday": ["Check the ports, webcam, keyboard layout, and screen in person if these affect daily use.", "Retail prices and local delivery availability can change by seller and pincode."],
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _read_json(value: Optional[str], fallback: Any = None) -> Any:
    if not value:
        return fallback if fallback is not None else {}
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback if fallback is not None else {}


def _session(db: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    row = db.execute("SELECT * FROM shopper_sessions WHERE session_id = ?", (session_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Shopper session not found")
    return {"session_id": row["session_id"], "handoff_code": row["handoff_code"], **_read_json(row["state_json"]), "created_at": row["created_at"], "updated_at": row["updated_at"], "finalized": bool(row["finalized"])}


def _store_state(db: sqlite3.Connection, state: dict[str, Any]) -> None:
    db.execute("UPDATE shopper_sessions SET state_json = ?, updated_at = ? WHERE session_id = ?", (_json({k: v for k, v in state.items() if k not in {"session_id", "handoff_code", "created_at", "updated_at", "finalized"}}), now_iso(), state["session_id"]))


def _sku(db: sqlite3.Connection, sku_id: str) -> dict[str, Any]:
    row = db.execute("SELECT data_json FROM laptops WHERE sku_id = ?", (sku_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Laptop SKU not found")
    return _read_json(row["data_json"])


def _catalog(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return [_read_json(r["data_json"]) for r in db.execute("SELECT data_json FROM laptops ORDER BY price_inr ASC, sku_id ASC").fetchall()]


def _recent_mission(db: sqlite3.Connection, session_id: str) -> Optional[dict[str, Any]]:
    row = db.execute("SELECT result_json FROM mission_runs WHERE session_id = ? ORDER BY created_at DESC LIMIT 1", (session_id,)).fetchone()
    return _read_json(row["result_json"]) if row else None


def _make_handoff_code(db: sqlite3.Connection) -> str:
    for _ in range(20):
        code = f"ARENA-{secrets.randbelow(9000) + 1000}"
        if not db.execute("SELECT 1 FROM shopper_sessions WHERE handoff_code = ?", (code,)).fetchone():
            return code
    raise HTTPException(503, "Could not allocate a handoff code; try again")


def _associate(authorization: Optional[str], db: sqlite3.Connection) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Associate login required")
    token = authorization.split(" ", 1)[1].strip()
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.execute("SELECT store_id, expires_at FROM associate_tokens WHERE token_hash = ?", (digest,)).fetchone()
    if not row or row["expires_at"] <= now_iso():
        raise HTTPException(401, "Associate demo session expired")
    return row["store_id"]


@app.get("/health")
@app.get("/api/health")
def health(db: sqlite3.Connection = Depends(get_db)):
    db_ok = False
    sku_count = 0
    try:
        sku_count = db.execute("SELECT COUNT(*) FROM laptops").fetchone()[0]
        db_ok = True
    except Exception:
        pass
    return {
        "ok": db_ok,
        "service": "intel-ai-pc-arena",
        "database_mode": DB_MODE,
        "sku_count": sku_count,
        "timestamp": now_iso(),
        "npu_verified": False,
        "available": True,
        "status": "ok",
    }


@app.get("/api/system/status")
def system_status(db: sqlite3.Connection = Depends(get_db)):
    sku_count = db.execute("SELECT COUNT(*) FROM laptops").fetchone()[0]
    return {
        "backend": "ok",
        "database": "ok",
        "hardware_capability": "UNVERIFIED",
        "execution_modes": ["SAMPLE DEMO", "HISTORICAL DATA"],
        "live_hardware_available": False,
        "demo_mode": True,
        "npu_verified": False,
        "catalogue_laptops": sku_count,
        "disclaimer": "SAMPLE DEMONSTRATION DATA — not Intel-certified or a hardware benchmark.",
        "timestamp": now_iso(),
    }


OPERATIVES = [
    {"id": "nova", "name": "NOVA", "role": "The student", "icon": "✦", "color": "#6ad7ff", "quote": "Curiosity is my superpower.", "mission": "Turn a messy lecture note into a clean study guide.", "priority": "Battery life", "detail": "Classes, research & local AI study help"},
    {"id": "pixel", "name": "PIXEL", "role": "The creator", "icon": "◈", "color": "#ff8ec3", "quote": "Make the idea impossible to ignore.", "mission": "Organise a creative brief and prep a visual pitch.", "priority": "GPU performance", "detail": "Editing, rendering & AI-assisted creation"},
    {"id": "cipher", "name": "CIPHER", "role": "The professional", "icon": "⌘", "color": "#a89dff", "quote": "Make room for the work that matters.", "mission": "Triage a busy inbox and prep a meeting brief.", "priority": "Multitasking", "detail": "Meetings, documents & productive AI"},
    {"id": "volt", "name": "VOLT", "role": "The gamer", "icon": "⚡", "color": "#ffc76b", "quote": "Every frame is another chance.", "mission": "Plan a tournament loadout under pressure.", "priority": "Graphics performance", "detail": "High refresh play, thermals & fast storage"},
    {"id": "orbit", "name": "ORBIT", "role": "The everyday user", "icon": "◎", "color": "#7ee3bd", "quote": "The little things add up to a good day.", "mission": "Plan a weekend and clear a small to-do list.", "priority": "Portability", "detail": "Everyday speed, battery & easy carry"},
]


@app.get("/api/operatives")
def list_operatives():
    return {"operatives": OPERATIVES}


@app.get("/api/laptops")
def laptops(db: sqlite3.Connection = Depends(get_db)):
    return {"items": _catalog(db), "count": db.execute("SELECT COUNT(*) FROM laptops").fetchone()[0], "currency": "INR", "generated_at": now_iso(), "price_notice": "Seed prices are source snapshots, not live quotes or inventory. Confirm price and stock with seller."}


@app.post("/sessions", status_code=201)
@app.post("/api/sessions", status_code=201)
def create_session(payload: SessionCreate, db: sqlite3.Connection = Depends(get_db)):
    sid = payload.session_id or str(uuid4())
    # Upsert-friendly: return existing session if already created with same ID
    existing = db.execute("SELECT * FROM shopper_sessions WHERE session_id = ?", (sid,)).fetchone()
    if existing:
        return _session(db, sid)
    # Build initial state enriched with any fields sent by App.tsx
    state: dict[str, Any] = {
        "blind_pick_sku_id": payload.current_laptop_id if hasattr(payload, "current_laptop_id") else None,
        "visual_reason": "",
        "persona": getattr(payload, "persona", None) or None,
        "budget_ceiling": getattr(payload, "budget", None) or 140_000,
        "non_negotiable": "",
        "top_priority": getattr(payload, "priority", "") or "",
        "required_apps": [],
        "last_mission": None,
        "handoff": None,
        "stage": "pick",
        "mode": "SAMPLE DEMO",
        "checklist": [False, False, False],
        "rounds": [],
    }
    code = _make_handoff_code(db)
    ts = now_iso()
    try:
        with db:
            db.execute("INSERT INTO shopper_sessions (session_id, handoff_code, state_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", (sid, code, _json(state), ts, ts))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "Session could not be created") from exc
    return {"session_id": sid, "handoff_code": code, **state, "created_at": ts, "updated_at": ts}


@app.get("/api/sessions/{session_id}")
def get_shopper_session(session_id: str, db: sqlite3.Connection = Depends(get_db)):
    return _session(db, session_id)


@app.patch("/api/sessions/{session_id}/blind-pick")
def update_blind_pick(session_id: str, payload: BlindPick, db: sqlite3.Connection = Depends(get_db)):
    state = _session(db, session_id)
    _sku(db, payload.sku_id)
    state["blind_pick_sku_id"] = payload.sku_id
    state["visual_reason"] = payload.visual_reason
    with db:
        _store_state(db, state)
    return {"session_id": session_id, "blind_pick_sku_id": payload.sku_id, "visual_reason": payload.visual_reason, "updated_at": now_iso()}


@app.patch("/api/sessions/{session_id}/day")
def update_day(session_id: str, payload: ShopperDay, db: sqlite3.Connection = Depends(get_db)):
    state = _session(db, session_id)
    state.update(payload.model_dump())
    with db:
        _store_state(db, state)
    return {"session_id": session_id, "persona": payload.persona, "budget_ceiling": payload.budget_ceiling, "top_priority": payload.top_priority, "required_apps": payload.required_apps, "updated_at": now_iso()}


def _runner_result(session_id: str, mission_id: str, airplane_mode: bool) -> Optional[dict[str, Any]]:
    runner_url = os.getenv("LOCAL_RUNNER_URL", "").strip()
    if not runner_url:
        return None
    request = urllib.request.Request(runner_url.rstrip("/") + "/relay", data=_json({"session_id": session_id, "mission_id": mission_id, "airplane_mode": airplane_mode}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=2.5) as response:
            if response.status != 200:
                return None
            result = json.loads(response.read(1_000_000).decode("utf-8"))
            return result if isinstance(result, dict) else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _simulation_result(session_id: str, mission_id: str, airplane_mode: bool) -> dict[str, Any]:
    seed = hashlib.sha256(f"{session_id}:{mission_id}".encode()).digest()
    local_ms = 420 + int.from_bytes(seed[:2], "big") % 1580
    cloud_ms = 180 + int.from_bytes(seed[2:4], "big") % 820
    online = not airplane_mode
    return {
        "mission_id": mission_id,
        "execution_mode": "ILLUSTRATIVE_SIMULATION",
        "badge": "DEMO / RECORDED PROOF",
        "verified_hardware": False,
        "simulated": True,
        "network_state": "ONLINE (SIMULATED)" if online else "AIRPLANE MODE / OFFLINE",
        "execution_location": "SIMULATION; no local or cloud inference ran",
        "compute_engine": "NOT MEASURED",
        "cloud": {"available": online, "illustrative_time_ms": cloud_ms if online else None, "label": "SIMULATED ESTIMATE" if online else "UNAVAILABLE OFFLINE"},
        "local": {"available": True, "illustrative_time_ms": local_ms, "label": "SIMULATED ESTIMATE"},
        "outcome": "Illustrative flow only; no workload was executed.",
        "timing_notice": "Illustrative deterministic UI timings, not measured performance.",
    }


@app.post("/api/sessions/{session_id}/run-mission", status_code=201)
def run_mission(session_id: str, payload: MissionRequest, db: sqlite3.Connection = Depends(get_db)):
    _session(db, session_id)
    runner = _runner_result(session_id, payload.mission_id, payload.airplane_mode)
    if runner is None:
        result = _simulation_result(session_id, payload.mission_id, payload.airplane_mode)
    else:
        verified = runner.get("verified_hardware") is True and runner.get("execution_mode") == "LOCAL"
        engine = str(runner.get("compute_engine", "NOT VERIFIED")).upper()
        badge = "DEMO / RECORDED PROOF"
        if verified and engine == "NPU":
            badge = "NPU-ACCELERATED"
        elif verified and engine in {"CPU", "GPU", "CPU/GPU"}:
            badge = "CPU/GPU LOCAL"
        elif verified:
            badge = "LOCAL"
        result = {
            "mission_id": payload.mission_id, "execution_mode": "LOCAL" if verified else "DEMO / RECORDED PROOF",
            "badge": badge, "verified_hardware": verified, "simulated": not verified,
            "network_state": "AIRPLANE MODE / OFFLINE" if payload.airplane_mode else ("ONLINE" if runner.get("network_used") else "NETWORK NOT USED / UNKNOWN"),
            "execution_location": "LOCAL DEVICE" if verified else "UNVERIFIED RUNNER RESPONSE",
            "compute_engine": engine if verified else "NOT VERIFIED", "cloud": {"available": False, "label": "NOT RUN"},
            "local": {"available": True, "duration_ms": runner.get("duration_ms") if verified else None, "label": "VERIFIED LOCAL RESULT" if verified else "RESULT NOT VERIFIED"},
            "outcome": runner.get("result") if verified else "Runner responded, but did not provide required verification evidence.",
            "timing_notice": "Hardware results are accepted only when the runner explicitly attests verified local execution.",
        }
    run_id, ts = str(uuid4()), now_iso()
    with db:
        db.execute("INSERT INTO mission_runs (run_id, session_id, mission_id, result_json, created_at) VALUES (?, ?, ?, ?, ?)", (run_id, session_id, payload.mission_id, _json(result), ts))
        state = _session(db, session_id)
        state["last_mission"] = {"run_id": run_id, "created_at": ts, **result}
        _store_state(db, state)
    return {"run_id": run_id, "created_at": ts, **result}


@app.get("/api/sessions/{session_id}/proof-receipt")
def proof_receipt(session_id: str, db: sqlite3.Connection = Depends(get_db)):
    state = _session(db, session_id)
    selected = _sku(db, state["blind_pick_sku_id"]) if state.get("blind_pick_sku_id") else None
    mission = _recent_mission(db, session_id)
    tradeoffs = PERSONA_TRADEOFFS.get(state.get("persona"), PERSONA_TRADEOFFS["Everyday"])
    return {
        "session_id": session_id,
        "pillars": {
            "network_state": (mission or {}).get("network_state", "NOT RUN"),
            "execution_location": (mission or {}).get("execution_location", "NOT RUN"),
            "compute_engine": (mission or {}).get("compute_engine", "NOT MEASURED"),
            "outcome": (mission or {}).get("outcome", "No mission result yet."),
        },
        "badge": (mission or {}).get("badge", "DEMO / RECORDED PROOF"),
        "blind_pick": selected,
        "blind_pick_reason": state.get("visual_reason", ""),
        "tradeoffs": tradeoffs,
        "price_notice": "Catalogue prices are source snapshots; this receipt is not a quote or inventory reservation.",
        "generated_at": now_iso(),
    }


def _required_apps_fit(sku: dict[str, Any], required_apps: list[str]) -> bool:
    if not required_apps:
        return True
    # These explicit requirements mean an x64 kernel driver/runtime is mandatory.
    x64_only = {"x64-only driver", "legacy x64 kernel driver", "x64-only anti-cheat"}
    return not (sku["app_compatibility"]["architecture"] == "Arm64" and any(a.strip().lower() in x64_only for a in required_apps))


def _ownership_breakdown(price: int) -> dict[str, Any]:
    return {"basis": "cash price divided evenly; no interest, fees, or financing implied", "monthly": {str(months): round(price / months, 2) for months in (12, 24, 36)}}


def _loadout_card(sku: dict[str, Any], state: dict[str, Any], selected: Optional[dict[str, Any]]) -> dict[str, Any]:
    price, budget = sku["price_inr"], state["budget_ceiling"]
    priority = (state.get("top_priority") or "").lower()
    ai_wanted = any(x in priority for x in ("ai", "npu", "copilot"))
    if "battery" in priority:
        priority_met = sku["battery_wh"] >= 70
        priority_reason = f"{sku['battery_wh']} Wh listed capacity; this is not a battery-life estimate."
    elif "portab" in priority:
        priority_met = sku["weight_kg"] <= 1.4
        priority_reason = f"Listed weight: {sku['weight_kg']} kg."
    elif "multi" in priority or "memory" in priority:
        priority_met = sku["ram_gb"] >= 16
        priority_reason = f"{sku['ram_gb']} GB listed memory."
    elif "display" in priority or "screen" in priority:
        priority_met = sku["display"]["panel"].lower().find("oled") >= 0 or sku["display"]["refresh_hz"] >= 120
        priority_reason = f"{sku['display']['panel']}, {sku['display']['refresh_hz']} Hz listed panel."
    elif "gpu" in priority or "graphic" in priority:
        priority_met = any(x in sku["gpu"].lower() for x in ("nvidia", "geforce", "radeon 8060", "rtx"))
        priority_reason = f"Listed graphics: {sku['gpu']}; no benchmark supplied."
    else:
        priority_met = sku["processor"]["npu_tops"] >= 40 if ai_wanted else True
        priority_reason = f"{sku['processor']['npu_tops']} processor NPU TOPS listed; app support still varies."
    app_fit = _required_apps_fit(sku, state.get("required_apps", []))
    persona = state.get("persona") or "Everyday"
    persona_fit = sku["ram_gb"] >= 16
    if persona == "Gamer":
        persona_fit = sku["display"]["refresh_hz"] >= 120 or any(x in sku["gpu"].lower() for x in ("rtx", "geforce"))
    elif persona == "Creator":
        persona_fit = sku["ram_gb"] >= 16 and sku["storage_gb"] >= 512
    elif persona == "Student":
        persona_fit = sku["weight_kg"] <= 1.9 and sku["storage_gb"] >= 512
    within_budget = price <= budget
    criteria = [within_budget, sku["ram_gb"] >= 16, app_fit, persona_fit, priority_met]
    reasons = [f"{price:,} INR source snapshot is within the {budget:,} INR budget." if within_budget else "Over budget; excluded from eligible cards.", priority_reason, f"Architecture: {sku['app_compatibility']['architecture']}; required apps checked against the declared compatibility notes."]
    delta = price - selected["price_inr"] if selected else None
    return {
        "sku": sku, "priorities_met": f"{sum(criteria)} of 5 priorities met", "score": sum(criteria),
        "reasons": reasons, "compromise": sku["limitation"], "price_delta_inr": delta,
        "monthly_ownership_cost": _ownership_breakdown(price),
    }


@app.get("/api/sessions/{session_id}/loadout")
def loadout(session_id: str, priority: Optional[str] = Query(default=None, max_length=100), db: sqlite3.Connection = Depends(get_db)):
    state = _session(db, session_id)
    if priority is not None:
        state["top_priority"] = priority
    if state.get("budget_ceiling") is None:
        raise HTTPException(409, "Complete the shopper day before requesting recommendations")
    if not state.get("blind_pick_sku_id"):
        raise HTTPException(409, "Select a blind-pick laptop before requesting recommendations")
    selected = _sku(db, state["blind_pick_sku_id"])
    candidates = [x for x in _catalog(db) if x["price_inr"] is not None and x["price_inr"] <= state["budget_ceiling"] and _required_apps_fit(x, state.get("required_apps", []))]
    scored = [_loadout_card(x, state, selected) for x in candidates]
    if not scored:
        return {"priority": state.get("top_priority"), "best_match": None, "save_money": None, "stretch": None, "excluded": "No catalogue SKU passes the budget and app-compatibility gates.", "generated_at": now_iso()}
    best = sorted(scored, key=lambda x: (-x["score"], abs(x["sku"]["price_inr"] - (state["budget_ceiling"] * 0.7)), x["sku"]["price_inr"], x["sku"]["brand"]))[0]
    save = min(scored, key=lambda x: (x["sku"]["price_inr"], x["sku"]["brand"]))
    stretch = max(scored, key=lambda x: (x["sku"]["price_inr"], x["sku"]["brand"]))
    return {"priority": state.get("top_priority"), "budget_ceiling": state["budget_ceiling"], "best_match": best, "save_money": save, "stretch": stretch, "shortlisted_skus": len(scored), "rule_notice": "Hard gates are budget and explicit app-architecture conflicts. Scores use only listed configuration fields; no brand weighting or benchmark ranking.", "generated_at": now_iso()}


@app.get("/api/sessions/{session_id}/reality-reveal")
def reality_reveal(session_id: str, db: sqlite3.Connection = Depends(get_db)):
    state = _session(db, session_id)
    if not state.get("blind_pick_sku_id"):
        raise HTTPException(409, "Choose a blind-pick laptop before revealing its configuration")
    return {"session_id": session_id, "selected_configuration": _sku(db, state["blind_pick_sku_id"]), "revealed_at": now_iso(), "data_notice": "Manufacturer and catalogue fields; no performance result is implied."}


@app.post("/api/sessions/{session_id}/foreground-challenge", status_code=201)
def foreground_challenge(session_id: str, payload: ForegroundChallenge, db: sqlite3.Connection = Depends(get_db)):
    state = _session(db, session_id)
    result = {"challenge_id": payload.challenge_id, "completed_steps": payload.completed_steps, "elapsed_ms": payload.elapsed_ms, "execution": "BROWSER SESSION", "hardware_benchmark": False, "recorded_at": now_iso()}
    state["foreground_challenge"] = result
    with db:
        _store_state(db, state)
    return {"session_id": session_id, **result}


@app.get("/api/sessions/{session_id}/foreground-challenge")
def get_foreground_challenge(session_id: str, db: sqlite3.Connection = Depends(get_db)):
    state = _session(db, session_id)
    return {"session_id": session_id, "result": state.get("foreground_challenge"), "hardware_benchmark": False}


@app.get("/api/sessions/{session_id}/foreground-test/results")
def get_foreground_test_results(session_id: str, db: sqlite3.Connection = Depends(get_db)):
    return get_foreground_challenge(session_id, db)


@app.post("/api/sessions/{session_id}/recommendations")
def create_recommendations(session_id: str, payload: RecommendationRequest, db: sqlite3.Connection = Depends(get_db)):
    return loadout(session_id, payload.priority, db)


@app.get("/api/sessions/{session_id}/recommendations")
def get_recommendations(session_id: str, priority: Optional[str] = Query(default=None, max_length=100), db: sqlite3.Connection = Depends(get_db)):
    return loadout(session_id, priority, db)


@app.post("/api/sessions/{session_id}/complete")
def complete_session(session_id: str, db: sqlite3.Connection = Depends(get_db)):
    state = _session(db, session_id)
    with db:
        db.execute("UPDATE shopper_sessions SET finalized = 1, updated_at = ? WHERE session_id = ?", (now_iso(), session_id))
        state["completed_at"] = now_iso()
        _store_state(db, state)
    return {"session_id": session_id, "completed": True, "completed_at": state["completed_at"]}


@app.get("/api/sessions/{session_id}/handoff/qr")
def handoff_qr(session_id: str, db: sqlite3.Connection = Depends(get_db)):
    state = _session(db, session_id)
    if not state.get("handoff"):
        raise HTTPException(409, "Create a handoff before requesting its QR code")
    import qrcode
    from qrcode.image.svg import SvgPathImage

    buffer = io.BytesIO()
    qrcode.make(state["handoff"]["qr_payload"]["path"], image_factory=SvgPathImage, box_size=8, border=2).save(buffer)
    return Response(content=buffer.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


@app.post("/api/sessions/{session_id}/handoff")
def finalize_handoff(session_id: str, payload: Optional[HandoffRequest] = None, db: sqlite3.Connection = Depends(get_db)):
    state = _session(db, session_id)
    code = state["handoff_code"]
    qr_payload = {"code": code, "path": f"/associate?code={code}"}
    with db:
        db.execute("UPDATE shopper_sessions SET finalized = 1, updated_at = ? WHERE session_id = ?", (now_iso(), session_id))
        state["handoff"] = {"handoff_code": code, "qr_payload": qr_payload, "created_at": now_iso()}
        _store_state(db, state)
    return {"session_id": session_id, "handoff_code": code, "qr_payload": qr_payload, "finalized": True, "privacy": "QR payload contains only an opaque session lookup code."}


@app.post("/api/associate/login")
def associate_login(payload: AssociateLogin, db: sqlite3.Connection = Depends(get_db)):
    if payload.demo_login:
        store_id = payload.store_id or "DEMO-STORE"
    elif payload.store_id and payload.pin == "1234":
        store_id = payload.store_id
    else:
        raise HTTPException(401, "Use Demo Login or enter a store ID and demo PIN 1234")
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(timespec="seconds").replace("+00:00", "Z")
    digest = hashlib.sha256(token.encode()).hexdigest()
    with db:
        db.execute("INSERT INTO associate_tokens(token_hash, store_id, expires_at, created_at) VALUES (?, ?, ?, ?)", (digest, store_id, expires, now_iso()))
    return {"access_token": token, "token_type": "bearer", "store_id": store_id, "expires_at": expires, "demo_auth": True}


@app.post("/api/associate/sessions/{session_id}/claim")
def claim_session(session_id: str, authorization: Optional[str] = Header(default=None), db: sqlite3.Connection = Depends(get_db)):
    store_id = _associate(authorization, db)
    state = _session(db, session_id)
    if not state.get("handoff"):
        raise HTTPException(409, "Shopper must generate a handoff before an associate can claim the session")
    token = authorization.split(" ", 1)[1].strip()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    existing = db.execute("SELECT store_id FROM associate_claims WHERE session_id = ?", (session_id,)).fetchone()
    if existing:
        if existing["store_id"] != store_id:
            raise HTTPException(409, "Shopper session is already claimed by another store")
        return {"session_id": session_id, "store_id": store_id, "claimed": True, "already_claimed": True}
    with db:
        db.execute("INSERT INTO associate_claims(session_id, store_id, token_hash, created_at) VALUES (?, ?, ?, ?)", (session_id, store_id, token_hash, now_iso()))
    return {"session_id": session_id, "store_id": store_id, "claimed": True, "already_claimed": False}


@app.get("/api/associate/dashboard")
def associate_dashboard(authorization: Optional[str] = Header(default=None), db: sqlite3.Connection = Depends(get_db)):
    store_id = _associate(authorization, db)
    rows = db.execute("SELECT session_id, handoff_code, state_json, created_at, updated_at, finalized FROM shopper_sessions ORDER BY updated_at DESC LIMIT 30").fetchall()
    sessions = [{"session_id": r["session_id"], "handoff_code": r["handoff_code"], "persona": _read_json(r["state_json"]).get("persona"), "blind_pick_sku_id": _read_json(r["state_json"]).get("blind_pick_sku_id"), "updated_at": r["updated_at"], "finalized": bool(r["finalized"])} for r in rows]
    totals = db.execute("SELECT COUNT(*) AS sessions, SUM(finalized) AS handoffs FROM shopper_sessions").fetchone()
    actions = {r["action"]: r["count"] for r in db.execute("SELECT action, COUNT(*) AS count FROM associate_interactions GROUP BY action").fetchall()}
    return {"store_id": store_id, "sessions": sessions, "metrics": {"sessions": totals["sessions"] or 0, "handoffs": totals["handoffs"] or 0, "trials": actions.get("trial", 0), "quotes": actions.get("quote", 0), "purchases": actions.get("purchase", 0), "follow_ups": actions.get("follow_up", 0)}, "generated_at": now_iso()}


@app.get("/api/associate/lookup/{code}")
def associate_lookup(code: str, authorization: Optional[str] = Header(default=None), db: sqlite3.Connection = Depends(get_db)):
    _associate(authorization, db)
    row = db.execute("SELECT session_id FROM shopper_sessions WHERE handoff_code = ? OR session_id = ?", (code.upper(), code)).fetchone()
    if row is None:
        raise HTTPException(404, "Shopper session not found; try the cached kiosk session or rescan its QR code")
    state = _session(db, row["session_id"])
    if not state.get("handoff"):
        raise HTTPException(409, "Shopper has not generated a handoff for this session")
    if state.get("blind_pick_sku_id"):
        state["blind_pick"] = _sku(db, state["blind_pick_sku_id"])
    state["proof_receipt"] = proof_receipt(state["session_id"], db)
    state["loadout"] = loadout(state["session_id"], None, db) if state.get("budget_ceiling") and state.get("blind_pick_sku_id") else None
    state["checklist"] = _read_json((db.execute("SELECT checklist_json FROM associate_checklists WHERE session_id = ?", (state["session_id"],)).fetchone() or {"checklist_json": "{}"})["checklist_json"])
    return state


@app.post("/api/associate/compare")
def associate_compare(payload: CompareRequest, authorization: Optional[str] = Header(default=None), db: sqlite3.Connection = Depends(get_db)):
    _associate(authorization, db)
    if len(set(payload.sku_ids)) != len(payload.sku_ids):
        raise HTTPException(422, "Choose distinct laptop SKUs")
    return {"items": [_sku(db, sku_id) for sku_id in payload.sku_ids], "fairness_notice": "Exact SKU configurations are compared side by side. No performance score is inferred from brand or processor name.", "generated_at": now_iso()}


@app.patch("/api/associate/sessions/{session_id}/checklist")
def update_checklist(session_id: str, payload: ChecklistUpdate, authorization: Optional[str] = Header(default=None), db: sqlite3.Connection = Depends(get_db)):
    _associate(authorization, db)
    _session(db, session_id)
    allowed = {"power_on", "wifi", "camera", "audio", "keyboard", "local_demo", "ports", "customer_questions"}
    if not set(payload.states).issubset(allowed):
        raise HTTPException(422, "Unknown physical demo checklist item")
    old_row = db.execute("SELECT checklist_json FROM associate_checklists WHERE session_id = ?", (session_id,)).fetchone()
    states = _read_json(old_row["checklist_json"]) if old_row else {}
    states.update(payload.states)
    with db:
        db.execute("INSERT INTO associate_checklists(session_id, checklist_json, updated_at) VALUES (?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET checklist_json=excluded.checklist_json, updated_at=excluded.updated_at", (session_id, _json(states), now_iso()))
    return {"session_id": session_id, "states": states, "updated_at": now_iso()}


@app.post("/api/associate/sessions/{session_id}/complete", status_code=201)
def complete_interaction(session_id: str, payload: CompleteInteraction, authorization: Optional[str] = Header(default=None), db: sqlite3.Connection = Depends(get_db)):
    store_id = _associate(authorization, db)
    state = _session(db, session_id)
    if payload.selected_sku_id:
        _sku(db, payload.selected_sku_id)
    interaction_id, ts = str(uuid4()), now_iso()
    with db:
        db.execute("INSERT INTO associate_interactions(interaction_id, session_id, store_id, action, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?)", (interaction_id, session_id, store_id, payload.action, _json({"note": payload.note, "selected_sku_id": payload.selected_sku_id}), ts))
        state["retail_action"] = payload.action
        _store_state(db, state)
    return {"interaction_id": interaction_id, "session_id": session_id, "action": payload.action, "selected_sku_id": payload.selected_sku_id, "recorded_at": ts}
