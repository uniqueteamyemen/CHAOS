#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score,precision_score,recall_score
from explore_tree_reverse_extraction import TARGET,build_origins,load_panel

ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/macro_plus_eia_energy/regime_locked_test_v1'; H=3; LABEL='outcome_material_drop_2pp'

def calc(name,y,p,frame):
 y=y.astype(int);p=p.astype(int); pos=int(y.sum()); neg=int(len(y)-pos)
 return {'model':name,'n_origins':len(y),'support':int(p.sum()),'positive_outcomes':pos,'precision':float(precision_score(y,p,zero_division=0)),'recall':float(recall_score(y,p,zero_division=0)),'f1':float(f1_score(y,p,zero_division=0)),'balanced_accuracy':float(balanced_accuracy_score(y,p)),'false_alarm_rate':float(((p==1)&(y==0)).sum()/neg) if neg else None,'entity_coverage':int(frame.loc[p.astype(bool),'entity_code'].nunique()) if p.any() else 0,'year_coverage':int(frame.loc[p.astype(bool),'target_year'].nunique()) if p.any() else 0}

def main():
 OUT.mkdir(parents=True,exist_ok=True); o=build_origins(load_panel(),H); o['target_current']=o[f'{TARGET}__lag0'];
 frame=o[o.target_year.between(2020,2024)&o[LABEL].notna()&o.target_current.notna()&o['wdi__SP_POP_TOTL__lag2'].notna()&o['eia__energy_consumption_per_gdp__lag2'].notna()].copy().reset_index(drop=True); y=frame[LABEL].astype(int).to_numpy()
 preds={
  'population_regime_v1':((frame.target_current>4.0)&(frame['wdi__SP_POP_TOTL__lag2']<=75_000_000)).to_numpy(),
  'energy_per_gdp_regime_v1':((frame.target_current>4.0)&(frame['eia__energy_consumption_per_gdp__lag2']<=10.0)).to_numpy(),
  'always_negative':np.zeros(len(frame),bool),
  'always_positive':np.ones(len(frame),bool),
  'target_history_growth_gt_4':(frame.target_current>4.0).to_numpy(),
  'population_only_bounded':(frame['wdi__SP_POP_TOTL__lag2']<=75_000_000).to_numpy(),
  'energy_per_gdp_only_bounded':(frame['eia__energy_consumption_per_gdp__lag2']<=10.0).to_numpy(),
 }
 rows=[calc(n,y,p,frame) for n,p in preds.items()]; pd.DataFrame(rows).to_csv(OUT/'LOCKED_TEST_METRICS.csv',index=False)
 detail=[]
 for n,p in preds.items():
  for yr,g in frame.assign(_pred=p).groupby('target_year'):
   yy=g[LABEL].astype(int).to_numpy(); pp=g['_pred'].astype(int).to_numpy(); detail.append({'model':n,'target_year':int(yr),**calc(n,yy,pp,g)})
 pd.DataFrame(detail).to_csv(OUT/'LOCKED_TEST_METRICS_BY_YEAR.csv',index=False)
 ent=[]
 for n,p in preds.items():
  for e,g in frame.assign(_pred=p).groupby('entity_code'):
   yy=g[LABEL].astype(int).to_numpy();pp=g['_pred'].astype(int).to_numpy();ent.append({'model':n,'entity_code':e,**calc(n,yy,pp,g)})
 pd.DataFrame(ent).to_csv(OUT/'LOCKED_TEST_METRICS_BY_ENTITY.csv',index=False)
 frame_out=frame[['entity_code','year','target_year',TARGET,'wdi__SP_POP_TOTL__lag2','eia__energy_consumption_per_gdp__lag2',LABEL]].copy(); frame_out['population_regime_v1']=preds['population_regime_v1']; frame_out['energy_per_gdp_regime_v1']=preds['energy_per_gdp_regime_v1']; frame_out.to_csv(OUT/'LOCKED_TEST_REPLAY_ROWS.csv',index=False)
 summary={'run_id':'regime_locked_test_v1','contract':'experimental_contracts/REGIME_LOCKED_TEST_CONTRACT_V1.json','target_years':[2020,2021,2022,2023,2024],'origin_years':[2017,2018,2019,2020,2021],'n_origins':len(frame),'entities':int(frame.entity_code.nunique()),'models_replayed':list(preds),'test_used_for_selection':False,'path_or_threshold_changed_after_test':False,'locked_test_executed':True,'raw_data_modified':False,'imputation':False,'normalization':False,'causal_claims_permitted':False,'promotion_decision':'deferred_until_report_review; both frozen paths reported without winner selection'}
 (OUT/'LOCKED_TEST_RUN_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2)); print(pd.DataFrame(rows).to_string(index=False))
if __name__=='__main__':main()
