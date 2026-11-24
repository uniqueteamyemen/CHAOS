from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from chaos_governance_kernel.domain_state import build_domain_state_integrity_report  # noqa: E402

REGISTRY = ROOT / "campaigns" / "CAMPAIGN_SHARED_GATE_V1" / "DOMAIN_STATE_SCHEMA_VALIDATION_V1.json"
OUTPUT = ROOT / "governance" / "artifacts" / "DOMAIN_STATE_INTEGRITY_REPORT_V2.json"


def main() -> int:
    report = build_domain_state_integrity_report(ROOT, REGISTRY, OUTPUT)
    print(json.dumps({
        "report": OUTPUT.relative_to(ROOT).as_posix(),
        "readiness": report["readiness"],
        "files_registered": report["files_registered"],
        "files_by_status": report["files_by_status"],
        "records_seen": report["records_seen"],
        "invalid_records": report["invalid_records"],
        "missing_references": len(report["missing_references"]),
        "missing_evidence_references": len(report["missing_evidence_references"]),
        "files_with_unresolved_evidence_refs": len(report["files_with_unresolved_evidence_refs"]),
        "evidence_ref_audit_files": report["evidence_ref_audit_files"],
        "evidence_records_without_refs": report["evidence_records_without_refs"],
    }, ensure_ascii=False, sort_keys=True))
    # Missing assets or evidence block readiness but remain explicit in the report.
    # Malformed records and unsafe repository-relative paths are a hard CI failure.
    return 1 if report["readiness"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
