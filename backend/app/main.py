import os
import hashlib
import secrets
from datetime import timedelta
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session
from . import models
from .db import Base, engine, get_db
from .schemas import BenchmarkIn, BenchmarkOut, EventIn, SessionIn

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Intel AI PC Arena API", version="1.0.0")
origins = [x.strip() for x in os.getenv("ARENA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET","POST","PATCH","DELETE","OPTIONS"], allow_headers=["Content-Type","Authorization","X-Admin-Token"])

def _now(): return datetime.now(timezone.utc)
def _hash(value: str): return hashlib.sha256(value.encode()).hexdigest()
def _event(db, sid, kind, details=None):
    db.add(models.SessionHistory(id=str(uuid4()), session_id=sid, event_type=kind, details=details or {}))

def _session(db, sid):
    row = db.get(models.GameSession, sid)
    if not row or (row.expires_at and row.expires_at < _now()): raise HTTPException(404, "Session not found or expired")
    return row

@app.get("/health")
def health(): return {"ok": True, "service": "arena-api", "version": "0.1.0"}

@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    try: db.execute(select(1)); return {"ok": True, "database": "ready"}
    except Exception: raise HTTPException(503, "Database unavailable")

@app.post("/sessions", status_code=201)
def create_session(payload: SessionIn, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"session_id"})
    sid = payload.session_id or str(uuid4())
    row = db.get(models.GameSession, sid)
    if row:
        if row.expires_at and row.expires_at < _now(): raise HTTPException(410, "Session expired")
        for key, value in data.items():
            if value is not None and value != "": setattr(row, key, value)
    else:
        row = models.GameSession(session_id=sid, **data, expires_at=_now()+timedelta(hours=24))
        db.add(row)
    _event(db, sid, "SESSION_CREATED" if not row.start_time else "SESSION_UPDATED", {"persona": data.get("persona", "")})
    db.commit()
    return {"session_id": row.session_id, "created": True, "expires_at": row.expires_at}

@app.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    row = _session(db, session_id)
    return {k: getattr(row, k) for k in ("session_id","current_laptop_id","persona","budget","priority","priorities","workloads","preferred_features","portability","start_time","expires_at")}

@app.patch("/sessions/{session_id}")
def update_session(session_id: str, payload: SessionIn, db: Session = Depends(get_db)):
    row = _session(db, session_id)
    for key, value in payload.model_dump(exclude={"session_id"}, exclude_unset=True).items(): setattr(row, key, value)
    _event(db, session_id, "SESSION_UPDATED", payload.model_dump(exclude_none=True)); db.commit(); return {"session_id": session_id, "updated": True}

@app.get("/sessions/{session_id}/history")
def session_history(session_id: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    _session(db, session_id)
    rows = db.scalars(select(models.SessionHistory).where(models.SessionHistory.session_id==session_id).order_by(models.SessionHistory.created_at.desc()).offset(offset).limit(limit)).all()
    return {"items": [{"event_type":r.event_type,"details":r.details,"created_at":r.created_at} for r in rows], "limit":limit,"offset":offset}

@app.post("/sessions/{session_id}/handoff", status_code=201)
def create_handoff(session_id: str, db: Session = Depends(get_db)):
    _session(db, session_id); token=secrets.token_urlsafe(32); expiry=_now()+timedelta(minutes=10)
    db.add(models.HandoffToken(token_hash=_hash(token),session_id=session_id,expires_at=expiry)); _event(db,session_id,"HANDOFF_CREATED"); db.commit()
    base=os.getenv("ARENA_PUBLIC_URL","http://localhost:5173").rstrip("/")
    return {"url":f"{base}/associate/handoff?token={token}","expires_at":expiry}

@app.post("/handoffs/redeem")
def redeem_handoff(token: str, db: Session = Depends(get_db)):
    row=db.get(models.HandoffToken,_hash(token))
    if not row or row.redeemed_at or row.expires_at < _now(): raise HTTPException(410,"Handoff token invalid, expired, or already used")
    row.redeemed_at=_now(); _event(db,row.session_id,"HANDOFF_REDEEMED"); db.commit()
    s=_session(db,row.session_id)
    return {"session_id":s.session_id,"persona":s.persona,"budget":s.budget,"priority":s.priority,"workloads":s.workloads}

@app.get("/products")
def products(limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0), include_samples:bool=True, db:Session=Depends(get_db)):
    q=select(models.Product)
    if not include_samples: q=q.where(models.Product.is_sample.is_(False))
    rows=db.scalars(q.offset(offset).limit(limit)).all()
    return {"items":[{c:getattr(x,c) for c in ("product_id","brand","model","processor","ram_gb","storage_gb","display","battery","price","currency","ai_pc","source","verification_status","is_sample")} for x in rows],"limit":limit,"offset":offset,"total":db.scalar(select(func.count()).select_from(models.Product))}

