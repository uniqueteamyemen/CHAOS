#!/usr/bin/env python3
"""Predeclared threshold-grid sensitivity for the promising h=3 regime candidate."""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score
from explore_tree_reverse_extraction import TARGET, build_origins, load_panel

ROOT=Path('/home/ubuntu/CHAOS')
OUT=ROOT/'experiments/macro_plus_eia_energy/threshold_grid_v1'
H=3
FAMILY='material_drop_2pp'
# Predeclared before reading validation metrics. The discovered 4.96 / 77m cell
# is represented approximately by (5.0, 75m), not inserted as an exact fitted value.
TARGET_THRESHOLDS=(3.0,4.0,5.0,6.0,7.0,8.0)
POP_THRESHOLDS=(25_000_000,50_000_000,75_000_000,100_000_000,150_000_000,250_000_000)
FOLDS=(
 ('fold_A',(2006,2010),(2011,2013),(2014,2016)),
 ('fold_B',(2006,2012),(2013,2015),(2016,2019)),
 ('fold_C',(2007,2011),(2012,2014),(2015,2018)),
)

def metric(y,p,entity,year,group='all'):
 return {'n_origins':len(y),'support':int(p.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,p,zero_division=0),'recall':recall_score(y,p,zero_division=0),'f1':f1_score(y,p,zero_division=0),'balanced_accuracy':balanced_accuracy_score(y,p),'entity_coverage':int(np.unique(entity[p]).size) if p.any() else 0,'year_coverage':int(np.unique(year[p]).size) if p.any() else 0,'group':group}

def main():
 OUT.mkdir(parents=True,exist_ok=True); origins=build_origins(load_panel(),H); origins['pop_lag2']=origins['wdi__SP_POP_TOTL__lag2']; origins['target_current']=origins[f'{TARGET}__lag0']; label=f'outcome_{FAMILY}'
 rows=[]
 # population strata thresholds frozen from discovery fit only.
 fit_pop=origins[origins.target_year.between(2006,2012)]['pop_lag2'].dropna()
 q33=float(fit_pop.quantile(.33)); q67=float(fit_pop.quantile(.67))
 origins['pop_stratum']=np.select([origins.pop_lag2<=q33,origins.pop_lag2<=q67],['low','middle'],'high')
 for tau_t in TARGET_THRESHOLDS:
  for tau_p in POP_THRESHOLDS:
   rule=(origins.target_current>tau_t)&(origins.pop_lag2<=tau_p)
   for fold,fit_y,inner_y,val_y in FOLDS:
    for split,years in [('fit',fit_y),('inner',inner_y),('validation',val_y)]:
     frame=origins[origins.target_year.between(*years)&origins[label].notna()&origins.target_current.notna()&origins.pop_lag2.notna()].copy(); y=frame[label].astype(int).to_numpy(); p=rule.loc[frame.index].to_numpy();
     rows.append({'threshold_target':tau_t,'threshold_population':tau_p,'fold':fold,'split':split,**metric(y,p,frame.entity_code.to_numpy(),frame.target_year.to_numpy())})
     if split=='validation':
      for stratum in ('low','middle','high'):
       sub=frame[frame.pop_stratum==stratum]; ys=sub[label].astype(int).to_numpy(); ps=rule.loc[sub.index].to_numpy(); rows.append({'threshold_target':tau_t,'threshold_population':tau_p,'fold':fold,'split':'validation_stratum',**metric(ys,ps,sub.entity_code.to_numpy(),sub.target_year.to_numpy(),stratum)})
 result=pd.DataFrame(rows); result.to_csv(OUT/'THRESHOLD_GRID_METRICS.csv',index=False)
 val=result[result.split=='validation']; aggregate=val.groupby(['threshold_target','threshold_population']).agg(validation_ba_mean=('balanced_accuracy','mean'),validation_ba_sd=('balanced_accuracy','std'),validation_f1_mean=('f1','mean'),validation_support_mean=('support','mean'),folds_with_support=('support',lambda x:int((x>=20).sum())),folds_ba_above_055=('balanced_accuracy',lambda x:int((x>0.55).sum()))).reset_index(); aggregate.to_csv(OUT/'THRESHOLD_GRID_AGGREGATE.csv',index=False)
 best=aggregate.sort_values(['validation_ba_mean','validation_f1_mean'],ascending=False).iloc[0]
 summary={'run_id':'threshold_grid_stability_v1','horizon':H,'family':FAMILY,'target_thresholds':list(TARGET_THRESHOLDS),'population_thresholds':list(POP_THRESHOLDS),'grid_cells':len(TARGET_THRESHOLDS)*len(POP_THRESHOLDS),'population_strata_fit_q33':q33,'population_strata_fit_q67':q67,'folds':list(FOLDS),'best_cell_by_validation_mean_ba':best.to_dict(),'selection_note':'best cell is descriptive grid summary; no locked test or operational promotion','locked_test_executed':False,'raw_data_modified':False,'imputation':False,'normalization':False}
 (OUT/'THRESHOLD_GRID_RUN_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2)); print(aggregate.sort_values(['validation_ba_mean','validation_f1_mean'],ascending=False).head(15).to_string(index=False))
if __name__=='__main__': main()
