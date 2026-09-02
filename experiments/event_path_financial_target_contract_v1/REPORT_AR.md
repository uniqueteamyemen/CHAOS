# Event-Path Financial Target Contract v1

Financial third-domain run using the World Bank domestic-credit series and the same frozen target-aware engine.

- Events: **5123**; entities: **233**; target rows: **2571**
- Feature: domestic credit to private sector (% of GDP) at t
- Raw target: ratio at t+3 is lower than at t
- Same engine: window_width=3, train_size=8, min_support=2; unsupported paths abstain

| Model | Accuracy | N | Coverage/rate |
|---|---:|---:|---:|
| path_model | 0.5175 | 572 | coverage=0.2225 |
| majority_baseline | 0.5455 | 572 | coverage=0.2225 |
| abstention | — | 1999 | rate=0.7775 |
| target | — | 2571 | rate=0.0000 |

## Status

`provisional_financial_transfer_only`

Predictive diagnostic only; no causal or operational promotion.
