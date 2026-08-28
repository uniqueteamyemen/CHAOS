# Event-Path Prototype v1 — Execution Report

This is a predictive prototype, not causal evidence.

- Source: `/home/ubuntu/CHAOS/catalog_first/readiness_gate/ANNUAL_PANEL_RAW_WDI_IMF_2000_2024.csv`
- Value column: `wdi__NY.GDP.MKTP.KD.ZG`
- Window width: `3`
- Chronological train size: `8`
- Events: **4780**; states: **4780**; transitions: **4586**; windows: **4392**; predictions: **3229**
- Unsupported paths abstain; no fallback is included in path_model.

## Rolling OOS metrics

| Model | Accuracy | N | Coverage/rate |
|---|---:|---:|---:|
| path_model | 0.6028 | 1523 | coverage=0.4717 |
| majority_baseline | 0.4859 | 1523 | coverage=0.4717 |
| persistence_baseline | 0.3454 | 1523 | coverage=0.4717 |
| abstention | — | 1706 | rate=0.5283 |

## Interpretation

The path model is marked **provisional** because this first pass uses one annual economic series and has not yet undergone independent-domain replication, null-search correction, or external event-native validation. Accuracy is reported only against chronological out-of-sample outcomes; it must not be described as causal evidence or as a deployable signal.
