# CHAOS — Repository Hygiene Audit V1

**Audit date:** 21 November 2026  
**Repository:** `uniqueteamyemen/CHAOS`  
**Audit base:** `main-phase2`  
**Base commit:** `1b941282a4a415230a65098e066043fbd6a19155`  
**Purpose:** Establish a non-destructive repository organization plan before any structural cleanup.

## 1. Audit boundary and integrity constraints

This audit is read-only with respect to the scientific implementation and historical evidence.

The following constraints remain binding:

- Do not modify, move, rename, reformat, or delete any path under `experiments/**`.
- Do not modify the frozen detector under `structural_engine/isolated_break_detector_v1/**`.
- Do not rewrite historical results, snapshots, manifests, raw data, or experiment outputs to make the tree appear cleaner.
- Do not merge experimental branches into `main-phase2` as part of repository hygiene.
- Do not alter the default branch or protected branch settings.
- Preserve the distinction between executable implementation, evidence, experiment history, governance records, and presentation assets.
- Every proposed deletion or relocation must first be supported by a reference/consumer audit and a recoverable archive plan.

The repository's `AGENTS.md` remains authoritative for integrity and immutability requirements.

## 2. Verified repository inventory

The recursive Git tree for the audited base contains **1,556 tracked paths**. The top-level distribution is:

| Top-level path | Tracked paths |
|---|---:|
| `experiments/` | 1,049 |
| `campaigns/` | 112 |
| `catalog_first/` | 91 |
| `campaign/` | 56 |
| `experimental_contracts/` | 47 |
| Repository root files | 37 |
| `.github/` | 24 |
| `docs/` | 17 |
| `real_data_stress_pipeline/` | 16 |
| `data/` | 13 |
| `structural_engine/` | 12 |
| `scripts/` | 10 |
| `chaos_governance_kernel/` | 4 |
| `src/` | 36 |
| `lightning_logs/` | 30 |
| `tooling/` | 2 |

The `.github/workflows/` directory contains **21 YAML workflows**. The `docs/` directory contains **17 tracked paths**, including the repository protection audit, scope and phase reports, freeze documentation, and one review report.

The large `experiments/` footprint is historical evidence, not proof of accidental duplication. It is explicitly outside the cleanup mutation scope.

## 3. Current branch and integration observations

- The audited `main-phase2` head is `1b941282a4a415230a65098e066043fbd6a19155`.
- The latest commit is a documentation-only update to `docs/REPOSITORY_PROTECTION_AUDIT.md`.
- The repository has an open P0 governance pull request (#21) targeting `main-phase2`. Repository hygiene work must not duplicate or silently absorb that PR's governance scope.
- Recent Actions activity includes repeated runs on `discovery/d1-domainstate-integrity-v1`, including successful, failed, and cancelled WEO source-vintage audit runs. This is active branch work and must not be interrupted by cleanup.
- The repository has multiple historical experiment and ERP branches. Branch names alone are insufficient evidence for deletion or archival.

## 4. Structural findings

### 4.1 Evidence and implementation boundaries

The repository currently contains distinct concerns that should remain explicit:

1. **Scientific core:** frozen detector implementation and its governed runtime interfaces.
2. **Contracts:** schemas and machine-readable admissibility/lineage definitions.
3. **Data acquisition and catalogs:** source inventories, raw data, manifests, and readiness gates.
4. **Evidence and campaign operations:** DomainState records, transition evidence, supervisor decisions, agent registries, and campaign manifests.
5. **Historical experiments:** immutable experiment code, outputs, and reports.
6. **Validation and CI:** tests, guards, stress pipelines, and workflow definitions.
7. **Presentation:** `src/` and its static snapshots, which must not be treated as the scientific source of truth.

### 4.2 Duplication candidates are not yet deletion candidates

Previously identified overlapping areas include repeated WDI/trade artifacts, multiple detector implementations from historical B-series experiments, repeated reverse-extraction/TFT work, and overlapping P-engine/sequential-break workflows.

These are **review candidates only**. No item is classified as safe to delete or move until import/reference, workflow-trigger, artifact, and provenance checks establish that it is redundant and not a required historical record.

### 4.3 Workflow surface

Twenty-one workflow YAML files are present. Their names suggest several historical experiment families, but names alone do not establish that workflows are obsolete. Each workflow must be checked for:

- trigger conditions and branch filters;
- referenced scripts, paths, and artifacts;
- required status-check contexts and protection dependencies;
- latest successful and failed runs;
- whether it is historical, active, or duplicated in behavior.

No workflow is disabled or removed by this audit.

## 5. Target organization model

The target is a logical organization first, not a forced directory migration:

| Logical layer | Responsibility | Existing locations to preserve initially |
|---|---|---|
| Core | Governed scientific execution | `structural_engine/`, `real_data_stress_pipeline/` |
| Governance | Rules, lineage, admission, immutability | `chaos_governance_kernel/`, `experimental_contracts/`, governance scripts |
| Data and catalogs | Sources, raw evidence, manifests, readiness | `data/`, `catalog_first/`, `campaign/raw/` |
| Discovery | DomainState and discovery-only analysis | Existing discovery branch and its isolated paths |
| Evidence operations | Campaigns, agent records, ledgers, gates | `campaigns/`, `campaign/` |
| Historical research | Frozen experiments and their evidence | `experiments/` (immutable) |
| Validation and CI | Tests, guards, workflows | `.github/workflows/`, tests, `scripts/` |
| Presentation | UI and static display data | `src/` |

This model does not authorize moving existing files. It is a classification map for future decisions.

## 6. Safe execution sequence

### Stage A — Complete inventory (read-only)
- Enumerate all paths and file types.
- Build a workflow-to-script and workflow-to-artifact reference map.
- Build a Python/TypeScript import and entry-point map.
- Identify data manifests whose referenced raw objects are absent.
- Compare repeated artifacts by content hash, provenance, and schema—not by filename alone.

### Stage B — Classification (read-only)
Assign each non-experiment path one status:
- `ACTIVE`: used by a current runtime, test, or workflow.
- `REFERENCE`: authoritative contract, governance record, or source-of-truth documentation.
- `HISTORICAL`: retained evidence or retired implementation.
- `DUPLICATE_CANDIDATE`: byte-identical or behaviorally overlapping item requiring review.
- `UNREFERENCED`: no consumer found after a complete bounded search; not automatically deletable.

### Stage C — Minimal documentation and CI hygiene
- Correct misleading documentation and stale path references.
- Add a clear repository map and ownership boundaries.
- Consolidate workflow definitions only where trigger, permissions, outputs, and required-check semantics are demonstrably equivalent.
- Keep each change isolated and reviewable.

### Stage D — Controlled structural changes
- Use a dedicated branch and pull request.
- Move only non-historical, non-core files with proven consumers and path updates.
- Delete only proven generated duplicates; preserve provenance and checksums.
- Never bundle workflow changes, code changes, and data changes into one broad cleanup commit.

### Stage E — Verification
- Run all affected tests and workflow checks.
- Verify that protected paths are unchanged.
- Verify that no referenced file, artifact, or entry point was orphaned.
- Compare the resulting tree and behavior against the baseline.
- Merge only through the repository's approved PR and CI process.

## 7. Immediate next action

Complete Stage A on a dedicated audit branch. The first deliverable is a machine-checkable path/reference inventory and workflow dependency map. No file relocation, deletion, workflow disablement, experiment modification, or detector modification is authorized by this audit.

**Audit status:** Baseline established; full dependency/reference audit remains pending.
