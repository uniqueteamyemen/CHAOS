#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score
from run_high_growth_outcome_families import prep,FOLDS,HORIZONS,TARGET,TARGET_THRESHOLD
ROOT=Path('/home/ubuntu/CHAOS');OUT=ROOT/'experiments/macro_plus_eia_energy/high_growth_outcomes_v1';REPS=2000;SEED=2401
FAMILY_NAMES=['contraction','onset_contraction','material_drop_2pp','deterioration','adverse_tail_q10','any_contraction','persistent_contraction']

def main():
 df=prep(); specs=[]; folds=[]; obs=[]
 for h in HORIZONS:
  dfx=df.assign(target_year=df.year+h)
  for family in FAMILY_NAMES:
   col=f'{family}_{h}'
   specs.append((family,h,col))
   for fold,fy,iy,vy in FOLDS:
    fr=dfx[dfx.target_year.between(*vy)&dfx[col].notna()&dfx[TARGET].notna()].copy();y=fr[col].astype(int).to_numpy();p=(fr[TARGET].to_numpy()>TARGET_THRESHOLD);e=fr.entity_code.to_numpy();folds.append((len(folds),family,h,col,fr,y,p,e));
    if len(np.unique(y))>1: obs.append({'family':family,'horizon':h,'fold':fold,'ba':balanced_accuracy_score(y,p),'f1':f1_score(y,p,zero_division=0)})
 od=pd.DataFrame(obs);agg=od.groupby(['family','horizon']).agg(observed_mean_ba=('ba','mean'),observed_mean_f1=('f1','mean')).reset_index();
 rng=np.random.default_rng(SEED);null=[]
 for rep in range(REPS):
  vals_ba=[];vals_f1=[]
  for family,h,col in specs:
   b=[];f=[]
   for _,fam,hh,cc,fr,y,p,e in [x for x in folds if x[1]==family and x[2]==h]:
    yp=y.copy()
    for ent in np.unique(e):
     idx=np.flatnonzero(e==ent);yp[idx]=rng.permutation(yp[idx])
    b.append(balanced_accuracy_score(yp,p) if len(np.unique(yp))>1 else .5);f.append(f1_score(yp,p,zero_division=0))
   vals_ba.append(np.mean(b));vals_f1.append(np.mean(f))
  null.append({'replicate':rep,'max_mean_ba':max(vals_ba),'max_mean_f1':max(vals_f1)})
 nd=pd.DataFrame(null);nd.to_csv(OUT/'HIGH_GROWTH_OUTCOME_MAXSTAT_NULL.csv',index=False);best_ba=agg.loc[agg.observed_mean_ba.idxmax()];best_f1=agg.loc[agg.observed_mean_f1.idxmax()]
 s={'run_id':'high_growth_outcome_families_v1','rule':'target[t] > 4.0','spec_count':len(specs),'families':FAMILY_NAMES,'horizons':list(HORIZONS),'folds':list(FOLDS),'best_by_ba':best_ba.to_dict(),'best_by_f1':best_f1.to_dict(),'null_replicates':REPS,'null_max_mean_ba_mean':float(nd.max_mean_ba.mean()),'null_max_mean_ba_q975':float(nd.max_mean_ba.quantile(.975)),'null_max_mean_f1_mean':float(nd.max_mean_f1.mean()),'null_max_mean_f1_q975':float(nd.max_mean_f1.quantile(.975)),'p_best_ba_maxstat':float((1+(nd.max_mean_ba>=best_ba.observed_mean_ba).sum())/(REPS+1)),'p_best_f1_maxstat':float((1+(nd.max_mean_f1>=best_f1.observed_mean_f1).sum())/(REPS+1)),'locked_test_reopened':False,'raw_data_modified':False,'imputation':False,'normalization':False,'decision':'outcome-family exploratory only; prior locked test remains closed'}
 (OUT/'HIGH_GROWTH_OUTCOME_RUN_SUMMARY.json').write_text(json.dumps(s,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(s,ensure_ascii=False,indent=2));print(agg.sort_values('observed_mean_ba',ascending=False).to_string(index=False))
if __name__=='__main__':main()
