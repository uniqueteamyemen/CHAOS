# Gulf of Aden Seismic Transfer Test v1

This is a frozen transfer test after the prediction-mechanics repair; no economic-model tuning was performed.

- Source: `/home/ubuntu/CHAOS/data/raw/seismic_gulf_of_aden_v1/usgs_gulf_of_aden_query.geojson`
- Fixed region: 10–15°N, 42–52°E
- Fixed period: 2000-01-01 through 2024-12-31 UTC
- Fixed threshold: magnitude ≥ 4.5
- Events retained: **408**
- Window width: **3**; train size: **8**
- Path support: **2**; unsupported paths abstain

## Metrics

| Model | Accuracy | N | Coverage/rate |
|---|---:|---:|---:|
| path_model | 0.3271 | 269 | coverage=0.6725 |
| majority_baseline | 0.2454 | 269 | coverage=0.6725 |
| persistence_baseline | 0.0855 | 269 | coverage=0.6725 |
| abstention | — | 131 | rate=0.3275 |

## Status: `provisional_transfer_only`

The transfer result is descriptive and predictive only; it does not revise the economic judgment.

No seismic result is used to alter the economic Event-Path definition, window width, train size, or model selection.
