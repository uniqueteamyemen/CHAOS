# Phase 1 — Break Detector Freeze and Phase 2 — Real Data Transition Scan

**Status:** Phase 1 frozen; Phase 2 historical scan completed and archived.  
**Working branch:** `phase1-detector-freeze-phase2-real-data`  
**B-v7.1 source branch:** `experiment/b7-1-isolated-markov-router`  
**B-v7.1 validation run:** [43963431381](https://github.com/uniqueteamyemen/CHAOS/actions/runs/43963431381)  
**Phase 2 scan run:** [43972264171](https://github.com/uniqueteamyemen/CHAOS/actions/runs/43972264171) — success, 11 tests passed  
**Archived results commit:** `861028fbb7f6ec55912da3cb3e22c1f41e5630ef`

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
- Minimum length to begin evaluation: 52 observations (40 quiet observations plus a 12-observation rolling window).
- Minimum length for the full 14-step resolution horizon: 66 observations.
- Minimum length for the full 35-step Consensus matching window: 87 observations.
- Every result includes sample-adequacy flags; passing the 52-point start gate does not imply that the full lifecycle can resolve.
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
- Monthly representation: 300 UTC bins; 51.67% are empty and the quiet-period scale is degenerate, so its detector outputs are not interpretable.
- Quarterly representation: 100 UTC bins; 17% are empty, the baseline scale is non-degenerate, and no transition was detected by the three modes.
- Event-time representation: 407 inter-event intervals, transformed as `log1p(days_between_consecutive_events)`; this is the useful representation for the first historical transition ledger.

### 6.2 Global USGS earthquakes

Source manifest: `data/raw/usgs_earthquake_m6_5_2000_2024/MANIFEST.json`.

- Query window: 2000-01-01 through 2024-12-31 UTC.
- Minimum magnitude: 6.5.
- Committed raw CSV: 1,141 events.
- Monthly representation: 300 UTC bins; 3.67% are empty, the baseline scale is non-degenerate, and no transition was detected.
- Quarterly representation: 100 UTC bins; no empty quarters, the baseline scale is non-degenerate, and no transition was detected.
- Event-time representation: 1,140 inter-event intervals, transformed as `log1p(days_between_consecutive_events)`.

Monthly and quarterly event counts are event-activity proxies, not magnitude, seismic energy, or direct physical-hazard measures. No interpolation or forward-fill is used. Empty bins are interpreted as zero events only within the frozen complete-query window. Event-time intervals preserve the exact event ordering and timestamps; their detector horizons are measured in event intervals, not calendar months.

### 6.3 World Bank financial series

Source: `FS.AST.PRVT.GD.ZS`, domestic credit to private sector (% of GDP), annual 2000–2024.

- 5,123 rows and 233 entity codes.
- Maximum available history per entity: 25 annual observations.
- The frozen detector requires at least 52 observations.

This dataset is therefore excluded from direct execution. It is not padded, interpolated, or silently expanded to meet the detector minimum.

### 6.4 Catalog-first annual data and missing raw payloads

The committed UN AMA GDP-growth panel contains 12,100 rows and 220 country series. Of these, 179 countries have 54 contiguous annual GDP-growth observations from 1971–2024. All 179 were screened through the three modes, but **zero** have the 66 observations needed for full resolution or the 87 needed for full Consensus confirmation. The scan produced three Fast provisional candidates (Bangladesh, Guinea, Singapore), with no Markov confirmations. They remain screening flags only.

The other annual panels are shorter:

- Macro + EIA complete panel: 139 country entities, 25 annual observations each.
- EIA selected annual long panel: 378 country-variable series, 25 observations each.
- World Bank domestic-credit panel: 233 entities, 25 annual observations each.

These were not padded or interpolated to satisfy detector requirements.

UCDP GED, NOAA GSOM, and WHO daily sources have committed manifests/profiles, but their corresponding raw event/station/daily payloads are absent at the referenced repository paths. They were not run. A catalog entry or manifest is not treated as a committed raw dataset.

## 7. Real-data scan and quality gates

The dedicated workflow is:

`.github/workflows/phase1-detector-real-data.yml`

It runs the detector contract tests, applies all three modes to both USGS monthly series, records source and code SHA-256 hashes, and uploads a JSON transition scan plus checksums.

The real-data scan results are summarized below.

The successful scan produced the following event-time transition ledger:

| Source | Mode | Result |
|---|---|---|
| Gulf of Aden, 407 inter-event intervals | Fast | 3 `PROVISIONAL` candidates |
| Gulf of Aden, 407 inter-event intervals | Markov CUSUM | 2 internally `CONFIRMED` transitions: 2010-11-14 and 2023-06-03 |
| Gulf of Aden, 407 inter-event intervals | Consensus | 1 internally cross-detector-confirmed transition: provisional onset 2009-11-05, confirmation 2010-11-14 after 16 event intervals; 2 remain provisional |
| Global M6.5+, 1,140 inter-event intervals | Markov CUSUM | 1 internally `CONFIRMED` transition: onset 2022-01-14, detection 2022-08-14 |
| Global M6.5+, 1,140 inter-event intervals | Fast / Consensus | No transitions |

For the Gulf series, the Markov-confirmed directions are negative (shorter inter-event intervals). The global Markov-confirmed direction is positive (longer intervals). These describe changes in waiting-time sequences, not earthquake magnitudes or hazard probabilities.

The word `CONFIRMED` here means confirmed by the detector's own Markov threshold rule or by Fast/Markov agreement. It does **not** mean independently validated by a geophysical reference catalog, causal explanation, or successful forecast. The full ledgers, source hashes, per-mode diagnostics, and series values are committed in `structural_engine/isolated_break_detector_v1/results/real_data_transition_scan.json`.

The scan must be interpreted with the following constraints:

1. The monthly and quarterly count distributions, including empty periods, are recorded.
2. The Gulf monthly count baseline is degenerate and is excluded from interpretation.
3. The 14-step resolution horizon and 35-step consensus window are inherited from synthetic experiments; they have not been calibrated to event-time or annual economic series.
4. Detected historical transitions are candidates for independent review, not predictions of future earthquakes.
5. Provisional, confirmed, transient, and unresolved outcomes are preserved in the ledger.

## 8. Phase 2 — Predictive Early-Warning Sensing Engine

The predictive layer is a separate system above the frozen detector. It must not rewrite or tune the detector during evaluation. The detailed Arabic architecture, event-matching contract, acceptance gates, and next execution sequence are in [PREDICTIVE_EARLY_WARNING_ENGINE_PLAN_AR.md](PREDICTIVE_EARLY_WARNING_ENGINE_PLAN_AR.md).

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

The authoritative SHA-256 values were generated by successful CI run 43972264171 and committed to the working branch:

`structural_engine/isolated_break_detector_v1/results/SHA256SUMS.txt`

The accompanying real-data output is:

`structural_engine/isolated_break_detector_v1/results/real_data_transition_scan.json`

The freeze is complete. The B6.1 and B7.1 engine files were verified byte-for-byte identical to their source files before the run. The core package SHA-256 values are:

- `break_detector_v1.py`: `57bfc10fa2098479c04db17b3d07ff449da957e49818c5ec3b0f5c43fda52678`
- `engine_fast_ref.py`: `34482667f93a3b1a6acf1eeeeed1dc714bfaa1b674c97c8773a92e886be46e16`
- `engine_markov_cusum.py`: `0402eb6e98a4a20065f9cf33b6d90c9a29dd263383e9a782c6fc9d67b53eb843`
- `run_real_data.py`: `636bfcf6f8c17ee2b9ee3c67a5de345046ec81473d8fc806d8a618f3cce4adba`

The full inventory, including both test files and every input data/manifest/contract file, is in `SHA256SUMS.txt`. The source Git blob IDs are not substitutes for SHA-256 file checksums.

## 10. Files

- `structural_engine/isolated_break_detector_v1/break_detector_v1.py`
- `structural_engine/isolated_break_detector_v1/engine_fast_ref.py`
- `structural_engine/isolated_break_detector_v1/engine_markov_cusum.py`
- `structural_engine/isolated_break_detector_v1/run_real_data.py`
- `structural_engine/isolated_break_detector_v1/tests/test_contract.py`
- `structural_engine/isolated_break_detector_v1/tests/test_real_data_adapter.py`
- `.github/workflows/phase1-detector-real-data.yml`
