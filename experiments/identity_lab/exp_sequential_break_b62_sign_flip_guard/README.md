# B-v6.2 — D1/P1 with Conditional Sign-Flip Guard

## Question
Can D1/P1 retain its transient-alert improvement and sensitivity while recovering some structural false-positive reduction through a conditional scale guard?

B-v6.2 replaces the global G factor with a local guard activated only when a 12-point window is highly directionally oscillatory.

## Fixed configurations
Control: B-v6.1 D1_P1_G0. Candidate: same D/P settings plus sign-flip guard threshold 8. Holdout also includes frozen B6a Pearson. No B6 or B6.1 source files are modified.

## Exact sign-flip count
A 12-point window contains 11 first differences and at most 10 adjacent sign comparisons:
1. Calculate first differences.
2. Take their signs and remove zero signs.
3. Count adjacent unequal signs.

The guard activates at 8 or more sign flips. This is a conservative fixed cutoff, above the approximate Gaussian AR(1) expected counts in the generator's positive-rho regimes (about 5.5 at rho 0.7 and 6.1 at rho 0.3). These are theoretical reference means, not calibrated false-alarm quantiles. Heavy tails, finite windows, and estimated rho must be measured.

## Conditional scale
Only when the guard activates:
context_scale_guarded = context_scale_D1P1G0 * (1 + 0.25*rho).
Otherwise the context scale is unchanged. No other D/P, score, threshold, lifecycle, or reversion rule changes.

## Limitation being tested
A persistent level shift is a step, not a monotone ramp. It has one large onset increment followed by differences of noise around the new level. Thus real shifts can still produce many sign flips. Sign flips are also magnitude-blind: tiny jitter and large alternating movements count equally. The experiment records guard activation frequency by scenario and directly measures sensitivity.

## Paired experiment
- Same eight B-v6 scenarios and generator.
- 18M development: 500 sequences per case, control and candidate (8,000 evaluations).
- 19M validation: 500 sequences per case, B6a, D1/P1G0, and D1/P1SF8 (12,000 evaluations).
- Seed formula: seed_base + case_index*10000 + trial_index; 18M/19M blocks are disjoint.
- Threshold 8 is frozen before 19M. Holdout does not tune it.
- Wilson 95% intervals are reported for each rate; Combined includes structural, transient and unresolved alerts.

## Acceptance gates
All six non-level structural and transient FPRs <=5%; all four pure-null Combined FPRs <=5%; both level-shift pre-onset Combined rates <=5%; mean directional sensitivity >=93%; exact lifecycle accounting; and Wilson upper bounds <=5% for each FPR category. The report also compares candidate sensitivity against D1/P1G0 on identical 19M series.

CI success means the experiment completed, not that the candidate passed. No merge or production approval is implied.
