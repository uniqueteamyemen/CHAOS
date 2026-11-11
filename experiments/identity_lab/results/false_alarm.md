# Threshold calibration — what the rule buys

Monte Carlo, 4000 replications, 36-month horizon, leak starts month 7.
Rule: *run_len* consecutive residuals, same sign, each beyond *k*·σ. No model, no likelihood.

## A. σ known from a long quiet history

| k | run | false alarm / 36 mo | detect λ=2σ | λ=3σ | λ=5σ | λ=10σ |
|---|---|---|---|---|---|---|
| 2.0 | 2 | 3.43% | 100% | 100% @ m8.0 | 100% @ m8.0 | 100% @ m8.0 |
| 2.0 | 3 | 0.10% | 90% | 100% @ m9.0 | 100% @ m9.0 | 100% @ m9.0 |
| 2.0 | 4 | 0.00% | 63% | 100% @ m10 | 100% @ m10.0 | 100% @ m10.0 |
| 2.5 | 2 | 0.18% | 91% | 100% @ m9.0 | 100% @ m8.0 | 100% @ m8.0 |
| 2.5 | 3 | 0.00% | 46% | 100% @ m11.0 | 100% @ m9.0 | 100% @ m9.0 |
| 2.5 | 4 | 0.00% | 16% | 97% @ m14.0 | 100% @ m10.0 | 100% @ m10.0 |
| 3.0 | 2 | 0.00% | 47% | 100% @ m10.0 | 100% @ m8.0 | 100% @ m8.0 |
| 3.0 | 3 | 0.00% | 9% | 90% @ m15.0 | 100% @ m9.0 | 100% @ m9.0 |
| 3.0 | 4 | 0.00% | 2% | 62% @ m20 | 100% @ m10.0 | 100% @ m10.0 |
| 4.0 | 2 | 0.00% | 1% | 47% @ m20.0 | 100% @ m8.0 | 100% @ m8.0 |
| 4.0 | 3 | 0.00% | 0% | 10% @ m20.0 | 100% @ m9.0 | 100% @ m9.0 |
| 4.0 | 4 | 0.00% | 0% | 2% @ m22 | 100% @ m11 | 100% @ m10.0 |

## B. σ estimated from a 6-month quiet window (the real situation)

| k | run | false alarm / 36 mo | detect λ=3σ | λ=5σ |
|---|---|---|---|---|
| 2.0 | 3 | 13.30% | 97% @ m9 | 100% @ m9.0 |
| 2.0 | 5 | 1.15% | 91% @ m11.0 | 100% @ m11.0 |
| 3.0 | 3 | 4.80% | 80% @ m9.0 | 98% @ m9 |
| 3.0 | 5 | 0.55% | 64% @ m11 | 96% @ m11.0 |

## Reading it

- At k=3, run=3 the false-alarm rate over three years is under 1 in 1000 — the rule is
  conservative, and that is why it can be adopted before the system is stable.
- The price is a floor: leaks below about 3σ are invisible. That floor is arithmetic, not
  a tuning problem, and it is the honest answer to *'what if the leak is small?'*.
- Estimating σ from six points inflates false alarms by an order of magnitude, because a
  short window can land below the true scale. Pool σ across entities, or use a floor.
- Therefore: **the threshold is a purchase, not a discovery.** k and run are chosen by the
  smallest leak you must see and the number of false alarms you can absorb per year.
- Until 20 labelled events exist, do not automate. Label by hand, then calibrate.
