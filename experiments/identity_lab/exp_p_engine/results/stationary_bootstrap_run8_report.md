# World Bank residual prewhitening — stationary-bootstrap screen (Run #8)

**Status:** completed, diagnostic only; no production promotion  
**Branch:** `experiment/residual-innovation-whitening-v1`  
**Code commit:** `3d40f45d115c9f8c990ce874a3353cf34d1b3189`  
**GitHub Actions run:** [#8](https://github.com/uniqueteamyemen/CHAOS/actions/runs/43668759009) — success  
**Artifact SHA-256:** `dd7bc7edc8ad8d484e3748b9cbb253d347411f19686a46e1c84b4cb3d1bcc9d4`

## Design

- Source: World Bank indicator `FS.AST.PRVT.GD_ZS`.
- Baseline: rolling Theil–Sen, 8-observation history.
- AR(1) dependence estimated only from pre-evaluation residuals through 2014, then frozen for evaluation from 2015 onward.
- Raw and prewhitened streams were restricted to the same 177 entity/metric series.
- Both streams used identical detector grids, six stationary-bootstrap restart probabilities, 300 replicates, and the same upper-95% series-alarm screen (maximum 5%).
- Contiguous ready segments were retained down to length 2. Block starts were sampled uniformly over valid observations, making segment selection length-weighted. Blocks stopped at a geometric restart or at the source segment end. There was no circular wrap-around or continuation across gaps.

## Dependence result

Frozen panel estimate: `rho = 0.4183`, 95% interval `[0.3206, 0.4692]`.

On the matched held-out cohort, median entity lag-1 correlation changed from **0.4124** (raw residuals) to **0.1174** (prewhitened innovations), a reduction of approximately **71.5%**. The statistic was available for 169 of the 177 matched series because the lag-correlation calculation requires sufficient adjacent pairs.

## Stationary-bootstrap behavior

The theoretical geometric means are (1/p), but source-boundary truncation materially reduced the realised sampled block length. Observed means were:

| p | Theoretical 1/p | Raw observed mean | Innovation observed mean |
|---:|---:|---:|---:|
| 0.10 | 10.00 | 3.203 | 3.193 |
| 0.15 | 6.67 | 2.894 | 2.890 |
| 0.20 | 5.00 | 2.623 | 2.619 |
| 0.25 | 4.00 | 2.399 | 2.401 |
| 0.30 | 3.33 | 2.208 | 2.204 |
| 0.35 | 2.86 | 2.035 | 2.038 |

This is an observed consequence of the finite, fragmented annual series; theoretical (1/p) must not be reported as the realised mean block length for these data.

## 5% series-alarm screen

The screen required the upper 95th percentile of the proportion of series with at least one alarm to be at most 5% at **every** tested p value.

- **CUSUM:** 0/15 candidates passed in either stream. The best (lowest) worst-case upper-95% alarm rate was 17.51% for raw residuals and 16.95% for innovations. Thus the tested CUSUM family is not admissible under this screen.
- **Sign-run / P1:** 9/16 raw candidates and 8/16 innovation candidates passed. Eight settings passed in both streams: (threshold, run length) = (5,4), (6,4), (4,5), (5,5), (6,5), (4,6), (5,6), (6,6).

The screen is an empirical candidate filter on unlabelled source history, not a verified production false-alarm guarantee.

## Matched injection recall

Among the eight P1 settings passing in **both** streams, mean recall differences (innovation minus raw) across those settings were:

| Controlled shift | Mean recall difference |
|---|---:|
| Negative 3 sigma | -0.38 percentage points |
| Negative 6 sigma | -0.08 percentage points |
| Positive 3 sigma | -0.23 percentage points |
| Positive 6 sigma | 0.00 percentage points |

Recall under the strict shared gate was extremely low in both streams. No CUSUM setting passed the screen, so there is no admissible CUSUM recall comparison.

## Decision

1. AR(1) prewhitening **does reduce held-out lag-1 dependence** on this cohort.
2. It **does not demonstrate a recall improvement** under the shared 5% series-alarm screen. P1 is effectively tied with a slight raw-residual advantage for three scenarios; the positive 6-sigma case is tied.
3. The current CUSUM candidate family fails the 5% screen in both streams.
4. Do not promote prewhitening, detector thresholds, or this experiment into the production engine from these results. Keep this branch isolated. The next engineering step is to investigate the residual distribution / detector family and the very low sensitivity of admissible P1 settings, not to relax the alarm gate merely to manufacture recall.

All injected shifts are controlled simulations. The historical World Bank series has no adjudicated anomaly labels; historical alarms are therefore not classified as ground-truth false positives.
