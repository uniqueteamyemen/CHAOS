from __future__ import annotations

import csv
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from lightning.pytorch import Trainer, seed_everything
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint
from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer
from pytorch_forecasting.metrics import MAE

ROOT = Path('/home/ubuntu/CHAOS')
MATRIX = ROOT / 'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
CONTRACT = ROOT / 'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1_1.json'
EXP = ROOT / 'experiments/macro_plus_eia_energy/next_phase'
EXP.mkdir(parents=True, exist_ok=True)

contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
TARGET_ORIGINAL = contract['target']['id']
FEATURES_ORIGINAL = list(contract['features'])
EXOG_ORIGINAL = [c for c in FEATURES_ORIGINAL if c != TARGET_ORIGINAL]
FNAME = {c: c.replace('.', '_') for c in FEATURES_ORIGINAL}
TARGET = FNAME[TARGET_ORIGINAL]

raw = pd.read_csv(MATRIX, dtype={'entity_code': str})
raw['year'] = raw['year'].astype(int)
raw = raw.rename(columns=FNAME).sort_values(['entity_code', 'year']).reset_index(drop=True)
ENTITY_COUNT = int(raw['entity_code'].nunique())

DOMAIN_FEATURES = {
    'wdi_only': [FNAME[TARGET_ORIGINAL]] + [FNAME[x] for x in EXOG_ORIGINAL if x.startswith('wdi__')],
    'imf_only': [FNAME[TARGET_ORIGINAL]] + [FNAME[x] for x in EXOG_ORIGINAL if x.startswith('imf__')],
    'eia_only': [FNAME[TARGET_ORIGINAL]] + [FNAME[x] for x in EXOG_ORIGINAL if x.startswith('eia__')],
    'wdi_imf': [FNAME[TARGET_ORIGINAL]] + [FNAME[x] for x in EXOG_ORIGINAL if x.startswith(('wdi__','imf__'))],
    'wdi_eia': [FNAME[TARGET_ORIGINAL]] + [FNAME[x] for x in EXOG_ORIGINAL if x.startswith(('wdi__','eia__'))],
    'imf_eia': [FNAME[TARGET_ORIGINAL]] + [FNAME[x] for x in EXOG_ORIGINAL if x.startswith(('imf__','eia__'))],
    'full': [FNAME[x] for x in FEATURES_ORIGINAL],
}


def set_seed(seed: int) -> None:
    seed_everything(seed, workers=True)
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)


def make_dataset(feature_cols: list[str], encoder: int, support_start: int, train_end: int = 2015, val_end: int = 2019):
    # Data are already raw and numeric-validated. We only rename columns to API-safe aliases.
    kwargs = dict(
        time_idx='year', target=TARGET, group_ids=['entity_code'],
        max_encoder_length=encoder, min_encoder_length=encoder,
        min_prediction_length=1, max_prediction_length=1,
        static_categoricals=['entity_code'], static_reals=[],
        time_varying_known_categoricals=[], time_varying_known_reals=[],
        time_varying_unknown_categoricals=[], time_varying_unknown_reals=feature_cols,
        allow_missing_timesteps=False, add_relative_time_idx=False,
        add_target_scales=False, add_encoder_length=False, randomize_length=False,
        target_normalizer=None, scalers={c: None for c in feature_cols if c != TARGET},
    )
    train_df = raw[(raw.year >= support_start - encoder) & (raw.year <= train_end)].copy()
    val_df = raw[(raw.year >= support_start - encoder) & (raw.year <= val_end)].copy()
    test_df = raw[(raw.year >= support_start - encoder) & (raw.year <= 2024)].copy()
    train_min_target = support_start
    val_min_target = train_end + 1
    test_min_target = val_end + 1
    training = TimeSeriesDataSet(train_df, min_prediction_idx=train_min_target, **kwargs)
    validation = TimeSeriesDataSet.from_dataset(training, val_df, min_prediction_idx=val_min_target, stop_randomization=True)
    testing = TimeSeriesDataSet.from_dataset(training, test_df, min_prediction_idx=test_min_target, stop_randomization=True)
    return training, validation, testing


