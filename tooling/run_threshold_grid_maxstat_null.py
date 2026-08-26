#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from explore_tree_reverse_extraction import TARGET, build_origins, load_panel
from run_threshold_grid_stability import TARGET_THRESHOLDS, POP_THRESHOLDS, FOLDS, H, FAMILY

ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/macro_plus_eia_energy/threshold_grid_v1'; REPS=2000; SEED=1181

def ba(y,p):
 y=y.astype(bool); p=p.astype(bool); pos=y.sum(); neg=(~y).sum(); return ((p[y].mean() if pos else 0)+((~p[~y]).mean() if neg else 0))/2

def main():
 origins=build_origins(load_panel(),H); origins['pop_lag2']=origins['wdi__SP_POP_TOTL__lag2']; origins['target_current']=origins[f'{TARGET}__lag0']; label=f'outcome_{FAMILY}'
 fold_data=[]; obs_rows=[]
 for fold,fit_y,inner_y,val_y in FOLDS:
  frame=origins[origins.target_year.between(*val_y)&origins[label].notna()&origins.target_current.notna()&origins.pop_lag2.notna()].copy(); y=frame[label].astype(int).to_numpy(); e=frame.entity_code.to_numpy();
  fold_data.append((fold,frame,y,e))
  for tt in TARGET_THRESHOLDS:
   for tp in POP_THRESHOLDS:
    p=((frame.target_current>tt)&(frame.pop_lag2<=tp)).to_numpy(); obs_rows.append({'threshold_target':tt,'threshold_population':tp,'fold':fold,'ba':ba(y,p),'f1':None})
 obs=pd.DataFrame(obs_rows); agg=obs.groupby(['threshold_target','threshold_population']).ba.mean().reset_index(name='observed_mean_ba'); best=agg.loc[agg.observed_mean_ba.idxmax()];
 rng=np.random.default_rng(SEED); null_rows=[]
 for rep in range(REPS):
  means=[]
  for tt in TARGET_THRESHOLDS:
   for tp in POP_THRESHOLDS:
    vals=[]
    for fold,frame,y,e in fold_data:
     yp=y.copy()
     for ent in np.unique(e):
      idx=np.flatnonzero(e==ent); yp[idx]=rng.permutation(yp[idx])
     p=((frame.target_current>tt)&(frame.pop_lag2<=tp)).to_numpy(); vals.append(ba(yp,p))
    means.append(float(np.mean(vals)))
  null_rows.append({'replicate':rep,'max_mean_ba':max(means)})
 null=pd.DataFrame(null_rows); null.to_csv(OUT/'THRESHOLD_GRID_MAXSTAT_NULL_REPLICATES.csv',index=False)
 summary={'run_id':'threshold_grid_maxstat_null_v1','grid_cells':len(TARGET_THRESHOLDS)*len(POP_THRESHOLDS),'replicates':REPS,'seed':SEED,'observed_best_cell':best.to_dict(),'null_max_mean_ba_mean':float(null.max_mean_ba.mean()),'null_max_mean_ba_q025':float(null.max_mean_ba.quantile(.025)),'null_max_mean_ba_q500':float(null.max_mean_ba.quantile(.5)),'null_max_mean_ba_q975':float(null.max_mean_ba.quantile(.975)),'p_best_cell_max_stat':float((1+(null.max_mean_ba>=best.observed_mean_ba).sum())/(REPS+1)),'locked_test_executed':False,'raw_data_modified':False,'decision':'grid max-statistic only; no promotion'}
 (OUT/'THRESHOLD_GRID_MAXSTAT_NULL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
