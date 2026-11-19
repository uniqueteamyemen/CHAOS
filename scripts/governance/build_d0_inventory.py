from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
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
        ["git", *args], cwd=ROOT, check=True,
        capture_output=True, text=True,
    )
    return proc.stdout.strip()


def tracked_paths() -> list[str]:
    raw = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True,
        capture_output=True,
    ).stdout
    return [part.decode("utf-8") for part in raw.split(bytes([0])) if part]


def is_text_source(path: str) -> bool:
    return Path(path).suffix.lower() in {
        ".py", ".ts", ".tsx", ".js", ".jsx", ".yml", ".yaml",
        ".json", ".md", ".toml", ".txt",
    }


def read_text(path: str) -> str | None:
    p = ROOT / path
    try:
        if p.stat().st_size > 2_000_000:
            return None
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def classify_contracts(tracked: list[str]) -> dict[str, Any]:
    roots = (
        "experimental_contracts/",
        "catalog_first/experimental_contracts/",
        "campaigns/CAMPAIGN_SHARED_GATE_V1/",
    )
    contract_paths = [
        p for p in tracked
        if p.startswith(roots) and Path(p).suffix.lower() in {".json", ".md"}
        and any(token in Path(p).name.lower() for token in ("contract", "schema", "ledger", "dictionary", "amendment"))
    ]
    searchable = [
        p for p in tracked
        if not p.startswith("experiments/") and is_text_source(p)
    ]
    texts = {p: read_text(p) for p in searchable}
    texts = {p: t for p, t in texts.items() if t is not None}
    rows = []
    families: dict[str, list[str]] = defaultdict(list)

    for contract in sorted(contract_paths):
        name = Path(contract).name
        stem = Path(contract).stem
        references = []
        token = name.lower()
        stem_token = stem.lower()
        for source_path, content in texts.items():
            if source_path == contract:
                continue
            low = content.lower()
            if token in low or (len(stem_token) >= 18 and stem_token in low):
                references.append(source_path)

        low_name = name.lower()
        if "draft" in low_name or "/draft" in contract.lower():
            status = "draft"
        elif "review" in low_name or "amendment" in low_name:
            status = "review_or_amendment"
        elif any(p.startswith((".github/workflows/", "structural_engine/", "real_data_stress_pipeline/", "chaos_governance_kernel/", "scripts/")) for p in references):
            status = "referenced_by_executable_or_workflow"
        elif references:
            status = "documented_reference_only"
        else:
            status = "unreferenced_candidate"

        family = stem
        for marker in ("_V", "_v", "-v", "_DRAFT", "_REVIEW", "_draft", "_review"):
            position = family.find(marker)
            if position > 12:
                family = family[:position]
                break
        family = stem
        for marker in ("_V", "_v", "-v", "_DRAFT", "_REVIEW", "_draft", "_review"):
            position = family.find(marker)
            if position > 12:
                family = family[:position]
                break
        families[family].append(contract)
        rows.append({
            "path": contract,
            "classification": status,
            "reference_count": len(references),
            "references": references[:30],
            "version_family": family,
        })

    related = [
        {"family": family, "members": members}
        for family, members in sorted(families.items()) if len(members) > 1
    ]
    return {
        "classification_rule": "Path/name and literal references in tracked non-experiment sources; this is a routing inventory, not semantic approval.",
        "contract_count": len(rows),
        "counts_by_classification": dict(Counter(row["classification"] for row in rows)),
        "version_or_name_families": related,
        "items": rows,
    }


def build_runtime_map(tracked: list[str]) -> dict[str, Any]:
    source_paths = [
        p for p in tracked
        if not p.startswith("experiments/") and is_text_source(p)
    ]
    texts = {p: read_text(p) for p in source_paths}
    texts = {p: t for p, t in texts.items() if t is not None}

    symbols = {
        "python_frozen_detector": [
            "BreakDetectorV1", "structural_engine.isolated_break_detector_v1"
        ],
        "python_historical_pipeline": [
            "real_data_stress_pipeline.run_pipeline", "run_pipeline.py"
        ],
        "python_governance_kernel": [
            "chaos_governance_kernel.core", "validate_manifest(", "build_graph("
        ],
        "typescript_runtime": [
            "executeChaosRuntimeV1", "chaosRuntimeV1"
        ],
        "typescript_discovery": [
            "runNeutralDiscoveryPipeline", "discoveryEngineCore"
        ],
        "typescript_forecasting": [
            "runFutureForecastEngine", "futureForecastEngine"
        ],
        "typescript_browser_governance": [
            "validateGovernanceManifest", "governanceKernel"
        ],
    }
    callsites = {}
    for component, needles in symbols.items():
        matches = []
        for path, content in texts.items():
            if path.startswith("experiments/"):
                continue
            if any(needle in content for needle in needles):
                matches.append(path)
        callsites[component] = matches

    workflow_commands = []
    for path in tracked:
        if not path.startswith(".github/workflows/") or Path(path).suffix not in {".yml", ".yaml"}:
            continue
        content = texts.get(path, "")
        commands = []
        in_run = False
        for number, line in enumerate(content.splitlines(), 1):
            if re.match(r"\\s*run:\\s*\\|?", line):
                in_run = True
            elif line.startswith("      - ") or (line.startswith("    ") and not line.startswith("          ")):
                in_run = False
            if in_run and any(token in line for token in ("python ", "pytest", "npm ", "npx ", "node ", "docker ", "unittest")):
                commands.append({"line": number, "command": line.strip()[:240]})
        workflow_commands.append({"workflow": path, "commands": commands})

    return {
        "method": "static source-reference scan; no dynamic execution was performed during P0",
        "call_sites": callsites,
        "workflow_execution_commands": workflow_commands,
        "runtime_interpretation": {
            "python": "research and authoritative computation, detectors, data pipeline, governance validation",
            "typescript": "browser UI and legacy/demo calculations; not authoritative for new scientific results",
            "warning": "Static references do not prove that every referenced path is exercised in production."
        },
    }


