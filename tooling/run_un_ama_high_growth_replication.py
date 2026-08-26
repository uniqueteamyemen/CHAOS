#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score,precision_score,recall_score
ROOT=Path('/home/ubuntu/CHAOS'); PANEL=ROOT/'catalog_first/readiness_gate/independent_sources/un_ama_2026/staged/UN_AMA_INDEPENDENT_GDP_GROWTH_POPULATION_PANEL.csv'; OUT=ROOT/'experiments/macro_plus_eia_energy/un_ama_replication_v1';OUT.mkdir(parents=True,exist_ok=True)
RULE_T=4.0; H=3; SPLITS={'discovery_fit':(2003,2009),'discovery_inner':(2010,2012),'validation':(2013,2016),'confirmation':(2017,2019)}

def metric(name,y,p,fr):
 y=y.astype(int);p=p.astype(int);return {'model':name,'n_origins':len(y),'support':int(p.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,p,zero_division=0),'recall':recall_score(y,p,zero_division=0),'f1':f1_score(y,p,zero_division=0),'balanced_accuracy':balanced_accuracy_score(y,p) if len(np.unique(y))>1 else .5,'false_alarm_rate':float(((p==1)&(y==0)).sum()/(y==0).sum()) if (y==0).sum() else None,'entity_coverage':int(fr.loc[p.astype(bool),'CountryID'].nunique()) if p.any() else 0,'year_coverage':int(fr.loc[p.astype(bool),'target_year'].nunique()) if p.any() else 0}

def main():
 d=pd.read_csv(PANEL);d['year']=pd.to_numeric(d.year,errors='coerce');d['target_year']=d.year+H;d['future_growth']=d.groupby('CountryID')['ama_gdp_growth_pct'].shift(-H);d['material_drop_2pp']=(d.future_growth<=d.ama_gdp_growth_pct-2.0)
 # t-2 population is represented by an observed population value at year t-2; it is descriptive only and not used by the frozen high-growth rule.
 d['population_t_minus_2']=d.groupby('CountryID')['ama_population'].shift(2)
 rows=[];replay=[]
 for split,years in SPLITS.items():
  fr=d[d.target_year.between(*years)&d.ama_gdp_growth_pct.notna()&d.future_growth.notna()].copy();y=fr.material_drop_2pp.astype(int).to_numpy();p=(fr.ama_gdp_growth_pct.to_numpy()>RULE_T);rows.append({'split':split,**metric('high_growth_rule',y,p,fr)});replay.append(fr.assign(high_growth_rule=p,split=split))
  for n,pp in [('always_negative',np.zeros(len(fr),bool)),('always_positive',np.ones(len(fr),bool))]:rows.append({'split':split,**metric(n,y,pp,fr)})
 out=pd.DataFrame(rows);out.to_csv(OUT/'UN_AMA_REPLICATION_METRICS.csv',index=False);pd.concat(replay,ignore_index=True).to_csv(OUT/'UN_AMA_REPLICATION_REPLAY_ROWS.csv',index=False)
 by_country=[]
 for split,fr in [(x,pd.concat(replay,ignore_index=True).query('split==@x')) for x in SPLITS]:
  for c,g in fr.groupby('CountryID'):
   y=g.material_drop_2pp.astype(int).to_numpy();p=g.high_growth_rule.astype(int).to_numpy();by_country.append({'split':split,'CountryID':c,'Country':g.Country.iloc[0],**metric('high_growth_rule',y,p,g)})
 pd.DataFrame(by_country).to_csv(OUT/'UN_AMA_REPLICATION_METRICS_BY_COUNTRY.csv',index=False)
 s={'run_id':'un_ama_high_growth_replication_v1','source':'UN AMA January 2026','target':'ama_gdp_growth_pct','rule':'ama_gdp_growth_pct[t] > 4.0','outcome':'ama_gdp_growth_pct[t+3] <= ama_gdp_growth_pct[t] - 2pp','splits':SPLITS,'rows_total':len(d),'countries_total':int(d.CountryID.nunique()),'eligible_origins':int(sum(r['n_origins'] for r in rows if r['model']=='high_growth_rule')),'used_future_2020_2024':False,'prior_locked_test_reopened':False,'threshold_changed_after_metrics':False,'raw_modified':False,'imputation':False,'normalization':False,'causal_claims_permitted':False,'decision':'independent-source replication only; no operational promotion'}
 (OUT/'UN_AMA_REPLICATION_SUMMARY.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');print(json.dumps(s,ensure_ascii=False,indent=2));print(out.to_string(index=False))
if __name__=='__main__':main()
