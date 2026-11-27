from backend.app.benchmark import compatible, difference, same_brand_records, summarize, valid_npu_evidence

def test_brand_filter_only_returns_verified_non_sample_matches():
    rows = [
        {"brand":"ASUS","verification_status":"VERIFIED","is_sample":False},
        {"brand":"Lenovo","verification_status":"VERIFIED","is_sample":False},
        {"brand":"ASUS","verification_status":"PENDING","is_sample":False},
        {"brand":"ASUS","verification_status":"VERIFIED","is_sample":True},
    ]
    assert same_brand_records("ASUS", rows) == [rows[0]]
    assert same_brand_records("Lenovo", rows) == [rows[1]]
    assert same_brand_records("HP", rows) == []

def test_series_and_round_must_match():
    current = {"brand":"ASUS","series":3,"round_id":"cpu","benchmark_version":"v1"}
    assert compatible(current, {**current,"tier":7})
    assert not compatible(current, {**current,"series":2})
    assert not compatible(current, {**current,"brand":"HP"})
    assert not compatible(current, {**current,"round_id":"gpu"})

def test_difference_and_missing_data():
    assert difference(20, 15, True)["direction"] == "comparison better"
    assert difference(20, 25, False)["direction"] == "comparison better"
    assert difference(None, 4, True)["available"] is False

def test_median_and_npu_runtime_evidence():
    assert summarize([1, 9, 5]) == 5
    assert summarize([]) is None
    assert not valid_npu_evidence({"execution_provider":"NPU","runtime_verified":False})
    assert valid_npu_evidence({"execution_provider":"NPU","runtime_verified":True,"model_hash":"abc","prompt_hash":"def"})

