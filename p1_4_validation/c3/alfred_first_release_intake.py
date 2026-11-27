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
import socket
import time
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "p1_4_validation" / "c3" / "c3_source_contract_v1.json"
ALFRED_GRAPH = "https://alfred.stlouisfed.org/graph/alfredgraph.csv"
USER_AGENT = "CHAOS-C3-point-in-time-intake/1.0"
BATCH_SIZE = 10
REQUEST_DELAY_SECONDS = 1.0
HTTP_TIMEOUT_SECONDS = 120
HTTP_MAX_ATTEMPTS = 5
HTTP_BACKOFF_INITIAL_SECONDS = 2.0
HTTP_BACKOFF_MAX_SECONDS = 30.0
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


def _http_get(url: str, timeout: int = HTTP_TIMEOUT_SECONDS) -> bytes:
    """Fetch ALFRED idempotent GETs with bounded retry and explicit diagnostics."""
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,text/csv, */*;q=0.8",
            "Cache-Control": "no-cache",
        },
    )
    retryable_http_statuses = {408, 425, 429, 500, 502, 503, 504}
    last_error: Exception | None = None

    for attempt in range(1, HTTP_MAX_ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise RuntimeError(f"ALFRED_HTTP_STATUS:{status}:{url}")
                payload = response.read()
                if not payload:
                    raise RuntimeError(f"ALFRED_EMPTY_RESPONSE:{url}")
                return payload
        except HTTPError as exc:
            last_error = exc
            if exc.code not in retryable_http_statuses:
                raise RuntimeError(
                    f"ALFRED_HTTP_NONRETRYABLE:{exc.code}:{url}"
                ) from exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
        except (URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
            last_error = exc
            retry_after = None

        if attempt >= HTTP_MAX_ATTEMPTS:
            break

        backoff = min(
            HTTP_BACKOFF_INITIAL_SECONDS * (2 ** (attempt - 1)),
            HTTP_BACKOFF_MAX_SECONDS,
        )
        try:
            server_delay = float(retry_after) if retry_after else 0.0
        except (TypeError, ValueError):
            server_delay = 0.0
        delay = min(max(backoff, server_delay), 60.0)
        print(
            f"ALFRED_RETRY attempt={attempt}/{HTTP_MAX_ATTEMPTS - 1} "
            f"next_delay_seconds={delay:g} error={type(last_error).__name__}",
            flush=True,
        )
        time.sleep(delay)

    raise RuntimeError(
        f"ALFRED_REQUEST_EXHAUSTED:attempts={HTTP_MAX_ATTEMPTS}:"
        f"timeout_seconds={timeout}:url={url}:"
        f"last_error={type(last_error).__name__}:{last_error}"
    ) from last_error


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


def build_vintage_batch_url(
    series_id: str,
    vintage_dates: list[str],
    observation_start: str,
    observation_end: str,
) -> str:
    """Build a bounded ALFRED snapshot request without changing vintage semantics."""
    query = urlencode({
        "id": ",".join([series_id] * len(vintage_dates)),
        "vintage_date": ",".join(vintage_dates),
        "observation_start": observation_start,
        "observation_end": observation_end,
    })
    return f"{ALFRED_GRAPH}?{query}"


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
        url = build_vintage_batch_url(
            series_id,
            vintage_batch,
            observation_start.isoformat(),
            observation_end.isoformat(),
        )
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
        record = {
            "series_id": series_id,
            "observation_date": observation.isoformat(),
            "available_at": available.isoformat(),
            "value": entry["value"],
            "frequency": series["frequency"],
            "units": series["units"],
            "value_semantics": "FIRST_ALFRED_VINTAGE_VALUE",
        }
        # V1 remains event-per-series; V2 stores one tape per unique series.
        # Event-to-series relationships live in the separate pre-registered map.
        if series.get("event_id"):
            record["event_id"] = series["event_id"]
        records.append(record)

    minimum_count = int(
        series.get("minimum_observation_count",
                   series.get("expected_initial_observation_count_min", 0))
    )
    if len(records) < minimum_count:
        raise ValueError(
            f"C3_INSUFFICIENT_FIRST_RELEASE_OBSERVATIONS:{series_id}:"
            f"{len(records)}<{minimum_count}"
        )
    if series.get("anchor_date"):
        anchor = date.fromisoformat(series["anchor_date"])
        pre_event = sum(date.fromisoformat(row["observation_date"]) < anchor for row in records)
        post_event = sum(date.fromisoformat(row["observation_date"]) >= anchor for row in records)
        min_pre = int(series.get("minimum_pre_event_observations", 0))
        min_post = int(series.get("minimum_post_event_observations", 0))
        if pre_event < min_pre:
            raise ValueError(
                f"C3_INSUFFICIENT_PRE_EVENT_HISTORY:{series_id}:{pre_event}<{min_pre}"
            )
        if post_event < min_post:
            raise ValueError(
                f"C3_INSUFFICIENT_POST_EVENT_HISTORY:{series_id}:{post_event}<{min_post}"
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
    contract_id = contract.get("contract_id")
    supported_contracts = {
        "CHAOS_P1_4_C3_POINT_IN_TIME_SOURCE_INTAKE_V1",
        "CHAOS_P1_4_C3_EXPANDED_EVENT_COHORT_V1",
        "CHAOS_P1_4_C3_EXPANDED_EVENT_COHORT_V2_1",
    }
    if contract_id not in supported_contracts:
        raise ValueError("C3_SOURCE_CONTRACT_ID_MISMATCH")

    output_dir.mkdir(parents=True, exist_ok=True)
    all_records: list[dict] = []
    series_results: list[dict] = []
    raw_batches: list[dict] = []
    # Original V1 contract is event-per-series. Expanded V1 fetches each unique
    # series once, while multiple historical anchors are represented separately.
    series_specs = contract.get("series", contract.get("events", []))
    if not series_specs:
        raise ValueError("C3_SOURCE_CONTRACT_HAS_NO_SERIES")

    for series in series_specs:
        records, batches = fetch_series_initial_releases(series, output_dir)
        all_records.extend(records)
        raw_batches.extend(batches)
        summary = {
            "series_id": series["series_id"],
            "observation_start": series["observation_start"],
            "observation_end": series["observation_end"],
            "observation_count": len(records),
            "pre_event_observations": (
                sum(date.fromisoformat(r["observation_date"]) < date.fromisoformat(series["anchor_date"]) for r in records)
                if series.get("anchor_date") else None
            ),
            "post_event_observations": (
                sum(date.fromisoformat(r["observation_date"]) >= date.fromisoformat(series["anchor_date"]) for r in records)
                if series.get("anchor_date") else None
            ),
            "first_observation": records[0]["observation_date"],
            "last_observation": records[-1]["observation_date"],
            "first_available_at": records[0]["available_at"],
            "last_available_at": records[-1]["available_at"],
            "vintage_batches": len(batches),
        }
        if series.get("event_id"):
            summary["event_id"] = series["event_id"]
        series_results.append(summary)

    tape_path = output_dir / contract["intake_output"]["normalized_file"]
    fieldnames = (
        ["event_id", "series_id", "observation_date", "available_at",
         "value", "frequency", "units", "value_semantics"]
        if contract_id == "CHAOS_P1_4_C3_POINT_IN_TIME_SOURCE_INTAKE_V1"
        else ["series_id", "observation_date", "available_at",
              "value", "frequency", "units", "value_semantics"]
    )
    with tape_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(
            all_records,
            key=lambda x: (x["series_id"], x["available_at"], x["observation_date"]),
        ))

    manifest = {
        "artifact_type": "CHAOS_P1_4_C3_SOURCE_INTAKE",
        "contract_id": contract_id,
        "contract_version": contract.get("contract_version"),
        "status": "SOURCE_TAPES_ACQUIRED_NOT_DETECTOR_EXECUTED",
        "event_count": len(contract.get("events", [])),
        "series_count": len(series_specs),
        "event_series_pair_count": (
            sum(len(event.get("expected_sign_by_series", {}))
                for event in contract.get("events", []))
            if any("expected_sign_by_series" in event for event in contract.get("events", []))
            else len(series_specs)
        ),
        "contract_sha256": sha256_bytes(contract_bytes),
        "shock_event_contract_git_blob": contract["frozen_references"]["shock_event_contract_git_blob"],
        "shock_event_contract_sha256": contract["frozen_references"].get("shock_event_contract_sha256"),
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
