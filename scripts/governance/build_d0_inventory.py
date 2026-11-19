from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from chaos_governance_kernel.core import (  # noqa: E402
    registry_entry,
    utc_now,
    validate_manifest,
    write_json,
)

OUTPUT = ROOT / "governance" / "artifacts"
INVENTORY_PATH = OUTPUT / "D0_BASELINE_INVENTORY_V1.json"
MANIFEST_PATH = OUTPUT / "D0_BASELINE_MANIFEST_V1.json"
VALIDATION_PATH = OUTPUT / "D0_VALIDATION_REPORT_V1.json"

# Explicit, reviewable architecture surface. Historical experiment outputs are excluded.
CORE_ARTIFACTS = {
    "AGENTS.md": "integrity_policy",
    "README.md": "repository_entrypoint",
    "package.json": "typescript_ui_dependencies",
    "tsconfig.json": "typescript_ui_build_contract",
    "docs/PHASE1_DETECTOR_FREEZE.md": "frozen_detector_decision",
    "docs/P2.2_STATISTICAL_AUDIT_AR.md": "real_data_audit",
    "docs/EVENT_PATH_PREDICTION_MECHANICS_AUDIT_V1_AR.md": "event_path_audit",
    "docs/EVENT_PATH_ENGINE_SPEC_V1_AR.md": "event_path_contract",
    "docs/EVENT_PATH_KERNEL_REPAIR_V2_AR.md": "event_path_repair",
    "docs/MULTI_DOMAIN_SCOPE_AND_PRIORITY_AR.md": "domain_scope",
    "docs/PREDICTIVE_EARLY_WARNING_ENGINE_PLAN_AR.md": "forecasting_plan",
    "docs/SEVEN_STEP_EXECUTION_STATUS_AR.md": "legacy_research_sequence",
    "docs/REPOSITORY_PROTECTION_AUDIT.md": "repository_protection_audit",
    "structural_engine/isolated_break_detector_v1/break_detector_v1.py": "frozen_detector_adapter",
    "structural_engine/isolated_break_detector_v1/engine_fast_ref.py": "frozen_fast_detector",
    "structural_engine/isolated_break_detector_v1/engine_markov_cusum.py": "frozen_markov_detector",
    "structural_engine/isolated_break_detector_v1/tests/test_contract.py": "detector_contract_tests",
    "real_data_stress_pipeline/run_pipeline.py": "real_data_pipeline",
    "real_data_stress_pipeline/config/pipeline.json": "real_data_pipeline_config",
    "real_data_stress_pipeline/tests/test_pipeline.py": "pipeline_tests",
    "chaos_governance_kernel/core.py": "governance_kernel_core",
    "chaos_governance_kernel/checks.py": "governance_kernel_checks",
    "chaos_governance_kernel/cli.py": "governance_kernel_cli",
    "experimental_contracts/TRANSITION_EVIDENCE_SCHEMA_V1.json": "transition_evidence_contract",
    "experimental_contracts/DOMAIN_STATE_SCHEMA_V1.json": "domain_state_contract",
    "experimental_contracts/TEMPORAL_ALIGNMENT_CONTRACT_V1.json": "temporal_alignment_contract",
    "experimental_contracts/RESEARCH_RUNTIME_SANDBOX_CONTRACT_V1.json": "research_runtime_contract",
    "experimental_contracts/REGIME_LOCKED_TEST_CONTRACT_V1.json": "locked_test_contract",
    "experimental_contracts/RESEARCH_LEDGER_CONTRACT_V1.json": "research_ledger_contract",
    "src/App.tsx": "web_ui_entrypoint",
    "src/components/ChaosRuntimeView.tsx": "legacy_runtime_ui",
    "src/components/DiscoveryEngineView.tsx": "legacy_discovery_ui",
    "src/components/FutureForecastEngineView.tsx": "legacy_forecast_ui",
    "src/utils/chaosRuntimeV1.ts": "legacy_typescript_runtime",
    "src/utils/discoveryEngineCore.ts": "legacy_typescript_discovery",
    "src/utils/futureForecastEngine.ts": "legacy_typescript_forecast",
    "src/utils/governanceKernel.ts": "browser_governance_adapter",
    ".github/workflows/real-data-stress.yml": "real_data_workflow",
    ".github/workflows/experiments-immutable.yml": "experiment_immutability_workflow",
    ".github/workflows/phase1-detector-real-data.yml": "phase1_workflow",
    ".github/CODEOWNERS": "review_ownership",
    "scripts/guards/check_experiments_immutable.py": "experiment_immutability_guard",
}


