# Gemini Self-Normalized M-CUSUM — comparison result

- Workflow run: https://github.com/uniqueteamyemen/CHAOS/actions/runs/43728694339
- Source commit: `209b6be617d6b29781b83d6bd7618d2a3bd3122c`
- Trials: 500 per condition × 10 conditions
- Seed base: `2900000` (disjoint from G/H)
- Artifact SHA-256: `sha256:c53f42924177d939004c65d0b8fa20c209ee051172cfd6132d4d816f2d54a15b`

## Aggregate result

| Candidate | Worst null false-alarm rate | Minimum shift sensitivity | Mean shift sensitivity | 5% / 75% gates |
|---|---:|---:|---:|---|
| Gemini-M0 | 87.0% | 99.2% | 99.8% | FAIL |
| M-no-SN | 98.0% | 100.0% | 100.0% | FAIL |
| M-no-rho | 96.6% | 99.8% | 100.0% | FAIL |
| M-Huber-only | 99.8% | 100.0% | 100.0% | FAIL |
| C-default | 98.2% | 100.0% | 100.0% | FAIL |
| C-h24 | 45.8% | 99.2% | 99.8% | FAIL |
| E-h24 | 24.0% | 90.2% | 96.9% | FAIL |
| F-h16 | 33.2% | 89.4% | 97.0% | FAIL |

## Gemini M0 by scenario

| Scenario | False-alarm rate / pre-onset false rate | Sensitivity | 95% CI | Mean delay | Raw alerts per sequence |
|---|---:|---:|---:|---:|---:|
| gaussian_ar1_null | 67.4% | — | 63.2%–71.4% | — | 6.65 |
| gaussian_ar1_variance_jump_null | 84.6% | — | 81.2%–87.5% | — | 6.02 |
| student_t3_ar1_null | 72.6% | — | 68.5%–76.3% | — | 6.83 |
| student_t3_ar1_variance_jump_null | 87.0% | — | 83.8%–89.7% | — | 7.64 |
| gaussian_ar1_positive_step3 | pre 24.8% | 100.0% | 99.2%–100.0% | 4.92 | 69.69 |
| gaussian_ar1_negative_step3 | pre 22.6% | 100.0% | 99.2%–100.0% | 5.10 | 69.43 |
| student_t3_ar1_positive_step3 | pre 25.0% | 100.0% | 99.2%–100.0% | 5.03 | 69.90 |
| student_t3_ar1_negative_step3 | pre 27.6% | 100.0% | 99.2%–100.0% | 5.17 | 69.59 |
| student_t3_ar1_transition_positive_step3 | pre 32.0% | 99.2% | 98.0%–99.7% | 7.78 | 47.37 |
| student_t3_ar1_transition_negative_step3 | pre 30.8% | 99.4% | 98.2%–99.8% | 6.88 | 49.26 |

## Component ablations

The submitted complete M0 had the lowest worst-case null rate among the four M-CUSUM variants, but still failed materially. Removing self-normalization increased the worst null rate to 98.0%; removing rho-based k adjustment increased it to 96.6%; Huber-only reached 99.8%. None passed the gates.

## Diagnostics and decision

- M0 estimated median rho across scenarios: 0.528–0.560.
- Effective k: 0.640–0.655.
- Median self-normalizer v: 0.850–1.126.
- The exact submitted M0 produced a 67.4%–87.0% sequence-level false-alarm rate across the four null regimes.
- It produced 47–70 raw alerts per shifted sequence; this is consistent with the missing reset/cooldown in the submitted function.
- Detection sensitivity remained high (minimum 99.2%), but pre-onset false alarms were 22.6%–32.0% in shifted scenarios.
- Decision: reject M0 as submitted; preserve it as an experimental baseline. Do not promote to P-engine or merge into production.