@app.post("/products",status_code=201)
def add_product(payload:dict, x_admin_token:str|None=Header(default=None), db:Session=Depends(get_db)):
    require_admin(x_admin_token)
    required={"product_id","brand","model","processor","source","verification_status"}
    if not required.issubset(payload): raise HTTPException(422,"Missing required product fields")
    row=models.Product(**payload,is_sample=False); db.add(row); db.commit(); return {"product_id":row.product_id}

@app.post("/sessions/{session_id}/recommendations")
def recommend(session_id:str, db:Session=Depends(get_db)):
    s=_session(db,session_id); rows=db.scalars(select(models.Product).where(models.Product.price.is_not(None),models.Product.is_sample.is_(True))).all()
    affordable=[p for p in rows if p.price<= (s.budget or 200000)]
    if not affordable: return {"recommendations":[]}
    best=min(affordable,key=lambda p:abs((s.budget or p.price)-p.price)); value=min(affordable,key=lambda p:p.price)
    ai=[p for p in affordable if p.ai_pc]; ai_pick=min(ai,key=lambda p:abs((s.budget or p.price)-p.price)) if ai else None
    recs=[]
    for label,p in (("Best Match",best),("Best Value",value),("AI-Ready Option",ai_pick)):
        if p: recs.append({"category":label,"product_id":p.product_id,"brand":p.brand,"model":p.model,"price":p.price,"reasons":[f"Within stated budget of ₹{s.budget or 200000:,}"],"limitations":["Demonstration catalogue; confirm current specifications and price with seller."],"trade_offs":"Recommendation reflects listed fields only; no comparative benchmark claim."})
    db.add(models.RecommendationResult(session_id=session_id,recommended_laptop_ids=[x["product_id"] for x in recs],reason_codes=[x["category"] for x in recs])); db.commit()
    return {"recommendations":recs}

@app.get("/inventory")
def inventory(db:Session=Depends(get_db)):
    rows=db.execute(select(models.Inventory,models.Product).join(models.Product)).all()
    return {"label":"DEMO INVENTORY — NOT RETAIL STOCK","items":[{"inventory_id":i.inventory_id,"product_id":i.product_id,"brand":p.brand,"model":p.model,"location":i.location,"available":i.quantity} for i,p in rows]}

@app.post("/reservations",status_code=201)
def reserve(session_id:str, inventory_id:str, quantity:int=Query(1,ge=1,le=5), db:Session=Depends(get_db)):
    _session(db,session_id)
    try:
        with db.begin_nested():
            result=db.execute(update(models.Inventory).where(models.Inventory.inventory_id==inventory_id,models.Inventory.quantity>=quantity).values(quantity=models.Inventory.quantity-quantity))
            if not result.rowcount: raise HTTPException(409,"Insufficient demo inventory")
            row=models.Reservation(reservation_id=str(uuid4()),session_id=session_id,inventory_id=inventory_id,quantity=quantity,expires_at=_now()+timedelta(minutes=30)); db.add(row)
        db.commit(); return {"reservation_id":row.reservation_id,"status":row.status,"expires_at":row.expires_at,"inventory_label":"DEMO INVENTORY"}
    except HTTPException: db.rollback(); raise

@app.post("/reservations/{reservation_id}/cancel")
def cancel_reservation(reservation_id:str,db:Session=Depends(get_db)):
    r=db.get(models.Reservation,reservation_id)
    if not r: raise HTTPException(404,"Reservation not found")
    if r.status!="CONFIRMED": raise HTTPException(409,"Reservation is not active")
    inv=db.get(models.Inventory,r.inventory_id); inv.quantity+=r.quantity; r.status="CANCELLED"; db.commit(); return {"reservation_id":r.reservation_id,"status":r.status}

