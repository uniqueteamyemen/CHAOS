#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json,hashlib,gzip
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS')
WHO=ROOT/'catalog_first/readiness_gate/independent_sources/who_covid_2026/raw/WHO_COVID_GLOBAL_DAILY_RAW.csv'
USGS=ROOT/'catalog_first/readiness_gate/independent_sources/usgs_earthquake_2026/raw/USGS_EARTHQUAKE_M6_5_2000_2024_RAW.csv'
OUT=ROOT/'experiments/multi_domain_native_adapters_v1'; OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 who=pd.read_csv(WHO)
 who['New_cases_num']=pd.to_numeric(who['New_cases'],errors='coerce'); who['New_deaths_num']=pd.to_numeric(who['New_deaths'],errors='coerce')
 reported=who[who['New_cases_num'].notna() | who['New_deaths_num'].notna()].copy()
 states=[]
 for r in reported.itertuples(index=False):
  states.append({'pattern_id':'WHO_PANDEMIC_REPORTED_ACTIVITY_V1','domain':'health_pandemic','entity_id':r.Country_code,'entity_name':r.Country,'timestamp':r.Date_reported,'native_frequency':'daily','state_label':'pandemic_reported_activity','state_probability':None,'source_observations':{'new_cases_raw':None if pd.isna(r.New_cases) else r.New_cases,'new_deaths_raw':None if pd.isna(r.New_deaths) else r.New_deaths,'new_cases_numeric':None if pd.isna(r.New_cases_num) else float(r.New_cases_num),'new_deaths_numeric':None if pd.isna(r.New_deaths_num) else float(r.New_deaths_num)},'lead_profile':{},'uncertainty':['date is date reported to WHO','reporting definitions and retrospective revisions vary'],'failure_cases':['blank values were not converted to zero','no causal or economic shock inferred'] ,'edge_status':'not_testable','evidence_refs':['WHO_COVID_GLOBAL_DAILY_RAW.csv']})
 with gzip.open(OUT/'WHO_COVID_DOMAIN_STATES_DAILY_V1.jsonl.gz','wt',encoding='utf-8') as f:
  for x in states:f.write(json.dumps(x,ensure_ascii=False)+'\n')
 eq=pd.read_csv(USGS)
 est=[]
 for r in eq.itertuples(index=False):
  est.append({'pattern_id':'USGS_EARTHQUAKE_MAG_GE_6_5_EVENT_V1','domain':'environmental','entity_id':str(r.id),'entity_name':str(r.place),'timestamp':r.time,'native_frequency':'event','state_label':'earthquake_magnitude_ge_6_5','state_probability':None,'source_observations':{'latitude':r.latitude,'longitude':r.longitude,'depth':r.depth,'magnitude':r.mag,'magnitude_type':r.magType,'status':r.status,'place':r.place,'event_type':r.type},'lead_profile':{},'uncertainty':['scoped query minmagnitude=6.5','country attribution absent from source output'],'failure_cases':['no production shock inferred','no country matching performed'],'edge_status':'not_testable','evidence_refs':['USGS_EARTHQUAKE_M6_5_2000_2024_RAW.csv']})
 with (OUT/'USGS_EARTHQUAKE_DOMAIN_STATES_EVENT_V1.jsonl').open('w',encoding='utf-8') as f:
  for x in est:f.write(json.dumps(x,ensure_ascii=False)+'\n')
 summary={'adapter_run_id':'CHAOS_NATIVE_HEALTH_DISASTER_ADAPTERS_V1','who':{'raw':str(WHO.relative_to(ROOT)),'sha256':sha(WHO),'raw_rows':int(len(who)),'rows_with_reported_case_or_death':int(len(reported)),'entities':int(reported.Country_code.nunique()),'start':str(reported.Date_reported.min()),'end':str(reported.Date_reported.max()),'native_frequency':'daily','imputation':False},'usgs':{'raw':str(USGS.relative_to(ROOT)),'sha256':sha(USGS),'events':int(len(eq)),'start':str(eq.time.min()),'end':str(eq.time.max()),'native_frequency':'event','country_matching':False},'annualization':False,'production_shock_inferred':False,'event_to_annual_edge_status':'not_testable','causal_claims_permitted':False}
 (OUT/'NATIVE_ADAPTERS_RUN_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
