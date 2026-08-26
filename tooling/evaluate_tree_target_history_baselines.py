#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score
from explore_tree_reverse_extraction import TARGET, HORIZONS, FAMILIES, SEEDS, DEPTHS, MIN_LEAF, build_origins, load_panel, select_leaf

ROOT=Path('/home/ubuntu/CHAOS')
OUT=ROOT/'experiments/macro_plus_eia_energy/reverse_extraction_tree_v1'

def main():
    rows=[]; panel=load_panel()
    for h in HORIZONS:
        origins=build_origins(panel,h)
        feats=[f'{TARGET}__lag{i}' for i in (0,1,2)]
        for family in FAMILIES:
            label=f'outcome_{family}'
            fit=origins[origins.split=='discovery_fit'].dropna(subset=feats+[label])
            inner=origins[origins.split=='discovery_inner'].dropna(subset=feats+[label])
            val=origins[origins.split=='validation'].dropna(subset=feats+[label])
            for depth in DEPTHS:
                for seed in SEEDS:
                    tree=DecisionTreeClassifier(max_depth=depth,min_samples_leaf=MIN_LEAF,class_weight='balanced',random_state=seed)
                    tree.fit(fit[feats].to_numpy(float),fit[label].astype(int).to_numpy())
                    candidates=select_leaf(tree,inner,inner[label].astype(int).to_numpy(),feats,'discovery_inner')
                    if candidates.empty: continue
                    chosen=candidates.sort_values(['balanced_accuracy','f1','support','path_length'],ascending=[False,False,False,True]).iloc[0]
                    leaf=int(chosen.leaf_id)
                    for split,frame in [('discovery_fit',fit),('discovery_inner',inner),('validation',val)]:
                        y=frame[label].astype(int).to_numpy(); pred=tree.apply(frame[feats].to_numpy(float))==leaf
                        rows.append({'baseline':'target_history_tree','horizon':h,'family':family,'depth':depth,'seed':seed,'split':split,'support':int(pred.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,pred,zero_division=0),'recall':recall_score(y,pred,zero_division=0),'f1':f1_score(y,pred,zero_division=0),'balanced_accuracy':balanced_accuracy_score(y,pred),'path_length':int(chosen.path_length),'clauses':chosen.clauses})
            # prevalence controls on validation
            y=val[label].astype(int).to_numpy();
            for name,pred in [('always_negative',np.zeros(len(y),bool)),('always_positive',np.ones(len(y),bool))]:
                rows.append({'baseline':name,'horizon':h,'family':family,'depth':None,'seed':None,'split':'validation','support':int(pred.sum()),'positive_outcomes':int(y.sum()),'precision':precision_score(y,pred,zero_division=0),'recall':recall_score(y,pred,zero_division=0),'f1':f1_score(y,pred,zero_division=0),'balanced_accuracy':balanced_accuracy_score(y,pred),'path_length':0,'clauses':''})
    out=pd.DataFrame(rows); out.to_csv(OUT/'TREE_TARGET_HISTORY_BASELINES.csv',index=False)
    print(out[out.split=='validation'].sort_values(['horizon','family','balanced_accuracy'],ascending=[True,True,False]).to_string(index=False))

if __name__=='__main__': main()
