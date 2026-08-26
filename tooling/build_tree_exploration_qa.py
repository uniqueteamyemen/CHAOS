#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS')
OUT=ROOT/'experiments/macro_plus_eia_energy/reverse_extraction_tree_v1'
PANEL=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
RAW=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_RAW_2000_2024_WIDE.csv'
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
 return h.hexdigest()
def git_hash(p):
 import subprocess
 try: b=subprocess.check_output(['git','show',f'HEAD:{p.relative_to(ROOT)}'],cwd=ROOT)
 except subprocess.CalledProcessError: return None
 return hashlib.sha256(b).hexdigest()
def main():
 grid=pd.read_csv(OUT/'TREE_GRID_OBSERVED_VALIDATION.csv'); null=pd.read_csv(OUT/'TREE_GRID_MAXSTAT_NULL_REPLICATES.csv'); suite=pd.read_csv(OUT/'TREE_GRID_NULL_SUITE_SUMMARY.csv'); roll=pd.read_csv(OUT/'TREE_ROLLING_STABILITY_METRICS.csv'); summary=json.loads((OUT/'TREE_GRID_MAXSTAT_NULL_SUMMARY.json').read_text())
 manifest={
  'manifest_type':'CHAOS_tree_path_exploration_qa','run_id':'reverse_extraction_tree_v1_exploratory',
  'counts':{'grid_models':len(grid),'maxstat_replicates':len(null),'suite_summary_rows':len(suite),'rolling_rows':len(roll)},
  'best_observed':{'model_id':summary['observed_best_ba_model_id'],'balanced_accuracy':summary['observed_best_ba'],'f1':summary['observed_best_f1']},
  'raw_integrity':{'panel_sha256':sha(PANEL),'panel_head_sha256':git_hash(PANEL),'raw_sha256':sha(RAW),'raw_head_sha256':git_hash(RAW),'panel_matches_head':sha(PANEL)==git_hash(PANEL),'raw_matches_head':sha(RAW)==git_hash(RAW)},
  'execution_flags':{'locked_test_executed':summary['locked_test_executed'],'raw_data_modified':summary['raw_data_modified'],'imputation':summary['imputation'],'normalization':summary['normalization']},
  'qa_pass_conditions':{
   'grid_72_models':len(grid)==72,'maxstat_2000':len(null)==2000,'suite_three_nulls':set(suite['null'])=={'label_permutation','support_matched','cyclic_shift'},'rolling_has_three_folds':roll['fold'].nunique()==3,'locked_test_closed':summary['locked_test_executed'] is False,'raw_unchanged':summary['raw_data_modified'] is False,'panel_matches_head':sha(PANEL)==git_hash(PANEL),'raw_matches_head':sha(RAW)==git_hash(RAW),'no_imputation_or_normalization':summary['imputation'] is False and summary['normalization'] is False},
  'artifacts':sorted([str(p.relative_to(ROOT)) for p in OUT.iterdir() if p.is_file()])
 }
 (OUT/'TREE_EXPLORATION_QA_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'qa_all_true':all(manifest['qa_pass_conditions'].values()),**manifest['counts'],'best_model':summary['observed_best_ba_model_id'],'locked_test_executed':summary['locked_test_executed']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
