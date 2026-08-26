#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from zipfile import ZipFile
import json,re,hashlib
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS');AMA=ROOT/'catalog_first/readiness_gate/independent_sources/un_ama_2026/staged/UN_AMA_INDEPENDENT_GDP_GROWTH_POPULATION_PANEL.csv';UZ=ROOT/'catalog_first/readiness_gate/independent_sources/ucdp_organized_violence_cy_26_1/raw/UCDP_ORGANIZED_VIOLENCE_CY_26_1_RAW.zip';OUT=ROOT/'experiments/macro_plus_eia_energy/domain_state_v1';OUT.mkdir(parents=True,exist_ok=True)
def norm(x):return re.sub(r'[^a-z0-9]+','',str(x).lower())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def rec(pattern,domain,name,eid,t,freq,label,prob,obs,unc,refs):
 return {'pattern_id':pattern,'domain':domain,'entity_name':name,'entity_id':str(eid),'timestamp':str(int(t)),'native_frequency':freq,'state_label':label,'state_probability':float(prob),'source_observations':obs,'lead_profile':{},'uncertainty':unc,'failure_cases':[],'edge_status':'not_testable','evidence_refs':refs}
def main():
 a=pd.read_csv(AMA);a['year']=pd.to_numeric(a.year,errors='coerce');a=a[a.ama_gdp_growth_pct.notna()].copy();states=[]
 for r in a.itertuples():
  high=float(r.ama_gdp_growth_pct)>4.0;states.append(rec('AMA_HIGH_GROWTH_STATE_V1','economic',r.Country,r.CountryID,r.year,'annual','high_growth_gt_4pp' if high else 'non_high_growth',1.0 if high else 0.0,{'ama_gdp_growth_pct':float(r.ama_gdp_growth_pct)}, {'source':'UN AMA January 2026','state_probability_is_rule_score':True}, {'source_id':'UN_AMA_2026','raw_ref':'catalog_first/readiness_gate/independent_sources/un_ama_2026/raw','staged_ref':str(AMA.relative_to(ROOT))}))
 with ZipFile(UZ) as z:
  with z.open(z.namelist()[0]) as f:u=pd.read_csv(f)
 u['year']=pd.to_numeric(u.year,errors='coerce');u['sb_exist']=pd.to_numeric(u.sb_exist,errors='coerce');u['sb_total_deaths_best']=pd.to_numeric(u.sb_total_deaths_best,errors='coerce');u=u[u.year.notna()].copy()
 for r in u.itertuples():
  states.append(rec('UCDP_STATE_CONFLICT_STATE_V1','conflict',r.country,r.country_id,r.year,'annual','state_based_conflict_present' if r.sb_exist==1 else 'no_state_based_conflict',1.0 if r.sb_exist==1 else 0.0,{'sb_exist':int(r.sb_exist),'sb_total_deaths_best':float(r.sb_total_deaths_best)}, {'source':'UCDP Organized Violence Country-Year 26.1','measurement_note':'country-year native; not aggregated from GED'}, {'source_id':'UCDP_CY_26_1','raw_ref':'catalog_first/readiness_gate/independent_sources/ucdp_organized_violence_cy_26_1/raw','staged_ref':'catalog_first/readiness_gate/independent_sources/ucdp_organized_violence_cy_26_1/raw/UCDP_ORGANIZED_VIOLENCE_CY_26_1_RAW.zip'}))
  states.append(rec('UCDP_HIGH_FATALITY_STATE_V1','conflict',r.country,r.country_id,r.year,'annual','state_based_high_fatality_25_plus' if r.sb_total_deaths_best>=25 else 'below_25_best_deaths',1.0 if r.sb_total_deaths_best>=25 else 0.0,{'sb_total_deaths_best':float(r.sb_total_deaths_best),'sb_exist':int(r.sb_exist)}, {'source':'UCDP Organized Violence Country-Year 26.1','measurement_note':'best-estimate fatalities; country-year native'}, {'source_id':'UCDP_CY_26_1','raw_ref':'catalog_first/readiness_gate/independent_sources/ucdp_organized_violence_cy_26_1/raw','staged_ref':'catalog_first/readiness_gate/independent_sources/ucdp_organized_violence_cy_26_1/raw/UCDP_ORGANIZED_VIOLENCE_CY_26_1_RAW.zip'}))
 df=pd.DataFrame(states);df.to_json(OUT/'DOMAIN_STATES_V1.jsonl',orient='records',lines=True,force_ascii=False);df.to_csv(OUT/'DOMAIN_STATES_V1.csv',index=False)
 meta={'schema':'experimental_contracts/DOMAIN_STATE_SCHEMA_V1.json','records':len(df),'economic_records':int((df.domain=='economic').sum()),'conflict_records':int((df.domain=='conflict').sum()),'domains':sorted(df.domain.unique().tolist()),'native_frequencies':sorted(df.native_frequency.unique().tolist()),'state_probabilities_are_rule_scores':True,'future_outcome_used_in_state':False,'imputation':False,'normalization':False,'source_averaging':False,'raw_modified':False,'ama_sha256':sha(AMA),'ucdp_cy_zip_sha256':sha(UZ)}
 (OUT/'DOMAIN_STATE_BUILD_SUMMARY.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n');print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
