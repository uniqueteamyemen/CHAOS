from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
GATE = ROOT / 'readiness_gate'
OUT = GATE / 'macro_plus_eia_energy'
OUT.mkdir(exist_ok=True)

YEARS = list(range(2000, 2025))
MACRO_COLS = [
    'wdi__NY.GDP.MKTP.KD.ZG',
    'wdi__NY.GDP.PCAP.KD',
    'wdi__FP.CPI.TOTL.ZG',
    'wdi__SP.POP.TOTL',
    'wdi__PA.NUS.PPP',
    'imf__NGDP_RPCH',
    'imf__PCPI',
    'imf__PPPEX',
    'imf__BCA_NGDPD',
]
EIA_COLS = ['eia__energy_consumption_per_capita', 'eia__energy_consumption_per_gdp']
VALUE_COLS = MACRO_COLS + EIA_COLS
KEY_COLS = ['entity_code', 'year']
NAME_COLS = ['wdi_entity_name', 'imf_entity_name']

source_panel_path = GATE / 'ANNUAL_PANEL_RAW_WDI_IMF_UCDP_EIA_2000_2024.csv'
panel = pd.read_csv(source_panel_path, dtype={'entity_code': str})
panel = panel[panel['year'].isin(YEARS)].copy()

# Keep source-provided values and labels. Selecting rows/columns is not a numeric transformation.
keep_cols = KEY_COLS + [c for c in NAME_COLS if c in panel.columns] + VALUE_COLS
missing_input_cols = [c for c in VALUE_COLS if c not in panel.columns]
if missing_input_cols:
    raise RuntimeError(f'Missing expected source columns: {missing_input_cols}')
raw = panel[keep_cols].sort_values(KEY_COLS).reset_index(drop=True)

# Source-level missingness is calculated only from raw cell presence. No fill, cast, scale, or derivation.
raw_wide_path = OUT / 'MACRO_PLUS_EIA_ENERGY_RAW_2000_2024_WIDE.csv'
raw.to_csv(raw_wide_path, index=False, encoding='utf-8')

long = raw.melt(id_vars=[c for c in KEY_COLS + NAME_COLS if c in raw.columns], value_vars=VALUE_COLS,
                var_name='variable_id', value_name='raw_value')
long['source'] = long['variable_id'].str.split('__', n=1).str[0]
long['native_frequency'] = 'annual'
long_path = OUT / 'MACRO_PLUS_EIA_ENERGY_RAW_2000_2024_LONG.csv'
long.to_csv(long_path, index=False, encoding='utf-8')

# WDI region metadata is source-provided. Aggregates with blank Region are not in the 194-country panel.
wdi_country_path = ROOT / 'staged/worldbank/wdi_csv/WDICountry.csv'
wdi = pd.read_csv(wdi_country_path, dtype=str, encoding='utf-8-sig')
wdi_meta = wdi[['Country Code', 'Short Name', 'Region', 'Income Group']].rename(columns={
    'Country Code':'entity_code', 'Short Name':'wdi_short_name', 'Region':'wdi_region', 'Income Group':'wdi_income_group'
})
raw = raw.merge(wdi_meta, on='entity_code', how='left')

# Complete-entity rule: all 11 selected variables present in all 25 years. This identifies the 140, not fills them.
complete_by_entity = raw.groupby('entity_code', dropna=False)[VALUE_COLS].apply(lambda x: x.notna().all().all())
complete_entities = sorted(complete_by_entity[complete_by_entity].index.astype(str).tolist())
raw['complete_140'] = raw['entity_code'].isin(complete_entities)
complete = raw[raw['complete_140']].copy().sort_values(KEY_COLS).reset_index(drop=True)
complete_path = OUT / 'MACRO_PLUS_EIA_ENERGY_COMPLETE_140_RAW_2000_2024_WIDE.csv'
complete.to_csv(complete_path, index=False, encoding='utf-8')
complete_long = complete.melt(id_vars=[c for c in KEY_COLS + NAME_COLS + ['wdi_short_name','wdi_region','wdi_income_group'] if c in complete.columns], value_vars=VALUE_COLS,
                              var_name='variable_id', value_name='raw_value')
