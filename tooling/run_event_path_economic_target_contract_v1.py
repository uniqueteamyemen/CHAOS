#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import asdict
import csv
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "structural_engine"))
from src.event_path_engine import AnnualPanelAdapter, EventPathEngine, build_states, build_transitions, build_windows, build_paths, write_artifacts  # noqa: E402
INPUT = ROOT / "catalog_first/readiness_gate/ANNUAL_PANEL_RAW_WDI_IMF_UCDP_EIA_2000_2024.csv"
OUTPUT = ROOT / "experiments/event_path_economic_target_contract_v1"
SOURCE_COLUMN = "wdi__NY.GDP.MKTP.KD.ZG"

def load_rows(path: Path):
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                year = int(row["year"])
                growth = float(row[SOURCE_COLUMN])
            except (ValueError, TypeError):
                continue
            rows.append((row["entity_code"], year, growth))
    return rows

def main():
    dataset = AnnualPanelAdapter(SOURCE_COLUMN, domain="economic").load(INPUT)
    states = build_states(dataset.events)
    transitions = build_transitions(dataset.events, states)
    windows = build_windows(dataset.events, states, width=3)
    paths = build_paths(windows, states, transitions)
    growth = {}
    for entity, year, value in load_rows(INPUT):
        growth.setdefault(entity, {})[year] = value
    targets = {}
    for entity, series in growth.items():
        for year, value in series.items():
            future = series.get(year + 3)
            if value > 4.0 and future is not None and future <= value - 2.0:
                targets.setdefault(entity, {})[year + 3] = "1"
            elif value > 4.0 and future is not None:
                targets.setdefault(entity, {})[year + 3] = "0"
    engine = EventPathEngine(window_width=3, min_support=2, max_path_length=6)
    predictions, metrics = engine.rolling_oos_frozen_targets(states, dataset.events, targets, horizon=3, train_size=8)
    write_artifacts(OUTPUT, dataset, dataset.events, states, transitions, predictions, metrics)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "WINDOWS.jsonl").write_text("\n".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) for row in windows) + "\n", encoding="utf-8")
    (OUTPUT / "PATHS.jsonl").write_text("\n".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) for row in paths) + "\n", encoding="utf-8")
    contract = {"contract_id": "event-path-economic-raw-target-v1", "source_feature": SOURCE_COLUMN, "source_rule": "GDP growth at t > 4.0%", "raw_target": "GDP growth at t+3 <= GDP growth at t - 2pp", "horizon": 3, "window_width": 3, "train_size": 8, "min_support": 2, "unsupported_paths": "abstain", "no_future_target_in_source_states": True, "causal_claims_permitted": False}
    (OUTPUT / "CONTRACT.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = ["# Event-Path Economic Target Contract v1", "", "This run tests the frozen economic rule with a raw future deterioration target.", "", f"- Source: `{INPUT}`", f"- Feature at t: `{SOURCE_COLUMN}` with high-growth rule >4.0%", "- Raw target at t+3: future GDP growth <= origin growth −2 percentage points", "- Same general frozen engine; min_support=2; unsupported paths abstain", "", "| Model | Accuracy | N | Coverage/rate |", "|---|---:|---:|---:|"]
    for name, values in metrics.items():
        if "accuracy" in values:
            report.append(f"| {name} | {values['accuracy']:.4f} | {int(values['n'])} | coverage={values.get('coverage', 1.0):.4f} |")
        else:
            report.append(f"| {name} | — | {int(values['n'])} | rate={values.get('rate', 0.0):.4f} |")
    report += ["", "## Status", "", "`provisional_economic_raw_target_only`", "", "This is predictive evidence only; no causal or operational promotion is permitted.", ""]
    (OUTPUT / "REPORT_AR.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"events": len(dataset.events), "entities": len({e.entity for e in dataset.events}), "predictions": len(predictions), "metrics": metrics}, ensure_ascii=False))
if __name__ == "__main__": main()
