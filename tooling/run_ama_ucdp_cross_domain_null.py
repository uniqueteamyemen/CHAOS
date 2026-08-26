#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from zipfile import ZipFile
import numpy as np,pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score
ROOT=Path('/home/ubuntu/CHAOS');AMA=ROOT/'catalog_first/readiness_gate/independent_sources/un_ama_2026/staged/UN_AMA_INDEPENDENT_GDP_GROWTH_POPULATION_PANEL.csv';Z=ROOT/'catalog_first/readiness_gate/independent_sources/ucdp_organized_violence_cy_26_1/raw/UCDP_ORGANIZED_VIOLENCE_CY_26_1_RAW.zip';OUT=ROOT/'experiments/macro_plus_eia_energy/ama_ucdp_cross_domain_v1';REPS=2000;SEED=2503;H=3
with ZipFile(Z) as z:
 with z.open(z.namelist()[0]) as f:U=pd.read_csv(f)
def norm(x):
 import re
 return re.sub(r'[^a-z0-9]+','',str(x).lower())
def main():
 a=pd.read_csv(AMA);a['year']=pd.to_numeric(a.year);a['country_key']=a.Country.map(norm);u=U.copy();u['year']=pd.to_numeric(u.year);u['country_key']=u.country.map(norm);u['country_id']=pd.to_numeric(u.country_id);u['sb_exist']=pd.to_numeric(u.sb_exist,errors='coerce');u['sb_total_deaths_best']=pd.to_numeric(u.sb_total_deaths_best,errors='coerce');u['state_based_conflict']=u.sb_exist.eq(1);u['state_based_high_fatality_25']=u.sb_total_deaths_best>=25;d=a.merge(u[['country_key','country_id','country','year','state_based_conflict','state_based_high_fatality_25']],on=['country_key','year'],how='inner');d['target_year']=d.year+H;d['future_state_conflict']=d.groupby('country_id')['state_based_conflict'].shift(-H);d['future_high_fatality_25']=d.groupby('country_id')['state_based_high_fatality_25'].shift(-H);d['high_growth']=d.ama_gdp_growth_pct>4; rng=np.random.default_rng(SEED);rows=[];obs=[]
 for outcome in ['future_state_conflict','future_high_fatality_25']:
  for split,(lo,hi) in {'validation':(2013,2016),'confirmation':(2017,2019)}.items():
   fr=d[d.target_year.between(lo,hi)&d.ama_gdp_growth_pct.notna()&d[outcome].notna()].copy();y=fr[outcome].astype(int).to_numpy();p=fr.high_growth.to_numpy();e=fr.country_id.to_numpy();oba=balanced_accuracy_score(y,p);of=f1_score(y,p,zero_division=0);obs.append({'outcome':outcome,'split':split,'observed_ba':oba,'observed_f1':of,'n':len(y)})
   for rep in range(REPS):
    yp=y.copy()
    for ent in np.unique(e):
     idx=np.flatnonzero(e==ent);yp[idx]=rng.permutation(yp[idx])
    rows.append({'outcome':outcome,'split':split,'replicate':rep,'null_ba':balanced_accuracy_score(yp,p) if len(np.unique(yp))>1 else .5,'null_f1':f1_score(yp,p,zero_division=0)})
 n=pd.DataFrame(rows);o=pd.DataFrame(obs);n.to_csv(OUT/'AMA_UCDP_CROSS_DOMAIN_NULL_REPLICATES.csv',index=False);o.to_csv(OUT/'AMA_UCDP_CROSS_DOMAIN_OBSERVED.csv',index=False);s=[]
 for _,ob in o.iterrows():
  g=n[(n.outcome==ob.outcome)&(n.split==ob.split)];s.append({'outcome':ob.outcome,'split':ob.split,'observed_ba':ob.observed_ba,'observed_f1':ob.observed_f1,'null_ba_mean':g.null_ba.mean(),'null_ba_q975':g.null_ba.quantile(.975),'null_f1_mean':g.null_f1.mean(),'null_f1_q975':g.null_f1.quantile(.975),'p_ba':(1+(g.null_ba>=ob.observed_ba).sum())/(REPS+1),'p_f1':(1+(g.null_f1>=ob.observed_f1).sum())/(REPS+1)})
 pd.DataFrame(s).to_csv(OUT/'AMA_UCDP_CROSS_DOMAIN_NULL_SUMMARY.csv',index=False);print(pd.DataFrame(s).to_string(index=False))
if __name__=='__main__':main()
