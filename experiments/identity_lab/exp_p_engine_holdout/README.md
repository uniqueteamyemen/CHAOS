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
