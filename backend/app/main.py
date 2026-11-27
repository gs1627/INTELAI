from __future__ import annotations

import hashlib
import hmac
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
from statistics import median

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .db import DB_MODE, DB_PERSISTENT, connect, get_db, init_db, now_iso
from .schemas import (
    AssociateLogin, BenchmarkResultSubmission, BlindPick, ChecklistUpdate, ClaimHandoff, CompareRequest, CompleteInteraction,
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


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


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
    return {"session_id": row["session_id"], **_read_json(row["state_json"]), "created_at": row["created_at"], "updated_at": row["updated_at"], "finalized": bool(row["finalized"])}


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


def _make_handoff_code() -> str:
    return secrets.token_urlsafe(32)


def _demo_auth_enabled() -> bool:
    default = "false" if os.getenv("VERCEL") else "true"
    return os.getenv("ARENA_DEMO_AUTH_ENABLED", default).strip().lower() in {"1", "true", "yes", "on"}


def _claim_store(db: sqlite3.Connection, session_id: str, store_id: str) -> None:
    claim = db.execute("SELECT store_id FROM associate_claims WHERE session_id = ?", (session_id,)).fetchone()
    if not claim or claim["store_id"] != store_id:
        raise HTTPException(403, "This customer session is not claimed by your store")


def _rate_limit_lookup(db: sqlite3.Connection, store_id: str, client_host: str) -> None:
    import time
    bucket = str(int(time.time()) // 60)
    key_hash = hashlib.sha256(f"{store_id}:{client_host}".encode()).hexdigest()
    with db:
        db.execute("DELETE FROM lookup_rate_windows WHERE window_bucket <> ?", (bucket,))
        db.execute("INSERT INTO lookup_rate_windows(key_hash, window_bucket, attempts) VALUES (?, ?, 1) ON CONFLICT(key_hash, window_bucket) DO UPDATE SET attempts=lookup_rate_windows.attempts+1", (key_hash, bucket))
    row = db.execute("SELECT attempts FROM lookup_rate_windows WHERE key_hash = ? AND window_bucket = ?", (key_hash, bucket)).fetchone()
    if row and row["attempts"] > 8:
        raise HTTPException(429, "Too many handoff lookups; try again in a minute")


def _associate(authorization: Optional[str], db: sqlite3.Connection) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Associate login required")
    token = authorization.split(" ", 1)[1].strip()
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.execute("SELECT store_id, expires_at FROM associate_tokens WHERE token_hash = ?", (digest,)).fetchone()
    if not row or row["expires_at"] <= now_iso():
        raise HTTPException(401, "Associate demo session expired")
    return row["store_id"]


def _handoff_session(db: sqlite3.Connection, code: str) -> dict[str, Any]:
    if len(code) < 24 or len(code) > 100:
        raise HTTPException(404, "Handoff not found or expired")
    digest = hashlib.sha256(code.encode()).hexdigest()
    row = db.execute("SELECT session_id, handoff_expires_at FROM shopper_sessions WHERE handoff_token_hash = ?", (digest,)).fetchone()
    if not row or not row["handoff_expires_at"] or row["handoff_expires_at"] <= now_iso():
        raise HTTPException(404, "Handoff not found or expired")
    return _session(db, row["session_id"])


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
        "database_persistent": DB_PERSISTENT,
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
def laptops(brand: Optional[str] = Query(default=None, max_length=40), db: sqlite3.Connection = Depends(get_db)):
    items = _catalog(db)
    if brand:
        items = [item for item in items if item.get("brand", "").casefold() == brand.casefold()]
    return {"items": items, "count": len(items), "currency": "INR", "generated_at": now_iso(), "price_notice": "Seed prices are source snapshots, not live quotes or inventory. Confirm price and stock with seller."}


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
    ts = now_iso()
    try:
        with db:
            db.execute("INSERT INTO shopper_sessions (session_id, handoff_code, handoff_token_hash, state_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (sid, f"retired-{sid}", None, _json(state), ts, ts))
    except Exception as exc:
        if isinstance(exc, sqlite3.IntegrityError) or getattr(exc, "sqlstate", None) == "23505":
            raise HTTPException(409, "Session could not be created") from exc
        raise
    return {"session_id": sid, **state, "created_at": ts, "updated_at": ts}


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
    # In production, loopback belongs to the serverless function, not the shopper's PC.
    if not runner_url or os.getenv("VERCEL") or mission_id != "nova_campus_rush":
        return None
    # The unchanged local companion accepts a fixed, synthetic prompt plus a provider.
    # Do not pass shopper text to it; normalize its legacy response and verify nothing
    # unless it independently supplies signed evidence under the v1 contract.
    payload = {"prompt": "Summarize the fixed synthetic NOVA campus lecture notes into three study bullets.", "provider": "CPU"}
    request = urllib.request.Request(runner_url.rstrip("/") + "/relay", data=_json(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=2.5) as response:
            if response.status != 200:
                return None
            result = json.loads(response.read(1_000_000).decode("utf-8"))
            if not isinstance(result, dict):
                return None
            if result.get("execution") == "NOT VERIFIED":
                return {"contract_version": "arena-relay-v1", "mission_id": "nova_campus_rush", "execution_provider": "UNKNOWN", "verification_status": "NOT VERIFIED", "result_status": "PARTIAL", "result": result.get("detail", "Runner did not verify execution."), "signature_verified": False}
            result["signature_verified"] = _verify_runner_signature(result)
            return result
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _runner_signature_fields(result: dict[str, Any]) -> dict[str, Any]:
    names = ("contract_version", "mission_id", "execution_provider", "device_name", "runtime_version", "model_id", "model_hash", "input_hash", "prompt_hash", "benchmark_version", "duration_ms", "result_status", "verification_status", "measurement_conditions", "measured_at", "result")
    return {key: result.get(key) for key in names}


def _verify_runner_signature(result: dict[str, Any]) -> bool:
    key = os.getenv("ARENA_RUNNER_VERIFY_KEY", "").encode()
    signature = result.get("signature")
    if not key or not isinstance(signature, str):
        return False
    digest = hmac.new(key, _json(_runner_signature_fields(result)).encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def _simulation_result(session_id: str, mission_id: str, airplane_mode: bool) -> dict[str, Any]:
    return {
        "mission_id": mission_id,
        "contract_version": "arena-relay-v1",
        "execution_mode": "NOT VERIFIED",
        "badge": "DEMO / NOT VERIFIED",
        "verified_hardware": False,
        "simulated": True,
        "network_state": "UNKNOWN",
        "execution_location": "NOT VERIFIED",
        "compute_engine": "UNKNOWN",
        "result_status": "NOT RUN",
        "duration_ms": None,
        "model_id": None,
        "model_hash": None,
        "input_hash": None,
        "prompt_hash": None,
        "benchmark_version": None,
        "measurement_conditions": None,
        "measured_at": None,
        "outcome": "No validated hardware result is available in this session.",
        "timing_notice": "No hardware timing was recorded.",
    }


@app.post("/api/sessions/{session_id}/run-mission", status_code=201)
def run_mission(session_id: str, payload: MissionRequest, db: sqlite3.Connection = Depends(get_db)):
    _session(db, session_id)
    runner = _runner_result(session_id, payload.mission_id, payload.airplane_mode)
    if runner is None:
        result = _simulation_result(session_id, payload.mission_id, payload.airplane_mode)
    else:
        engine = str(runner.get("execution_provider", "UNKNOWN")).upper()
        hash_fields = all(isinstance(runner.get(key), str) and len(runner[key]) == 64 for key in ("model_hash", "input_hash", "prompt_hash"))
        verified = (
            runner.get("contract_version") == "arena-relay-v1"
            and runner.get("mission_id") == "nova_campus_rush"
            and runner.get("verification_status") == "VERIFIED"
            and runner.get("result_status") == "COMPLETED"
            and runner.get("signature_verified") is True
            and engine in {"CPU", "NPU"}
            and isinstance(runner.get("duration_ms"), int) and runner["duration_ms"] > 0
            and isinstance(runner.get("device_name"), str) and bool(runner["device_name"])
            and isinstance(runner.get("runtime_version"), str) and bool(runner["runtime_version"])
            and isinstance(runner.get("model_id"), str) and bool(runner["model_id"])
            and hash_fields
            and isinstance(runner.get("benchmark_version"), str)
            and isinstance(runner.get("measurement_conditions"), dict)
            and isinstance(runner.get("measured_at"), str)
        )
        badge = "DEMO / NOT VERIFIED"
        if verified and engine == "NPU":
            badge = "NPU-ACCELERATED"
        elif verified and engine == "CPU":
            badge = "CPU/GPU LOCAL"
        result = {
            "mission_id": payload.mission_id, "contract_version": runner.get("contract_version"), "execution_mode": "LOCAL" if verified else "NOT VERIFIED",
            "badge": badge, "verified_hardware": verified, "simulated": not verified,
            "network_state": "UNKNOWN",
            "execution_location": "LOCAL DEVICE" if verified else "UNVERIFIED RUNNER RESPONSE",
            "compute_engine": engine if verified else "UNKNOWN", "cloud": {"available": False, "label": "NOT RUN"},
            "duration_ms": runner.get("duration_ms") if verified else None,
            "local": {"available": True, "duration_ms": runner.get("duration_ms") if verified else None, "label": "LIVE SESSION" if verified else "NOT VERIFIED"},
            "device_name": runner.get("device_name"), "runtime_version": runner.get("runtime_version"),
            "model_id": runner.get("model_id"), "model_hash": runner.get("model_hash"),
            "input_hash": runner.get("input_hash"), "prompt_hash": runner.get("prompt_hash"),
            "benchmark_version": runner.get("benchmark_version"), "measurement_conditions": runner.get("measurement_conditions"),
            "measured_at": runner.get("measured_at"), "result_status": runner.get("result_status", "PARTIAL"),
            "outcome": runner.get("result") if verified else "Runner did not provide complete, signed verification evidence.",
            "timing_notice": "Timing is displayed only after the runner signature and required execution evidence are verified.",
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
        "badge": (mission or {}).get("badge", "DEMO / NOT VERIFIED"),
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


def _benchmark_admin(authorization: Optional[str]) -> None:
    expected = os.getenv("ARENA_BENCHMARK_INGEST_TOKEN", "")
    supplied = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else ""
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        raise HTTPException(401, "Benchmark ingestion is not enabled or authorized")


@app.get("/api/benchmarks")
def benchmark_definitions(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT test_id, round_id, benchmark_version, task_definition, model_id, model_hash, prompt_hash, input_hash, metric_name, metric_unit, lower_is_better, approved FROM benchmark_definitions ORDER BY test_id").fetchall()
    return {"items": [dict(row) for row in rows], "generated_at": now_iso(), "notice": "No result is shown as historical verified until a controlled test definition has been approved."}


@app.post("/api/benchmarks/results", status_code=201)
def submit_benchmark_result(payload: BenchmarkResultSubmission, authorization: Optional[str] = Header(default=None), db: sqlite3.Connection = Depends(get_db)):
    _benchmark_admin(authorization)
    definition = db.execute("SELECT * FROM benchmark_definitions WHERE test_id=?", (payload.test_id,)).fetchone()
    sku = db.execute("SELECT sku_id FROM laptops WHERE sku_id=?", (payload.sku_id,)).fetchone()
    if not definition or not sku:
        raise HTTPException(422, "Unknown benchmark definition or exact SKU")
    if definition["model_id"] and payload.model_id != definition["model_id"]:
        raise HTTPException(422, "Result model does not match the benchmark definition")
    for column, value in (("model_hash", payload.model_hash.lower()), ("input_hash", payload.input_hash.lower()), ("prompt_hash", payload.prompt_hash.lower())):
        if definition[column] and definition[column].lower() != value:
            raise HTTPException(422, f"Result {column} does not match the established benchmark protocol")
    signed_fields = payload.model_dump()
    evidence = dict(signed_fields.pop("evidence"))
    signature = evidence.pop("signature", None)
    signed_fields.update({"contract_version": "arena-benchmark-v1", "evidence": evidence})
    key = os.getenv("ARENA_RUNNER_VERIFY_KEY", "").encode()
    expected = hmac.new(key, _canonical_json(signed_fields).encode(), hashlib.sha256).hexdigest() if key else ""
    if not isinstance(signature, str) or not expected or not hmac.compare_digest(expected, signature):
        raise HTTPException(422, "Benchmark evidence signature is missing or invalid")
    if payload.execution_provider == "NPU":
        if not payload.model_id or (definition["model_hash"] and payload.model_hash.lower() != definition["model_hash"].lower()):
            raise HTTPException(422, "NPU result must match the established exact model hash")
        if payload.evidence.get("runtime_verified") is not True or payload.evidence.get("device_name") != payload.device_name:
            raise HTTPException(422, "NPU result requires signed device and runtime verification evidence")
    with db:
        if not definition["model_hash"] and definition["model_id"]:
            db.execute("UPDATE benchmark_definitions SET model_hash=?, input_hash=?, prompt_hash=? WHERE test_id=? AND model_hash IS NULL", (payload.model_hash.lower(), payload.input_hash.lower(), payload.prompt_hash.lower(), payload.test_id))
        db.execute("INSERT INTO benchmark_sessions (benchmark_session_id, sku_id, test_date, device_name, os_version, runtime_version, power_mode, ac_power, bios_version, driver_version, environment_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(benchmark_session_id) DO NOTHING", (payload.benchmark_session_id, payload.sku_id, payload.test_date, payload.device_name, payload.os_version, payload.runtime_version, payload.power_mode, int(payload.ac_power), payload.bios_version, payload.driver_version, _json(payload.evidence), now_iso()))
        db.execute("INSERT INTO benchmark_results (result_id, benchmark_session_id, test_id, run_index, metric_value, result_status, execution_provider, model_hash, input_hash, prompt_hash, runtime_version, verification_status, evidence_json, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (payload.result_id, payload.benchmark_session_id, payload.test_id, payload.run_index, payload.metric_value, payload.result_status, payload.execution_provider, payload.model_hash.lower(), payload.input_hash.lower(), payload.prompt_hash.lower(), payload.runtime_version, "VERIFIED", _json({**payload.evidence, "signature_verified": True}), payload.measurement_timestamp))
    return {"result_id": payload.result_id, "verification_status": "VERIFIED", "approved_for_comparison": bool(definition["approved"])}


@app.post("/api/benchmarks/{test_id}/approve")
def approve_benchmark(test_id: str, authorization: Optional[str] = Header(default=None), db: sqlite3.Connection = Depends(get_db)):
    _benchmark_admin(authorization)
    definition = db.execute("SELECT test_id FROM benchmark_definitions WHERE test_id=?", (test_id,)).fetchone()
    if not definition:
        raise HTTPException(404, "Benchmark definition not found")
    count = db.execute("SELECT COUNT(DISTINCT benchmark_session_id) AS n FROM benchmark_results WHERE test_id=? AND verification_status='VERIFIED' AND result_status='COMPLETED'", (test_id,)).fetchone()["n"]
    if count < 3:
        raise HTTPException(409, "At least three verified benchmark sessions are required before approval")
    with db:
        db.execute("UPDATE benchmark_definitions SET approved=1 WHERE test_id=?", (test_id,))
    return {"test_id": test_id, "approved": True, "verified_sessions": count}


@app.get("/api/comparisons")
def compare_benchmarks(sku_ids: list[str] = Query(min_length=2, max_length=4), db: sqlite3.Connection = Depends(get_db)):
    if len(set(sku_ids)) != len(sku_ids):
        raise HTTPException(422, "Choose distinct exact laptop SKUs")
    items = [_sku(db, sku_id) for sku_id in sku_ids]
    if len({item.get("brand") for item in items}) != 1:
        raise HTTPException(422, "Only same-brand exact SKU comparisons are supported")
    rows = db.execute("SELECT d.test_id, d.round_id, d.benchmark_version, d.metric_name, d.metric_unit, d.lower_is_better, s.sku_id, r.metric_value FROM benchmark_definitions d JOIN benchmark_results r ON r.test_id=d.test_id JOIN benchmark_sessions s ON s.benchmark_session_id=r.benchmark_session_id WHERE d.approved=1 AND r.verification_status='VERIFIED' AND r.result_status='COMPLETED' AND s.sku_id IN (" + ",".join("?" for _ in sku_ids) + ") ORDER BY d.test_id", tuple(sku_ids)).fetchall()
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        group = groups.setdefault(row["test_id"], {"test_id": row["test_id"], "round_id": row["round_id"], "benchmark_version": row["benchmark_version"], "metric_name": row["metric_name"], "metric_unit": row["metric_unit"], "lower_is_better": bool(row["lower_is_better"]), "values": {}})
        group["values"].setdefault(row["sku_id"], []).append(row["metric_value"])
    rounds = []
    for group in groups.values():
        rounds.append({**{k: v for k, v in group.items() if k != "values"}, "results": [{"sku_id": sku, "median": median(group["values"][sku]), "verified_runs": len(group["values"][sku]), "source": "HISTORICAL VERIFIED"} for sku in sku_ids if sku in group["values"]]})
    return {"sku_ids": sku_ids, "rounds": rounds, "notice": "Only approved, compatible, signed results are returned. Missing results mean no verified comparison is available.", "generated_at": now_iso()}


@app.get("/api/sessions/{session_id}/handoff/qr")
def handoff_qr(session_id: str, request: Request, code: str = Query(default="", max_length=100), db: sqlite3.Connection = Depends(get_db)):
    state = _handoff_session(db, code)
    if state["session_id"] != session_id:
        raise HTTPException(404, "Handoff not found or expired")
    import qrcode
    from qrcode.image.svg import SvgPathImage

    buffer = io.BytesIO()
    public_url = os.getenv("ARENA_PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    qrcode.make(f"{public_url}/associate?code={code}", image_factory=SvgPathImage, box_size=8, border=2).save(buffer)
    return Response(content=buffer.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


@app.post("/api/sessions/{session_id}/handoff")
def finalize_handoff(session_id: str, request: Request, payload: Optional[HandoffRequest] = None, db: sqlite3.Connection = Depends(get_db)):
    state = _session(db, session_id)
    code = _make_handoff_code()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds").replace("+00:00", "Z")
    digest = hashlib.sha256(code.encode()).hexdigest()
    public_url = os.getenv("ARENA_PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    qr_payload = {"code": code, "path": f"{public_url}/associate?code={code}"}
    with db:
        db.execute("UPDATE shopper_sessions SET finalized = 1, handoff_token_hash = ?, handoff_expires_at = ?, updated_at = ? WHERE session_id = ?", (digest, expires, now_iso(), session_id))
        state["handoff"] = {"created_at": now_iso(), "expires_at": expires}
        _store_state(db, state)
    return {"session_id": session_id, "handoff_code": code, "qr_payload": qr_payload, "expires_at": expires, "finalized": True, "privacy": "QR payload contains only an opaque, expiring session lookup token."}


@app.post("/api/associate/login")
def associate_login(payload: AssociateLogin, db: sqlite3.Connection = Depends(get_db)):
    if not _demo_auth_enabled() or not payload.demo_login:
        raise HTTPException(401, "Associate authentication is not configured for this deployment")
    store_id = payload.store_id or "DEMO-STORE"
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(timespec="seconds").replace("+00:00", "Z")
    digest = hashlib.sha256(token.encode()).hexdigest()
    with db:
        db.execute("INSERT INTO associate_tokens(token_hash, store_id, expires_at, created_at) VALUES (?, ?, ?, ?)", (digest, store_id, expires, now_iso()))
    return {"access_token": token, "token_type": "bearer", "store_id": store_id, "expires_at": expires, "demo_auth": True}


@app.post("/api/associate/sessions/{session_id}/claim")
def claim_session(session_id: str, payload: ClaimHandoff, authorization: Optional[str] = Header(default=None), db: sqlite3.Connection = Depends(get_db)):
    store_id = _associate(authorization, db)
    state = _handoff_session(db, payload.handoff_code)
    if state["session_id"] != session_id:
        raise HTTPException(404, "Handoff not found or expired")
    token = authorization.split(" ", 1)[1].strip()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    existing = db.execute("SELECT store_id FROM associate_claims WHERE session_id = ?", (session_id,)).fetchone()
    if existing:
        if existing["store_id"] != store_id:
            raise HTTPException(409, "Shopper session is already claimed by another store")
        return {"session_id": session_id, "store_id": store_id, "claimed": True, "already_claimed": True}
    with db:
        db.execute("INSERT INTO associate_claims(session_id, store_id, token_hash, created_at) VALUES (?, ?, ?, ?) ON CONFLICT(session_id) DO NOTHING", (session_id, store_id, token_hash, now_iso()))
    existing = db.execute("SELECT store_id FROM associate_claims WHERE session_id = ?", (session_id,)).fetchone()
    if existing["store_id"] != store_id:
        raise HTTPException(409, "Shopper session is already claimed by another store")
    return {"session_id": session_id, "store_id": store_id, "claimed": True, "already_claimed": False}


@app.get("/api/associate/dashboard")
def associate_dashboard(authorization: Optional[str] = Header(default=None), db: sqlite3.Connection = Depends(get_db)):
    store_id = _associate(authorization, db)
    rows = db.execute("SELECT s.session_id, s.state_json, s.updated_at, s.finalized FROM shopper_sessions s JOIN associate_claims c ON c.session_id=s.session_id WHERE c.store_id=? ORDER BY s.updated_at DESC LIMIT 30", (store_id,)).fetchall()
    sessions = [{"session_id": r["session_id"], "persona": _read_json(r["state_json"]).get("persona"), "blind_pick_sku_id": _read_json(r["state_json"]).get("blind_pick_sku_id"), "updated_at": r["updated_at"], "finalized": bool(r["finalized"])} for r in rows]
    totals = db.execute("SELECT COUNT(*) AS sessions, SUM(s.finalized) AS handoffs FROM shopper_sessions s JOIN associate_claims c ON c.session_id=s.session_id WHERE c.store_id=?", (store_id,)).fetchone()
    actions = {r["action"]: r["count"] for r in db.execute("SELECT action, COUNT(*) AS count FROM associate_interactions WHERE store_id=? GROUP BY action", (store_id,)).fetchall()}
    return {"store_id": store_id, "sessions": sessions, "metrics": {"sessions": totals["sessions"] or 0, "handoffs": totals["handoffs"] or 0, "trials": actions.get("trial", 0), "quotes": actions.get("quote", 0), "purchases": actions.get("purchase", 0), "follow_ups": actions.get("follow_up", 0)}, "generated_at": now_iso()}


@app.get("/api/associate/lookup/{code}")
def associate_lookup(code: str, request: Request, authorization: Optional[str] = Header(default=None), db: sqlite3.Connection = Depends(get_db)):
    store_id = _associate(authorization, db)
    _rate_limit_lookup(db, store_id, request.client.host if request.client else "unknown")
    state = _handoff_session(db, code)
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
    store_id = _associate(authorization, db)
    _claim_store(db, session_id, store_id)
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
    _claim_store(db, session_id, store_id)
    state = _session(db, session_id)
    if payload.selected_sku_id:
        _sku(db, payload.selected_sku_id)
    interaction_id, ts = str(uuid4()), now_iso()
    with db:
        db.execute("INSERT INTO associate_interactions(interaction_id, session_id, store_id, action, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?)", (interaction_id, session_id, store_id, payload.action, _json({"note": payload.note, "selected_sku_id": payload.selected_sku_id}), ts))
        state["retail_action"] = payload.action
        _store_state(db, state)
    return {"interaction_id": interaction_id, "session_id": session_id, "action": payload.action, "selected_sku_id": payload.selected_sku_id, "recorded_at": ts}
