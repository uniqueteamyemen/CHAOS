# CHAOS — Repository Hygiene Audit V1

**Audit date:** 22 November 2026  
**Repository:** `uniqueteamyemen/CHAOS`  
**Audit base:** `main-phase2`  
**Base commit:** `b838eb48b2040bf358fc216e1e004311edfc30e8`  
**Audit branch:** `chore/repository-hygiene-audit-v1@228591f56ef4d9ec8e9a2e1f8b8660717d1781aa`  \n**Purpose:** Establish and maintain a non-destructive repository classification and staged verification plan after Discovery V1 integration.

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

**Current audit baseline:** `main-phase2@b838eb48b2040bf358fc216e1e004311edfc30e8`.

The recursive Git tree and the post-integration architecture record establish the following current counts:

| Measure | Verified count |
|---|---:|
| Tracked files | 1,408 |
| Directories | 225 |
| Total tree entries | 1,633 |
| Files under `experiments/**` | 916 |
| YAML workflows under `.github/workflows/` | 27 |
| Additional non-workflow marker under `.github/workflows/` | 1 |

These figures supersede the earlier 1,556-path inventory from the 17 November baseline. The 916 experiment files remain historical evidence and are outside the cleanup mutation scope.

The inventory is a Git-tree count. It does not imply that external raw data, local workspace files, or GitHub Actions artifact payloads are present in a clean clone.

## 3. Current branch and integration observations

- The current `main-phase2` head is `b838eb48b2040bf358fc216e1e004311edfc30e8`.
- PR #30 merged the dependency map and frozen-archive guard work at `7eb619c1a7756b52aeffb32a06278e786c0dd762`.
- PR #28 merged Discovery V1 at `e0c13b41ef1bbbdfe46f1dc266a007eb2dedd8d7`.
- PR #31 merged the post-Discovery documentation refresh at `b838eb48b2040bf358fc216e1e004311edfc30e8`.
- The current component classification therefore treats Discovery V1 as integrated into `main-phase2`, but only as a research/candidate-generation and governance foundation.
- The audit branch `chore/repository-hygiene-audit-v1` is at `228591f56ef4d9ec8e9a2e1f8b8660717d1781aa`. Its comparison with current `main-phase2` is diverged: 17 commits ahead, 3 behind, merge base `365bb2111c89352466d72e60965246bf238ffabb`, with eight paths in the net file comparison. PR #30 is already merged; do not reopen or merge the whole branch as a new combined change. Keep its remaining audit history and isolate any future documentation-only change from workflow/code scope.
- The open PR #24 concerns Markov rho observability and targets `p2.2.2-markov-calibration-audit`; it is unrelated to Discovery integration and repository hygiene.
- The P2.2 stress run `44951886189` is running on SHA `7eb619c1a7756b52aeffb32a06278e786c0dd762`. The immutable-guard run `44951886251` on that same SHA completed successfully. These are SHA-specific results; they do not convert the DomainState registry into PASS.

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

Twenty-seven workflow YAML files are present in the post-Discovery main-phase2 tree. Their names suggest several historical experiment families, but names alone do not establish that workflows are obsolete. Each workflow must be checked for:

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
| Discovery | Integrated research/candidate-generation and evidence governance | `observation_foundation/`, `discovery_engine/`, `discovery/`, `scripts/discovery/`, `scripts/governance/`, and adapters; integrated by PR #28, not a validated forecasting engine |
| Evidence operations | Campaigns, agent records, ledgers, gates | `campaigns/`, `campaign/` |
| Historical research | Frozen experiments and their evidence | `experiments/` (immutable) |
| Validation and CI | Tests, guards, workflows | `.github/workflows/`, tests, `scripts/` |
| Presentation | UI and static display data | `src/` |

This model does not authorize moving existing files. It is a classification map for future decisions.

## 6. Stage execution status

The staged work is assessed against the current `main-phase2` baseline above. “Complete” means complete within the bounded Git-tracked repository scope, not proof that every external source or historical artifact is available.

### Stage A — Inventory and dependency mapping

<badge>COMPLETED — BOUNDED SCOPE</badge>