def score(y, p):
    y = np.asarray(y, dtype=float).reshape(-1); p = np.asarray(p, dtype=float).reshape(-1)
    ss = float(np.sum((y-y.mean())**2))
    return {'n': int(len(y)), 'MAE': float(np.mean(np.abs(y-p))), 'RMSE': float(np.sqrt(np.mean((y-p)**2))), 'R2': float(1-np.sum((y-p)**2)/ss) if ss else 0.0, 'directional_accuracy': float(np.mean(np.sign(y)==np.sign(p)))}


def evaluate(model, dataset, split: str, run_dir: Path):
    loader = dataset.to_dataloader(train=False, batch_size=64, num_workers=0)
    result = model.predict(loader, mode='prediction', return_y=True, return_index=True)
    y = result.y[0] if isinstance(result.y, (tuple, list)) else result.y
    p = np.asarray(result.output).reshape(-1); y = np.asarray(y).reshape(-1)
    idx = result.index.reset_index(drop=True)
    year_col = 'year' if 'year' in idx.columns else 'time_idx'
    years = idx[year_col].astype(int).to_numpy()
    rows = pd.DataFrame({'entity_code': idx['entity_code'].astype(str), 'target_year': years, 'actual': y, 'prediction': p, 'residual': y-p})
    rows.to_csv(run_dir / f'{split.upper()}_PREDICTIONS.csv', index=False)
    metrics = score(y, p); metrics['split'] = split
    per=[]
    for entity,g in rows.groupby('entity_code', sort=True):
        q=score(g.actual,g.prediction); q['entity_code']=entity; per.append(q)
    pd.DataFrame(per).to_csv(run_dir / f'{split.upper()}_PER_ENTITY_METRICS.csv', index=False)
    by_year=[]
    for year,g in rows.groupby('target_year', sort=True):
        q=score(g.actual,g.prediction); q['target_year']=int(year); by_year.append(q)
    pd.DataFrame(by_year).to_csv(run_dir / f'{split.upper()}_PER_YEAR_METRICS.csv', index=False)
    return metrics


