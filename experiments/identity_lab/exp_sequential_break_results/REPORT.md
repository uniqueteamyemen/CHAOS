# ImprovedSequentialBreakEngine — six-scenario benchmark result

- Branch: experiment/sequential-break-engine-v1
- Workflow: https://github.com/uniqueteamyemen/CHAOS/actions/runs/43731744193
- Tested commit: e3ad70d813038542ec1cdf196fb2ef93d857ef81
- Workflow conclusion: success
- 500 independent paths per scenario × 6 scenarios = 3,000 paths per method
- Generator: N=140, AR(1) rho=0.70, onset index 65
- Parameters unchanged: quiet_end=40, anomaly_z_thresh=3.2, confirm_window=12, break_percent_thresh=76.0
- Artifact SHA-256: sha256:77b20ea623aa32d397fa4b55fd9355d3edbb7d0db7bdd38fde3b79d7af201352

## Aggregate comparison

| Metric | ImprovedSequentialBreakEngine | AG-CUSUM |
|---|---:|---:|
| Worst null sequence false-alarm rate | 54.8% | 24.8% |
| Minimum shift directional sensitivity | 95.8% | 100.0% |
| Worst pre-onset false-alarm rate | 10.2% | 3.8% |
| Operational detection delay | 7.9–8.3 periods | 13.8–14.2 periods |

## Detailed null cases

| Scenario | New engine false sequences | Rate | Wilson 95% |
|---|---:|---:|---:|
| Gaussian AR(1) | 171/500 | 34.2% | 30.18%–38.46% |
| Gaussian AR(1), variance jump | 203/500 | 40.6% | 36.38%–44.96% |
| Student-t3 AR(1) | 226/500 | 45.2% | 40.89%–49.58% |
| Student-t3 AR(1), variance jump | 274/500 | 54.8% | 50.42%–59.11% |

## Shift cases

| Scenario | Pre-onset false rate | Sensitivity | Mean operational delay | Median delay |
|---|---:|---:|---:|---:|
| Positive +3σ | 6.8% | 96.8% | 7.90 | 7 |
| Negative -3σ | 10.2% | 95.8% | 8.34 | 7 |

## Timing review

The code scans the entire 12-point window beginning at t. A decision associated with onset_time=t is not available until t+11. It therefore uses 11 future observations relative to the reported onset time. In the two shift scenarios, the reported onset estimate was backdated by an average of 3.57 and 3.24 periods, respectively. The actual evidence availability still lagged the true shift by an average of 7.90 and 8.34 periods.

The "zero-step delay" claim is not supported by this implementation. The detector can retrospectively locate an earlier start point, but it cannot issue the alert before the confirmation window has been observed.

## Decision

The detector is faster than AG-CUSUM in this benchmark, but its false-alarm rates are substantially worse in every null condition, and pre-onset alerts are higher in both shift cases. The Student-t3 plus variance-jump false-alarm rate is 54.8%.

The break percentage is a weighted heuristic score, not a probability. The result does not support the claimed sub-5% false-alarm performance.

**Decision: preserve as an isolated research challenger, do not promote or merge into the P-engine. No threshold tuning was performed.**