- Recursive repository inventory refreshed to 1,408 tracked files, 225 directories, 1,633 total tree entries, and 27 YAML workflows.
- Workflow-to-entrypoint/artifact dependency map recorded in `docs/WORKFLOW_DEPENDENCY_MAP_V1_AR.md`.
- Python/TypeScript entrypoint and import map recorded in `docs/ENTRYPOINT_AND_IMPORT_MAP_V1_AR.md`.
- Branch history, PR relationships, CI workflow scope, and protected-path boundaries reviewed.
- Limitation: this audit did not download and inspect every historical Actions artifact payload, and it did not run a fresh local checkout of every manual tool. Missing external assets remain explicit.

### Stage B — Repository classification

<badge>COMPLETED</badge>

- Component and branch classifications recorded in `docs/REPOSITORY_COMPONENT_CLASSIFICATION_V1_AR.md`.
- Discovery V1 reclassified from candidate branch work to integrated `ACTIVE-BASE / RESEARCH-ONLY` after PR #28.
- Source existence, adapter readiness, supported edge evidence, causal claims, and runtime eligibility remain separate statuses.
- DomainState registry remains `BLOCKED_INCOMPLETE_ASSET_SET`: 21 registered paths, 15 present, 6 absent, 94,231 records read, and zero schema-invalid records.
- One absent path is the WGI materialized output in the active campaign area. Five absent references belong to the immutable `experiments/**` archive.

### Stage C — Documentation and CI hygiene

<badge>PARTIALLY COMPLETED</badge>

- Repository architecture, workflow, entrypoint, component classification, Engine 1 integration, and DomainState audit documentation were refreshed in PR #31.
- PR #30 added a fail-closed immutable-path guard for both `experiments/**` and `structural_engine/isolated_break_detector_v1/**`, with tests and workflow integration.
- The `experiments-immutable` run `44951886251` passed on SHA `7eb619c1a7756b52aeffb32a06278e786c0dd762`.
- The expensive P2.2 stress run `44951886189` on that SHA remains in progress; its historical pipeline and release-artifact steps have not yet completed.

### Stage D — Controlled structural changes

<badge>NOT STARTED</badge>

No repository paths have been moved, renamed, or deleted by this audit. No workflow has been consolidated or disabled. The frozen detector and `experiments/**` remain untouched.

### Stage E — Verification and closure

<badge>IN PROGRESS</badge>

- Frozen-path integrity check: passed on the recorded SHA.
- P2.2 stress validation: still running at the time of this snapshot; step 8, “Execute real historical stress pipeline”, is in progress. Snapshot packaging, raw-response upload/numerical audit, and release publication are pending.
- DomainState asset completeness: blocked independently of CI execution; six references remain unresolved.
- Final closure requires the stress run's completed conclusion and artifact review, plus an explicit evidence-based disposition of the six missing registry references.

## 7. Immediate next action

1. Preserve the active P2.2 run without launching a duplicate. After run `44951886189` finishes, inspect its final job conclusion, source-snapshot artifacts, numerical audit, and release outcome. Record the SHA tested; the run currently targets `7eb619c1`, while the latest branch head is `b838eb48`.
2. Reconcile the one missing active WGI output only after the declared raw `WGI_CSV.zip` is supplied and its SHA-256 is verified. The current tree contains WGI provenance and summary metadata, but not the source ZIP or a tracked WGI materialization entrypoint. Do not treat the 32,403 estimated states as reproducible output yet.
3. Keep the five missing WHO/IMF references under `experiments/**` immutable. Resolve their registry semantics through an explicit, versioned scope/requiredness decision; do not recreate or modify those historical files to force a PASS.
4. Only after the registry reports an honest, policy-valid readiness state should Engine 1 proceed to its remaining pattern/relationship/structural validation and freeze-manifest/handoff gate. Engine 2 remains closed until that handoff is accepted.

No file relocation, deletion, workflow disablement, experiment modification, detector modification, or automatic branch deletion is authorized by this audit.

**Audit status:** Stage A and Stage B complete within the audited Git scope; Stage C partially complete; Stage D not started; Stage E still in progress. Discovery V1 is integrated as research-only foundation. DomainState registry remains blocked, and the P2.2 stress run has not yet reported a final result.
