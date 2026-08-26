#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score,precision_score,recall_score
ROOT=Path('/home/ubuntu/CHAOS');P=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv';OUT=ROOT/'experiments/macro_plus_eia_energy/energy_mediator_v1';OUT.mkdir(parents=True,exist_ok=True)
TARGET='wdi__NY.GDP.MKTP.KD.ZG';ENERGY='eia__energy_consumption_per_gdp';H=3;SEED=2701;REPS=2000;SPLITS={'fit':(2006,2009),'inner':(2010,2012),'validation':(2013,2016),'confirmation':(2017,2019)}
def metric(name,y,p,fr):
 y=y.astype(int);p=p.astype(int);return {'path_id':name,'n':len(y),'support':int(p.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,p,zero_division=0),'recall':recall_score(y,p,zero_division=0),'f1':f1_score(y,p,zero_division=0),'balanced_accuracy':balanced_accuracy_score(y,p) if len(np.unique(y))>1 else .5,'entity_coverage':int(fr.loc[p.astype(bool),'entity_code'].nunique()) if p.any() else 0}
def main():
 d=pd.read_csv(P);d['year']=pd.to_numeric(d.year);d['target_year']=d.year+H;g=d.groupby('entity_code',sort=False);d['target_future']=g[TARGET].shift(-H);d['material_drop_2pp']=d.target_future<=d[TARGET]-2.0;d['high_growth_t']=d[TARGET]>4.0;rows=[];replay=[]
 specs=[]
 for lag in [1,2]:
  for direction in ['up','down']:
   pid=f'energy_gdp_{direction}_at_t_plus_{lag}'
   future=g[ENERGY].shift(-lag);delta=future-d[ENERGY];cond=delta>0 if direction=='up' else delta<0;d[pid]=d.high_growth_t & cond;specs.append((pid,lag,direction))
 for split,(lo,hi) in SPLITS.items():
  fr=d[d.target_year.between(lo,hi)&d[TARGET].notna()&d.target_future.notna()&d[ENERGY].notna()].copy();y=fr.material_drop_2pp.astype(int).to_numpy();
  for pid,lag,direction in specs:
   fr2=fr[fr[pid].notna()].copy();p=fr2[pid].astype(bool).to_numpy();yy=fr2.material_drop_2pp.astype(int).to_numpy();rows.append({'split':split,'family':'energy_mediator','lag_years':lag,'direction':direction,**metric(pid,yy,p,fr2)});replay.append(fr2.assign(path_id=pid,split=split,pred=p))
  p=fr.high_growth_t.to_numpy();rows.append({'split':split,'family':'baseline','lag_years':0,'direction':'none',**metric('high_growth_only',y,p,fr)})
 out=pd.DataFrame(rows);out.to_csv(OUT/'ENERGY_MEDIATOR_PATH_METRICS.csv',index=False);pd.concat(replay,ignore_index=True).to_csv(OUT/'ENERGY_MEDIATOR_REPLAY_ROWS.csv',index=False)
 # max-stat null on the four fixed mediator paths, per split
 rng=np.random.default_rng(SEED);null_rows=[];obs_rows=[]
 for split,(lo,hi) in {'validation':(2013,2016),'confirmation':(2017,2019)}.items():
  fr=d[d.target_year.between(lo,hi)&d[TARGET].notna()&d.target_future.notna()&d[ENERGY].notna()].copy();y=fr.material_drop_2pp.astype(int).to_numpy();e=fr.entity_code.to_numpy();vals=[]
  for pid,lag,direction in specs:
   idx=fr[pid].notna().to_numpy();yy=y[idx];pp=fr.loc[idx,pid].astype(bool).to_numpy();vals.append((pid,balanced_accuracy_score(yy,pp),f1_score(yy,pp,zero_division=0)))
  best=max(vals,key=lambda x:x[1]);obs_rows.append({'split':split,'observed_best_path':best[0],'observed_best_ba':best[1],'observed_best_f1':best[2]})
  for rep in range(REPS):
   yp=y.copy()
   for ent in np.unique(e):
    idx=np.flatnonzero(e==ent);yp[idx]=rng.permutation(yp[idx])
   best_ba=-1;best_f1=-1
   for pid,lag,direction in specs:
    idx=fr[pid].notna().to_numpy();pp=fr.loc[idx,pid].astype(bool).to_numpy();v=yp[idx];ba=balanced_accuracy_score(v,pp) if len(np.unique(v))>1 else .5;f=f1_score(v,pp,zero_division=0);best_ba=max(best_ba,ba);best_f1=max(best_f1,f)
   null_rows.append({'split':split,'replicate':rep,'max_null_ba':best_ba,'max_null_f1':best_f1})
 n=pd.DataFrame(null_rows);o=pd.DataFrame(obs_rows);n.to_csv(OUT/'ENERGY_MEDIATOR_MAXSTAT_NULL_REPLICATES.csv',index=False);o.to_csv(OUT/'ENERGY_MEDIATOR_OBSERVED_BEST.csv',index=False);s=[]
 for _,r in o.iterrows():
  z=n[n.split==r.split];s.append({'split':r.split,'observed_best_path':r.observed_best_path,'observed_best_ba':r.observed_best_ba,'observed_best_f1':r.observed_best_f1,'null_max_ba_mean':z.max_null_ba.mean(),'null_max_ba_q975':z.max_null_ba.quantile(.975),'null_max_f1_mean':z.max_null_f1.mean(),'null_max_f1_q975':z.max_null_f1.quantile(.975),'p_ba':(1+(z.max_null_ba>=r.observed_best_ba).sum())/(REPS+1),'p_f1':(1+(z.max_null_f1>=r.observed_best_f1).sum())/(REPS+1)})
 ss=pd.DataFrame(s);ss.to_csv(OUT/'ENERGY_MEDIATOR_MAXSTAT_NULL_SUMMARY.csv',index=False);summary={'run_id':'energy_mediator_paths_v1','source':'macro_plus_eia_energy v1.1','target':TARGET,'mediator':ENERGY,'outcome':'material_drop_2pp_at_t_plus_3','paths':len(specs),'path_specs':[{'path_id':x[0],'lag_years':x[1],'direction':x[2]} for x in specs],'splits':SPLITS,'null_replicates':REPS,'used_locked_test':False,'raw_modified':False,'imputation':False,'normalization':False,'causal_claims_permitted':False,'interpretation':'conditional mediator-path exploration; mediator is observed at t+lag and is not a t-origin early warning'}
 (OUT/'ENERGY_MEDIATOR_RUN_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(out.to_string(index=False));print(ss.to_string(index=False))
if __name__=='__main__':main()
