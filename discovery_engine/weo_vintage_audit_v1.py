"""Auditable cross-vintage review of the IMF WEO 2020 real-GDP-growth signal.

The script compares published historical vintages with the committed April 2026
WEO panel. It preserves raw downloaded vintage files as workflow artifacts,
records their URLs/SHA-256, and derives only a pre-2020 Theil-Sen extrapolation
diagnostic. It does not call the 2020 value an observation available in 2020,
and it does not repeat the symmetric point-anomaly detector (which requires
post-2020 observations).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

CONTRACT_ID = "CHAOS_WEO_GDP_GROWTH_VINTAGE_AUDIT_V1"
YEAR_COLUMNS = [str(year) for year in range(2016, 2021)]
REQUIRED_PANEL_COLUMNS = {"entity_code", "imf_entity_name", "year", "imf__NGDP_RPCH"}
WE0_SUBJECT_CODE = "NGDP_RPCH"

VINTAGES = [
    {
        "vintage_id": "WEO_2020_OCT",
        "release_label": "October 2020",
        "release_page": "https://www.imf.org/en/publications/weo/weo-database/2020/october",
        "download_url": "https://www.imf.org/-/media/files/publications/weo/weo-database/2020/02/weooct2020all.xls",
    },
    {
        "vintage_id": "WEO_2021_APR",
        "release_label": "April 2021",
        "release_page": "https://www.imf.org/en/publications/weo/weo-database/2021/april",
        "download_url": "https://www.imf.org/-/media/files/publications/weo/weo-database/2021/weoapr2021all.xls",
    },
]


class VintageAuditError(ValueError):
    """Raised when official vintage data cannot be parsed or matched safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def download_official_vintage(url: str, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CHAOS-Research/1.0 (source-vintage reproducibility audit)",
            "Accept": "*/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            status = int(response.status)
            content_type = response.headers.get("Content-Type", "")
            data = response.read()
    except Exception as exc:
        raise VintageAuditError(f"official_vintage_download_failed:{url}:{exc}") from exc
    if status != 200:
        raise VintageAuditError(f"official_vintage_http_status:{status}:{url}")
    if len(data) < 100_000:
        raise VintageAuditError(f"official_vintage_payload_too_small:{len(data)}:{url}")
    if data.lstrip().startswith((b"<!DOCTYPE html", b"<html", b"<?xml")):
        raise VintageAuditError(f"official_vintage_download_returned_markup:{url}")
    path.write_bytes(data)
    return {
        "url": url,
        "http_status": status,
        "content_type": content_type,
        "bytes": len(data),
        "sha256": sha256_file(path),
        "local_raw_file": path.name,
    }


def _decode_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise VintageAuditError(f"vintage_text_decode_failed:{path.name}")


def read_weo_country_file(path: Path) -> dict[str, dict[str, Any]]:
    """Read the IMF legacy tab-delimited By Countries file without guessing columns."""
    text = _decode_text(path)
    lines = text.splitlines()
    header_index = None
    for index, line in enumerate(lines[:30]):
        normalized = {part.strip().strip('"').casefold() for part in line.split("\t")}
        if "iso" in normalized and "weo subject code" in normalized:
            header_index = index
            break
    if header_index is None:
        preview = "\n".join(lines[:8])[:1500]
        raise VintageAuditError(f"weo_tsv_header_not_found:{path.name}:{preview}")

    reader = csv.DictReader(lines[header_index:], delimiter="\t")
    if not reader.fieldnames:
        raise VintageAuditError(f"weo_tsv_fieldnames_missing:{path.name}")
    headers = [str(item or "").strip().strip('"') for item in reader.fieldnames]
    if len(set(headers)) != len(headers):
        raise VintageAuditError(f"weo_tsv_duplicate_headers:{path.name}")
    required = {"ISO", "WEO Subject Code", "Country", *YEAR_COLUMNS}
    missing = sorted(required - set(headers))
    if missing:
        raise VintageAuditError(f"weo_tsv_required_columns_missing:{path.name}:{missing}")

    result: dict[str, dict[str, Any]] = {}
    matched_rows = 0
    for row_number, raw in enumerate(reader, header_index + 2):
        row = {str(k).strip().strip('"'): (v or "").strip().strip('"') for k, v in raw.items() if k is not None}
        if row.get("WEO Subject Code") != WE0_SUBJECT_CODE:
            continue
        iso = row.get("ISO", "").strip().upper()
        if not iso or len(iso) != 3 or not iso.isalpha():
            # IMF country-group aggregates do not necessarily have an ISO code.
            continue
        if iso in result:
            raise VintageAuditError(f"duplicate_weo_iso_subject_row:{path.name}:{iso}:{row_number}")
        values: dict[str, float | None] = {}
        raw_values: dict[str, str] = {}
        for year in YEAR_COLUMNS:
            raw_value = row.get(year, "").strip()
            raw_values[year] = raw_value
            if not raw_value or raw_value.casefold() in {
                "n/a", "na", "--", "...", "no data", "not available"
            }:
                values[year] = None
                continue
            try:
                decimal_value = Decimal(raw_value.replace(",", ""))
            except InvalidOperation as exc:
                raise VintageAuditError(
                    f"weo_numeric_value_invalid:{path.name}:{iso}:{year}:{raw_value}"
                ) from exc
            if not decimal_value.is_finite():
                raise VintageAuditError(
                    f"weo_numeric_value_nonfinite:{path.name}:{iso}:{year}:{raw_value}"
                )
            number = float(decimal_value)
            if not math.isfinite(number):
                raise VintageAuditError(
                    f"weo_numeric_value_overflow:{path.name}:{iso}:{year}:{raw_value}"
                )
            values[year] = number
        result[iso] = {
            "iso": iso,
            "country_name": row.get("Country", ""),
            "values": values,
            "raw_values": raw_values,
            "estimates_start_after_raw": row.get("Estimates Start After", ""),
            "country_series_notes": row.get("Country/Series-specific Notes", ""),
        }
        matched_rows += 1
    if not result:
        raise VintageAuditError(f"weo_subject_rows_not_found:{path.name}:{WE0_SUBJECT_CODE}")
    return result


def _parse_current_panel(path: Path) -> dict[str, dict[int, float]]:
    output: dict[str, dict[int, float]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not REQUIRED_PANEL_COLUMNS.issubset(set(reader.fieldnames)):
            raise VintageAuditError(
                f"current_panel_columns_missing:{sorted(REQUIRED_PANEL_COLUMNS-set(reader.fieldnames or []))}"
            )
        for row_number, row in enumerate(reader, 2):
            entity = (row.get("entity_code") or "").strip().upper()
            if not entity:
                raise VintageAuditError(f"current_panel_entity_missing:{row_number}")
            try:
                year = int(row["year"])
            except (TypeError, ValueError) as exc:
                raise VintageAuditError(f"current_panel_year_invalid:{row_number}") from exc
            if year not in range(2016, 2021):
                continue
            raw = (row.get("imf__NGDP_RPCH") or "").strip()
            if not raw:
                continue
            try:
                value = float(Decimal(raw))
            except (InvalidOperation, ValueError) as exc:
                raise VintageAuditError(f"current_panel_value_invalid:{entity}:{year}:{raw}") from exc
            if not math.isfinite(value):
                raise VintageAuditError(f"current_panel_value_nonfinite:{entity}:{year}")
            values = output.setdefault(entity, {})
            if year in values:
                raise VintageAuditError(f"current_panel_duplicate_country_year:{entity}:{year}")
            values[year] = value
    if not output:
        raise VintageAuditError("current_panel_no_imf_gdp_growth_rows")
    return output


def theil_sen_pretrend_projection(values: Sequence[float]) -> float:
    """Project the 2016-2019 Theil-Sen trend one year forward to 2020."""
    if len(values) != 4:
        raise VintageAuditError("pretrend_requires_four_values_2016_to_2019")
    x = [0.0, 1.0, 2.0, 3.0]
    slopes = [
        (values[j] - values[i]) / (x[j] - x[i])
        for i in range(3)
        for j in range(i + 1, 4)
    ]
    slope = float(statistics.median(slopes))
    intercept = float(statistics.median([value - slope * point for value, point in zip(values, x)]))
    return intercept + slope * 4.0


def _summarize_vintage(
    vintage_id: str,
    source: Mapping[str, Mapping[str, Any]],
    current_panel: Mapping[str, Mapping[int, float]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    matched = set(source) & set(current_panel)
    for iso in sorted(matched):
        vintage = source[iso]
        values = vintage["values"]
        pre = [values[str(year)] for year in range(2016, 2020)]
        event = values["2020"]
        if event is None or any(value is None for value in pre):
            continue
        pre_values = [float(value) for value in pre if value is not None]
        forecast = theil_sen_pretrend_projection(pre_values)
        event_value = float(event)
        current_2020 = current_panel[iso].get(2020)
        rows.append({
            "iso": iso,
            "country_name_vintage": vintage["country_name"],
            "vintage_id": vintage_id,
            "2016": pre_values[0],
            "2017": pre_values[1],
            "2018": pre_values[2],
            "2019": pre_values[3],
            "2020": event_value,
            "pretrend_projection_2020": forecast,
            "deviation_from_pretrend_2020": event_value - forecast,
            "below_pretrend_projection": event_value < forecast,
            "below_2019_value": event_value < pre_values[-1],
            "current_apr2026_panel_2020": current_2020,
            "revision_vs_current_apr2026": (
                current_2020 - event_value if current_2020 is not None else None
            ),
            "estimates_start_after_raw": vintage["estimates_start_after_raw"],
            "country_series_notes": vintage["country_series_notes"],
        })

    if not rows:
        raise VintageAuditError(f"vintage_common_complete_rows_empty:{vintage_id}")
    below_trend = sum(row["below_pretrend_projection"] for row in rows)
    below_2019 = sum(row["below_2019_value"] for row in rows)
    revisions = [
        abs(float(row["revision_vs_current_apr2026"]))
        for row in rows if row["revision_vs_current_apr2026"] is not None
    ]
    signed_revisions = [
        float(row["revision_vs_current_apr2026"])
        for row in rows if row["revision_vs_current_apr2026"] is not None
    ]
    summary = {
        "vintage_id": vintage_id,
        "iso_matched_to_current_panel": len(matched),
        "rows_with_complete_2016_2020": len(rows),
        "below_pretrend_count": below_trend,
        "below_pretrend_fraction": below_trend / len(rows),
        "below_2019_count": below_2019,
        "below_2019_fraction": below_2019 / len(rows),
        "median_absolute_2020_revision_vs_current_apr2026": (
            float(statistics.median(revisions)) if revisions else None
        ),
        "median_signed_2020_revision_vs_current_apr2026": (
            float(statistics.median(signed_revisions)) if signed_revisions else None
        ),
        "pretrend_definition": "Theil-Sen line fit on 2016-2019 only, extrapolated one year to 2020; this is a source-vintage diagnostic, not the V1 symmetric point-anomaly detector.",
    }
    return summary, rows


def run_vintage_audit(
    *,
    panel_path: Path,
    raw_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    current_panel = _parse_current_panel(panel_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    sources: dict[str, dict[str, dict[str, Any]]] = {}
    downloads: list[dict[str, Any]] = []
    for vintage in VINTAGES:
        raw_path = raw_dir / f"{vintage['vintage_id']}_BY_COUNTRIES.xls"
        download_meta = download_official_vintage(vintage["download_url"], raw_path)
        download_meta.update({
            "vintage_id": vintage["vintage_id"],
            "release_label": vintage["release_label"],
            "release_page": vintage["release_page"],
        })
        downloads.append(download_meta)
        sources[vintage["vintage_id"]] = read_weo_country_file(raw_path)

    current_source: dict[str, dict[str, Any]] = {}
    for iso, values in current_panel.items():
        current_source[iso] = {
            "iso": iso,
            "country_name": iso,
            "values": {str(year): values.get(year) for year in range(2016, 2021)},
            "raw_values": {},
            "estimates_start_after_raw": "",
            "country_series_notes": "",
        }

    vintage_summaries: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    for vintage in VINTAGES:
        summary, rows = _summarize_vintage(
            vintage["vintage_id"], sources[vintage["vintage_id"]], current_panel
        )
        summary["release_label"] = vintage["release_label"]
        summary["release_page"] = vintage["release_page"]
        vintage_summaries.append(summary)
        all_rows.extend(rows)

    current_summary, current_rows = _summarize_vintage(
        "WEO_APR2026_CURRENT_PANEL", current_source, current_panel
    )
    current_summary["release_label"] = "April 2026 WEO current snapshot as staged in CHAOS"
    vintage_summaries.append(current_summary)
    all_rows.extend(current_rows)

    # Per-country revision trajectory across available vintages, without
    # imputing missing countries or silently equating estimates and actuals.
    comparison_rows: dict[str, dict[str, Any]] = {}
    for row in all_rows:
        iso = row["iso"]
        target = comparison_rows.setdefault(iso, {"iso": iso})
        prefix = row["vintage_id"].lower()
        for field in (
            "2016", "2017", "2018", "2019", "2020",
            "pretrend_projection_2020", "deviation_from_pretrend_2020",
            "below_pretrend_projection", "below_2019_value",
            "revision_vs_current_apr2026", "estimates_start_after_raw",
        ):
            target[f"{prefix}_{field}"] = row.get(field)

    revision_pairs: dict[str, dict[str, Any]] = {}
    for iso, item in comparison_rows.items():
        for vintage_id in ("WEO_2020_OCT", "WEO_2021_APR"):
            key = vintage_id.lower()
            value = item.get(f"{key}_2020")
            if value is not None:
                revision_pairs.setdefault(vintage_id, {})[iso] = float(value)

    summary = {
        "contract_id": CONTRACT_ID,
        "status": "SOURCE_VINTAGE_AUDIT_COMPLETED",
        "series": {
            "imf_subject_code": WE0_SUBJECT_CODE,
            "current_panel_column": "imf__NGDP_RPCH",
            "current_panel_release_id": "imf_weo_apr2026_current",
            "native_frequency": "annual",
            "event_year": 2020,
            "pretrend_years": [2016, 2017, 2018, 2019],
            "pretrend_method": "Theil-Sen extrapolation fitted only on 2016-2019",
        },
        "panel": {
            "path": panel_path.as_posix(),
            "sha256": sha256_file(panel_path),
            "entities_with_2016_to_2020": len(current_panel),
        },
        "downloads": downloads,
        "vintages": vintage_summaries,
        "comparison_entity_count": len(comparison_rows),
        "interpretation": [
            "This tests whether the sign and magnitude of the 2020 real-GDP-growth dip relative to a pre-2020 robust trend persist across official IMF WEO releases.",
            "It is not the same statistic as the V1 symmetric local-reference point anomaly because early vintages do not contain four future observations after 2020.",
            "The estimates_start_after and country/series notes are retained as source fields; the script does not infer actual-versus-estimate status from the column label.",
            "No point-in-time forecast is constructed and no p-value or causal claim is produced.",
        ],
        "causal_claims_permitted": False,
        "forecasting_performed": False,
        "point_in_time_eligibility": "Historical-vintage publication is identified by the official release file, but country/series availability and estimate status must be interpreted from the retained source fields.",
    }

    rows_path = output_dir / "WEO_GDP_GROWTH_2020_VINTAGE_COMPARISON_V1.csv"
    fieldnames = sorted({key for row in comparison_rows.values() for key in row})
    with rows_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comparison_rows[iso] for iso in sorted(comparison_rows))

    summary_path = output_dir / "WEO_GDP_GROWTH_2020_VINTAGE_AUDIT_V1.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "bundle_id": "CHAOS_WEO_GDP_GROWTH_VINTAGE_AUDIT_V1",
        "generated_at_utc": None,
        "contract_id": CONTRACT_ID,
        "panel_sha256": sha256_file(panel_path),
        "downloads": downloads,
        "derived_artifacts": [
            {
                "path": rows_path.resolve().relative_to(Path.cwd().resolve()).as_posix(),
                "sha256": sha256_file(rows_path),
                "bytes": rows_path.stat().st_size,
            },
            {
                "path": summary_path.resolve().relative_to(Path.cwd().resolve()).as_posix(),
                "sha256": sha256_file(summary_path),
                "bytes": summary_path.stat().st_size,
            },
        ],
        "raw_downloads_are_uploaded_as_workflow_artifacts_not_committed_to_git": True,
    }
    manifest_path = output_dir / "WEO_GDP_GROWTH_VINTAGE_MANIFEST_V1.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary["derived_artifacts"] = {
        "comparison_csv": rows_path.name,
        "comparison_csv_sha256": sha256_file(rows_path),
        "manifest": manifest_path.name,
        "manifest_sha256": sha256_file(manifest_path),
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
