# Event-Path — Third Political Path v1

This run applies the domain-neutral frozen predictor to the native annual UCDP state-based conflict series.

- Source: `/home/ubuntu/CHAOS/experiments/macro_plus_eia_energy/ama_ucdp_cross_domain_v1/AMA_UCDP_CROSS_DOMAIN_REPLAY_ROWS.csv`
- Value: `state_based_conflict`
- Entities: **163**
- Events: **5474**; states: **5474**; transitions: **5311**; windows: **5148**; OOS predictions: **4170**
- Unsupported paths abstain; no persistence fallback is included in path_model.

## Metrics

| Model | Accuracy | N | Coverage/rate |
|---|---:|---:|---:|
| path_model | 0.9815 | 3515 | coverage=0.8429 |
| majority_baseline | 0.4615 | 3515 | coverage=0.8429 |
| persistence_baseline | 0.0000 | 3515 | coverage=0.8429 |
| abstention | — | 655 | rate=0.1571 |

## Status

`provisional_political_transfer_only`

This is a predictive diagnostic, not causal evidence and not an operational promotion.
