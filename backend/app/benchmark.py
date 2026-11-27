from __future__ import annotations

from statistics import median

def compatible(current: dict, historical: dict) -> bool:
    """First release comparison gate: exact brand, same series, same round and protocol."""
    return all(current.get(key) == historical.get(key) for key in ("brand", "series", "round_id", "benchmark_version"))

def same_brand_records(current_brand: str, records: list[dict]) -> list[dict]:
    return [r for r in records if r.get("brand") == current_brand and not r.get("is_sample", False) and r.get("verification_status") == "VERIFIED"]

def summarize(values: list[float]) -> float | None:
    return median(values) if values else None

def difference(current: float | None, comparison: float | None, lower_is_better: bool) -> dict:
    if current is None or comparison is None:
        return {"available": False, "difference": None, "direction": "INSUFFICIENT COMPARABLE DATA"}
    delta = comparison - current
    improves = delta < 0 if lower_is_better else delta > 0
    return {"available": True, "difference": delta, "direction": "comparison better" if improves else "current better" if delta else "similar"}

def valid_npu_evidence(record: dict) -> bool:
    import re

    hashes_valid = all(isinstance(record.get(key), str) and re.fullmatch(r"[a-fA-F0-9]{64}", record[key]) for key in ("model_hash", "input_hash", "prompt_hash"))
    return (
        record.get("execution_provider") == "NPU"
        and record.get("runtime_verified") is True
        and record.get("verification_status") == "VERIFIED"
        and record.get("signature_verified") is True
        and bool(record.get("device_name"))
        and bool(record.get("runtime_version"))
        and hashes_valid
    )

