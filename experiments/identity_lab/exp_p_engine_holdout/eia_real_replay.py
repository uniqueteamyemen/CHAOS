"""Replay selected P-engine candidates on the committed EIA weekly residual series.

All source observations are read from existing EIA HTML snapshots. Injected
steps are applied only to fresh in-memory copies. This observational replay is
not a labeled false-alarm benchmark.
"""
from __future__ import annotations

import json
import statistics
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from experiments.identity_lab.exp_p_engine.parallel_fusion import run_candidates
from experiments.identity_lab.exp_r_grade4 import grade4_diagnostics as eia

OUTPUT = Path(__file__).resolve().parent / "results" / "eia_weekly_real_series_replay.json"
INJECTION_INDEX = 300
POST_ADAPT_WEEKS = 130
INJECTION_LEVELS = (3.0, 6.0)
CANDIDATES = (
    {"id": "A-production-control", "variant": "A", "k": 0.5, "h": 8.5},
    {"id": "C-default-control", "variant": "C", "k": 0.5, "h": 8.5},
    {"id": "C-G-selected", "variant": "C", "k": 0.5, "h": 24.0},
    {"id": "D-G-selected", "variant": "D", "k": 0.5, "h": 24.0},
    {"id": "E-G-selected", "variant": "E", "k": 0.5, "h": 24.0},
    {"id": "F-G-selected", "variant": "F", "k": 0.5, "h": 16.0},
)


def ordinal_day(value: str) -> int:
    return date.fromisoformat(value[:10]).toordinal()


def iso_day(value: int) -> str:
    return date.fromordinal(int(value)).isoformat()


def inject_copy(series: list[dict[str, Any]], start_index: int, magnitude: float) -> list[dict[str, Any]]:
    """Create a changed test copy; leave the archived EIA observations untouched."""
    return [
        {**row, "residual": float(row["residual"]) + magnitude} if i >= start_index else dict(row)
        for i, row in enumerate(series)
    ]


