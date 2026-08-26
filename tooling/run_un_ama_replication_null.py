#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score
ROOT=Path('/home/ubuntu/CHAOS'); PANEL=ROOT/'catalog_first/readiness_gate/independent_sources/un_ama_2026/staged/UN_AMA_INDEPENDENT_GDP_GROWTH_POPULATION_PANEL.csv'; OUT=ROOT/'experiments/macro_plus_eia_energy/un_ama_replication_v1'; REPS=2000; SEED=2489; H=3

def main():
 d=pd.read_csv(PANEL);d['year']=pd.to_numeric(d.year);d['target_year']=d.year+H;d['future_growth']=d.groupby('CountryID')['ama_gdp_growth_pct'].shift(-H);d['outcome']=(d.future_growth<=d.ama_gdp_growth_pct-2.0)
 folds={'validation':(2013,2016),'confirmation':(2017,2019)}; rng=np.random.default_rng(SEED); rows=[]; obs=[]
 for split,years in folds.items():
  fr=d[d.target_year.between(*years)&d.ama_gdp_growth_pct.notna()&d.future_growth.notna()].copy();y=fr.outcome.astype(int).to_numpy();p=(fr.ama_gdp_growth_pct.to_numpy()>4.0);e=fr.CountryID.to_numpy();obs.append({'split':split,'observed_ba':balanced_accuracy_score(y,p),'observed_f1':f1_score(y,p,zero_division=0),'n':len(y)})
  for rep in range(REPS):
   yp=y.copy()
   for ent in np.unique(e):
    idx=np.flatnonzero(e==ent);yp[idx]=rng.permutation(yp[idx])
   rows.append({'split':split,'replicate':rep,'null_ba':balanced_accuracy_score(yp,p) if len(np.unique(yp))>1 else .5,'null_f1':f1_score(yp,p,zero_division=0)})
 null=pd.DataFrame(rows);null.to_csv(OUT/'UN_AMA_REPLICATION_NULL_REPLICATES.csv',index=False);o=pd.DataFrame(obs);o.to_csv(OUT/'UN_AMA_REPLICATION_OBSERVED.csv',index=False)
 summaries=[]
 for split,g in null.groupby('split'):
  ob=o[o.split==split].iloc[0];summaries.append({'split':split,'replicates':len(g),'observed_ba':ob.observed_ba,'observed_f1':ob.observed_f1,'null_ba_mean':g.null_ba.mean(),'null_ba_q975':g.null_ba.quantile(.975),'null_f1_mean':g.null_f1.mean(),'null_f1_q975':g.null_f1.quantile(.975),'p_ba':(1+(g.null_ba>=ob.observed_ba).sum())/(REPS+1),'p_f1':(1+(g.null_f1>=ob.observed_f1).sum())/(REPS+1)})
 s=pd.DataFrame(summaries);s.to_csv(OUT/'UN_AMA_REPLICATION_NULL_SUMMARY.csv',index=False);print(s.to_string(index=False))
if __name__=='__main__':main()
