#!/usr/bin/env python3
"""Max-statistic null controls for the exploratory tree-path grid."""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score
from explore_tree_reverse_extraction import (
    ALL_FEATURES, FAMILIES, HORIZONS, MODES, DEPTHS, SEEDS,
    TARGET, OUT, build_origins, feature_columns, load_panel,
    select_leaf, MIN_LEAF,
)

NULL_REPS=2000
NULL_SEED=917
VALIDATION_YEARS=(2016,2019)


def ba_fast(y,p):
    y=y.astype(bool); p=p.astype(bool)
    pos=y.sum(); neg=(~y).sum()
    return ((p[y].mean() if pos else 0.0) + ((~p[~y]).mean() if neg else 0.0))/2


def f1_fast(y,p):
    y=y.astype(bool); p=p.astype(bool)
    tp=np.sum(y&p); fp=np.sum(~y&p); fn=np.sum(y&~p)
    return 2*tp/(2*tp+fp+fn) if (2*tp+fp+fn) else 0.0


def make_grid():
    panel=load_panel(); models=[]
    for h in HORIZONS:
        origins=build_origins(panel,h)
        for family in FAMILIES:
            label=f'outcome_{family}'
            for mode in MODES:
                features=feature_columns(mode)
                fit=origins[origins.split=='discovery_fit'].dropna(subset=features+[label])
                inner=origins[origins.split=='discovery_inner'].dropna(subset=features+[label])
                val=origins[origins.split=='validation'].dropna(subset=features+[label])
                Xfit=fit[features].to_numpy(float); yfit=fit[label].astype(int).to_numpy()
                Xinner=inner[features].to_numpy(float); yinner=inner[label].astype(int).to_numpy()
                Xval=val[features].to_numpy(float); yval=val[label].astype(int).to_numpy()
                for depth in DEPTHS:
                    for seed in SEEDS:
                        tree=DecisionTreeClassifier(max_depth=depth,min_samples_leaf=MIN_LEAF,class_weight='balanced',random_state=seed)
                        tree.fit(Xfit,yfit)
                        cand=select_leaf(tree,inner,yinner,features,'discovery_inner')
                        if cand.empty: continue
                        chosen=cand.sort_values(['balanced_accuracy','f1','support','path_length'],ascending=[False,False,False,True]).iloc[0]
                        leaf=int(chosen.leaf_id)
                        pred=(tree.apply(Xval)==leaf)
                        models.append({'model_id':f'h{h}|{family}|{mode}|d{depth}|s{seed}','horizon':h,'family':family,'mode':mode,'depth':depth,'seed':seed,'inner_ba':float(chosen.balanced_accuracy),'inner_f1':float(chosen.f1),'path_length':int(chosen.path_length),'clauses':chosen.clauses,'y':yval,'pred':pred,'entity':val.entity_code.to_numpy(),'year':val.target_year.to_numpy()})
    return models


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    models=make_grid()
    observed=[]
    for m in models:
        observed.append({'model_id':m['model_id'],'horizon':m['horizon'],'family':m['family'],'mode':m['mode'],'depth':m['depth'],'seed':m['seed'],'inner_ba':m['inner_ba'],'inner_f1':m['inner_f1'],'path_length':m['path_length'],'clauses':m['clauses'],'validation_ba':ba_fast(m['y'],m['pred']),'validation_f1':f1_fast(m['y'],m['pred']),'support':int(m['pred'].sum())})
    obs=pd.DataFrame(observed)
    obs.to_csv(OUT/'TREE_GRID_OBSERVED_VALIDATION.csv',index=False)
    rng=np.random.default_rng(NULL_SEED)
    max_rows=[]
    for rep in range(NULL_REPS):
        # Generate one entity-preserving permutation per horizon/family validation label vector.
        perm_cache={}
        for key in {(m['horizon'],m['family']) for m in models}:
            group=[m for m in models if (m['horizon'],m['family'])==key][0]
            y=group['y']; ent=group['entity']; yp=y.copy()
            for e in np.unique(ent):
                idx=np.flatnonzero(ent==e); yp[idx]=rng.permutation(yp[idx])
            perm_cache[key]=yp
        max_ba=-1.0; max_f1=-1.0; max_ba_id=''; max_f1_id=''
        for m in models:
            yp=perm_cache[(m['horizon'],m['family'])]
            ba=ba_fast(yp,m['pred']); f1=f1_fast(yp,m['pred'])
            if ba>max_ba: max_ba=ba; max_ba_id=m['model_id']
            if f1>max_f1: max_f1=f1; max_f1_id=m['model_id']
        max_rows.append({'replicate':rep,'null':'entity_label_permutation_max_stat','max_validation_ba':max_ba,'max_ba_model_id':max_ba_id,'max_validation_f1':max_f1,'max_f1_model_id':max_f1_id})
    null=pd.DataFrame(max_rows); null.to_csv(OUT/'TREE_GRID_MAXSTAT_NULL_REPLICATES.csv',index=False)
    best_ba=obs.loc[obs.validation_ba.idxmax()]; best_f1=obs.loc[obs.validation_f1.idxmax()]
    summary={
        'run_id':'reverse_extraction_tree_maxstat_null_v1','models':len(models),'null_replicates':NULL_REPS,'null_seed':NULL_SEED,
        'observed_best_ba':float(best_ba.validation_ba),'observed_best_ba_model_id':best_ba.model_id,
        'observed_best_f1':float(best_f1.validation_f1),'observed_best_f1_model_id':best_f1.model_id,
        'null_max_ba_mean':float(null.max_validation_ba.mean()),'null_max_ba_q025':float(null.max_validation_ba.quantile(.025)),'null_max_ba_q500':float(null.max_validation_ba.quantile(.5)),'null_max_ba_q975':float(null.max_validation_ba.quantile(.975)),
        'null_max_f1_mean':float(null.max_validation_f1.mean()),'null_max_f1_q025':float(null.max_validation_f1.quantile(.025)),'null_max_f1_q500':float(null.max_validation_f1.quantile(.5)),'null_max_f1_q975':float(null.max_validation_f1.quantile(.975)),
        'p_best_ba_max_stat':float((1+(null.max_validation_ba>=best_ba.validation_ba).sum())/(NULL_REPS+1)),
        'p_best_f1_max_stat':float((1+(null.max_validation_f1>=best_f1.validation_f1).sum())/(NULL_REPS+1)),
        'locked_test_executed':False,'raw_data_modified':False,'imputation':False,'normalization':False,
        'decision':'exploratory_grid_maxstat_only; no promotion; locked test remains closed',
    }
    (OUT/'TREE_GRID_MAXSTAT_NULL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('\nTOP OBSERVED')
    print(obs.sort_values(['validation_ba','validation_f1'],ascending=False).head(15).to_string(index=False))

if __name__=='__main__': main()
