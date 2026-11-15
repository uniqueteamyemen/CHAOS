# P-engine independent robustness holdout

This stage is deliberately separated from the G threshold sweep. It reads the
G artifact, selects candidate settings using only the training report, then
evaluates the selected settings on disjoint random seeds and new distributions.

## Holdout conditions

- Gaussian AR(1), phi=0.60: stable null and variance-only jump null.
- Student-t(3) AR(1), phi=0.60: stable null and variance-only jump null.
- Gaussian AR(1): positive and negative 3-sigma level steps.
- Student-t(3) AR(1): positive and negative 3-sigma level steps.
- Student-t(3) AR(1): positive and negative 3-sigma steps coincident with a gradual variance transition.

Each condition uses 500 fresh trials. Evaluation scores CUSUM raw evidence only;
P1 alerts and fused-event notifications are excluded.

## Selection and promotion

Training selects the best (k,h) for C, E and F under the 5% worst-case rate
across the three G null scenarios. It also requires a 75% minimum sensitivity
across the four G shift scenarios for holdout eligibility. E/F may be retained
as diagnostic challengers even when their training sensitivity is below the
promotion floor. C at its fixed default (0.5, 8.5) remains the control.

A holdout candidate passes only when every holdout null scenario has a CUSUM
false-alarm rate <=5% and every holdout shift scenario has directional
sensitivity >=75%. No threshold is changed after inspecting holdout results.


## Stage I — archived EIA weekly real-series replay

A separate replay reads the five already-committed EIA HTML snapshots under experiments/identity_lab/exp_c_eia/raw/. The workflow verifies their recorded SHA-256 sums before execution. It does not request fresh data from EIA.

Candidate arms are A production, C default, C threshold selected from G, D adaptive high-noise P1, E reset-at-transition with capped scale, and F reset-at-transition with uncapped scale. The report separates raw P1 hits, raw CUSUM hits, fused event counts, and timing proximity to declared historical dates. Historical date alignment is descriptive, not ground truth.

Positive and negative 3-sigma/6-sigma level shifts are injected into copies of the residual stream, never into source data. Detection is measured after 130 weeks of adaptation. No false-alarm-rate or production-approval claim is inferred from unlabeled EIA history.


## Gemini Self-Normalized M-CUSUM candidate comparison

The submitted M0 function is implemented verbatim at the equation/default
level (Huber clip=2.0, rho estimate from the quiet 40, adaptive k,
25-observation partial-sum window, v-floor=0.85, h=7.5, min-run=3).
The workflow compares M0 with three component ablations and the prior CHAOS
C/E/F candidates using fresh seeds disjoint from G and H.

The M0 result intentionally retains the submitted no-reset/no-cooldown
behavior; repeated raw alerts are reported. The run also reports the
ablation contributions separately. A candidate is not promoted unless every
null regime is <=5% and every shifted regime retains >=75% directional
sensitivity. This is a test of the supplied implementation, not a claim that
its moving-window denominator equals the Shao-Zhang self-normalized statistic.


## Stage K — Asymmetry-Guarded Bounded CUSUM (AG-CUSUM)

Gemini's revision is reproduced with its supplied defaults: psi=1.8, gamma=0.90,
k=0.50, h=9.5, dwell=4, directional ratio=3.5, cooldown=6, quiet_end=40.
The screen uses the exact H scenario generators and seed range for a paired
comparison against H's C/E/F baseline results. No parameters are tuned here.

The report measures sequence-level null alerts, pre-onset alerts, sensitivity,
detection delay, raw alert multiplicity, and scale diagnostics.

Mathematical note: for stationary AR(1),
Var(X_t-X_(t-1)) = 2 sigma^2 (1-rho), so SD(diff)/sqrt(2) estimates
sigma*sqrt(1-rho), not the marginal sigma. Positive autocorrelation therefore
makes the proposed scale smaller than marginal sigma. The test reports this
effect instead of assuming that differencing removes autocorrelation.


## Stage K2 — untouched-seed confirmation of AG-CUSUM

The candidate parameters were frozen at the values submitted by Gemini and
tested on a new seed range, 7,300,000, with 1,000 trials per scenario.
No tuning was performed after the K paired screen.

The confirmation repeated the near-threshold failure:
- Worst null sequence false-alarm rate: 6.0%.
- Worst 95% Wilson upper bound: 7.65%.
- Minimum directional sensitivity: 95.8%.
- Minimum sensitivity lower 95% bound: 94.37%.
- Worst pre-onset false-alarm rate: 1.0%.

AG-CUSUM remains a promising experimental candidate but does not pass the
strict 5% null gate. It is not approved for production; the parameters remain
frozen for this confirmation result.
