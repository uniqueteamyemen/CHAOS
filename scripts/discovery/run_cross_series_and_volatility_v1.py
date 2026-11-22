from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from chaos_governance_kernel.core import sha256_file, utc_now, write_json
from discovery_engine.cross_series_relationship_discovery_v1 import (
    discover_cross_series_relationships,
    jsonl_bytes,
    load_active_annual_series,
    scan_variance_shifts,
)

INPUTS = {
    "macro_panel": ROOT / "catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv",
    "macro_summary": ROOT / "catalog_first/readiness_gate/macro_plus_eia_energy/NUMERIC_COMPLETE_MATRIX_V1_1_SUMMARY.json",
    "macro_provenance": ROOT / "catalog_first/readiness_gate/macro_plus_eia_energy/SELECTED_VARIABLE_PROVENANCE.csv",
    "macro_manifest": ROOT / "discovery/behavioral_v1/BEHAVIORAL_DISCOVERY_MANIFEST_V1.json",
    "trade_csv": ROOT / "campaigns/agents/trade_v1/WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv",
    "trade_summary": ROOT / "campaigns/agents/trade_v1/WDI_TRADE_EXTRACT_SUMMARY.json",
    "trade_adapter": ROOT / "campaigns/agents/trade_v1/WDI_TRADE_DOMAIN_ADAPTER_RUN_V2.json",
    "trade_metadata": ROOT / "campaigns/agents/trade_v1/WDI_TRADE_SELECTED_SERIES_METADATA.csv",
}
REL_CONTRACT = ROOT / "experimental_contracts/CROSS_SERIES_RELATIONSHIP_DISCOVERY_CONTRACT_V1.json"
VOL_CONTRACT = ROOT / "experimental_contracts/VARIANCE_VOLATILITY_SHIFT_CONTRACT_V1.json"
REL_OUT = ROOT / "discovery/cross_series_v1"
VOL_OUT = ROOT / "discovery/volatility_v1"


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jsonl_bytes(rows))


