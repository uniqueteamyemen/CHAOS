#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/macro_plus_eia_energy/threshold_grid_v1'; PANEL=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'; RAW=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_RAW_2000_2024_WIDE.csv'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
 return h.hexdigest()
def gsha(p):
 import subprocess
 try: b=subprocess.check_output(['git','show',f'HEAD:{p.relative_to(ROOT)}'],cwd=ROOT)
 except subprocess.CalledProcessError:return None
 return hashlib.sha256(b).hexdigest()
def main():
 metrics=pd.read_csv(OUT/'THRESHOLD_GRID_METRICS.csv'); agg=pd.read_csv(OUT/'THRESHOLD_GRID_AGGREGATE.csv'); null=pd.read_csv(OUT/'THRESHOLD_GRID_MAXSTAT_NULL_REPLICATES.csv'); summary=json.loads((OUT/'THRESHOLD_GRID_MAXSTAT_NULL_SUMMARY.json').read_text())
 manifest={'manifest_type':'CHAOS_threshold_grid_stability_qa','run_id':'threshold_grid_stability_v1','counts':{'metric_rows':len(metrics),'aggregate_cells':len(agg),'null_replicates':len(null),'folds':metrics.fold.nunique(),'grid_cells':summary['grid_cells']},'best_cell':summary['observed_best_cell'],'raw_integrity':{'panel_sha256':sha(PANEL),'panel_head_sha256':gsha(PANEL),'raw_sha256':sha(RAW),'raw_head_sha256':gsha(RAW),'panel_matches_head':sha(PANEL)==gsha(PANEL),'raw_matches_head':sha(RAW)==gsha(RAW)},'flags':{'locked_test_executed':summary['locked_test_executed'],'raw_data_modified':summary['raw_data_modified'],'imputation':summary.get('imputation',False),'normalization':summary.get('normalization',False)},'qa_pass_conditions':{'grid_36_cells':summary['grid_cells']==36,'three_folds':metrics.fold.nunique()==3,'null_2000':len(null)==2000,'locked_test_closed':summary['locked_test_executed'] is False,'raw_unchanged':summary['raw_data_modified'] is False,'panel_matches_head':sha(PANEL)==gsha(PANEL),'raw_matches_head':sha(RAW)==gsha(RAW),'no_imputation_or_normalization':summary.get('imputation',False) is False and summary.get('normalization',False) is False},'artifacts':sorted(str(p.relative_to(ROOT)) for p in OUT.iterdir() if p.is_file())}
 (OUT/'THRESHOLD_GRID_QA_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'qa_all_true':all(manifest['qa_pass_conditions'].values()),**manifest['counts'],'best_cell':summary['observed_best_cell'],'p_best_cell_max_stat':summary['p_best_cell_max_stat']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
