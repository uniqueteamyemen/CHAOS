#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,zipfile
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); ZIP=ROOT/'catalog_first/readiness_gate/independent_sources/worldbank_wgi_2025/raw/WGI_CSV.zip'; OUT=ROOT/'campaigns/agents/institutions_policy_v1'; OUT.mkdir(parents=True,exist_ok=True)
def main():
 with zipfile.ZipFile(ZIP) as zf:
  with zf.open('WGICSV.csv') as f: wide=pd.read_csv(f)
 estimates=wide[wide['Indicator Code'].astype(str).str.endswith('.EST')].copy(); year_cols=[c for c in estimates.columns if str(c).isdigit()]
 rows=[]
 for _,r in estimates.iterrows():
  for y in year_cols:
   v=r[y]
   if pd.isna(v): continue
   rows.append({'pattern_id':f"WGI_INSTITUTIONAL_MEASUREMENT_{r['Indicator Code']}_V1",'domain':'institutions_policy','entity_id':r['Country Code'],'entity_name':r['Country Name'],'timestamp':int(y),'native_frequency':'annual_source_defined_years','state_label':'institutional_measurement_observed','state_probability':None,'source_observations':{'indicator_id':r['Indicator Code'],'indicator_name':r['Indicator Name'],'value_raw':v},'lead_profile':{},'uncertainty':['WGI is a composite perception-based governance measure','source methodology and historical recalculation apply'],'failure_cases':['not a dated policy shock','not a leader-specific deviation','no causal inference'],'edge_status':'not_testable','evidence_refs':['WGI_CSV.zip/WGICSV.csv']})
 out=OUT/'WGI_INSTITUTIONAL_DOMAIN_STATES_ANNUAL_SOURCE_YEARS_V1.jsonl'
 with out.open('w',encoding='utf8') as f:
  for x in rows:f.write(json.dumps(x,ensure_ascii=False)+'\n')
 summary={'adapter_id':'INSTITUTIONS_POLICY_WGI_ADAPTER_V1','source_raw':str(ZIP.relative_to(ROOT)),'source_sha256':hashlib.sha256(ZIP.read_bytes()).hexdigest(),'indicator_rows':int(len(estimates)),'estimate_domain_states':len(rows),'entities':int(estimates['Country Code'].nunique()),'source_years':sorted(int(x) for x in year_cols),'native_frequency':'annual_source_defined_years','policy_shock_states':0,'leader_specific_deviation_states':0,'imputation':False,'normalization':False,'raw_modified':False,'status':'institutional_measurement_only'}
 (OUT/'WGI_ADAPTER_RUN_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
