# ERP Reconciliation A/B/C Comparative Benchmark

**Classification:** synthetic adversarial benchmark; not production validation.

- Seeds: 40
- Cases per seed: 18
- Total shipment cases: 720
- Shared loss threshold: 0.5

| Metric | A — legacy | B — hardened | C — hybrid |
|---|---:|---:|---:|
| exact_precision | 0.666667 | 1.0 | 1.0 |
| exact_recall | 0.857143 | 0.857143 | 1.0 |
| loss_precision | 1.0 | 1.0 | 1.0 |
| loss_recall | 1.0 | 1.0 | 1.0 |
| candidate_precision | None | 1.0 | 1.0 |
| candidate_recall | None | 1.0 | 1.0 |
| false_confirmations | 120 | 0 | 0 |
| false_loss_claims | 0 | 0 | 0 |
| missed_exact | 40 | 40 | 0 |
| missed_losses | 0 | 0 | 0 |
| candidate_tp | None | 240 | 240 |
| candidate_fp | None | 0 | 0 |
| candidate_fn | None | 0 | 0 |
| mean_runtime_ms | 0.1307 | 0.9365 | 1.4126 |
| p95_runtime_ms | 0.157 | 1.6977 | 2.5228 |

## Interpretation guardrails

- Exact-match scoring is evaluated against source_picking_id ground truth.
- A is the historical algorithm with a schema-only adapter for its old transfer-key convention.
- B and C receive identical canonical records and UoM metadata.
- Candidate discovery and confirmed reconciliation are scored separately.
- Loss classification uses the same declared 0.5-unit ground-truth threshold.
- Runtime is informational and measured in a shared Python process; it is not a deployment benchmark.
- Synthetic performance cannot establish production readiness or real-world accuracy.
