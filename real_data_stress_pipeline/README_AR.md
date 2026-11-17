# Automated Historical Sensor Stress Pipeline

**Phase:** P2.2 — Automated Historical Sensor Stress Validation  
**Branch:** `main-phase2`  
**Frozen detector:** `structural_engine/isolated_break_detector_v1/`  
**Detector math:** unchanged; no tuning or edits are performed by this pipeline.

## What it does

1. Retrieves the official World Bank Pink Sheet workbook in memory, hashes it, and does not publish the raw workbook or numeric Pink Sheet inputs until workbook-specific redistribution terms are verified.
2. Queries World Bank GEM (Data API source 15) for a declared set of indicators. GEM is a **secondary cohort** with a minimum 87-point gate; its published 1990–2023 coverage cannot meet the strict >500 monthly-point cohort. Annual/quarterly data are not relabelled as monthly.
3. Retrieves five geographically separated USGS ComCat belts from 1980 through 2024, retaining exact GeoJSON responses and query parameters in the private workflow artifact.
4. Builds monthly commodity log-return series, secondary monthly seismic-count series, and seismic inter-event intervals without filling gaps.
5. Applies G0, screens stationarity with ADF and KPSS (G1), and runs the three frozen detector modes: `fast`, `markov_cusum`, and `consensus`.
6. Estimates empirical null alarm rates using the Politis–Romano Stationary Bootstrap only for series that pass G1; failed and untested series remain in the ledger with the reason for skipping the null resampling. The bootstrap result is a conditional sequence-level null diagnostic, not a substitute for a domain-specific earthquake point-process null.
7. Measures structural alarms per decade and matches detector events to a predeclared historical macro-shock anchor contract. A positive lead means the detector event was available before the anchor date; a post-anchor detection is a lag, not a warning.
8. Emits an Arabic report, a JSON manifest, SHA-256 inventory, and raw source snapshots.

## Quality gates

- Pink Sheet primary cohort: at least 502 contiguous positive monthly prices (therefore at least 501 adjacent log returns), valid chronology, and non-degenerate robust scale.
- GEM secondary cohort: at least 87 contiguous, actual monthly observations and non-degenerate robust scale; reported separately from the Pink Sheet cohort.
- Seismic inter-event cohort: at least 87 consecutive event intervals, valid time ordering, and non-degenerate robust scale.
- Monthly seismic event counts are a separate secondary representation and are never substituted for inter-event intervals.
- G1 passes only when ADF rejects a unit root at 5% and KPSS does not reject level stationarity at 5%; this is a preliminary screen, not proof of strict stationarity.
- Stationary Block-Bootstrap is skipped when G1 does not pass. The G1 result itself and p-values are retained per series.
- G1: ADF p-value < 0.05 and KPSS p-value ≥ 0.05. This is a preliminary screen, not proof of strict stationarity.
- Stationary Block-Bootstrap: 999 replicates by default; mean block length 12 months for market returns and 25 event intervals for seismic series.
- No missing-value imputation, interpolation, or artificial extension is permitted.
- Failed sources and rejected series remain visible in the report with explicit reasons.
- Config files under `config/` are the sole source of runtime cohort, source, window, and bootstrap defaults; the report and manifest retain the exact config objects.

## Historical shock anchors

The contract at `shock_event_contract.json` fixes four external anchor dates before the detector is run:

- 2008-09-15 — Lehman Brothers bankruptcy / global financial-crisis anchor.
- 2014-06-01 — start-of-decline anchor for the 2014 oil-price shock.
- 2020-03-11 — WHO pandemic characterization anchor.
- 2022-02-24 — start-of-war anchor for the 2022 commodity-supply shock.

These are global calendar anchors, not assertions that every commodity or seismic belt experienced its own shock on that exact date. The report distinguishes pre-anchor lead, same-window detection, and post-anchor lag, and does not claim causal attribution.

## Reproducibility

Run from repository root:

```bash
python -m pip install -r real_data_stress_pipeline/requirements.txt
python -m unittest discover -s real_data_stress_pipeline/tests -v
python -m real_data_stress_pipeline.run_pipeline
```

Configuration is available through environment variables:

- `STRESS_BOOTSTRAP_REPLICATES` (default 199; set to 999 for a higher-resolution follow-up)
- `STRESS_BOOTSTRAP_MEAN_BLOCK_MONTHS` (default 12)
- `STRESS_MIN_COMMODITY_POINTS` (default 501 log-return observations; at least 502 contiguous monthly prices)
- `STRESS_USGS_MIN_MAGNITUDE` (default 4.5)

USGS and GEM API raw responses are written to `artifacts/real_data_stress/raw/` and attached to the private workflow artifact; they are not committed to the source tree. The Pink Sheet workbook remains in memory only while its workbook-specific redistribution terms are unverified; only its SHA-256 and derived detector event audit are recorded. Numeric Pink Sheet observations are redacted from the public normalized CSV. GitHub Actions uploads permitted raw responses, report, manifest, and SHA-256 inventory as a versioned artifact. The generated Arabic report is also committed at repository root.

## Interpretation limits

The ADF/KPSS pair is a conservative preliminary screen; passing it does not prove strict stationarity. The bootstrap asks how often the frozen detector alarms on stationary-block-resampled versions of each eligible observed sequence. It does not remove every possible historical regime effect and does not establish a causal mechanism. Bootstrap outputs are not computed for G1-failing series. The report distinguishes unassociated alarms outside the predeclared shock-anchor windows from scientifically established false positives. For earthquake catalogs, event-time interval resampling is only a conditional diagnostic; a defensible seismic null additionally requires point-process/declustering review, catalog-completeness analysis, and sensitivity across magnitude thresholds.

The detector's `CONFIRMED` status remains internal to its own rules. A detected break is not automatically a validated historical shock, an early warning, a forecast, or a probability of future events.
