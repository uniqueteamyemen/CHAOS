# B-v7 — Quantized Block Fusion Engine

## Purpose and falsifiable hypothesis

B-v7 replaces the short-sample lag-1 autocorrelation estimate and its derived correction factors with empirical dispersion measured from overlapping block medians in the original quiet segment. It then makes a structural decision using three non-compensatory gates: amplitude, three-sub-epoch positional agreement, and bounded fixed-point consistency.

**Hypothesis:** the empirical quiet-block envelope plus the three simultaneous structural gates will reduce false structural/combined alerts under high serial dependence and heavy-tailed innovations while preserving useful directional sensitivity.

This is a testable hypothesis, not an assumed improvement. The 29 overlapping quiet blocks are highly dependent and are not 29 independent samples. Their empirical 95th percentile is therefore a short-sample guard, not a population-level 95% tolerance bound.

## Isolation

- Branch: `experiment/b7-quantized-block-fusion`
- Parent: B-v6 branch `experiment/b6-spearman-ablation-documented`
- Parent commit: `97220248dea1f359c366540a58d245461556c21e`
- B-v3.1, B-v3.2, B-v4, B-v5 and B-v6 are references only; no prior file is modified or deleted.
- B-v7 has an independent engine, benchmark, tests, README and GitHub Actions workflow.

## Fixed contract

| Parameter | Value |
|---|---:|
| Quiet segment end | 40 |
| Window size | 12 |
| Series length | 140 |
| Change onset (zero-based) | 65 |
| Resolution horizon | 14 |
| Pending point threshold | 3.8 |
| Sub-epoch block-z threshold | 1.25 |
| Quantized directional mean | 1.15 |
| Return-to-baseline threshold | 1.5 |
| Number of overlapping quiet blocks | 29 |

All rates are sequence-level. Combined is the union of any structural event (correct direction, wrong direction or pre-onset), any resolved transient alert, or any unresolved alert.

The lifecycle invariant is enforced inside the engine:
`pending_opened = resolved_structural + resolved_transient + unresolved`.

## Step 1 — quiet-reference calibration

For `quiet = values[:40]`:

- `mu0 = median(quiet)`.
- `sigma0 = max(1.4826 * median(abs(quiet - mu0)), 1e-6)`.
- `sigma_delta0 = max(1.4826 * median(abs(diff(quiet))) / sqrt(2), 1e-6)`.

Every overlapping 12-point block is evaluated, with starts 0 through 28 inclusive:
`m_i = median(quiet[i:i+12])`.

Then:
- `sigma_block = max(1.4826 * median(abs(m_i - mu0)), 1e-6)`.
- `B_sup = percentile_95(abs(m_i - mu0))`, using NumPy's default linear percentile method.

The block medians preserve the observed ordering and tail behavior within the measured quiet sample. Because the blocks overlap heavily, their dependence reduces the effective sample size; B_sup is a conservative empirical envelope and its sampling uncertainty is not removed by the percentile calculation.

## Step 2 — local robust difference-scale adaptation

At each t from 51 through 139:
- `window = values[t-11:t+1]`.
- `hist = values[max(1,t-21):t+1]`.
- `sigma_delta_t = max(1.4826 * median(abs(diff(hist))) / sqrt(2), 1e-6)`.
- `R_var = max(1.0, sigma_delta_t / sigma_delta0)`.

Then multiply each quiet-reference scale by R_var:
- `sigma_t = sigma0 * R_var`.
- `sigma_block_t = sigma_block * R_var`.
- `B_sup_t = B_sup * R_var`.

This is a robust first-difference **scale ratio**, not a classical variance ratio: it is based on a scaled median absolute difference rather than a second moment. It never deflates the quiet-reference scales.

## Step 3 — bounded point scores and pending lifecycle

For all 12 points in the current window:
`z_k = (window[k] - mu0) / sigma_t`.

PENDING opens only if the last three z-scores:
- each have absolute magnitude strictly greater than 3.8;
- all have the same sign;
- the direction is not latched.

The implementation retains B6's short duplicate guard: a PENDING opened within the previous two time steps suppresses another open. This prevents repeated opens on the immediately adjacent evaluations without changing the required three-point criterion.

