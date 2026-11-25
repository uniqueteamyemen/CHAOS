# Event-Path Economic Target Contract v1

This run tests the frozen economic rule with a raw future deterioration target.

- Source: `/home/ubuntu/CHAOS/catalog_first/readiness_gate/ANNUAL_PANEL_RAW_WDI_IMF_UCDP_EIA_2000_2024.csv`
- Feature at t: `wdi__NY.GDP.MKTP.KD.ZG` with high-growth rule >4.0%
- Raw target at t+3: future GDP growth <= origin growth −2 percentage points
- Same general frozen engine; min_support=2; unsupported paths abstain

| Model | Accuracy | N | Coverage/rate |
|---|---:|---:|---:|
| path_model | 0.5419 | 203 | coverage=0.1939 |
| majority_baseline | 0.5123 | 203 | coverage=0.1939 |
| abstention | — | 844 | rate=0.8061 |
| target | — | 1047 | rate=0.0000 |

## Status

`provisional_economic_raw_target_only`

This is predictive evidence only; no causal or operational promotion is permitted.
