# Phase 1 — Break Detector Freeze and Phase 2 — Real Data Transition Scan

**Status:** Freeze candidate; final verification is gated on the dedicated CI run and its SHA-256 artifact.  
**Working branch:** `phase1-detector-freeze-phase2-real-data`  
**B-v7.1 source branch:** `experiment/b7-1-isolated-markov-router`  
**B-v7.1 validation run:** [43963431381](https://github.com/uniqueteamyemen/CHAOS/actions/runs/43963431381)

## 1. Decision

Freeze the B-v7.1 detector lineage behind a single public interface:

`structural_engine/isolated_break_detector_v1/BreakDetectorV1`

The interface supports three modes:

| Mode | Meaning | Public lifecycle |
|---|---|---|
| `fast` | B6.1 Fast_Ref high-sensitivity reference | structural candidates are `PROVISIONAL` |
| `markov_cusum` | B7 innovation-sign conditional Markov CUSUM | detector decisions are `CONFIRMED` |
| `consensus` | Fast_Ref provisional plus one-to-one forward same-direction Markov confirmation | matched events `CONFIRMED`; unmatched candidates remain `PROVISIONAL` |

Transient returns are exposed as `TRANSIENT`; unresolved end-of-series or unconfirmed pending cases are exposed as `UNRESOLVED`.

The adapter standardizes the API and event vocabulary. The two underlying detector implementations are preserved in separate files and their numerical logic is not rewritten:

- `engine_fast_ref.py` — copied from B6.1 `SurgicalFactorEngineB61`.
- `engine_markov_cusum.py` — copied from B7.1 `InnovationSignCusumEngineB7`.

The deterministic auto-router is not part of the frozen public API. Its validation did not establish a general advantage over Markov CUSUM, and its role remains experimental.

## 2. Provenance and commit interpretation

The reference commit is:

`b88a9b71931ca249e3e2de46e3ca93c10f4f39c3`

A direct commit inspection shows that this commit adds only `.github/workflows/b71-trigger-once.txt`, a one-time launch marker. It is therefore the benchmark launch reference, not the source-code commit for the detector implementation.

The actual benchmark and detector source files were recovered from the same source branch:

- `experiments/identity_lab/exp_sequential_break_b7_1_isolated_markov_router/engine_b71.py`
- `experiments/identity_lab/exp_sequential_break_b7_1_isolated_markov_router/benchmark_b71.py`
- `experiments/identity_lab/exp_sequential_break_b61_sarp_sagp_factorial/engine_b61.py`

This distinction is retained to avoid assigning code provenance to a marker-only commit.

## 3. Development history and experiment count

The sequential-break lineage contains **nine named experiment packages** under `experiments/identity_lab/`:

1. `exp_sequential_break` — initial sequential detector.
2. `exp_sequential_break_audit` — audit and lifecycle accounting.
3. `exp_sequential_break_b3_2_retest` — minimal B3.2 retest.
4. `exp_sequential_break_b4_two_point` — B4 two-point variant.
5. `exp_sequential_break_b5_rho_adaptive` — B5 adaptive-rho variant.
6. `exp_sequential_break_b6_spearman_ablation` — B6 Spearman ablation.
7. `exp_sequential_break_b61_sarp_sagp_factorial` — B6.1 factor isolation and Fast_Ref baseline.
8. `exp_sequential_break_b7_innovation_sign_cusum` — B7 innovation-sign CUSUM.
9. `exp_sequential_break_b7_1_isolated_markov_router` — B7.1 isolation, Markov threshold selection, router, and consensus.

These are nine named packages, not nine total executions. The B-v7.1 benchmark then separated development (26M) from validation (27M):

- Development: 8 synthetic regimes, 500 trials per regime, comparing H = 7.0, 7.5, 8.0, and 8.5. The same seeded series are reused across threshold candidates to make the comparison paired.
- Validation: a separate seed family, 2,000 trials per regime = 16,000 independent series; all four systems process the same series.
- The reported 27M validation therefore represents 64,000 system-series evaluations (16,000 series × 4 systems).

The synthetic benchmark is now **closed and frozen as historical evidence**. Do not modify its data generator, thresholds, outputs, or result artifacts to improve agreement with real data. New real-data tests belong in Phase 2 and must remain separate.

## 4. B-v7.1 validation evidence

The following figures are the reported 27M holdout results from the B-v7.1 report.

| Metric | Fast_Ref | Markov CUSUM H=8.5 | Auto-Router | Consensus |
|---|---:|---:|---:|---:|
| Confirmed Structural FPR | 22.05% | **7.05%** | 9.05% | **1.90%** |
| Transient FPR | 3.25% | 5.75% | 4.85% | 3.25% |
| Combined FPR — Null | 15.60% | **7.90%** | 9.85% | **3.75%** |
| Combined FPR — All nonlevel | 23.75% | **9.15%** | 11.30% | **7.15%** |
| Mean Directional Sensitivity | **91.45%** | 84.40% | 84.15% | 63.45% |
| Confirmed Delay (miss penalty 75) | **19.057** | 44.181 | 42.617 | 48.565 |

Interpretation:

- Markov CUSUM reduced confirmed structural FPR from 22.05% to 7.05% and combined FPR across all nonlevel cases from 23.75% to 9.15%, with sensitivity declining from 91.45% to 84.40%.
- Consensus reduced confirmed structural FPR to 1.90%, but sensitivity fell to 63.45%; it missed 1,462 of 4,000 true transitions in the reported validation.
- Auto-Router did not establish general superiority: its combined all-nonlevel FPR was 11.30%, above Markov's 9.15%.
- PENDING opened-event times matched Fast_Ref across all four systems: zero timing mismatches and 678 opens per system. Lifecycle accounting was complete.

**Frozen decision:** Markov CUSUM H=8.5 is the primary candidate for real-data examination; Fast_Ref remains the sensitivity reference; Consensus is a confirmation/staging mode; Auto-Router remains experimental.

H=8.5 is the Markov log-likelihood CUSUM threshold. It is not the Fast_Ref break percentage threshold of 85.0. These constants must not be conflated.

This decision is limited to the eight synthetic regimes in the benchmark. It is not a claim of real-world, cross-domain, or production validity.

## 5. Detector contract

- Input: finite one-dimensional numeric series.
- Minimum length: 52 observations (40 quiet observations plus a 12-observation rolling window).
- Fast_Ref parameters match the B-v7.1 benchmark configuration.
- Markov CUSUM defaults to H=8.5, with the benchmark's finite-sample rho correction and innovation-drain setting.
- The original resolution horizon is 14 observations.
- Consensus matching is one-to-one, forward-only, same-direction, and limited to 35 observations.
- All horizons are measured in input steps. They do not imply calendar units until a data adapter declares the frequency.

## 6. Real historical data available and Phase 2 input decisions

### 6.1 USGS Gulf of Aden

Source contract: `experimental_contracts/EVENT_PATH_SEISMIC_TRANSFER_CONTRACT_V1.json`.

- Fixed bounding box: 10–15° N, 42–52° E.
- Query window: 2000-01-01 through 2024-12-31 UTC.
- Minimum magnitude: 4.5.
- Committed GeoJSON: 408 events; observed event dates span 2000-02-10 through 2024-10-21.
- Planned detector input: 300 UTC calendar-month bins, transformed as `log1p(monthly_event_count)`.

### 6.2 Global USGS earthquakes

Source manifest: `data/raw/usgs_earthquake_m6_5_2000_2024/MANIFEST.json`.

- Query window: 2000-01-01 through 2024-12-31 UTC.
- Minimum magnitude: 6.5.
- Committed raw CSV: 1,141 events.
- Planned detector input: 300 UTC calendar-month bins, transformed as `log1p(monthly_event_count)`.

Monthly event count is an event-activity proxy. It is not magnitude, seismic energy, or a direct measure of physical hazard. No interpolation or forward-fill is used. Empty bins are interpreted as zero events only within the frozen complete-query window.

### 6.3 World Bank financial series

Source: `FS.AST.PRVT.GD.ZS`, domestic credit to private sector (% of GDP), annual 2000–2024.

- 5,123 rows and 233 entity codes.
- Maximum available history per entity: 25 annual observations.
- The frozen detector requires at least 52 observations.

This dataset is therefore excluded from direct execution. It is not padded, interpolated, or silently expanded to meet the detector minimum.

## 7. Real-data scan and quality gates

The dedicated workflow is:

`.github/workflows/phase1-detector-real-data.yml`

It runs the detector contract tests, applies all three modes to both USGS monthly series, records source and code SHA-256 hashes, and uploads a JSON transition scan plus checksums.

The real-data scan must be interpreted with the following constraints:

1. The monthly count transform and its zero-month distribution are recorded.
2. A degenerate quiet-period scale is a data-quality failure, not a reason to tune the detector silently.
3. The 14-step resolution horizon and 35-step consensus window are inherited from synthetic experiments; they are not yet calibrated to monthly observations.
4. Detected historical transitions are candidate signals for review, not predictions of future earthquakes.
5. The scan must preserve provisional, confirmed, transient, and unresolved outcomes, not only the final confirmed events.

## 8. Phase 2 — Predictive Early-Warning Sensing Engine

The predictive layer is a separate system above the frozen detector. It must not rewrite or tune the detector during evaluation.

Recommended architecture:

1. **Source adapters:** enforce provenance, query window, frequency, completeness, and immutable raw records.
2. **Signal builders:** create domain-appropriate regular or event-time representations with explicit transforms and missingness semantics.
3. **Frozen detector:** emit transition candidates and lifecycle events through `BreakDetectorV1`.
4. **Transition ledger:** persist onset, detection, confirmation, direction, strength, transient return, unresolved status, source hashes, and detector version.
5. **Lead/lag evaluator:** test whether a signal precedes a separately defined target event, with event horizons declared before evaluation.
6. **Early-warning scorer:** estimate calibrated risk/lead-time only after adequate positive and negative histories exist.
7. **Governance gate:** require temporal holdouts, false-alarm burden, missed-event cost, stability, and reproducible replay before any operational alert.

The first Phase 2 deliverable is the historical transition ledger and data-adequacy report. A predictive model is not authorized merely because the detector returns a break.

## 9. SHA-256 freeze inventory

The authoritative SHA-256 values are generated by the successful CI run and uploaded as:

`structural_engine/isolated_break_detector_v1/results/SHA256SUMS.txt`

The accompanying real-data output is:

`structural_engine/isolated_break_detector_v1/results/real_data_transition_scan.json`

**Final freeze status remains conditional until the workflow passes and these artifacts are inspected.** The source Git blob IDs are not substitutes for SHA-256 file checksums.

## 10. Files

- `structural_engine/isolated_break_detector_v1/break_detector_v1.py`
- `structural_engine/isolated_break_detector_v1/engine_fast_ref.py`
- `structural_engine/isolated_break_detector_v1/engine_markov_cusum.py`
- `structural_engine/isolated_break_detector_v1/run_real_data.py`
- `structural_engine/isolated_break_detector_v1/tests/test_contract.py`
- `.github/workflows/phase1-detector-real-data.yml`
