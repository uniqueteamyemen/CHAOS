#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from run_regime_size_substitutes import SIZE_SPECS,TARGET_THRESHOLDS,FOLDS,H,FAMILY
from explore_tree_reverse_extraction import TARGET,build_origins,load_panel
ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/macro_plus_eia_energy/regime_size_substitutes_v1'; REPS=2000; SEED=1397

def main():
 o=build_origins(load_panel(),H);o['target_current']=o[f'{TARGET}__lag0'];label=f'outcome_{FAMILY}'
 fold_data=[]; obs=[]; specs=[]
 for var,(col,ths) in SIZE_SPECS.items():
  for tt in TARGET_THRESHOLDS:
   for ts in ths: specs.append((var,col,tt,ts))
 for fold,fy,iy,vy in FOLDS:
  fr=o[o.target_year.between(*vy)&o[label].notna()&o.target_current.notna()].copy(); y=fr[label].astype(int).to_numpy(); e=fr.entity_code.to_numpy();
  P=np.stack([((fr.target_current>tt)&(fr[col]<=ts)).to_numpy() for _,col,tt,ts in specs])
  fold_data.append((fr,y,e,P))
  for j,(var,col,tt,ts) in enumerate(specs):
   p=P[j]; yb=y.astype(bool); pos=yb.sum();neg=len(y)-pos; ba=(p[yb].mean() if pos else 0)+((~p[~yb]).mean() if neg else 0); obs.append({'variant':var,'threshold_target':tt,'threshold_size':ts,'fold':fold,'ba':ba/2})
 obs=pd.DataFrame(obs);agg=obs.groupby(['variant','threshold_target','threshold_size']).ba.mean().reset_index(name='observed_mean_ba');best=agg.loc[agg.observed_mean_ba.idxmax()]
 rng=np.random.default_rng(SEED);rows=[]
 for rep in range(REPS):
  fold_max=[]
  for fr,y,e,P in fold_data:
   yp=y.copy()
   for ent in np.unique(e):
    idx=np.flatnonzero(e==ent);yp[idx]=rng.permutation(yp[idx])
   pos=yp.sum();neg=len(yp)-pos
   tpr=(P[:,yp.astype(bool)].sum(axis=1)/pos) if pos else np.zeros(P.shape[0]); tnr=((~P[:,~yp.astype(bool)]).sum(axis=1)/neg) if neg else np.zeros(P.shape[0]); fold_max.append((tpr+tnr)/2)
  max_mean=np.mean(np.stack(fold_max),axis=0).max();rows.append({'replicate':rep,'max_mean_ba':float(max_mean)})
 null=pd.DataFrame(rows);null.to_csv(OUT/'SIZE_SUBSTITUTE_MAXSTAT_NULL_REPLICATES.csv',index=False)
 s={'run_id':'regime_size_substitutes_maxstat_null_v1_fast','grid_cells':len(specs),'replicates':REPS,'seed':SEED,'observed_best_cell':best.to_dict(),'null_max_mean_ba_mean':float(null.max_mean_ba.mean()),'null_max_mean_ba_q025':float(null.max_mean_ba.quantile(.025)),'null_max_mean_ba_q500':float(null.max_mean_ba.quantile(.5)),'null_max_mean_ba_q975':float(null.max_mean_ba.quantile(.975)),'p_best_cell_max_stat':float((1+(null.max_mean_ba>=best.observed_mean_ba).sum())/(REPS+1)),'locked_test_executed':False,'raw_data_modified':False,'imputation':False,'normalization':False,'decision':'proxy-and-threshold grid max-statistic only; no promotion'}
 (OUT/'SIZE_SUBSTITUTE_MAXSTAT_NULL_SUMMARY.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');print(json.dumps(s,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
