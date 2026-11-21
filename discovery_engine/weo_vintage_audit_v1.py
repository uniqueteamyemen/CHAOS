"""Auditable cross-vintage review of the IMF WEO 2020 real-GDP-growth signal.

The official IMF tab-delimited country files are compared with the April-2026
WEO values staged in the CHAOS source panel. The IMF "Estimates Start After"
field is interpreted as the latest actual-data year (zero means the whole
series is estimated). Each raw vintage is kept as an artifact and hashed.

The Theil-Sen pretrend is a revision-sensitivity diagnostic, not a forecast
and not the V1 symmetric point-anomaly score.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

from chaos_governance_kernel.core import utc_now
from .weo_hf_mirror_v1 import WeoMirrorError, load_hf_mirror_vintages

CONTRACT_ID = "CHAOS_WEO_GDP_GROWTH_VINTAGE_AUDIT_V1"
SUPPORTED_YEARS = [2016, 2017, 2018, 2019, 2020]
PANEL_REQUIRED_FIELDS = {"entity_code", "imf_entity_name", "year"}


class VintageAuditError(ValueError):
    """Raised when official vintage data cannot be parsed safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def download_official_vintage(url_candidates: Sequence[str], path: Path) -> dict[str, Any]:
    """Try only explicit IMF-hosted URLs and retain every attempt in the manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    attempts: list[dict[str, Any]] = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/tab-separated-values,text/plain,application/vnd.ms-excel,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.imf.org/",
    }
    for url in url_candidates:
        if not isinstance(url, str) or not url.startswith("https://www.imf.org/"):
            raise VintageAuditError(f"non_imf_vintage_url_rejected:{url}")
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                status = int(response.status)
                content_type = response.headers.get("Content-Type", "")
                data = response.read()
            attempts.append({
                "url": url,
                "http_status": status,
                "content_type": content_type,
                "bytes": len(data),
            })
        except urllib.error.HTTPError as exc:
            attempts.append({
                "url": url,
                "http_status": int(exc.code),
                "error": str(exc.reason),
            })
            continue
        except Exception as exc:
            attempts.append({
                "url": url,
                "error": f"{type(exc).__name__}:{exc}",
            })
            continue

        if status != 200:
            continue
        if len(data) < 100_000:
            attempts[-1]["rejected"] = "payload_too_small"
            continue
        if data.lstrip().startswith((b"<!DOCTYPE html", b"<html", b"<?xml")):
            attempts[-1]["rejected"] = "markup_not_data"
            continue
        # The WEO legacy .xls files are tab-delimited text, not binary BIFF workbooks.
        if b"\t" not in data[:8192] or b"WEO Subject Code" not in data[:65536]:
            attempts[-1]["rejected"] = "payload_not_recognized_as_weo_tab_delimited"
            continue

        path.write_bytes(data)
        return {
            "selected_url": url,
            "http_status": status,
            "content_type": content_type,
            "bytes": len(data),
            "sha256": sha256_file(path),
            "local_raw_file": path.name,
            "retrieved_at_utc": utc_now(),
            "attempts": attempts,
        }

    raise VintageAuditError(
        "official_imf_vintage_download_failed_all_urls:"
        + json.dumps(attempts, ensure_ascii=False, sort_keys=True)
    )


def parse_latest_actual_year(raw: Any) -> int | None:
    """IMF field: year of latest actual data; zero means the series is all estimates."""
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise VintageAuditError(f"estimates_start_after_invalid:{value}") from exc
    if parsed == 0:
        return 0
    if not 1900 <= parsed <= 2100:
        raise VintageAuditError(f"estimates_start_after_out_of_range:{value}")
    return parsed


def event_year_status(event_year: int, latest_actual_year: int | None) -> str:
    if latest_actual_year is None:
        return "UNKNOWN"
    return "ACTUAL" if event_year <= latest_actual_year else "ESTIMATE_OR_PROJECTION"


def read_weo_country_file(
    path: Path,
    *,
    subject_code: str,
    years: Sequence[int],
) -> dict[str, dict[str, Any]]:
    """Read a legacy IMF WEO By-Countries tab-delimited file."""
    data = path.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise VintageAuditError(f"weo_text_decode_failed:{path.name}")

    lines = text.splitlines()
    header_index = None
    required_normalized = {
        "iso", "weo subject code", "country", "estimates start after",
        *[str(year).casefold() for year in years],
    }
    for index, line in enumerate(lines[:50]):
        normalized = {
            part.strip().strip('"').lstrip("\ufeff").casefold()
            for part in line.split("\t")
        }
        if required_normalized.issubset(normalized):
            header_index = index
            break
    if header_index is None:
        preview = "\n".join(lines[:12])[:2000]
        raise VintageAuditError(f"weo_tsv_header_not_found:{path.name}:{preview}")

    reader = csv.DictReader(lines[header_index:], delimiter="\t")
    if not reader.fieldnames:
        raise VintageAuditError(f"weo_tsv_fieldnames_missing:{path.name}")
    headers = [str(item or "").strip().strip('"').lstrip("\ufeff") for item in reader.fieldnames]
    if len(set(headers)) != len(headers):
        raise VintageAuditError(f"weo_tsv_duplicate_headers:{path.name}")
    required = {"ISO", "WEO Subject Code", "Country", "Estimates Start After"}
    required.update(str(year) for year in years)
    missing = sorted(required - set(headers))
    if missing:
        raise VintageAuditError(f"weo_tsv_required_columns_missing:{path.name}:{missing}")

    output: dict[str, dict[str, Any]] = {}
    for row_number, raw in enumerate(reader, header_index + 2):
        row = {
            str(key).strip().strip('"').lstrip("\ufeff"): (value or "").strip().strip('"')
            for key, value in raw.items()
            if key is not None
        }
        if row.get("WEO Subject Code") != subject_code:
            continue
        iso = row.get("ISO", "").strip().upper()
        if len(iso) != 3 or not iso.isalpha():
            # Country-group aggregates and non-country rows are not matched to countries.
            continue
        if iso in output:
            raise VintageAuditError(
                f"duplicate_weo_iso_subject_row:{path.name}:{iso}:{row_number}"
            )

        values: dict[str, float | None] = {}
        raw_values: dict[str, str] = {}
        for year in years:
            key = str(year)
            raw_value = row.get(key, "").strip()
            raw_values[key] = raw_value
            if not raw_value or raw_value.casefold() in {
                "n/a", "na", "--", "...", "no data", "not available"
            }:
                values[key] = None
                continue
            try:
                parsed = Decimal(raw_value.replace(",", ""))
            except InvalidOperation as exc:
                raise VintageAuditError(
                    f"weo_numeric_invalid:{path.name}:{iso}:{key}:{raw_value}"
                ) from exc
            if not parsed.is_finite():
                raise VintageAuditError(f"weo_numeric_nonfinite:{path.name}:{iso}:{key}")
            value = float(parsed)
            if not math.isfinite(value):
                raise VintageAuditError(f"weo_numeric_overflow:{path.name}:{iso}:{key}")
            values[key] = value

        latest_raw = row.get("Estimates Start After", "")
        latest_actual = parse_latest_actual_year(latest_raw)
        output[iso] = {
            "iso": iso,
            "country_name": row.get("Country", ""),
            "values": values,
            "raw_values": raw_values,
            "estimates_start_after_raw": latest_raw,
            "latest_actual_year": latest_actual,
            "event_year_data_status": event_year_status(int(years[-1]), latest_actual),
            "pretrend_all_actual": (
                latest_actual is not None and latest_actual >= int(years[-2])
            ),
            "country_series_notes": row.get("Country/Series-specific Notes", ""),
        }

    if not output:
        raise VintageAuditError(f"weo_subject_rows_not_found:{path.name}:{subject_code}")
    return output


def _parse_current_panel(
    path: Path,
    years: Sequence[int],
    value_column: str,
) -> dict[str, dict[int, float]]:
    output: dict[str, dict[int, float]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = PANEL_REQUIRED_FIELDS | {value_column}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise VintageAuditError(
                "current_panel_columns_missing:"
                + str(sorted(required - set(reader.fieldnames or [])))
            )
        accepted_years = set(years)
        for row_number, row in enumerate(reader, 2):
            iso = (row.get("entity_code") or "").strip().upper()
            if len(iso) != 3 or not iso.isalpha():
                raise VintageAuditError(f"current_panel_iso_invalid:{row_number}:{iso}")
            try:
                year = int(row.get("year") or "")
            except ValueError as exc:
                raise VintageAuditError(f"current_panel_year_invalid:{row_number}") from exc
            if year not in accepted_years:
                continue
            raw = (row.get(value_column) or "").strip()
            if not raw:
                continue
            try:
                value = float(Decimal(raw))
            except (InvalidOperation, ValueError) as exc:
                raise VintageAuditError(
                    f"current_panel_value_invalid:{iso}:{year}:{raw}"
                ) from exc
            if not math.isfinite(value):
                raise VintageAuditError(f"current_panel_value_nonfinite:{iso}:{year}")
            values = output.setdefault(iso, {})
            if year in values:
                raise VintageAuditError(f"current_panel_duplicate_iso_year:{iso}:{year}")
            values[year] = value
    if not output:
        raise VintageAuditError("current_panel_has_no_matching_values")
    return output


def theil_sen_pretrend_reference(values: Sequence[float]) -> float:
    """Fit on 2016–2019 only and extrapolate one year to 2020."""
    if len(values) != 4:
        raise VintageAuditError("pretrend_requires_four_values")
    x = [0.0, 1.0, 2.0, 3.0]
    slopes = [
        (values[j] - values[i]) / (x[j] - x[i])
        for i in range(3)
        for j in range(i + 1, 4)
    ]
    slope = float(statistics.median(slopes))
    intercept = float(
        statistics.median([value - slope * point for value, point in zip(values, x)])
    )
    return intercept + slope * 4.0


def _summarize_vintage(
    vintage_id: str,
    source: Mapping[str, Mapping[str, Any]],
    panel: Mapping[str, Mapping[int, float]],
    years: Sequence[int],
    *,
    current_panel: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    matched = set(source) & set(panel)
    event_year = int(years[-1])
    for iso in sorted(matched):
        vintage = source[iso]
        values = vintage["values"]
        pre = [values.get(str(year)) for year in years[:-1]]
        event_value = values.get(str(event_year))
        if event_value is None or any(value is None for value in pre):
            continue
        pre_values = [float(value) for value in pre if value is not None]
        reference = theil_sen_pretrend_reference(pre_values)
        event_value = float(event_value)
        current_value = panel[iso].get(event_year)
        status = (
            "UNKNOWN_CURRENT_STAGED_PANEL"
            if current_panel
            else str(vintage["event_year_data_status"])
        )
        latest_actual = None if current_panel else vintage["latest_actual_year"]
        rows.append({
            "iso": iso,
            "country_name_vintage": vintage["country_name"],
            "vintage_id": vintage_id,
            **{str(year): value for year, value in zip(years[:-1], pre_values)},
            str(event_year): event_value,
            "pretrend_reference_2020": reference,
            "deviation_from_pretrend_2020": event_value - reference,
            "below_pretrend_reference": event_value < reference,
            "below_2019_value": event_value < pre_values[-1],
            "latest_actual_year": latest_actual,
            "estimates_start_after_raw": (
                "" if current_panel else vintage["estimates_start_after_raw"]
            ),
            "event_2020_data_status": status,
            "pretrend_all_actual": (
                False if current_panel else bool(vintage["pretrend_all_actual"])
            ),
            "current_panel_2020": current_value,
            "revision_vs_current_panel_2020": (
                current_value - event_value if current_value is not None else None
            ),
            "country_series_notes": (
                "" if current_panel else vintage["country_series_notes"]
            ),
        })

    if not rows:
        raise VintageAuditError(f"no_complete_common_iso_rows:{vintage_id}")

    actual = [row for row in rows if row["event_2020_data_status"] == "ACTUAL"]
    estimated = [
        row for row in rows
        if row["event_2020_data_status"] == "ESTIMATE_OR_PROJECTION"
    ]
    unknown = [
        row for row in rows
        if str(row["event_2020_data_status"]).startswith("UNKNOWN")
    ]
    actual_pretrend = [row for row in rows if row["pretrend_all_actual"]]

    def _fraction(group: Sequence[Mapping[str, Any]]) -> float | None:
        return (
            sum(bool(row["below_pretrend_reference"]) for row in group) / len(group)
            if group else None
        )

    revisions = [
        abs(float(row["revision_vs_current_panel_2020"]))
        for row in rows if row["revision_vs_current_panel_2020"] is not None
    ]
    summary = {
        "vintage_id": vintage_id,
        "iso_matched_to_panel": len(matched),
        "complete_2016_2020_rows": len(rows),
        "event_2020_status": {
            "actual": len(actual),
            "estimate_or_projection": len(estimated),
            "unknown": len(unknown),
        },
        "below_pretrend_fraction_all_complete": _fraction(rows),
        "below_pretrend_fraction_actual_2020": _fraction(actual),
        "below_pretrend_fraction_estimated_2020": _fraction(estimated),
        "all_actual_pretrend_rows": len(actual_pretrend),
        "below_pretrend_fraction_all_actual_pretrend": _fraction(actual_pretrend),
        "below_2019_fraction_all_complete": (
            sum(bool(row["below_2019_value"]) for row in rows) / len(rows)
        ),
        "median_absolute_2020_revision_vs_staged_panel": (
            float(statistics.median(revisions)) if revisions else None
        ),
        "pretrend_definition": (
            "Theil-Sen fitted on 2016–2019 only and extrapolated one year; "
            "2020 actual/estimate status comes from IMF Estimates Start After."
        ),
    }
    return summary, rows


def run_vintage_audit(
    *,
    panel_path: Path,
    contract_path: Path,
    raw_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("contract_id") != CONTRACT_ID:
        raise VintageAuditError("vintage_audit_contract_id_mismatch")
    years = contract.get("years")
    if years != SUPPORTED_YEARS or contract.get("event_year") != 2020:
        raise VintageAuditError("vintage_audit_year_contract_invalid")
    if contract.get("pretrend_years") != years[:-1]:
        raise VintageAuditError("vintage_audit_pretrend_years_invalid")
    subject_code = contract.get("subject_code")
    if not isinstance(subject_code, str) or not subject_code:
        raise VintageAuditError("subject_code_missing")

    vintages = contract.get("vintages")
    if not isinstance(vintages, list) or len(vintages) < 3:
        raise VintageAuditError("vintage_contract_requires_two_historical_and_one_panel_release")
    current_items = [
        item for item in vintages
        if item.get("vintage_id") == "WEO_APR2026_PANEL_STAGED"
    ]
    historical = [
        item for item in vintages
        if item.get("vintage_id") != "WEO_APR2026_PANEL_STAGED"
    ]
    if len(current_items) != 1 or len(historical) < 2:
        raise VintageAuditError("vintage_registry_invalid")
    current_item = current_items[0]
    panel_column = current_item.get("panel_column")
    if not isinstance(panel_column, str) or not panel_column:
        raise VintageAuditError("current_panel_column_missing")

    panel = _parse_current_panel(panel_path, years, panel_column)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    source_by_vintage: dict[str, dict[str, dict[str, Any]]] = {}
    download_manifest: list[dict[str, Any]] = []
    vintage_summaries: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []

    official_access_failures: list[dict[str, Any]] = []
    for item in historical:
        vintage_id = item.get("vintage_id")
        urls = item.get("download_url_candidates")
        if not isinstance(vintage_id, str) or not vintage_id:
            raise VintageAuditError("historical_vintage_id_invalid")
        if not isinstance(urls, list) or not urls:
            raise VintageAuditError(f"download_url_candidates_missing:{vintage_id}")

        raw_path = raw_dir / f"{vintage_id}_BY_COUNTRIES.xls"
        try:
            download = download_official_vintage(urls, raw_path)
        except VintageAuditError as exc:
            message = str(exc)
            if not message.startswith("official_imf_vintage_download_failed_all_urls:"):
                raise
            official_access_failures.append({
                "vintage_id": vintage_id,
                "release_label": item.get("release_label"),
                "release_page": item.get("release_page"),
                "publication_year": item.get("publication_year"),
                "publication_release": item.get("publication_release"),
                "official_download_failure": message,
            })
            continue

        download.update({
            "vintage_id": vintage_id,
            "release_label": item.get("release_label"),
            "release_page": item.get("release_page"),
            "source_type": "OFFICIAL_IMF_DIRECT",
        })
        download_manifest.append(download)
        source_by_vintage[vintage_id] = read_weo_country_file(
            raw_path, subject_code=subject_code, years=years
        )

    mirror_meta: dict[str, Any] | None = None
    if official_access_failures:
        mirror_contract = contract.get("mirror")
        if not isinstance(mirror_contract, dict):
            raise VintageAuditError(
                "official_imf_access_failed_and_no_secondary_mirror_contract"
            )
        if mirror_contract.get("fallback_policy") != "USE_ONLY_AFTER_OFFICIAL_IMF_DOWNLOAD_ACCESS_FAILURE":
            raise VintageAuditError("secondary_mirror_fallback_policy_not_explicit")
        mirror_specs = []
        for failed in official_access_failures:
            if failed["publication_year"] is None or not failed["publication_release"]:
                raise VintageAuditError(
                    f"mirror_publication_metadata_missing:{failed['vintage_id']}"
                )
            mirror_specs.append({
                "vintage_id": failed["vintage_id"],
                "publication_year": failed["publication_year"],
                "publication_release": failed["publication_release"],
            })
        try:
            mirror_sources, mirror_meta = load_hf_mirror_vintages(
                repo_id=mirror_contract["repository_id"],
                vintage_specs=mirror_specs,
                subject_code=subject_code,
                years=years,
                raw_dir=raw_dir / "huggingface",
            )
        except WeoMirrorError as exc:
            raise VintageAuditError(
                "official_imf_access_failed_and_secondary_mirror_failed:"
                + str(exc)
            ) from exc

        for failed in official_access_failures:
            vintage_id = failed["vintage_id"]
            source_by_vintage[vintage_id] = mirror_sources[vintage_id]
            download_manifest.append({
                **failed,
                "source_type": "THIRD_PARTY_DERIVED_MIRROR",
                "mirror_source": mirror_meta,
                "actual_estimate_status": "UNKNOWN_MIRROR_METADATA_NOT_PRESERVED",
            })

    for item in historical:
        vintage_id = item["vintage_id"]
        summary, rows = _summarize_vintage(
            vintage_id, source_by_vintage[vintage_id], panel, years
        )
        summary["release_label"] = item.get("release_label")
        summary["release_page"] = item.get("release_page")
        acquisition = next(
            entry for entry in download_manifest
            if entry["vintage_id"] == vintage_id
        )
        summary["source_type"] = acquisition["source_type"]
        if acquisition["source_type"] == "THIRD_PARTY_DERIVED_MIRROR":
            summary["actual_estimate_status"] = (
                "UNKNOWN_MIRROR_METADATA_NOT_PRESERVED"
            )
        vintage_summaries.append(summary)
        all_rows.extend(rows)

    staged_source: dict[str, dict[str, Any]] = {
        iso: {
            "iso": iso,
            "country_name": iso,
            "values": {str(year): values.get(year) for year in years},
            "latest_actual_year": None,
            "event_year_data_status": "UNKNOWN",
            "pretrend_all_actual": False,
            "estimates_start_after_raw": "",
            "country_series_notes": "",
        }
        for iso, values in panel.items()
    }
    staged_id = current_item["vintage_id"]
    staged_summary, staged_rows = _summarize_vintage(
        staged_id, staged_source, panel, years, current_panel=True
    )
    staged_summary["release_label"] = current_item.get("release_label")
    vintage_summaries.append(staged_summary)
    all_rows.extend(staged_rows)

    comparison: dict[str, dict[str, Any]] = {}
    for row in all_rows:
        target = comparison.setdefault(row["iso"], {"iso": row["iso"]})
        prefix = row["vintage_id"].lower()
        for field in (
            *[str(year) for year in years],
            "pretrend_reference_2020",
            "deviation_from_pretrend_2020",
            "below_pretrend_reference",
            "below_2019_value",
            "latest_actual_year",
            "estimates_start_after_raw",
            "event_2020_data_status",
            "pretrend_all_actual",
            "revision_vs_current_panel_2020",
        ):
            target[f"{prefix}_{field}"] = row.get(field)

    rows_path = output_dir / "WEO_GDP_GROWTH_2020_VINTAGE_COMPARISON_V1.csv"
    fieldnames = sorted({key for row in comparison.values() for key in row})
    with rows_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comparison[iso] for iso in sorted(comparison))

    module_path = Path(__file__).resolve()
    runner_path = Path.cwd() / "scripts" / "discovery" / "run_weo_vintage_audit_v1.py"
    panel_sha = sha256_file(panel_path)
    contract_sha = sha256_file(contract_path)
    summary = {
        "contract_id": CONTRACT_ID,
        "status": (
            "SOURCE_VINTAGE_AUDIT_COMPLETED_WITH_SECONDARY_MIRROR"
            if mirror_meta is not None
            else "SOURCE_VINTAGE_AUDIT_COMPLETED_FROM_OFFICIAL_IMF_FILES"
        ),
        "generated_at_utc": utc_now(),
        "contract_sha256": contract_sha,
        "code_sha256": sha256_file(module_path),
        "panel": {
            "path": panel_path.as_posix(),
            "sha256": panel_sha,
            "entities_with_any_panel_values": len(panel),
        },
        "series": {
            "subject_code": subject_code,
            "panel_column": panel_column,
            "event_year": 2020,
            "pretrend_years": list(years[:-1]),
            "method": "Theil-Sen on 2016–2019 only, extrapolated to 2020",
        },
        "downloads": download_manifest,
        "secondary_mirror": mirror_meta,
        "official_imf_access_failures": official_access_failures,
        "vintages": vintage_summaries,
        "comparison_iso_count": len(comparison),
        "limits": [
            "Only ISO-3 exact matching is used; no fuzzy country-name matching.",
            "The staged April-2026 panel has no source-vintage actual/estimate metadata; its event status is UNKNOWN.",
            "Official IMF files use Estimates Start After for actual/estimate classification; secondary mirror values remain UNKNOWN because this metadata is not preserved in the mirror.",
            "A third-party mirror is never reported as an official IMF source file."
            "Theil-Sen extrapolation is a source-vintage revision diagnostic, not a prediction or a p-value.",
            "No causal claim or forecasting is performed.",
        ],
        "causal_claims_permitted": False,
        "forecasting_performed": False,
    }
    summary_path = output_dir / "WEO_GDP_GROWTH_2020_VINTAGE_AUDIT_V1.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "bundle_id": "CHAOS_WEO_GDP_GROWTH_VINTAGE_AUDIT_V1",
        "contract_id": CONTRACT_ID,
        "generated_at_utc": utc_now(),
        "contract_sha256": contract_sha,
        "panel_sha256": panel_sha,
        "code": {
            "module_path": module_path.relative_to(Path.cwd().resolve()).as_posix(),
            "module_sha256": sha256_file(module_path),
            "runner_path": runner_path.resolve().relative_to(Path.cwd().resolve()).as_posix(),
            "runner_sha256": sha256_file(runner_path),
        },
        "raw_downloads_and_source_acquisitions": download_manifest,
        "secondary_mirror": mirror_meta,
        "official_imf_access_failures": official_access_failures,
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
        "raw_files_uploaded_as_workflow_artifacts_only": True,
    }
    manifest_path = output_dir / "WEO_GDP_GROWTH_VINTAGE_MANIFEST_V1.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
