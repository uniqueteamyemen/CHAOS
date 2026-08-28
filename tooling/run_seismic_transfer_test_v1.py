#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "structural_engine"))
from src.event_path_engine import USGSGeoJSONAdapter, EventPathEngine, build_states, build_transitions, build_windows, build_paths, write_artifacts

INPUT = ROOT / "data/raw/seismic_gulf_of_aden_v1/usgs_gulf_of_aden_query.geojson"
OUTPUT = ROOT / "experiments/seismic_transfer_test_v1"


def main() -> None:
    dataset = USGSGeoJSONAdapter().load(INPUT)
    states = build_states(dataset.events)
    transitions = build_transitions(dataset.events, states)
    windows = build_windows(dataset.events, states, width=3)
    paths = build_paths(windows, states, transitions)
    predictions, metrics = EventPathEngine(window_width=3, min_support=2, max_path_length=6).rolling_oos(states, dataset.events, train_size=8)
    write_artifacts(OUTPUT, dataset, dataset.events, states, transitions, predictions, metrics)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "WINDOWS.jsonl").write_text("\n".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) for row in windows) + "\n", encoding="utf-8")
    (OUTPUT / "PATHS.jsonl").write_text("\n".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) for row in paths) + "\n", encoding="utf-8")
    (OUTPUT / "TRANSFER_CONTRACT_REF.json").write_text(json.dumps({"contract": "experimental_contracts/EVENT_PATH_SEISMIC_TRANSFER_CONTRACT_V1.json", "economic_definition_changed": False, "window_width": 3, "train_size": 8, "tuning_after_transfer": False}, indent=2) + "\n", encoding="utf-8")
    report = ["# Gulf of Aden Seismic Transfer Test v1", "", "This is a frozen transfer test; no economic-model tuning was performed.", "", f"- Source: `{INPUT}`", "- Fixed region: 10–15°N, 42–52°E", "- Fixed period: 2000-01-01 through 2024-12-31 UTC", "- Fixed threshold: magnitude ≥ 4.5", "- Events retained: **%d**" % len(dataset.events), "- Window width: **3**; train size: **8**", "", "## Metrics", "", "| Model | Accuracy | N |", "|---|---:|---:|"]
    for name, values in metrics.items():
        report.append(f"| {name} | {values['accuracy']:.4f} | {int(values['n'])} |")
    if len(dataset.events) <= 8 or not predictions:
        status = "not_testable"
        reason = "The frozen query did not provide enough chronological events for the fixed OOS design."
    else:
        status = "provisional_transfer_only"
        reason = "The transfer result is descriptive and predictive only; it does not revise the economic judgment."
    report += ["", f"## Status: `{status}`", "", reason, "", "No seismic result is used to alter the economic Event-Path definition, window width, train size, or model selection.", ""]
    (OUTPUT / "TRANSFER_REPORT_AR.md").write_text("\n".join(report), encoding="utf-8")
    print({"events": len(dataset.events), "states": len(states), "transitions": len(transitions), "windows": len(windows), "predictions": len(predictions), "metrics": metrics, "status": status})


if __name__ == "__main__":
    main()
