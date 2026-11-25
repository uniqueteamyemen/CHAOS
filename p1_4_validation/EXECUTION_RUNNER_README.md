# run_evidence_pipeline.py

## Purpose
The P1.4 runner has a narrow operational scope:
- `calibrate`: calibrate the 20 frozen C1 pilot IDs using the Threshold-90 FOCuS grid and the post-quiet Huber comparators at positions 0.30, 0.50 and 0.70.
- `postprocess`: aggregate calibration artifacts, measure the detector's 40/20 rearm behavior, and run the C1 detector-comparator Pilot on every candidate that passes the actual frozen calibration gates.

## Frozen protocol and cohort frame
- `pilot_protocol.json`, its schema and `cohort_manifest.json` are preserved exactly from `2ae721d` (v1.1.9).
- `selected_cohort_frame` is the 40-series selection frame (20 C1 + 20 C2; 19 cases per series; 760 frame cases). It is not an execution count.
- The calibration matrix covers the 20 frozen C1 IDs. Pilot includes every C1 series that passes all three per-position Threshold-90 calibration gates and `n>=150`; no ID is replaced and no fixed cap is applied.
- C2 is not inferred to be calibrated from C1 and is not executed in this C1-only Pilot. C3 remains pending external evidence.

## Operational controls
- AR order 1..3 is selected on the pre-break prefix only; unstable fits fail closed.
- Each series-position uses 1000 deterministic development and 1000 independent holdout null traces.
- FOCuS, Post-Quiet Huber-MAD and Post-Quiet Huber-Bartlett receive the same null path per replicate.
- Thresholds and R-FPOP penalties are chosen from development only; holdout is evaluation only.
- A series that cannot calibrate within the frozen Threshold-90 grid is marked `NOT_CALIBRATABLE` and excluded from the Pilot; no post-hoc threshold fallback is introduced.
- Rearm validation uses 1000 independent rearm-phase null streams per eligible series and half-open 20-observation intervals; initial calibration remains 40 observations.
- A_FAST and A_CONSENSUS are read-only comparators. No raw series values are written to result artifacts.

## Explicit exclusions
- The pre-registered Threshold-200 research extension remains intact in the frozen protocol but is not executed by this engine Pilot.
- Track B (GARCH, ARCH-LM, lag-12 and trend diagnostics) has been removed from the runner and workflow. It does not gate calibration or detector comparison.

## Outputs
Calibration artifacts include series IDs, candidate hash, pre-break AR metadata, development/holdout score arrays, frozen thresholds, P0/Wilson results, seed-ledger hashes and replay commands. Postprocess writes rearm overlap, Pilot manifest/results, an engine Pilot decision and SHA-256 inventory. Counts are derived from actual eligible artifacts.

## Execution gate
The Evidence Pipeline defaults to `contract_only` (contract gates + runtime preflight). The C1 matrix and postprocess run only when a manual dispatch explicitly selects `full_20_series`.
