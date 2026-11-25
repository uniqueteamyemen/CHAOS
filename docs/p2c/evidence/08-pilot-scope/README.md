# Pilot Scope — C1 Detector Comparator

## Objective
Run a bounded operational comparator Pilot on the frozen C1 candidates after the primary Threshold-90 calibration has produced real eligibility evidence.

## Selection frame vs execution
The frozen `selected_cohort_frame` records 40 selected series (20 C1 + 20 C2) and 19 cases per series (one original plus 18 injections). The 40/760 values describe the selection frame, not executed work.

The active pipeline calibrates the 20 frozen C1 candidates. The Pilot executes on every C1 candidate that passes all three actual Threshold-90 FOCuS calibration gates and the `n>=150` minimum. No candidate ID is replaced and no fixed 15/285 execution ceiling is applied. Candidates that fail the primary calibration remain `NOT_CALIBRATABLE`; Threshold 200 is not used as a fallback. C2 and C3 are not executed in this C1-only path.

## Detector comparison
The Pilot records FOCuS, Post-Quiet Huber variants, BOCPD prefix corroboration, R-FPOP retrospective segmentation, and read-only A_FAST/A_CONSENSUS references. Rearm overlap is measured separately to check the detector's 40/20 reset behavior.

## Explicit exclusions
Threshold-200 extension and Track B diagnostics remain documented in frozen protocol/history but are not run by this operational Pilot.
