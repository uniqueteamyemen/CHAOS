#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score,precision_score,recall_score
ROOT=Path('/home/ubuntu/CHAOS');P=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv';OUT=ROOT/'experiments/macro_plus_eia_energy/path_composer_v1';OUT.mkdir(parents=True,exist_ok=True)
T='wdi__NY.GDP.MKTP.KD.ZG';E='eia__energy_consumption_per_gdp';H=3;SPLITS={'fit':(2006,2009),'inner':(2010,2012),'validation':(2013,2016),'confirmation':(2017,2019)}
def main():
 d=pd.read_csv(P);d['year']=pd.to_numeric(d.year);g=d.groupby('entity_code',sort=False);d['future_target']=g[T].shift(-H);d['y']=(d.future_target<=d[T]-2.0);d['high_growth']=d[T]>4.0;d['energy_down_t2']=g[E].shift(-2)<d[E];d['energy_path']=d.high_growth&d.energy_down_t2
 fit=d[d.year.between(*SPLITS['fit'])&d[T].notna()&d.future_target.notna()&d[E].notna()].copy();
 def rate(mask): return float((fit.loc[mask,'y'].sum()+1)/(mask.sum()+2))
 weights={'economic_core':rate(fit.high_growth),'energy_mediator':rate(fit.energy_path),'conflict_edge':0.0}
 rows=[];replays=[]
 for split,(lo,hi) in SPLITS.items():
  fr=d[d.year.between(lo,hi)&d[T].notna()&d.future_target.notna()&d[E].notna()].copy();fr['composer_score']=(weights['economic_core']*fr.high_growth.astype(float)+weights['energy_mediator']*fr.energy_path.astype(float)).clip(0,1);fr['composer_prediction']=fr.composer_score>=0.5;y=fr.y.astype(int).to_numpy();p=fr.composer_prediction.astype(int).to_numpy();rows.append({'split':split,'model':'path_composer_v1','n':len(fr),'support':int(p.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,p,zero_division=0),'recall':recall_score(y,p,zero_division=0),'f1':f1_score(y,p,zero_division=0),'balanced_accuracy':balanced_accuracy_score(y,p) if len(np.unique(y))>1 else .5,'entity_coverage':int(fr.loc[p.astype(bool),'entity_code'].nunique()) if p.any() else 0});replays.append(fr.assign(split=split))
 pd.DataFrame(rows).to_csv(OUT/'PATH_COMPOSER_METRICS.csv',index=False);pd.concat(replays,ignore_index=True).to_csv(OUT/'PATH_COMPOSER_REPLAY_ROWS.csv',index=False)
 graph={'composer_id':'PATH_COMPOSER_V1','formula':'score = alpha_economic*I(high_growth) + alpha_energy_mediator*I(high_growth AND energy_intensity_down_at_t_plus_2); prediction if score >= 0.5','weights_fitted_on':'fit 2006-2009 only','weights':weights,'nodes':['AMA_HIGH_GROWTH_STATE_V1','AMA_MATERIAL_DROP_2PP_T_PLUS_3_V1','ENERGY_INTENSITY_DOWN_T_PLUS_2_V1','UCDP_STATE_CONFLICT_T_PLUS_3_V1'],'edges':[{'source':'AMA_HIGH_GROWTH_STATE_V1','target':'AMA_MATERIAL_DROP_2PP_T_PLUS_3_V1','status':'supported_predictive','enabled':True},{'source':'AMA_HIGH_GROWTH_STATE_V1','target':'ENERGY_INTENSITY_DOWN_T_PLUS_2_V1','status':'candidate_mediator','enabled':True},{'source':'ENERGY_INTENSITY_DOWN_T_PLUS_2_V1','target':'AMA_MATERIAL_DROP_2PP_T_PLUS_3_V1','status':'rejected_as_additive_in_current_evidence','enabled':False},{'source':'AMA_HIGH_GROWTH_STATE_V1','target':'UCDP_STATE_CONFLICT_T_PLUS_3_V1','status':'rejected_or_unresolved','enabled':False}], 'interpretation':'scores are predictive composition weights, not causal coefficients','native_frequency':'annual','locked_test_used':False,'raw_modified':False,'imputation':False,'normalization':False}
 (OUT/'PATH_COMPOSER_GRAPH_V1.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2)+'\n');print(json.dumps(graph,ensure_ascii=False,indent=2));print(pd.DataFrame(rows).to_string(index=False))
if __name__=='__main__':main()
