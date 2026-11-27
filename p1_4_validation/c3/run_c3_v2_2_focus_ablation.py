"""Controlled FOCuS scale-window ablation on the frozen C3 v2.2 source tape.

This experiment does not recalibrate thresholds. It compares legacy scale=None
against causal scale=40 at fixed thresholds, fixed re-arm waits, and identical
Development/Holdout null traces. Historical event matching is diagnostic only.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

import numpy as np

from p1_4_validation.c3 import run_c3_v2_2_equal_risk_evaluation as c3


UNRATE_TARGET_EVENTS = {
    "NBER_19731975_PEAK",
    "NBER_2001_PEAK",
    "NBER_20072009_PEAK",
    "GFC_LEHMAN_2008",
}
WCOIL_TARGET_EVENTS = {"UKRAINE_ENERGY_SUPPLY_SHOCK_2022"}
SCALE_ARMS = (None, 40)


def ablation_matrix() -> list[dict]:
    matrix = [
        {
            "series_id": "WCOILBRENTEU",
            "threshold": 250.0,
            "rearm_points": 20,
            "scale_points": scale,
            "arm_id": "WCOIL_t250_r20_" + ("legacy" if scale is None else "scale40"),
            "target_event_ids": sorted(WCOIL_TARGET_EVENTS),
        }
        for scale in SCALE_ARMS
    ]
    for threshold in (175.0, 200.0):
        for rearm in (4, 5):
            for scale in SCALE_ARMS:
                matrix.append({
                    "series_id": "UNRATE",
                    "threshold": threshold,
                    "rearm_points": rearm,
                    "scale_points": scale,
                    "arm_id": (
                        "UNRATE_t" + str(int(threshold))
                        + "_r" + str(rearm)
                        + "_" + ("legacy" if scale is None else "scale40")
                    ),
                    "target_event_ids": sorted(UNRATE_TARGET_EVENTS),
                })
    return matrix


def robust_mad(values: np.ndarray) -> dict:
    data = np.asarray(values, dtype=float)
    if data.ndim != 1 or data.size == 0 or not np.all(np.isfinite(data)):
        return {"n": int(data.size), "median": None, "mad_raw": None, "mad_sigma": None}
    center = float(np.median(data))
    mad_raw = float(np.median(np.abs(data - center)))
    return {
        "n": int(data.size),
        "median": center,
        "mad_raw": mad_raw,
        "mad_sigma": 1.4826 * mad_raw,
    }


def generate_shared_null_traces(
    series_id: str,
    values: np.ndarray,
    tape_sha: str,
    seed_namespace: str,
    replicates: int,
) -> tuple[dict, dict[str, list[np.ndarray]], list[str]]:
    model = c3.select_ar_model(values[:c3.QUIET_POINTS])
    if model.get("status") != "OK":
        raise RuntimeError(
            "FOCUS_ABLATION_AR_MODEL_NOT_ELIGIBLE:"
            + series_id + ":" + str(model.get("reason"))
        )

    traces: dict[str, list[np.ndarray]] = {"development": [], "holdout": []}
    ledger: list[str] = []
    for phase in ("development", "holdout"):
        for replicate in range(int(replicates)):
            seed = c3.deterministic_seed(
                tape_sha,
                series_id,
                int(model["order"]),
                phase,
                replicate,
                namespace=seed_namespace,
            )
            ledger.append(phase + ":" + str(replicate) + ":" + str(seed))
            traces[phase].append(c3.generate_ar_null_trace(
                model,
                values[:c3.QUIET_POINTS],
                int(values.size),
                seed,
            ))
    return model, traces, ledger


def run_focus(values: np.ndarray, config: dict) -> dict:
    return c3.focus_reset_rearm(
        values,
        threshold=float(config["threshold"]),
        quiet_points=c3.QUIET_POINTS,
        rearm_quiet_points=int(config["rearm_points"]),
        rearm_scale_points=(
            int(config["scale_points"])
            if config["scale_points"] is not None else None
        ),
        max_events=c3.MAX_EVENTS,
        min_series_length=c3.QUIET_POINTS + 1,
    )


def false_alarm_stats(traces: list[np.ndarray], config: dict, phase: str) -> dict:
    outcomes = []
    for trace in traces:
        result = run_focus(trace, config)
        outcomes.append(
            bool(result.get("hits"))
            if result.get("status") == "OK" else None
        )
    valid = [value for value in outcomes if value is not None]
    alarms = sum(bool(value) for value in valid)
    stats = c3.wilson_stats(alarms, len(valid))
    stats["p0_target"] = (
        c3.DEV_P0_TARGET if phase == "development" else c3.P0_TARGET
    )
    stats["phase"] = phase
    stats["invalid_replicates"] = len(outcomes) - len(valid)
    stats["risk_gate"] = (
        "PASS"
        if len(valid) >= min(c3.MIN_VALID_REPLICATES, len(traces))
        and stats["wilson_upper_95_one_sided"] is not None
        and stats["wilson_upper_95_one_sided"] <= stats["p0_target"]
        else "FAIL_OR_INCONCLUSIVE"
    )
    return stats


def rearm_mad_diagnostics(
    values: np.ndarray,
    rows: list[dict],
    result: dict,
    rearm_points: int,
    target_anchor: date | None,
) -> list[dict]:
    """Expose the exact legacy and scale-40 MAD windows used at each re-arm."""
    diagnostics = []
    for interval_number, interval in enumerate(result.get("rearm_intervals", []), 1):
        start = int(interval["start_inclusive"])
        end = int(interval["end_exclusive"])
        if end <= start:
            continue

        legacy_window = values[start:end]
        scale40_start = max(0, end - 40)
        scale40_window = values[scale40_start:end]
        end_date = rows[end - 1]["observation_date_obj"]
        before_target = target_anchor is None or end_date <= target_anchor
        diagnostics.append({
            "rearm_number": interval_number,
            "rearm_start_index": start,
            "rearm_end_exclusive": end,
            "rearm_start_observation": rows[start]["observation_date"],
            "rearm_end_observation": rows[end - 1]["observation_date"],
            "legacy_scale_window": {
                "start_index": start,
                "end_exclusive": end,
                "mad": robust_mad(legacy_window),
            },
            "scale40_window": {
                "start_index": scale40_start,
                "end_exclusive": end,
                "mad": robust_mad(scale40_window),
            },
            "window_ends_before_target_event": before_target,
            "configured_rearm_points": int(rearm_points),
        })
    return diagnostics


def historical_event_evidence(
    rows: list[dict],
    events: list[dict],
    values: np.ndarray,
    config: dict,
) -> dict:
    result = run_focus(values, config)
    hits = result.get("hits", []) if result.get("status") == "OK" else []
    calibration = {
        "arms": {
            "FOCuS (reset-rearm)": {
                "frozen_threshold": float(config["threshold"]),
                "rearm_quiet_points": int(config["rearm_points"]),
                "rearm_scale_points": (
                    int(config["scale_points"])
                    if config["scale_points"] is not None else None
                ),
            }
        }
    }
    prefix_replays = (
        c3.audit_prefix_replay(
            "FOCuS (reset-rearm)", values, hits, calibration
        )
        if hits else 0
    )
    matched_rows, unmatched = c3.match_events_one_to_one(
        rows, events, hits, config["arm_id"]
    )
    by_event = {row["event_id"]: row for row in matched_rows}
    targets = [
        {
            "event_id": event_id,
            "hit_miss": by_event[event_id]["hit_miss"],
            "match_status": by_event[event_id]["match_status"],
            "detection_available_at": by_event[event_id]["detection_available_at"],
            "detection_index": by_event[event_id]["detection_index"],
            "detection_lag_weeks_or_months": by_event[event_id]["detection_lag_weeks_or_months"],
            "lag_unit": by_event[event_id]["lag_unit"],
        }
        for event_id in config["target_event_ids"]
        if event_id in by_event
    ]
    target_anchor = None
    if config["series_id"] == "WCOILBRENTEU":
        target_anchor = date.fromisoformat("2022-02-24")
    diagnostics = rearm_mad_diagnostics(
        values, rows, result, int(config["rearm_points"]), target_anchor
    )
    return {
        "detector_status": result.get("status"),
        "event_count": len(hits),
        "target_events": targets,
        "matched_event_series_pairs": unmatched.get("matched_event_count", 0),
        "unmatched_alarm_count": unmatched.get("unmatched_alarm_count", 0),
        "no_lookahead_prefix_replays": prefix_replays,
        "all_hits": [
            {
                "index": int(hit["index"]),
                "available_at": rows[int(hit["index"])]["available_at"],
                "sign": int(hit["sign"]),
                "score": hit.get("score"),
            }
            for hit in hits
        ],
        "rearm_mad_diagnostics": diagnostics,
    }


def build_event_pairs(contract: dict, series_id: str) -> list[dict]:
    output = []
    for event in contract["events"]:
        sign = event.get("expected_sign_by_series", {}).get(series_id)
        if sign is None:
            continue
        output.append({
            **event,
            "series_id": series_id,
            "expected_sign": int(sign),
        })
    return output


def run(args: argparse.Namespace) -> dict:
    source_zip = Path(args.source_zip)
    manifest, by_series, contract, archive_sha, contract_sha = c3.verify_source_bundle(
        source_zip, Path(args.contract)
    )
    if str(manifest.get("workflow_run_id")) != str(args.expected_source_run_id):
        raise ValueError("FOCUS_ABLATION_SOURCE_RUN_ID_MISMATCH")

    by_series, transform_audit = c3.apply_causal_series_transforms(
        source_zip, manifest, by_series, contract
    )
    analysis_sha = c3.analysis_tape_sha256(by_series)
    configs = ablation_matrix()
    seed_namespace = str(args.seed_namespace)
    series_cache = {}
    for series_id in ("WCOILBRENTEU", "UNRATE"):
        rows = by_series[series_id]
        values = np.asarray([row["value_float"] for row in rows], dtype=float)
        model, traces, ledger = generate_shared_null_traces(
            series_id,
            values,
            manifest["normalized_tape"]["sha256"],
            seed_namespace,
            int(args.replicates),
        )
        series_cache[series_id] = {
            "rows": rows,
            "values": values,
            "model": model,
            "traces": traces,
            "seed_ledger_sha256": c3.sha256("\n".join(ledger).encode("utf-8")),
            "event_pairs": build_event_pairs(contract, series_id),
        }

    arms = []
    for arm_index, config in enumerate(configs, 1):
        cached = series_cache[config["series_id"]]
        print(
            "FOCUS_ABLATION_ARM "
            + str(arm_index) + "/" + str(len(configs))
            + " id=" + config["arm_id"],
            flush=True,
        )
        development = false_alarm_stats(
            cached["traces"]["development"], config, "development"
        )
        holdout = false_alarm_stats(
            cached["traces"]["holdout"], config, "holdout"
        )
        historical = historical_event_evidence(
            cached["rows"], cached["event_pairs"], cached["values"], config
        )
        arms.append({
            **config,
            "threshold_policy": "FIXED_PREDECLARED_NO_RETUNING",
            "development": development,
            "holdout": holdout,
            "historical": historical,
            "risk_validation_status": (
                "VALIDATED"
                if development["risk_gate"] == "PASS"
                and holdout["risk_gate"] == "PASS"
                else "NOT_VALIDATED_OR_INCONCLUSIVE"
            ),
            "same_null_traces_shared_across_scale_arms": True,
        })

    source_ledger = {
        series_id: {
            "selected_ar_order": int(cache["model"]["order"]),
            "seed_namespace": seed_namespace,
            "seed_ledger_sha256": cache["seed_ledger_sha256"],
            "development_replicates": len(cache["traces"]["development"]),
            "holdout_replicates": len(cache["traces"]["holdout"]),
        }
        for series_id, cache in series_cache.items()
    }
    return {
        "schema_version": "1.0.0",
        "experiment_id": "C3_V2_2_FOCUS_SCALE_ABLATION_V1",
        "status": (
            "FULL_REPLICATE_ABLATION"
            if int(args.replicates) == c3.REPLICATES
            and all(
                arm["development"]["valid_replicates"] >= c3.MIN_VALID_REPLICATES
                and arm["holdout"]["valid_replicates"] >= c3.MIN_VALID_REPLICATES
                for arm in arms
            )
            else "SMOKE_OR_INCOMPLETE_REPLICATE_EVIDENCE"
        ),
        "source_integrity": {
            "source_intake_run_id": manifest.get("workflow_run_id"),
            "source_archive_sha256": archive_sha,
            "normalized_tape_sha256": manifest["normalized_tape"]["sha256"],
            "analysis_tape_sha256": analysis_sha,
            "contract_sha256": contract_sha,
            "analysis_transforms": transform_audit,
            "source_archive_mutated": False,
        },
        "seed_protocol": {
            "seed_namespace": seed_namespace,
            "replicates_per_phase": int(args.replicates),
            "same_seeded_traces_used_for_both_scale_arms": True,
            "series": source_ledger,
        },
        "protocol": {
            "development_wilson_u95_max": c3.DEV_P0_TARGET,
            "holdout_wilson_u95_max": c3.P0_TARGET,
            "minimum_valid_replicates": min(c3.MIN_VALID_REPLICATES, int(args.replicates)),
            "quiet_points": c3.QUIET_POINTS,
            "fixed_thresholds_only": True,
            "threshold_retuning": False,
            "matrix_arm_count": len(configs),
            "scale_arms": ["legacy_scale_none", "causal_scale_40"],
        },
        "arms": arms,
        "evaluation_commit": __import__("os").environ.get("GITHUB_SHA", "LOCAL_REPLAY"),
        "run_id": __import__("os").environ.get("GITHUB_RUN_ID", "LOCAL_ABLATION"),
        "replay_command": (
            "python p1_4_validation/c3/run_c3_v2_2_focus_ablation.py "
            "--source-zip <c3-v2-expanded-source-intake.zip> "
            "--contract p1_4_validation/c3/c3_expanded_event_cohort_v2_2.json "
            "--expected-source-run-id 45757611871"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", required=True)
    parser.add_argument(
        "--contract",
        default="p1_4_validation/c3/c3_expanded_event_cohort_v2_2.json",
    )
    parser.add_argument("--expected-source-run-id", default="45757611871")
    parser.add_argument("--seed-namespace", default="CHAOS:C3_V2_2")
    parser.add_argument("--replicates", type=int, default=c3.REPLICATES)
    parser.add_argument(
        "--output",
        default="artifacts/p1_4/c3/focus_ablation_v1/FOCUS_ABLATION.json",
    )
    args = parser.parse_args()
    if args.replicates < 1:
        raise ValueError("FOCUS_ABLATION_REPLICATES_MUST_BE_POSITIVE")
    report = run(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(c3.clean(report), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    output.write_bytes(payload)
    output_manifest = {
        "schema_version": "1.0.0",
        "run_id": report["run_id"],
        "evaluation_commit": report["evaluation_commit"],
        "report_path": str(output),
        "report_sha256": c3.sha256(payload),
        "source_archive_sha256": report["source_integrity"]["source_archive_sha256"],
        "contract_sha256": report["source_integrity"]["contract_sha256"],
        "seed_namespace": report["seed_protocol"]["seed_namespace"],
        "replay_command": report["replay_command"],
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(output_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "output": str(output),
        "output_manifest": str(manifest_path),
        "report_sha256": output_manifest["report_sha256"],
        "arm_count": len(report["arms"]),
        "source_run_id": report["source_integrity"]["source_intake_run_id"],
        "evaluation_commit": report["evaluation_commit"],
        "replay_command": report["replay_command"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
