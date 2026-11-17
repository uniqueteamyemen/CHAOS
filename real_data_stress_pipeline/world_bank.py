"""World Bank Pink Sheet workbook and GEM monthly-series adapters."""
from __future__ import annotations

import calendar
import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
from openpyxl import load_workbook

from .fetch import SourceFetcher

PINK_SHEET_URL = (
    "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/"
    "related/CMO-Historical-Data-Monthly.xlsx"
)
GEM_SOURCE_ID = 15
GEM_API = "https://api.worldbank.org/v2"


def parse_month(value: Any) -> str | None:
    if isinstance(value, datetime):
        return f"{value.year:04d}-{value.month:02d}"
    if isinstance(value, date):
        return f"{value.year:04d}-{value.month:02d}"
    if value is None:
        return None
    text = str(value).strip()
    patterns = (
        r"^(\d{4})[-/]([01]?\d)$",
        r"^(\d{4})M([01]?\d)$",
        r"^(\d{4})/([01]?\d)/\d{1,2}$",
        r"^(\d{4})(\d{2})$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            year, month = int(match.group(1)), int(match.group(2))
            if 1 <= month <= 12:
                return f"{year:04d}-{month:02d}"
    return None


def _month_index(period: str) -> int:
    year, month = map(int, period.split("-"))
    return year * 12 + month - 1


def _longest_contiguous(points: dict[str, float]) -> list[tuple[str, float]]:
    ordered = sorted(points.items(), key=lambda item: _month_index(item[0]))
    best: list[tuple[str, float]] = []
    current: list[tuple[str, float]] = []
    previous_index: int | None = None
    for period, value in ordered:
        index = _month_index(period)
        if previous_index is None or index == previous_index + 1:
            current.append((period, value))
        else:
            if len(current) > len(best):
                best = current
            current = [(period, value)]
        previous_index = index
    if len(current) > len(best):
        best = current
    return best


def _find_pink_sheet_table(workbook_path: Path) -> dict:
    wb = load_workbook(workbook_path, read_only=True, data_only=True)
    best: dict | None = None

    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        max_columns = max((len(row) for row in rows), default=0)
        if max_columns < 3:
            continue

        parsed_rows: list[tuple[int, str, tuple[Any, ...]]] = []
        date_column_scores: dict[int, int] = defaultdict(int)
        for row_index, row in enumerate(rows):
            if not row:
                continue
            for column_index, value in enumerate(row):
                period = parse_month(value)
                if period:
                    date_column_scores[column_index] += 1
                    parsed_rows.append((row_index, period, row))
        if not date_column_scores:
            continue

        date_column = max(date_column_scores, key=date_column_scores.get)
        data_rows = []
        for row_index, period, row in parsed_rows:
            if date_column >= len(row):
                continue
            if parse_month(row[date_column]) != period:
                continue
            data_rows.append((row_index, period, row))
        if len(data_rows) < 100:
            continue

        first_data_row = min(item[0] for item in data_rows)
        header_candidates = range(max(0, first_data_row - 8), first_data_row)
        header_row_index = None
        best_score = -1
        data_columns = [
            col for col in range(max_columns) if col != date_column
        ]
        for candidate_index in header_candidates:
            header = rows[candidate_index]
            score = sum(
                1 for col in data_columns
                if col < len(header)
                and isinstance(header[col], str)
                and header[col].strip()
                and parse_month(header[col]) is None
            )
            if score > best_score:
                best_score = score
                header_row_index = candidate_index
        if header_row_index is None or best_score < 2:
            continue

        candidate = {
            "sheet_name": ws.title,
            "rows": rows,
            "date_column": date_column,
            "header_row_index": header_row_index,
            "data_rows": data_rows,
            "column_count": max_columns,
            "score": len(data_rows),
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate

    wb.close()
    if best is None:
        raise ValueError("pink_sheet_monthly_table_not_found")
    return best


def extract_pink_sheet_series(workbook_path: Path) -> tuple[list[dict], dict]:
    table = _find_pink_sheet_table(workbook_path)
    rows = table["rows"]
    header = rows[table["header_row_index"]]
    grouped: dict[int, dict[str, float]] = defaultdict(dict)

    for _, period, row in table["data_rows"]:
        for col in range(table["column_count"]):
            if col == table["date_column"] or col >= len(row):
                continue
            raw = row[col]
            if raw is None or isinstance(raw, str) and not raw.strip():
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if np.isfinite(value):
                grouped[col][period] = value

    series: list[dict] = []
    for col, observations in grouped.items():
        label = str(header[col]).strip() if col < len(header) else ""
        if not label or label.lower() in {"none", "nan"}:
            continue
        contiguous = _longest_contiguous(observations)
        if len(contiguous) < 87:
            continue
        periods = [item[0] for item in contiguous]
        prices = np.asarray([item[1] for item in contiguous], dtype=float)
        # Prices must be positive for log-return construction; invalid points
        # split the sequence rather than being imputed.
        valid_runs: list[list[tuple[str, float]]] = []
        run: list[tuple[str, float]] = []
        previous: int | None = None
        for period, price in contiguous:
            idx = _month_index(period)
            if price <= 0:
                if len(run) > 0:
                    valid_runs.append(run)
                run = []
                previous = None
                continue
            if previous is None or idx == previous + 1:
                run.append((period, price))
            else:
                if run:
                    valid_runs.append(run)
                run = [(period, price)]
            previous = idx
        if run:
            valid_runs.append(run)
        best_run = max(valid_runs, key=len, default=[])
        if len(best_run) < 2:
            continue
        price_periods = [item[0] for item in best_run]
        price_values = np.asarray([item[1] for item in best_run], dtype=float)
        log_returns = np.diff(np.log(price_values))
        return_periods = price_periods[1:]
        series.append({
            "source_id": "WORLD_BANK_PINK_SHEET",
            "series_id": f"PINK_SHEET::{col}::{label}",
            "series_name": label,
            "category": classify_commodity(label),
            "frequency": "monthly",
            "transform": "first_difference(log(monthly_price))",
            "periods": return_periods,
            "values": log_returns.tolist(),
            "price_observations": len(price_values),
            "observation_count": len(log_returns),
            "source_column_index": col,
            "source_sheet": table["sheet_name"],
            "source_header_row": table["header_row_index"] + 1,
        })

    summary = {
        "sheet_name": table["sheet_name"],
        "date_column_index": table["date_column"],
        "header_row_index": table["header_row_index"] + 1,
        "series_discovered": len(series),
        "series_with_more_than_500_log_returns": sum(
            item["observation_count"] > 500 for item in series
        ),
        "row_count_with_month_dates": len(table["data_rows"]),
    }
    return series, summary


def classify_commodity(name: str) -> str:
    value = name.lower()
    if any(term in value for term in ("crude", "brent", "wti", "coal", "gas", "oil", "petroleum", "propane", "lng")):
        return "energy"
    if any(term in value for term in ("gold", "silver", "copper", "aluminum", "aluminium", "nickel", "zinc", "tin", "lead", "iron", "steel", "uranium")):
        return "metals"
    if any(term in value for term in ("wheat", "maize", "corn", "rice", "soy", "palm", "sugar", "coffee", "cocoa", "cotton", "meat", "beef", "chicken", "fertilizer", "urea", "phosphate")):
        return "agriculture_food"
    return "other_commodity"


def _extract_monthly_frequency(metadata: dict) -> bool:
    candidates = [
        metadata.get("periodicity"),
        metadata.get("frequency"),
        metadata.get("frequencyDesc"),
        metadata.get("period"),
    ]
    joined = " ".join(str(item or "") for item in candidates).lower()
    return "monthly" in joined or re.search(r"\bmonth(?:ly)?\b", joined) is not None


def fetch_gem_series(
    fetcher: SourceFetcher,
    max_indicators: int = 16,
    period_window: str = "1990:2023",
) -> tuple[list[dict], dict]:
    metadata_url = f"{GEM_API}/sources/{GEM_SOURCE_ID}/series"
    metadata_payload, meta_snapshot = fetcher.get_json(
        "worldbank_gem_series_metadata",
        metadata_url,
        params={"format": "json", "per_page": 20000, "page": 1},
        subdirectory="worldbank_gem",
    )
    if not isinstance(metadata_payload, list) or len(metadata_payload) < 2:
        raise ValueError("gem_series_metadata_response_unexpected")
    metadata_rows = metadata_payload[1] or []
    monthly_metadata = [
        item for item in metadata_rows
        if isinstance(item, dict) and _extract_monthly_frequency(item)
    ]

    preferred_terms = (
        "consumer price", "price index", "industrial production",
        "exchange rate", "interest rate", "stock market", "money",
        "reserves", "trade", "exports", "imports",
    )
    monthly_metadata.sort(
        key=lambda item: (
            -sum(term in str(item.get("name", "")).lower() for term in preferred_terms),
            str(item.get("id", "")),
        )
    )
    chosen = monthly_metadata[:max_indicators]
    summaries: list[dict] = []
    series: list[dict] = []

    for metadata in chosen:
        indicator_id = str(metadata.get("id", "")).strip()
        if not indicator_id:
            continue
        url = f"{GEM_API}/country/all/indicator/{indicator_id}"
        params = {
            "source": GEM_SOURCE_ID,
            "date": period_window,
            "format": "json",
            "per_page": 20000,
            "page": 1,
        }
        payload, snapshot = fetcher.get_json(
            f"worldbank_gem_{indicator_id}",
            url,
            params=params,
            subdirectory="worldbank_gem",
        )
        if not isinstance(payload, list) or len(payload) < 2:
            summaries.append({"indicator_id": indicator_id, "status": "invalid_response"})
            continue
        meta = payload[0] or {}
        rows = payload[1] or []
        pages = int(meta.get("pages") or 1)
        for page in range(2, pages + 1):
            page_params = dict(params)
            page_params["page"] = page
            extra, _ = fetcher.get_json(
                f"worldbank_gem_{indicator_id}_page_{page}",
                url,
                params=page_params,
                subdirectory="worldbank_gem",
            )
            if isinstance(extra, list) and len(extra) > 1 and extra[1]:
                rows.extend(extra[1])

        grouped: dict[str, dict] = {}
        skipped_nonmonthly = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            period = parse_month(row.get("date"))
            if period is None:
                skipped_nonmonthly += 1
                continue
            value = row.get("value")
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if not np.isfinite(numeric):
                continue
            country = row.get("country") or {}
            country_name = str(country.get("value") or row.get("countryiso3code") or "unknown")
            iso = str(row.get("countryiso3code") or row.get("country", {}).get("id") or country_name)
            key = f"{iso}::{indicator_id}"
            entry = grouped.setdefault(key, {
                "source_id": "WORLD_BANK_GEM",
                "series_id": f"GEM::{iso}::{indicator_id}",
                "series_name": f"{country_name} — {metadata.get('name', indicator_id)}",
                "category": "macro",
                "frequency": "monthly",
                "transform": "raw_monthly_indicator",
                "_observations": {},
                "country_code": iso,
                "indicator_id": indicator_id,
                "indicator_name": metadata.get("name"),
            })
            entry["_observations"][period] = numeric

        valid_for_indicator = 0
        for entry in grouped.values():
            points = _longest_contiguous(entry.pop("_observations"))
            if len(points) < 87:
                continue
            entry["periods"] = [period for period, _ in points]
            entry["values"] = [value for _, value in points]
            entry["observation_count"] = len(points)
            entry["source_indicator_metadata"] = {
                "periodicity": metadata.get("periodicity"),
                "frequency": metadata.get("frequency"),
                "source_id": GEM_SOURCE_ID,
                "source_name": "Global Economic Monitor",
            }
            series.append(entry)
            valid_for_indicator += 1

        summaries.append({
            "indicator_id": indicator_id,
            "indicator_name": metadata.get("name"),
            "metadata_frequency": metadata.get("periodicity") or metadata.get("frequency"),
            "api_rows": len(rows),
            "non_monthly_or_unparsed_rows": skipped_nonmonthly,
            "country_series_g0_ge_87": valid_for_indicator,
            "raw_sha256": snapshot.sha256,
        })

    return series, {
        "metadata_raw_sha256": meta_snapshot.sha256,
        "monthly_indicators_discovered": len(monthly_metadata),
        "monthly_indicators_queried": len(chosen),
        "indicator_summaries": summaries,
    }
