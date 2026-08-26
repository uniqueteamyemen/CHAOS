#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS');OUT=ROOT/'experiments/macro_plus_eia_energy/high_growth_outcomes_v1';PANEL=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv';RAW=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_RAW_2000_2024_WIDE.csv'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def gsha(p):
 import subprocess
 try:b=subprocess.check_output(['git','show',f'HEAD:{p.relative_to(ROOT)}'],cwd=ROOT)
 except subprocess.CalledProcessError:return None
 return hashlib.sha256(b).hexdigest()
def main():
 s=json.loads((OUT/'HIGH_GROWTH_OUTCOME_RUN_SUMMARY.json').read_text());m=pd.read_csv(OUT/'HIGH_GROWTH_OUTCOME_METRICS.csv');a=pd.read_csv(OUT/'HIGH_GROWTH_OUTCOME_AGGREGATE.csv');n=pd.read_csv(OUT/'HIGH_GROWTH_OUTCOME_MAXSTAT_NULL.csv')
 q={'manifest_type':'CHAOS_high_growth_outcome_families_qa','run_id':s['run_id'],'counts':{'spec_count':s['spec_count'],'metric_rows':len(m),'aggregate_rows':len(a),'null_replicates':len(n),'families':len(s['families']),'horizons':len(s['horizons'])},'best_by_ba':s['best_by_ba'],'best_by_f1':s['best_by_f1'],'maxstat':{'p_ba':s['p_best_ba_maxstat'],'p_f1':s['p_best_f1_maxstat'],'null_ba_q975':s['null_max_mean_ba_q975'],'null_f1_q975':s['null_max_mean_f1_q975']},'raw_integrity':{'panel_sha256':sha(PANEL),'panel_head_sha256':gsha(PANEL),'raw_sha256':sha(RAW),'raw_head_sha256':gsha(RAW),'panel_matches_head':sha(PANEL)==gsha(PANEL),'raw_matches_head':sha(RAW)==gsha(RAW)},'flags':{'locked_test_reopened':s['locked_test_reopened'],'raw_data_modified':s['raw_data_modified'],'imputation':s['imputation'],'normalization':s['normalization']},'qa_pass_conditions':{'21_specs':s['spec_count']==21,'null_2000':s['null_replicates']==2000 and len(n)==2000,'three_horizons':len(s['horizons'])==3,'seven_families':len(s['families'])==7,'locked_test_closed':s['locked_test_reopened'] is False,'raw_unchanged':s['raw_data_modified'] is False and sha(PANEL)==gsha(PANEL) and sha(RAW)==gsha(RAW),'no_transformations':s['imputation'] is False and s['normalization'] is False},'artifacts':sorted(str(p.relative_to(ROOT)) for p in OUT.iterdir() if p.is_file())}
 (OUT/'HIGH_GROWTH_OUTCOME_QA_MANIFEST.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'qa_all_true':all(q['qa_pass_conditions'].values()),**q['counts'],'best_ba':s['best_by_ba'],'p_ba':s['p_best_ba_maxstat']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
