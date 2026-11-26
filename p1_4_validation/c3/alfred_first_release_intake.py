"""Acquire first-release, point-in-time C3 source tapes from ALFRED.

This is an evidence-intake step only. It does not import or execute any detector.
Values are taken from the earliest ALFRED vintage in which an observation exists.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import time
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "p1_4_validation" / "c3" / "c3_source_contract_v1.json"
ALFRED_GRAPH = "https://alfred.stlouisfed.org/graph/alfredgraph.csv"
USER_AGENT = "CHAOS-C3-point-in-time-intake/1.0"
BATCH_SIZE = 10
REQUEST_DELAY_SECONDS = 1.0
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


class VintageOptionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.dates: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "option":
            return
        value = dict(attrs).get("value")
        if value and DATE_RE.fullmatch(value):
            self.dates.add(value)


def extract_vintage_dates(html: str, start: str, end: str) -> list[str]:
    parser = VintageOptionParser()
    parser.feed(html)
    dates = sorted(d for d in parser.dates if start <= d <= end)
    if not dates:
        raise ValueError(f"ALFRED_VINTAGE_DATES_NOT_FOUND:{start}:{end}")
    return dates


def _http_get(url: str, timeout: int = 60) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise RuntimeError(f"ALFRED_HTTP_STATUS:{status}:{url}")
        return response.read()


def fetch_vintage_dates(series: dict) -> list[str]:
    page = _http_get(series["download_page_url"])
    html = page.decode("utf-8", errors="strict")
    return extract_vintage_dates(
        html,
        series["vintage_search_start"],
        series["vintage_search_end"],
    )


def _missing(value: str | None) -> bool:
    return value is None or value.strip() in {"", ".", "NA", "N/A", "nan", "NaN"}


def parse_vintage_batch(
    csv_text: str,
    series_id: str,
    vintage_dates: list[str],
) -> dict[str, dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise ValueError(f"ALFRED_EMPTY_CSV:{series_id}")
    date_field = reader.fieldnames[0]
    if date_field not in {"observation_date", "DATE"}:
        raise ValueError(f"ALFRED_DATE_COLUMN_MISMATCH:{series_id}:{date_field}")
    expected_fields = [f"{series_id}_{d.replace('-', '')}" for d in vintage_dates]
    if reader.fieldnames[1:] != expected_fields:
        raise ValueError(
            "ALFRED_HEADER_MISMATCH:"
            f"{series_id}:expected={expected_fields}:actual={reader.fieldnames[1:]}"
        )

    first_values: dict[str, dict[str, str]] = {}
    for row in reader:
        observation_date = (row.get(date_field) or "").strip()
        if not observation_date or not DATE_RE.fullmatch(observation_date):
            continue
        for vintage_date, field in zip(vintage_dates, expected_fields):
            value = row.get(field)
            if _missing(value):
                continue
            if observation_date not in first_values:
                try:
                    numeric = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"ALFRED_NON_NUMERIC_VALUE:{series_id}:{observation_date}:{value}"
                    ) from exc
                if not (float("-inf") < numeric < float("inf")):
                    raise ValueError(
                        f"ALFRED_NON_FINITE_VALUE:{series_id}:{observation_date}:{value}"
                    )
                first_values[observation_date] = {
                    "value": format(numeric, ".15g"),
                    "available_at": vintage_date,
                }
    return first_values


def _chunks(values: list[str], size: int):
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def fetch_series_initial_releases(series: dict, output_dir: Path) -> tuple[list[dict], list[dict]]:
    series_id = series["series_id"]
    observation_start = date.fromisoformat(series["observation_start"])
    observation_end = date.fromisoformat(series["observation_end"])
    all_vintages = fetch_vintage_dates(series)
    selected = [
        d for d in all_vintages
        if date.fromisoformat(d) >= observation_start - timedelta(days=60)
        and date.fromisoformat(d) <= observation_end + timedelta(days=60)
    ]
    if not selected:
        raise ValueError(f"NO_VINTAGES_IN_CAPTURE_WINDOW:{series_id}")

    raw_dir = output_dir / "raw_vintage_batches" / series_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    first_values: dict[str, dict[str, str]] = {}
    batch_records: list[dict] = []

    for batch_number, vintage_batch in enumerate(_chunks(selected, BATCH_SIZE), start=1):
        ids = ",".join([series_id] * len(vintage_batch))
        dates = ",".join(vintage_batch)
        query = urlencode({"id": ids, "vintage_date": dates})
        url = f"{ALFRED_GRAPH}?{query}"
        raw = _http_get(url)
        raw_path = raw_dir / f"batch_{batch_number:03d}.csv"
        raw_path.write_bytes(raw)
        batch_values = parse_vintage_batch(
            raw.decode("utf-8-sig", errors="strict"),
            series_id,
            vintage_batch,
        )
        for observation_date, entry in batch_values.items():
            if observation_date not in first_values:
                first_values[observation_date] = entry
        batch_records.append({
            "batch": batch_number,
            "requested_vintage_dates": vintage_batch,
            "file": str(raw_path.relative_to(output_dir)),
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
        })
        time.sleep(REQUEST_DELAY_SECONDS)

    records: list[dict] = []
    for observation_text, entry in sorted(first_values.items()):
        observation = date.fromisoformat(observation_text)
        available = date.fromisoformat(entry["available_at"])
        if observation < observation_start or observation > observation_end:
            continue
        if available < observation:
            raise ValueError(
                f"ALFRED_LOOKAHEAD_VINTAGE:{series_id}:{observation}:{available}"
            )
        if available < date.fromisoformat(series["expected_alfred_release_start"]):
            raise ValueError(
                f"ALFRED_PRE_ARCHIVE_AVAILABILITY:{series_id}:{observation}:{available}"
            )
        records.append({
            "event_id": series["event_id"],
            "series_id": series_id,
            "observation_date": observation.isoformat(),
            "available_at": available.isoformat(),
            "value": entry["value"],
            "frequency": series["frequency"],
            "units": series["units"],
            "value_semantics": "FIRST_ALFRED_VINTAGE_VALUE",
        })

    if len(records) < int(series["expected_initial_observation_count_min"]):
        raise ValueError(
            f"C3_INSUFFICIENT_FIRST_RELEASE_OBSERVATIONS:{series_id}:"
            f"{len(records)}<{series['expected_initial_observation_count_min']}"
        )
    observations = [r["observation_date"] for r in records]
    availability = [r["available_at"] for r in records]
    if len(observations) != len(set(observations)):
        raise ValueError(f"C3_DUPLICATE_OBSERVATION_DATES:{series_id}")
    if availability != sorted(availability):
        raise ValueError(f"C3_NON_MONOTONIC_AVAILABILITY:{series_id}")

    return records, batch_records


def write_intake(contract_path: Path, output_dir: Path) -> dict:
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes)
    if contract.get("contract_id") != "CHAOS_P1_4_C3_POINT_IN_TIME_SOURCE_INTAKE_V1":
        raise ValueError("C3_SOURCE_CONTRACT_ID_MISMATCH")

    output_dir.mkdir(parents=True, exist_ok=True)
    all_records: list[dict] = []
    series_results: list[dict] = []
    raw_batches: list[dict] = []

    for series in contract["events"]:
        records, batches = fetch_series_initial_releases(series, output_dir)
        all_records.extend(records)
        raw_batches.extend(batches)
        series_results.append({
            "event_id": series["event_id"],
            "series_id": series["series_id"],
            "observation_start": series["observation_start"],
            "observation_end": series["observation_end"],
            "observation_count": len(records),
            "first_observation": records[0]["observation_date"],
            "last_observation": records[-1]["observation_date"],
            "first_available_at": records[0]["available_at"],
            "last_available_at": records[-1]["available_at"],
            "vintage_batches": len(batches),
        })

    tape_path = output_dir / contract["intake_output"]["normalized_file"]
    fieldnames = [
        "event_id", "series_id", "observation_date", "available_at",
        "value", "frequency", "units", "value_semantics",
    ]
    with tape_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(
            all_records,
            key=lambda x: (x["series_id"], x["available_at"], x["observation_date"]),
        ))

    manifest = {
        "artifact_type": "CHAOS_P1_4_C3_SOURCE_INTAKE",
        "status": "SOURCE_TAPES_ACQUIRED_NOT_DETECTOR_EXECUTED",
        "contract_sha256": sha256_bytes(contract_bytes),
        "shock_event_contract_git_blob": contract["frozen_references"]["shock_event_contract_git_blob"],
        "source_commit": os.environ.get("GITHUB_SHA"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "acquisition_method": "ALFRED historical vintage CSV snapshots; earliest non-missing value per observation",
        "series": series_results,
        "point_count": len(all_records),
        "raw_vintage_batches": raw_batches,
        "normalized_tape": {
            "file": tape_path.name,
            "bytes": tape_path.stat().st_size,
            "sha256": sha256_file(tape_path),
        },
        "guardrails": contract["guardrails"],
        "detector_execution_performed": False,
    }
    manifest_path = output_dir / contract["intake_output"]["manifest_file"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = write_intake(args.contract, args.output)
    print(json.dumps({
        "status": manifest["status"],
        "point_count": manifest["point_count"],
        "series": manifest["series"],
        "tape_sha256": manifest["normalized_tape"]["sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
