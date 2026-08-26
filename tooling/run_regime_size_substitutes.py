#!/usr/bin/env python3
"""Compare frozen bounded-scale regime definitions across size proxies."""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score
from explore_tree_reverse_extraction import TARGET, build_origins, load_panel

ROOT=Path('/home/ubuntu/CHAOS')
OUT=ROOT/'experiments/macro_plus_eia_energy/regime_size_substitutes_v1'
H=3; FAMILY='material_drop_2pp'
TARGET_THRESHOLDS=(3.0,4.0,5.0,6.0,7.0,8.0)
# Frozen in native units before validation is inspected.
SIZE_SPECS={
 'population':('wdi__SP_POP_TOTL__lag2',(25_000_000,50_000_000,75_000_000,100_000_000,150_000_000,250_000_000)),
 'gdp_per_capita':('wdi__NY_GDP_PCAP_KD__lag2',(1000.0,2000.0,2500.0,3000.0,5000.0,10000.0)),
 'energy_per_gdp':('eia__energy_consumption_per_gdp__lag2',(1.0,2.0,4.0,6.0,8.0,10.0)),
}
FOLDS=(('fold_A',(2006,2010),(2011,2013),(2014,2016)),('fold_B',(2006,2012),(2013,2015),(2016,2019)),('fold_C',(2007,2011),(2012,2014),(2015,2018)))

def metric(y,p,entity,year,group='all'):
 return {'n_origins':len(y),'support':int(p.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,p,zero_division=0),'recall':recall_score(y,p,zero_division=0),'f1':f1_score(y,p,zero_division=0),'balanced_accuracy':balanced_accuracy_score(y,p),'entity_coverage':int(np.unique(entity[p]).size) if p.any() else 0,'year_coverage':int(np.unique(year[p]).size) if p.any() else 0,'group':group}

def main():
 OUT.mkdir(parents=True,exist_ok=True); origins=build_origins(load_panel(),H); origins['target_current']=origins[f'{TARGET}__lag0']; label=f'outcome_{FAMILY}'; rows=[]; strata_meta={}
 for variant,(col,thresholds) in SIZE_SPECS.items():
  origins['size_value']=origins[col]
  fit_ref=origins[origins.target_year.between(2006,2012)]['size_value'].dropna(); q33=float(fit_ref.quantile(.33)); q67=float(fit_ref.quantile(.67)); strata_meta[variant]={'column':col,'fit_q33':q33,'fit_q67':q67,'thresholds':list(thresholds)}
  origins['size_stratum']=np.select([origins.size_value<=q33,origins.size_value<=q67],['low','middle'],'high')
  for tt in TARGET_THRESHOLDS:
   for ts in thresholds:
    rule=(origins.target_current>tt)&(origins.size_value<=ts)
    for fold,fit_y,inner_y,val_y in FOLDS:
     for split,years in [('fit',fit_y),('inner',inner_y),('validation',val_y)]:
      frame=origins[origins.target_year.between(*years)&origins[label].notna()&origins.target_current.notna()&origins.size_value.notna()].copy(); y=frame[label].astype(int).to_numpy(); p=rule.loc[frame.index].to_numpy(); rows.append({'variant':variant,'size_column':col,'threshold_target':tt,'threshold_size':ts,'fold':fold,'split':split,**metric(y,p,frame.entity_code.to_numpy(),frame.target_year.to_numpy())})
      if split=='validation':
       for s in ('low','middle','high'):
        sub=frame[frame.size_stratum==s]; ys=sub[label].astype(int).to_numpy(); ps=rule.loc[sub.index].to_numpy(); rows.append({'variant':variant,'size_column':col,'threshold_target':tt,'threshold_size':ts,'fold':fold,'split':'validation_stratum',**metric(ys,ps,sub.entity_code.to_numpy(),sub.target_year.to_numpy(),s)})
 result=pd.DataFrame(rows); result.to_csv(OUT/'SIZE_SUBSTITUTE_METRICS.csv',index=False)
 val=result[result.split=='validation']; aggregate=val.groupby(['variant','threshold_target','threshold_size']).agg(validation_ba_mean=('balanced_accuracy','mean'),validation_ba_sd=('balanced_accuracy','std'),validation_f1_mean=('f1','mean'),validation_support_mean=('support','mean'),folds_with_support=('support',lambda x:int((x>=20).sum())),folds_ba_above_055=('balanced_accuracy',lambda x:int((x>0.55).sum()))).reset_index(); aggregate.to_csv(OUT/'SIZE_SUBSTITUTE_AGGREGATE.csv',index=False)
 best=aggregate.sort_values(['validation_ba_mean','validation_f1_mean'],ascending=False).iloc[0]
 summary={'run_id':'regime_size_substitutes_v1','horizon':H,'family':FAMILY,'target_thresholds':list(TARGET_THRESHOLDS),'size_specs':strata_meta,'grid_cells':len(SIZE_SPECS)*len(TARGET_THRESHOLDS)*6,'folds':list(FOLDS),'best_cell_by_validation_mean_ba':best.to_dict(),'selection_note':'all variants and thresholds predeclared; best is descriptive grid summary only','locked_test_executed':False,'raw_data_modified':False,'imputation':False,'normalization':False}
 (OUT/'SIZE_SUBSTITUTE_RUN_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2)); print(aggregate.sort_values(['validation_ba_mean','validation_f1_mean'],ascending=False).head(20).to_string(index=False))
if __name__=='__main__':main()
