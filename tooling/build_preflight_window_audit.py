from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT=Path('/home/ubuntu/CHAOS')
MATRIX=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
CONTRACT=ROOT/'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1_1.json'
OUT=ROOT/'experimental_contracts'

def sha(path):
 h=hashlib.sha256();
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
 return h.hexdigest()

contract=json.loads(CONTRACT.read_text(encoding='utf-8'))
N_ENTITIES=contract['matrix']['numeric_complete_entity_count']
df=pd.read_csv(MATRIX,dtype={'entity_code':str})
target=contract['target']['id']
all_vars=contract['features']
exog=[c for c in all_vars if c != target]
enc_len=contract['encoder_length']
rows=[]
for entity,g in df.groupby('entity_code',sort=True):
 g=g.sort_values('year').reset_index(drop=True)
 years=set(g['year'].astype(int))
 for origin in range(2005,2024):
  target_year=origin+1
  enc_years=list(range(origin-enc_len+1,origin+1))
  split='train' if 2006<=target_year<=2015 else 'validation' if 2016<=target_year<=2019 else 'test' if 2020<=target_year<=2024 else 'out'
  if split=='out': continue
  rows.append({'entity_code':entity,'origin_year':origin,'encoder_years':';'.join(map(str,enc_years)),'target_year':target_year,'split':split,'encoder_min':enc_years[0],'encoder_max':enc_years[-1],'target_outside_encoder':target_year not in enc_years,'all_encoder_years_present':all(y in years for y in enc_years),'target_year_present':target_year in years})
windows=pd.DataFrame(rows)
window_path=OUT/'WINDOW_MANIFEST_PRE_TRAIN_V1_1.csv'; windows.to_csv(window_path,index=False)
checks={
 'matrix_rows': {'expected':N_ENTITIES*25,'observed':len(df),'pass':len(df)==N_ENTITIES*25},
 'entity_count': {'expected':N_ENTITIES,'observed':int(df.entity_code.nunique()),'pass':int(df.entity_code.nunique())==N_ENTITIES},
 'variable_count': {'expected':11,'observed':len(all_vars),'pass':all(c in df.columns for c in all_vars)},
 'missing_cells': {'observed':int(df[all_vars].isna().sum().sum()),'pass':int(df[all_vars].isna().sum().sum())==0},
 'duplicate_entity_year': {'observed':int(df.duplicated(['entity_code','year']).sum()),'pass':int(df.duplicated(['entity_code','year']).sum())==0},
 'duplicate_windows': {'observed':int(windows.duplicated(['entity_code','origin_year']).sum()),'pass':int(windows.duplicated(['entity_code','origin_year']).sum())==0},
 'encoder_target_firewall': {'violations':int((~windows.target_outside_encoder).sum()),'pass':bool(windows.target_outside_encoder.all())},
 'encoder_presence': {'violations':int((~windows.all_encoder_years_present).sum()),'pass':bool(windows.all_encoder_years_present.all())},
 'target_presence': {'violations':int((~windows.target_year_present).sum()),'pass':bool(windows.target_year_present.all())},
 'chronological_split': {'pass': all(windows.groupby('split').target_year.min().to_dict().get(k,0) < windows.groupby('split').target_year.max().to_dict().get(k,1)+1 for k in ['train','validation','test'])},
}
counts=windows.groupby('split').size().to_dict()
expected={'train':N_ENTITIES*10,'validation':N_ENTITIES*4,'test':N_ENTITIES*5}
checks['split_counts']={'observed':counts,'expected':expected,'pass':counts==expected}
result={'matrix_sha256':sha(MATRIX),'contract_sha256':sha(CONTRACT),'window_manifest':str(window_path.relative_to(ROOT)),'checks':checks,'all_pass':all(x['pass'] for x in checks.values()),'training_run':False}
(OUT/'PRE_TRAIN_INTEGRITY_LEAKAGE_AUDIT_V1_1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
