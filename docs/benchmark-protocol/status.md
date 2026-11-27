# Benchmark protocol status

The prototype records browser-side game events separately from hardware benchmark results. Sample records are excluded from the verified benchmark query. An admin review endpoint requires three samples and prevents sample records from becoming verified; NPU approval also requires `runtime_verified: true` evidence.

No model hash, prompt hash, controlled power state, cold/warm protocol, compatible local model, inference execution, GPU workload, or validated historical result is bundled. Consequently all actual hardware performance comparisons currently show insufficient data. The local runner's device list is discovery only. A store operator must implement and validate a fixed OpenVINO model workflow before making runtime attribution claims.
