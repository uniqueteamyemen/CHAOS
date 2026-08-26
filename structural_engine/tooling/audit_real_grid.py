from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "reports" / "real_10000_grid_results.json"
payload = json.loads(path.read_text(encoding="utf-8"))
results = payload["results"]
print("variables", payload["variables"])
print("result_count", len(results))
print("lag_counts", dict(sorted(Counter(row["lag"] for row in results).items())))
print("surrogate_counts", sorted({row["metrics"]["surrogate_count"] for row in results}))
print("fdr_q_le_0.01", sum(row["fdr_q_value"] <= 0.01 for row in results))
