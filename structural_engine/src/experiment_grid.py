from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    name: str
    source_variables: list[str]
    native_frequencies: dict[str, str]
    alignment_method: str
    transformations_applied: dict[str, list[str]]
    candidate_lag_range: dict[str, int | str]
    discovery_algorithm: str
    surrogate_method: str
    block_length_configuration: list[int]
    number_of_surrogates: int
    random_seed: int
    multiple_testing_correction: str
    train_test_temporal_split: dict[str, str]
    experimental_result_summary: dict[str, Any] = field(default_factory=dict)


def deterministic_experiment_id(name: str, config: dict[str, Any]) -> str:
    serialized = json.dumps({"name": name, "config": config}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]


def write_registry(specs: Iterable[ExperimentSpec], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for spec in specs:
            handle.write(json.dumps(asdict(spec), ensure_ascii=False, sort_keys=True) + "\n")


def build_initial_specs() -> list[ExperimentSpec]:
    annual = {
        "source_variables": [
            "worldbank.wdi.WLD.gdp_constant_usd",
            "worldbank.wdi.WLD.inflation_cpi",
            "worldbank.wdi.WLD.energy_use_per_capita",
            "worldbank.wdi.WLD.population",
            "imf.datamapper.NGDP_RPCH",
        ],
        "native_frequencies": {"all": "annual"},
        "alignment_method": "inner_join_on_calendar_year; no_imputation",
        "transformations_applied": {"all": ["none_at_ingestion"]},
        "candidate_lag_range": {"min": 0, "max": 5, "unit": "years", "reason": "annual_native_frequency"},
        "discovery_algorithm": "lagged_dependence_grid_then_optional_PCMCI",
        "surrogate_method": "circular_shift_and_block_permutation",
        "block_length_configuration": [2, 3, 5],
        "number_of_surrogates": 10000,
        "random_seed": 20260825,
        "multiple_testing_correction": "Benjamini-Hochberg-FDR",
        "train_test_temporal_split": {"train_start": "2000", "train_end": "2017", "test_start": "2018", "test_end": "2025"},
    }
    daily = {
        "source_variables": ["usgs.nwis.01646500.00060"],
        "native_frequencies": {"usgs.nwis.01646500.00060": "daily"},
        "alignment_method": "native_daily_only; no cross-frequency merge",
        "transformations_applied": {"usgs.nwis.01646500.00060": ["none_at_ingestion"]},
        "candidate_lag_range": {"min": 1, "max": 180, "unit": "days", "reason": "initial inverse-window candidate range"},
        "discovery_algorithm": "not_run_single_variable",
        "surrogate_method": "not_run_single_variable",
        "block_length_configuration": [7, 30, 90],
        "number_of_surrogates": 10000,
        "random_seed": 20260825,
        "multiple_testing_correction": "not_applicable_single_variable",
        "train_test_temporal_split": {"train_start": "2000-01-01", "train_end": "2017-12-31", "test_start": "2018-01-01", "test_end": "2025-12-31"},
    }
    specs: list[ExperimentSpec] = []
    for name, config in [("annual_global_macro_grid", annual), ("daily_usgs_streamflow_isolated", daily)]:
        specs.append(ExperimentSpec(experiment_id=deterministic_experiment_id(name, config), name=name, **config))
    return specs


def write_run_manifest(specs: list[ExperimentSpec], path: str | Path) -> None:
    path = Path(path)
    path.write_text(
        json.dumps(
            {
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "experiments": [asdict(spec) for spec in specs],
                "policy": {
                    "predeclared_before_analysis": True,
                    "no_raw_mutation": True,
                    "no_blanket_imputation": True,
                    "no_forced_reconciliation": True,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_matrix(rows: list[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
