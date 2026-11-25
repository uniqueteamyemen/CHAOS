# Threshold 200 — Historical Protocol Extension (Not Executed)

## Status
`NOT_EXECUTED_ENGINE_SCOPE`

The pre-registered Threshold-200 extension remains recorded in the frozen P1.4 protocol v1.1.9 at `2ae721d`. The protocol and schema are not rewritten.

## Engineering decision
The operational P1.4 Pilot uses only thresholds selected from the frozen Threshold-90 development calibration grid. A series that does not calibrate within that grid is marked `NOT_CALIBRATABLE` and excluded from the detector Pilot. No post-hoc Threshold-200 fallback is applied.

This prevents a supplementary extension from changing cohort eligibility or obscuring detector behavior under the primary calibration contract. No Threshold-200 execution artifact is expected from this runner.
