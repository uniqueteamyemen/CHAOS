from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from discovery_engine.weo_vintage_audit_v1 import run_vintage_audit

if __name__ == "__main__":
    summary = run_vintage_audit(
        panel_path=ROOT / "catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv",
        raw_dir=Path("/tmp/chaos_weo_vintage_raw"),
        output_dir=ROOT / "discovery/source_vintage_v1",
    )
    print({
        "status": summary["status"],
        "vintages": summary["vintages"],
        "comparison_entity_count": summary["comparison_entity_count"],
        "downloads": summary["downloads"],
    })