def build() -> dict[str, Any]:
    tracked = tracked_paths()
    missing = sorted(set(CORE_ARTIFACTS) - set(tracked))
    if missing:
        raise RuntimeError(f"D0 core inventory paths are missing or untracked: {missing}")

    source_entries = [
        registry_entry(ROOT / path, ROOT, role)
        for path, role in sorted(CORE_ARTIFACTS.items())
    ]
    suffixes = Counter(Path(path).suffix.lower() or "[no extension]" for path in tracked)
    workflows = [
        p for p in tracked if p.startswith(".github/workflows/")
        and Path(p).suffix.lower() in {".yml", ".yaml"}
    ]
    contract_inventory = classify_contracts(tracked)
    runtime_inventory = build_runtime_map(tracked)

    checkout = {
        "commit": git_output("rev-parse", "HEAD"),
        "branch": os.getenv("GITHUB_HEAD_REF") or os.getenv("GITHUB_REF_NAME") or git_output("branch", "--show-current"),
        "event_name": os.getenv("GITHUB_EVENT_NAME") or "local",
        "base_ref": os.getenv("GITHUB_BASE_REF") or None,
        "pr_base_sha": os.getenv("PR_BASE_SHA") or None,
        "pr_head_sha": os.getenv("PR_HEAD_SHA") or None,
        "working_tree": git_output("status", "--porcelain"),
        "note": "On pull_request workflows, commit is the tested merge commit; PR head/base SHAs are recorded separately.",
    }

    counts = {
        "tracked_files": len(tracked),
        "python_files": suffixes[".py"],
        "typescript_and_tsx_files": suffixes[".ts"] + suffixes[".tsx"],
        "javascript_files": suffixes[".js"] + suffixes[".jsx"],
        "workflow_files": len(workflows),
        "experimental_contract_files": contract_inventory["contract_count"],
        "experiment_tree_files": sum(p.startswith("experiments/") for p in tracked),
        "test_named_files": sum(
            Path(p).name.startswith("test_") or "test" in Path(p).stem.lower()
            for p in tracked
        ),
    }

    inventory = {
        "bundle_id": "D0_REPOSITORY_BASELINE_V1",
        "schema_version": "1.1.0",
        "captured_at": utc_now(),
        "repository": "uniqueteamyemen/CHAOS",
        "checkout": checkout,
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
        "runtime_inventory": runtime_inventory,
        "contract_inventory": contract_inventory,
        "observed_governance": {
            "ruleset_id": 27488330,
            "ruleset_name": "main-phase2",
            "enforcement": "active",
            "target": "refs/heads/main-phase2",
            "required_status_checks": ["stress"],
            "experiments_immutable_workflow_exists": True,
            "experiments_immutable_is_required_check": False,
            "governance_artifact_workflow_exists": True,
            "governance_artifact_workflow_is_required_check": False,
            "require_pull_request": False,
            "require_independent_approval": False,
            "bypass_available": True,
            "tag_refs_observed": [
                "p2.2-historical-stress-v1.0.0",
                "p2.2-historical-stress-v1.0.1",
                "phase1-detector-freeze-v1.0"
            ],
            "tag_protection": "not verified; remains an explicit repository-governance blocker"
        },
        "inventory_artifacts": [
            {
                "path": entry.path, "role": entry.role,
                "sha256": entry.sha256, "bytes": entry.bytes
            }
            for entry in source_entries
        ],
        "limitations": [
            "P0 performs static inventory and does not execute research workflows or certify scientific validity.",
            "Static references show wiring, not necessarily runtime reachability for every code path.",
            "Branch-protection read endpoint was unavailable through the connected integration; ruleset state was read directly.",
            "Ruleset/tag protection changes are not made by this workflow.",
            "The inventory must be regenerated after relevant source or governance changes."
        ],
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json(INVENTORY_PATH, inventory)
    inventory_entry = registry_entry(INVENTORY_PATH, ROOT, "d0_inventory_output")
    manifest = {
        "bundle_id": "D0_REPOSITORY_BASELINE_V1",
        "schema_version": "1.1.0",
        "decision_status": "baseline_captured",
        "generated_at": utc_now(),
        "artifacts": [
            {
                "path": entry.path, "role": entry.role,
                "sha256": entry.sha256, "bytes": entry.bytes
            }
            for entry in [*source_entries, inventory_entry]
        ],
        "decision": {
            "status": "P0_IN_PROGRESS",
            "summary": "D0 captures runtime and contract references; P0 still requires semantic contract reconciliation and external ruleset/tag enforcement."
        },
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
        "contracts_classified": contract_inventory["contract_count"],
        "runtime_components": len(runtime_inventory["call_sites"]),
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, sort_keys=True))