A pending alert resolves:
- as `RESOLVED_STRUCTURAL` when a same-direction structural break absorbs it within age 0..14;
- as `RESOLVED_TRANSIENT` as soon as an observed value returns within `abs(value-mu0)/sigma0 < 1.5` during age 1..14;
- as `UNRESOLVED_HORIZON_EXPIRED` at age 14 if no qualifying return or structural resolution has occurred;
- as `UNRESOLVED_AT_END` if the series ends before its horizon expires.

Expiry alone is never interpreted as evidence of a transient return. This makes the 14-step horizon terminal and auditable.

## Step 4 — non-compensatory structural gates

Direction is `d = sign(median(window) - mu0)`. A structural break requires all three gate groups simultaneously.

### A. Amplitude gate

Both conditions must hold:
`abs(M_t-mu0) > c_sup * B_sup_t`

and

`abs(M_t-mu0) / sigma_block_t > z_block`.

**Algebraic clarification:** because `B_sup_t = B_sup*R_var` and `sigma_block_t = sigma_block*R_var`, the two inequalities share the same positive multiplier. Together they are equivalent to:
`abs(M_t-mu0) > R_var * max(c_sup*B_sup, z_block*sigma_block)`.

They remain implemented and separately reported as requested, but they are not two statistically independent pieces of evidence.

### B. Three-sub-epoch positional fusion

Split the 12-point window into three non-overlapping groups of four:
- `E1 = window[0:4]`
- `E2 = window[4:8]`
- `E3 = window[8:12]`

All three epoch medians must have the same direction d and each satisfy:
`abs(m_Ej-mu0) / sigma_block_t > 1.25`.

This prevents a large early excursion from compensating for an opposing or weak final sub-epoch.

### C. Quantized level consistency

`q = clip(rint(z), -2, +2)`, where NumPy `rint` is round-to-nearest with ties-to-even. The final gate is:
`d * mean(q) >= 1.15`.

The per-point influence is bounded to [-2,+2]. The structural decision is the strict logical AND of amplitude, sub-epoch and quantized gates.

The direction latch is released when the absolute block-scaled window displacement falls below 0.40. This carries forward the prior engine's hysteresis behavior using the new block scale; it is explicitly documented because the B7 specification did not prescribe a release threshold.

## Development calibration — 10M seeds

The 9 parameter pairs are:
- `c_sup ∈ {1.05, 1.15, 1.25}`
- `z_block ∈ {1.8, 2.0, 2.2}`

Each pair receives the same 500 generated sequences in each of the eight fixed scenarios (4,000 unique development sequences total).

The deterministic selection order is:
1. Minimize the number of FPR gate categories exceeding 5%: worst structural FPR over all six non-level-shift cases; worst Combined FPR over the four pure-null cases; worst pre-onset Combined over the two directional-shift cases.
2. Minimize the sum of percentage-point excess above 5% for those three categories.
3. Maximize mean directional sensitivity over positive and negative shifts.
4. On a complete tie, prefer higher `c_sup`, then higher `z_block`.

Sensitivity is not allowed to compensate for an FPR gate violation in the first two ranking stages. If no pair reaches all three FPR ceilings, the report states that fact; the selected best-effort pair is not thereby accepted.

## Holdout verification — 11M seeds

After the development pair is selected and frozen, exactly two engines receive the same 4,000 holdout sequences:
1. B-v7 with the selected `c_sup` and `z_block`.
2. Frozen `B-v6a_pearson` at threshold 85.0, the threshold selected for B-v6 by its development calibration.

Every rate includes a Wilson 95% interval. Holdout results do not influence parameter selection. Development and holdout seed ranges are recorded and checked for overlap.

## Provenance

- `c_sup` and `z_block`: new B-v7 calibration hypotheses selected only from the 10M development sweep.
- Point, difference and block scales; 29-block envelope; sub-epoch and quantization gates: the B-v7 mathematical specification.
- Three-point pending gate and threshold 3.8: carried forward from B-v6.
- Quiet/window/series/onset/horizon and lifecycle contract: fixed cross-version benchmark contract.
- B-v6a reference implementation and threshold: B-v6 frozen branch at the recorded parent commit.

## Execution

```bash
python -m unittest experiments.identity_lab.exp_sequential_break_b7_quantized_block_fusion.test_b7 -v
python -m experiments.identity_lab.exp_sequential_break_b7_quantized_block_fusion.benchmark_b7 --dev-trials 500 --holdout-trials 500
```

CI success means the experiment ran and produced an auditable artifact. It does not imply that B-v7 passes the performance gates or is approved for merge.
