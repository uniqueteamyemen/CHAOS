from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiment_grid import build_initial_specs, write_matrix, write_registry, write_run_manifest

RAW = ROOT.parent / "campaign" / "raw"
OUT = ROOT / "reports"
DERIVED = ROOT / "derived"
OUT.mkdir(parents=True, exist_ok=True)
DERIVED.mkdir(parents=True, exist_ok=True)


def latest_json(pattern: str) -> Path | None:
    candidates = sorted(RAW.glob(f"*/{pattern}"))
    return candidates[-1] if candidates else None


def parse_world_bank(path: Path, label: str) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload[1] if isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], list) else []
    return {str(row["date"]): float(row["value"]) for row in values if row.get("date") and row.get("value") is not None}


def parse_imf(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("values", {}).get("NGDP_RPCH", {})
    # World aggregate is preferred; no aggregate is fabricated when absent.
    for key in ("WEO:001", "WLD", "001"):
        series = values.get(key)
        if isinstance(series, dict):
            return {str(year): float(value) for year, value in series.items() if str(year) <= "2025" and value is not None}
    return {}


specs = build_initial_specs()
write_registry(specs, OUT / "experiment_registry.jsonl")
write_run_manifest(specs, OUT / "experiment_registry_manifest.json")

series: dict[str, dict[str, float]] = {}
for label in ["gdp_constant_usd", "inflation_cpi", "energy_use_per_capita", "population", "trade_growth"]:
    path = latest_json(f"worldbank_WLD_{label}.json")
    if path:
        series[f"worldbank.wdi.WLD.{label}"] = parse_world_bank(path, label)

imf_path = latest_json("imf.json")
if imf_path:
    series["imf.datamapper.NGDP_RPCH"] = parse_imf(imf_path)

# The annual experiment is descriptive and uses inner-join rows only.
years = sorted(set().union(*(set(values) for values in series.values())))
rows = []
for year in years:
    row = {"year": year}
    present = 0
    for variable, values in series.items():
        if year in values:
            row[variable] = values[year]
            present += 1
    if present >= 2:
        rows.append(row)

write_matrix(rows, DERIVED / "annual_observed_matrix.csv")
(OUT / "experiment_grid_build_summary.json").write_text(
    json.dumps(
        {
            "experiments_declared": [spec.experiment_id for spec in specs],
            "variables_seen": sorted(series),
            "annual_rows_with_at_least_two_observed_variables": len(rows),
            "imputation_performed": False,
            "raw_mutation_performed": False,
            "source_reconciliation_performed": False,
            "note": "This is an observed inner-join matrix for exploratory validation; no annual value was inferred.",
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(f"experiments={len(specs)} rows={len(rows)} variables={len(series)}")
