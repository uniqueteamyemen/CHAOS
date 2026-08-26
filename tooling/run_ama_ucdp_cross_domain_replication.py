#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from zipfile import ZipFile
import json,re,hashlib
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score,precision_score,recall_score
ROOT=Path('/home/ubuntu/CHAOS'); AMA=ROOT/'catalog_first/readiness_gate/independent_sources/un_ama_2026/staged/UN_AMA_INDEPENDENT_GDP_GROWTH_POPULATION_PANEL.csv'; Z=ROOT/'catalog_first/readiness_gate/independent_sources/ucdp_organized_violence_cy_26_1/raw/UCDP_ORGANIZED_VIOLENCE_CY_26_1_RAW.zip'; OUT=ROOT/'experiments/macro_plus_eia_energy/ama_ucdp_cross_domain_v1';OUT.mkdir(parents=True,exist_ok=True)
H=3; RULE=4.0; SPLITS={'fit':(2003,2009),'inner':(2010,2012),'validation':(2013,2016),'confirmation':(2017,2019)}
def norm(x): return re.sub(r'[^a-z0-9]+','',str(x).lower())
def load_ucdp():
 with ZipFile(Z) as z:
  with z.open(z.namelist()[0]) as f:return pd.read_csv(f)
def metric(name,y,p,fr):
 y=y.astype(int);p=p.astype(int);return {'model':name,'n':len(y),'support':int(p.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,p,zero_division=0),'recall':recall_score(y,p,zero_division=0),'f1':f1_score(y,p,zero_division=0),'balanced_accuracy':balanced_accuracy_score(y,p) if len(np.unique(y))>1 else .5,'false_alarm_rate':float(((p==1)&(y==0)).sum()/(y==0).sum()) if (y==0).sum() else None,'countries':int(fr.country_id.nunique()) if p.any() else 0}
def main():
 ama=pd.read_csv(AMA); ama['year']=pd.to_numeric(ama.year);ama['country_key']=ama.Country.map(norm)
 u=load_ucdp();u['year']=pd.to_numeric(u.year);u['country_key']=u.country.map(norm);u['sb_exist']=pd.to_numeric(u.sb_exist,errors='coerce');u['sb_total_deaths_best']=pd.to_numeric(u.sb_total_deaths_best,errors='coerce')
 # Independent outcome families are native UCDP Country-Year facts, not annualized GED events.
 u['state_based_conflict']=u.sb_exist.eq(1);u['state_based_high_fatality_25']=u.sb_total_deaths_best>=25
 keys=ama[['country_key','Country']].drop_duplicates();matches=keys.merge(u[['country_key','country']].drop_duplicates(),on='country_key',how='left');matches.to_csv(OUT/'COUNTRY_NAME_MATCH_AUDIT.csv',index=False)
 d=ama.merge(u[['country_key','country_id','country','year','state_based_conflict','state_based_high_fatality_25','sb_total_deaths_best']],on=['country_key','year'],how='inner'); d['target_year']=d.year+H; d['future_state_conflict']=d.groupby('country_id')['state_based_conflict'].shift(-H); d['future_high_fatality_25']=d.groupby('country_id')['state_based_high_fatality_25'].shift(-H); d['high_growth']=(d.ama_gdp_growth_pct>RULE)
 rows=[];replay=[]
 for outcome in ['future_state_conflict','future_high_fatality_25']:
  for split,years in SPLITS.items():
   fr=d[d.target_year.between(*years)&d.ama_gdp_growth_pct.notna()&d[outcome].notna()].copy();y=fr[outcome].astype(int).to_numpy();p=fr.high_growth.to_numpy();rows.append({'outcome':outcome,'split':split,**metric('high_growth',y,p,fr)});replay.append(fr.assign(pred_high_growth=p,outcome_name=outcome,split=split))
   for n,pp in [('always_negative',np.zeros(len(fr),bool)),('always_positive',np.ones(len(fr),bool))]:rows.append({'outcome':outcome,'split':split,**metric(n,y,pp,fr)})
 out=pd.DataFrame(rows);out.to_csv(OUT/'AMA_UCDP_CROSS_DOMAIN_METRICS.csv',index=False);pd.concat(replay,ignore_index=True).to_csv(OUT/'AMA_UCDP_CROSS_DOMAIN_REPLAY_ROWS.csv',index=False)
 s={'run_id':'ama_ucdp_cross_domain_replication_v1','ama_source':'UN AMA January 2026','ucdp_source':'UCDP Organized Violence Country-Year 26.1','ama_rows':len(ama),'ucdp_rows':len(u),'matched_rows':len(d),'matched_countries':int(d.country_id.nunique()),'outcomes':['future_state_conflict','future_high_fatality_25'],'rule':'ama_gdp_growth_pct[t] > 4.0','horizon':3,'splits':SPLITS,'ged_daily_aggregated':False,'ucdp_country_year_native':True,'previous_ama_replication_test_reopened':False,'raw_modified':False,'imputation':False,'normalization':False,'causal_claims_permitted':False,'decision':'cross-domain exploratory replication; no operational promotion'}
 (OUT/'AMA_UCDP_CROSS_DOMAIN_SUMMARY.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');print(json.dumps(s,ensure_ascii=False,indent=2));print(out.to_string(index=False))
if __name__=='__main__':main()
