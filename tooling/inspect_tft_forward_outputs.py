import json
from pathlib import Path
import pandas as pd
from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer
ROOT=Path('/home/ubuntu/CHAOS'); M=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'; C=ROOT/'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1_1.json'; CK=sorted((ROOT/'experiments/macro_plus_eia_energy/next_phase/stability_seed17_enc7/checkpoints').glob('*.ckpt'))[-1]
c=json.loads(C.read_text()); t0=c['target']['id']; feats=c['features']; fmap={x:x.replace('.','_') for x in feats}; t=fmap[t0]; reals=[fmap[x] for x in feats]
df=pd.read_csv(M,dtype={'entity_code':str}); df.year=df.year.astype(int); df=df.rename(columns=fmap).sort_values(['entity_code','year'])
kw=dict(time_idx='year',target=t,group_ids=['entity_code'],max_encoder_length=7,min_encoder_length=7,min_prediction_length=1,max_prediction_length=1,static_categoricals=['entity_code'],static_reals=[],time_varying_known_categoricals=[],time_varying_known_reals=[],time_varying_unknown_categoricals=[],time_varying_unknown_reals=reals,allow_missing_timesteps=False,add_relative_time_idx=False,add_target_scales=False,add_encoder_length=False,randomize_length=False,target_normalizer=None,scalers={x:None for x in reals if x!=t})
train=TimeSeriesDataSet(df[df.year<=2015],min_prediction_idx=2006,**kw); loader=train.to_dataloader(train=False,batch_size=4,num_workers=0); x,y=next(iter(loader)); model=TemporalFusionTransformer.load_from_checkpoint(str(CK)); model.eval();
with __import__('torch').no_grad(): out=model(x)
print('x keys',list(x.keys())); print('out keys',list(out.keys()));
for k,v in out.items():
 try: print(k, type(v).__name__, list(v.shape))
 except Exception: print(k,type(v).__name__)
