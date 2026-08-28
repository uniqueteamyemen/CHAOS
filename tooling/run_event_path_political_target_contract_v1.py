#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import asdict
import csv
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "structural_engine"))
from src.event_path_engine import AnnualPanelAdapter, EventPathEngine, build_states, build_transitions, build_windows, build_paths, write_artifacts  # noqa: E402
INPUT = ROOT / "experiments/macro_plus_eia_energy/ama_ucdp_cross_domain_v1/AMA_UCDP_CROSS_DOMAIN_REPLAY_ROWS.csv"
OUTPUT = ROOT / "experiments/event_path_political_target_contract_v1"
SOURCE_COLUMN = "ama_gdp_growth_pct"
TARGET_COLUMN = "state_based_conflict"

def target_map(path: Path) -> dict[str, dict[int, str]]:
    result = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            entity = row["country_key"]
            value = row.get(TARGET_COLUMN, "").strip().lower()
            if value not in {"true", "false"}:
                continue
            result.setdefault(entity, {})[int(row["year"])] = "1" if value == "true" else "0"
    return result

def main():
    dataset = AnnualPanelAdapter(SOURCE_COLUMN, domain="economic").load(INPUT, entity_column="country_key", time_column="year")
    states = build_states(dataset.events)
    transitions = build_transitions(dataset.events, states)
    windows = build_windows(dataset.events, states, width=3)
    paths = build_paths(windows, states, transitions)
    engine = EventPathEngine(window_width=3, min_support=2, max_path_length=6)
    targets = target_map(INPUT)
    result = {"source": SOURCE_COLUMN, "target": TARGET_COLUMN, "contract": "information available at t -> Event-Path -> raw political outcome at t+h", "horizons": {}, "events": len(dataset.events), "entities": len({e.entity for e in dataset.events})}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for horizon in (1, 3):
        predictions, metrics = engine.rolling_oos_frozen_targets(states, dataset.events, targets, horizon=horizon, train_size=8)
        out = OUTPUT / f"horizon_{horizon}"
        write_artifacts(out, dataset, dataset.events, states, transitions, predictions, metrics)
        (out / "WINDOWS.jsonl").write_text("\n".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) for row in windows) + "\n", encoding="utf-8")
        (out / "PATHS.jsonl").write_text("\n".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) for row in paths) + "\n", encoding="utf-8")
        result["horizons"][str(horizon)] = metrics
    (OUTPUT / "CONTRACT.json").write_text(json.dumps({"contract_id": "event-path-political-raw-target-v1", "source_features": SOURCE_COLUMN, "raw_target": TARGET_COLUMN, "unit": "country-year", "horizons": [1, 3], "window_width": 3, "train_size": 8, "min_support": 2, "no_future_target_in_state_features": True, "unsupported_paths": "abstain", "causal_claims_permitted": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "RUN_SUMMARY.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
if __name__ == "__main__": main()
