from pathlib import Path
import json
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS')
M=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_RAW_2000_2024_WIDE.csv'
OUT=ROOT/'experiments/macro_plus_eia_energy'
contract=json.loads((ROOT/'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1.json').read_text(encoding='utf-8'))
vars=[contract['target']['id']]+[x['id'] for x in contract['input_columns']['exogenous_covariates']]
df=pd.read_csv(M,dtype={'entity_code':str})
rows=[]
for e,g in df.groupby('entity_code',sort=True):
 good=True; bad=[]
 for c in vars:
  numeric=pd.to_numeric(g[c],errors='coerce')
  if numeric.isna().any() or len(numeric)!=25:
   good=False; bad.append({'variable':c,'bad_cells':int(numeric.isna().sum())})
 rows.append({'entity_code':e,'numeric_complete':good,'bad_variables':bad})
prof=pd.DataFrame(rows)
prof.to_json(OUT/'NUMERIC_COMPLETENESS_PROFILE.json',orient='records',force_ascii=False,indent=2)
complete=prof[prof.numeric_complete].entity_code.tolist()
print(json.dumps({'full_entities':len(prof),'numeric_complete_entities':len(complete),'numeric_complete_codes':complete,'incomplete':[r for r in rows if not r['numeric_complete']]},ensure_ascii=False,indent=2))
