# Visual QA notes

- `01_annual_variable_coverage_wdi_imf.png`: PASS. All 20 selected WDI/IMF variables are legible, ordered by coverage, with numeric percentage labels, axis range 80–101%, and a clear source legend. The chart is a deterministic plot from the augmented coverage CSV.
- `02_candidate_matrix_comparison.png`: PASS. The four candidate matrices are legible in both panels; coverage percentages and 25-year complete-country counts are displayed directly above bars. The chart makes clear that the previous macro candidate has the highest readiness and that adding UCDP reduces completeness.

No visual interpretation adds data or transformations; plots use only stored gate outputs.

- `03_scope_and_gap_funnel.png`: PASS. The plot labels the four counts and explicitly notes they are not interchangeable: common country IDs, EIA per-concept countries, conservative UCDP name matches, and NOAA stations.
- `04_gsom_prcp_station_coverage.png`: PASS. All nine station-level native monthly PRCP coverage values are legible, including the extreme gaps, and the title explicitly states no daily-to-monthly conversion.

All four visual outputs passed a lightweight visual check.
