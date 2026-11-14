"""Run Experiment L deterministic fault-injection stress tests."""
from __future__ import annotations
import json
from pathlib import Path

from .fault_injection import run_experiment

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def main() -> None:
    result = run_experiment(
        count=100, missing_rate=0.10, duplicate_rate=0.10,
        delayed_rate=0.10, seed=20261113,
    )
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "fault_injection_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = result["mutated_result"]
    print(json.dumps({
        "classification": result["classification"],
        "baseline_sha256": result["baseline_sha256"],
        "baseline_unchanged": result["baseline_unchanged_after_injection"],
        "mutated_states": summary["states"],
        "confirmed_losses": summary["confirmed_losses"],
        "false_loss_candidates": summary["false_loss_candidates_from_unconfirmed"],
    }))
    assert result["baseline_unchanged_after_injection"]
    assert result["baseline_result"]["states"]["exact"] == 100
    assert summary["states"]["exact"] == 70
    assert summary["states"]["ambiguous"] == 10
    assert summary["states"]["unmatched"] == 20
    assert summary["confirmed_losses"] == 0
    assert summary["false_loss_candidates_from_unconfirmed"] == 0


if __name__ == "__main__":
    main()
