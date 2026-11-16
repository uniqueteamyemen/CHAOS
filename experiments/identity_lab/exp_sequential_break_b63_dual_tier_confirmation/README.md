# B-v6.3 — Dual-Tier Structural Confirmation

## Immutable base

This experiment starts directly from corrected B-v6.1 commit `1f3f369f9c0b67344954d288c99d923d5b9b5c22`. The B-v6.1 source, B-v6a source, and earlier experiment files are not modified. Only a new B-v6.3 package and its dedicated workflow are added.

The candidate base is `D1_P1_G0`:

- Raw Pearson lag-1 `rho`, clipped to `[0.0, 0.88]`; no `G` scale multiplier and no Sign-Flip Guard.
- `D=1` remains limited to the transient PENDING path: initiating raw point `abs(z0)>3.8`, then both normalized innovations `abs(u)>2.8` in the initiating point's direction.
- `P=1` remains an independent structural AND gate: `dominant_persistence >= 0.75`, with `persistence_z=1.45`, 12-point window and `winsor_cap=1.8`.
- Structural scoring, transient resolution and PENDING lifecycle inherit B-v6.1 behavior except for the dual-tier structural announcement rule.

## Sole structural change

Let `break_pct` be the unchanged B-v6 structural score.

1. **Fast path:** announce at current time `t` when `break_pct >= fast_thresh` and `dominant_persistence >= 0.75`.
2. **Confirmed path:** when `83.0 <= break_pct < fast_thresh` and persistence is at least `0.75`, start a candidate in the current direction. The initial sample starts the candidate at counter zero. Each subsequent consecutive sample must remain in the same borderline band, pass the same persistence floor, and retain the same direction. Announce at the sample that completes `hold_steps` additional consecutive steps.
3. **Reset:** a score below `83.0`, a persistence-floor failure, or a direction flip before confirmation clears the counter and produces no alert for the rejected candidate. A flip sample rejects the old candidate and does not also seed a new opposite-direction candidate in the same step.
4. **Latch:** after announcement, latch the announced direction. Reset the latch only when `abs(window_shift_z) < 0.40`, following B-v6.1.

The four and only four development configurations are `(88,2)`, `(88,3)`, `(90,2)`, and `(90,3)`. `hold_steps` counts additional consecutive steps after the initial borderline sample.

## Pre-registered selection rule

Development uses only seed block 20M. A configuration is eligible only if all four point-estimate ceilings pass: worst Structural FPR across six non-level cases <=5%; worst Transient FPR across six non-level cases <=5%; worst Combined FPR across four pure-null cases <=5%; and worst pre-onset Combined rate across both level-shift cases <=5%. It must also reach mean directional sensitivity >=93% and complete the PENDING lifecycle equation for every evaluated sequence.

If eligible: maximize mean directional sensitivity, then minimize pooled median correct-detection delay, then prefer the higher fast threshold and longer hold duration. If none is eligible: minimize the number of failed FPR ceilings, then sum of percentage-point excess above 5, then maximize sensitivity, minimize delay, and prefer the more conservative configuration. Lexical order is the final tie-break. A best-effort selection is not acceptance.

## Paired holdout

Only after the 20M winner is fixed, seed block 21M evaluates exactly two engines on each same generated series:

- B-v6.1 `D1_P1_G0` reference at fixed `break_percent_thresh=85.0`.
- The single 20M-selected B-v6.3 candidate.

Each of the eight canonical cases receives 500 sequences. Development: 4,000 generated series x 4 configurations = 16,000 evaluations. Holdout: 4,000 generated series x 2 configurations = 8,000 evaluations. Seed blocks are disjoint. No 21M values participate in selection.

## Metrics and invariants

The complete JSON records per-case Structural FPR / directional sensitivity, Transient FPR, Combined FPR, pre-onset Combined, median correct-detection delay, Wilson 95% intervals, event totals, hold-counter instrumentation, and lifecycle totals.

For every evaluated sequence and every aggregate case, enforce:

`pending_opened == pending_resolved_structural + pending_resolved_transient + pending_unresolved`

Here `pending_resolved_structural` counts transient PENDING alerts absorbed by structural announcements; it is distinct from the count of structural-break events. Combined alert rate is the union of structural, transient and unresolved alerts.

CI runs unit tests, smoke tests on separate non-official seeds, then the official 20M/21M experiment, and uploads the full JSON. CI success alone does not authorize integration or adoption.
