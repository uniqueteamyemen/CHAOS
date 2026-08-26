from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer

ROOT=Path('/home/ubuntu/CHAOS')
EXP=ROOT/'experiments/macro_plus_eia_energy'
CONTRACT=ROOT/'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1_1.json'
MATRIX=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
CHECKPOINT=sorted((EXP/'checkpoints').glob('*.ckpt'))[-1]
contract=json.loads(CONTRACT.read_text(encoding='utf-8'))
target_original=contract['target']['id']
exog_original=[x for x in contract['features'] if x != target_original]
feature_name_map={c:c.replace('.', '_') for c in [target_original]+exog_original}
target=feature_name_map[target_original]
all_reals=[feature_name_map[c] for c in [target_original]+exog_original]
df=pd.read_csv(MATRIX,dtype={'entity_code':str}); df['year']=df['year'].astype(int); df=df.rename(columns=feature_name_map).sort_values(['entity_code','year']).reset_index(drop=True)
# Recreate the same identity/raw dataset parameters as training.
base_kwargs=dict(time_idx='year',target=target,group_ids=['entity_code'],max_encoder_length=5,min_encoder_length=5,min_prediction_length=1,max_prediction_length=1,static_categoricals=['entity_code'],static_reals=[],time_varying_known_categoricals=[],time_varying_known_reals=[],time_varying_unknown_categoricals=[],time_varying_unknown_reals=all_reals,allow_missing_timesteps=False,add_relative_time_idx=False,add_target_scales=False,add_encoder_length=False,randomize_length=False,target_normalizer=None,scalers={c:None for c in all_reals if c!=target})
training=TimeSeriesDataSet(df[df.year<=2015].copy(),min_prediction_idx=2006,**base_kwargs)
testing=TimeSeriesDataSet.from_dataset(training,df[df.year<=2024].copy(),min_prediction_idx=2020,stop_randomization=True)
loader=testing.to_dataloader(train=False,batch_size=64,num_workers=0)
model=TemporalFusionTransformer.load_from_checkpoint(str(CHECKPOINT))
result=model.predict(loader,mode='prediction',return_y=True,return_index=True)
print('prediction_fields',result._fields)
output=result.output
actual=result.y
if isinstance(actual,(tuple,list)): actual=actual[0]
pred=np.asarray(output).reshape(-1); y=np.asarray(actual).reshape(-1)
idx=result.index.reset_index(drop=True)
print('prediction_index_columns',idx.columns.tolist())
if len(pred)!=len(idx): raise RuntimeError(f'prediction/index mismatch {len(pred)} vs {len(idx)}')
mae=float(np.mean(np.abs(y-pred))); rmse=float(np.sqrt(np.mean((y-pred)**2))); ss_res=float(np.sum((y-pred)**2)); ss_tot=float(np.sum((y-y.mean())**2)); r2=float(1-ss_res/ss_tot) if ss_tot else 0.0; direction=float(np.mean(np.sign(y)==np.sign(pred)))
metrics={'split':'test','n':len(y),'MAE':mae,'RMSE':rmse,'R2':r2,'directional_accuracy':direction}
out=pd.DataFrame({'entity_code':idx['entity_code'].astype(str),'target_year':(idx['time_idx'] if 'time_idx' in idx.columns else idx['year']).astype(int),'actual_target':y,'prediction':pred,'residual':y-pred})
out.to_csv(EXP/'TFT_TEST_PREDICTIONS.csv',index=False)
(EXP/'TFT_TEST_METRICS.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary={'experiment_id':'macro_plus_eia_energy_tft_baseline_v1_1','checkpoint':str(CHECKPOINT.relative_to(ROOT)),'dataset_entities':int(df.entity_code.nunique()),'test_windows':len(testing),'metrics':metrics,'checkpoint_selected_by':'validation val_loss','test_evaluation_locked':True,'extraction_completed_at_utc':datetime.now(timezone.utc).isoformat(),'training_completed':True,'stability_grid_run':False,'ablations_run':False,'reverse_extraction_run':False}
(EXP/'TFT_TRAINING_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
