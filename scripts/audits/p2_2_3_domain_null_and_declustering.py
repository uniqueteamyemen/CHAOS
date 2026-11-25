#!/usr/bin/env python3
"""Isolated seismic declustering and domain-null audit for CHAOS P2.2.3."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import kstest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from real_data_stress_pipeline import run_pipeline as p2
from real_data_stress_pipeline.diagnostics.gardner_knopoff import (
    gardner_knopoff_declustering,
)
from structural_engine.isolated_break_detector_v1 import (
    BreakDetectorV1,
    DEFAULT_MARKOV_THRESHOLD,
)

WB_PER_PAGE = 20000
WB_WORKERS = 4
WB_PERIOD = "1990M01:2023M12"
WB_INDICATORS = {
    "CPTOTSAXN": "Consumer price index, total, seasonally adjusted",
    "IPTOTSAKD": "Industrial production, total, seasonally adjusted",
    "DXGSRMRCHSAXD": "Merchandise exports, seasonally adjusted, current US dollars",
    "DXGSRMRCHNSKD": "Merchandise exports, seasonally adjusted, constant US dollars",
}
FRED_SERIES = {
    "CPIAUCSL": {"name": "Consumer Price Index for All Urban Consumers", "transform": "log_difference"},
    "INDPRO": {"name": "Industrial Production Index", "transform": "log_difference"},
    "UNRATE": {"name": "Unemployment Rate", "transform": "first_difference"},
    "FEDFUNDS": {"name": "Federal Funds Effective Rate", "transform": "first_difference"},
}
EIA_SERIES_DEFAULT = ("PET.RWTC.M", "PET.RBRTE.M")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fetch_bytes(url: str, timeout: int = 60, attempts: int = 5) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "CHAOS-P2.2.3-domain-null-audit/1.0",
                "Accept": "application/json, application/geo+json, */*",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
                if response.status != 200 or not payload:
                    raise RuntimeError(f"HTTP_{response.status}_EMPTY_{not bool(payload)}")
                return payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                break
        except Exception as exc:
            last_error = exc
        if attempt + 1 < attempts:
            time.sleep(min(2 ** attempt, 12))
    error_name = type(last_error).__name__ if last_error else "UnknownError"
    raise RuntimeError(f"request_failed_after_retries:{error_name}")


def fetch_json(url: str, timeout: int = 60) -> tuple[dict[str, Any], bytes]:
    raw = fetch_bytes(url, timeout=timeout)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("source_returned_non_json_payload") from exc
    if not isinstance(data, dict):
        raise ValueError("source_json_root_must_be_object")
    return data, raw


def parse_world_bank_page(raw: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = json.loads(raw)
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[0], dict):
        raise ValueError("world_bank_response_shape_invalid")
    meta = data[0]
    if meta.get("message"):
        raise RuntimeError("world_bank_api_message_present")
    rows = data[1] or []
    if not isinstance(rows, list):
        raise ValueError("world_bank_data_page_not_list")
    return meta, rows


def contiguous_transformed_series(
    monthly_mapping: dict[int, float],
    transform: str,
) -> tuple[list[str], list[float]]:
    month_indices, raw_values = p2.longest_run(monthly_mapping)
    if transform == "log_difference":
        return p2.returns(month_indices, raw_values)
    if transform == "first_difference":
        if len(raw_values) < 2:
            return [], []
        return [p2.label_month(index) for index in month_indices[1:]], [
            float(raw_values[i] - raw_values[i - 1])
            for i in range(1, len(raw_values))
        ]
    if transform == "level":
        return [p2.label_month(index) for index in month_indices], [
            float(value) for value in raw_values
        ]
    raise ValueError(f"unsupported_transform:{transform}")


def detector_summary(values: list[float] | np.ndarray) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    result: dict[str, Any] = {
        "observations": int(array.size),
        "g0": p2.g0(array, 87),
        "g1": p2.g1(array),
        "detector": None,
    }
    if array.size < BreakDetectorV1.MIN_SERIES_LENGTH:
        result["detector_status"] = "SKIPPED_TOO_SHORT"
        return result
    try:
        output = BreakDetectorV1(
            mode="markov_cusum",
            markov_threshold=DEFAULT_MARKOV_THRESHOLD,
        ).analyze(array)
        events = output.get("structural_breaks", [])
        times = [
            int(event["detection_time"])
            for event in events
            if event.get("detection_time") is not None
        ]
        diagnostics = output.get("diagnostics", {})
        result["detector"] = {
            "alarm_count": len(events),
            "first_alarm_index": min(times) if times else None,
            "cusum_peak": diagnostics.get("cusum_peak"),
            "cusum_updates": diagnostics.get("cusum_updates"),
            "rho_raw": diagnostics.get("rho_raw"),
            "rho_cusum_used": diagnostics.get("rho_cusum_used"),
        }
        result["detector_status"] = "COMPLETED"
    except Exception as exc:
        result["detector_status"] = "ERROR"
        result["detector_error"] = type(exc).__name__
    return result


def redact_secret_payload(raw: bytes, secret: str) -> tuple[bytes, bool]:
    """Prevent API credentials from entering stored raw response artifacts."""
    if not secret:
        return raw, False
    secret_bytes = secret.encode("utf-8")
    stored = raw.replace(secret_bytes, b"[REDACTED]")
    return stored, stored != raw


def save_raw(output_dir: Path, relative: str, raw: bytes) -> dict[str, Any]:
    path = output_dir / "raw" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "path": path.relative_to(output_dir).as_posix(),
        "sha256": sha256_bytes(raw),
        "bytes": len(raw),
    }


def load_world_bank_gem_snapshot(
    snapshot_dir: Path,
    output_dir: Path,
) -> tuple[
    dict[str, dict[int, list[dict[str, Any]]]],
    dict[str, dict[int, dict[str, Any]]],
    dict[str, int],
    dict[str, Any],
]:
    """Load published P2.2.1 GEM pages after strict manifest and SHA-256 checks."""
    manifest_path = (
        snapshot_dir
        / "real_data_stress_pipeline"
        / "results"
        / "real_data_stress_manifest.json"
    )
    if not manifest_path.is_file():
        raise FileNotFoundError("p2_2_1_source_manifest_missing")

    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    gem_config = manifest.get("gem_config") or {}
    if (
        int(gem_config.get("world_bank_source_id", -1)) != 15
        or gem_config.get("period_window") != WB_PERIOD
    ):
        raise ValueError("p2_2_1_gem_source_contract_mismatch")

    indicators = {
        str(item.get("code")): item
        for item in manifest.get("gem_indicators", [])
        if isinstance(item, dict) and item.get("code")
    }
    if set(indicators) != set(WB_INDICATORS):
        raise ValueError("p2_2_1_gem_indicator_set_mismatch")

    source_raw_dir = (
        snapshot_dir
        / "artifacts"
        / "real_data_stress"
        / "raw"
        / "world_bank"
        / "gem"
    )
    pages_by_indicator: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(dict)
    hashes_by_indicator: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    page_counts: dict[str, int] = {}
    observed_per_page: set[int] = set()

    for code in sorted(WB_INDICATORS):
        expected_hashes = indicators[code].get("raw_hashes")
        if not isinstance(expected_hashes, list) or not expected_hashes:
            raise ValueError(f"p2_2_1_gem_hash_list_missing:{code}")

        page_counts[code] = len(expected_hashes)
        for page_number, expected_hash in enumerate(expected_hashes, start=1):
            filename = f"{code}_page_{page_number:03d}.json"
            source_path = source_raw_dir / filename
            if not source_path.is_file():
                raise FileNotFoundError(f"p2_2_1_gem_page_missing:{filename}")

            raw = source_path.read_bytes()
            if sha256_bytes(raw) != str(expected_hash):
                raise ValueError(f"p2_2_1_gem_sha256_mismatch:{filename}")

            meta, rows = parse_world_bank_page(raw)
            if int(meta.get("page", page_number)) != page_number:
                raise ValueError(f"p2_2_1_gem_page_index_mismatch:{filename}")
            if int(meta.get("pages", len(expected_hashes))) != len(expected_hashes):
                raise ValueError(f"p2_2_1_gem_page_count_mismatch:{filename}")
            if meta.get("per_page") is not None:
                observed_per_page.add(int(meta["per_page"]))

            pages_by_indicator[code][page_number] = rows
            hashes_by_indicator[code][page_number] = save_raw(
                output_dir,
                f"world_bank_gem/{filename}",
                raw,
            )

    if len(observed_per_page) > 1:
        raise ValueError("p2_2_1_gem_per_page_inconsistent")

    source_info = {
        "mode": "REUSED_VERIFIED_P2_2_1_RELEASE_SNAPSHOT",
        "release_tag": "p2.2-historical-stress-v1.0.1",
        "source_repository_commit": manifest.get("git_commit"),
        "source_run_timestamp_utc": manifest.get("run_timestamp_utc"),
        "source_manifest_sha256": sha256_bytes(manifest_bytes),
        "source_id": 15,
        "period": WB_PERIOD,
        "indicators": sorted(WB_INDICATORS),
        "pages_verified": sum(page_counts.values()),
        "per_page": next(iter(observed_per_page), None),
    }
    return pages_by_indicator, hashes_by_indicator, page_counts, source_info


def fetch_world_bank_gem(
    output_dir: Path,
    snapshot_dir: Path | None = None,
) -> dict[str, Any]:
    raw_dir = output_dir / "raw" / "world_bank_gem"
    raw_dir.mkdir(parents=True, exist_ok=True)

    pages_by_indicator: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(dict)
    hashes_by_indicator: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    page_counts: dict[str, int] = {}
    source_snapshot: dict[str, Any] | None = None

    if snapshot_dir is not None:
        (
            pages_by_indicator,
            hashes_by_indicator,
            page_counts,
            source_snapshot,
        ) = load_world_bank_gem_snapshot(snapshot_dir, output_dir)
    else:
        first_requests = [(code, 1) for code in sorted(WB_INDICATORS)]

        def fetch_page(
            task: tuple[str, int],
        ) -> tuple[str, int, bytes, dict[str, Any], list[dict[str, Any]]]:
            code, page = task
            params = urllib.parse.urlencode({
                "source": 15,
                "format": "json",
                "per_page": WB_PER_PAGE,
                "page": page,
                "date": WB_PERIOD,
            })
            url = f"https://api.worldbank.org/v2/country/all/indicator/{code}?{params}"
            raw = fetch_bytes(url, timeout=75)
            meta, rows = parse_world_bank_page(raw)
            return code, page, raw, meta, rows

        with ThreadPoolExecutor(max_workers=WB_WORKERS) as executor:
            first_futures = [executor.submit(fetch_page, task) for task in first_requests]
            first_results = [future.result() for future in as_completed(first_futures)]

            remaining_tasks: list[tuple[str, int]] = []
            for code, page, raw, meta, rows in first_results:
                pages_total = max(1, int(meta.get("pages", 1) or 1))
                page_counts[code] = pages_total
                pages_by_indicator[code][page] = rows
                hashes_by_indicator[code][page] = save_raw(
                    output_dir, f"world_bank_gem/{code}_page_{page:04d}.json", raw
                )
                remaining_tasks.extend(
                    (code, page_number)
                    for page_number in range(2, pages_total + 1)
                )

            remaining_futures = [
                executor.submit(fetch_page, task) for task in remaining_tasks
            ]
            for future in as_completed(remaining_futures):
                code, page, raw, _meta, rows = future.result()
                pages_by_indicator[code][page] = rows
                hashes_by_indicator[code][page] = save_raw(
                    output_dir, f"world_bank_gem/{code}_page_{page:04d}.json", raw
                )

    source_status = (
        "REUSED_VERIFIED_SNAPSHOT" if source_snapshot is not None else "FETCHED"
    )

    indicator_results: list[dict[str, Any]] = []
    country_series_results: list[dict[str, Any]] = []
    for code in sorted(WB_INDICATORS):
        country_values: dict[str, dict[int, float]] = defaultdict(dict)
        country_names: dict[str, str] = {}
        total_rows = 0
        for page in sorted(pages_by_indicator[code]):
            for row in pages_by_indicator[code][page]:
                total_rows += 1
                month_index = p2.month(row.get("date", ""))
                value = p2.number(row.get("value"))
                if month_index is None or value is None:
                    continue
                if not (p2.Y0 * 12 <= month_index < (p2.Y1 + 1) * 12):
                    continue
                country = row.get("country") or {}
                iso = str(row.get("countryiso3code") or country.get("id") or "UNK")
                country_names[iso] = str(country.get("value") or iso)
                country_values[iso][month_index] = float(value)

        g0_pass = 0
        g1_pass = 0
        monthly_series_count = 0
        for iso, mapping in sorted(country_values.items()):
            axis, transformed = contiguous_transformed_series(mapping, "log_difference")
            if not transformed:
                continue
            monthly_series_count += 1
            quality = p2.g0(transformed, 87)
            stationarity = p2.g1(transformed)
            g0_pass += int(bool(quality.get("passed")))
            g1_pass += int(bool(stationarity.get("passed")))
            country_series_results.append({
                "source": "World Bank GEM",
                "indicator": code,
                "country_iso3": iso,
                "country": country_names.get(iso, iso),
                "observations": len(transformed),
                "first": axis[0],
                "last": axis[-1],
                "g0": quality,
                "g1": stationarity,
            })

        indicator_results.append({
            "indicator": code,
            "description": WB_INDICATORS[code],
            "status": source_status,
            "per_page": WB_PER_PAGE,
            "pages": page_counts.get(code, 0),
            "records_returned": total_rows,
            "country_series_with_contiguous_months": monthly_series_count,
            "g0_passed_series": g0_pass,
            "g1_passed_series": g1_pass,
            "raw_pages": [
                hashes_by_indicator[code][page]
                for page in sorted(hashes_by_indicator[code])
            ],
        })

    write_json(output_dir / "world_bank_gem_country_series_qa.json", country_series_results)
    return {
        "status": source_status,
        "period": WB_PERIOD,
        "per_page": WB_PER_PAGE,
        "parallel_workers": WB_WORKERS,
        "indicators": indicator_results,
        "country_series_qa_path": "world_bank_gem_country_series_qa.json",
        "source_snapshot": source_snapshot,
    }


def fetch_fred(output_dir: Path, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return {"status": "SKIPPED_SECRET_MISSING", "series": []}

    def fetch_one(series_id: str, config: dict[str, str]) -> dict[str, Any]:
        params = urllib.parse.urlencode({
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": "1990-01-01",
            "observation_end": "2024-12-31",
            "sort_order": "asc",
        })
        url = f"https://api.stlouisfed.org/fred/series/observations?{params}"
        payload, raw = fetch_json(url, timeout=60)
        if payload.get("error_code"):
            raise RuntimeError("fred_api_error")
        observations = payload.get("observations") or []
        mapping: dict[int, float] = {}
        for item in observations:
            month_index = p2.month(str(item.get("date", ""))[:7])
            value = p2.number(item.get("value"))
            if month_index is None or value is None:
                continue
            if p2.Y0 * 12 <= month_index < (p2.Y1 + 1) * 12:
                mapping[month_index] = float(value)
        axis, values = contiguous_transformed_series(mapping, config["transform"])
        stored_payload, credential_redacted = redact_secret_payload(raw, api_key)
        raw_info = save_raw(output_dir, f"fred/{series_id}.json", stored_payload)
        raw_info["source_response_sha256"] = sha256_bytes(raw)
        raw_info["credential_redacted_before_storage"] = credential_redacted
        return {
            "series_id": series_id,
            "name": config["name"],
            "transform": config["transform"],
            "status": "FETCHED",
            "observations_raw": len(observations),
            "observations_contiguous_transformed": len(values),
            "first": axis[0] if axis else None,
            "last": axis[-1] if axis else None,
            "qa": detector_summary(values) if values else None,
            "raw": raw_info,
        }

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(fetch_one, series_id, config): series_id
            for series_id, config in FRED_SERIES.items()
        }
        for future in as_completed(futures):
            series_id = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({
                    "series_id": series_id,
                    "status": "ERROR",
                    "error_type": type(exc).__name__,
                })
    results.sort(key=lambda item: item["series_id"])
    return {
        "status": "COMPLETED_WITH_ERRORS" if any(x["status"] == "ERROR" for x in results) else "FETCHED",
        "authentication": "FRED_API_KEY supplied through GitHub Actions Secret",
        "series": results,
    }


def fetch_eia(output_dir: Path, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return {"status": "SKIPPED_SECRET_MISSING", "series": []}

    configured = os.getenv("EIA_SERIES_IDS", "")
    series_ids = tuple(
        item.strip() for item in configured.split(";") if item.strip()
    ) or EIA_SERIES_DEFAULT

    def fetch_one(series_id: str) -> dict[str, Any]:
        params = urllib.parse.urlencode({
            "api_key": api_key,
            "length": 5000,
            "offset": 0,
        })
        url = (
            "https://api.eia.gov/v2/seriesid/"
            + urllib.parse.quote(series_id, safe=".")
            + "?"
            + params
        )
        payload, raw = fetch_json(url, timeout=60)
        if payload.get("error"):
            raise RuntimeError("eia_api_error")
        response = payload.get("response") or {}
        rows = response.get("data") or []
        mapping: dict[int, float] = {}
        for row in rows:
            period = str(row.get("period", ""))
            month_index = p2.month(period[:7])
            value = p2.number(row.get("value"))
            if month_index is None or value is None:
                continue
            if p2.Y0 * 12 <= month_index < (p2.Y1 + 1) * 12:
                mapping[month_index] = float(value)
        axis, values = contiguous_transformed_series(mapping, "log_difference")
        # EIA may echo request parameters, including api_key, in its response.
        # Keep the exact source-response hash but never persist the credential.
        stored_payload, credential_redacted = redact_secret_payload(raw, api_key)
        raw_info = save_raw(
            output_dir, f"eia/{series_id.replace('.', '_')}.json", stored_payload
        )
        raw_info["source_response_sha256"] = sha256_bytes(raw)
        raw_info["credential_redacted_before_storage"] = credential_redacted
        return {
            "series_id": series_id,
            "status": "FETCHED",
            "observations_raw": len(rows),
            "observations_contiguous_log_returns": len(values),
            "first": axis[0] if axis else None,
            "last": axis[-1] if axis else None,
            "qa": detector_summary(values) if values else None,
            "raw": raw_info,
        }

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(series_ids))) as executor:
        futures = {executor.submit(fetch_one, series_id): series_id for series_id in series_ids}
        for future in as_completed(futures):
            series_id = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({
                    "series_id": series_id,
                    "status": "ERROR",
                    "error_type": type(exc).__name__,
                })
    results.sort(key=lambda item: item["series_id"])
    return {
        "status": "COMPLETED_WITH_ERRORS" if any(x["status"] == "ERROR" for x in results) else "FETCHED",
        "authentication": "EIA_API_KEY supplied through GitHub Actions Secret",
        "series": results,
    }


def read_usgs_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "time": row["time"],
            "epoch_ms": int(row["epoch_ms"]),
            "magnitude": float(row["magnitude"]),
            "longitude": float(row["longitude"]),
            "latitude": float(row["latitude"]),
            "depth_km": float(row["depth_km"]) if row.get("depth_km") else None,
            "place": row.get("place"),
            # Optional fields preserve compatibility with historical CSV files
            # whose headers predate magnitude-type/source provenance.
            "mag_type": row.get("mag_type"),
            "mag_source": row.get("mag_source"),
        })
    return result


def monthly_counts(events: list[dict[str, Any]]) -> np.ndarray:
    counts = np.zeros((p2.Y1 - p2.Y0 + 1) * 12, dtype=np.int64)
    start_month = p2.Y0 * 12
    for event in events:
        month_index = p2.month(str(event["time"])[:7])
        if month_index is None:
            continue
        index = month_index - start_month
        if 0 <= index < counts.size:
            counts[index] += 1
    return counts


def interval_series(events: list[dict[str, Any]]) -> list[float]:
    ordered = sorted(events, key=lambda item: int(item["epoch_ms"]))
    gaps = [
        (int(ordered[i]["epoch_ms"]) - int(ordered[i - 1]["epoch_ms"])) / 86_400_000.0
        for i in range(1, len(ordered))
    ]
    return [math.log1p(value) for value in gaps if value >= 0.0]


def homogeneous_poisson_fit_diagnostics(
    counts: np.ndarray,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return descriptive diagnostics only; no uncalibrated goodness-of-fit p-values."""
    values = np.asarray(counts, dtype=float)
    mean_count = float(np.mean(values)) if values.size else 0.0
    variance = float(np.var(values, ddof=1)) if values.size > 1 else 0.0
    dispersion = variance / mean_count if mean_count > 0 else None
    result: dict[str, Any] = {
        "monthly_count_mean": mean_count,
        "monthly_count_variance": variance,
        "index_of_dispersion": dispersion,
        "poisson_reference_index_of_dispersion": 1.0,
        "monthly_count_dispersion_interpretation": (
            "descriptive_ratio_only; values near 1 are compatible with Poisson "
            "equidispersion but do not establish independence or model adequacy"
        ),
        "homogeneous_poisson_status": "BENCHMARK_ONLY_NOT_VALIDATED",
        "catalog_completeness_status": "NOT_ASSESSED",
        "inferential_goodness_of_fit_p_values_reported": False,
    }

    ordered = sorted(events, key=lambda item: int(item["epoch_ms"]))
    gaps = np.asarray([
        (int(ordered[i]["epoch_ms"]) - int(ordered[i - 1]["epoch_ms"])) / 86_400_000.0
        for i in range(1, len(ordered))
    ], dtype=float)
    if gaps.size >= 5 and float(np.mean(gaps)) > 0:
        # The exponential scale is estimated from the same observed gaps and
        # event intervals may be dependent. Keep the KS distance descriptive;
        # the usual one-sample KS p-value is not calibrated for this setting.
        fitted_mean = float(np.mean(gaps))
        test = kstest(gaps, "expon", args=(0.0, fitted_mean))
        result["inter_event_exponential_ks"] = {
            "statistic": float(test.statistic),
            "observations": int(gaps.size),
            "fitted_mean_inter_event_days": fitted_mean,
            "interpretation": (
                "descriptive distance to a fitted exponential distribution only; "
                "no p-value because the rate is estimated from this sample and "
                "interval independence is not established"
            ),
        }
    else:
        result["inter_event_exponential_ks"] = None
    return result


