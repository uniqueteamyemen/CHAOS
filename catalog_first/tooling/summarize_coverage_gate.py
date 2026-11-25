from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
GATE = ROOT / 'readiness_gate'
path = GATE / 'VARIABLE_LEVEL_COVERAGE_MATRIX.csv'
rows = list(csv.DictReader(path.open(encoding='utf-8', newline='')))

def as_num(value: str, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

# Exact rows relevant to proposed annual matrix.
annual = [r for r in rows if r['dataset_id'] in ('worldbank_wdi_bulk_csv', 'imf_weo_apr2026_current')]
for r in annual:
    r['coverage_ratio_num'] = as_num(r['panel_coverage_ratio'])

print('total coverage rows:', len(rows))
print('WDI+WEO annual variable rows:', len(annual))
print('\nWDI selected variables:')
for r in annual:
    if r['dataset_id'] == 'worldbank_wdi_bulk_csv':
        print(f"{r['variable_id']} | {r['variable_name']} | unit={r['unit']} | true={r['true_start_date']}..{r['true_end_date']} | entities={r['panel_active_entities']} | observed={r['panel_observed_cells']}/{r['panel_expected_cells']} | coverage={r['panel_coverage_ratio']} | full_entities={r['full_panel_entity_count']}")
print('\nIMF WEO selected variables:')
for r in annual:
    if r['dataset_id'] == 'imf_weo_apr2026_current':
        print(f"{r['variable_id']} | {r['variable_name']} | unit={r['unit']} | true={r['true_start_date']}..{r['true_end_date']} | entities={r['panel_active_entities']} | observed={r['panel_observed_cells']}/{r['panel_expected_cells']} | coverage={r['panel_coverage_ratio']} | full_entities={r['full_panel_entity_count']}")

# Best direct candidates by coverage ratio, requiring at least 1 active entity.
ranked = sorted([r for r in annual if as_num(r['panel_expected_cells']) > 0], key=lambda r: (-as_num(r['panel_coverage_ratio']), r['dataset_id'], r['variable_id']))
print('\nTop annual variables by raw 2000–2024 cell coverage:')
for r in ranked[:40]:
    print(r['dataset_id'], r['variable_id'], r['panel_coverage_ratio'], r['full_panel_entity_count'])

# Group counts for all rows by dataset/frequency/status.
print('\nRows by dataset:')
print(json.dumps(Counter(r['dataset_id'] for r in rows), ensure_ascii=False, indent=2))
print('\nRows by native frequency:')
print(json.dumps(Counter(r['native_frequency'] for r in rows), ensure_ascii=False, indent=2))

# Coverage report for requested concrete variables including event/daily representations.
concrete = []
for r in rows:
    if r['dataset_id'] in ('worldbank_wdi_bulk_csv','imf_weo_apr2026_current','imf_weo_historical_forecasts','fred_cpiaucsl','fred_dcoilwtico','ucdp_ged_global_v26_1','ucdp_prio_armed_conflict_v26_1','noaa_ghcn_daily_selected_stations','gdelt_reduced_1979_2013'):
        concrete.append(r)
summary = GATE / 'VARIABLE_COVERAGE_GATE_SUMMARY.json'
summary.write_text(json.dumps({
    'total_rows': len(rows),
    'annual_wdi_weo_rows': len(annual),
    'top_annual_by_coverage': [
        {k: r[k] for k in ('dataset_id','variable_id','variable_name','unit','true_start_date','true_end_date','panel_active_entities','panel_expected_cells','panel_observed_cells','panel_missing_cells','panel_coverage_ratio','full_panel_entity_count','missing_gaps','definition_methodology_shifts','provenance')}
        for r in ranked[:50]
    ],
    'concrete_downloaded_rows_count': len(concrete),
    'dataset_row_counts': dict(Counter(r['dataset_id'] for r in rows)),
    'frequency_row_counts': dict(Counter(r['native_frequency'] for r in rows)),
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('\nWrote', summary)
