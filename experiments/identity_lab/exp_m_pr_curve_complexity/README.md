# Experiment M — Temporal precision/recall and concurrent UoM stress

Deterministic synthetic labelled stress test. It is not operational validation and does not estimate production accuracy or event prevalence.

## Metrics
- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2PR / (P + R)
- Resolved coverage = (TP + FP) / N
- Ambiguity rate = ambiguous / N

Only uniquely resolved receipt IDs count as predictions. Ambiguous and unmatched outcomes are unresolved false negatives. A prediction is correct only when it equals the known fixture truth.

## Scenarios
1. Seventy labelled shipments across count and weight categories, receipt delays from 0 to 9 days, and 14 hard-negative receipts sharing product, destination and quantity.
2. Concurrent outbound pickings with products across count and weight categories. Sender and receiver quantities use kg/g and unit/box conversions. A wrong-destination decoy tests edge separation.

Approximate matches remain unconfirmed and cannot produce loss claims.

## Run
From experiments/identity_lab:
- python3 -m exp_m_pr_curve_complexity.experiment
- python3 -m unittest exp_m_pr_curve_complexity.test_experiment -v

Outputs: results/precision_recall_curve.json and results/precision_recall_report.md
