from __future__ import annotations

import csv
import json
import math
import re
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
GATE = ROOT / 'readiness_gate'
OUT = ROOT / 'gap_assets'
YEARS = list(range(2000, 2025))

MATRIX_FIELDS = [
    'dataset_id', 'source', 'variable_id', 'variable_name', 'definition', 'unit',
    'native_frequency', 'true_start_date', 'true_end_date', 'native_record_count',
    'native_entity_or_event_count', 'panel_start', 'panel_end', 'panel_active_entities',
    'panel_expected_cells', 'panel_observed_cells', 'panel_missing_cells',
    'panel_coverage_ratio', 'full_panel_entity_count', 'missing_gaps',
    'definition_methodology_shifts', 'provenance', 'status', 'notes'
]

def clean(x: object) -> str:
    if x is None: return ''
    if isinstance(x, float) and math.isnan(x): return ''
    return str(x).strip()

def norm_name(x: object) -> str:
    s = unicodedata.normalize('NFKD', clean(x)).encode('ascii','ignore').decode().lower()
    s = re.sub(r"[^a-z0-9]+", ' ', s).strip()
    return s

def ratio(a: int, b: int): return round(a / b, 6) if b else ''

def add_cov(rows, **kw):
    rows.append({f: kw.get(f, '') for f in MATRIX_FIELDS})

# Load the previous variable-level matrix and retain it verbatim as the base.
base_path = GATE / 'VARIABLE_LEVEL_COVERAGE_MATRIX.csv'
with base_path.open(encoding='utf-8', newline='') as f:
    base_rows = list(csv.DictReader(f))
augmented = list(base_rows)

# ---------- UCDP Country-Year v26.1: all fields, with codebook-backed key definitions ----------
ucdp_path = ROOT / 'staged/ucdp/country_year261/OrganizedViolenceCYDataSet26_1.csv'
ucdp = pd.read_csv(ucdp_path, dtype=str, low_memory=False)
ucdp['year_num'] = pd.to_numeric(ucdp['year'], errors='coerce')
ucdp_fields = [c for c in ucdp.columns if c != 'year_num']
key_defs = {
 'sb_exist': ('bool', 'Existence of state-based organized violence within the borders of a country in a given year; 1 if it occurs.'),
 'sb_total_deaths_best': ('integer', 'Best estimate for total fatalities in state-based violence within the borders of a country in a given year.'),
 'ns_exist': ('bool', 'Existence of non-state violence within the borders of a country in a given year; 1 if it occurs.'),
 'ns_total_deaths_best': ('integer', 'Best estimate for total fatalities in non-state violence within the borders of a country in a given year.'),
 'os_exist': ('bool', 'Existence of one-sided violence within the borders of a country in a given year; 1 if it occurs.'),
 'os_total_deaths_best': ('integer', 'Best estimate for total fatalities in one-sided violence within the borders of a country in a given year.'),
 'cumulative_total_deaths_in_orgvio_best': ('integer', 'Best estimate for cumulative total fatalities in organized violence within the borders of a country.'),
 'country': ('identifier', 'UCDP country name in the country-year record.'),
 'country_id': ('identifier', 'UCDP numeric country identifier.'),
 'year': ('year', 'Country-year observation year.'),
}
for col in ucdp_fields:
    present = ucdp[col].notna() & ucdp[col].astype(str).str.strip().ne('')
    d = ucdp.loc[present, 'year_num'].dropna()
    if len(d):
        lo, hi = int(d.min()), int(d.max())
    else:
        lo = hi = ''
    window = ucdp[(ucdp['year_num'].isin(YEARS))]
    wpresent = window[col].notna() & window[col].astype(str).str.strip().ne('')
    active_entities = set(window.loc[wpresent, 'country_id'].dropna().astype(str))
    expected = len(active_entities) * len(YEARS)
    observed = int(wpresent.sum())
    by_entity = window.assign(_present=wpresent).groupby('country_id')['_present'].agg(['sum','count'])
    full_entities = int((by_entity['sum'] == len(YEARS)).sum()) if len(by_entity) else 0
    dtype, definition = key_defs.get(col, ('field-specific', f'UCDP Country-Year field `{col}`; see official codebook.'))
    unit = {'bool':'0/1 boolean','integer':'fatality/count integer','identifier':'source identifier','year':'calendar year'}.get(dtype, 'field-specific; see codebook')
    add_cov(augmented,
      dataset_id='ucdp_country_year_organized_violence_v26_1', source='UCDP', variable_id=col,
      variable_name=col, definition=definition, unit=unit, native_frequency='annual country-year',
      true_start_date=lo, true_end_date=hi, native_record_count=int(present.sum()), native_entity_or_event_count=int(ucdp['country_id'].nunique()),
      panel_start='2000', panel_end='2024', panel_active_entities=len(active_entities), panel_expected_cells=expected,
      panel_observed_cells=observed, panel_missing_cells=expected-observed, panel_coverage_ratio=ratio(observed,expected),
      full_panel_entity_count=full_entities,
      missing_gaps=f'2000–2024 country-year field cells expected={expected}; observed={observed}; missing={expected-observed}; no filling applied',
      definition_methodology_shifts='UCDP version 26.1 country-year aggregation; codebook/version history retained. This is a source-defined aggregation of GED, not a new aggregation performed here.',
      provenance=f'raw={ROOT / "raw/ucdp/country_year261/organizedviolencecy-261-csv.zip"}; staged={ucdp_path}; codebook={ROOT / "raw/ucdp/country_year261/UCDP_OrganizedViolenceCY_Codebook_261.pdf"}; manifest={ROOT / "raw/ucdp/country_year261/sha256sums.txt"}',
      status='downloaded/raw+staged', notes=f'UCDP field type={dtype}; empty values remain missing; textual NO_DYAD is a source value, not converted to null.'
    )