def train_one(run_id: str, family: str, feature_cols: list[str], seed: int, encoder: int, support_start: int, max_epochs: int = 25):
    run_dir = EXP / run_id; run_dir.mkdir(parents=True, exist_ok=True)
    set_seed(seed)
    training, validation, testing = make_dataset(feature_cols, encoder, support_start)
    counts = {'train':len(training), 'validation':len(validation), 'test':len(testing)}
    expected = {'train':ENTITY_COUNT*(2015-support_start+1), 'validation':ENTITY_COUNT*4, 'test':ENTITY_COUNT*5}
    if counts != expected:
        raise RuntimeError(f'{run_id}: window counts {counts} != expected {expected}')
    train_loader=training.to_dataloader(train=True,batch_size=64,num_workers=0)
    val_loader=validation.to_dataloader(train=False,batch_size=64,num_workers=0)
    ckpt_dir=run_dir/'checkpoints'; ckpt_dir.mkdir(exist_ok=True)
    checkpoint=ModelCheckpoint(dirpath=str(ckpt_dir),filename='tft-{epoch:02d}-{val_loss:.4f}',monitor='val_loss',mode='min',save_top_k=1)
    early=EarlyStopping(monitor='val_loss',min_delta=0.0,patience=5,mode='min')
    model=TemporalFusionTransformer.from_dataset(training,hidden_size=16,lstm_layers=1,dropout=0.1,attention_head_size=2,hidden_continuous_size=8,loss=MAE(),output_size=1,learning_rate=1e-3,log_interval=-1,reduce_on_plateau_patience=3)
    trainer=Trainer(max_epochs=max_epochs,accelerator='cpu',devices=1,deterministic=True,gradient_clip_val=0.1,callbacks=[checkpoint,early],logger=False,enable_progress_bar=False,enable_model_summary=False,default_root_dir=str(run_dir),limit_train_batches=1.0,limit_val_batches=1.0)
    t0=time.time(); trainer.fit(model,train_dataloaders=train_loader,val_dataloaders=val_loader); elapsed=time.time()-t0
    best=checkpoint.best_model_path
    if not best: raise RuntimeError(f'{run_id}: no checkpoint')
    best_model=TemporalFusionTransformer.load_from_checkpoint(best)
    val_metrics=evaluate(best_model,validation,'validation',run_dir)
    test_metrics=evaluate(best_model,testing,'test',run_dir)
    summary={'run_id':run_id,'family':family,'seed':seed,'encoder_length':encoder,'support_start_target_year':support_start,'train_target_years':[support_start,2015],'validation_target_years':[2016,2019],'test_target_years':[2020,2024],'feature_columns':feature_cols,'feature_columns_original':[next((k for k,v in FNAME.items() if v==c),c) for c in feature_cols],'window_counts':counts,'expected_window_counts':expected,'best_checkpoint':str(Path(best).relative_to(ROOT)),'best_epoch':int(trainer.current_epoch),'elapsed_seconds':elapsed,'validation_metrics':val_metrics,'test_metrics':test_metrics,'test_used_for_selection':False,'raw_data_modified':False,'imputation':False,'transformations':False,'model_params':{'hidden_size':16,'lstm_layers':1,'dropout':0.1,'attention_head_size':2,'hidden_continuous_size':8,'learning_rate':0.001,'max_epochs':max_epochs},'status':'completed'}
    (run_dir/'RUN_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary


def main():
    results=[]
    failures=[]
    # Stability grid: common support starts at 2008 so encoder 3/5/7 have identical target-year support.
    for seed in [17,43,101]:
        for encoder in [3,5,7]:
            run_id=f'stability_seed{seed}_enc{encoder}'
            try: results.append(train_one(run_id,'stability',DOMAIN_FEATURES['full'],seed,encoder,2008))
            except Exception as e: failures.append({'run_id':run_id,'family':'stability','error':repr(e)})
    # Ablation: full arm is the already completed contract baseline; reduced arms are new runs.
    for arm in ['wdi_only','imf_only','eia_only','wdi_imf','wdi_eia','imf_eia']:
        run_id=f'ablation_{arm}_seed17_enc5'
        try: results.append(train_one(run_id,'ablation',DOMAIN_FEATURES[arm],17,5,2006))
        except Exception as e: failures.append({'run_id':run_id,'family':'ablation','error':repr(e)})
    # Target-history ablation: full and target-history-only; exogenous-only is one unique arm for duplicated B/D request.
    for arm,features in [('target_history_only',[TARGET]),('exogenous_only',[c for c in DOMAIN_FEATURES['full'] if c!=TARGET])]:
        run_id=f'target_history_{arm}_seed17_enc5'
        try: results.append(train_one(run_id,'target_history_ablation',features,17,5,2006))
        except Exception as e: failures.append({'run_id':run_id,'family':'target_history_ablation','error':repr(e)})
    (EXP/'CAMPAIGN_RUN_RESULTS.json').write_text(json.dumps({'results':results,'failures':failures,'full_baseline_reference':'../TFT_TRAINING_SUMMARY.json','notes':['Stability selection is validation-only; test metrics are descriptive for the trained runs and never used to choose configuration.','Ablation full arm references completed TFT baseline v1.1 rather than duplicating the same training.','Campaign target-history arms B and D are semantically identical exogenous-only specifications; they are represented by one run and documented as a duplicate request.','No new data, transformations, imputation, raw edits, or architecture changes.']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # compact tables
    rows=[]
    for r in results:
        rows.append({'run_id':r['run_id'],'family':r['family'],'seed':r['seed'],'encoder':r['encoder_length'],'support_start':r['support_start_target_year'],'val_MAE':r['validation_metrics']['MAE'],'val_RMSE':r['validation_metrics']['RMSE'],'test_MAE':r['test_metrics']['MAE'],'test_RMSE':r['test_metrics']['RMSE'],'test_R2':r['test_metrics']['R2'],'test_directional_accuracy':r['test_metrics']['directional_accuracy'],'checkpoint':r['best_checkpoint']})
    pd.DataFrame(rows).to_csv(EXP/'CAMPAIGN_METRICS_SUMMARY.csv',index=False)
    print(json.dumps({'completed':len(results),'failures':failures,'output':str(EXP/'CAMPAIGN_RUN_RESULTS.json')},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
