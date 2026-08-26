#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score,precision_score,recall_score
from run_regime_size_substitutes import SIZE_SPECS,TARGET_THRESHOLDS,FOLDS,H,FAMILY
from explore_tree_reverse_extraction import TARGET,build_origins,load_panel
ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/macro_plus_eia_energy/regime_entity_holdout_v1'
ENTITY_FOLDS=5

def ba(y,p):
 return balanced_accuracy_score(y,p) if len(np.unique(y))>1 else 0.5

def main():
 OUT.mkdir(parents=True,exist_ok=True);o=build_origins(load_panel(),H);o['target_current']=o[f'{TARGET}__lag0'];label=f'outcome_{FAMILY}'
 entities=sorted(o.entity_code.dropna().unique().tolist(),key=str); assign={e:int(hashlib.sha256(str(e).encode()).hexdigest()[:8],16)%ENTITY_FOLDS for e in entities};o['entity_holdout_fold']=o.entity_code.map(assign)
 specs=[]
 for var,(col,ths) in SIZE_SPECS.items():
  for tt in TARGET_THRESHOLDS:
   for ts in ths:specs.append((var,col,tt,ts))
 rows=[]
 for fold,fy,iy,vy in FOLDS:
  # Use the later pre-test years as evaluation; the entity split is independent of time.
  frame=o[o.target_year.between(*vy)&o[label].notna()&o.target_current.notna()].copy()
  for ef in range(ENTITY_FOLDS):
   sub=frame[frame.entity_holdout_fold==ef].copy()
   if sub.empty: continue
   y=sub[label].astype(int).to_numpy();e=sub.entity_code.to_numpy();yr=sub.target_year.to_numpy()
   for var,col,tt,ts in specs:
    p=((sub.target_current>tt)&(sub[col]<=ts)).to_numpy();rows.append({'time_fold':fold,'entity_holdout_fold':ef,'variant':var,'threshold_target':tt,'threshold_size':ts,'n_origins':len(sub),'support':int(p.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,p,zero_division=0),'recall':recall_score(y,p,zero_division=0),'f1':f1_score(y,p,zero_division=0),'balanced_accuracy':ba(y,p),'entity_count':int(np.unique(e).size),'year_coverage':int(np.unique(yr).size)})
 result=pd.DataFrame(rows);result.to_csv(OUT/'ENTITY_HOLDOUT_METRICS.csv',index=False)
 agg=result.groupby(['variant','threshold_target','threshold_size']).agg(mean_ba=('balanced_accuracy','mean'),sd_ba=('balanced_accuracy','std'),mean_f1=('f1','mean'),mean_support=('support','mean'),entity_folds_with_support=('support',lambda x:int((x>=10).sum())),groups=('support','size')).reset_index();agg.to_csv(OUT/'ENTITY_HOLDOUT_AGGREGATE.csv',index=False)
 best_by=[]
 for var,g in agg.groupby('variant'):
  r=g.sort_values(['mean_ba','mean_f1'],ascending=False).iloc[0];best_by.append(r.to_dict())
 summary={'run_id':'regime_entity_holdout_v1','horizon':H,'family':FAMILY,'entity_folds':ENTITY_FOLDS,'time_folds':len(FOLDS),'grid_cells':len(specs),'entity_assignment':'sha256(entity_code) mod 5, fixed before metrics','best_cell_by_variant':best_by,'locked_test_executed':False,'raw_data_modified':False,'imputation':False,'normalization':False,'decision':'entity-holdout descriptive robustness; no promotion'}
 (OUT/'ENTITY_HOLDOUT_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2));print(agg.sort_values(['mean_ba','mean_f1'],ascending=False).groupby('variant').head(5).to_string(index=False))
if __name__=='__main__':main()
