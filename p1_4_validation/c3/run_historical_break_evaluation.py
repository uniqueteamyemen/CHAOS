"""C3 historical break evaluation on a SHA-pinned ALFRED first-release tape.

No ALFRED calls are made here. Online detectors are replayed on exact detection
prefixes; calendar anchors are labels, not causal claims or series-specific truth.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from p2_b_benchmark.p2c_engine import (  # noqa: E402
    FOCUS_THRESHOLD,
    HUBER_THRESHOLD,
    QUIET_POINTS,
    focus_detector,
    post_quiet_huber_detector,
)
from structural_engine.isolated_break_detector_v1 import BreakDetectorV1  # noqa: E402

PINNED = {
    "artifact_sha256": "8b4c7c4bc0cca7aea5a1346fdbd8f1f41076a88ae73622ff6331aad912a30c59",
    "tape_sha256": "a21a3b6e456a3f0a4821c51de6a347dd11242601b2ab460e31c06f8916dcf5aa",
    "manifest_sha256": "7f8741c44046cbe174b31acb6e35fa23b6beef5860c1c5049b820156dbc6e6e6",
    "contract_sha256": "6891999cf831c5b4045e0a7d554b897cb72df8f5e5dbbb4b6154744d1e0afe0a",
    "shock_contract_sha256": "f7ee733eebedec96b0d06eae5c960edf36aee49d52edb24df549b8784a7ba18e",
    "source_run_id": "45738391381",
    "source_commit": "2f3a38aa616719c6d1781ce4161703bcb7c0a14a",
}
EXPECTED_SERIES = {"UNRATE", "WCOILBRENTEU", "ICSA"}
DETECTORS = (
    "Post-Quiet Huber + MAD",
    "Post-Quiet Huber + Bartlett LRV",
    "FOCuS",
    "A_FAST",
    "A_CONSENSUS",
)

# Keep this schema aligned with score_events(); list-valued date fields are
# serialized as JSON arrays so downstream CSV consumers can parse them safely.
CSV_FIELDNAMES = (
    "event_id", "series_id", "detector", "hit_miss",
    "detection_index", "detection_available_at", "detection_lag_days",
    "detection_lag_weeks_or_months", "lag_unit",
    "false_alarms_before_anchor", "baseline_observations_after_quiet",
    "false_alarms_per_100_baseline_observations", "baseline_alarm_dates",
    "post_anchor_alarm_count", "all_post_anchor_alarm_dates",
    "detector_status",
)


def csv_export_row(row: dict) -> dict:
    metrics = dict(row["metrics"])
    for field in ("baseline_alarm_dates", "all_post_anchor_alarm_dates"):
        metrics[field] = json.dumps(metrics[field], ensure_ascii=False, separators=(",", ":"))
    return {
        "event_id": row["event_id"],
        "series_id": row["series_id"],
        "detector": row["detector"],
        **metrics,
        "detector_status": row["detector_status"],
    }



def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def verify_bundle(zip_path: Path, contract_path: Path) -> tuple[dict, dict[str, list[dict]], dict]:
    payload = zip_path.read_bytes()
    if sha256(payload) != PINNED["artifact_sha256"]:
        raise ValueError("C3_ARTIFACT_ZIP_SHA256_MISMATCH")
    contract_bytes = contract_path.read_bytes()
    if sha256(contract_bytes) != PINNED["contract_sha256"]:
        raise ValueError("C3_SOURCE_CONTRACT_SHA256_MISMATCH")
    contract = json.loads(contract_bytes)
    if contract["frozen_references"]["shock_event_contract_sha256"] != PINNED["shock_contract_sha256"]:
        raise ValueError("C3_SHOCK_CONTRACT_PIN_MISMATCH")
    shock_path = ROOT / contract["frozen_references"]["shock_event_contract_path"]
    if sha256(shock_path.read_bytes()) != PINNED["shock_contract_sha256"]:
        raise ValueError("C3_SHOCK_EVENT_CONTRACT_SHA256_MISMATCH")

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if archive.testzip() is not None:
            raise ValueError("C3_SOURCE_ARTIFACT_CORRUPT_ZIP_MEMBER")
        names = {n for n in archive.namelist() if not n.endswith("/")}
        manifest_bytes = archive.read("source_intake_manifest.json")
        tape_bytes = archive.read("initial_release_tape.csv")
        if sha256(manifest_bytes) != PINNED["manifest_sha256"]:
            raise ValueError("C3_MANIFEST_SHA256_MISMATCH")
        if sha256(tape_bytes) != PINNED["tape_sha256"]:
            raise ValueError("C3_NORMALIZED_TAPE_SHA256_MISMATCH")
        manifest = json.loads(manifest_bytes)
        if manifest.get("workflow_run_id") != PINNED["source_run_id"]:
            raise ValueError("C3_SOURCE_RUN_ID_MISMATCH")
        if manifest.get("source_commit") != PINNED["source_commit"]:
            raise ValueError("C3_SOURCE_COMMIT_MISMATCH")
        if manifest.get("status") != "SOURCE_TAPES_ACQUIRED_NOT_DETECTOR_EXECUTED":
            raise ValueError("C3_SOURCE_MANIFEST_STATUS_MISMATCH")
        if manifest.get("contract_sha256") != PINNED["contract_sha256"]:
            raise ValueError("C3_MANIFEST_CONTRACT_SHA_MISMATCH")
        if int(manifest.get("point_count", -1)) != 840:
            raise ValueError("C3_POINT_COUNT_MISMATCH")

        raw_rows = manifest.get("raw_vintage_batches", [])
        if len(raw_rows) != 87:
            raise ValueError(f"C3_RAW_BATCH_COUNT_MISMATCH:{len(raw_rows)}")
        for batch in raw_rows:
            member = batch["file"]
            if member not in names:
                raise ValueError(f"C3_RAW_BATCH_MISSING:{member}")
            raw = archive.read(member)
            if len(raw) != int(batch["bytes"]) or sha256(raw) != batch["sha256"]:
                raise ValueError(f"C3_RAW_BATCH_INTEGRITY_FAILURE:{member}")
        if len(names) != 89:
            raise ValueError(f"C3_ARTIFACT_MEMBER_COUNT_MISMATCH:{len(names)}")

    rows = list(csv.DictReader(io.StringIO(tape_bytes.decode("utf-8-sig"))))
    if len(rows) != 840:
        raise ValueError(f"C3_TAPE_ROWS_MISMATCH:{len(rows)}")
    by_series: dict[str, list[dict]] = {}
    for row in rows:
        sid = row["series_id"]
        if sid not in EXPECTED_SERIES:
            raise ValueError(f"C3_UNEXPECTED_SERIES:{sid}")
        if row["value_semantics"] != "FIRST_ALFRED_VINTAGE_VALUE":
            raise ValueError(f"C3_NON_FIRST_RELEASE_VALUE:{sid}")
        obs = date.fromisoformat(row["observation_date"])
        available = date.fromisoformat(row["available_at"])
        value = float(row["value"])
        if not math.isfinite(value) or available < obs:
            raise ValueError(f"C3_POINT_INVALID:{sid}:{obs}")
        by_series.setdefault(sid, []).append({
            **row, "value_float": value, "observation_date_obj": obs,
            "available_at_obj": available,
        })
    if set(by_series) != EXPECTED_SERIES:
        raise ValueError("C3_SERIES_SET_MISMATCH")
    for sid, values in by_series.items():
        values.sort(key=lambda r: (r["observation_date_obj"], r["available_at_obj"]))
        dates = [r["observation_date"] for r in values]
        if len(set(dates)) != len(dates):
            raise ValueError(f"C3_DUPLICATE_OBSERVATION_DATE:{sid}")
    events = {e["series_id"]: e for e in contract["events"]}
    if set(events) != EXPECTED_SERIES:
        raise ValueError("C3_CONTRACT_SERIES_SET_MISMATCH")
    return manifest, by_series, events


def extract_hits(detector: str, values: np.ndarray) -> tuple[list[dict], str, dict]:
    if detector == "Post-Quiet Huber + MAD":
        result = post_quiet_huber_detector(values, scale_mode="mad")
        hits = result.get("hits", [])
    elif detector == "Post-Quiet Huber + Bartlett LRV":
        result = post_quiet_huber_detector(values, scale_mode="bartlett")
        hits = result.get("hits", [])
    elif detector == "FOCuS":
        result = focus_detector(values)
        hits = result.get("hits", [])
    elif detector in {"A_FAST", "A_CONSENSUS"}:
        mode = "fast" if detector == "A_FAST" else "consensus"
        result = BreakDetectorV1(mode=mode).analyze(values)
        hits = []
        for event in result.get("structural_breaks", []):
            idx = event.get("detection_time", event.get("time"))
            sign = event.get("direction", event.get("sign"))
            if idx is None or sign is None:
                raise ValueError(f"{detector}_EVENT_SCHEMA_MISMATCH")
            hits.append({"index": int(idx), "sign": int(sign), **event})
    else:
        raise ValueError(f"UNKNOWN_DETECTOR:{detector}")
    status = str(result.get("status", "OK"))
    metadata = result.get("metadata", {})
    normalized = []
    for hit in hits:
        idx = hit.get("index", hit.get("detection_index"))
        sign = hit.get("sign", hit.get("direction"))
        if isinstance(idx, bool) or not isinstance(idx, (int, np.integer)):
            raise ValueError(f"{detector}_HIT_INDEX_INVALID")
        if int(sign) not in (-1, 1) or not 0 <= int(idx) < len(values):
            raise ValueError(f"{detector}_HIT_CONTRACT_INVALID:{idx}:{sign}")
        normalized.append({"index": int(idx), "sign": int(sign)})
    normalized.sort(key=lambda h: h["index"])
    return normalized, status, metadata


def audit_prefix_replay(detector: str, values: np.ndarray, hits: list[dict]) -> int:
    for hit in hits:
        idx = hit["index"]
        prefix_hits, status, _ = extract_hits(detector, values[:idx + 1])
        if status == "ABSTAIN" or not any(
            h["index"] == idx and h["sign"] == hit["sign"] for h in prefix_hits
        ):
            raise ValueError(f"NO_LOOKAHEAD_PREFIX_REPLAY_FAILED:{detector}:{idx}")
    return len(hits)


def score_events(rows: list[dict], anchor: str, hits: list[dict], quiet_points: int = QUIET_POINTS) -> dict:
    anchor_date = date.fromisoformat(anchor)
    valid_hits = []
    for hit in hits:
        idx = int(hit["index"])
        if idx < quiet_points:
            raise ValueError(f"DETECTOR_ALARM_DURING_RESERVED_QUIET:{idx}")
        available = rows[idx]["available_at_obj"]
        valid_hits.append({**hit, "available_at": available.isoformat()})
    baseline = [h for h in valid_hits if date.fromisoformat(h["available_at"]) < anchor_date]
    post = [h for h in valid_hits if date.fromisoformat(h["available_at"]) >= anchor_date]
    first = post[0] if post else None
    lag_days = (
        (date.fromisoformat(first["available_at"]) - anchor_date).days if first else None
    )
    frequency = rows[0]["frequency"]
    lag = (lag_days / 7.0 if lag_days is not None and "Weekly" in frequency
           else lag_days / 30.4375 if lag_days is not None else None)
    baseline_n = sum(
        1 for i, row in enumerate(rows)
        if i >= quiet_points and row["available_at_obj"] < anchor_date
    )
    return {
        "hit_miss": "HIT" if first else "MISS",
        "detection_index": first["index"] if first else None,
        "detection_available_at": first["available_at"] if first else None,
        "detection_lag_days": lag_days,
        "detection_lag_weeks_or_months": round(lag, 3) if lag is not None else None,
        "lag_unit": "weeks" if "Weekly" in frequency else "months",
        "baseline_observations_after_quiet": baseline_n,
        "false_alarms_before_anchor": len(baseline),
        "false_alarms_per_100_baseline_observations": (
            round(100.0 * len(baseline) / baseline_n, 3) if baseline_n else None
        ),
        "baseline_alarm_dates": [h["available_at"] for h in baseline],
        "post_anchor_alarm_count": len(post),
        "all_post_anchor_alarm_dates": [h["available_at"] for h in post],
    }


def markdown_report(report: dict) -> str:
    lines = [
        "# C3 — Historical Break Detector Evaluation",
        "",
        f"- Status: **{report['status']}**",
        f"- Source workflow: [Run #45738391381](https://github.com/uniqueteamyemen/CHAOS/actions/runs/45738391381)",
        f"- Evaluation commit: `{report['evaluation_commit']}`",
        f"- Source artifact SHA-256: `{report['source_integrity']['artifact_sha256']}`",
        f"- Normalized tape SHA-256: `{report['source_integrity']['tape_sha256']}`",
        f"- Source points: **{report['source_integrity']['point_count']}** across 3 series",
        "",
        "## 1. Frozen execution rules",
        "",
        "- Input is the pinned C3 first-release tape; no ALFRED request is made.",
        "- Initial 40 observations are calibration-only and excluded from baseline alarm counts.",
        "- Detection timestamps use `available_at`, never observation dates or retrospective onset estimates.",
        "- Event anchors are calendar references, not proof of a series-specific causal break.",
        "- Evaluation window is anchor through the frozen contract's observation_end.",
        "- Thresholds are frozen implementation defaults; no threshold fitting or holdout tuning is performed here.",
        "- A_FAST and A_CONSENSUS are read-only frozen reference implementations.",
        "",
        "## 2. Full head-to-head results",
        "",
        "| Series / event | Detector | Hit / Miss | Detection available_at | Lag | Baseline false alarms | Baseline n | Alarms / 100 baseline n |",
        "|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for row in report["results"]:
        r = row["metrics"]
        lag = f"{r['detection_lag_weeks_or_months']} {r['lag_unit']}" if r["detection_lag_weeks_or_months"] is not None else "—"
        lines.append(
            f"| {row['series_id']} / {row['event_id']} | {row['detector']} | {r['hit_miss']} | "
            f"{r['detection_available_at'] or '—'} | {lag} | {r['false_alarms_before_anchor']} | "
            f"{r['baseline_observations_after_quiet']} | "
            f"{r['false_alarms_per_100_baseline_observations'] if r['false_alarms_per_100_baseline_observations'] is not None else '—'} |"
        )
    lines += [
        "",
        "## 3. Event anchors and series windows",
        "",
        "| Event | Series | Anchor | Observation window | Frequency |",
        "|---|---|---|---|---|",
    ]
    for e in report["events"]:
        lines.append(
            f"| {e['event_id']} | {e['series_id']} | {e['anchor_date']} | "
            f"{e['observation_start']} to {e['observation_end']} | {e['frequency']} |"
        )
    lines += [
        "",
        "## 4. Detector settings and execution audit",
        "",
        "| Detector | Frozen setting | No-lookahead prefix replay |",
        "|---|---|---:|",
        f"| Post-Quiet Huber + MAD | threshold={HUBER_THRESHOLD}; quiet_points={QUIET_POINTS} | PASS |",
        f"| Post-Quiet Huber + Bartlett LRV | threshold={HUBER_THRESHOLD}; quiet_points={QUIET_POINTS} | PASS |",
        f"| FOCuS | threshold={FOCUS_THRESHOLD}; quiet_points={QUIET_POINTS} | PASS |",
        "| A_FAST | frozen BreakDetectorV1 fast mode | PASS |",
        "| A_CONSENSUS | frozen BreakDetectorV1 consensus mode | PASS |",
        "",
        "## 5. Interpretation limits",
        "",
        "- Pre-anchor alarm counts are observed baseline burden, not an estimated population false-positive rate.",
        "- The event anchors are broad macro-calendar labels; they do not identify exact series-specific structural-break onset.",
        "- The candidate thresholds are not equal-risk calibrated on this C3 set. Raw Hit/Lag/Alarm comparisons are descriptive and cannot alone establish detector superiority or close the per-series P0 gate.",
        "- A no-hit result is a miss against the calendar anchor within the available contract window, not proof that the detector cannot detect the underlying economic change.",
        "",
        "## 6. Reproducibility",
        "",
        f"- Replay command: `python p1_4_validation/c3/run_historical_break_evaluation.py --artifact-zip <pinned-source.zip> --contract p1_4_validation/c3/c3_source_contract_v1.json --output-dir artifacts/p1_4/c3/historical_evaluation`",
        f"- Run ID: `{report['run_id']}`",
        f"- Evaluation source commit: `{report['evaluation_commit']}`",
        f"- Report JSON SHA-256: `{report['report_json_sha256']}`",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-zip", required=True)
    parser.add_argument("--contract", default="p1_4_validation/c3/c3_source_contract_v1.json")
    parser.add_argument("--output-dir", default="artifacts/p1_4/c3/historical_evaluation")
    args = parser.parse_args()

    zip_path = Path(args.artifact_zip)
    manifest, by_series, events = verify_bundle(zip_path, Path(args.contract))
    results = []
    event_rows = []
    for sid in ("UNRATE", "WCOILBRENTEU", "ICSA"):
        rows = by_series[sid]
        event = events[sid]
        values = np.asarray([r["value_float"] for r in rows], dtype=float)
        if len(values) <= QUIET_POINTS:
            raise ValueError(f"C3_SERIES_TOO_SHORT:{sid}")
        for detector in DETECTORS:
            hits, status, metadata = extract_hits(detector, values)
            replayed = audit_prefix_replay(detector, values, hits) if hits else 0
            metrics = score_events(rows, event["anchor_date"], hits)
            results.append({
                "event_id": event["event_id"], "series_id": sid,
                "detector": detector, "detector_status": status,
                "hit_count_total": len(hits), "no_lookahead_prefix_replays": replayed,
                "metrics": metrics, "detector_metadata": metadata,
                "hits": hits,
            })
        event_rows.append({
            "event_id": event["event_id"], "series_id": sid,
            "anchor_date": event["anchor_date"],
            "observation_start": event["observation_start"],
            "observation_end": event["observation_end"],
            "frequency": event["frequency"],
        })
        print(f"C3_PROGRESS series={sid} observations={len(rows)} detectors={len(DETECTORS)}", flush=True)

    report = {
        "schema_version": "1.0.0",
        "status": "EVALUATION_COMPLETE_DESCRIPTIVE_THRESHOLDS_NOT_EQUAL_RISK_CALIBRATED",
        "run_id": __import__("os").environ.get("GITHUB_RUN_ID", "LOCAL_REPLAY"),
        "evaluation_commit": __import__("os").environ.get("GITHUB_SHA", "LOCAL_REPLAY"),
        "source_integrity": {
            "artifact_sha256": PINNED["artifact_sha256"],
            "manifest_sha256": PINNED["manifest_sha256"],
            "tape_sha256": PINNED["tape_sha256"],
            "contract_sha256": PINNED["contract_sha256"],
            "source_run_id": PINNED["source_run_id"],
            "source_commit": PINNED["source_commit"],
            "point_count": 840, "series_count": 3, "raw_batch_count": 87,
        },
        "execution_policy": {
            "quiet_points": QUIET_POINTS,
            "thresholds_tuned_on_c3": False,
            "available_at_used_for_detection_time": True,
            "prefix_replay_required": True,
            "a_fast_and_consensus_read_only": True,
            "causal_claim_from_calendar_match": False,
        },
        "events": event_rows,
        "results": results,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "C3_HISTORICAL_BREAK_EVALUATION_V1.json"
    json_path.write_bytes(canonical_json(report))
    report["report_json_sha256"] = sha256(json_path.read_bytes())
    md_path = out / "C3_HISTORICAL_BREAK_EVALUATION_V1_AR.md"
    md_path.write_text(markdown_report(report), encoding="utf-8")
    csv_path = out / "C3_HISTORICAL_BREAK_EVALUATION_V1.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in results:
            writer.writerow(csv_export_row(row))
    print(md_path.read_text(encoding="utf-8"), flush=True)
    print("C3_EVALUATION_OUTPUTS " + json.dumps({
        "json": str(json_path), "json_sha256": report["report_json_sha256"],
        "markdown": str(md_path), "csv": str(csv_path),
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
