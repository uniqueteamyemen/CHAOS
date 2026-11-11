# Experiment C — the stock identity on real official data

US crude oil, EIA Weekly Petroleum Status Report: five separate published surveys,
**617 weeks** (2015-01-09 → 2026-10-30).

`stock_t − stock_(t−1) = 7 × (production + imports − exports − refinery_inputs) + adjustment`

Zero parameters. Quiet window declared **2015-01-02 → 2016-12-30**, detection starts 2017.

## The residual is not centred

| quantity | value |
|---|---|
| σ (MAD, quiet window) | 195.6 kb/d |
| **bias** (median, quiet window) | **-333.1 kb/d** |
| median residual, all weeks | -421.0 kb/d |
| mean absolute residual | 575.1 kb/d |
| lag-1 autocorrelation | 0.22 |
| weeks below −3σ | 42% |

The four surveys do not balance, and they do not balance in the same direction every week.
A persistent offset of this size is not a break — it is the identity telling you it is
**missing a term**. The raw rule cannot tell the difference, so it fires on the offset.

## Largest departures

| week | residual (kb/d) |
|---|---|
| 2023-07-21 | -2416.3 |
| 2022-10-21 | -2266.6 |
| 2023-02-24 | -2266.6 |
| 2022-12-09 | -2258.3 |
| 2023-03-10 | -2230.4 |

## Same rule, raw and bias-corrected

Detection window: 513 weeks ≈ 9.9 years.

| k | run | raw alarms | per year | bias-corrected | per year |
|---|---|---|---|---|---|
| 2.0 | 2 | 119 | 12.1 | 62 | 6.3 |
| 2.0 | 3 | 65 | 6.6 | 31 | 3.1 |
| 2.0 | 4 | 34 | 3.4 | 12 | 1.2 |
| 2.0 | 6 | 18 | 1.8 | 4 | 0.4 |
| 2.0 | 8 | 5 | 0.5 | 1 | 0.1 |
| 3.0 | 2 | 74 | 7.5 | 29 | 2.9 |
| 3.0 | 3 | 37 | 3.8 | 11 | 1.1 |
| 3.0 | 4 | 18 | 1.8 | 3 | 0.3 |
| 3.0 | 6 | 6 | 0.6 | 1 | 0.1 |
| 3.0 | 8 | 1 | 0.1 | 0 | 0.0 |
| 4.0 | 2 | 36 | 3.6 | 15 | 1.5 |
| 4.0 | 3 | 20 | 2.0 | 7 | 0.7 |
| 4.0 | 4 | 8 | 0.8 | 2 | 0.2 |
| 4.0 | 6 | 2 | 0.2 | 1 | 0.1 |
| 4.0 | 8 | 1 | 0.1 | 0 | 0.0 |
| 5.0 | 2 | 13 | 1.3 | 9 | 0.9 |
| 5.0 | 3 | 5 | 0.5 | 4 | 0.4 |
| 5.0 | 4 | 1 | 0.1 | 1 | 0.1 |
| 5.0 | 6 | 0 | 0.0 | 1 | 0.1 |
| 5.0 | 8 | 0 | 0.0 | 0 | 0.0 |

Simulated i.i.d. noise said this rule fires almost never. On real data it fires **37 times**.
Removing the declared bias takes it to **11**, and a run of six to **1**.

## What this forces

1. **A bias term is unavoidable** in any real identity, because official series are produced by
   different agencies with different timing. But a bias term is a parameter by another name.
   The only safe way to hold it is to freeze it from the declared quiet window and version it:
   changing the bias changes the identity, and must be recorded as a new identity version,
   otherwise every leak can be hidden by nudging the offset.
2. **Autocorrelation (ρ₁ ≈ 0.22) is secondary here, not the main culprit.** The main culprit is
   the level. My earlier claim that a 3σ/3-run rule is 'near-silent' held only for i.i.d. noise —
   it was never true for real series, and the simulated table should not have been read as if it were.
3. **Attribution remains impossible on this dataset.** No second independent recording of the same
   quantity exists, and EIA publishes no standalone 'unaccounted for' series to compare against.
   All events are emitted as `unresolved` — the honest state, and the same wall as before.