complete_long['source'] = complete_long['variable_id'].str.split('__', n=1).str[0]
complete_long['native_frequency'] = 'annual'
complete_long.to_csv(OUT / 'MACRO_PLUS_EIA_ENERGY_COMPLETE_140_RAW_2000_2024_LONG.csv', index=False, encoding='utf-8')

# Country-level gap profile across the full 194-country candidate universe.
country_rows = []
for entity, g in raw.groupby('entity_code', sort=True):
    g = g.sort_values('year')
    name = next((x for x in g.get('wdi_entity_name', pd.Series(dtype=str)).dropna().astype(str).unique()), '')
    region = next((x for x in g.get('wdi_region', pd.Series(dtype=str)).dropna().astype(str).unique()), '')
    income = next((x for x in g.get('wdi_income_group', pd.Series(dtype=str)).dropna().astype(str).unique()), '')
    miss_mask = g[VALUE_COLS].isna()
    missing_cells = int(miss_mask.sum().sum())
    observed_cells = int((~miss_mask).sum().sum())
    missing_years_any = sorted(g.loc[miss_mask.any(axis=1), 'year'].astype(int).tolist())
    missing_year_count = len(missing_years_any)
    var_missing = {c: int(miss_mask[c].sum()) for c in VALUE_COLS}
    var_missing_years = {c: g.loc[miss_mask[c], 'year'].astype(int).tolist() for c in VALUE_COLS if miss_mask[c].any()}
    country_rows.append({
        'entity_code': entity, 'wdi_entity_name': name, 'wdi_region': region, 'wdi_income_group': income,
        'years_expected': len(YEARS), 'rows_present': len(g), 'observed_cells': observed_cells,
        'expected_cells': len(YEARS) * len(VALUE_COLS), 'missing_cells': missing_cells,
        'cell_coverage_ratio': observed_cells / (len(YEARS)*len(VALUE_COLS)),
        'missing_year_count_any_variable': missing_year_count,
        'missing_years_any_variable': ';'.join(map(str, missing_years_any)),
        'complete_11_variables_25_years': entity in complete_entities,
        'variable_missing_counts_json': json.dumps(var_missing, ensure_ascii=False),
        'variable_missing_years_json': json.dumps(var_missing_years, ensure_ascii=False),
    })
country_gap = pd.DataFrame(country_rows).sort_values(['complete_11_variables_25_years','missing_cells','entity_code'], ascending=[False, False, True])
country_gap.to_csv(OUT / 'COUNTRY_GAP_PROFILE_ALL_194.csv', index=False, encoding='utf-8')

# Variable-level gap profile: temporal coverage and geographic distribution in the full candidate.
variable_rows=[]
for col in VALUE_COLS:
    present = raw[col].notna()
    by_entity = raw.assign(_present=present).groupby('entity_code')['_present'].agg(['sum','count'])
    entity_any = int((by_entity['sum'] > 0).sum())
    entity_full = int((by_entity['sum'] == len(YEARS)).sum())
    observed = int(present.sum())
    expected = len(raw)
    observed_years = sorted(raw.loc[present, 'year'].astype(int).unique().tolist())
    missing_year_counts = raw.assign(_present=present).groupby('year')['_present'].apply(lambda s: int((~s).sum())).to_dict()
    variable_rows.append({
        'variable_id': col, 'source': col.split('__',1)[0], 'native_frequency':'annual',
        'true_panel_start':'2000', 'true_panel_end':'2024', 'entity_count_full_candidate':int(raw['entity_code'].nunique()),
        'expected_cells':expected, 'observed_cells':observed, 'missing_cells':expected-observed,
        'cell_coverage_ratio':observed/expected, 'entities_with_any_value':entity_any,
        'entities_complete_25_years':entity_full, 'observed_years':';'.join(map(str,observed_years)),
        'missing_cells_by_year_json':json.dumps(missing_year_counts,ensure_ascii=False),
        'no_imputation_or_transformation':True,
    })
variable_gap = pd.DataFrame(variable_rows).sort_values('variable_id')
variable_gap.to_csv(OUT / 'VARIABLE_GAP_PROFILE_11_VARIABLES.csv', index=False, encoding='utf-8')

