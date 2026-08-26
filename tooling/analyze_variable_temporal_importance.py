from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer

ROOT=Path('/home/ubuntu/CHAOS')
EXP=ROOT/'experiments/macro_plus_eia_energy'
NEXT=EXP/'next_phase'
OUT=NEXT/'importance'
OUT.mkdir(parents=True,exist_ok=True)
contract=json.loads((ROOT/'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1_1.json').read_text(encoding='utf-8'))
target_original=contract['target']['id']; features=list(contract['features']); fmap={c:c.replace('.','_') for c in features}; target=fmap[target_original]; reals=[fmap[c] for c in features]
M=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
raw=pd.read_csv(M,dtype={'entity_code':str}); raw.year=raw.year.astype(int); raw=raw.rename(columns=fmap).sort_values(['entity_code','year']).reset_index(drop=True)
kwargs=dict(time_idx='year',target=target,group_ids=['entity_code'],max_encoder_length=5,min_encoder_length=5,min_prediction_length=1,max_prediction_length=1,static_categoricals=['entity_code'],static_reals=[],time_varying_known_categoricals=[],time_varying_known_reals=[],time_varying_unknown_categoricals=[],time_varying_unknown_reals=reals,allow_missing_timesteps=False,add_relative_time_idx=False,add_target_scales=False,add_encoder_length=False,randomize_length=False,target_normalizer=None,scalers={c:None for c in reals if c!=target})

def npv(v):
    if v is None:return None
    try:return v.detach().cpu().numpy()
    except Exception:return np.asarray(v)

imp_rows=[]; att_rows=[]; step_var_rows=[]; field_rows=[]; errors=[]
stability=pd.read_csv(NEXT/'CAMPAIGN_METRICS_SUMMARY.csv').query("family == 'stability'")
for r in stability.to_dict('records'):
    run_id=r['run_id']; seed=int(r['seed']); enc=int(r['encoder']); ck=ROOT/r['checkpoint'];
    try:
        tr=TimeSeriesDataSet(raw[raw.year<=2015].copy(),min_prediction_idx=2006,**{**kwargs,'max_encoder_length':enc,'min_encoder_length':enc})
        val=TimeSeriesDataSet.from_dataset(tr,raw[raw.year<=2019].copy(),min_prediction_idx=2016,stop_randomization=True)
        loader=val.to_dataloader(train=False,batch_size=64,num_workers=0)
        model=TemporalFusionTransformer.load_from_checkpoint(str(ck)); model.eval()
        feature_order=list(tr.reals)
        feature_order=[x for x in feature_order if x not in {'year'}]
        # The model's encoder_variables last dimension is aligned with tr.reals in this setup.
        for batch_no,(x,_) in enumerate(loader):
            with torch.no_grad(): out=model(x)
            for key in ['encoder_variables','decoder_variables','encoder_attention','decoder_attention','static_variables']:
                a=npv(out.get(key));
                if a is not None: field_rows.append({'run_id':run_id,'seed':seed,'encoder':enc,'field':key,'batch':batch_no,'shape':json.dumps(list(a.shape)),'mean':float(np.nanmean(a)),'std':float(np.nanstd(a))})
            interp=model.interpret_output(out,reduction='none',attention_prediction_horizon=0)
            ev=npv(interp['encoder_variables'])
            at=npv(interp['attention'])
            if ev is not None:
                # ev: batch x encoder x variables (or compatible singleton dimensions)
                ev=np.squeeze(ev)
                if ev.ndim==2: ev=ev[None,:,:]
                if ev.ndim!=3: raise RuntimeError(f'Unexpected encoder_variables shape {ev.shape}')
                if ev.shape[-1] != len(feature_order):
                    feature_order=list(tr.reals)
                for j,name in enumerate(feature_order[:ev.shape[-1]]):
                    vals=ev[:,:,j]
                    imp_rows.append({'run_id':run_id,'seed':seed,'encoder':enc,'variable':name,'mean_importance':float(np.nanmean(vals)),'std_importance':float(np.nanstd(vals)),'n_values':int(vals.size)})
                means=np.nanmean(ev,axis=0)
                for step in range(means.shape[0]):
                    label=f't-{means.shape[0]-1-step}' if step < means.shape[0]-1 else 't'
                    for j,name in enumerate(feature_order[:means.shape[1]]):
                        step_var_rows.append({'run_id':run_id,'seed':seed,'encoder':enc,'encoder_step_index':step,'encoder_position':label,'variable':name,'mean_importance':float(means[step,j])})
            if at is not None:
                at=np.squeeze(at)
                if at.ndim==1: at=at[None,:]
                if at.ndim!=2: raise RuntimeError(f'Unexpected attention shape {at.shape}')
                # attention includes encoder positions then decoder horizon; only retain encoder side.
                enc_at=at[:,:enc]
                mean_at=np.nanmean(enc_at,axis=0)
                for step,value in enumerate(mean_at):
                    label=f't-{enc-1-step}' if step < enc-1 else 't'
                    att_rows.append({'run_id':run_id,'seed':seed,'encoder':enc,'encoder_step_index':step,'encoder_position':label,'mean_attention':float(value)})
    except Exception as e:
        errors.append({'run_id':run_id,'error':repr(e)})

