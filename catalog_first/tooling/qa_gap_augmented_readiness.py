from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT=Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
GATE=ROOT/'readiness_gate'
with (GATE/'VARIABLE_LEVEL_COVERAGE_MATRIX_GAP_AUGMENTED.csv').open(encoding='utf-8',newline='') as f:
    cov=list(csv.DictReader(f))
with (GATE/'ANNUAL_PANEL_RAW_WDI_IMF_UCDP_EIA_2000_2024.csv').open(encoding='utf-8',newline='') as f:
    panel=list(csv.DictReader(f))
comp=json.loads((GATE/'CANDIDATE_MATRIX_COMPARISON_GAP_AUGMENTED.json').read_text(encoding='utf-8'))
assert len(cov)==105026, len(cov)
assert len(panel)==4850, len(panel)
assert len(panel[0])==33, len(panel[0])
assert sum(r['dataset_id']=='ucdp_country_year_organized_violence_v26_1' for r in cov)==74
assert sum(r['dataset_id']=='eia_selected_annual_energy_intensity' for r in cov)==378
assert sum(r['dataset_id']=='noaa_gsom_monthly_selected_stations' for r in cov)==9
assert comp['no_experiment_or_model'] is True
assert comp['eia_country_count_per_concept']=={'energy_consumption_per_capita':189,'energy_consumption_per_gdp':189}
assert comp['ucdp_country_name_mapping_exact_normalized_unique_count']==155
assert comp['gsom_station_count']==9
for p in [ROOT/'GAP_AUGMENTED_DATA_READINESS_REPORT_AR.md',ROOT/'HISTORICAL_DATASET_ACQUISITION_INVENTORY.csv',ROOT/'gap_assets/EIA_SELECTED_SERIES_CATALOG.csv',ROOT/'gap_assets/EIA_SELECTED_ANNUAL_2000_2024_LONG.csv',ROOT/'gap_assets/UCDP_COUNTRY_NAME_MAPPING_AUDIT.csv',ROOT/'gsom_monthly_profile.json']:
    assert p.exists() and p.stat().st_size>0, p
print('coverage_rows=',len(cov),'ucdp_rows=',sum(r['dataset_id']=='ucdp_country_year_organized_violence_v26_1' for r in cov),'eia_rows=',sum(r['dataset_id']=='eia_selected_annual_energy_intensity' for r in cov),'gsom_rows=',sum(r['dataset_id']=='noaa_gsom_monthly_selected_stations' for r in cov))
print('panel_rows=',len(panel),'panel_columns=',len(panel[0]))
print('eia_country_counts=',comp['eia_country_count_per_concept'],'ucdp_exact_mapping=',comp['ucdp_country_name_mapping_exact_normalized_unique_count'])
print('QA=PASS')