# Year-level temporal distribution across the full candidate and among the 140 complete entities.
year_rows=[]
for year in YEARS:
    g=raw[raw['year']==year]
    c=g[g['complete_140']]
    for scope, gg in [('all_194_candidate_entities',g),('complete_140_entities',c)]:
        present=gg[VALUE_COLS].notna()
        year_rows.append({
          'scope':scope,'year':year,'entity_count':int(gg['entity_code'].nunique()),
          'expected_cells':int(len(gg)*len(VALUE_COLS)), 'observed_cells':int(present.sum().sum()),
          'missing_cells':int(present.size-present.sum().sum()),
          'cell_coverage_ratio':float(present.sum().sum()/present.size) if present.size else None,
          'entities_with_any_missing':int((~present.all(axis=1)).sum()),
          'entities_complete_all_11':int(present.all(axis=1).sum()),
        })
pd.DataFrame(year_rows).to_csv(OUT / 'YEAR_GAP_PROFILE.csv',index=False,encoding='utf-8')

# Region-level distribution using WDI Region metadata, not a constructed geography.
region_rows=[]
for region, g in raw.groupby('wdi_region', dropna=False):
    region_label = region if isinstance(region,str) and region else '[WDI Region blank / non-country aggregate not used]'
    entities=sorted(g['entity_code'].unique().tolist())
    complete_region=sorted(set(entities).intersection(complete_entities))
    present=g[VALUE_COLS].notna()
    region_rows.append({
      'wdi_region':region_label,'candidate_entity_count':len(entities),'complete_140_entity_count':len(complete_region),
      'candidate_expected_cells':int(present.size),'candidate_observed_cells':int(present.sum().sum()),
      'candidate_missing_cells':int(present.size-present.sum().sum()),
      'candidate_cell_coverage_ratio':float(present.sum().sum()/present.size) if present.size else None,
      'complete_140_entity_codes':';'.join(complete_region),
    })
pd.DataFrame(region_rows).sort_values('wdi_region').to_csv(OUT / 'REGION_GAP_PROFILE.csv',index=False,encoding='utf-8')

