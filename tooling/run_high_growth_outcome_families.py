#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score,precision_score,recall_score
from explore_tree_reverse_extraction import TARGET,load_panel

ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/macro_plus_eia_energy/high_growth_outcomes_v1'; OUT.mkdir(parents=True,exist_ok=True)
HORIZONS=(1,2,3); FOLDS=(('fold_A',(2006,2010),(2011,2013),(2014,2016)),('fold_B',(2006,2012),(2013,2015),(2016,2019)),('fold_C',(2007,2011),(2012,2014),(2015,2018)))
RULE='target[t] > 4.0'; TARGET_THRESHOLD=4.0

def prep():
 df=load_panel(); g=df.groupby('entity_code')[TARGET]
 for h in (1,2,3):
  df[f'future_{h}']=g.shift(-h)
  df[f'any_contraction_{h}']=False
  vals=[g.shift(-k) for k in range(1,h+1)]
  df[f'any_contraction_{h}']=pd.concat(vals,axis=1).min(axis=1)<0
  df[f'persistent_contraction_{h}']=pd.concat(vals,axis=1).max(axis=1)<0
  df[f'contraction_{h}']=df[f'future_{h}']<0
  df[f'onset_contraction_{h}']=(df[TARGET]>=0)&(df[f'future_{h}']<0)
  df[f'material_drop_2pp_{h}']=df[f'future_{h}']<=df[TARGET]-2.0
  df[f'deterioration_{h}']=df[f'future_{h}']<df[TARGET]
 # fit-only q10 for each horizon
 for h in HORIZONS:
  f=df[df.year.between(2003,2012)][f'future_{h}'].dropna(); q=float(f.quantile(.10)); df[f'adverse_tail_q10_{h}']=df[f'future_{h}']<=q
 return df

def metric(y,p,frame):
 return {'n_origins':len(y),'support':int(p.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,p,zero_division=0),'recall':recall_score(y,p,zero_division=0),'f1':f1_score(y,p,zero_division=0),'balanced_accuracy':balanced_accuracy_score(y,p) if len(np.unique(y))>1 else .5,'false_alarm_rate':float(((p==1)&(y==0)).sum()/(y==0).sum()) if (y==0).sum() else None,'entity_coverage':int(frame.loc[p,'entity_code'].nunique()) if p.any() else 0,'year_coverage':int(frame.loc[p,'target_year'].nunique()) if p.any() else 0}

def main():
 df=prep(); specs=[]
 for h in HORIZONS:
  for family in ['contraction','onset_contraction','material_drop_2pp','deterioration','adverse_tail_q10','any_contraction','persistent_contraction']:
   specs.append((family,h,f'{family}_{h}'))
 rows=[]
 for family,h,col in specs:
  for fold,fy,iy,vy in FOLDS:
   for split,years in [('fit',fy),('inner',iy),('validation',vy)]:
    dfx=df.assign(target_year=df.year+h); fr=dfx[dfx.target_year.between(*years)&dfx[col].notna()&dfx[TARGET].notna()].copy(); y=fr[col].astype(int).to_numpy(); p=(fr[TARGET].to_numpy()>TARGET_THRESHOLD); rows.append({'family':family,'horizon':h,'rule':RULE,'fold':fold,'split':split,**metric(y,p,fr)})
 result=pd.DataFrame(rows); result.to_csv(OUT/'HIGH_GROWTH_OUTCOME_METRICS.csv',index=False)
 val=result[result.split=='validation']; agg=val.groupby(['family','horizon']).agg(validation_ba_mean=('balanced_accuracy','mean'),validation_ba_sd=('balanced_accuracy','std'),validation_f1_mean=('f1','mean'),validation_support_mean=('support','mean'),folds_with_support=('support',lambda x:int((x>=20).sum())),folds_ba_above_055=('balanced_accuracy',lambda x:int((x>0.55).sum()))).reset_index(); agg.to_csv(OUT/'HIGH_GROWTH_OUTCOME_AGGREGATE.csv',index=False)
 # Predeclare null over full 21-spec grid; compare max mean BA and max mean F1.
 rng=np.random.default_rng(2401); null=[]
 for rep in range(2000):
  means_ba=[]; means_f1=[]
  for family,h,col in specs:
   vals_ba=[]; vals_f1=[]
   for fold,fy,iy,vy in FOLDS:
    dfx=df.assign(target_year=df.year+h)
    fr=dfx[dfx.target_year.between(*vy)&dfx[col].notna()&dfx[TARGET].notna()].copy()
    y=fr[col].astype(int).to_numpy(); e=fr.entity_code.to_numpy(); yp=y.copy()
    for ent in np.unique(e):
     idx=np.flatnonzero(e==ent); yp[idx]=rng.permutation(yp[idx])
    p=(fr[TARGET].to_numpy()>TARGET_THRESHOLD)
    vals_ba.append(balanced_accuracy_score(yp,p) if len(np.unique(yp))>1 else .5)
    vals_f1.append(f1_score(yp,p,zero_division=0))
   means_ba.append(np.mean(vals_ba)); means_f1.append(np.mean(vals_f1))
  null.append({'replicate':rep,'max_mean_ba':max(means_ba),'max_mean_f1':max(means_f1)})
 null_df=pd.DataFrame(null);null_df.to_csv(OUT/'HIGH_GROWTH_OUTCOME_MAXSTAT_NULL.csv',index=False)
 best_ba=agg.loc[agg.validation_ba_mean.idxmax()];best_f1=agg.loc[agg.validation_f1_mean.idxmax()]
 s={'run_id':'high_growth_outcome_families_v1','rule':RULE,'target_threshold':TARGET_THRESHOLD,'spec_count':len(specs),'families':sorted(set(x[0] for x in specs)),'horizons':list(HORIZONS),'folds':list(FOLDS),'best_by_ba':best_ba.to_dict(),'best_by_f1':best_f1.to_dict(),'null_replicates':2000,'null_max_mean_ba_mean':float(null_df.max_mean_ba.mean()),'null_max_mean_ba_q975':float(null_df.max_mean_ba.quantile(.975)),'null_max_mean_f1_mean':float(null_df.max_mean_f1.mean()),'null_max_mean_f1_q975':float(null_df.max_mean_f1.quantile(.975)),'p_best_ba_maxstat':float((1+(null_df.max_mean_ba>=best_ba.validation_ba_mean).sum())/2001),'p_best_f1_maxstat':float((1+(null_df.max_mean_f1>=best_f1.validation_f1_mean).sum())/2001),'locked_test_reopened':False,'raw_data_modified':False,'imputation':False,'normalization':False,'decision':'outcome-family exploratory only; prior locked test remains closed'}
 (OUT/'HIGH_GROWTH_OUTCOME_RUN_SUMMARY.json').write_text(json.dumps(s,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(s,ensure_ascii=False,indent=2));print(agg.sort_values('validation_ba_mean',ascending=False).to_string(index=False))
if __name__=='__main__':main()
