# CHAOS — Governed Historical Signals and Structural Discovery

> **Start here:** [STATUS.md — current execution status, active phase, and mandatory entry point](STATUS.md)

**CHAOS** is a research and engineering workspace for discovering, testing, and governing temporal structure across independent real-world domains. Its purpose is broader than any single forecasting task or dataset: preserve source evidence, identify transitions, test whether signals repeat or connect, and only then evaluate whether they support sensing or prediction.

This repository keeps raw observations, source provenance, data contracts, detector experiments, and derived outputs auditable. It does not treat correlation as causality, an anomaly as a structural transition, or a detected transition as a forecast.

## ملخص تنفيذي بالعربية

- أُغلقت سلسلة التجارب الاصطناعية بعد **9 حزم تجريبية مسماة**، ثم تطوير 26M والتحقق المستقل 27M.
- شمل تحقق 27M عدد 16,000 سلسلة مستقلة وثلاثة/أربعة أنظمة مقارنة؛ القرار المرحلي كان ترشيح Markov CUSUM عند H=8.5، لا اعتماده إنتاجياً.
- عُزل المحرك في حزمة مستقلة بثلاثة أوضاع: Fast وMarkov CUSUM وConsensus، مع حالات PROVISIONAL وCONFIRMED وTRANSIENT وUNRESOLVED.
- فُحصت بيانات USGS الحقيقية بصيغ شهرية وفصلية وبفواصل الأحداث؛ كما فُحصت بيانات UN AMA واللوحات الاقتصادية في catalog_first.
- ظهرت تحولات داخلية مؤكدة في سلاسل الفواصل بين الزلازل، لكنها لم تُتحقق بعد مقابل مرجع جيولوجي مستقل، ولذلك لا تُعد تنبؤات زلزالية.
- أُرشفت نتائج الفحص وبصمات SHA-256 داخل الفرع المستقل.

## Current repository state

The authoritative working and default branch is `main-phase2`. The active phase, accepted decisions, current baselines, and mandatory next steps are maintained in **[STATUS.md — authoritative execution status](STATUS.md)**.

This README retains historical research context and archived results. Historical branch names and detector recommendations below do not override the current state in STATUS.md.

## How the detector reached this point

The sequential-break line developed through **nine named experiment packages** in `experiments/identity_lab/`:

1. Initial sequential-break engine.
2. Audited lifecycle and accounting.
3. B3.2 minimal retest.
4. B4 two-point variant.
5. B5 adaptive-rho variant.
6. B6 Spearman ablation.
7. B6.1 SARP/SAGP factorial baseline.
8. B7 innovation-sign CUSUM.
9. B7.1 isolated Markov/router/consensus validation.

These are nine named experiment packages, not nine total runs. B-v7.1 then used a 26M development seed and a separate 27M validation seed. The final validation covered eight synthetic regimes, 16,000 independent series, and four systems evaluated on the same series. The development stage compared Markov thresholds 7.0, 7.5, 8.0, and 8.5 before selecting H=8.5 for the holdout.

### B-v7.1 final validation reference

The figures below are the reported 27M holdout results, not real-world performance estimates.

| Metric | Fast_Ref | Markov CUSUM H=8.5 | Auto-Router | Consensus |
|---|---:|---:|---:|---:|
| Confirmed Structural FPR | 22.05% | **7.05%** | 9.05% | **1.90%** |
| Transient FPR | 3.25% | 5.75% | 4.85% | 3.25% |
| Combined FPR — Null | 15.60% | **7.90%** | 9.85% | **3.75%** |
| Combined FPR — All nonlevel | 23.75% | **9.15%** | 11.30% | **7.15%** |
| Mean Directional Sensitivity | **91.45%** | 84.40% | 84.15% | 63.45% |
| Confirmed Delay (miss penalty 75) | **19.057** | 44.181 | 42.617 | 48.565 |

