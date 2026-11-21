from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from discovery_engine.weo_vintage_audit_v1 import run_vintage_audit

if __name__ == "__main__":
    summary = run_vintage_audit(
        panel_path=ROOT / "catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv",
        contract_path=ROOT / "experimental_contracts/WEO_GDP_GROWTH_VINTAGE_AUDIT_CONTRACT_V1.json",
        raw_dir=ROOT / "discovery/source_vintage_v1/raw_downloads",
        output_dir=ROOT / "discovery/source_vintage_v1",
    )
    print({
        "status": summary["status"],
        "comparison_iso_count": summary["comparison_iso_count"],
        "vintages": summary["vintages"],
        "downloads": summary["downloads"],
    })