def git_output(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def tracked_paths() -> list[str]:
    raw = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return [part.decode("utf-8") for part in raw.split(b"\0") if part]


def build() -> dict[str, Any]:
    tracked = tracked_paths()
    missing = sorted(set(CORE_ARTIFACTS) - set(tracked))
    if missing:
        raise RuntimeError(f"D0 core inventory paths are missing or untracked: {missing}")

    source_entries = [
        registry_entry(ROOT / path, ROOT, role)
        for path, role in sorted(CORE_ARTIFACTS.items())
    ]
    files_by_suffix = Counter(Path(path).suffix.lower() or "[no extension]" for path in tracked)
    counts = {
        "tracked_files": len(tracked),
        "python_files": files_by_suffix[".py"],
        "typescript_and_tsx_files": files_by_suffix[".ts"] + files_by_suffix[".tsx"],
        "javascript_files": files_by_suffix[".js"] + files_by_suffix[".jsx"],
        "workflow_files": sum(
            path.startswith(".github/workflows/")
            and Path(path).suffix.lower() in {".yml", ".yaml"}
            for path in tracked
        ),
        "experimental_contract_files": sum(
            path.startswith("experimental_contracts/")
            and Path(path).suffix.lower() == ".json"
            for path in tracked
        ),
        "experiment_tree_files": sum(path.startswith("experiments/") for path in tracked),
        "test_named_files": sum(
            Path(path).name.startswith("test_")
            or "test" in Path(path).stem.lower()
            for path in tracked
        ),
    }

    inventory = {
        "bundle_id": "D0_REPOSITORY_BASELINE_V1",
        "schema_version": "1.0.0",
        "captured_at": utc_now(),
        "repository": "uniqueteamyemen/CHAOS",
        "checkout": {
            "commit": git_output("rev-parse", "HEAD"),
            "branch": git_output("branch", "--show-current"),
            "working_tree": git_output("status", "--porcelain"),
        },
        "audited_refs": {
            "main_phase2": "1b941282a4a415230a65098e066043fbd6a19155",
            "archive_phase1_detector_freeze": "51e4278309b7d32917b85903323a63f81d9e9b6a",
        },
        "repository_counts": dict(counts),
        "canonical_runtime_decision": {
            "scientific_compute": "Python",
            "typescript_role": "React presentation, interaction, and legacy/demo calculations only",
            "status": "architectural decision for new work; legacy UI migration remains gated",
            "basis": [
                "Python detector, historical-data pipeline, tests, and research workflows are explicit and reproducible.",
                "The web application executes TypeScript calculations locally against embedded or preloaded data.",
                "The browser governance helper validates hash shape rather than recomputing file bytes.",
                "The root package manifest describes the Vite/React client; no root Python dependency lock/manifest was found in this baseline."
            ],
            "constraint": "No new independent scientific algorithm may be implemented in TypeScript."
        },
        "observed_governance": {
            "ruleset_id": 27488330,
            "ruleset_name": "main-phase2",
            "enforcement": "active",
            "target": "refs/heads/main-phase2",
            "required_status_checks": ["stress"],
            "experiments_immutable_workflow_exists": True,
            "experiments_immutable_is_required_check": False,
            "require_pull_request": False,
            "require_independent_approval": False,
            "bypass_available": True,
            "tag_refs_observed": [
                "p2.2-historical-stress-v1.0.0",
                "p2.2-historical-stress-v1.0.1",
                "phase1-detector-freeze-v1.0"
            ],
            "tag_protection": "not verified by the available read endpoint; treat as outstanding until a matching tag ruleset is observed"
        },
        "inventory_artifacts": [
            {
                "path": entry.path,
                "role": entry.role,
                "sha256": entry.sha256,
                "bytes": entry.bytes
            }
            for entry in source_entries
        ],
        "limitations": [
            "P0 inventory captures the current tracked source surface; it does not execute research workflows or certify their scientific validity.",
            "Branch-protection read was unavailable through the connected integration; ruleset state was read directly.",
            "The audit snapshot must be regenerated after source or governance changes."
        ]
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json(INVENTORY_PATH, inventory)
    inventory_entry = registry_entry(INVENTORY_PATH, ROOT, "d0_inventory_output")
    manifest = {
        "bundle_id": "D0_REPOSITORY_BASELINE_V1",
        "schema_version": "1.0.0",
        "decision_status": "baseline_captured",
        "generated_at": utc_now(),
        "artifacts": [
            {
                "path": entry.path,
                "role": entry.role,
                "sha256": entry.sha256,
                "bytes": entry.bytes
            }
            for entry in [*source_entries, inventory_entry]
        ],
        "decision": {
            "status": "P0_IN_PROGRESS",
            "summary": "Baseline captured; contract conflict classification and runtime call-site closure remain P0 exit checks."
        }
    }
    write_json(MANIFEST_PATH, manifest)

    validation = validate_manifest(MANIFEST_PATH, ROOT)
    write_json(VALIDATION_PATH, validation)
    if validation["status"] != "pass":
        raise RuntimeError(f"D0 artifact validation failed: {validation['failures']}")
    return {
        "inventory": str(INVENTORY_PATH.relative_to(ROOT)),
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "validation": validation["status"],
        "artifact_count": validation["artifact_count"],
        "tracked_files": len(tracked),
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, sort_keys=True))
