#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/macro_plus_eia_energy/regime_locked_test_v1'; PANEL=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'; RAW=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_RAW_2000_2024_WIDE.csv'
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
 s=json.loads((OUT/'LOCKED_TEST_RUN_SUMMARY.json').read_text()); m=pd.read_csv(OUT/'LOCKED_TEST_METRICS.csv'); y=pd.read_csv(OUT/'LOCKED_TEST_METRICS_BY_YEAR.csv'); e=pd.read_csv(OUT/'LOCKED_TEST_METRICS_BY_ENTITY.csv'); r=pd.read_csv(OUT/'LOCKED_TEST_REPLAY_ROWS.csv')
 q={'manifest_type':'CHAOS_regime_locked_test_v1_qa','run_id':s['run_id'],'counts':{'origins':s['n_origins'],'entities':s['entities'],'target_years':len(s['target_years']),'models':len(s['models_replayed']),'metric_rows':len(m),'year_rows':len(y),'entity_rows':len(e),'replay_rows':len(r)},'frozen_contract':s['contract'],'flags':{'locked_test_executed':s['locked_test_executed'],'test_used_for_selection':s['test_used_for_selection'],'path_or_threshold_changed_after_test':s['path_or_threshold_changed_after_test'],'raw_data_modified':s['raw_data_modified'],'imputation':s['imputation'],'normalization':s['normalization'],'causal_claims_permitted':s['causal_claims_permitted']},'raw_integrity':{'panel_sha256':sha(PANEL),'panel_head_sha256':gsha(PANEL),'raw_sha256':sha(RAW),'raw_head_sha256':gsha(RAW),'panel_matches_head':sha(PANEL)==gsha(PANEL),'raw_matches_head':sha(RAW)==gsha(RAW)},'qa_pass_conditions':{'695_origins':s['n_origins']==695,'139_entities':s['entities']==139,'five_target_years':s['target_years']==[2020,2021,2022,2023,2024],'two_frozen_paths_present':set(['population_regime_v1','energy_per_gdp_regime_v1']).issubset(set(s['models_replayed'])),'test_not_used_for_selection':s['test_used_for_selection'] is False,'no_post_test_change':s['path_or_threshold_changed_after_test'] is False,'raw_unchanged':s['raw_data_modified'] is False and sha(PANEL)==gsha(PANEL) and sha(RAW)==gsha(RAW),'no_transformations':s['imputation'] is False and s['normalization'] is False,'no_causal_claim':s['causal_claims_permitted'] is False},'artifacts':sorted(str(p.relative_to(ROOT)) for p in OUT.iterdir() if p.is_file())}
 (OUT/'REGIME_LOCKED_TEST_QA_MANIFEST.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'qa_all_true':all(q['qa_pass_conditions'].values()),**q['counts'],'population_ba':float(m.loc[m.model=='population_regime_v1','balanced_accuracy'].iloc[0]),'energy_ba':float(m.loc[m.model=='energy_per_gdp_regime_v1','balanced_accuracy'].iloc[0])},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
