#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, hashlib
import numpy as np, pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score
ROOT=Path('/home/ubuntu/CHAOS')
SRC=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
OUT=ROOT/'experiments/macro_plus_eia_energy/within_domain_edges_v1'; OUT.mkdir(parents=True,exist_ok=True)
SEED=20260826; REPS=2000
EDGES={
 'high_inflation_to_deterioration':lambda d: d['wdi__FP.CPI.TOTL.ZG']>10.0,
 'current_account_stress_to_deterioration':lambda d: d['imf__BCA_NGDPD']<=-5.0,
 'energy_intensity_increase_to_deterioration':lambda d: d['eia__energy_consumption_per_gdp']>d['energy_prev']
}
SPLITS={'fit':(2006,2015),'validation':(2016,2019),'confirmation':(2020,2024)}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def metric(y,p):
 return {'balanced_accuracy':balanced_accuracy_score(y,p),'f1':f1_score(y,p,zero_division=0),'precision':precision_score(y,p,zero_division=0),'recall':recall_score(y,p,zero_division=0),'prevalence':float(np.mean(y)),'n':int(len(y))}
def main():
 df=pd.read_csv(SRC); df['energy_prev']=df.groupby('entity_code')['eia__energy_consumption_per_gdp'].shift(1)
 rows=[]
 for h in (1,2,3):
  x=df.copy(); x['target_year']=x['year']+h
  future=df[['entity_code','year','wdi__NY.GDP.MKTP.KD.ZG']].rename(columns={'year':'target_year','wdi__NY.GDP.MKTP.KD.ZG':'gdp_future'})
  x=x.merge(future,on=['entity_code','target_year'],how='left'); x['y']=x['gdp_future']<=x['wdi__NY.GDP.MKTP.KD.ZG']-2.0
  for edge,fn in EDGES.items():
   pred=fn(x)
   ybase=x['y'].notna() & pred.notna()
   if edge=='energy_intensity_increase_to_deterioration': ybase &= x['energy_prev'].notna()
   for split,(lo,hi) in SPLITS.items():
    z=x[ybase & x['target_year'].between(lo,hi)].copy(); y=z['y'].astype(int).to_numpy(); p=pred[z.index].astype(int).to_numpy()
    m=metric(y,p); rows.append({'edge_id':edge,'horizon_years':h,'split':split,'source_rule':{'high_inflation_to_deterioration':'wdi__FP.CPI.TOTL.ZG > 10','current_account_stress_to_deterioration':'imf__BCA_NGDPD <= -5','energy_intensity_increase_to_deterioration':'eia__energy_consumption_per_gdp[t] > eia__energy_consumption_per_gdp[t-1]'}[edge],**m})
  # baseline is intentionally reported for comparison, not selected post hoc
  z=x[x['y'].notna() & x['target_year'].between(2006,2024)].copy(); z['base']=z['wdi__NY.GDP.MKTP.KD.ZG']>4.0
  for split,(lo,hi) in SPLITS.items():
   q=z[z['target_year'].between(lo,hi)]; rows.append({'edge_id':'high_growth_gt_4_existing_baseline','horizon_years':h,'split':split,'source_rule':'wdi__NY.GDP.MKTP.KD.ZG > 4','**baseline':None,**metric(q['y'].astype(int),q['base'].astype(int))})
 metrics=pd.DataFrame(rows); metrics.to_csv(OUT/'WITHIN_DOMAIN_EDGE_METRICS.csv',index=False)
 # null: permute target labels within entity; max statistic across edges/horizons/splits
 base=[]
 prepared={}
 for h in (1,2,3):
  x=df.copy(); x['energy_prev']=df.groupby('entity_code')['eia__energy_consumption_per_gdp'].shift(1); x['target_year']=x['year']+h
  future=df[['entity_code','year','wdi__NY.GDP.MKTP.KD.ZG']].rename(columns={'year':'target_year','wdi__NY.GDP.MKTP.KD.ZG':'gdp_future'}); x=x.merge(future,on=['entity_code','target_year'],how='left'); x['y']=x['gdp_future']<=x['wdi__NY.GDP.MKTP.KD.ZG']-2.0
  prepared[h]=x
 for _,r in metrics[metrics.edge_id!='high_growth_gt_4_existing_baseline'].iterrows(): base.append((r.edge_id,int(r.horizon_years),r.split))
 rng=np.random.default_rng(SEED); null=[]
 for rep in range(REPS):
  maxstat=-np.inf
  for h in (1,2,3):
   x=prepared[h];    yp=x['y'].astype('float').to_numpy(); valid=x['y'].notna().to_numpy() & x['energy_prev'].notna().to_numpy()
   perm=yp.copy()
   for _,idx in x[valid].groupby('entity_code').groups.items():
    vals=perm[idx].copy(); rng.shuffle(vals); perm[idx]=vals
   for edge,fn in EDGES.items():
    pred=fn(x).to_numpy(); okay=valid & np.isfinite(pred)
    for split,(lo,hi) in SPLITS.items():
     mask=okay & x['target_year'].between(lo,hi).to_numpy()
     if mask.sum()>0: maxstat=max(maxstat,balanced_accuracy_score(perm[mask].astype(int),pred[mask].astype(int)))
  null.append({'replicate':rep+1,'max_balanced_accuracy':maxstat})
 null_df=pd.DataFrame(null); null_df.to_csv(OUT/'WITHIN_DOMAIN_EDGE_MAXSTAT_NULL_REPLICATES.csv',index=False)
 observed=metrics[metrics.edge_id!='high_growth_gt_4_existing_baseline'].copy(); obsmax=float(observed.balanced_accuracy.max()); p=float((1+(null_df.max_balanced_accuracy>=obsmax).sum())/(REPS+1)); summary={'contract_ref':'experimental_contracts/WITHIN_DOMAIN_EDGE_CONTRACT_V1.json','source':str(SRC.relative_to(ROOT)),'source_sha256':sha(SRC),'replicates':REPS,'seed':SEED,'observed_max_balanced_accuracy':obsmax,'maxstat_p_value':p,'edges_tested':sorted(metrics.edge_id.unique().tolist()),'horizons':[1,2,3],'splits':SPLITS,'raw_data_modified':False,'imputation':False,'transformations':False,'native_frequency':'annual','causal_claims_permitted':False,'status':'research_evidence_only'}
 (OUT/'WITHIN_DOMAIN_EDGE_MAXSTAT_NULL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
