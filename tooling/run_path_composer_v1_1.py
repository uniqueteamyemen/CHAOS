#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score,precision_score,recall_score,brier_score_loss,log_loss
ROOT=Path('/home/ubuntu/CHAOS');P=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv';OUT=ROOT/'experiments/macro_plus_eia_energy/path_composer_v1_1';OUT.mkdir(parents=True,exist_ok=True);T='wdi__NY.GDP.MKTP.KD.ZG';E='eia__energy_consumption_per_gdp';H=3;SPLITS={'fit':(2006,2009),'inner':(2010,2012),'validation':(2013,2016),'confirmation':(2017,2019)}
def smooth(y):return float((y.sum()+1)/(len(y)+2))
def main():
 d=pd.read_csv(P);d['year']=pd.to_numeric(d.year);g=d.groupby('entity_code',sort=False);d['future']=g[T].shift(-H);d['y']=(d.future<=d[T]-2.0).astype(int);d['high_growth']=d[T]>4;d['energy_down_t2']=g[E].shift(-2)<d[E];fit=d[d.year.between(*SPLITS['fit'])&d[T].notna()&d.future.notna()&d[E].notna()].copy();p_base=smooth(fit.y.to_numpy());p_hg=smooth(fit.loc[fit.high_growth,'y'].to_numpy());p_hge=smooth(fit.loc[fit.high_growth&fit.energy_down_t2,'y'].to_numpy());rows=[];replays=[]
 for split,(lo,hi) in SPLITS.items():
  fr=d[d.year.between(lo,hi)&d[T].notna()&d.future.notna()&d[E].notna()].copy();fr['composer_p']=np.where(fr.high_growth&fr.energy_down_t2,p_hge,np.where(fr.high_growth,p_hg,p_base));fr['hg_p']=np.where(fr.high_growth,p_hg,p_base);fr['composer_pred']=fr.composer_p>=.5;fr['hg_pred']=fr.hg_p>=.5;y=fr.y.to_numpy();
  for model,col,pred in [('path_composer_v1_1','composer_p','composer_pred'),('high_growth_probability','hg_p','hg_pred')]:
   pp=fr[pred].to_numpy();prob=np.clip(fr[col].to_numpy(),1e-6,1-1e-6);rows.append({'split':split,'model':model,'n':len(fr),'support':int(pp.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,pp,zero_division=0),'recall':recall_score(y,pp,zero_division=0),'f1':f1_score(y,pp,zero_division=0),'balanced_accuracy':balanced_accuracy_score(y,pp) if len(np.unique(y))>1 else .5,'brier':brier_score_loss(y,prob),'log_loss':log_loss(y,prob,labels=[0,1]),'p_base_fit':p_base,'p_high_growth_fit':p_hg,'p_high_growth_energy_down_fit':p_hge});
  replays.append(fr.assign(split=split))
 pd.DataFrame(rows).to_csv(OUT/'PATH_COMPOSER_V1_1_METRICS.csv',index=False);pd.concat(replays,ignore_index=True).to_csv(OUT/'PATH_COMPOSER_V1_1_REPLAY_ROWS.csv',index=False);graph={'composer_id':'PATH_COMPOSER_V1_1','formula':'p = p_base if not high_growth; p = p_high_growth if high_growth and not energy_down_t2; p = p_high_growth_energy_down if high_growth and energy_down_t2','parameters_fit_only':{'p_base':p_base,'p_high_growth':p_hg,'p_high_growth_energy_down':p_hge},'threshold_for_binary_metrics':0.5,'interpretation':'probability composition; no causal coefficients','locked_test_used':False,'raw_modified':False,'imputation':False,'normalization':False};(OUT/'PATH_COMPOSER_V1_1_GRAPH.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2)+'\n');print(json.dumps(graph,ensure_ascii=False,indent=2));print(pd.DataFrame(rows).to_string(index=False))
if __name__=='__main__':main()
