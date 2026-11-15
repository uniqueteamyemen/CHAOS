"""A/B/C/D/E/F/G replay on the archived official EIA weekly balance residuals.

Historical event counts are descriptive only: EIA residuals do not carry an
adjudicated anomaly ground truth. Controlled +3σ/+6σ injections are applied to
copies of the exact residual series and scored only after the shared adaptation
horizon used by exp_r_grade4.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from experiments.identity_lab.exp_r_grade4.grade4_diagnostics import build
from experiments.identity_lab.exp_p_engine.engine import DOMAINS, mad_sigma
from experiments.identity_lab.exp_p_engine.parallel_fusion import run_candidates

# Importing grade4_diagnostics adds the experiment source directories to sys.path.
from oil import QUIET, DETECT_START  # type: ignore  # noqa: E402


INJECT_AT_INDEX = 300
POST_ADAPT_WEEKS = 130
VARIANTS = ("A", "B", "C", "D", "E", "F", "G")
DETECTORS = ("P1", "CUSUM")


def to_engine_rows(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Encode the exact archived residual sequence as a canonical stock identity."""
    columns = DOMAINS["stock"]
    rows = []
    for index, row in enumerate(series):
        residual = float(row["residual"])
        rows.append({
            columns["opening"]: 0.0,
            columns["inflow"]: 0.0,
            columns["outflow"]: 0.0,
            columns["other"]: 0.0,
            columns["closing"]: -residual,
            "month": index,
        })
    return rows


def clone_with_positive_shift(
    rows: list[dict[str, Any]], start_index: int, amount: float
) -> list[dict[str, Any]]:
    """Apply a persistent positive residual shift to a copy; never mutate source rows."""
    out = []
    for index, row in enumerate(rows):
        copied = dict(row)
        if index >= start_index:
            copied[DOMAINS["stock"]["closing"]] -= amount
        out.append(copied)
    return out


def _signals(result: dict[str, Any], variant: str, residuals: list[float], bias: float):
    if variant == "A":
        source = result["A"].get("alerts", []) + result["A"].get("suppressed", [])
        out = []
        for hit in source:
            detector_name = hit.get("detector")
            if detector_name == "sign_run":
                detector = "P1"
                index = int(hit["time"])
                sign = 1 if residuals[index] - bias >= 0 else -1
            elif detector_name == "cusum":
                detector = "CUSUM"
                sign = 1  # unchanged production P2 is positive-only
                index = int(hit["time"])
            else:
                continue
            out.append({"index": index, "detector": detector, "sign": sign})
        return out

    out = []
    for hit in result[variant]["raw_hits"]:
        detector_name = hit.get("detector", "")
        detector = "P1" if detector_name == "sign_run" else (
            "CUSUM" if detector_name.startswith("cusum_") else None
        )
        if detector is not None:
            out.append({
                "index": int(hit["index"]),
                "detector": detector,
                "sign": int(hit["sign"]),
            })
    return out


def _event_times(result: dict[str, Any], variant: str):
    if variant == "A":
        return sorted({int(x["time"]) for x in result["A"].get("alerts", [])})
    return sorted({int(x["time"]) for x in result[variant]["events"]})