def stable_seed(token: str) -> int:
    return int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:8], "big")


def poisson_alarm_benchmark(
    counts: np.ndarray,
    observed_alarm_count: int | None,
    replicates: int,
    token: str,
) -> dict[str, Any]:
    values = np.asarray(counts, dtype=np.int64)
    exposure_months = int(values.size)
    total_events = int(values.sum())
    if exposure_months < 52 or total_events <= 0 or replicates < 1:
        return {
            "status": "INSUFFICIENT_FOR_RATE_MATCHED_POISSON",
            "replicates_requested": replicates,
            "exposure_months": exposure_months,
            "events": total_events,
        }
    rate = total_events / exposure_months
    rng = np.random.default_rng(stable_seed(token))
    alarm_counts: list[int] = []
    errors = 0
    for _ in range(replicates):
        simulated_counts = rng.poisson(rate, size=exposure_months)
        detected = detector_summary(np.log1p(simulated_counts))["detector"]
        if detected is None:
            errors += 1
        else:
            alarm_counts.append(int(detected["alarm_count"]))
    if not alarm_counts:
        return {
            "status": "NO_SUCCESSFUL_REPLICATES",
            "replicates_requested": replicates,
            "replicates_successful": 0,
            "errors": errors,
            "rate_events_per_month": rate,
        }
    any_alarm = sum(value > 0 for value in alarm_counts)
    result = {
        "status": "BENCHMARK_ONLY_NOT_VALIDATED",
        "rate_events_per_month": rate,
        "exposure_months": exposure_months,
        "events_used_to_estimate_rate": total_events,
        "replicates_requested": replicates,
        "replicates_successful": len(alarm_counts),
        "replicate_errors": errors,
        "conditional_null_alarm_probability": any_alarm / len(alarm_counts),
        "replicates_with_any_alarm": any_alarm,
        "alarm_count_mean": float(np.mean(alarm_counts)),
        "alarm_count_median": float(np.median(alarm_counts)),
        "alarm_count_q95": float(np.quantile(alarm_counts, 0.95)),
        "not_fpr": True,
    }
    if observed_alarm_count is not None:
        result["empirical_upper_tail_probability_vs_rate_matched_poisson"] = (
            1 + sum(value >= observed_alarm_count for value in alarm_counts)
        ) / (len(alarm_counts) + 1)
    return result


