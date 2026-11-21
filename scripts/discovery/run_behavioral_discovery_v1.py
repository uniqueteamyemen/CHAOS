from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from discovery_engine.behavioral_discovery_v1 import run_behavioral_discovery

if __name__ == "__main__":
    run_behavioral_discovery(
        panel_path=ROOT / "catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv",
        provenance_path=ROOT / "catalog_first/readiness_gate/macro_plus_eia_energy/SELECTED_VARIABLE_PROVENANCE.csv",
        input_summary_path=ROOT / "catalog_first/readiness_gate/macro_plus_eia_energy/NUMERIC_COMPLETE_MATRIX_V1_1_SUMMARY.json",
        contract_path=ROOT / "experimental_contracts/BEHAVIORAL_DISCOVERY_CONTRACT_V1.json",
        output_dir=ROOT / "discovery/behavioral_v1",
    )