# ---------- EIA selected annual series: one matrix row per selected series ----------
eia_catalog = pd.read_csv(OUT / 'EIA_SELECTED_SERIES_CATALOG.csv', dtype=str)
eia_values = pd.read_csv(OUT / 'EIA_SELECTED_ANNUAL_2000_2024_LONG.csv', dtype={'entity_code':str,'year':int,'variable_id':str,'concept':str})
for _, r in eia_catalog.iterrows():
    sid = clean(r['series_id']); values = eia_values[eia_values['variable_id'].eq(sid)]
    nums = pd.to_numeric(values['value'], errors='coerce')
    observed = int(nums.notna().sum())
    expected = len(YEARS)
    add_cov(augmented,
      dataset_id='eia_selected_annual_energy_intensity', source='EIA', variable_id=sid,
      variable_name=clean(r['name']), definition=clean(r['name']), unit=clean(r['units']), native_frequency='annual',
      true_start_date=clean(r['start']), true_end_date=clean(r['end']), native_record_count=int(r['data_points']), native_entity_or_event_count=1,
      panel_start='2000', panel_end='2024', panel_active_entities=1, panel_expected_cells=expected, panel_observed_cells=observed,
      panel_missing_cells=expected-observed, panel_coverage_ratio=ratio(observed,expected), full_panel_entity_count=1 if observed==expected else 0,
      missing_gaps=f'series-native 2000–2024 expected={expected}; observed={observed}; missing={expected-observed}; no filling applied',
      definition_methodology_shifts=f'EIA INTL series-specific record; source last_updated={clean(r["last_updated"])}; no methodology-shift detection applied.',
      provenance=f'raw={ROOT / "raw/eia/INTL.zip"}; staged={ROOT / "staged/eia/intl/INTL.txt"}; selected_catalog={OUT / "EIA_SELECTED_SERIES_CATALOG.csv"}; values={OUT / "EIA_SELECTED_ANNUAL_2000_2024_LONG.csv"}; manifest={ROOT / "raw/fred_eia_sha256sums.txt"}',
      status='downloaded/raw+selected', notes=f'concept={clean(r["concept"])}; geography={clean(r["geography"])}; selection required exact non-null values for all 2000–2024.'
    )

