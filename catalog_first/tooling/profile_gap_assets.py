from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
GATE = ROOT / 'readiness_gate'

# Exact country-level universe already proven by the WDI/IMF raw-panel intersection.
panel = pd.read_csv(GATE / 'ANNUAL_PANEL_RAW_WDI_IMF_2000_2024.csv', usecols=['entity_code'])
common_codes = set(panel['entity_code'].dropna().astype(str))

# Select two EIA annual concepts that have explicit definitions, country geography, and every 2000-2024 point.
concepts = {
    'energy_consumption_per_capita': 'energy consumption per capita',
    'energy_consumption_per_gdp': 'energy consumption per gdp',
}
selected = {}
catalog_rows = []
for line in (ROOT / 'staged/eia/intl/INTL.txt').open(encoding='utf-8', errors='replace'):
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        continue
    if obj.get('f') != 'A' or not isinstance(obj.get('data'), list):
        continue
    geo = str(obj.get('geography', '')).strip()
    if geo not in common_codes:
        continue
    name = str(obj.get('name', ''))
    low = name.lower()
    concept = next((key for key, phrase in concepts.items() if phrase in low), None)
    if concept is None:
        continue
    points = {str(x[0]): x[1] for x in obj['data'] if isinstance(x, list) and len(x) >= 2 and x[1] is not None}
    years = [str(y) for y in range(2000, 2025)]
    if not all(y in points for y in years):
        continue
    candidate = {
        'series_id': obj.get('series_id'), 'name': name, 'units': obj.get('units'), 'frequency': obj.get('f'),
        'geography': geo, 'start': obj.get('start'), 'end': obj.get('end'), 'last_updated': obj.get('last_updated'),
        'data_points': len(points), 'values_2000_2024': {y: points[y] for y in years}, 'copyright': obj.get('copyright'),
    }
    catalog_rows.append({'concept': concept, **{k: v for k, v in candidate.items() if k != 'values_2000_2024'}})
    selected.setdefault((concept, geo), candidate)

# Preserve one deterministic series per concept/geography and export raw native annual points unchanged.
selected_rows = []
for (concept, geo), obj in sorted(selected.items()):
    for year, value in obj['values_2000_2024'].items():
        selected_rows.append({'entity_code': geo, 'year': int(year), 'variable_id': obj['series_id'], 'concept': concept, 'value': value})

outdir = ROOT / 'gap_assets'
outdir.mkdir(exist_ok=True)
with (outdir / 'EIA_SELECTED_ANNUAL_2000_2024_LONG.csv').open('w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['entity_code','year','variable_id','concept','value'])
    writer.writeheader(); writer.writerows(selected_rows)
unique_catalog_rows = []
for (concept, geo), obj in sorted(selected.items()):
    unique_catalog_rows.append({'concept': concept, **{k: v for k, v in obj.items() if k != 'values_2000_2024'}})
with (outdir / 'EIA_SELECTED_SERIES_CATALOG.csv').open('w', encoding='utf-8', newline='') as f:
    fields=['concept','series_id','name','units','frequency','geography','start','end','last_updated','data_points','copyright']
    writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(unique_catalog_rows)

# UCDP full field profile plus key candidate fields.
ucdp_path = ROOT / 'staged/ucdp/country_year261/OrganizedViolenceCYDataSet26_1.csv'
ucdp = pd.read_csv(ucdp_path, dtype=str, low_memory=False)
ucdp['year_num'] = pd.to_numeric(ucdp['year'], errors='coerce')
key_fields = {
    'sb_exist': ('bool', 'Existence of state-based organized violence within country borders in a given year; 1 if it occurs.'),
    'sb_total_deaths_best': ('integer', 'Best estimate for total fatalities in state-based violence within country borders in a given year.'),
    'ns_exist': ('bool', 'Existence of non-state violence within country borders in a given year; 1 if it occurs.'),
    'ns_total_deaths_best': ('integer', 'Best estimate for total fatalities in non-state violence within country borders in a given year.'),
    'os_exist': ('bool', 'Existence of one-sided violence within country borders in a given year; 1 if it occurs.'),
    'os_total_deaths_best': ('integer', 'Best estimate for total fatalities in one-sided violence within country borders in a given year.'),
    'cumulative_total_deaths_in_orgvio_best': ('integer', 'Best estimate for cumulative total fatalities in organized violence within country borders.'),
}
ucdp_rows=[]
for col in ucdp.columns:
    if col == 'year_num': continue
    nonempty = ucdp[col].notna() & ucdp[col].astype(str).str.strip().ne('')
    years = ucdp.loc[nonempty, 'year_num'].dropna()
    field_type, definition = key_fields.get(col, ('field-specific', f'UCDP Country-Year field {col}; see official codebook.'))
    ucdp_rows.append({
      'dataset_id':'ucdp_country_year_organized_violence_v26_1','source':'UCDP','version':'26.1','variable_id':col,
      'variable_name':col,'definition':definition,'field_type':field_type,'unit':'field-specific; see codebook',
      'native_frequency':'annual country-year','true_start_date':int(years.min()) if len(years) else '',
      'true_end_date':int(years.max()) if len(years) else '', 'native_record_count':int(nonempty.sum()),
      'total_rows':len(ucdp),'distinct_country_ids':int(ucdp['country_id'].nunique()),
      'missing_rows':int((~nonempty).sum()), 'missing_rate':round(float((~nonempty).mean()),6),
      'raw_path':str(ROOT/'raw/ucdp/country_year261/organizedviolencecy-261-csv.zip'),
      'staged_path':str(ucdp_path),'codebook':str(ROOT/'raw/ucdp/country_year261/UCDP_OrganizedViolenceCY_Codebook_261.pdf'),
    })
(ROOT/'ucdp_country_year_variable_profile.json').write_text(json.dumps({
  'dataset_id':'ucdp_country_year_organized_violence_v26_1','rows':len(ucdp),'columns':len(ucdp.columns)-1,
  'country_id_count':int(ucdp['country_id'].nunique()),'country_name_count':int(ucdp['country'].nunique()),
  'year_range':[int(ucdp['year_num'].min()),int(ucdp['year_num'].max())], 'variables':ucdp_rows,
  'key_candidate_fields':key_fields,
},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary={
 'eia_selected_concepts': list(concepts),
 'eia_selected_series_count': len(selected),
 'eia_selected_country_count': len({geo for _,geo in selected}),
 'eia_selected_long_rows': len(selected_rows),
 'eia_catalog_candidate_rows': len(catalog_rows),
 'eia_selected_catalog_rows': len(unique_catalog_rows),
 'eia_selected_country_concept_counts': Counter(k[0] for k in selected),
 'common_panel_country_count': len(common_codes),
 'ucdp_rows': len(ucdp), 'ucdp_columns': len(ucdp.columns)-1, 'ucdp_country_id_count': int(ucdp['country_id'].nunique()),
 'ucdp_country_name_count': int(ucdp['country'].nunique()), 'ucdp_year_range':[int(ucdp['year_num'].min()),int(ucdp['year_num'].max())],
 'outputs':[str(outdir/'EIA_SELECTED_ANNUAL_2000_2024_LONG.csv'),str(outdir/'EIA_SELECTED_SERIES_CATALOG.csv'),str(ROOT/'ucdp_country_year_variable_profile.json')],
 'no_transformations_or_imputation': True,
}
(ROOT/'gap_assets_profile.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