Key trade-off: Markov CUSUM materially reduced false alarms against Fast_Ref while retaining more sensitivity than Consensus. Consensus achieved the lowest confirmed structural false-positive rate but missed 1,462 of 4,000 true transitions in the reported validation. Its provisional events must therefore remain internal until independently confirmed.

The PENDING accounting audit reported 678 opened events per system, with zero opening-time mismatches and complete terminal accounting across structural, transient, and unresolved outcomes.

**Decision carried forward:** Markov CUSUM H=8.5 is the primary candidate for real-data examination; Fast_Ref remains the high-sensitivity reference; Consensus remains a confirmation/staging mode; Auto-Router remains experimental. This is a candidate selection for further testing, not a production approval.

Original benchmark reference: [GitHub Actions Run 43963431381](https://github.com/uniqueteamyemen/CHAOS/actions/runs/43963431381).

## Frozen detector interface

The stable Python entry point is:

```python
from structural_engine.isolated_break_detector_v1 import BreakDetectorV1

result = BreakDetectorV1(mode="markov_cusum", markov_threshold=8.5).analyze(series)
```

Supported modes:

- `fast`: Fast_Ref structural candidates are exposed as `PROVISIONAL`.
- `markov_cusum`: Markov innovation-sign CUSUM transitions are exposed as `CONFIRMED` within this detector's own decision rule.
- `consensus`: a Fast_Ref provisional transition is promoted only when matched one-to-one with a forward, same-direction Markov transition; unmatched candidates remain `PROVISIONAL`.

Lifecycle statuses are normalized as `PROVISIONAL`, `CONFIRMED`, `TRANSIENT`, and `UNRESOLVED`. The adapter preserves the original detector calculations; it standardizes the public interface and status vocabulary. The original B6.1 and B7 engines are preserved as separate source files.

The detector requires at least 52 finite, one-dimensional observations to begin evaluation (40 quiet observations plus a 12-point window). At least **66 observations** allow the earliest eligible event to complete the 14-step resolution horizon; **87** allow the earliest eligible event to complete the 35-step consensus window. Later detections can still be right-censored. The adapter reports these sample-level adequacy flags for every run. All horizons are measured in observations or event intervals; they are not calendar units unless the input representation declares them.

## Real historical data scan

The archived scan is `structural_engine/isolated_break_detector_v1/results/real_data_transition_scan.json`. It preserves the series, event-time axes, per-mode diagnostics, and full transition ledgers. The companion `SHA256SUMS.txt` records the exact detector, source-data, and contract hashes.

### USGS event sources

| Source / representation | Observations | Data-quality result | Detector result |
|---|---:|---|---|
| Gulf of Aden M4.5+, monthly counts | 300 months | 51.67% empty months; quiet-period scale degenerate | Not interpretable |
| Gulf of Aden M4.5+, quarterly counts | 100 quarters | Non-degenerate scale; 17% empty quarters | No transitions detected |
| Gulf of Aden, inter-event intervals | 407 intervals | Non-degenerate; full lifecycle horizon available | Fast: 3 provisional; Markov: 2 internally confirmed; Consensus: 1 confirmed + 2 provisional |
| Global M6.5+, monthly counts | 300 months | Non-degenerate; 3.67% empty months | No transitions detected |
| Global M6.5+, quarterly counts | 100 quarters | Non-degenerate; no empty quarters | No transitions detected |
| Global M6.5+, inter-event intervals | 1,140 intervals | Non-degenerate; full lifecycle horizon available | Markov: 1 internally confirmed; Fast and Consensus: none |

The event-time representation is `log1p(days_between_consecutive_events)`. A negative direction means shorter waiting intervals (higher event rate); a positive direction means longer intervals (lower event rate).

Historical event-time candidates:

- **Gulf of Aden:** Markov transitions at 2010-11-14 and 2023-06-03, both in the shorter-interval direction. Consensus matched the Fast provisional onset of 2009-11-05 to the Markov confirmation on 2010-11-14 (16 event intervals later). The 2006 and 2023 Fast candidates remain provisional under Consensus.
- **Global M6.5+:** one Markov transition with onset 2022-01-14 and detection 2022-08-14, in the longer-interval direction.

These are detector-internal structural decisions on event waiting times. They are not independently validated geological regime changes, causal explanations, or earthquake forecasts. The monthly Gulf count result is explicitly invalidated by its degenerate baseline scale; it is not included as evidence.

### Catalog-first annual data readiness

| Dataset | Committed coverage | Decision |
|---|---|---|
| UN AMA GDP growth panel | 220 country series; 179 have 54 contiguous annual observations (1971–2024) | Screened; 0 series has the 66-point full-resolution horizon or 87-point consensus horizon |
| Macro + EIA complete annual panel | 139 country entities; 25 years each | Not run: too short |
| EIA selected annual long panel | 378 country-variable series; 25 years each | Not run: too short |
| World Bank domestic credit (% GDP) | 233 entities; 25 years each | Not run: too short |

The UN AMA scan produced three Fast provisional candidates (Bangladesh, Guinea, Singapore), with no Markov confirmations. Since the series have only 54 observations, these are screening flags only; the full 14-step resolution and 35-step consensus windows cannot complete.

The repository contains manifests or profiles for UCDP GED, NOAA GSOM, and WHO daily data, but their corresponding raw event/station/daily payload files are not committed at the referenced paths. They were therefore not fabricated, downloaded implicitly, or run. The annual panels were not padded or interpolated to satisfy detector requirements.

## Reproducibility

The workflow `.github/workflows/phase1-detector-real-data.yml`:

1. Runs 11 detector and data-adapter tests.
2. Scans USGS monthly, quarterly, and event-time representations plus the eligible UN AMA GDP-growth panel.
3. Records SHA-256 hashes for the isolated package, input files, manifests, and source contract.
4. Commits the report and checksum inventory to this working branch and uploads the same files as a GitHub Actions artifact.

Run locally from the repository root:

```bash
python -m pip install numpy
python -m unittest discover -s structural_engine/isolated_break_detector_v1/tests -v
python -m structural_engine.isolated_break_detector_v1.run_real_data
```

## Research sequence after the scan

1. Establish whether each real-data series has sufficient variation, coverage, and temporal resolution for the frozen detector.
2. Review every detected transition against its raw source interval and preserve the full event ledger, including transient and unresolved outcomes.
3. Evaluate stability across domains and sampling frequencies without tuning the detector to the observed answer.
4. Build the predictive early-warning layer only after signal lead time, false-alarm burden, missed-event cost, and out-of-sample performance can be measured.
5. Add cross-domain relationships only when the source timelines and evidence semantics support them.

A transition detector is a sensor for changes in a series. A predictive early-warning system additionally needs a validated relationship between earlier signals and later target events, causal ordering where relevant, calibrated lead-time estimates, and independent temporal holdouts.

## Repository map

| Path | Purpose |
|---|---|
| `catalog_first/` | Dataset inventories, coverage matrices, readiness reports, and candidate panels |
| `data/raw/` | Versioned source observations and manifests |
| `experimental_contracts/` | Frozen source and experiment contracts |
| `experiments/identity_lab/` | Historical detector development and validation lineage |
| `structural_engine/isolated_break_detector_v1/` | Frozen detector package, public adapter, tests, and real-data runner |
| `docs/` | Governance, data-readiness, experiment, and phase reports |
| `.github/workflows/` | Reproducible CI and benchmark workflows |

## Data and governance principles

- Preserve raw source records and provenance.
- Keep source-specific variables separate unless an explicit contract authorizes a transformation.
- Preserve missingness, conflicting observations, and unresolved cases.
- Do not treat temporal precedence as causality.
- Do not tune thresholds on the holdout or select a model because its output looks desirable.
- Distinguish executed results, verified evidence, interpretation, assumptions, and work not yet performed.
