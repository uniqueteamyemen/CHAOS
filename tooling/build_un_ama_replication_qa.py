#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS');RAW=ROOT/'catalog_first/readiness_gate/independent_sources/un_ama_2026/raw';ST=ROOT/'catalog_first/readiness_gate/independent_sources/un_ama_2026/staged';OUT=ROOT/'experiments/macro_plus_eia_energy/un_ama_replication_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def main():
 s=json.loads((OUT/'UN_AMA_REPLICATION_SUMMARY.json').read_text());m=pd.read_csv(OUT/'UN_AMA_REPLICATION_METRICS.csv');n=pd.read_csv(OUT/'UN_AMA_REPLICATION_NULL_SUMMARY.csv');r=pd.read_csv(OUT/'UN_AMA_REPLICATION_REPLAY_ROWS.csv');p=ST/'UN_AMA_INDEPENDENT_GDP_GROWTH_POPULATION_PANEL.csv'
 q={'manifest_type':'CHAOS_un_ama_independent_replication_qa','run_id':s['run_id'],'source':s['source'],'counts':{'raw_growth_bytes':(RAW/'AMA_GDP_GROWTH_ALL_COUNTRIES_RAW.xlsx').stat().st_size,'raw_population_bytes':(RAW/'AMA_EXCHANGE_RATES_POPULATION_ALL_COUNTRIES_RAW.xlsx').stat().st_size,'panel_rows':s['rows_total'],'panel_countries':s['countries_total'],'eligible_origins':s['eligible_origins'],'metric_rows':len(m),'null_summary_rows':len(n),'replay_rows':len(r)},'results':{'validation':m[(m.split=='validation')&(m.model=='high_growth_rule')].to_dict('records'),'confirmation':m[(m.split=='confirmation')&(m.model=='high_growth_rule')].to_dict('records'),'null':n.to_dict('records')},'hashes':{'raw_growth_sha256':sha(RAW/'AMA_GDP_GROWTH_ALL_COUNTRIES_RAW.xlsx'),'raw_population_sha256':sha(RAW/'AMA_EXCHANGE_RATES_POPULATION_ALL_COUNTRIES_RAW.xlsx'),'staged_panel_sha256':sha(p)},'flags':{'used_future_2020_2024':s['used_future_2020_2024'],'prior_locked_test_reopened':s['prior_locked_test_reopened'],'threshold_changed_after_metrics':s['threshold_changed_after_metrics'],'raw_modified':s['raw_modified'],'imputation':s['imputation'],'normalization':s['normalization'],'causal_claims_permitted':s['causal_claims_permitted']},'qa_pass_conditions':{'four_split_metrics':len(m)==12,'two_null_splits':len(n)==2,'two_thousand_null_each':set(n.replicates.astype(int))=={2000},'no_future_2020_2024':s['used_future_2020_2024'] is False,'previous_test_closed':s['prior_locked_test_reopened'] is False,'no_post_metric_change':s['threshold_changed_after_metrics'] is False,'raw_unchanged':s['raw_modified'] is False,'no_transformations':s['imputation'] is False and s['normalization'] is False,'no_causal_claim':s['causal_claims_permitted'] is False},'artifacts':sorted(str(x.relative_to(ROOT)) for d in [RAW,ST,OUT] for x in d.iterdir() if x.is_file())}
 (OUT/'UN_AMA_REPLICATION_QA_MANIFEST.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'qa_all_true':all(q['qa_pass_conditions'].values()),**q['counts'],'validation_ba':q['results']['validation'][0]['balanced_accuracy'],'confirmation_ba':q['results']['confirmation'][0]['balanced_accuracy']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