def artifact_entry(path: Path, role: str) -> dict:
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "role": role,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def main() -> dict:
    rel_contract = json.loads(REL_CONTRACT.read_text(encoding="utf-8"))
    vol_contract = json.loads(VOL_CONTRACT.read_text(encoding="utf-8"))
    if rel_contract.get("contract_id") != "CHAOS_CROSS_SERIES_RELATIONSHIP_DISCOVERY_V1":
        raise ValueError("relationship_contract_id_mismatch")
    if vol_contract.get("contract_id") != "CHAOS_VARIANCE_VOLATILITY_SHIFT_V1":
        raise ValueError("volatility_contract_id_mismatch")
    if rel_contract.get("status") != "candidate_generation_only" or vol_contract.get("status") != "candidate_generation_only":
        raise ValueError("contracts_must_remain_candidate_generation_only")

    series, metric_meta, source_report = load_active_annual_series(
        macro_panel_path=INPUTS["macro_panel"],
        macro_summary_path=INPUTS["macro_summary"],
        macro_provenance_path=INPUTS["macro_provenance"],
        macro_manifest_path=INPUTS["macro_manifest"],
        trade_csv_path=INPUTS["trade_csv"],
        trade_extract_summary_path=INPUTS["trade_summary"],
        trade_adapter_run_path=INPUTS["trade_adapter"],
        trade_metadata_path=INPUTS["trade_metadata"],
    )

    rc = rel_contract["discovery"]
    rel_rows = discover_cross_series_relationships(
        series,
        metric_metadata=metric_meta,
        minimum_entities=int(rc["minimum_entities"]),
        minimum_pairs_per_entity=int(rc["minimum_pairs_per_entity"]),
        minimum_median_abs_correlation=float(rc["minimum_median_abs_correlation"]),
        minimum_direction_concordance=float(rc["minimum_direction_concordance"]),
        maximum_lag_years=int(rc["maximum_lag_years"]),
        early_window=tuple(rc["early_window"]),
        late_window=tuple(rc["late_window"]),
        temporal_minimum_entities=int(rc["temporal_minimum_entities"]),
        temporal_minimum_pairs_per_entity=int(rc["temporal_minimum_pairs_per_entity"]),
    )
    rel_candidates = [row for row in rel_rows if row["candidate_screen_passed"]]
    rel_status_counts = Counter(row["candidate_status"] for row in rel_rows)
    rel_stability_counts = Counter(row["temporal_stability"] for row in rel_rows)
    rel_lag_counts = Counter(str(row["lag_years"]) for row in rel_rows)

    vc = vol_contract["detection"]
    vol_rows = scan_variance_shifts(
        series,
        metric_metadata=metric_meta,
        minimum_segment_changes=int(vc["minimum_segment_changes"]),
        minimum_variance_change_factor=float(vc["minimum_variance_change_factor"]),
    )
    vol_candidates = [row for row in vol_rows if row["candidate"]]
    vol_status_counts = Counter(row["candidate_status"] for row in vol_rows)
    vol_direction_counts = Counter(row["direction"] for row in vol_candidates)

    REL_OUT.mkdir(parents=True, exist_ok=True)
    VOL_OUT.mkdir(parents=True, exist_ok=True)
    rel_scan = REL_OUT / "RELATIONSHIP_SCAN_V1.jsonl"
    rel_selected = REL_OUT / "RELATIONSHIP_CANDIDATES_V1.jsonl"
    rel_summary_path = REL_OUT / "RELATIONSHIP_DISCOVERY_SUMMARY_V1.json"
    vol_scan = VOL_OUT / "VOLATILITY_SHIFT_SCAN_V1.jsonl"
    vol_selected = VOL_OUT / "VOLATILITY_SHIFT_CANDIDATES_V1.jsonl"
    vol_summary_path = VOL_OUT / "VOLATILITY_SHIFT_SUMMARY_V1.json"

    write_jsonl(rel_scan, rel_rows)
    write_jsonl(rel_selected, rel_candidates)
    write_jsonl(vol_scan, vol_rows)
    write_jsonl(vol_selected, vol_candidates)

    rel_summary = {
        "contract_id": rel_contract["contract_id"],
        "status": "CANDIDATE_GENERATION_ONLY",
        "search_comparisons": len(rel_rows),
        "candidate_count": len(rel_candidates),
        "candidate_status_counts": dict(sorted(rel_status_counts.items())),
        "lag_year_counts": dict(sorted(rel_lag_counts.items())),
        "temporal_stability_counts": dict(sorted(rel_stability_counts.items())),
        "analysis_modes": ["ENTITY_DEMEANED", "ENTITY_AND_YEAR_EFFECT_ADJUSTED"],
        "metric_count": len(metric_meta),
        "metric_ids": sorted(metric_meta),
        "max_lag_years": int(rc["maximum_lag_years"]),
        "thresholds_are_inferential": False,
        "null_tests_performed": False,
        "p_values_computed": False,
        "causal_claims_permitted": False,
        "forecasts_permitted": False,
        "point_in_time_eligible": False,
        "sources": source_report,
    }
    vol_summary = {
        "contract_id": vol_contract["contract_id"],
        "status": "CANDIDATE_GENERATION_ONLY",
        "series_scanned": len(vol_rows),
        "testable_series": sum(not row["candidate_status"].startswith("NOT_TESTABLE") for row in vol_rows),
        "candidate_count": len(vol_candidates),
        "candidate_status_counts": dict(sorted(vol_status_counts.items())),
        "candidate_direction_counts": dict(sorted(vol_direction_counts.items())),
        "minimum_segment_changes": int(vc["minimum_segment_changes"]),
        "minimum_variance_change_factor": float(vc["minimum_variance_change_factor"]),
        "variance_measure": "squared_max_of_qn_mad_iqr_scales_of_transformed_exact_annual_changes",
        "change_transform_counts": dict(sorted(Counter(row["change_transform"] for row in vol_rows).items())),
        "not_testable_reasons": dict(sorted(Counter(row["candidate_status"] for row in vol_rows if row["candidate_status"].startswith("NOT_TESTABLE")).items())),

        "null_tests_performed": False,
        "p_values_computed": False,
        "causal_claims_permitted": False,
        "forecasts_permitted": False,
        "point_in_time_eligible": False,
        "sources": source_report,
    }
    write_json(rel_summary_path, rel_summary)
    write_json(vol_summary_path, vol_summary)

    artifacts = [
        artifact_entry(rel_scan, "complete_relationship_search_family"),
        artifact_entry(rel_selected, "unvalidated_relationship_candidates"),
        artifact_entry(rel_summary_path, "relationship_discovery_summary"),
        artifact_entry(vol_scan, "complete_volatility_series_scan"),
        artifact_entry(vol_selected, "unvalidated_volatility_candidates"),
        artifact_entry(vol_summary_path, "volatility_shift_summary"),
    ]
    manifest = {
        "bundle_id": "CHAOS_CROSS_SERIES_AND_VOLATILITY_DISCOVERY_V1",
        "generated_at_utc": utc_now(),
        "status": "CANDIDATE_GENERATION_ONLY",
        "source_report": source_report,
        "metric_registry": metric_meta,
        "contracts": {
            "relationship": {"path": REL_CONTRACT.relative_to(ROOT).as_posix(), "sha256": sha256_file(REL_CONTRACT)},
            "volatility": {"path": VOL_CONTRACT.relative_to(ROOT).as_posix(), "sha256": sha256_file(VOL_CONTRACT)},
        },
        "code": {
            "module": {
                "path": "discovery_engine/cross_series_relationship_discovery_v1.py",
                "sha256": sha256_file(ROOT / "discovery_engine/cross_series_relationship_discovery_v1.py"),
            },
            "runner": {
                "path": "scripts/discovery/run_cross_series_and_volatility_v1.py",
                "sha256": sha256_file(Path(__file__)),
            },
        },
        "artifacts": artifacts,
        "inference_policy": {
            "candidate_generation_only": True,
            "null_tests_performed": False,
            "inferential_p_values": False,
            "causal_claims": False,
            "forecasts": False,
            "imputation": False,
            "frequency_conversion": False,
            "source_averaging": False,
            "available_at_inference": "not_possible_source_metadata_unknown",
            "point_in_time_eligible": False,
        },
    }
    manifest_path = REL_OUT / "CROSS_SERIES_DISCOVERY_MANIFEST_V1.json"
    write_json(manifest_path, manifest)
    return {
        "status": "success",
        "manifest": manifest_path.relative_to(ROOT).as_posix(),
        "relationship_search_comparisons": len(rel_rows),
        "relationship_candidates": len(rel_candidates),
        "volatility_series_scanned": len(vol_rows),
        "volatility_candidates": len(vol_candidates),
        "macro_entities": source_report["macro_eia"]["entities"],
        "trade_entities": source_report["wdi_trade"]["entities"],
        "exact_entity_code_intersection": source_report["exact_entity_code_intersection"],
        "metric_count": source_report["metric_count_total"],
    }


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
