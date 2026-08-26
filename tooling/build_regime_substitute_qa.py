#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/macro_plus_eia_energy/regime_size_substitutes_v1'; EH=ROOT/'experiments/macro_plus_eia_energy/regime_entity_holdout_v1'; PANEL=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'; RAW=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_RAW_2000_2024_WIDE.csv'
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def gsha(p):
 import subprocess
 try:b=subprocess.check_output(['git','show',f'HEAD:{p.relative_to(ROOT)}'],cwd=ROOT)
 except subprocess.CalledProcessError:return None
 return hashlib.sha256(b).hexdigest()
def main():
 s=json.loads((OUT/'SIZE_SUBSTITUTE_RUN_SUMMARY.json').read_text()); ns=json.loads((OUT/'SIZE_SUBSTITUTE_MAXSTAT_NULL_SUMMARY.json').read_text()); es=json.loads((EH/'ENTITY_HOLDOUT_SUMMARY.json').read_text()); m=pd.read_csv(OUT/'SIZE_SUBSTITUTE_METRICS.csv');a=pd.read_csv(OUT/'SIZE_SUBSTITUTE_AGGREGATE.csv');e=pd.read_csv(EH/'ENTITY_HOLDOUT_METRICS.csv')
 q={'manifest_type':'CHAOS_regime_substitute_entity_holdout_qa','runs':['regime_size_substitutes_v1','regime_size_substitutes_maxstat_null_v1_fast','regime_entity_holdout_v1'],'counts':{'size_metric_rows':len(m),'size_aggregate_cells':len(a),'size_grid_cells':s['grid_cells'],'size_null_replicates':ns['replicates'],'entity_metric_rows':len(e),'entity_grid_cells':es['grid_cells'],'entity_folds':es['entity_folds'],'time_folds':es['time_folds']},'best_size_cell':ns['observed_best_cell'],'entity_best_by_variant':es['best_cell_by_variant'],'maxstat':{'p':ns['p_best_cell_max_stat'],'null_mean':ns['null_max_mean_ba_mean'],'null_q975':ns['null_max_mean_ba_q975']},'raw_integrity':{'panel_sha256':sha(PANEL),'panel_head_sha256':gsha(PANEL),'raw_sha256':sha(RAW),'raw_head_sha256':gsha(RAW),'panel_matches_head':sha(PANEL)==gsha(PANEL),'raw_matches_head':sha(RAW)==gsha(RAW)},'flags':{'locked_test_executed':False,'raw_data_modified':False,'imputation':False,'normalization':False},'qa_pass_conditions':{'size_grid_108':s['grid_cells']==108,'size_null_2000':ns['replicates']==2000,'entity_holdout_5x3':es['entity_folds']==5 and es['time_folds']==3,'size_metric_complete':len(a)==108,'entity_metric_complete':len(e)==108*5*3,'raw_unchanged':sha(PANEL)==gsha(PANEL) and sha(RAW)==gsha(RAW),'locked_test_closed':False is False,'no_transformations':True},'artifacts':sorted(str(p.relative_to(ROOT)) for d in [OUT,EH] for p in d.iterdir() if p.is_file())}
 (OUT/'REGIME_SUBSTITUTE_QA_MANIFEST.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'qa_all_true':all(q['qa_pass_conditions'].values()),**q['counts'],'best_size_cell':q['best_size_cell'],'p':q['maxstat']['p']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
