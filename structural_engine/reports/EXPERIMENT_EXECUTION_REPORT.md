# Controlled Experimental Grid Report

## Scope

This report covers the controlled experimental grid executed on the observed data available in the isolated workspace. It does not claim that all 25 years of all named sources were available in a single matrix. Native frequencies were kept separate, and no value was imputed.

## Experiment registry

Two experiments were declared before calculations:

| Experiment | Frequency | Purpose | Status |
|---|---|---|---|
| `annual_global_macro_grid` | Annual | Explore lagged dependence across observed World Bank global series with an IMF candidate variable recorded in the registry | Executed on available observed columns |
| `daily_usgs_streamflow_isolated` | Daily | Reserve a native-frequency experiment for the USGS series without cross-frequency merging | Declared; no multi-variable discovery because only one daily variable was available |

The registry records source variables, native frequencies, alignment, transformations, lag window, surrogate method, block configurations, surrogate budget, seed, multiple-testing procedure, and temporal split.

## Executed annual grid

The executed annual matrix contains 26 calendar-year rows with at least two observed variables and no imputation. Variables with no observations were not used as measured values. Positive-valued stock/scale variables were transformed with log differences in a derived matrix; inflation was retained as an observed rate. Raw source records remain unchanged.

The lag grid evaluated pairwise time-directed candidates over 0–5 years. It used exact non-zero circular shifts for the short observed sample, Benjamini–Hochberg FDR correction across the tested candidates, and a chronological train/test split of 2000–2017 versus 2018–2025.

| Result | Count |
|---|---:|
| Tested lag results | 72 |
| Candidate patterns retained | 0 |
| Rejected/spurious or insufficiently supported patterns retained | 72 |
| Golden/validated patterns promoted | 0 |

The empty golden registry is intentional. The bounded annual matrix is an exploratory validation surface, not sufficient evidence for promoting a structural pattern. All rejected lines remain stored with their experiment ID, lag, score, empirical surrogate p-value, FDR q-value, train/test fields, transformation log, and matrix provenance.

## Scientific interpretation

The results are temporal-dependence test outputs, not claims of physical causation. The grid did not discover a pattern strong enough to enter the validated or golden registry under the declared procedure. This is a valid experimental result and prevents a small annual sample from being promoted into a false causal rule.

## Verification

Python compilation passed, all five unit tests passed, and TypeScript compilation passed. The raw store and earlier acquisition artifacts remain separate from the derived experimental matrices. No raw source response was modified, no blanket forward-fill/back-fill/interpolation was performed, and no source conflict was reconciled by averaging.

## Corrected 10,000-surrogate real run

The corrected engine was run on the real annual matrix using three fully observed variables (World Bank global GDP, CPI inflation, and population). The fourth captured World Bank series, energy use per capita, was excluded from this inferential matrix because the derived aligned values were not complete under the explicit observed-only policy; the raw series remains preserved. Six lags (0–5 years) were evaluated for each directed pair, producing 36 edge-lag results. Every result executed exactly 10,000 train-only circular surrogates. BH-FDR, chronological OOS stability, and minimum test support produced zero validated structural patterns and 36 rejected or unstable lines. Two raw p-values were below 0.01 before FDR; neither was promoted after the declared family-wise candidate correction and stability gates.
