#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "structural_engine"))
from src.event_path_engine import AnnualPanelAdapter, EventPathEngine, build_states, build_transitions, build_windows, build_paths, write_artifacts  # noqa: E402

INPUT = ROOT / "experiments/macro_plus_eia_energy/ama_ucdp_cross_domain_v1/AMA_UCDP_CROSS_DOMAIN_REPLAY_ROWS.csv"
OUTPUT = ROOT / "experiments/event_path_third_political_v1"
VALUE_COLUMN = "state_based_conflict"


def main() -> None:
    dataset = AnnualPanelAdapter(VALUE_COLUMN, domain="political").load(INPUT, entity_column="country_key", time_column="year")
    states = build_states(dataset.events)
    transitions = build_transitions(dataset.events, states)
    windows = build_windows(dataset.events, states, width=3)
    paths = build_paths(windows, states, transitions)
    engine = EventPathEngine(window_width=3, min_support=2, max_path_length=6)
    predictions, metrics = engine.rolling_oos(states, dataset.events, train_size=8)
    write_artifacts(OUTPUT, dataset, dataset.events, states, transitions, predictions, metrics)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "WINDOWS.jsonl").write_text("\n".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) for row in windows) + "\n", encoding="utf-8")
    (OUTPUT / "PATHS.jsonl").write_text("\n".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) for row in paths) + "\n", encoding="utf-8")
    contract = {
        "contract_id": "event-path-third-political-v1",
        "source": str(INPUT),
        "value_column": VALUE_COLUMN,
        "unit": "country-year",
        "native_frequency": "annual",
        "window_width": 3,
        "train_size": 8,
        "min_support": 2,
        "path_policy": "frozen conditional path; abstain when unsupported",
        "economic_model_tuning": False,
        "causal_claims_permitted": False,
    }
    (OUTPUT / "CONTRACT.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "# Event-Path — Third Political Path v1",
        "",
        "This run applies the domain-neutral frozen predictor to the native annual UCDP state-based conflict series.",
        "",
        f"- Source: `{INPUT}`",
        f"- Value: `{VALUE_COLUMN}`",
        f"- Entities: **{len({event.entity for event in dataset.events})}**",
        f"- Events: **{len(dataset.events)}**; states: **{len(states)}**; transitions: **{len(transitions)}**; windows: **{len(windows)}**; OOS predictions: **{len(predictions)}**",
        "- Unsupported paths abstain; no persistence fallback is included in path_model.",
        "",
        "## Metrics",
        "",
        "| Model | Accuracy | N | Coverage/rate |",
        "|---|---:|---:|---:|",
    ]
    for name, values in metrics.items():
        if "accuracy" in values:
            report.append(f"| {name} | {values['accuracy']:.4f} | {int(values['n'])} | coverage={values.get('coverage', 1.0):.4f} |")
        else:
            report.append(f"| {name} | — | {int(values['n'])} | rate={values.get('rate', 0.0):.4f} |")
    report += ["", "## Status", "", "`provisional_political_transfer_only`", "", "This is a predictive diagnostic, not causal evidence and not an operational promotion.", ""]
    (OUTPUT / "REPORT_AR.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"events": len(dataset.events), "entities": len({event.entity for event in dataset.events}), "predictions": len(predictions), "metrics": metrics}, ensure_ascii=False))


if __name__ == "__main__":
    main()
