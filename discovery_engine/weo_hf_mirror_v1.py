"""Read pinned WEO publication vintages from the documented EconDataverse mirror.

This is a secondary distribution of IMF WEO data, cleaned into long-form
Parquet by the imfweo project. It is a fallback only when the official IMF
host returns access errors. It does not preserve IMF's Estimates Start After
metadata, so actual/estimate status remains UNKNOWN for mirrored values.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


class WeoMirrorError(ValueError):
    """Raised when the secondary WEO vintage archive cannot be loaded safely."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_records_from_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    publication_year: int,
    publication_release: str,
    subject_code: str,
    years: Sequence[int],
) -> dict[str, dict[str, Any]]:
    """Turn a filtered mirror slice into country-keyed records without imputation."""
    result: dict[str, dict[str, Any]] = {}
    accepted_years = set(years)
    for row in rows:
        if str(row.get("series_id")) != subject_code:
            continue
        try:
            row_publication_year = int(row.get("publication_year"))
        except (TypeError, ValueError) as exc:
            raise WeoMirrorError("mirror_publication_year_invalid") from exc
        if row_publication_year != publication_year:
            continue
        if str(row.get("publication_release", "")).casefold() != publication_release.casefold():
            continue

        iso = str(row.get("entity_id", "")).strip().upper()
        # The mirror also contains aggregates; only exact ISO-3 country codes
        # participate in the cross-vintage panel match.
        if len(iso) != 3 or not iso.isalpha():
            continue
        try:
            year = int(row["year"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WeoMirrorError(f"mirror_year_invalid:{iso}") from exc
        if year not in accepted_years:
            continue

        raw_value = row.get("value")
        if raw_value is None:
            value = None
        else:
            try:
                value = float(raw_value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise WeoMirrorError(f"mirror_value_invalid:{iso}:{year}") from exc
            if not math.isfinite(value):
                raise WeoMirrorError(f"mirror_value_nonfinite:{iso}:{year}")

        item = result.setdefault(iso, {
            "iso": iso,
            "country_name": str(row.get("entity_name", iso)),
            "values": {},
            "raw_values": {},
            "estimates_start_after_raw": "",
            "latest_actual_year": None,
            "event_year_data_status": "UNKNOWN_MIRROR_METADATA_NOT_PRESERVED",
            "pretrend_all_actual": False,
            "country_series_notes": "",
        })
        key = str(year)
        if key in item["values"]:
            raise WeoMirrorError(f"mirror_duplicate_iso_year:{publication_year}:{publication_release}:{iso}:{year}")
        item["values"][key] = value
        item["raw_values"][key] = raw_value

    if not result:
        raise WeoMirrorError(
            f"mirror_publication_rows_missing:{publication_year}:{publication_release}:{subject_code}"
        )
    return result


def load_hf_mirror_vintages(
    *,
    repo_id: str,
    vintage_specs: Sequence[Mapping[str, Any]],
    subject_code: str,
    years: Sequence[int],
    raw_dir: Path,
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    """Download a pinned HF dataset revision and extract required WEO vintages."""
    try:
        from huggingface_hub import HfApi, hf_hub_download
        import pyarrow.dataset as ds
    except ImportError as exc:
        raise WeoMirrorError("mirror_dependencies_missing:huggingface_hub,pyarrow") from exc

    raw_dir.mkdir(parents=True, exist_ok=True)
    api = HfApi()
    try:
        info = api.dataset_info(repo_id, repo_type="dataset", files_metadata=True)
    except Exception as exc:
        raise WeoMirrorError(f"mirror_dataset_info_failed:{repo_id}:{exc}") from exc

    revision = getattr(info, "sha", None)
    if not revision:
        raise WeoMirrorError("mirror_revision_sha_missing")
    siblings = list(getattr(info, "siblings", []) or [])
    parquet_names = sorted(
        item.rfilename for item in siblings
        if getattr(item, "rfilename", "").lower().endswith(".parquet")
    )
    if not parquet_names:
        raise WeoMirrorError("mirror_parquet_files_missing")

    downloaded: list[dict[str, Any]] = []
    parquet_paths: list[str] = []
    for filename in parquet_names:
        try:
            local_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                repo_type="dataset",
                revision=revision,
                local_dir=str(raw_dir / "huggingface"),
            )
        except Exception as exc:
            raise WeoMirrorError(f"mirror_parquet_download_failed:{filename}:{exc}") from exc
        path = Path(local_path)
        parquet_paths.append(str(path))
        downloaded.append({
            "repository": f"https://huggingface.co/datasets/{repo_id}",
            "revision": revision,
            "filename": filename,
            "local_path": path.resolve().as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        })

    dataset = ds.dataset(parquet_paths, format="parquet")
    available = set(dataset.schema.names)
    required_columns = {
        "entity_name", "entity_id", "series_id", "year", "value",
        "publication_year", "publication_release",
    }
    if not required_columns.issubset(available):
        raise WeoMirrorError(
            "mirror_required_columns_missing:"
            + ",".join(sorted(required_columns - available))
        )

    years_set = set(int(year) for year in years)
    # Extract each release separately; keep the data table narrow and deterministic.
    output: dict[str, dict[str, dict[str, Any]]] = {}
    selected_rows: dict[str, int] = {}
    for spec in vintage_specs:
        vintage_id = str(spec["vintage_id"])
        pub_year = int(spec["publication_year"])
        pub_release = str(spec["publication_release"])
        filter_expression = (
            (ds.field("series_id") == subject_code)
            & ds.field("year").isin(sorted(years_set))
            & (ds.field("publication_year") == pub_year)
            & (ds.field("publication_release") == pub_release)
        )
        try:
            table = dataset.to_table(
                columns=[
                    "entity_name", "entity_id", "series_id", "year", "value",
                    "publication_year", "publication_release",
                ],
                filter=filter_expression,
            )
        except Exception as exc:
            raise WeoMirrorError(f"mirror_parquet_query_failed:{vintage_id}:{exc}") from exc
        rows = table.to_pylist()
        selected_rows[vintage_id] = len(rows)
        output[vintage_id] = source_records_from_rows(
            rows,
            publication_year=pub_year,
            publication_release=pub_release,
            subject_code=subject_code,
            years=years,
        )

    card_data = getattr(info, "cardData", None) or {}
    mirror_meta = {
        "source_type": "THIRD_PARTY_DERIVED_MIRROR",
        "repository": f"https://huggingface.co/datasets/{repo_id}",
        "repository_id": repo_id,
        "revision": revision,
        "created_at": str(getattr(info, "created_at", "")),
        "last_modified": str(getattr(info, "last_modified", "")),
        "license": card_data.get("license") if isinstance(card_data, dict) else None,
        "transformation_notice": (
            "Long-form Parquet converted from IMF WEO publications by the imfweo project; "
            "IMF Estimates Start After and original country/series notes are not present."
        ),
        "parquet_files": downloaded,
        "selected_row_count_by_vintage": selected_rows,
        "metadata_missing_for_actual_estimate_status": True,
    }
    return output, mirror_meta
