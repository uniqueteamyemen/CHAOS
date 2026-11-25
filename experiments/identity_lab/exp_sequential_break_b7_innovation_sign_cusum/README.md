# B-v7 — Robust Innovation Sign-Likelihood CUSUM

## Objective

B-v6.2 showed that sign-flip counts do not discriminate null from variance-jump regimes. B-v6.3 reduced structural false alarms through repeated confirmation of overlapping 12-point windows, but paid in sensitivity and delay. Adjacent windows reuse 11 of 12 observations; a hold counter on those windows does not create independent evidence.

B-v7 changes how structural evidence is built: it derives a one-step AR innovation, retains only its sign, and accumulates a sequential log-likelihood ratio. This makes a single extreme value contribute no more than one sign observation.

## Isolation and comparator

The branch starts directly from corrected B-v6.1 commit `1f3f369f9c0b67344954d288c99d923d5b9b5c22`. Only new B-v7 files and its dedicated workflow are added. No B-v6.1, B-v6a, or B-v6.3 reference file is modified.

The paired comparator is the original B-v6.1 `D1_P1_G0` engine with fixed structural threshold `85.0`.

## Structural innovation

Let `m` be the quiet-period median and `rho_raw` the raw Pearson lag-1 estimate from the 40-point quiet segment.

The existing context scale and transient D/PENDING gate continue using the raw clipped estimate `clip(rho_raw,0,0.88)`.

The new structural channel has a development ablation:

- **Raw:** `rho_struct = clip(rho_raw,0,0.88)`.
- **Corrected:** `rho_struct = clip((rho_raw + 1/n)/(1 - 3/n),0,0.88)`, with `n=40`.

This is an approximate first-order AR(1) finite-sample bias correction, not a universally unbiased estimator. Its incremental value is tested rather than presumed.

The one-step structural innovation is:

`v_t = x_t - m - rho_struct * (x_(t-1) - m)`.

The structural channel starts at the first observation after quiet calibration. The inherited D/PENDING channel retains the original B-v6.1 12-point scan start, so the transient opportunity timing is not moved earlier by this change.

## Sequential sign-likelihood evidence

The null sign probability is `p0=0.5`; the directional alternative is fixed at `p1=0.65` before development. For a sign matching a given direction, the log-likelihood increment is:

`log(2*p1) = log(1.30)`.

For the opposite sign:

`log(2*(1-p1)) = log(0.70)`.

Each directional score is a reflected CUSUM: `C=max(0,C+LLR)`. These increments have negative expected drift under the symmetric null and positive expected drift when the target sign occurs with probability 0.65. This avoids the zero-mean reflected-random-walk issue in the initial prototype. A zero innovation sign contributes no evidence.

After a direction is latched, only the opposite-direction CUSUM accumulates. When the existing `abs(window_shift_z)<0.40` return condition is met while latched, the latch and both scores reset. An unlatched accumulator is not cleared merely because the current median remains near baseline; this permits sequential evidence to accumulate before a new level occupies half of the 12-point window.

The model assumes that sign innovations are approximately independent under the null after AR whitening. Heavy tails are less problematic for sign magnitude, but residual serial dependence, estimation error in `rho`, and distributional asymmetry remain testable risks.

## Development and holdout protocol

Development seed block: `24,000,000`; 500 sequences per each of the eight canonical cases. Development crosses:

- CUSUM threshold `h in {6.0,6.5,7.0,7.5,8.0}`.
- Structural rho treatment: raw or finite-sample corrected.

That gives 10 candidate configurations, 4,000 common generated series, and 40,000 candidate evaluations.

Only after the 24M winner is fixed does holdout seed block `25,000,000` run. It compares exactly two engines on the same 2,000 generated sequences per case: B-v6.1 D1_P1_G0 at 85.0 and the single selected B-v7 configuration. This is 16,000 generated series and 32,000 engine evaluations. The seed blocks are disjoint.

Selection eligibility requires all four point-estimate FPR ceilings <=5% (Structural and Transient across nonlevel cases, Combined across pure-null cases, and pre-onset Combined across both level shifts), mean directional sensitivity >=93%, and complete PENDING accounting. If none qualifies, the rule minimizes failed FPR gates, total excess above 5, then maximizes sensitivity, minimizes censored delay, prefers the higher CUSUM threshold, and finally prefers the simpler raw-rho variant. The same final tie-break applies when eligible configurations are otherwise equal.

Missed detections receive a censored delay penalty equal to the remaining 75 observations to the end of the series. This prevents median delay from excluding misses.

## Required report

The JSON includes per-case Structural FPR/sensitivity, Transient FPR, Combined FPR, pre-onset Combined, Wilson 95% intervals, correct-detection delay, censored delay, missed-detection rate, PENDING accounting, event totals, CUSUM instrumentation, and paired outcome tables with exact two-sided McNemar tests.

Holdout approval requires all Wilson upper-bound gates, sensitivity >=93%, and lifecycle accounting. Development selection and CI success alone do not authorize integration or deployment.
