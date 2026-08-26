from __future__ import annotations

import hashlib
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from lightning.pytorch import Trainer, seed_everything
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint
from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer
from pytorch_forecasting.data import TorchNormalizer
from pytorch_forecasting.metrics import MAE

ROOT=Path('/home/ubuntu/CHAOS')
EXP=ROOT/'experiments/macro_plus_eia_energy'
EXP.mkdir(parents=True,exist_ok=True)
CONTRACT=ROOT/'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1_1.json'
AUTH=ROOT/'experimental_contracts/TRAINING_AUTHORIZATION_MACRO_PLUS_EIA_ENERGY_V1.json'
AUDIT=ROOT/'experimental_contracts/PRE_TRAIN_INTEGRITY_LEAKAGE_AUDIT_V1_1.json'
MATRIX=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'

contract=json.loads(CONTRACT.read_text(encoding='utf-8'))
auth=json.loads(AUTH.read_text(encoding='utf-8'))
audit=json.loads(AUDIT.read_text(encoding='utf-8'))
if not auth.get('authorized_by_user') or not auth.get('preflight_gate_required'):
    raise RuntimeError('Training authorization file is not active')
if not audit.get('all_pass'):
    raise RuntimeError('Pre-training audit failed; training is blocked')
if not audit.get('training_run') is False:
    raise RuntimeError('Audit metadata is inconsistent')

SEED=17
seed_everything(SEED, workers=True)
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)

target_original=contract['target']['id']
exog_original=[x['id'] for x in contract['input_columns']['exogenous_covariates']] if 'input_columns' in contract else [x for x in contract['features'] if x != target_original]
original_reals=[target_original]+exog_original
feature_name_map={c:c.replace('.', '_') for c in original_reals}
target=feature_name_map[target_original]
exog=[feature_name_map[c] for c in exog_original]
all_reals=[target]+exog
df=pd.read_csv(MATRIX,dtype={'entity_code':str})
df['year']=df['year'].astype(int)
df=df.rename(columns=feature_name_map)
df=df.sort_values(['entity_code','year']).reset_index(drop=True)

# Raw-value mode: explicit None entries prevent TimeSeriesDataSet from auto-fitting StandardScaler.
# target_normalizer=None preserves the target in its source units.
scalers={c:None for c in all_reals if c != target}
base_kwargs=dict(
    time_idx='year', target=target, group_ids=['entity_code'], max_encoder_length=5, min_encoder_length=5,
    min_prediction_length=1, max_prediction_length=1, static_categoricals=['entity_code'], static_reals=[],
    time_varying_known_categoricals=[], time_varying_known_reals=[], time_varying_unknown_categoricals=[],
    time_varying_unknown_reals=all_reals, allow_missing_timesteps=False, add_relative_time_idx=False,
    add_target_scales=False, add_encoder_length=False, randomize_length=False,
    target_normalizer=None, scalers=scalers,
)
train_df=df[df.year<=2015].copy()
val_df=df[df.year<=2019].copy()
test_df=df[df.year<=2024].copy()
training=TimeSeriesDataSet(train_df,min_prediction_idx=2006,**base_kwargs)
validation=TimeSeriesDataSet.from_dataset(training,val_df,min_prediction_idx=2016,stop_randomization=True)
testing=TimeSeriesDataSet.from_dataset(training,test_df,min_prediction_idx=2020,stop_randomization=True)

sizes={'train':len(training),'validation':len(validation),'test':len(testing)}
n_entities=int(contract['matrix']['numeric_complete_entity_count'])
expected={'train':n_entities*10,'validation':n_entities*4,'test':n_entities*5}
if sizes!=expected: raise RuntimeError(f'Window counts differ from contract: {sizes} != {expected}')
train_loader=training.to_dataloader(train=True,batch_size=64,num_workers=0)
val_loader=validation.to_dataloader(train=False,batch_size=64,num_workers=0)
test_loader=testing.to_dataloader(train=False,batch_size=64,num_workers=0)

ckpt_dir=EXP/'checkpoints'; ckpt_dir.mkdir(exist_ok=True)
checkpoint=ModelCheckpoint(dirpath=str(ckpt_dir),filename='tft-baseline-{epoch:02d}-{val_loss:.4f}',monitor='val_loss',mode='min',save_top_k=1)
early=EarlyStopping(monitor='val_loss',min_delta=0.0,patience=8,mode='min')
model=TemporalFusionTransformer.from_dataset(
    training, hidden_size=16, lstm_layers=1, dropout=0.1, attention_head_size=2,
    hidden_continuous_size=8, loss=MAE(), output_size=1, learning_rate=1e-3,
    log_interval=-1, reduce_on_plateau_patience=4,
)
trainer=Trainer(
    max_epochs=50, accelerator='cpu', devices=1, deterministic=True, gradient_clip_val=0.1,
    callbacks=[checkpoint,early], logger=False, enable_progress_bar=False, enable_model_summary=False,
    default_root_dir=str(EXP), limit_train_batches=1.0, limit_val_batches=1.0,
)
start=datetime.now(timezone.utc)
trainer.fit(model,train_dataloaders=train_loader,val_dataloaders=val_loader)
best=checkpoint.best_model_path
if not best: raise RuntimeError('No validation checkpoint produced')
model=TemporalFusionTransformer.load_from_checkpoint(best)
# Locked test: only after training and checkpoint selection.
preds,y=model.predict(test_loader,mode='prediction',return_y=True)
pred=np.asarray(preds).reshape(-1); actual=np.asarray(y).reshape(-1)
mae=float(np.mean(np.abs(actual-pred))); rmse=float(np.sqrt(np.mean((actual-pred)**2)))
ss_res=float(np.sum((actual-pred)**2)); ss_tot=float(np.sum((actual-actual.mean())**2)); r2=float(1-ss_res/ss_tot) if ss_tot else 0.0
directional=float(np.mean(np.sign(actual)==np.sign(pred)))
metrics={'split':'test','n':len(actual),'MAE':mae,'RMSE':rmse,'R2':r2,'directional_accuracy':directional}
# Save predictions with stable row order from the dataset index.
index=testing.index.copy().reset_index(drop=True)
if len(index)!=len(pred): raise RuntimeError(f'Prediction/index length mismatch {len(pred)} vs {len(index)}')
out_pred=pd.DataFrame({'entity_code':index['entity_code'].astype(str),'target_year':index['time_idx']+1,'actual_target':actual,'prediction':pred,'residual':actual-pred})
out_pred.to_csv(EXP/'TFT_TEST_PREDICTIONS.csv',index=False)
(EXP/'TFT_TEST_METRICS.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary={
 'experiment_id':'macro_plus_eia_energy_tft_baseline_v1_1','seed':SEED,'target_original':target_original,'feature_name_map':feature_name_map,'started_at_utc':start.isoformat(),'finished_at_utc':datetime.now(timezone.utc).isoformat(),
 'dataset_sizes':sizes,'best_checkpoint':str(Path(best).relative_to(ROOT)),'best_epoch':int(trainer.current_epoch),
 'metrics':metrics,'raw_mode_identity_normalizers':True,'no_imputation':True,'test_locked_after_selection':True,
 'architecture_ref':str((ROOT/'experimental_contracts/TFT_INITIAL_ARCHITECTURE_SPEC_V1.json').relative_to(ROOT)),
 'authorization_ref':str(AUTH.relative_to(ROOT)),'training_completed':True,'stability_grid_run':False,'ablations_run':False,'reverse_extraction_run':False,
}
(EXP/'TFT_TRAINING_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