def main() -> int:
    source = build()
    if not source:
        raise RuntimeError("EIA_source_series_empty")

    quiet_indices = [
        i for i, row in enumerate(source)
        if QUIET[0] <= row["time"] <= QUIET[1]
    ]
    if len(quiet_indices) < 8:
        raise RuntimeError("EIA_quiet_window_insufficient")
    quiet_range = (quiet_indices[0], quiet_indices[-1])
    detect_start = next(
        (i for i, row in enumerate(source) if row["time"] >= DETECT_START),
        None,
    )
    if detect_start is None:
        raise RuntimeError("EIA_detection_window_missing")
    if INJECT_AT_INDEX >= len(source) - POST_ADAPT_WEEKS:
        raise RuntimeError("EIA_injection_horizon_out_of_range")

    residual_values = [float(row["residual"]) for row in source]
    sigma_quiet = mad_sigma([residual_values[i] for i in quiet_indices])
    if sigma_quiet <= 0:
        raise RuntimeError("EIA_quiet_sigma_invalid")
    bias = sorted(residual_values[i] for i in quiet_indices)[len(quiet_indices) // 2]
    rows = to_engine_rows(source)

    baseline = run_candidates(
        "stock", rows, quiet_range=quiet_range,
        entity="US-CRUDE-EIA", code_revision=os.getenv("GITHUB_SHA", "local-unpinned"),
    )
    historical = {}
    for variant in VARIANTS:
        times = [t for t in _event_times(baseline, variant) if t >= detect_start]
        signals = [
            x for x in _signals(baseline, variant, residual_values, bias)
            if x["index"] >= detect_start
        ]
        historical[variant] = {
            "fused_or_production_alerts": len(times),
            "alerts_per_year": round(len(times) / ((len(source) - detect_start) / 52), 3),
            "first_alert_dates": [source[t]["time"] for t in times[:12]],
            "p1_raw_or_emitted_hits": sum(x["detector"] == "P1" for x in signals),
            "cusum_raw_or_emitted_hits": sum(x["detector"] == "CUSUM" for x in signals),
            "negative_cusum_hits": sum(
                x["detector"] == "CUSUM" and x["sign"] < 0 for x in signals
            ),
        }

    injections = {}
    for magnitude_sigma in (3.0, 6.0):
        injected_rows = clone_with_positive_shift(
            rows, INJECT_AT_INDEX, magnitude_sigma * sigma_quiet
        )
        result = run_candidates(
            "stock", injected_rows, quiet_range=quiet_range,
            entity=f"US-CRUDE-EIA-INJECT-{int(magnitude_sigma)}SIGMA",
            code_revision=os.getenv("GITHUB_SHA", "local-unpinned"),
        )
        cutoff = INJECT_AT_INDEX + POST_ADAPT_WEEKS
        residual_injected = [
            residual_values[i] + (magnitude_sigma * sigma_quiet if i >= INJECT_AT_INDEX else 0.0)
            for i in range(len(source))
        ]
        rows_by_variant = {}
        for variant in VARIANTS:
            signals = _signals(result, variant, residual_injected, bias)
            post_adapt = [x for x in signals if x["index"] >= cutoff]
            events = [t for t in _event_times(result, variant) if t >= cutoff]
            rows_by_variant[variant] = {
                "post_adaptation_event_count": len(events),
                "post_adaptation_p1_hits": sum(
                    x["detector"] == "P1" for x in post_adapt
                ),
                "post_adaptation_cusum_hits": sum(
                    x["detector"] == "CUSUM" for x in post_adapt
                ),
                "post_adaptation_expected_direction_detected": any(
                    x["sign"] > 0 for x in post_adapt
                ),
                "first_post_adaptation_detection_date": (
                    source[min(events)]["time"] if events else None
                ),
            }
        injections[f"positive_{int(magnitude_sigma)}sigma"] = {
            "magnitude_sigma_of_declared_quiet_scale": magnitude_sigma,
            "injection_start_index": INJECT_AT_INDEX,
            "post_adaptation_cutoff_index": cutoff,
            "variants": rows_by_variant,
        }

    output = {
        "source": {
            "dataset": "EIA Weekly Petroleum Status Report archived five-series identity residual",
            "synthetic": False,
            "weeks": len(source),
            "date_range": [source[0]["time"], source[-1]["time"]],
            "quiet_window": list(QUIET),
            "quiet_points": len(quiet_indices),
            "detection_start": DETECT_START,
            "detection_points": len(source) - detect_start,
            "quiet_bias": bias,
            "quiet_sigma": sigma_quiet,
            "units": "thousand barrels residual",
        },
        "baseline_historical_replay": {
            "interpretation": "descriptive only; no adjudicated historical anomaly labels",
            "variants": historical,
        },
        "controlled_injections": {
            "note": "persistent positive shifts applied to copies; source snapshot unchanged",
            "post_adaptation_weeks": POST_ADAPT_WEEKS,
            "results": injections,
        },
        "decision_boundary": (
            "Historical event counts are not false-alarm estimates. Candidate sensitivity "
            "is measured only against the controlled injected shifts."
        ),
    }

    output_path = Path(__file__).resolve().parent / "results" / "parallel_fusion_eia_probe.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
