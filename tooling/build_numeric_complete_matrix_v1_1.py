from pathlib import Path
import json
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS')
SRC=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_RAW_2000_2024_WIDE.csv'
OUTDIR=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy'
PROFILE=ROOT/'experiments/macro_plus_eia_energy/NUMERIC_COMPLETENESS_PROFILE.json'
contract=json.loads((ROOT/'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1.json').read_text(encoding='utf-8'))
vars=[contract['target']['id']]+[x['id'] for x in contract['input_columns']['exogenous_covariates']]
profile=pd.DataFrame(json.loads(PROFILE.read_text(encoding='utf-8')))
keep=profile.loc[profile.numeric_complete,'entity_code'].astype(str).tolist()
df=pd.read_csv(SRC,dtype={'entity_code':str})
selected=df[df.entity_code.isin(keep)].sort_values(['entity_code','year']).reset_index(drop=True)
if len(keep)!=139 or len(selected)!=139*25: raise RuntimeError(f'Unexpected numeric-complete matrix size: entities={len(keep)}, rows={len(selected)}')
if selected[vars].apply(pd.to_numeric,errors='coerce').isna().sum().sum()!=0: raise RuntimeError('Numeric completeness failed after selection')
out=OUTDIR/'MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
selected.to_csv(out,index=False)
summary={'source_raw':str(SRC.relative_to(ROOT)),'output':str(out.relative_to(ROOT)),'entities':len(keep),'rows':len(selected),'years':[2000,2024],'variables':len(vars),'missing_cells':int(selected[vars].apply(pd.to_numeric,errors='coerce').isna().sum().sum()),'excluded_entities':[e for e in df.entity_code.unique() if e not in keep],'selection_rule':'numeric coercion only; no imputation, no transformation, no value replacement'}
(OUTDIR/'NUMERIC_COMPLETE_MATRIX_V1_1_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
