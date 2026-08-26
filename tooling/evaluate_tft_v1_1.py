from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer
ROOT=Path('/home/ubuntu/CHAOS'); EXP=ROOT/'experiments/macro_plus_eia_energy'
CONTRACT=ROOT/'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1_1.json'
MATRIX=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
contract=json.loads(CONTRACT.read_text(encoding='utf-8'))
target_original=contract['target']['id']; original=[target_original]+[x for x in contract['features'] if x!=target_original]; fmap={c:c.replace('.','_') for c in original}; target=fmap[target_original]; reals=[fmap[c] for c in original]
df=pd.read_csv(MATRIX,dtype={'entity_code':str}); df['year']=df['year'].astype(int); df=df.rename(columns=fmap).sort_values(['entity_code','year']).reset_index(drop=True)
kwargs=dict(time_idx='year',target=target,group_ids=['entity_code'],max_encoder_length=5,min_encoder_length=5,min_prediction_length=1,max_prediction_length=1,static_categoricals=['entity_code'],static_reals=[],time_varying_known_categoricals=[],time_varying_known_reals=[],time_varying_unknown_categoricals=[],time_varying_unknown_reals=reals,allow_missing_timesteps=False,add_relative_time_idx=False,add_target_scales=False,add_encoder_length=False,randomize_length=False,target_normalizer=None,scalers={c:None for c in reals if c!=target})
training=TimeSeriesDataSet(df[df.year<=2015].copy(),min_prediction_idx=2006,**kwargs)
val=TimeSeriesDataSet.from_dataset(training,df[df.year<=2019].copy(),min_prediction_idx=2016,stop_randomization=True)
test=TimeSeriesDataSet.from_dataset(training,df[df.year<=2024].copy(),min_prediction_idx=2020,stop_randomization=True)
model=TemporalFusionTransformer.load_from_checkpoint(str(sorted((EXP/'checkpoints').glob('*.ckpt'))[-1]))
def score(y,p):
 y=np.asarray(y).reshape(-1); p=np.asarray(p).reshape(-1); ss=np.sum((y-y.mean())**2); return {'n':len(y),'MAE':float(np.mean(np.abs(y-p))),'RMSE':float(np.sqrt(np.mean((y-p)**2))),'R2':float(1-np.sum((y-p)**2)/ss) if ss else 0.0,'directional_accuracy':float(np.mean(np.sign(y)==np.sign(p)))}
def predict(ds):
 r=model.predict(ds.to_dataloader(train=False,batch_size=64,num_workers=0),mode='prediction',return_y=True,return_index=True); y=r.y[0] if isinstance(r.y,(tuple,list)) else r.y; return r.index.reset_index(drop=True),np.asarray(y).reshape(-1),np.asarray(r.output).reshape(-1)
all_scores=[]
for name,ds in [('validation',val),('test',test)]:
 idx,y,p=predict(ds); s=score(y,p); s['split']=name; all_scores.append(s)
 rows=pd.DataFrame({'entity_code':idx['entity_code'].astype(str),'target_year':idx['year'].astype(int),'actual':y,'prediction':p,'residual':y-p}); rows.to_csv(EXP/f'TFT_{name.upper()}_PREDICTIONS.csv',index=False)
 per=[]
 for e,g in rows.groupby('entity_code'):
  q=score(g.actual,g.prediction); q['entity_code']=e; per.append(q)
 pd.DataFrame(per).to_csv(EXP/f'TFT_{name.upper()}_PER_ENTITY_METRICS.csv',index=False)
# baseline comparison: pooled rows only
base=pd.read_csv(EXP/'BASELINE_V1_1_METRICS.csv')
base=base[base['entity_code'].isna()].copy()
comp=[]
for r in all_scores: comp.append({'model':'TFT','split':r['split'],**{k:r[k] for k in ['n','MAE','RMSE','R2','directional_accuracy']}})
for _,r in base.iterrows(): comp.append({'model':r['baseline'],'split':r['split'],'n':int(r['n']),'MAE':r['MAE'],'RMSE':r['RMSE'],'R2':r['R2'],'directional_accuracy':r['directional_accuracy']})
pd.DataFrame(comp).sort_values(['split','MAE']).to_csv(EXP/'MODEL_BASELINE_COMPARISON_V1_1.csv',index=False)
(EXP/'TFT_EVALUATION_SUMMARY_V1_1.json').write_text(json.dumps({'experiment_id':'macro_plus_eia_energy_tft_baseline_v1_1','scores':all_scores,'comparison_file':'experiments/macro_plus_eia_energy/MODEL_BASELINE_COMPARISON_V1_1.csv','per_entity_files':['experiments/macro_plus_eia_energy/TFT_VALIDATION_PER_ENTITY_METRICS.csv','experiments/macro_plus_eia_energy/TFT_TEST_PER_ENTITY_METRICS.csv'],'test_locked':True},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(pd.DataFrame(comp).sort_values(['split','MAE']).to_string(index=False))
