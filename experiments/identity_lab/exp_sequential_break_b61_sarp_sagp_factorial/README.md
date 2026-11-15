# B-v6.1 — Surgical SARP/SAGP Factorial Experiment

## Objective

This branch isolates three proposed changes on top of the frozen B-v6a Pearson engine. It does not edit any B-v6 source file and does not modify B-v6a defaults.

The three binary factors are evaluated as a complete 2^3 factorial:

| Factor | Off | On |
|---|---|---|
| D — Normalized Innovation Drain | Original B-v6a three-point same-sign raw-z gate | First point remains abs(z)>3.8; the next two normalized AR(1) innovations must each exceed 2.8 in the first point's direction |
| P — Non-compensatory persistence floor | Original weighted break score only | dominant_persistence >= 0.75 is an independent AND condition |
| G — Heuristic scale guard | Original context scale | Multiply context_scale by 1 + 0.25*rho |

## Frozen B-v6a invariants

All eight development variants retain Pearson lag-1 rho_raw, clipping to [0.0, 0.88], winsor cap 1.8, persistence z threshold 1.45, anomaly threshold 3.8, break threshold 85.0, quiet window 40, rolling window 12, resolution horizon 14, observed-return rule, and exact pending lifecycle accounting.

With D=P=G=off, B-v6.1 must be event-for-event equivalent to the frozen B-v6a engine. The test suite checks parity against the original B-v6 implementation.

## Mathematical specification

### D — Normalized Innovation Drain (transient PENDING channel only)

For the latest three raw point scores z0,z1,z2, D=1 requires only the initiating point to cross the original 3.8 threshold: abs(z0)>3.8. The subsequent two values are judged by their innovations; z1 and z2 are not independently required to exceed 3.8:

u_i = (z_i - rho*z_(i-1)) / sqrt(max(1-rho^2, 0.15)), for i=1,2.

Both abs(u1) and abs(u2) must be strictly greater than 2.8 and both must have the sign of z0. This gate controls only whether a transient-channel PENDING record opens. It does not gate, delay, or suppress the structural scan.

The denominator follows the supplied experiment specification; it is a model-based normalization under an AR(1)-style approximation, not a claim that the B-v6 rolling robust z-scores are exactly stationary unit-variance AR(1) observations. Diagnostics report the number of eligible raw-gate opportunities and the number rejected by D. This instrumentation distinguishes fewer false alerts from broad suppression of alert opportunities.

### P — Non-compensatory persistence floor

The existing B-v6 score is unchanged:

break_pct = 100 * (0.45*dominant_persistence + 0.55*separation_score).

When P is enabled, structural acceptance additionally requires dominant_persistence = max(full_pos, full_neg) >= 0.75. The numerator and denominator remain those in B-v6: qualifying same-direction points beyond persistence_z_threshold=1.45, divided by the 12-point window.

### G — Heuristic Scale Guard

When G is enabled only the context scale changes:

context_scale_guarded = context_scale_B6a * (1 + 0.25*rho).

The factor is explicitly a heuristic sensitivity factor, not an estimator or confidence bound for the sampling uncertainty of Pearson rho.

## Paired experiment design

- Eight canonical B-v6 scenarios, unchanged generator and scenario definitions.
- Development seed base: 12,000,000, 500 sequences per scenario.
- Holdout seed base: 13,000,000, 500 sequences per scenario.
- Each development sequence is evaluated by all eight factorial configurations.
- Development: 4,000 generated series x 8 configurations = 32,000 evaluations.
- Holdout: 4,000 generated series x frozen B-v6a reference and the single development-selected B-v6.1 configuration = 8,000 evaluations.
- 13M is not read or evaluated until selection on 12M is frozen. No threshold or factor is tuned on 13M.
- The same generated series is used for every configuration within each stage; seed ranges are recorded and checked for disjointness.

## Selection rule (development only)

A configuration is eligible only if all four point-estimate ceilings pass: worst structural FPR across all six non-level cases <=5%; worst transient FPR across all six non-level cases <=5%; worst Combined FPR across four pure-null cases <=5%; and worst pre-onset Combined rate across both level-shift cases <=5%. It must also reach mean directional sensitivity >=93% and complete lifecycle accounting.

If any configurations are eligible, select the one with highest mean directional sensitivity, then fewer active factors, then lexical configuration order. If none is eligible, select deterministically by: fewest failed FPR ceilings; smallest sum of percentage-point excess above 5 across the four FPR categories; highest directional sensitivity; fewest active factors; lexical order. A best-effort selection is not an acceptance.

## Metrics and anti-masking controls

The JSON records per-case structural, transient, unresolved and Combined rates with Wilson 95% intervals; pre-onset Combined rates; correct-direction sensitivity and detection delay; lifecycle totals; and instrumentation counts for raw PENDING opportunities rejected by D and structural score candidates rejected by P. Combined remains the union of structural, transient and unresolved alerts. Gate rejections are reported separately and are not silently reclassified as resolved transient events.

The final holdout includes the frozen B-v6a reference, for a paired comparator, and only the selected B-v6.1 candidate. Every FPR category has a Wilson-upper-bound <=5% gate in addition to the sensitivity and lifecycle gates.

## Execution

Run the B61 unit tests, then the smoke mode (small non-official seed blocks), then the official 12M/13M run. CI follows that order and uploads the complete JSON. This is an isolated experiment; CI success alone does not authorize a merge or production adoption.
