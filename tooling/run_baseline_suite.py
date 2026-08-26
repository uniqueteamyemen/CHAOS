from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT=Path('/home/ubuntu/CHAOS')
MATRIX=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
OUT=ROOT/'experiments/macro_plus_eia_energy'
OUT.mkdir(parents=True,exist_ok=True)
TARGET='wdi__NY.GDP.MKTP.KD.ZG'
ENC=5
TRAIN_YEARS=range(2006,2016)
VAL_YEARS=range(2016,2020)
TEST_YEARS=range(2020,2025)

df=pd.read_csv(MATRIX,dtype={'entity_code':str}).sort_values(['entity_code','year'])
rows=[]
for entity,g in df.groupby('entity_code',sort=True):
 g=g.sort_values('year').set_index('year')
 for target_year in list(TRAIN_YEARS)+list(VAL_YEARS)+list(TEST_YEARS):
  origin=target_year-1
  years=list(range(origin-ENC+1,origin+1))
  vals=g.loc[years,TARGET].astype(float).to_numpy()
  y=float(g.loc[target_year,TARGET])
  split='train' if target_year in TRAIN_YEARS else 'validation' if target_year in VAL_YEARS else 'test'
  rows.append({'entity_code':entity,'target_year':target_year,'origin_year':origin,'split':split,'target':y,'lag_1':vals[-1],'lag_2':vals[-2],'lag_3':vals[-3],'lag_4':vals[-4],'lag_5':vals[-5]})
seq=pd.DataFrame(rows)
train=seq[seq.split=='train'].copy()

def directional(y,p):
 y=np.asarray(y); p=np.asarray(p)
 return float(np.mean(np.sign(y)==np.sign(p)))

def eval_metrics(y,p):
 return {'MAE':float(mean_absolute_error(y,p)),'RMSE':float(np.sqrt(mean_squared_error(y,p))),'R2':float(r2_score(y,p)),'directional_accuracy':directional(y,p)}

preds=[]
# Persistence
p=seq['lag_1'].to_numpy(dtype=float)
preds.append(seq.assign(baseline='persistence_one_step',prediction=p))
# Entity train mean
a=train.groupby('entity_code').target.mean().to_dict()
p=seq.entity_code.map(a).to_numpy(dtype=float)
preds.append(seq.assign(baseline='entity_train_mean',prediction=p))
# Global train mean
global_mean=float(train.target.mean())
preds.append(seq.assign(baseline='global_train_mean',prediction=global_mean))
# Per-entity AR(5), fitted only on train target rows.
ar_predictions=[]
for entity,g in seq.groupby('entity_code',sort=True):
 tr=g[g.split=='train']
 X=tr[['lag_1','lag_2','lag_3','lag_4','lag_5']].to_numpy(dtype=float); y=tr.target.to_numpy(dtype=float)
 X1=np.column_stack([np.ones(len(X)),X])
 coef=np.linalg.lstsq(X1,y,rcond=None)[0]
 gg=g[['lag_1','lag_2','lag_3','lag_4','lag_5']].to_numpy(dtype=float)
 pred=np.column_stack([np.ones(len(gg)),gg])@coef
 ar_predictions.append(pd.DataFrame({'entity_code':entity,'target_year':g.target_year.to_numpy(),'origin_year':g.origin_year.to_numpy(),'split':g.split.to_numpy(),'target':g.target.to_numpy(),'baseline':'linear_ar5_entity_train','prediction':pred}))
preds.append(pd.concat(ar_predictions,ignore_index=True))
all_preds=pd.concat(preds,ignore_index=True)
all_preds.to_csv(OUT/'BASELINE_V1_1_PREDICTIONS.csv',index=False)
metric_rows=[]
for baseline,g in all_preds.groupby('baseline',sort=True):
 for split,gg in g.groupby('split',sort=True):
  m=eval_metrics(gg.target,gg.prediction); metric_rows.append({'baseline':baseline,'split':split,'n':len(gg),**m})
  for entity,eg in gg.groupby('entity_code',sort=True):
   em=eval_metrics(eg.target,eg.prediction); metric_rows.append({'baseline':baseline,'split':split,'entity_code':entity,'n':len(eg),**em})
metrics=pd.DataFrame(metric_rows); metrics.to_csv(OUT/'BASELINE_V1_1_METRICS.csv',index=False)
summary={'experiment_id':'macro_plus_eia_energy_baseline_suite_v1_1','matrix':'macro_plus_eia_energy','entity_count':int(seq.entity_code.nunique()),'target':TARGET,'encoder_length':ENC,'train_years':[2006,2015],'validation_years':[2016,2019],'test_years':[2020,2024],'baselines':['persistence_one_step','entity_train_mean','global_train_mean','linear_ar5_entity_train'],'primary_metrics':['MAE','RMSE'],'no_transformations_or_imputation':True,'tft_run':False,'note':'Optional raw multivariate linear baseline not run because 10 training sequences per entity and 11 selected columns would be underdetermined without a separately approved regularization/transform contract.'}
(OUT/'BASELINE_V1_1_SUITE_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(metrics[(metrics.entity_code.isna()) if 'entity_code' in metrics.columns else metrics.index==metrics.index].to_string(index=False))