# ---------- NOAA GSOM monthly PRCP: one row per station, native monthly only ----------
gsom_dir = ROOT / 'raw/noaa/gsom_monthly/stations'
for path in sorted(gsom_dir.glob('*.csv')):
    df = pd.read_csv(path, dtype=str, low_memory=False)
    dates = pd.to_datetime(df['DATE'], errors='coerce')
    present = df['PRCP'].notna() & df['PRCP'].astype(str).str.strip().ne('') & dates.notna()
    d = dates[present]
    lo, hi = d.min().strftime('%Y-%m'), d.max().strftime('%Y-%m')
    window = (dates.dt.year >= 2000) & (dates.dt.year <= 2024)
    wpresent = present & window
    observed = int(wpresent.sum())
    expected = 25 * 12
    add_cov(augmented,
      dataset_id='noaa_gsom_monthly_selected_stations', source='NOAA/NCEI GSOM v1', variable_id=f'{path.stem}:PRCP',
      variable_name=f'{path.stem} — monthly total precipitation (PRCP)',
      definition='GSOM monthly total precipitation at the named station; native NOAA monthly summary field PRCP.',
      unit='direct CSV precipitation unit; GSOM documentation permits inches or millimeters by output preference; no conversion applied', native_frequency='monthly',
      true_start_date=lo, true_end_date=hi, native_record_count=int(present.sum()), native_entity_or_event_count=1,
      panel_start='2000-01', panel_end='2024-12', panel_active_entities=1, panel_expected_cells=expected, panel_observed_cells=observed,
      panel_missing_cells=expected-observed, panel_coverage_ratio=ratio(observed,expected), full_panel_entity_count=1 if observed==expected else 0,
      missing_gaps=f'2000-01..2024-12 expected={expected} months; observed={observed}; missing={expected-observed}; no daily-to-monthly conversion and no filling',
      definition_methodology_shifts='GSOM v1 weekly-updated monthly product; primary input is GHCN-Daily, but the downloaded input is an original GSOM monthly file. Quality/attribute fields retained.',
      provenance=f'raw={path}; station_manifest={gsom_dir / "sha256sums.txt"}; documentation={ROOT / "raw/noaa/gsom_monthly/GSOM_documentation.pdf"}; DOI=https://doi.org/10.7289/V5QV3JJ5',
      status='downloaded/raw', notes='Only PRCP is registered for the gap; other columns in the file are not promoted into a candidate matrix.'
    )

updated_matrix = GATE / 'VARIABLE_LEVEL_COVERAGE_MATRIX_GAP_AUGMENTED.csv'
with updated_matrix.open('w', encoding='utf-8', newline='') as f:
    writer=csv.DictWriter(f, fieldnames=MATRIX_FIELDS); writer.writeheader(); writer.writerows(augmented)

# ---------- Exact-name UCDP-to-WDI country mapping audit, then raw augmented annual panel ----------
wdi_country = pd.read_csv(ROOT / 'staged/worldbank/wdi_csv/WDICountry.csv', dtype=str)
wdi_names = {}
for _, r in wdi_country.iterrows():
    code=clean(r.get('Country Code')); name=norm_name(r.get('Short Name'))
    if code and name: wdi_names.setdefault(name, []).append(code)
ucdp_map={}
for name in sorted(ucdp['country'].dropna().unique()):
    n=norm_name(name)
    codes=wdi_names.get(n,[])
    if len(codes)==1: ucdp_map[name]=codes[0]
