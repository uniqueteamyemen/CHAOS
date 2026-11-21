# CHAOS — Repository Architecture and Status

**Repository:** `uniqueteamyemen/CHAOS`  
**Current main-phase2 head:** `7eb619c1a7756b52aeffb32a06278e786c0dd762` (Stage A/B documentation and frozen-path CI guard merged; original Phase 2 common ancestor: `1b941282a4a415230a65098e066043fbd6a19155`)  
**Discovery candidate:** `discovery/d1-domainstate-integrity-v1@db57bf29d2e4211d1c23af21cfa0fa3d858f7717` (PR #28; candidate only, no merge yet)  
**USGS-labelled candidate:** `fix/p2-2-3-usgs-catalog-integrity-v1`  
**Document status:** Architecture and integration map; not a scientific approval or merge authorization.

## 1. System identity and execution boundary

CHAOS is a domain-general temporal-structure discovery system. Its intended progression is:

`Observation → Behavioral Discovery → Pattern Discovery → Relationship Discovery → Structural Discovery → Validation → Freeze`

Only after the Engine 1 handoff gate is passed may a separate Engine 2 consume frozen discovery artifacts for sensing and forecasting. A discovered pattern, a temporal association, a detector confirmation, and a validated forecast are different evidence states. None implies the next.

**Canonical scientific runtime:** Python. Python code, contracts, source snapshots, manifests, reproducible workflows, and governed artifacts form the scientific execution path.

**Presentation runtime:** TypeScript/React under `src/`. It is a legacy/demo presentation surface that may display static snapshots and fixtures. It is not an independent scientific authority, does not supersede Python evidence, and must not be promoted as a live source of truth. Keep it operational while decoupling it from scientific approval.

## 2. Architecture map

| Layer | Current responsibility | Canonical locations |
|---|---|---|
| Observation and identity | Source record identity, versions, availability time, lifecycle and disposition | `observation_foundation/`, `experimental_contracts/`, `chaos_governance_kernel/` |
| Engine 1 — behavioral discovery | Per-series behavior, candidates, null/negative controls, vintage review | `discovery_engine/`, `discovery/`, `scripts/discovery/`, `tests/discovery/` |
| DomainState adapters | Native-frequency states and source-specific provenance | `scripts/adapters/`, `campaigns/agents/`, `catalog_first/` |
| Evidence library and admission | Transition evidence, campaign manifests, evidence graph, supervisor gates | `campaigns/`, `chaos_governance_kernel/`, relevant contracts |
| Existing detector research | Frozen Phase 1 detector and historical evaluation | `structural_engine/isolated_break_detector_v1/` and its existing governed interfaces |
| Stress and domain audits | Separate domain/null/declustering validation pipelines | `real_data_stress_pipeline/`, audit scripts and tests |
| Historical research | Immutable prior experiments, results, and provenance | `experiments/**` |
| CI and integrity | Workflow execution, immutability guards, contract and runtime tests | `.github/workflows/`, `scripts/guards/`, `tests/` |
| Presentation | UI and static data display | `src/` |

### Engine 1 status

The Discovery branch introduces:
- `discovery_engine/behavioral_discovery_v1.py`
- calendar-coincidence null and WEO vintage audit modules;
- `observation_foundation/` identity and lifecycle modules;
- DomainState governance integration;
- WDI trade adapter and annual DomainState records;
- behavioral discovery artifacts and supporting contracts, tests, and workflows.

The branch reports a behavioral scan of 1,529 series and 38,225 observations, yielding 1,698 candidates and 45 shared patterns. It marks 697 candidates as sensitive to segmentation boundaries. These are discovery outputs, not validated predictive patterns.

The reported Conditional Calendar Null used 10,000 redistributions and returned the recorded empirical p-value. The WEO vintage audit compares October 2020, April 2021, and April 2026 vintages. Its own report explicitly says the actual-versus-estimate status validation is incomplete; the reported 130/139 sign stability must not be represented as full vintage or causal validation.

The WDI observed-record source and edge diagnostics are already tracked in main-phase2. The dedicated V2 DomainState materialization is part of the Discovery candidate branch. The adapter summary reports 29,004 records, 259 entities, five indicators, and 2000–2024; however the current WDI edge max-stat summaries report p=0.4547726137 for the within-domain test and p=0.5897051474 for WDI-to-economic deterioration (2,000 replicates each), both `research_evidence_only`. Data readiness is not evidence of a supported edge.

### DomainState registry completeness — BLOCKED

The read-only DomainState audit found 21 registered paths, 15 present files, 6 missing references, 94,231 records read, and zero invalid records. Its readiness is `BLOCKED_INCOMPLETE_ASSET_SET`. The CI job passes when the auditor executes and records no invalid data; a green job does not turn this completeness state into PASS.

The six absent paths are the WGI annual DomainState output and five missing files under the protected `experiments/**` archive (WHO daily, plus IMF IMTS BRA/CAN/MEX/ZAF shards). The five archived paths are not to be reconstructed or edited. The WGI summary reports 32,403 estimated DomainStates, but the expected output file is absent in the branch tree.

The previous validator called coarse key collisions `duplicate_state_slots`. Eleven existing archived IMF IMTS shards produced 59,553 collisions because their shared key omits source dimensions such as counterpart country, indicator, trade flow, and valuation. The records are not thereby proven duplicates. The Discovery branch now reports `coarse_identity_collisions`, renames the key function `domain_state_coarse_key`, and adds a regression test preserving separate multidimensional records. See [DomainState Registry Audit](docs/DOMAIN_STATE_REGISTRY_AUDIT_V1_AR.md).

This blocks a claim that the full multi-domain registry is complete. It does not invalidate the isolated WDI materialization or candidate-generation code; merge of PR #28, if approved after new exact-head CI, is an integration of a candidate Engine 1 foundation only, not a DomainState completeness certification or Engine 1 freeze.

**Engine 2 status:** Not authorized to start. Engine 1 has not yet been frozen through a complete acceptance and handoff gate.

## 3. Immutable and protected areas

The following are protected by the repository's `AGENTS.md` and remain outside repository-hygiene changes:

- `experiments/**`: historical experiment code, data, results, and reports. No edits, moves, renames, reformatting, or deletion.
- `structural_engine/isolated_break_detector_v1/**`: frozen detector implementation and mathematics. No edits under this phase.

The merged `experiments-immutable.yml` guard verifies both `experiments/**` and `structural_engine/isolated_break_detector_v1/**` on pull requests and relevant pushes. Unit tests cover the guard and it fails closed if the diff cannot be verified. The `stress` PR status is emitted using contract tests only; the expensive P2.2 stress pipeline and release publishing stay off PR events.

## 4. Source and domain readiness

Readiness is purpose-specific. A raw dataset can be present while an edge, cross-domain path, or predictive use remains blocked.

| Source/domain | Evidence present | Current admissible status |
|---|---|---|
| Macro + EIA Energy | 139 entities, 25 years (2000–2024), 11 numeric variables, 3,475 entity-year rows | Dataset available for analysis. The current energy-agent run reports no new positive within-domain edge and rejects the tested additive edge; do not equate dataset readiness with a supported relationship. |
| WDI Trade | 29,004 observations, 259 entities, five indicators, annual 2000–2024 | Ready for a within-domain edge contract according to the adapter summary. No causal claim or approved predictive edge follows from this status. |
| UN Comtrade | Bounded preview artifacts exist, but coverage is insufficient for a country/partner/commodity historical network | Not testable for the intended historical trade edge without multi-year multidimensional coverage and entity crosswalk. |
| USGS seismic | Native event data and 1,141 M≥6.5 event-state records are present in the campaign status artifact | Native states exist; the proposed cross-domain path is blocked by missing country attribution, observed production shock, and recovery contract. Event-to-annual alignment is not authorized without a new contract. |
| WHO | Daily raw source and derived states are present (573,360 raw rows; 215,751 reported rows used; 239 entities) | Source is present, but the current health-to-annual-GDP path is not testable: reporting-date semantics, cross-country reporting differences, revisions, missing production-shock observation, and prohibited daily-to-annual alignment remain unresolved. |
| WGI | Raw WGI source manifest and adapter output exist (1,296 indicator rows; 216 entities) | Measurement-only evidence. Existing continuity results are rejected as trivial prevalence persistence; decline edges are not testable under support rules. No positive composer edge. |
| UCDP GED | Raw GED ZIP manifest records a 39,122,522-byte archive outside Git and explicitly says it was not used in current replication; a Country-Year profile reports 7,132 rows, 74 columns, 1989–2025 from an external staged path | Do not say UCDP data is absent. The daily GED raw package is external/not committed and was not used; the Country-Year profile is a separate representation and must retain its provenance and native semantics. |
| NOAA GHCN-Daily / GSOM selection | Tracked station profile/selection metadata lists 9 selected stations; detailed CSV paths point to local workspace files outside Git | Station metadata exists; a clean Git clone does not contain the selected station CSV payloads. Reproducible source replay requires those external assets and hashes. |
| IMF IMTS | 15-reporter scoped acquisition for XG/MG returned HTTP 200; a 139-reporter XG-only acquisition records 139 successful responses; the 139-reporter XG+MG paired acquisition records 139 HTTP 403 endpoint errors | Partial acquisition. Export-only coverage is available in manifests/research assets, but the paired export/import series for the 139-reporter universe are blocked. Do not label the entire source either absent or fully ready. |

**Admission invariant:** `campaigns/CAMPAIGN_SHARED_GATE_V1/SUPERVISOR_GATE_DECISION_V1.json` records 2 admitted supported-predictive records, 31 quarantined records, and zero admitted causal claims. The final supervisor gate records zero compiled runtime-eligible outputs. Preserve this distinction; a gate pass is not permission to run an operational predictor.

## 5. Branch map and integration decisions

### Primary branches

- `main-phase2`: sole Phase 2 integration base for this work.
- `discovery/d1-domainstate-integrity-v1`: primary Engine 1 integration candidate.
- `chore/repository-hygiene-audit-v1`: documentation and non-destructive inventory work only.
- `governance/p0-baseline-audit-v1`: P0/D0 history; PR #21 was closed as superseded after verifying inclusion in Discovery ancestry.
- `fix/p2-2-3-usgs-catalog-integrity-v1`: requires selective review; do not merge by branch name.

### Discovery integration evidence

Discovery was rebased by a two-parent merge commit onto the protected-path-guard/documentation baseline in `main-phase2`. Subsequent commits corrected artifact-writer concurrency, added PR read-only validation, recorded current evidence, and corrected DomainState collision reporting. The latest comparison is against `main-phase2`; PR #28 changed-file inventory contains no paths under `experiments/**` or `structural_engine/isolated_break_detector_v1/**`.

Relevant successful Actions runs previously observed (each applies only to its recorded head SHA):
- WDI DomainState build: [44943154074](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44943154074)
- Behavioral Discovery V1: [44946871425](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44946871425)
- Conditional Calendar Null: [44945139684](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44945139684)
- WEO 2020 Source Vintage Audit: [44947329602](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44947329602)

The three generation workflows were made write-on-push/manual and read-only-on-PR. They completed successfully on the materialization head after their artifact-writer concurrency fixes. PR #28 exact-head checks on `4c9b0...` all completed successfully, including `stress`, `experiments-immutable`, Observation Foundation, Source Record Identity, D0 artifact validation, DomainState audit, and the three read-only generation validators. A later code change renamed the coarse DomainState collision metric and added a multidimensional regression test; those changes require a fresh exact-head CI cycle before PR #28 is made ready or merged.

### P0 PR overlap

Former PR #21 (P0 execution plan and D0 inventory) modified several files also changed by Discovery, including:
- `chaos_governance_kernel/core.py`
- `experimental_contracts/RESEARCH_LEDGER_CONTRACT_V1.json`
- `experimental_contracts/TEMPORAL_ALIGNMENT_CONTRACT_V1.json`
- `observation_foundation/**`
- `docs/CHAOS_EXECUTION_PLAN_V2_AR.md`
- `docs/P1_SOURCE_RECORD_IDENTITY_V1_AR.md`
- `docs/P1_HYPOTHESIS_AND_INPUT_LIFECYCLE_V1_AR.md`
- shared workflows and `.gitignore`.

PR #21 was closed as superseded after verifying that the Discovery branch is a descendant of the P0 governance branch (merge base equals P0 head), and that PR #28 contains all 19 paths changed by PR #21, including `scripts/governance/build_d0_inventory.py`. Thus the overlap is already represented in branch ancestry, not an unresolved divergence. The D0 inventory remains part of the Discovery candidate and must pass the exact-PR-head CI and artifact checks.

### USGS-labelled branch assessment

The net comparison for `fix/p2-2-3-usgs-catalog-integrity-v1` reports 87 commits ahead and zero behind. Its changed-file set includes observation-foundation code, seismic null/declustering contracts, a large domain-null audit, and changes to `real_data_stress_pipeline/run_pipeline.py`. It does not present as a narrowly scoped catalog-only patch in the net diff.

Do not merge this branch wholesale. First identify the exact commits and files that implement catalog integrity and magnitude provenance, compare them with Discovery and the current base, and selectively port only unique required changes. Run seismic-specific tests separately. Keep the frozen detector and historical experiment tree untouched.

## 6. Historical branches and open PR classification

Branch names are not proof of current usefulness. Preserve commit history; archive by classification and documentation rather than deleting branches.

| Branch family | Classification | Handling |
|---|---|---|
| `experiment/b3-*` through `experiment/b7-*`, `experiments/identity-lab-v1` | Historical detector/identity research | Preserve as immutable research history; no direct merge into Phase 2. |
| `diag/markov-*`, `p2.2.2-markov-calibration-audit`, `p2.2.2-seismic-null-contract`, `exp/p2-2-5-*` | Diagnostic and calibration tracks | Keep separate; only port independently useful non-mathematical observability or contracts after review. |
| `erp-*`, `feat/erp-*`, `benchmark/erp-*`, `review/abc-adversarial` | Independent ERP/reconciliation research | Keep outside the Engine 1 integration path; do not merge into the scientific core. |
| `archive/phase1-detector-freeze-v1.0`, `phase1-detector-freeze-phase2-real-data` | Frozen Phase 1 references | Preserve as archive references. |

Open PRs at the latest GitHub check:
- #28: Discovery V1 integration; open as Draft. Base/head are synchronized; all earlier exact-head checks passed, but the latest coarse-key validator correction requires a fresh CI pass and the full DomainState registry remains BLOCKED.
- #24: Markov rho observability; open, targets `p2.2.2-markov-calibration-audit`, not `main-phase2`. Keep isolated from the Engine 1 integration.
- #21: closed as superseded after confirming Discovery is a descendant of the P0 branch and all 19 P0 changed paths are included in PR #28.
- #20, #9, #2, #4, #3: closed from the active integration queue; their branches and commits remain. No branch deletion was performed.

## 7. Ordered integration plan

1. **Complete candidate validation:** inspect all Discovery changed files, workflow definitions, contract changes, generated artifact provenance, and the exact branch head. Verify no protected-path changes.
2. **P0 ancestry verified:** PR #21 was closed as superseded; its D0 inventory path and all other changed paths are included in the Discovery descendant. Preserve its branch and commits.
3. **Open/maintain a Discovery PR to `main-phase2`:** require CI on the PR merge candidate, all required checks green, and explicit diff review. Do not merge based solely on successful runs from earlier commits.
4. **Integrate Discovery first:** merge only after the PR's exact-head CI and protected-path checks pass. Engine 1 remains discovery-only; no Engine 2 work starts.
5. **USGS selective port:** identify catalog-specific commits and unique files. Port only the catalog/provenance changes that are absent from the integrated base, through a separate PR and separate CI.
6. **Resolve diagnostic PRs separately:** review #24 only within its Markov diagnostic branch lineage. The P-engine/ERP proposals that were in the active queue are closed without merging; preserve their branch histories.
7. **Repository cleanup:** only after the architecture map and dependency inventory are complete. Do not delete or move historical experiments or frozen detector assets.

## 8. Acceptance conditions before Engine 1 freeze

- Source-to-artifact lineage and content hashes are reproducible.
- DomainState and transition evidence contracts validate deterministically.
- Input disposition is separate from hypothesis lifecycle.
- Point-in-time availability and source revision semantics are explicit.
- Discovery outputs distinguish candidates, segmentation-sensitive candidates, rejected patterns, unresolved cases, and validated patterns.
- Null/negative-control procedures and multiple-testing scope are explicit.
- Independent validation is completed on data not used for discovery or tuning.
- A versioned Engine 1 freeze manifest and handoff contract are published.

Until these conditions are met, Discovery V1 remains a candidate generation and evidence organization capability—not an approved forecasting engine.

## 9. Stage A/B reference documents

- [Workflow dependency map](docs/WORKFLOW_DEPENDENCY_MAP_V1_AR.md)
- [Entrypoint and import map](docs/ENTRYPOINT_AND_IMPORT_MAP_V1_AR.md)
- [Component and branch classification](docs/REPOSITORY_COMPONENT_CLASSIFICATION_V1_AR.md)
- [Repository hygiene audit](docs/REPOSITORY_HYGIENE_AUDIT_V1_AR.md)
- [DomainState registry audit](docs/DOMAIN_STATE_REGISTRY_AUDIT_V1_AR.md)
- [Engine 1 Discovery integration status](docs/ENGINE1_DISCOVERY_INTEGRATION_STATUS_V1_AR.md)

At the checked baseline, `main-phase2` has 1,347 tracked files and 211 directories (1,558 total tree entries); `experiments/**` accounts for 916 files. It has 21 YAML workflows and one non-workflow text marker. The Discovery branch contains 1,400 files and six additional workflows; it is not yet integrated.

## 10. Repository hygiene guardrails

- No direct pushes to `main-phase2`.
- All integration through PR and CI.
- No modification to `experiments/**` or `structural_engine/isolated_break_detector_v1/**`.
- No automatic branch deletion.
- No bulk workflow consolidation based on filenames alone.
- No duplicate scientific runtime in TypeScript.
- No Engine 2 implementation before Engine 1 freeze.