def detector_on_seismic_representation(values: np.ndarray) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    result = {
        "observations": int(array.size),
        "g0": p2.g0(array, 87),
        "g1": p2.g1(array),
    }
    if array.size < BreakDetectorV1.MIN_SERIES_LENGTH:
        result.update({"detector_status": "SKIPPED_TOO_SHORT", "detector": None})
        return result
    try:
        output = BreakDetectorV1(
            mode="markov_cusum",
            markov_threshold=DEFAULT_MARKOV_THRESHOLD,
        ).analyze(array)
        events = output.get("structural_breaks", [])
        diagnostics = output.get("diagnostics", {})
        times = [
            int(event["detection_time"])
            for event in events
            if event.get("detection_time") is not None
        ]
        result.update({
            "detector_status": "COMPLETED",
            "detector": {
                "alarm_count": len(events),
                "first_alarm_index": min(times) if times else None,
                "cusum_peak": diagnostics.get("cusum_peak"),
                "cusum_updates": diagnostics.get("cusum_updates"),
            },
        })
    except Exception as exc:
        result.update({
            "detector_status": "ERROR",
            "detector_error": type(exc).__name__,
            "detector": None,
        })
    return result


def summarize_magnitude_metadata(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe measurement-scale heterogeneity without pooling distinct scales."""
    type_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for event in events:
        raw_type = event.get("mag_type")
        mag_type = str(raw_type).strip().lower() if raw_type is not None and str(raw_type).strip() else "missing"
        raw_source = event.get("mag_source")
        mag_source = str(raw_source).strip() if raw_source is not None and str(raw_source).strip() else "missing"
        type_counts[mag_type] += 1
        source_counts[mag_source] += 1

    observed_types = sorted(t for t in type_counts if t != "missing")
    missing = type_counts.get("missing", 0)
    observed_sources = sorted(t for t in source_counts if t != "missing")
    source_missing = source_counts.get("missing", 0)
    homogeneous = len(observed_types) == 1 and missing == 0
    source_homogeneous = len(observed_sources) == 1 and source_missing == 0
    return {
        "magnitude_type_counts": dict(sorted(type_counts.items())),
        "magnitude_source_counts": dict(sorted(source_counts.items())),
        "magnitude_type_missing_events": missing,
        "observed_magnitude_types": observed_types,
        "magnitude_source_missing_events": source_missing,
        "observed_magnitude_sources": observed_sources,
        "magnitude_source_homogeneous": source_homogeneous,
        "magnitude_source_mixture_requires_calibration_review": len(observed_sources) > 1 or source_missing > 0,
        "magnitude_type_homogeneous": homogeneous,
        "single_magnitude_type_precheck_pass": homogeneous,
        "pooled_frequency_magnitude_status": (
            "SINGLE_MAGNITUDE_TYPE_PRECHECK_PASS"
            if homogeneous
            else "MIXED_MAGNITUDE_TYPES"
            if len(observed_types) > 1
            else "MAGNITUDE_TYPE_MISSING_OR_UNAVAILABLE"
        ),
    }


def validate_usgs_belt_catalog(
    belt: dict[str, Any],
    events: list[dict[str, Any]],
    ingestion_record: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fail closed if ingestion accounting or any accepted event violates the source query."""
    errors: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    if not isinstance(ingestion_record, dict):
        errors.append({"reason": "INGESTION_RECORD_MISSING"})
        ingestion_record = {}

    def nonnegative_int(name: str) -> int | None:
        value = ingestion_record.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors.append({"reason": "INGESTION_COUNT_INVALID", "field": name})
            return None
        return value

    received = nonnegative_int("events_received")
    accepted = nonnegative_int("events_accepted")
    quarantined = nonnegative_int("events_quarantined")
    duplicates = nonnegative_int("duplicate_features_deduplicated")

    if ingestion_record.get("catalog_integrity_status") not in {"PASS", "PASS_WITH_QUARANTINE"}:
        errors.append({
            "reason": "INGESTION_INTEGRITY_STATUS_INVALID",
            "status": ingestion_record.get("catalog_integrity_status"),
        })
    if accepted is not None and accepted != len(events):
        errors.append({
            "reason": "ACCEPTED_COUNT_DOES_NOT_MATCH_ANALYTICAL_CATALOG",
            "reported": accepted,
            "actual": len(events),
        })

    if None not in (received, accepted, quarantined, duplicates):
        reconciled = accepted + quarantined + duplicates == received
        if not reconciled:
            errors.append({
                "reason": "INGESTION_ACCOUNTING_DOES_NOT_RECONCILE",
                "events_received": received,
                "events_accepted": accepted,
                "events_quarantined": quarantined,
                "duplicate_features_deduplicated": duplicates,
            })
    else:
        reconciled = False

    for event in events:
        reasons = p2.usgs_record_rejection_reasons(
            belt, event.get("latitude"), event.get("longitude"),
            event.get("magnitude"), event.get("epoch_ms"),
            min_magnitude=p2.MAG,
        )
        if reasons:
            rejected.append({"event_id": str(event.get("id", "")), "reasons": reasons})

    if rejected:
        errors.append({
            "reason": "POST_INGESTION_VALIDATION_REJECTED_EVENTS",
            "count": len(rejected),
        })

    return {
        "magnitude_metadata": summarize_magnitude_metadata(events),
        "status": "PASS" if not errors else "FAIL",
        "post_ingest_validation_status": "PASS" if not rejected else "FAIL",
        "catalog_integrity_status": ingestion_record.get("catalog_integrity_status"),
        "events_received": received,
        "events_accepted": accepted,
        "events_quarantined": quarantined,
        "duplicate_features_deduplicated": duplicates,
        "analytical_catalog_events": len(events),
        "accounting_reconciled": reconciled,
        "post_ingest_rejected_events": rejected,
        "errors": errors,
    }


def audit_belt(
    belt: dict[str, Any],
    events: list[dict[str, Any]],
    output_dir: Path,
    poisson_replicates: int,
    catalog_path: Path,
    ingestion_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog_integrity = validate_usgs_belt_catalog(belt, events, ingestion_record)
    if catalog_integrity["status"] != "PASS":
        return {
            "belt_id": belt["id"],
            "belt_name": belt["name"],
            "status": "CATALOG_POST_INGEST_VALIDATION_FAILED",
            "source_events": len(events),
            "catalog_integrity": catalog_integrity,
            "catalog_completeness_status": "NOT_ASSESSED",
        }

    baseline_counts = monthly_counts(events)
    intervals_before = interval_series(events)
    baseline_monthly = detector_on_seismic_representation(np.log1p(baseline_counts))
    baseline_intervals = detector_on_seismic_representation(np.asarray(intervals_before))

    sensitivity: list[dict[str, Any]] = []
    base_labeled: list[dict[str, Any]] = []
    base_retained: list[dict[str, Any]] = []
    for fraction in (0.25, 0.5, 1.0):
        labeled, decluster_summary = gardner_knopoff_declustering(
            events, foreshock_time_fraction=fraction
        )
        retained = [
            event for event in labeled
            if event["declustering_role"] in {"MAINSHOCK", "BACKGROUND"}
        ]
        counts_after = monthly_counts(retained)
        intervals_after = interval_series(retained)
        monthly_detector = detector_on_seismic_representation(np.log1p(counts_after))
        interval_detector = detector_on_seismic_representation(np.asarray(intervals_after))
        sensitivity.append({
            "foreshock_time_fraction": fraction,
            "declustering": decluster_summary,
            "monthly_counts_detector": monthly_detector,
            "inter_event_interval_detector": interval_detector,
        })
        if fraction == 0.5:
            base_labeled = labeled
            base_retained = retained

    write_csv(
        output_dir / "declustered_catalogs" / f"{belt['id']}_gk_labeled.csv",
        base_labeled,
    )
    after_counts = monthly_counts(base_retained)
    after_intervals = interval_series(base_retained)
    after_monthly = detector_on_seismic_representation(np.log1p(after_counts))
    after_interval_detector = detector_on_seismic_representation(np.asarray(after_intervals))

    before_observed_alarm = (
        baseline_monthly.get("detector") or {}
    ).get("alarm_count")
    after_observed_alarm = (
        after_monthly.get("detector") or {}
    ).get("alarm_count")
    before_poisson = poisson_alarm_benchmark(
        baseline_counts, before_observed_alarm, poisson_replicates,
        f"{belt['id']}|raw|poisson",
    )
    after_poisson = poisson_alarm_benchmark(
        after_counts, after_observed_alarm, poisson_replicates,
        f"{belt['id']}|gk_0.5|poisson",
    )

    return {
        "belt_id": belt["id"],
        "belt_name": belt["name"],
        "source_events": len(events),
        "source_catalog_csv_sha256": p2.hash_file(catalog_path),
        "analysis_period": f"{p2.Y0}-01 through {p2.Y1}-12",
        "query_minimum_magnitude": p2.MAG,
        "catalog_completeness_status": "NOT_ASSESSED",
        "status": "COMPLETED",
        "catalog_integrity": catalog_integrity,
        "before_declustering": {
            "event_count": len(events),
            "monthly_event_counts": {
                "mean": float(np.mean(baseline_counts)),
                "variance": float(np.var(baseline_counts, ddof=1)),
                "max": int(np.max(baseline_counts)),
                "nonzero_months": int(np.count_nonzero(baseline_counts)),
            },
            "monthly_counts_detector": baseline_monthly,
            "inter_event_interval_count": len(intervals_before),
            "inter_event_interval_detector": baseline_intervals,
            "poisson_fit_diagnostics": homogeneous_poisson_fit_diagnostics(
                baseline_counts, events
            ),
            "rate_matched_poisson_benchmark": before_poisson,
        },
        "after_declustering_gk_fraction_0_5": {
            "event_count": len(base_retained),
            "monthly_event_counts": {
                "mean": float(np.mean(after_counts)),
                "variance": float(np.var(after_counts, ddof=1)),
                "max": int(np.max(after_counts)),
                "nonzero_months": int(np.count_nonzero(after_counts)),
            },
            "monthly_counts_detector": after_monthly,
            "inter_event_interval_count": len(after_intervals),
            "inter_event_interval_detector": after_interval_detector,
            "poisson_fit_diagnostics": homogeneous_poisson_fit_diagnostics(
                after_counts, base_retained
            ),
            "rate_matched_poisson_benchmark": after_poisson,
            "labeled_catalog_path": f"declustered_catalogs/{belt['id']}_gk_labeled.csv",
        },
        "declustering_sensitivity": sensitivity,
    }


def required_source_gate(
    gem_result: dict[str, Any],
    usgs_result: dict[str, Any],
    seismic_belts: list[dict[str, Any]],
) -> dict[str, Any]:
    gem_indicators = gem_result.get("indicators") or []
    gem_codes = {
        item.get("indicator")
        for item in gem_indicators
        if isinstance(item, dict)
        and item.get("status") in {"FETCHED", "REUSED_VERIFIED_SNAPSHOT"}
    }
    gem_complete = (
        gem_result.get("status") in {"FETCHED", "REUSED_VERIFIED_SNAPSHOT"}
        and gem_codes == set(WB_INDICATORS)
    )
    usgs_complete = (
        usgs_result.get("status") == "COMPLETED"
        and not usgs_result.get("errors")
    )
    belts_complete = (
        len(seismic_belts) == len(p2.BELTS)
        and all(int(item.get("source_events", 0)) > 0 for item in seismic_belts)
    )
    catalog_integrity_complete = (
        len(seismic_belts) == len(p2.BELTS)
        and all(
            isinstance(item.get("catalog_integrity"), dict)
            and item["catalog_integrity"].get("status") == "PASS"
            and item["catalog_integrity"].get("post_ingest_validation_status") == "PASS"
            and item["catalog_integrity"].get("accounting_reconciled") is True
            for item in seismic_belts
        )
    )
    return {
        "world_bank_gem": gem_complete,
        "usgs_comcat": usgs_complete,
        "usgs_catalog_integrity": catalog_integrity_complete,
        "five_seismic_belts": belts_complete,
        "passed": gem_complete and usgs_complete and catalog_integrity_complete and belts_complete,
        "optional_sources": ["FRED", "EIA"],
    }


def run_audit(
    output_dir: Path,
    poisson_replicates: int,
    gem_snapshot_dir: Path | None = None,
    isolated_usgs_only: bool = False,
    max_belts: int | None = None,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_meta: dict[str, Any] = {"sources": [], "errors": [], "rejected": [], "belts": []}

    # Isolated audit storage prevents overwriting the historical P2.2 source archive.
    audit_raw_root = (output_dir / "source_snapshots" / "raw").resolve()
    audit_derived_root = (output_dir / "source_snapshots" / "derived").resolve()
    audit_raw_root.mkdir(parents=True, exist_ok=True)
    audit_derived_root.mkdir(parents=True, exist_ok=True)
    original_raw, original_derived = p2.RAW, p2.DERIVED
    original_belts = p2.BELTS
    if max_belts is not None:
        if max_belts < 1:
            raise ValueError("max_belts_must_be_positive")
        selected_belts = p2.BELTS[:max_belts]
    else:
        selected_belts = p2.BELTS

    # USGS ingestion always uses an isolated snapshot root, for both PR and full runs.
    try:
        p2.BELTS = selected_belts
        p2.RAW, p2.DERIVED = audit_raw_root, audit_derived_root
        seismic_series = p2.seismic(source_meta)
    finally:
        p2.BELTS = original_belts
        p2.RAW, p2.DERIVED = original_raw, original_derived

    if isolated_usgs_only:
        gem_result = {"status": "SKIPPED_BY_BOUNDED_PR_POLICY"}
        fred_result = {"status": "SKIPPED_BY_BOUNDED_PR_POLICY"}
        eia_result = {"status": "SKIPPED_BY_BOUNDED_PR_POLICY"}
    else:
        with ThreadPoolExecutor(max_workers=3) as executor:
            gem_future = executor.submit(fetch_world_bank_gem, output_dir, gem_snapshot_dir)
            fred_future = executor.submit(fetch_fred, output_dir, os.getenv("FRED_API_KEY"))
            eia_future = executor.submit(fetch_eia, output_dir, os.getenv("EIA_API_KEY"))
            try:
                gem_result = gem_future.result()
            except Exception as exc:
                gem_result = {
                    "status": "ERROR",
                    "indicators": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            fred_result = fred_future.result()
            eia_result = eia_future.result()

    belt_results: list[dict[str, Any]] = []
    ingestion_by_belt = {
        str(item.get("id")): item
        for item in source_meta["belts"]
        if isinstance(item, dict) and item.get("id")
    }
    for belt in selected_belts:
        catalog_path = audit_derived_root / f"{belt['id']}_events.csv"
        if not catalog_path.exists():
            belt_results.append({
                "belt_id": belt["id"],
                "status": "CATALOG_NOT_AVAILABLE",
                "catalog_integrity": {
                    "status": "FAIL",
                    "post_ingest_validation_status": "FAIL",
                    "accounting_reconciled": False,
                    "errors": [{"reason": "ANALYTICAL_CATALOG_MISSING"}],
                },
            })
            continue
        events = read_usgs_csv(catalog_path)
        belt_results.append(
            audit_belt(
                belt, events, output_dir, poisson_replicates, catalog_path,
                ingestion_record=ingestion_by_belt.get(belt["id"]),
            )
        )

    usgs_result = {
        "status": "COMPLETED_WITH_ERRORS" if source_meta["errors"] else "COMPLETED",
        "belts_queried": source_meta["belts"],
        "raw_sources": source_meta["sources"],
        "errors": source_meta["errors"],
        "rejected": source_meta["rejected"],
        "belts": source_meta["belts"],
    }
    if isolated_usgs_only:
        selected_belts_complete = (
            len(belt_results) == len(selected_belts)
            and bool(selected_belts)
            and all(
                item.get("status") == "COMPLETED"
                and int(item.get("source_events", 0) or 0) > 0
                and isinstance(item.get("catalog_integrity"), dict)
                and item["catalog_integrity"].get("status") == "PASS"
                and item["catalog_integrity"].get("accounting_reconciled") is True
                for item in belt_results
            )
        )
        source_gate = {
            "world_bank_gem": "SKIPPED_BY_BOUNDED_PR_POLICY",
            "usgs_comcat": usgs_result.get("status") == "COMPLETED",
            "usgs_catalog_integrity": selected_belts_complete,
            "selected_seismic_belts": len(selected_belts),
            "five_seismic_belts": "NOT_RUN_IN_BOUNDED_PR_MODE",
            "passed": selected_belts_complete and usgs_result.get("status") == "COMPLETED",
            "scope": "BOUNDED_PR_SMOKE_ONLY_NOT_FULL_DOMAIN_VALIDATION",
        }
    else:
        source_gate = required_source_gate(gem_result, usgs_result, belt_results)
    result = {
        "audit_id": "CHAOS-P2.2.3-DOMAIN-NULL-DECLUSTERING",
        "status": "completed" if source_gate["passed"] else "incomplete",
        "required_source_gate": source_gate,
        "repository_commit": os.getenv("GITHUB_SHA", "local-unresolved"),
        "audit_storage_isolated": True,
        "source_snapshot_root": str((output_dir / "source_snapshots").as_posix()),
        "detector": {
            "name": "BreakDetectorV1",
            "mode": "markov_cusum",
            "threshold_h": DEFAULT_MARKOV_THRESHOLD,
            "frozen": True,
        },
        "source_policy": {
            "original_usgs_event_catalogs_preserved": True,
            "declustering_output_is_labeled_copy": True,
            "no_cross_belt_pooling": True,
            "catalog_completeness": "NOT_ASSESSED; no inferential Poisson or ETAS claims accepted",
        },
        "world_bank_gem": gem_result,
        "fred": fred_result,
        "eia": eia_result,
        "usgs_source_ingestion": usgs_result,
        "seismic_belts": belt_results,
        "interpretation_limits": [
            "Gardner-Knopoff windows were empirically calibrated in Southern California; transfer to these belts is unvalidated.",
            "Catalog query minimum magnitude is not an estimate of Mc(t, region).",
            "The homogeneous Poisson simulation is a rate-matched exploratory benchmark, not an accepted seismic null or false-positive rate.",
            "A residual catalog is not assumed to be Poisson after declustering.",
            "No detector code, threshold, Phase 1 file, historical manifest, or experiments archive is modified.",
        ],
    }
    write_json(output_dir / "summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("artifacts/domain_null_and_declustering"))
    parser.add_argument("--poisson-replicates", type=int, default=200)
    parser.add_argument("--gem-snapshot-dir", type=Path, default=None)
    parser.add_argument("--isolated-usgs-only", action="store_true")
    parser.add_argument("--max-belts", type=int, default=None)
    args = parser.parse_args()
    if args.poisson_replicates < 1:
        parser.error("--poisson-replicates must be positive")
    try:
        started = time.monotonic()
        result = run_audit(
            args.output_dir,
            args.poisson_replicates,
            args.gem_snapshot_dir,
            isolated_usgs_only=args.isolated_usgs_only,
            max_belts=args.max_belts,
        )
        print(
            "DOMAIN_NULL_AUDIT_COMPLETE "
            f"belts={len(result['seismic_belts'])} "
            f"elapsed_seconds={round(time.monotonic() - started, 3)} "
            f"source_gate={result['required_source_gate']['passed']}",
            flush=True,
        )
        if not result["required_source_gate"]["passed"]:
            return 2
    except Exception as exc:
        parser.exit(2, f"DOMAIN NULL AUDIT ERROR: {type(exc).__name__}: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