def _candidate_rows(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return eia._engine_rows(series)


def _run_all_variants(series: list[dict[str, Any]], k: float, h: float) -> dict[str, Any]:
    quiet = (ordinal_day(eia.QUIET[0]), ordinal_day(eia.QUIET[1]))
    return run_candidates(
        "stock", _candidate_rows(series), quiet_range=quiet,
        entity="US-CRUDE", k_cusum=k, h_cusum=h,
        code_revision="p-engine-eia-weekly-real-replay-v1",
    )


def _raw_hits(result: Mapping[str, Any], variant: str) -> list[dict[str, Any]]:
    if variant == "A":
        baseline = result["A"]
        source = list(baseline.get("alerts", [])) + list(baseline.get("suppressed", []))
        unique = {}
        for hit in source:
            time_value = hit["time"]
            time_number = ordinal_day(time_value) if isinstance(time_value, str) else int(time_value)
            key = (time_number, hit.get("detector"), int(hit.get("sign", 0)))
            unique[key] = {"time": time_number, "detector": hit.get("detector"), "sign": key[2]}
        return list(unique.values())
    return list(result[variant].get("raw_hits", []))


def _fused_event_count(result: Mapping[str, Any], variant: str, detection_start: int) -> int:
    if variant == "A":
        return sum(
            1 for hit in result["A"].get("alerts", [])
            if (ordinal_day(hit["time"]) if isinstance(hit["time"], str) else int(hit["time"])) >= detection_start
        )
    return sum(1 for event in result[variant].get("events", []) if int(event["time"]) >= detection_start)


def summarize_candidate(
    result: Mapping[str, Any],
    candidate: Mapping[str, Any],
    series: list[dict[str, Any]],
) -> dict[str, Any]:
    variant = str(candidate["variant"])
    hits = _raw_hits(result, variant)
    detection_start = ordinal_day(eia.DETECT_START)
    cusum = [
        hit for hit in hits
        if str(hit.get("detector", "")).startswith("cusum")
        and int(hit["time"]) >= detection_start
    ]
    p1 = [
        hit for hit in hits
        if hit.get("detector") in {"sign_run", "P1"}
        and int(hit["time"]) >= detection_start
    ]
    detection_years = sum(row["time"] >= eia.DETECT_START for row in series) / 52.0
    known = {}
    for event_date in eia.KNOWN:
        target = ordinal_day(event_date)
        nearest = min((abs(int(hit["time"]) - target) for hit in cusum), default=None)
        known[event_date] = {
            "nearest_cusum_days": nearest,
            "within_60_days": nearest is not None and nearest <= 60,
        }
    return {
        "candidate": dict(candidate),
        "cusum_raw_hits_after_detection_start": len(cusum),
        "p1_raw_hits_after_detection_start": len(p1),
        "cusum_hits_per_detection_year": len(cusum) / detection_years if detection_years else None,
        "fused_events_after_detection_start": _fused_event_count(result, variant, detection_start),
        "nearest_known_event_alignment": known,
        "interpretation": "descriptive replay only; no ground-truth false-alarm labels",
    }


def evaluate_injections(
    series: list[dict[str, Any]],
    *,
    quiet_sigma: float,
) -> dict[str, Any]:
    cutoff_index = min(len(series) - 1, INJECTION_INDEX + POST_ADAPT_WEEKS)
    cutoff_time = ordinal_day(series[cutoff_index]["time"])
    output = {}
    for level in INJECTION_LEVELS:
        for direction in (-1, 1):
            label = ("negative" if direction < 0 else "positive") + f"_{int(level)}sigma"
            injected = inject_copy(series, INJECTION_INDEX, direction * level * quiet_sigma)
            by_pair: dict[tuple[float, float], dict[str, Any]] = {}
            for candidate in CANDIDATES:
                pair = (float(candidate["k"]), float(candidate["h"]))
                if pair not in by_pair:
                    by_pair[pair] = _run_all_variants(injected, *pair)
            candidate_metrics = {}
            for candidate in CANDIDATES:
                variant = str(candidate["variant"])
                result = by_pair[(float(candidate["k"]), float(candidate["h"]))]
                hits = _raw_hits(result, variant)
                detector_hits = [
                    hit for hit in hits
                    if str(hit.get("detector", "")).startswith("cusum")
                    and int(hit["time"]) >= cutoff_time
                ]
                correct = [hit for hit in detector_hits if int(hit.get("sign", 0)) == direction]
                wrong = [hit for hit in detector_hits if int(hit.get("sign", 0)) == -direction]
                first = min((int(hit["time"]) for hit in correct), default=None)
                candidate_metrics[candidate["id"]] = {
                    "correct_direction_cusum_hits_after_adaptation": len(correct),
                    "wrong_direction_cusum_hits_after_adaptation": len(wrong),
                    "detected_after_adaptation": first is not None,
                    "first_detection_date": iso_day(first) if first is not None else None,
                    "delay_weeks_after_adaptation": (first - cutoff_time) / 7.0 if first is not None else None,
                    "fused_events_after_adaptation": _fused_event_count(result, variant, cutoff_time),
                }
            output[label] = {
                "injection_index": INJECTION_INDEX,
                "injection_date": series[INJECTION_INDEX]["time"],
                "post_adaptation_cutoff_date": iso_day(cutoff_time),
                "candidate_results": candidate_metrics,
            }
    return output


def run_replay() -> dict[str, Any]:
    # eia.fetch is cache-first; the five archived HTML snapshots are committed.
    series = eia.build()
    if len(series) < 500:
        raise RuntimeError(f"eia_weekly_series_too_short:{len(series)}")
    quiet = [
        float(row["residual"]) for row in series
        if eia.QUIET[0] <= row["time"] <= eia.QUIET[1]
    ]
    if len(quiet) < 50:
        raise RuntimeError(f"eia_quiet_window_insufficient:{len(quiet)}")
    quiet_sigma = eia.mad_sigma(quiet)
    if not quiet_sigma or quiet_sigma <= 0:
        raise RuntimeError("eia_quiet_sigma_invalid")

    params = sorted({(float(item["k"]), float(item["h"])) for item in CANDIDATES})
    results_by_pair = {pair: _run_all_variants(series, *pair) for pair in params}
    summaries = {
        item["id"]: summarize_candidate(
            results_by_pair[(float(item["k"]), float(item["h"]))], item, series
        )
        for item in CANDIDATES
    }
    injections = evaluate_injections(series, quiet_sigma=quiet_sigma)
    known_events = {
        "2020-03-20": "COVID",
        "2021-02-19": "Texas freeze",
        "2022-03-04": "Russia-Ukraine",
        "2023-06-02": "SPR refill",
    }
    detect_weeks = sum(row["time"] >= eia.DETECT_START for row in series)
    return {
        "experiment": "p_engine_eia_weekly_real_series_replay_v1",
        "source": "EIA Weekly Petroleum Status Report — five archived weekly series",
        "source_series": dict(eia.SERIES),
        "series": {
            "weeks": len(series),
            "first_date": series[0]["time"],
            "last_date": series[-1]["time"],
            "quiet_window": list(eia.QUIET),
            "detection_start": eia.DETECT_START,
            "detection_weeks": detect_weeks,
            "detection_years": detect_weeks / 52.0,
        },
        "quiet_baseline": {
            "points": len(quiet),
            "mad_sigma": quiet_sigma,
            "bias_median": statistics.median(quiet),
            "units": "thousand_barrels",
        },
        "candidates": summaries,
        "known_events": {
            date_text: {"name": name, "use": "temporal alignment only; not ground truth"}
            for date_text, name in known_events.items()
        },
        "injection_protocol": {
            "source_series_mutated": False,
            "test_copy_only": True,
            "injection_index": INJECTION_INDEX,
            "injection_sigma_levels": list(INJECTION_LEVELS),
            "post_adaptation_weeks": POST_ADAPT_WEEKS,
            "scoring": "raw CUSUM direction and fused event; P1 counted separately",
        },
        "injections": injections,
        "decision": (
            "descriptive real-data replay only; no production promotion or empirical "
            "false-alarm claim can be made from unlabeled EIA residual history"
        ),
        "limitations": [
            "Published EIA balancing residual is survey mismatch, not verified ground-truth loss.",
            "Known event alignment is temporal proximity only; it does not establish causation or pre-event sensing.",
            "Injected changes exist only in copied test series; archived source data are never modified.",
        ],
    }


def main() -> int:
    report = run_replay()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "series": report["series"],
        "quiet_baseline": report["quiet_baseline"],
        "candidates": {
            key: {
                "cusum": value["cusum_raw_hits_after_detection_start"],
                "p1": value["p1_raw_hits_after_detection_start"],
                "fused": value["fused_events_after_detection_start"],
                "cusum_per_year": value["cusum_hits_per_detection_year"],
            }
            for key, value in report["candidates"].items()
        },
        "injections": report["injections"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
