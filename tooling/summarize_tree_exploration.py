#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT=Path('/home/ubuntu/CHAOS')
OUT=ROOT/'experiments/macro_plus_eia_energy/reverse_extraction_tree_v1'
metrics=pd.read_csv(OUT/'TREE_PATH_METRICS_BY_SPLIT.csv')
paths=pd.read_csv(OUT/'TREE_EXTRACTED_PATHS.csv')
selected=pd.read_csv(OUT/'TREE_SELECTED_PATHS.csv')

# Use only model configurations selected in discovery_inner; validation is for replay comparison.
key=['horizon','family','mode','depth','seed','selected_leaf_id']
val=metrics[metrics.split=='validation'].copy()
inner=metrics[metrics.split=='discovery_inner'].copy()
merged=val.merge(inner[key+['balanced_accuracy','f1','support']].rename(columns={'balanced_accuracy':'inner_ba','f1':'inner_f1','support':'inner_support'}),on=key,how='left')
merged=merged.merge(paths[['horizon','family','mode','depth','seed','leaf_id','path_length','clauses']].rename(columns={'leaf_id':'selected_leaf_id'}),on=['horizon','family','mode','depth','seed','selected_leaf_id'],how='left')
# Per group, identify the model with best validation BA and the model with best validation F1.
rows=[]
for (h,f,m),g in merged.groupby(['horizon','family','mode']):
    for criterion in ['balanced_accuracy','f1']:
        r=g.sort_values([criterion,'inner_ba','inner_f1'],ascending=[False,False,False]).iloc[0]
        rows.append({'horizon':h,'family':f,'mode':m,'chosen_by':criterion,**r.to_dict()})
summary=pd.DataFrame(rows)
summary.to_csv(OUT/'TREE_VALIDATION_BEST_BY_FAMILY.csv',index=False)
print(summary[['horizon','family','mode','chosen_by','depth','seed','support','positive_outcomes','precision','recall','f1','balanced_accuracy','inner_ba','path_length','clauses']].to_string(index=False))
print('\n--- overall top validation ---')
print(merged.sort_values(['balanced_accuracy','f1'],ascending=False)[['horizon','family','mode','depth','seed','support','positive_outcomes','precision','recall','f1','balanced_accuracy','inner_ba','path_length','clauses']].head(20).to_string(index=False))