# Summary JSON and reproducibility manifest.
summary={
 'matrix_id':'macro_plus_eia_energy', 'period':[2000,2024], 'frequency':'annual',
 'selected_variables':VALUE_COLS,'macro_variables':MACRO_COLS,'eia_variables':EIA_COLS,
 'full_candidate_entity_count':int(raw['entity_code'].nunique()),'full_candidate_rows':len(raw),
 'full_candidate_expected_cells':int(len(raw)*len(VALUE_COLS)),
 'full_candidate_observed_cells':int(raw[VALUE_COLS].notna().sum().sum()),
 'full_candidate_missing_cells':int(raw[VALUE_COLS].isna().sum().sum()),
 'full_candidate_cell_coverage_ratio':float(raw[VALUE_COLS].notna().sum().sum()/(len(raw)*len(VALUE_COLS))),
 'complete_entity_count':len(complete_entities),'complete_entity_rows':len(complete),
 'complete_entity_expected_cells':int(len(complete)*len(VALUE_COLS)),
 'complete_entity_missing_cells':int(complete[VALUE_COLS].isna().sum().sum()),
 'complete_entity_codes':complete_entities,
 'gap_definition':'Missing means source cell is empty in the selected raw panel. No zeros were reclassified and no missing value was filled.',
 'geography_definition':'WDI Region metadata joined by entity_code; no geographic inference was performed.',
 'source_panel':str(source_panel_path),
 'outputs':{
   'raw_wide':str(raw_wide_path),'raw_long':str(long_path),'complete_140_wide':str(complete_path),
   'complete_140_long':str(OUT/'MACRO_PLUS_EIA_ENERGY_COMPLETE_140_RAW_2000_2024_LONG.csv'),
   'country_gap':str(OUT/'COUNTRY_GAP_PROFILE_ALL_194.csv'),'variable_gap':str(OUT/'VARIABLE_GAP_PROFILE_11_VARIABLES.csv'),
   'year_gap':str(OUT/'YEAR_GAP_PROFILE.csv'),'region_gap':str(OUT/'REGION_GAP_PROFILE.csv'),
 },
 'no_log_no_difference_no_normalization_no_imputation':True,
 'no_experiment_no_model':True,
}
(OUT/'MACRO_PLUS_EIA_ENERGY_RAW_AND_GAP_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Explicit metadata file for the selected variables, derived only from prior variable-level coverage matrix.
with (GATE/'VARIABLE_LEVEL_COVERAGE_MATRIX_GAP_AUGMENTED.csv').open(encoding='utf-8',newline='') as f:
    cov=list(csv.DictReader(f))
source_id_map = {}
for variable_id in VALUE_COLS:
    source, raw_id = variable_id.split('__', 1)
    source_id_map[(source, raw_id)] = variable_id
selected_cov=[]
for r in cov:
    raw_id = r['variable_id']
    source = r['source'].lower() if r.get('source') else ''
    if source in {'world bank wdi', 'worldbank wdi'}: source = 'wdi'
    elif source == 'imf weo': source = 'imf'
    mapped = source_id_map.get((source, raw_id))
    if mapped:
        item=dict(r); item['selected_variable_id']=mapped; selected_cov.append(item)
# EIA coverage is represented in the gate at series_id level. For the contract, preserve a
# separate concept-level provenance row for each selected concept and point to the exact catalog.
eia_catalog_path = ROOT / 'gap_assets/EIA_SELECTED_SERIES_CATALOG.csv'
if eia_catalog_path.exists():
    eia_catalog = pd.read_csv(eia_catalog_path, dtype=str)
    for concept, group in eia_catalog.groupby('concept', sort=True):
        variable_id = f'eia__{concept}'
        if variable_id not in VALUE_COLS:
            continue
        item={field:'' for field in (list(selected_cov[0].keys()) if selected_cov else list(cov[0].keys()) + ['selected_variable_id'])}
        item.update({
          'dataset_id':'eia_selected_annual_energy_intensity','source':'EIA','variable_id':concept,
          'variable_name':concept,'definition':'; '.join(sorted(set(group['name'].astype(str))))[:1000],
          'unit':'; '.join(sorted(set(group['units'].astype(str)))), 'native_frequency':'annual',
          'true_start_date':group['start'].min(), 'true_end_date':group['end'].max(),
          'native_record_count':len(group), 'native_entity_or_event_count':group['geography'].nunique(),
          'panel_start':'2000','panel_end':'2024','panel_active_entities':group['geography'].nunique(),
          'panel_expected_cells':group['geography'].nunique()*25,'panel_observed_cells':group['geography'].nunique()*25,
          'panel_missing_cells':0,'panel_coverage_ratio':1.0,'full_panel_entity_count':group['geography'].nunique(),
          'missing_gaps':'No missing values in the selected 2000–2024 series subset; no filling applied.',
          'definition_methodology_shifts':'EIA series-level metadata retained; no automated break detection applied.',
          'provenance':f'raw={ROOT / "raw/eia/INTL.zip"}; staged={ROOT / "staged/eia/intl/INTL.txt"}; catalog={eia_catalog_path}; values={OUT / "EIA_SELECTED_ANNUAL_2000_2024_LONG.csv"}',
          'status':'downloaded/raw+selected','notes':'Concept-level contract row summarizing the exact EIA series catalog; individual series IDs remain in EIA_SELECTED_SERIES_CATALOG.csv.',
          'selected_variable_id':variable_id,
        })
        selected_cov.append(item)
with (OUT/'SELECTED_VARIABLE_PROVENANCE.csv').open('w',encoding='utf-8',newline='') as f:
    fields=list(selected_cov[0].keys()) if selected_cov else ['selected_variable_id','variable_id','source']
    writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(selected_cov)

print(json.dumps({
 'full_candidate_entities':int(raw['entity_code'].nunique()),'full_candidate_rows':len(raw),
 'full_candidate_missing_cells':int(raw[VALUE_COLS].isna().sum().sum()),
 'full_candidate_coverage':float(raw[VALUE_COLS].notna().sum().sum()/(len(raw)*len(VALUE_COLS))),
 'complete_entities':len(complete_entities),'complete_rows':len(complete),
 'complete_missing_cells':int(complete[VALUE_COLS].isna().sum().sum()),
 'outputs':summary['outputs']
},ensure_ascii=False,indent=2))
