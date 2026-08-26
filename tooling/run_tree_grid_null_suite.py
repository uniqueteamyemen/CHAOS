#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from run_tree_maxstat_null import make_grid, ba_fast, f1_fast, NULL_SEED

# Exploratory robustness pass: all 72 models, reduced replicates after the full
# 2,000-replicate label max-stat run. The reduction is recorded in the summary.
NULL_REPS = 500

ROOT=Path('/home/ubuntu/CHAOS')
OUT=ROOT/'experiments/macro_plus_eia_energy/reverse_extraction_tree_v1'


def permute_within_entity(y, entity, rng):
    yp=y.copy()
    for e in np.unique(entity):
        idx=np.flatnonzero(entity==e); yp[idx]=rng.permutation(yp[idx])
    return yp


def support_matched(pred, entity, rng):
    out=np.zeros(len(pred),dtype=bool)
    for e in np.unique(entity):
        idx=np.flatnonzero(entity==e); k=int(pred[idx].sum())
        if k: out[rng.choice(idx,size=min(k,len(idx)),replace=False)]=True
    return out


def cyclic_shift(pred, entity, year, rng):
    out=np.zeros(len(pred),dtype=bool)
    for e in np.unique(entity):
        idx=np.flatnonzero(entity==e); idx=idx[np.argsort(year[idx])]
        vals=pred[idx]
        if len(idx)<=1: out[idx]=vals
        else: out[idx]=np.roll(vals,int(rng.integers(1,len(idx))))
    return out


def main():
    models=make_grid(); rng=np.random.default_rng(NULL_SEED)
    observed=[]
    for m in models:
        observed.append({'model_id':m['model_id'],'validation_ba':ba_fast(m['y'],m['pred']),'validation_f1':f1_fast(m['y'],m['pred'])})
    obs=pd.DataFrame(observed)
    rows=[]
    for rep in range(NULL_REPS):
        maxes={name:{'ba':-1.,'f1':-1.,'ba_id':'','f1_id':''} for name in ['label_permutation','support_matched','cyclic_shift']}
        for m in models:
            y=m['y']; p=m['pred']; e=m['entity']; yr=m['year']
            controls={
                'label_permutation':(permute_within_entity(y,e,rng),p),
                'support_matched':(y,support_matched(p,e,rng)),
                'cyclic_shift':(y,cyclic_shift(p,e,yr,rng)),
            }
            for name,(yn,pn) in controls.items():
                ba=ba_fast(yn,pn); f1=f1_fast(yn,pn)
                if ba>maxes[name]['ba']: maxes[name]['ba']=ba; maxes[name]['ba_id']=m['model_id']
                if f1>maxes[name]['f1']: maxes[name]['f1']=f1; maxes[name]['f1_id']=m['model_id']
        for name,v in maxes.items(): rows.append({'replicate':rep,'null':name,'max_validation_ba':v['ba'],'max_ba_model_id':v['ba_id'],'max_validation_f1':v['f1'],'max_f1_model_id':v['f1_id']})
    null=pd.DataFrame(rows); null.to_csv(OUT/'TREE_GRID_NULL_SUITE_REPLICATES.csv',index=False)
    best_ba=obs.loc[obs.validation_ba.idxmax()]; best_f1=obs.loc[obs.validation_f1.idxmax()]
    summary=[]
    for name,g in null.groupby('null'):
        summary.append({
            'null':name,'replicates':len(g),'replicate_budget_note':'500 per control after 2,000-replicate label max-stat run; robustness pass only','observed_best_ba':float(best_ba.validation_ba),'observed_best_f1':float(best_f1.validation_f1),
            'null_max_ba_mean':float(g.max_validation_ba.mean()),'null_max_ba_q025':float(g.max_validation_ba.quantile(.025)),'null_max_ba_q500':float(g.max_validation_ba.quantile(.5)),'null_max_ba_q975':float(g.max_validation_ba.quantile(.975)),
            'null_max_f1_mean':float(g.max_validation_f1.mean()),'null_max_f1_q025':float(g.max_validation_f1.quantile(.025)),'null_max_f1_q500':float(g.max_validation_f1.quantile(.5)),'null_max_f1_q975':float(g.max_validation_f1.quantile(.975)),
            'p_best_ba_max_stat':float((1+(g.max_validation_ba>=best_ba.validation_ba).sum())/(NULL_REPS+1)),'p_best_f1_max_stat':float((1+(g.max_validation_f1>=best_f1.validation_f1).sum())/(NULL_REPS+1)),
        })
    out=pd.DataFrame(summary); out.to_csv(OUT/'TREE_GRID_NULL_SUITE_SUMMARY.csv',index=False)
    print(out.to_string(index=False))

if __name__=='__main__': main()
