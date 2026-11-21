from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from chaos_governance_kernel.core import sha256_file, write_json  # noqa: E402

AGENT_DIR = ROOT / "campaigns" / "agents" / "trade_v1"
INPUT_CSV = AGENT_DIR / "WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv"
METADATA_CSV = AGENT_DIR / "WDI_TRADE_SELECTED_SERIES_METADATA.csv"
EXTRACT_SUMMARY = AGENT_DIR / "WDI_TRADE_EXTRACT_SUMMARY.json"
OUTPUT_JSONL = AGENT_DIR / "WDI_TRADE_DOMAIN_STATES_ANNUAL_V1.jsonl"
OUTPUT_SUMMARY = AGENT_DIR / "WDI_TRADE_DOMAIN_ADAPTER_RUN_V2.json"

REQUIRED_INPUT_COLUMNS = {
    "Country Name", "Country Code", "Indicator Name", "Indicator Code", "year", "value_raw"
}
OUTPUT_POLICY = {
    "native_frequency": "annual",
    "domain": "trade",
    "no_imputation": True,
    "no_normalization": True,
    "no_source_averaging": True,
    "raw_value_lexeme_preserved": True,
    "partner_network_inferred": False,
    "shock_or_recovery_inferred": False,
}


def load_series_metadata(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "Series Code" not in reader.fieldnames:
            raise ValueError("series_metadata_missing_series_code")
        result: dict[str, dict[str, str]] = {}
        for row in reader:
            code = (row.get("Series Code") or "").strip()
            if not code:
                continue
            if code in result:
                raise ValueError(f"duplicate_series_metadata:{code}")
            result[code] = {
                "indicator_name": (row.get("Indicator Name") or "").strip(),
                "unit_of_measure": (row.get("Unit of measure") or "").strip(),
            }
    if not result:
        raise ValueError("series_metadata_empty")
    return result


def canonical_record(row: dict[str, str], metadata: dict[str, str]) -> dict[str, Any]:
    country_name = row["Country Name"].strip()
    country_code = row["Country Code"].strip()
    indicator_name = row["Indicator Name"].strip()
    indicator_code = row["Indicator Code"].strip()
    year_text = row["year"].strip()
    raw_value = row["value_raw"]

    if not country_name or not country_code or not indicator_name or not indicator_code:
        raise ValueError("source_identity_field_empty")
    if indicator_code not in metadata:
        raise ValueError(f"indicator_missing_from_source_metadata:{indicator_code}")
    try:
        year = int(year_text)
    except ValueError as exc:
        raise ValueError(f"invalid_source_year:{year_text}") from exc
    if not 1900 <= year <= 2100:
        raise ValueError(f"source_year_out_of_range:{year}")
    if raw_value is None or not raw_value.strip():
        raise ValueError(f"observed_source_row_has_empty_value:{country_code}:{indicator_code}:{year}")
    try:
        numeric = Decimal(raw_value.strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"source_value_not_decimal:{country_code}:{indicator_code}:{year}") from exc
    if not numeric.is_finite():
        raise ValueError(f"source_value_not_finite:{country_code}:{indicator_code}:{year}")

    return {
        "pattern_id": f"WDI_TRADE_{indicator_code}_V1",
        "domain": "trade",
        "entity_id": country_code,
        "entity_name": country_name,
        "timestamp": year,
        "native_frequency": "annual",
        "state_label": "trade_indicator_observed",
        "state_probability": None,
        "source_observations": {
            "indicator_code": indicator_code,
            "indicator_name": indicator_name,
            "value_raw": raw_value,
            "unit_of_measure": metadata[indicator_code]["unit_of_measure"],
        },
        "lead_profile": {},
        "uncertainty": [
            "WDI annual country-level indicator; compilation and revision practices may vary by source country",
            "aggregate indicators do not contain bilateral partner or commodity-level trade flows",
        ],
        "failure_cases": [
            "missing source years are not filled or converted to zero",
            "no trade disruption, production shock or recovery is inferred from this observation alone",
        ],
        "edge_status": "not_testable",
        "evidence_refs": [
            "campaigns/agents/trade_v1/WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv",
            "campaigns/agents/trade_v1/WDI_TRADE_SELECTED_SERIES_METADATA.csv",
            "campaigns/agents/trade_v1/WDI_TRADE_EXTRACT_SUMMARY.json",
        ],
    }


def build_wdi_trade_domain_states(
    input_csv: Path,
    metadata_csv: Path,
    extract_summary_path: Path,
    output_jsonl: Path,
    output_summary: Path,
) -> dict[str, Any]:
    metadata = load_series_metadata(metadata_csv)
    extract_summary = json.loads(extract_summary_path.read_text(encoding="utf-8"))

    records: list[dict[str, Any]] = []
    identity_counts: Counter[tuple[str, str, int]] = Counter()
    entity_names: dict[str, str] = {}
    indicators: set[str] = set()
    years: set[int] = set()

    with input_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_INPUT_COLUMNS - fields)
        if missing:
            raise ValueError("input_columns_missing:" + ",".join(missing))
        for row_number, row in enumerate(reader, 2):
            try:
                record = canonical_record(row, metadata)
            except Exception as exc:
                raise ValueError(f"input_row_invalid:line={row_number}:{exc}") from exc

            key = (
                record["entity_id"],
                record["pattern_id"],
                record["timestamp"],
            )
            identity_counts[key] += 1
            if identity_counts[key] > 1:
                raise ValueError(
                    "duplicate_source_slot:"
                    + ":".join(str(part) for part in key)
                )
            entity_id = record["entity_id"]
            entity_name = record["entity_name"]
            previous_name = entity_names.get(entity_id)
            if previous_name is not None and previous_name != entity_name:
                raise ValueError(f"entity_name_conflict:{entity_id}:{previous_name}:{entity_name}")
            entity_names[entity_id] = entity_name
            indicators.add(record["source_observations"]["indicator_code"])
            years.add(record["timestamp"])
            records.append(record)

    expected_rows = extract_summary.get("observed_rows")
    if isinstance(expected_rows, int) and len(records) != expected_rows:
        raise ValueError(f"extract_row_count_mismatch:expected={expected_rows}:actual={len(records)}")

    records.sort(key=lambda item: (
        item["entity_id"], item["pattern_id"], item["timestamp"]
    ))
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(
                record, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False
            ) + "\n")

    input_hash = sha256_file(input_csv)
    metadata_hash = sha256_file(metadata_csv)
    output_hash = sha256_file(output_jsonl)
    summary = {
        "adapter_id": "WDI_TRADE_DOMAIN_STATE_ADAPTER_V2",
        "status": "ready_for_domain_state_integrity_and_transition_layer",
        "input": input_csv.relative_to(ROOT).as_posix(),
        "input_sha256": input_hash,
        "source_archive_sha256": extract_summary.get("external_raw_sha256"),
        "metadata": metadata_csv.relative_to(ROOT).as_posix(),
        "metadata_sha256": metadata_hash,
        "output": output_jsonl.relative_to(ROOT).as_posix(),
        "output_sha256": output_hash,
        "records": len(records),
        "entities": len(entity_names),
        "indicators": sorted(indicators),
        "years": [min(years), max(years)] if years else [],
        "native_frequency": "annual",
        "domain": "trade",
        "duplicate_source_slots": 0,
        "transformations": [],
        "policy": OUTPUT_POLICY,
        "causal_claims_permitted": False,
        "edge_evaluation_performed": False,
    }
    write_json(output_summary, summary)
    return summary


def main() -> int:
    summary = build_wdi_trade_domain_states(
        INPUT_CSV, METADATA_CSV, EXTRACT_SUMMARY, OUTPUT_JSONL, OUTPUT_SUMMARY
    )
    print(json.dumps({
        "status": summary["status"],
        "records": summary["records"],
        "entities": summary["entities"],
        "indicators": len(summary["indicators"]),
        "years": summary["years"],
        "output_sha256": summary["output_sha256"],
        "summary": OUTPUT_SUMMARY.relative_to(ROOT).as_posix(),
        "output": OUTPUT_JSONL.relative_to(ROOT).as_posix(),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
