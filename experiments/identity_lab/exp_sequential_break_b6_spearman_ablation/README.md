# B-v6 — Spearman vs Pearson Ablation & Documented Calibration

## Objective

B-v6 isolates the quiet-window lag-1 correlation estimator while holding the transient gate and structural detector configuration constant. It compares:

- **B-v5_ref** — frozen B-v5, including the half-strength small-sample rho adjustment and adaptive 2/3-point pending gate, at threshold 85.0.
- **B-v6a_pearson** — raw lag-1 Pearson rho, clipped to [0.0, 0.88] without upward adjustment, with a fixed three-point same-sign pending gate.
- **B-v6b_spearman** — the same B-v6 engine settings as B-v6a, changing only the quiet-window lag-1 estimator to the specified rank-correlation calculation.

The primary ablation question is whether rank-based lag-1 dependence estimation changes false alarms or directional sensitivity relative to raw Pearson when the pending gate and structural parameters are otherwise identical.

## Experimental hypothesis

The rank-based estimator may be less sensitive to extreme quiet-window observations than Pearson, especially under Student-t3 innovations. This is a hypothesis, not an expected outcome or an acceptance claim. Both methods are evaluated on identical generated sequences and the same selected structural threshold.

## Parameter provenance

| Parameter / rule | Value | Provenance and interpretation |
|---|---:|---|
| `winsor_cap` | 1.8 | Retained from B-v4. Its historical comparative holdout replay recorded a 0.6% structural false-alarm rate in `t3_r0.3_null` and 90.7% mean directional sensitivity. |
| `persistence_z_threshold` | 1.45 | Retained from B-v4 alongside `winsor_cap=1.8`; not retuned in B-v6. |
| `anomaly_z_thresh` | 3.8 | Inherited from B-v5. On paired 7M sequences, transient-alert rate in `t3_r0.7_null` was 22.2% for B-v4 and 9.0% for B-v5 (−13.2 percentage points). |
| Fixed pending gate | 3 adjacent same-sign points | B-v5 used three points only when its adjusted rho exceeded 0.50. B-v6 tests that condition at every correlation level. The B-v4/B-v5 change was not a single-factor ablation: rho adjustment changed at the same time. |
| Kendall inflation removed | none | B-v5's half-strength adjustment coincided with mean sensitivity falling from 91.6% (B-v4) to 84.1% (B-v5) on the paired 7M data (−7.5 points). B-v5 actually estimated Pearson lag-1 correlation and added a heuristic adjustment; it did not calculate Kendall's tau. B-v6 removes that upward adjustment in both estimators. |
| `break_percent_thresh` baseline | 85.0 | Inherited B-v4/B-v5 reference threshold. |
| `break_percent_thresh` candidate | 83.5 | **`calibration_hypothesis` only.** Tested alongside 85.0 in development; not forced and never selected from holdout results. |

**Provenance correction:** B-v5's 13.2-point transient-alert reduction coincided with a 7.5-point decrease in mean directional sensitivity against B-v4 (91.6% to 84.1%) on the same 7M generated sequences. Therefore the assertion that the reduction occurred *without* sensitivity loss is unsupported. The 13.2-point delta is an observed paired-configuration difference, not proof that the three-point gate alone caused it.

