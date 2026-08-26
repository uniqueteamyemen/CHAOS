from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
GATE = ROOT / 'readiness_gate'
with (GATE / 'VARIABLE_LEVEL_COVERAGE_MATRIX.csv').open(encoding='utf-8', newline='') as f:
    coverage = list(csv.DictReader(f))
with (GATE / 'ANNUAL_PANEL_RAW_WDI_IMF_2000_2024.csv').open(encoding='utf-8', newline='') as f:
    panel = list(csv.DictReader(f))
summary = json.loads((GATE / 'ANNUAL_PANEL_READINESS_SUMMARY.json').read_text(encoding='utf-8'))
assert len(coverage) == 104565, len(coverage)
assert len(panel) == 4850, len(panel)
assert summary['experiment_run'] is False
assert summary['model_training_run'] is False
assert summary['transformations_applied'] == []
assert summary['imputation_applied'] is False
assert summary['source_reconciliation_applied'] is False
required = {'worldbank_wdi_bulk_csv','imf_weo_apr2026_current','imf_weo_historical_forecasts','eia_intl_bulk','fred_cpiaucsl','fred_dcoilwtico','ucdp_ged_global_v26_1','ucdp_prio_armed_conflict_v26_1','gdelt_reduced_1979_2013'}
assert required.issubset({r['dataset_id'] for r in coverage})
for path in [
    ROOT / 'DATA_READINESS_GATE_REPORT_AR.md',
    GATE / 'VARIABLE_COVERAGE_GATE_SUMMARY.json',
    GATE / 'FIRST_MATRIX_CANDIDATE_READINESS.json',
    GATE / 'FIRST_EXPERIMENTAL_MATRIX_CANDIDATES.json',
]:
    assert path.exists() and path.stat().st_size > 0, path
print('coverage_rows=', len(coverage))
print('panel_rows=', len(panel), 'panel_columns=', len(panel[0]))
print('common_entities=', summary['identifier_intersection_any_selected_variable'])
print('strict_20_variable_entities=', summary['strict_both_entities_complete_all_selected_variables_2000_2024'])
print('QA=PASS')
