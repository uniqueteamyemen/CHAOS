# ImprovedSequentialBreakEngine — isolated experiment

Branch: experiment/sequential-break-engine-v1

This branch reproduces the supplied detector without tuning:
- quiet_end=40
- anomaly_z_thresh=3.2
- confirm_window=12
- break_percent_thresh=76.0

The benchmark uses the six supplied scenario classes, 500 paths per scenario,
length 140, AR(1) rho=0.70, onset index 65, and the supplied seed formula.
AG-CUSUM with its frozen defaults is run on the same paths as a paired baseline.

## Timing semantics

The detector evaluates the complete window series[t:t+12]. Therefore it cannot
know whether the break at onset_time=t is valid until index t+11 arrives.
Reports include both retrospective onset estimate and evidence-available time.
A timestamp backdated to t is not a zero-latency operational alert.

## Scoring

- Null scenarios: sequence-level false-break rate, total false events per
  sequence, and average breaks per sequence.
- Shift scenarios: pre-onset alerts by actual evidence-available time,
  directionally correct sensitivity, wrong-direction rate, actual operational
  delay, and retrospective onset error.
- Transient anomalies are counted separately.

Break percentage is a heuristic score, not a calibrated probability. No
threshold adjustment or production promotion occurs in this stage.
