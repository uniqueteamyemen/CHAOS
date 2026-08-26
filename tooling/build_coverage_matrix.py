from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "campaign" / "raw"
OUT_DIR = ROOT / "campaign" / "derived"
OUT_DIR.mkdir(parents=True, exist_ok=True)
runs = sorted(path for path in RAW_ROOT.iterdir() if path.is_dir())
rows: list[dict[str, str]] = []


def add(**kwargs: object) -> None:
    rows.append({key: "" if value is None else str(value) for key, value in kwargs.items()})


for run in runs:
    imf_path = run / "imf.json"
    if imf_path.exists():
        data = json.loads(imf_path.read_text(encoding="utf-8"))
        values = data.get("values", {})
        indicator_values = values.get("NGDP_RPCH", {}) if isinstance(values, dict) else {}
        years: set[str] = set()
        country_count = 0
        if isinstance(indicator_values, dict):
            for country_values in indicator_values.values():
                country_count += 1
                if isinstance(country_values, dict):
                    years.update(str(year) for year in country_values if str(year) <= "2025")
        add(
            variable_unique_identifier="imf.datamapper.NGDP_RPCH",
            source="IMF DataMapper",
            stream_type="continuous_index",
            temporal_start_date=min(years) if years else "",
            temporal_end_date=max(years) if years else "",
            native_frequency="annual",
            missing_gaps_intervals="not_inferred_from_payload",
            source_definition_shifts="not_inferred; preserve IMF metadata and release",
            retrieval_provenance_hash=f"raw_run:{run.name}",
            coverage_status="observed_payload",
            source_record_count=country_count,
            notes="Real GDP growth indicator; historical years capped at 2025; forecasts retained only in raw",
        )

    usgs_path = run / "usgs.json"
    if usgs_path.exists():
        data = json.loads(usgs_path.read_text(encoding="utf-8"))
        for item in data.get("value", {}).get("timeSeries", []):
            source = item.get("sourceInfo", {})
            variable = item.get("variable", {})
            observations = []
            for block in item.get("values", []):
                observations.extend(block.get("value", []))
            dates = [observation.get("dateTime", "") for observation in observations if observation.get("dateTime")]
            codes = variable.get("variableCode", [{}])
            code = codes[0].get("value", "unknown") if codes else "unknown"
            site_codes = source.get("siteCode", [])
            site_code = site_codes[0].get("value", "unknown") if site_codes and isinstance(site_codes[0], dict) else "unknown"
            add(
                variable_unique_identifier=f"usgs.nwis.{site_code}.{code}",
                source="USGS NWIS",
                stream_type="continuous_index",
                temporal_start_date=min(dates) if dates else "",
                temporal_end_date=max(dates) if dates else "",
                native_frequency="daily_values",
                missing_gaps_intervals="not_inferred_from_payload",
                source_definition_shifts="preserve USGS variable and statistic metadata",
                retrieval_provenance_hash=f"raw_run:{run.name}",
                coverage_status="observed_payload",
                source_record_count=len(observations),
                notes=variable.get("variableDescription", ""),
            )

    if (run / "gdelt.txt").exists():
        add(
            variable_unique_identifier="gdelt.gdeltv2.lastupdate",
            source="GDELT",
            stream_type="metadata_probe",
            temporal_start_date="",
            temporal_end_date="",
            native_frequency="near_real_time",
            missing_gaps_intervals="not_applicable_metadata_only",
            source_definition_shifts="not_applicable",
            retrieval_provenance_hash=f"raw_run:{run.name}",
            coverage_status="metadata_only",
            source_record_count="1",
            notes="lastupdate manifest captured; event bulk extraction not performed in this run",
        )

    if (run / "eia.json").exists():
        add(
            variable_unique_identifier="eia.api.root",
            source="EIA",
            stream_type="metadata_probe",
            temporal_start_date="",
            temporal_end_date="",
            native_frequency="dataset_dependent",
            missing_gaps_intervals="not_applicable_metadata_only",
            source_definition_shifts="not_applicable",
            retrieval_provenance_hash=f"raw_run:{run.name}",
            coverage_status="metadata_only",
            source_record_count="1",
            notes="API root metadata captured; scoped series extraction requires route and key policy",
        )

    if (run / "fred.csv").exists():
        add(
            variable_unique_identifier="fred.md.request",
            source="FRED",
            stream_type="access_probe",
            temporal_start_date="",
            temporal_end_date="",
            native_frequency="unknown",
            missing_gaps_intervals="not_observable_from_error_or_probe_response",
            source_definition_shifts="not_observable",
            retrieval_provenance_hash=f"raw_run:{run.name}",
            coverage_status="access_exception_or_probe",
            source_record_count="0",
            notes="Response retained; no observations inferred",
        )

    for wb_path in sorted(run.glob("worldbank*.json")):
        data = json.loads(wb_path.read_text(encoding="utf-8"))
        observations = data[1] if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list) else []
        dates = [str(item.get("date", "")) for item in observations if item.get("date")]
        add(
            variable_unique_identifier=f"worldbank.wdi.WLD.{wb_path.stem.removeprefix('worldbank_WLD_')}",
            source="World Bank WDI",
            stream_type="continuous_index",
            temporal_start_date=min(dates) if dates else "",
            temporal_end_date=max(dates) if dates else "",
            native_frequency="annual",
            missing_gaps_intervals="not_inferred_from_payload",
            source_definition_shifts="preserve indicator metadata and source version",
            retrieval_provenance_hash=f"raw_run:{run.name}",
            coverage_status="observed_payload" if observations else "no_observation_payload",
            source_record_count=len(observations),
            notes="World Bank raw JSON retained; variable label derived from capture filename; no observation payload is not imputed",
        )

    comtrade_path = run / "un_comtrade_2022_au_imports.json"
    if comtrade_path.exists():
        data = json.loads(comtrade_path.read_text(encoding="utf-8"))
        add(
            variable_unique_identifier="uncomtrade.preview.AU.2022.TOTAL.imports",
            source="UN Comtrade",
            stream_type="trade_flow",
            temporal_start_date="2022",
            temporal_end_date="2022",
            native_frequency="annual",
            missing_gaps_intervals="not_applicable_single_period_probe",
            source_definition_shifts="classification and flow fields retained in raw payload",
            retrieval_provenance_hash=f"raw_run:{run.name}",
            coverage_status="observed_payload",
            source_record_count=len(data.get("data", [])) if isinstance(data, dict) else 0,
            notes="Bounded public preview probe; not a 25-year bulk extract",
        )

fields = [
    "variable_unique_identifier", "source", "stream_type", "temporal_start_date",
    "temporal_end_date", "native_frequency", "missing_gaps_intervals",
    "source_definition_shifts", "retrieval_provenance_hash", "coverage_status",
    "source_record_count", "notes",
]
out_path = OUT_DIR / "variable_coverage_matrix.csv"
with out_path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

report_path = OUT_DIR / "coverage_build_report.json"
report_path.write_text(
    json.dumps(
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "raw_runs": [str(run) for run in runs],
            "rows": len(rows),
            "policy": {
                "raw_immutable": True,
                "imputation_performed": False,
                "source_reconciliation_performed": False,
            },
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(out_path)
print(report_path)
print(f"rows={len(rows)}")
