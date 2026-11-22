# CHAOS P2 — Clean Stage Closure V1

**Base:** \`main-phase2@b838eb48b2040bf358fc216e1e004311edfc30e8\`  
**Integration branch:** \`p2/clean-stage-closure-v1\`  
**State:** candidate for merge after CI; not a release or operational approval.

## 1. Scope closed by this change set

1. **Cross-series/volatility discovery:** remains frozen on \`discovery/cross-series-volatility-v1\`; candidate-only and descriptive, with no PR and no P2 dependency.
2. **USGS catalog integrity:** selectively ported into P2.2 with raw hash retention, feature-level validation, quarantine, duplicate accounting, conflict handling, and magnitude provenance. This is ingestion integrity only.
3. **Markov diagnostics:** the read-only P2.2.2 manifest audit is ported with separate reporting for \`rho_raw\`, legacy \`rho_used\`, structural \`rho_cusum_used\`, and the structural correction flag. It does not change detector behavior.
4. **Null eligibility:** detector execution is unconditional. Null selection follows it:
   - level-stationary block bootstrap when level ADF/KPSS checks pass;
   - trend-residual block bootstrap only when trend ADF/KPSS and residual checks pass;
   - integrated-increment block bootstrap only when first differences pass ADF/KPSS;
   - unresolved series keep detector output but receive no null estimate.
5. **Pre-merge gate:** PRs run contract tests, immutable-archive checks, Markov diagnostic tests, and a bounded live USGS integrity query. The 999-replicate full historical run remains outside PRs.

## 2. Seismic boundary

The seismic cohort remains descriptive-only for P2.2 null calibration. Generic scalar stationary or integrated bootstraps are not accepted as a seismic point-process null. The canonical `real_data_stress_pipeline/contracts/seismic_null_model_contract_v1.json` and its Arabic design specification require magnitude-completeness analysis, magnitude-scale handling, a full-catalog ETAS-family null, an inhomogeneous-Poisson benchmark, a separate declustering-sensitivity track, fitted-model simulation calibration, and predeclared injected-break power tests.

This closure does **not** certify seismic FPR, earthquake prediction, or operational warning.

## 3. Preserved invariants

- \`structural_engine/isolated_break_detector_v1/**\` remains untouched.
- \`experiments/**\` remains untouched.
- No detector constants, thresholds, or lifecycle rules are changed.
- The completed cross-series branch is not merged or modified.
- Conditional bootstrap alarm probability is not renamed as operational FPR.
- Source snapshots are hashed; catalog accounting must close exactly.

## 4. Acceptance conditions

Merge only if all unit/contract tests pass, the bounded USGS PR gate passes, immutable archive checks pass, and the resulting main commit completes the full historical stress run. Manifests must retain the selected null family and distinguish null-ineligible series.

A failed or unavailable live-source check is a blocking status, not an automatic skip.
