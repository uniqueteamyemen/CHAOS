# run_evidence_pipeline.py

## Purpose
The script is invoked only by the evidence-first GitHub Actions workflow. It has two entry phases:
- `calibrate`: one exact C1 pilot ID per matrix job, producing AR(p) null-calibration artifacts for all three positions.
- `postprocess`: aggregate those artifacts, apply the preregistered threshold-200 extension, generate Track B and Rearm diagnostics, and run the maximum 15-series/285-case C1 Pilot if calibration gates permit.

## Scientific controls
- AR order 1..3 is selected on the pre-break prefix only; unstable fits fail closed.
- Each series-position uses 1000 deterministic development and 1000 independent holdout null traces.
- FOCuS, Huber-MAD and Huber-Bartlett receive the same null path per replicate.
- Thresholds and R-FPOP penalties are chosen from development only; holdout is evaluation only.
- Threshold 200 is applied once to artifact-identified threshold-90 failures; there is no 500 grid.
- Rearm overlap uses 1000 independent rearm-phase null streams per eligible series and actual half-open 20-observation intervals.
- Pilot IDs are chosen from the frozen C1 20-series list only after per-position FOCuS calibration and n>=150; at most 15 IDs and 19 conditions each.
- BOCPD is exported as a posterior feature generator; corroboration only replays prefixes through the FOCuS detection index.
- A_FAST and A_CONSENSUS are read-only comparators; no raw series values are written to result artifacts.

## Outputs
Each calibration artifact stores series IDs, candidate hash, pre-break AR metadata, development/holdout score arrays, frozen thresholds, P0/Wilson results, seed ledger hashes and replay command. Postprocessing writes threshold200_extension_results, track_b_diagnostics, rearm_overlap_results, pilot_run_manifest, pilot_results, p2_c_decision_report and SHA-256 inventory.

## Time budget
Each hosted Actions job has a 355-minute hard ceiling. The runner stops before that platform limit. The protocol retains its 24-hour overall budget; a job that reaches its hosted ceiling emits partial artifacts and explicit PARTIAL/NOT_RUN states rather than claiming completion.