@app.post("/demos",status_code=201)
def record_demo(payload:dict,db:Session=Depends(get_db)):
    s=_session(db,payload.get("session_id","")); workload=payload.get("workload")
    if workload not in {"Study Sprint","Meeting Makeover","Creator Quick-Fix"}: raise HTTPException(422,"Unknown workload")
    mode=payload.get("execution_mode")
    if mode not in {"LOCAL","CLOUD","ILLUSTRATIVE_SIMULATION"}: raise HTTPException(422,"Invalid execution mode")
    row=models.DemoResult(demo_id=str(uuid4()),session_id=s.session_id,workload=workload,input_reference=payload.get("input_reference",""),output=payload.get("output",{}),execution_mode=mode); db.add(row); _event(db,s.session_id,"DEMO_COMPLETED",{"workload":workload,"execution_mode":mode}); db.commit()
    return {"demo_id":row.demo_id,"workload":workload,"execution_mode":mode,"created_at":row.created_at}

@app.post("/events", status_code=201)
def collect_event(payload: EventIn, db: Session = Depends(get_db)):
    if not db.get(models.GameSession, payload.session_id): raise HTTPException(404, "Unknown anonymous session")
    if db.get(models.RoundEvent, payload.event_id): raise HTTPException(409, "Duplicate event")
    row = models.RoundEvent(event_id=payload.event_id, **payload.model_dump(exclude={"event_id"}))
    db.add(row); _event(db,payload.session_id,"ROUND_EVENT",{"round_id":payload.round_id,"outcome":payload.outcome}); db.commit(); return {"event_id": row.event_id, "stored": True, "benchmark_eligible": False}

@app.get("/benchmarks", response_model=list[BenchmarkOut])
def benchmarks(brand: str = Query(min_length=2, max_length=30), tier: int | None = Query(default=None, ge=5, le=9), series: int | None = Query(default=None, ge=2, le=3), db: Session = Depends(get_db)):
    stmt = select(models.BenchmarkResult, models.BenchmarkSession, models.Laptop, models.Processor, models.BenchmarkTest).join(models.BenchmarkSession).join(models.Laptop).join(models.Processor).join(models.BenchmarkTest).where(models.Laptop.brand == brand, models.BenchmarkResult.verification_status == "VERIFIED", models.BenchmarkResult.is_sample.is_(False))
    if tier: stmt = stmt.where(models.Processor.tier == tier)
    if series: stmt = stmt.where(models.Processor.series == series)
    rows = db.execute(stmt).all()
    return [BenchmarkOut(result_id=r.result_id,laptop_id=l.laptop_id,brand=l.brand,model_name=l.model_name,processor_sku=p.exact_sku,tier=p.tier,series=p.series,round_id=t.round_id,completion_time=r.completion_time,fps=r.fps,task_success=r.task_success,verification_status=r.verification_status,sample_count=r.sample_count,test_date=s.test_date,is_sample=r.is_sample) for r,s,l,p,t in rows]

@app.get("/sample/benchmarks")
def sample_benchmarks(brand: str = Query(min_length=2, max_length=30)):
    """Read-only illustrative fixture. It is always explicitly labelled sample data."""
    fixture = Path(__file__).resolve().parents[2] / "data" / "benchmark-fixtures" / "sample-rounds.json"
    if not fixture.exists():
        # Source checkout has the shared fixture at the project root, two levels above backend.
        fixture = Path(__file__).resolve().parents[3] / "data" / "benchmark-fixtures" / "sample-rounds.json"
    if not fixture.exists(): raise HTTPException(503, "Sample fixture unavailable")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    return {"evidence": "SAMPLE DATA", "disclaimer": payload.get("disclaimer", "Illustrative only"), "records": [r for r in payload.get("records", []) if r.get("brand") == brand]}

def require_admin(x_admin_token: str | None):
    expected = os.getenv("ARENA_ADMIN_TOKEN")
    if not expected or x_admin_token != expected: raise HTTPException(403, "Administrative access is not configured or token is invalid")

