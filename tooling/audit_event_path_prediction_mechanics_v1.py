#!/usr/bin/env python3
from __future__ import annotations
from collections import Counter
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "structural_engine"))
from src.event_path_engine import USGSGeoJSONAdapter, build_states  # noqa: E402

INPUT = ROOT / "data/raw/seismic_gulf_of_aden_v1/usgs_gulf_of_aden_query.geojson"
OUTPUT = ROOT / "experiments/seismic_transfer_test_v1/PREDICTION_MECHANICS_AUDIT_V1.json"


def majority(values: list[str], fallback: str) -> str:
    return Counter(values).most_common(1)[0][0] if values else fallback


def main() -> None:
    dataset = USGSGeoJSONAdapter().load(INPUT)
    states = build_states(dataset.events)
    labels = [state.label for state in states]
    width, train_size = 3, 8
    records = []
    for index in range(train_size, len(states)):
        train = states[:index]
        signature = tuple(state.label for state in train[-width:])
        matches = [j for j in range(width - 1, index - 1) if tuple(state.label for state in states[j-width+1:j+1]) == signature and j + 1 < index]
        prediction = majority([states[j + 1].label for j in matches], train[-1].label)
        records.append({"index": index, "signature": signature, "match_count": len(matches), "fallback": not bool(matches), "prediction": prediction, "actual": states[index].label})
    counts = Counter(record["match_count"] for record in records)
    matched = [r for r in records if not r["fallback"]]
    summary = {
        "source_sha256": dataset.source_sha256,
        "n_predictions": len(records),
        "n_fallback": sum(r["fallback"] for r in records),
        "fallback_rate": sum(r["fallback"] for r in records) / len(records),
        "n_with_historical_match": len(matched),
        "match_count_distribution": {str(k): v for k, v in sorted(counts.items())},
        "accuracy_all": sum(r["prediction"] == r["actual"] for r in records) / len(records),
        "accuracy_fallback": sum(r["prediction"] == r["actual"] for r in records if r["fallback"]) / max(1, sum(r["fallback"] for r in records)),
        "accuracy_matched": sum(r["prediction"] == r["actual"] for r in matched) / max(1, len(matched)),
        "unique_signatures_seen": len({r["signature"] for r in records}),
        "unique_signatures_with_match": len({r["signature"] for r in matched}),
        "state_label_counts": dict(Counter(labels)),
        "audit_findings": [
            "rolling_oos does not call discover and therefore min_support is not enforced",
            "a single historical match can emit a prediction",
            "no frozen candidate registry is used between discovery and OOS",
            "fallback persistence is embedded in path_model when no match exists",
        ],
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
