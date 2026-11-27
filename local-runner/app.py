"""Local companion service. This starter deliberately reports unsupported inference honestly."""
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Arena Local Runner", version="0.1.0")
origins = [x.strip() for x in os.getenv("ARENA_RUNNER_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET","POST","OPTIONS"], allow_headers=["Content-Type"])

def devices():
    try:
        import openvino as ov
        return {"runtime": ov.__version__, "devices": ov.Core().available_devices}
    except Exception:
        return {"runtime": None, "devices": []}

@app.get("/health")
def health():
    info = devices(); found_npu = any("NPU" in str(x).upper() for x in info["devices"])
    model_path = os.getenv("ARENA_MODEL_PATH", "")
    model_loaded = bool(model_path and os.path.isfile(model_path))
    return {"available": True, "runtime": info["runtime"], "devices": info["devices"], "npu_detected": found_npu, "model_loaded": model_loaded, "npu_verified": False, "execution_status": "NPU PATH NOT VERIFIED", "detail": "A detected device is not proof of successful inference. Configure and validate a compatible model before claiming execution."}

class RelayRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    provider: str = Field(pattern="^(CPU|NPU)$")

@app.post("/relay")
def relay(payload: RelayRequest):
    info = devices()
    if payload.provider == "NPU" and not any("NPU" in str(x).upper() for x in info["devices"]):
        return {"status":"PARTIAL","execution":"NOT VERIFIED","engine":"UNKNOWN","detail":"NPU PATH NOT VERIFIED"}
    # Until a known model artifact, hashes, fixed settings and measured execution are configured,
    # never report an engine or timing as if inference actually ran.
    return {"status":"PARTIAL","execution":"NOT VERIFIED","engine":"UNKNOWN","detail":"LOCAL ON-DEVICE — ENGINE NOT VERIFIED. No compatible benchmark model is configured."}

