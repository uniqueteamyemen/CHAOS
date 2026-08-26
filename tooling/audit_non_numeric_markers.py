from pathlib import Path
import json
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS')
M=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_140_RAW_2000_2024_WIDE.csv'
df=pd.read_csv(M,dtype={'entity_code':str})
contract=json.loads((ROOT/'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1.json').read_text(encoding='utf-8'))
vars=[contract['target']['id']]+[x['id'] for x in contract['input_columns']['exogenous_covariates']]
rows=[]
for c in vars:
 s=pd.to_numeric(df[c],errors='coerce')
 bad=df.loc[s.isna() & df[c].notna(),['entity_code','year',c]].copy()
 for _,r in bad.iterrows(): rows.append({'variable':c,'entity_code':str(r['entity_code']),'year':int(r['year']),'raw_value':str(r[c])})
summary={'rows':len(rows),'by_variable':{},'sample':rows[:100]}
for r in rows: summary['by_variable'][r['variable']]=summary['by_variable'].get(r['variable'],0)+1
(ROOT/'experiments/macro_plus_eia_energy/NON_NUMERIC_MARKER_AUDIT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
