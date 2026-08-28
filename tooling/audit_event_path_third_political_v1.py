#!/usr/bin/env python3
from __future__ import annotations
from collections import Counter
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "structural_engine"))
from src.event_path_engine import AnnualPanelAdapter, EventPathEngine, build_states  # noqa: E402
INPUT = ROOT / "experiments/macro_plus_eia_energy/ama_ucdp_cross_domain_v1/AMA_UCDP_CROSS_DOMAIN_REPLAY_ROWS.csv"
OUTPUT = ROOT / "experiments/event_path_third_political_v1/AUDIT.json"
def main():
    dataset = AnnualPanelAdapter("state_based_conflict", domain="political").load(INPUT, entity_column="country_key", time_column="year")
    states = build_states(dataset.events)
    engine = EventPathEngine(window_width=3, min_support=2, max_path_length=6)
    predictions, metrics = engine.rolling_oos(states, dataset.events, train_size=8)
    summary = {
        "events": len(dataset.events), "entities": len({e.entity for e in dataset.events}), "predictions": len(predictions),
        "state_label_counts": dict(Counter(s.label for s in states)), "metrics": metrics,
        "support_policy": "min_support=2 fixed; unsupported paths abstain",
        "interpretation": "This diagnostic is not a null validation and does not support causal claims.",
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
if __name__ == "__main__": main()