imp=pd.DataFrame(imp_rows); att=pd.DataFrame(att_rows); stepvar=pd.DataFrame(step_var_rows); fields=pd.DataFrame(field_rows)
imp.to_csv(OUT/'VARIABLE_SELECTION_IMPORTANCE_BY_RUN.csv',index=False)
att.to_csv(OUT/'TEMPORAL_ATTENTION_BY_RUN.csv',index=False)
stepvar.to_csv(OUT/'ENCODER_STEP_VARIABLE_IMPORTANCE_BY_RUN.csv',index=False)
fields.to_csv(OUT/'FORWARD_OUTPUT_FIELD_AUDIT.csv',index=False)
if not imp.empty:
    feature_summary=(imp.groupby('variable',as_index=False).agg(runs=('run_id','nunique'),mean_importance=('mean_importance','mean'),std_across_runs=('mean_importance','std'),top_run_count=('mean_importance',lambda s:0))).sort_values('mean_importance',ascending=False)
    top_by_run=imp.loc[imp.groupby('run_id')['mean_importance'].idxmax(),['run_id','variable']].rename(columns={'variable':'top_variable'})
    counts=imp.sort_values(['run_id','mean_importance'],ascending=[True,False]).groupby('run_id').head(3).groupby('variable').size().to_dict()
    feature_summary['top3_run_count']=feature_summary['variable'].map(counts).fillna(0).astype(int)
    feature_summary.to_csv(OUT/'VARIABLE_SELECTION_STABILITY_SUMMARY.csv',index=False)
else: feature_summary=pd.DataFrame()
if not att.empty:
    temporal_summary=att.groupby(['encoder_position'],as_index=False).agg(runs=('run_id','nunique'),mean_attention=('mean_attention','mean'),std_across_runs=('mean_attention','std'))
    topatt=att.loc[att.groupby('run_id')['mean_attention'].idxmax()].groupby('encoder_position').size().to_dict()
    temporal_summary['top_run_count']=temporal_summary['encoder_position'].map(topatt).fillna(0).astype(int)
    temporal_summary.to_csv(OUT/'TEMPORAL_ATTENTION_STABILITY_SUMMARY.csv',index=False)
else: temporal_summary=pd.DataFrame()
if not stepvar.empty:
    posvar=stepvar.groupby(['encoder_position','variable'],as_index=False).agg(runs=('run_id','nunique'),mean_importance=('mean_importance','mean'),std_across_runs=('mean_importance','std'))
    posvar.to_csv(OUT/'POSITION_VARIABLE_IMPORTANCE_SUMMARY.csv',index=False)
else: posvar=pd.DataFrame()
candidates=[]
if not feature_summary.empty:
    for _,x in feature_summary[feature_summary.top3_run_count>=6].iterrows(): candidates.append({'pattern_type':'candidate_structural_descriptive','pattern':f"variable_top3:{x.variable}",'support_runs':int(x.top3_run_count),'total_runs':9,'mean_importance':float(x.mean_importance),'status':'candidate_only','causal_claim':False})
if not temporal_summary.empty:
    for _,x in temporal_summary[temporal_summary.top_run_count>=6].iterrows(): candidates.append({'pattern_type':'candidate_temporal_descriptive','pattern':f"attention_position:{x.encoder_position}",'support_runs':int(x.top_run_count),'total_runs':9,'mean_attention':float(x.mean_attention),'status':'candidate_only','causal_claim':False})
pd.DataFrame(candidates).to_csv(OUT/'CANDIDATE_TEMPORAL_STRUCTURAL_PATTERNS.csv',index=False)
summary={'stability_checkpoints_requested':9,'runs_with_errors':len(errors),'interpretation_runs_completed':len(imp['run_id'].unique()) if not imp.empty else 0,'variable_rows':len(imp),'attention_rows':len(att),'step_variable_rows':len(stepvar),'candidate_pattern_count':len(candidates),'errors':errors,'selection_rule':'descriptive stability summaries across seeds/encoders; no TEST selection','causal_claims':False,'raw_data_modified':False,'training_repeated':False}
(OUT/'IMPORTANCE_ANALYSIS_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
if not feature_summary.empty: print('TOP VARIABLES'); print(feature_summary.head(12).to_string(index=False))
if not temporal_summary.empty: print('TEMPORAL'); print(temporal_summary.to_string(index=False))
