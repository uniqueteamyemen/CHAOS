# Experiment G2 — is the mirror gap a constant? Calibrate on H1, test on H2

Real Eurostat Comext data, 2024. The per-edge median gap from January–June is frozen as an
offset; July–December is then tested with that offset removed. Nothing was tuned on H2.

| quantity | value |
|---|---|
| edges calibrated | 12 |
| holdout edge-months | 72 |
| median abs gap, raw | **6.5%** |
| median abs gap, after frozen offset | **3.3%** |
| share above 5%, raw | 60% |
| share above 5%, after offset | 38% |
| spread of the frozen offsets across edges | 36.1% |

## Reading

Removing a frozen per-edge offset halves the median gap (6.5% → 3.3%) and cuts the share of edge-months above tolerance from 60% to 38%.

The offset is not one number: it spreads over 36% across the twelve edges,
which is what a mixed valuation and attribution difference looks like. A single global
offset would hide a real loss inside a definitional gap.

So a frozen bias makes the identity usable for **detecting change**, not for proving equality:
the residual answers 'did this corridor move away from its own norm', which is the only
question an edge detector can honestly answer on data of this kind.

## The rule this establishes

> A bias may be frozen only per edge, only from a declared window, and only as an identity
> version. A single global offset would hide a real loss inside a definitional gap.
