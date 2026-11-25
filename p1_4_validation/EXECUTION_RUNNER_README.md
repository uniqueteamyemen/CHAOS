# run_evidence_pipeline.py

## Purpose
The runner is invoked by the P1.4 Evidence Pipeline workflow:
- `calibrate`: one frozen C1 pilot ID per matrix job, producing AR(p) null-calibration artifacts for all three positions. The matrix covers the 20 C1 pilot IDs in the manifest.
- `postprocess`: aggregate the 20 C1 calibration artifacts, apply only the protocol-registered Threshold-200 extension, generate Track B and Rearm diagnostics, then run the artifact-eligible subset of C1. C2 and C3 are not executed.

## Frozen protocol and cohort frame
- `pilot_protocol.json` and its schema are preserved exactly from `2ae721d` (v1.1.9).
- `selected_cohort_frame` is the 40-series selection frame (20 C1 + 20 C2; 19 cases per series; 760 frame cases). It does not claim that 40 series or 760 cases have been executed.
- The heavy calibration matrix covers the 20 frozen C1 pilot IDs. Pilot includes every C1 series that passes all three per-position FOCuS calibration gates and `n>=150`; no ID is replaced and no fixed ceiling is applied.
- C2 is not inferred to be calibrated from C1 and is not run in this C1-only partial Pilot. C3 remains pending external evidence.

## Scientific controls
- AR order 1..3 is selected on the pre-break prefix only; unstable fits fail closed.
- Each series-position uses 1000 deterministic development and 1000 independent holdout null traces.
- FOCuS, Huber-MAD and Huber-Bartlett receive the same null path per replicate.
- Thresholds and R-FPOP penalties are chosen from development only; holdout is evaluation only.
- Threshold 200 is applied once only to C1 Stratum-106 members with artifact-backed `NOT_CALIBRATABLE` status at position 0.30. IDs and count derive from the actual threshold-90 artifact; no expected count is assumed.
- Rearm overlap uses 1000 independent rearm-phase null streams per eligible series and actual half-open 20-observation intervals; initial calibration remains 40 observations.
- BOCPD is exported as a posterior feature generator; corroboration only replays prefixes through the FOCuS detection index.
- A_FAST and A_CONSENSUS are read-only comparators; no raw series values are written to results.
- `arch==7.2.0` is a Track B dependency. The import is local to Track B; preflight and postprocess pin and verify the version.

## Outputs
Each calibration artifact stores series IDs, candidate hash, pre-break AR metadata, development/holdout score arrays, thresholds, P0/Wilson results, seed ledger hashes and replay command. Postprocess writes threshold200, Track B, Rearm, Pilot manifest/results, decision report and SHA-256 inventory. Pilot counts are computed from eligible C1 artifacts, never from a fixed cap.

## Execution gate
The Evidence Pipeline defaults to `contract_only` (contract gates + runtime preflight). C1 matrix calibration and postprocess occur only when a manual dispatch explicitly selects `full_20_series`.

## Time budget
Hosted job ceilings are enforced. Partial artifacts and explicit PARTIAL/NOT_RUN states are retained rather than claiming completion.