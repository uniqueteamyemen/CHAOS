#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score
from explore_tree_reverse_extraction import TARGET, build_origins, feature_columns, load_panel, select_leaf, MIN_LEAF, MODES, DEPTHS, SEEDS

ROOT=Path('/home/ubuntu/CHAOS')
OUT=ROOT/'experiments/macro_plus_eia_energy/reverse_extraction_tree_v1'
H=3
FAMILY='material_drop_2pp'
# Outcome-year folds; all validation outcomes end before locked test begins.
FOLDS=[
    ('fold_A', (2006,2010), (2011,2013), (2014,2016)),
    ('fold_B', (2006,2012), (2013,2015), (2016,2019)),
    ('fold_C', (2007,2011), (2012,2014), (2015,2018)),
]

def main():
    panel=load_panel(); origins=build_origins(panel,H); rows=[]; paths=[]
    label=f'outcome_{FAMILY}'
    for fold,fit_years,inner_years,val_years in FOLDS:
        fit=origins[origins.target_year.between(*fit_years)].dropna(subset=[label])
        inner=origins[origins.target_year.between(*inner_years)].dropna(subset=[label])
        val=origins[origins.target_year.between(*val_years)].dropna(subset=[label])
        for mode in MODES:
            feats=feature_columns(mode)
            fit=fit.dropna(subset=feats); inner=inner.dropna(subset=feats); val=val.dropna(subset=feats)
            for depth in DEPTHS:
                for seed in SEEDS:
                    tree=DecisionTreeClassifier(max_depth=depth,min_samples_leaf=MIN_LEAF,class_weight='balanced',random_state=seed)
                    tree.fit(fit[feats].to_numpy(float),fit[label].astype(int).to_numpy())
                    cand=select_leaf(tree,inner,inner[label].astype(int).to_numpy(),feats,'inner')
                    if cand.empty: continue
                    chosen=cand.sort_values(['balanced_accuracy','f1','support','path_length'],ascending=[False,False,False,True]).iloc[0]
                    leaf=int(chosen.leaf_id); clauses=chosen.clauses
                    for split,frame in [('fit',fit),('inner',inner),('validation',val)]:
                        y=frame[label].astype(int).to_numpy(); pred=tree.apply(frame[feats].to_numpy(float))==leaf
                        rows.append({'fold':fold,'fit_years':str(fit_years),'inner_years':str(inner_years),'validation_years':str(val_years),'mode':mode,'depth':depth,'seed':seed,'split':split,'support':int(pred.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,pred,zero_division=0),'recall':recall_score(y,pred,zero_division=0),'f1':f1_score(y,pred,zero_division=0),'balanced_accuracy':balanced_accuracy_score(y,pred),'path_length':int(chosen.path_length),'clauses':clauses})
                    paths.append({'fold':fold,'mode':mode,'depth':depth,'seed':seed,'inner_ba':float(chosen.balanced_accuracy),'inner_f1':float(chosen.f1),'path_length':int(chosen.path_length),'clauses':clauses})
    result=pd.DataFrame(rows); result.to_csv(OUT/'TREE_ROLLING_STABILITY_METRICS.csv',index=False); pd.DataFrame(paths).to_csv(OUT/'TREE_ROLLING_SELECTED_PATHS.csv',index=False)
    val=result[result.split=='validation']; best=val.sort_values(['balanced_accuracy','f1'],ascending=False).head(20)
    summary={'run_id':'reverse_extraction_tree_rolling_stability_v1','family':FAMILY,'horizon':H,'folds':[{'id':x[0],'fit':x[1],'inner':x[2],'validation':x[3]} for x in FOLDS],'validation_rows':len(val),'locked_test_executed':False,'raw_data_modified':False,'imputation':False,'normalization':False,'decision':'rolling stability diagnostic; no promotion'}
    (OUT/'TREE_ROLLING_STABILITY_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2)); print(best.to_string(index=False))

if __name__=='__main__': main()
