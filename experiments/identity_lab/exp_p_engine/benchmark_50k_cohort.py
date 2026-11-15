"""Synthetic throughput smoke test for 50,000 entities across 10 periods.

This measures cohort computation and known-injection handling only. It is not
real HR data, operational FPR calibration, or evidence about employee behavior.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

from experiments.identity_lab.exp_p_engine.domain_neutral import cohort_peer_residuals

ENTITY_COUNT = 50_000
PERIODS = 10
COHORT_COUNT = 500
INJECTION_PER_COHORT = 1
INJECTION_SIZE = 25.0
RAW_COUNT_RESIDUAL_THRESHOLD = 15.0
PEER_RATE_RESIDUAL_THRESHOLD = 0.20


def main() -> None:
    rng = random.Random(731)
    started = time.perf_counter()
    observations_processed = peer_residuals = injected = detected = rate_false_flags = raw_count_false_flags = 0

    for period in range(PERIODS):
        event_time = str(2020 + period)
        rows = []
        for staff_index in range(ENTITY_COUNT):
            cohort_index = staff_index % COHORT_COUNT
            is_injected = staff_index < COHORT_COUNT
            base_rate = 1.2 + (cohort_index % 17) * 0.01
            exposure = float(80 + 20 * ((staff_index // COHORT_COUNT) % 5))
            rate = base_rate + rng.gauss(0.0, 0.03) + (0.5 if is_injected else 0.0)
            value = rate * exposure
            rows.append({
                "entity_id": "staff-" + str(staff_index),
                "metric_id": "completed_cases_per_period",
                "event_time": event_time,
                "value": value,
                "observation_status": "observed",
                "cohort_id": "branch-role-season-" + str(cohort_index),
                "exposure": exposure,
                "exposure_unit": "hours",
            })
            if is_injected:
                injected += 1

        raw_results = cohort_peer_residuals(rows, min_peers=20)
        results = cohort_peer_residuals(rows, min_peers=20, use_exposure=True)
        observations_processed += len(rows)
        peer_residuals += len(results)
        injected_ids = {"staff-" + str(i) for i in range(COHORT_COUNT)}
        for row in results:
            flagged = abs(row["peer_residual"]) >= PEER_RATE_RESIDUAL_THRESHOLD
            if row["entity_id"] in injected_ids:
                detected += int(flagged)
            else:
                rate_false_flags += int(flagged)
        for row in raw_results:
            flagged = abs(row["peer_residual"]) >= RAW_COUNT_RESIDUAL_THRESHOLD
            if row["entity_id"] not in injected_ids:
                raw_count_false_flags += int(flagged)

    elapsed = time.perf_counter() - started
    report = {
        "benchmark": "synthetic_50k_entities_10_periods_peer_cohort",
        "synthetic_data": True,
        "real_hr_data": False,
        "entities_per_period": ENTITY_COUNT,
        "periods": PERIODS,
        "entity_period_observations": observations_processed,
        "cohort_count_per_period": COHORT_COUNT,
        "peer_residuals_computed": peer_residuals,
        "known_injections": injected,
        "known_injections_flagged": detected,
        "injection_recall": detected / injected if injected else None,
        "null_entity_periods": (ENTITY_COUNT - INJECTION_PER_COHORT) * PERIODS,
        "exposure_adjusted_null_peer_flags": rate_false_flags,
        "raw_count_null_peer_flags": raw_count_false_flags,
        "raw_count_threshold": RAW_COUNT_RESIDUAL_THRESHOLD,
        "exposure_rate_threshold": PEER_RATE_RESIDUAL_THRESHOLD,
        "exposure_normalization": "completed_cases_per_hour",
        "threshold_calibrated": False,
        "runtime_seconds": round(elapsed, 4),
        "observations_per_second": round(observations_processed / elapsed, 2) if elapsed else None,
        "scope": "throughput and controlled-injection smoke test; not HR validation or production FDR",
    }
    output = Path(__file__).resolve().parent / "results" / "domain_neutral_50k_benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
