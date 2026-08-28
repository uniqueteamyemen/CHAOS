#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "structural_engine"
sys.path.insert(0, str(ENGINE))

from src.event_path_engine import (  # noqa: E402
    AnnualPanelAdapter,
    EventPathEngine,
    build_states,
    build_transitions,
    build_windows,
    build_paths,
    write_artifacts,
)


DEFAULT_INPUT = ROOT / "catalog_first/readiness_gate/ANNUAL_PANEL_RAW_WDI_IMF_2000_2024.csv"
DEFAULT_OUTPUT = ROOT / "experiments/event_path_prototype_v1"
DEFAULT_COLUMN = "wdi__NY.GDP.MKTP.KD.ZG"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run governed, domain-neutral Event-Path prototype.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--value-column", default=DEFAULT_COLUMN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--window-width", type=int, default=3)
    parser.add_argument("--train-size", type=int, default=8)
    args = parser.parse_args()

    dataset = AnnualPanelAdapter(args.value_column, domain="economic").load(args.input)
    states = build_states(dataset.events)
    transitions = build_transitions(dataset.events, states)
    windows = build_windows(dataset.events, states, args.window_width)
    paths = build_paths(windows, states, transitions)
    engine = EventPathEngine(window_width=args.window_width, min_support=2)
    predictions, metrics = engine.rolling_oos(states, dataset.events, train_size=args.train_size)
    write_artifacts(args.output, dataset, dataset.events, states, transitions, predictions, metrics)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "WINDOWS.jsonl").write_text("\n".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) for row in windows) + "\n", encoding="utf-8")
    (args.output / "PATHS.jsonl").write_text("\n".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) for row in paths) + "\n", encoding="utf-8")
    candidate_counts = {}
    for path in paths:
        signature = " -> ".join(path.state_labels)
        candidate_counts[signature] = candidate_counts.get(signature, 0) + 1
    candidates = [{"pattern_id": f"event-path:{i:04d}", "state_signature": signature, "support": support, "status": "candidate" if support >= 2 else "unresolved", "evidence_refs": ["RUN_SUMMARY.json", "PATHS.jsonl"]} for i, (signature, support) in enumerate(sorted(candidate_counts.items(), key=lambda item: (-item[1], item[0])), 1)]
    (args.output / "CANDIDATE_PATTERNS.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in candidates) + "\n", encoding="utf-8")
    report = ["# Event-Path Prototype v1 — Execution Report", "", "This is a predictive prototype, not causal evidence.", "", f"- Source: `{args.input}`", f"- Value column: `{args.value_column}`", f"- Window width: `{args.window_width}`", f"- Chronological train size: `{args.train_size}`", f"- Events: **{len(dataset.events)}**; states: **{len(states)}**; transitions: **{len(transitions)}**; windows: **{len(windows)}**; predictions: **{len(predictions)}**", "- Unsupported paths abstain; no fallback is included in path_model.", "", "## Rolling OOS metrics", "", "| Model | Accuracy | N | Coverage/rate |", "|---|---:|---:|---:|"]
    for name, values in metrics.items():
        if "accuracy" in values:
            report.append(f"| {name} | {values['accuracy']:.4f} | {int(values['n'])} | coverage={values.get('coverage', 1.0):.4f} |")
        else:
            report.append(f"| {name} | — | {int(values['n'])} | rate={values.get('rate', 0.0):.4f} |")
    report += ["", "## Interpretation", "", "The path model is marked **provisional** because this first pass uses one annual economic series and has not yet undergone independent-domain replication, null-search correction, or external event-native validation. Accuracy is reported only against chronological out-of-sample outcomes; it must not be described as causal evidence or as a deployable signal.", ""]
    (args.output / "EXECUTION_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print({"input": str(args.input), "output": str(args.output), "events": len(dataset.events), "states": len(states), "transitions": len(transitions), "windows": len(windows), "paths": len(paths), "predictions": len(predictions), "metrics": metrics})


if __name__ == "__main__":
    main()