@app.post("/admin/benchmarks/{result_id}/review")
def review_benchmark(result_id: str, decision: str, x_admin_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    require_admin(x_admin_token)
    if decision not in {"APPROVE", "REJECT"}: raise HTTPException(422, "Decision must be APPROVE or REJECT")
    row = db.get(models.BenchmarkResult, result_id)
    if not row: raise HTTPException(404, "Benchmark result not found")
    # Review is not enough by itself: NPU claims require explicit runner evidence attached to metadata.
    evidence = row.benchmark_metadata or {}
    if decision == "APPROVE" and (row.is_sample or row.sample_count < 3 or (row.execution_provider == "NPU" and evidence.get("runtime_verified") is not True)):
        raise HTTPException(422, "Record lacks required validation evidence")
    row.verification_status = "VERIFIED" if decision == "APPROVE" else "REJECTED"
    db.commit(); return {"result_id": result_id, "verification_status": row.verification_status}

@app.post("/associates/register", status_code=201)
def register_associate(payload:dict, db:Session=Depends(get_db)):
    if os.getenv("ARENA_ALLOW_ASSOCIATE_REGISTRATION","false").lower()!="true": raise HTTPException(403,"Associate registration is disabled")
    username=str(payload.get("username","")); password=str(payload.get("password",""))
    if len(username)<3 or len(password)<12: raise HTTPException(422,"Username must be 3+ characters and password 12+ characters")
    if db.scalar(select(models.Associate).where(models.Associate.username==username)): raise HTTPException(409,"Username already exists")
    salt=secrets.token_hex(16); pw=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),310000).hex()
    row=models.Associate(associate_id=str(uuid4()),username=username,password_hash=salt+":"+pw); db.add(row); db.commit(); return {"associate_id":row.associate_id,"username":username}

@app.post("/associates/login")
def associate_login(payload:dict, db:Session=Depends(get_db)):
    row=db.scalar(select(models.Associate).where(models.Associate.username==str(payload.get("username",""))))
    if not row: raise HTTPException(401,"Invalid credentials")
    salt,stored=row.password_hash.split(":",1); candidate=hashlib.pbkdf2_hmac("sha256",str(payload.get("password"," ")).encode(),salt.encode(),310000).hex()
    if not secrets.compare_digest(stored,candidate): raise HTTPException(401,"Invalid credentials")
    token=secrets.token_urlsafe(36); row.token_hash=_hash(token); row.token_expires_at=_now()+timedelta(hours=8); db.commit(); return {"access_token":token,"token_type":"bearer","expires_at":row.token_expires_at}

def current_associate(authorization:str|None,db:Session):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"Associate authentication required")
    row=db.scalar(select(models.Associate).where(models.Associate.token_hash==_hash(authorization[7:])))
    if not row or not row.token_expires_at or row.token_expires_at<_now(): raise HTTPException(401,"Associate session expired")
    return row

@app.get("/associates/me")
def associate_me(authorization:str|None=Header(default=None),db:Session=Depends(get_db)):
    a=current_associate(authorization,db); return {"associate_id":a.associate_id,"username":a.username}

@app.post("/associates/interactions",status_code=201)
def associate_interaction(payload:dict,authorization:str|None=Header(default=None),db:Session=Depends(get_db)):
    a=current_associate(authorization,db); _session(db,payload.get("session_id",""))
    outcome=payload.get("outcome","Follow-up Required")
    if outcome not in {"Purchased Today","Quotation Taken","Follow-up Required"}: raise HTTPException(422,"Invalid interaction outcome")
    row=models.Interaction(interaction_id=str(uuid4()),associate_id=a.associate_id,session_id=payload["session_id"],product_id=payload.get("product_id"),reservation_id=payload.get("reservation_id"),checklist=payload.get("checklist",{}),outcome=outcome)
    db.add(row); _event(db,row.session_id,"ASSOCIATE_INTERACTION",{"outcome":outcome}); db.commit(); return {"interaction_id":row.interaction_id,"outcome":outcome}

@app.get("/reports/summary")
def reports_summary(db:Session=Depends(get_db)):
    return {"sessions":db.scalar(select(func.count()).select_from(models.GameSession)) or 0,"completed_demos":db.scalar(select(func.count()).select_from(models.DemoResult)) or 0,"reservations":db.scalar(select(func.count()).select_from(models.Reservation)) or 0,"associate_interactions":db.scalar(select(func.count()).select_from(models.Interaction)) or 0,"outcomes":{x:db.scalar(select(func.count()).select_from(models.Interaction).where(models.Interaction.outcome==x)) or 0 for x in ("Purchased Today","Quotation Taken","Follow-up Required")}}

@app.get("/reports/sessions")
def report_sessions(limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0),db:Session=Depends(get_db)):
    rows=db.scalars(select(models.GameSession).order_by(models.GameSession.start_time.desc()).offset(offset).limit(limit)).all()
    return {"items":[{"session_id":x.session_id,"persona":x.persona,"budget":x.budget,"start_time":x.start_time,"workload_count":len(x.workloads or [])} for x in rows],"limit":limit,"offset":offset}