Historical evidence:
- [B-v4 implementation](https://github.com/uniqueteamyemen/CHAOS/tree/experiment/b4-two-point-transient-winsor18)
- [B-v4 paired comparison workflow](https://github.com/uniqueteamyemen/CHAOS/actions/runs/43743029830)
- [B-v5 implementation](https://github.com/uniqueteamyemen/CHAOS/tree/experiment/b5-rho-adaptive-transient-kendall)
- [B-v5 paired comparison workflow](https://github.com/uniqueteamyemen/CHAOS/actions/runs/43744520316)

## Mathematical specification

Let `quiet = values[:quiet_end]`, `quiet_end=40`, `baseline_center=median(quiet)`, and `q_norm=(quiet-baseline_center)/baseline_spread`.

**B-v6a Pearson:**

```python
rho_raw = float(np.corrcoef(q_norm[:-1], q_norm[1:])[0, 1])
rho = float(np.clip(0.0 if not np.isfinite(rho_raw) else rho_raw, 0.0, 0.88))
```

**B-v6b specified Spearman-style ordinal ranks:**

```python
r0 = np.argsort(np.argsort(quiet[:-1])).astype(float)
r1 = np.argsort(np.argsort(quiet[1:])).astype(float)
rho_raw = float(np.corrcoef(r0, r1)[0, 1]) if len(r0) > 2 else 0.0
rho = float(np.clip(0.0 if not np.isfinite(rho_raw) else rho_raw, 0.0, 0.88))
```

The scalar coefficient is matrix element `[0, 1]`; `np.corrcoef(r0, r1)` alone returns a 2×2 matrix, not a scalar. The implementation indexes the scalar and guards constant inputs. The requested double-`argsort` transform assigns ordinal ranks; ties receive deterministic ordinal positions rather than average ranks. B-v6b therefore tests this specified rank transform, not tie-averaged `scipy.stats.spearmanr`.

Both B-v6 configurations use:
- `rho = clip(rho_raw, 0.0, 0.88)`, with no small-sample/Kendall-named adjustment.
- `anomaly_z_thresh=3.8`.
- Three latest `z_point_raw` values, all with absolute magnitude strictly greater than 3.8 and identical sign, to open PENDING.
- `winsor_cap=1.8`, `persistence_z_threshold=1.45`.
- `resolution_horizon=14` and an observed return condition `abs(return_z) < 1.5`, measured against fixed quiet-period baseline spread.
- Lifecycle equality: `pending_opened == resolved_structural + resolved_transient + unresolved`.

## Fixed sequence and scenario design

- `quiet_end=40`, `window_size=12`, `series_length=140`, `onset=65` (zero-based).
- Eight fixed scenarios cover Gaussian and Student-t3 innovations, rho 0.3 and 0.7, pure null, variance jump, and positive/negative level shifts.
- 500 sequences per scenario in development and 500 per scenario in holdout.

## Paired calibration and holdout protocol

### Stage 1 — development sweep (seed base 8,000,000)

Run both B-v6 estimators at both thresholds: Pearson at 85.0 and 83.5; Spearman at 85.0 and 83.5. Every configuration receives the same 500 generated sequences in each of the eight cases. Select one shared threshold for both estimators using development results only.

**Pre-registered selection rule:**

1. A threshold is eligible only if both Pearson and Spearman configurations meet all three point-estimate FPR ceilings: worst structural FPR across null/variance-jump cases ≤5%; worst Combined FPR across pure-null cases ≤5%; worst pre-onset Combined rate across level-shift cases ≤5%. Both also need mean directional sensitivity ≥93%.
2. If one or more thresholds are eligible, select the eligible threshold with the higher average sensitivity across Pearson and Spearman. On an exact tie, prefer 85.0.
3. If neither is eligible, choose a best-effort threshold lexicographically by minimizing (a) total failed point-estimate FPR ceilings across both methods, (b) sum of FPR percentage-point excess above 5 across those method/metric pairs, then (c) maximizing pooled directional sensitivity. On a complete tie, prefer 85.0. The report must state that no threshold met all development gates.

The fallback is deterministic calibration, not relaxation of the 5% acceptance budget.

### Stage 2 — pristine holdout (seed base 9,000,000)

After the development-selected threshold is frozen, evaluate exactly three configurations on the same holdout sequences:
- B-v5_ref at original threshold 85.0.
- B-v6a_pearson at the selected B-v6 threshold.
- B-v6b_spearman at the same selected B-v6 threshold.

500 holdout sequences are generated for each of the eight cases. Holdout results do not alter the selected threshold or any parameter. Every displayed rate includes a Wilson 95% confidence interval. The JSON includes all eight case tables, aggregate metrics, lifecycle checks, and point-estimate / Wilson-upper-bound gates.

Seed formula: `seed_base + case_index * 10,000 + trial_index`. The 8M and 9M intervals are checked for overlap and recorded.

## Combined-alert definition

For each sequence, Combined is the union of any structural alert (including wrong-direction or pre-onset), any resolved transient alert, or any unresolved alert. This prevents reductions in one alert class from hiding the total alert burden.

## Execution

```bash
python -m unittest experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.test_b6 -v
python -m experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.benchmark_b6 --dev-trials 500 --holdout-trials 500
```

The GitHub Actions workflow runs both commands and uploads the JSON report as an artifact. B-v6 is experimental; passing CI alone does not authorize adoption or merge.