map_rows=[{'ucdp_country':n,'normalized_name':norm_name(n),'wdi_code':ucdp_map.get(n,''),'match_status':'exact-normalized-unique' if n in ucdp_map else 'unmatched'} for n in sorted(ucdp['country'].dropna().unique())]
with (OUT/'UCDP_COUNTRY_NAME_MAPPING_AUDIT.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['ucdp_country','normalized_name','wdi_code','match_status']); w.writeheader(); w.writerows(map_rows)
ucdp['entity_code']=ucdp['country'].map(ucdp_map)
ucdp['year_num']=pd.to_numeric(ucdp['year'],errors='coerce')
window=ucdp[ucdp['year_num'].isin(YEARS) & ucdp['entity_code'].isin(set(pd.read_csv(GATE/'ANNUAL_PANEL_RAW_WDI_IMF_2000_2024.csv',usecols=['entity_code'])['entity_code']))].copy()
key_ucdp=['sb_exist','sb_total_deaths_best','ns_exist','ns_total_deaths_best','os_exist','os_total_deaths_best']
ucdp_small=window[['entity_code','year_num']+key_ucdp].rename(columns={'year_num':'year'})
for c in key_ucdp: ucdp_small[c]=pd.to_numeric(ucdp_small[c],errors='coerce')
ucdp_small=ucdp_small.rename(columns={c:f'ucdp__{c}' for c in key_ucdp})

base_panel=pd.read_csv(GATE/'ANNUAL_PANEL_RAW_WDI_IMF_2000_2024.csv')
eia_pivot=eia_values.pivot_table(index=['entity_code','year'],columns='concept',values='value',aggfunc='first').reset_index()
eia_pivot=eia_pivot.rename(columns={'energy_consumption_per_capita':'eia__energy_consumption_per_capita','energy_consumption_per_gdp':'eia__energy_consumption_per_gdp'})
panel=base_panel.merge(eia_pivot,on=['entity_code','year'],how='left').merge(ucdp_small,on=['entity_code','year'],how='left')
panel_path=GATE/'ANNUAL_PANEL_RAW_WDI_IMF_UCDP_EIA_2000_2024.csv'
panel.to_csv(panel_path,index=False,encoding='utf-8')

# Candidate comparison: no environment monthly column in annual candidates.
base_cols=['wdi__NY.GDP.MKTP.KD.ZG','wdi__NY.GDP.PCAP.KD','wdi__FP.CPI.TOTL.ZG','wdi__SP.POP.TOTL','wdi__PA.NUS.PPP','imf__NGDP_RPCH','imf__PCPI','imf__PPPEX','imf__BCA_NGDPD']
eia_cols=['eia__energy_consumption_per_capita','eia__energy_consumption_per_gdp']
conf_cols=['ucdp__sb_exist','ucdp__sb_total_deaths_best','ucdp__ns_exist','ucdp__ns_total_deaths_best','ucdp__os_exist','ucdp__os_total_deaths_best']
sets={
 'macro_with_levels_previous':base_cols,
 'macro_plus_eia_energy':base_cols+eia_cols,
 'macro_plus_ucdp_conflict':base_cols+conf_cols,
 'macro_plus_eia_plus_ucdp':base_cols+eia_cols+conf_cols,
}
comparison={}
for name, cols in sets.items():
    expected=len(panel)*len(cols); observed=int(panel[cols].notna().sum().sum())
    full=(panel[cols].notna().all(axis=1).groupby(panel['entity_code']).all())
    anyv=(panel[cols].notna().any(axis=1).groupby(panel['entity_code']).any())
    comparison[name]={
      'variables':cols,'variable_count':len(cols),'rows':len(panel),'entity_count':int(panel.entity_code.nunique()),
      'expected_cells':expected,'observed_cells':observed,'missing_cells':expected-observed,'cell_coverage_ratio':ratio(observed,expected),
      'entities_with_any_value':int(anyv.sum()),'entities_complete_all_selected_variables_for_all_25_years':int(full.sum()),
      'no_transformations_or_imputation':True,
    }
comparison_meta={
 'scope':'Gap-augmented candidate comparison; annual columns only. NOAA GSOM PRCP remains a separate monthly layer and is not inserted.',
 'ucdp_country_name_mapping_exact_normalized_unique_count':len(ucdp_map),'ucdp_country_name_total':int(ucdp['country'].nunique()),
 'ucdp_window_rows_after_exact_mapping_to_common_panel':len(window),
 'eia_series_per_concept':int(eia_catalog.groupby('concept').size().min()) if not eia_catalog.empty else 0,
 'eia_country_count_per_concept':{k:int(v) for k,v in eia_catalog.groupby('concept')['geography'].nunique().to_dict().items()},
 'gsom_station_count':len(list(gsom_dir.glob('*.csv'))),
 'annual_panel_path':str(panel_path),'updated_matrix_path':str(updated_matrix),
 'comparison':comparison,'no_experiment_or_model':True,
}
(GATE/'CANDIDATE_MATRIX_COMPARISON_GAP_AUGMENTED.json').write_text(json.dumps(comparison_meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(GATE/'UCDP_COUNTRY_YEAR_PROFILE_GAP_AUGMENTED.json').write_text(json.dumps({
 'rows':len(ucdp),'columns':len(ucdp_fields),'country_id_count':int(ucdp.country_id.nunique()),'country_name_count':int(ucdp.country.nunique()),
 'year_range':[int(ucdp.year_num.min()),int(ucdp.year_num.max())],'exact_normalized_unique_wdi_mapping_count':len(ucdp_map),
 'key_fields':key_ucdp,'raw_path':str(ROOT/'raw/ucdp/country_year261/organizedviolencecy-261-csv.zip'),'staged_path':str(ucdp_path),
},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'base_rows':len(base_rows),'augmented_rows':len(augmented),'mapped_ucdp_countries':len(ucdp_map),'ucdp_total_countries':int(ucdp.country.nunique()),'panel_rows':len(panel),'outputs':[str(updated_matrix),str(panel_path),str(GATE/'CANDIDATE_MATRIX_COMPARISON_GAP_AUGMENTED.json')]},ensure_ascii=False,indent=2))
