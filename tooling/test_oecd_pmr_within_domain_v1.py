#!/usr/bin/env python3
from pathlib import Path
from itertools import permutations
from datetime import datetime, timezone
import hashlib, json
import numpy as np
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS')
ROUND=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH'
RAW=ROUND/'raw/oecd_pmr_2013/OECD_DF_PMR_UNFILTERED.csv'
CONTRACT=ROOT/'experimental_contracts/OECD_PMR_WITHIN_DOMAIN_TRANSITION_CONTRACT_V1.json'
OUT=ROOT/'experiments/multi_domain_native_edges_v1/pmr_within_domain_v1'; OUT.mkdir(parents=True,exist_ok=True)

def main():
 contract=json.loads(CONTRACT.read_text(encoding='utf8'))
 df=pd.read_csv(RAW,low_memory=False)
 df['wave']=pd.to_numeric(df['TIME_PERIOD'],errors='coerce').astype('Int64')
 df['value']=pd.to_numeric(df['OBS_VALUE'],errors='coerce')
 waves=contract['source_waves']; sub=df[df.wave.isin(waves)][['COU','Country','IND','Indicator','wave','value']]
 wide=sub.pivot_table(index=['COU','Country','IND','Indicator'],columns='wave',values='value',aggfunc='first').reset_index()
 complete=wide.dropna(subset=waves).copy()
 arr=complete[waves].to_numpy(dtype=float); n=len(arr)
 if n==0: raise RuntimeError('no complete four-wave series')
 deltas=np.diff(arr,axis=1); valid=deltas!=0
 scores=[]; rows=[]
 for k in range(3):
  d=deltas[:,k]; v=d!=0; denom=int(v.sum()); up=int((d[v]>0).sum()); down=int((d[v]<0).sum()); score=(max(up,down)/denom) if denom else None
  scores.append(score if score is not None else np.nan)
  rows.append({'interval_start':waves[k],'interval_end':waves[k+1],'complete_series':n,'nonzero_changes':denom,'up_changes':up,'down_changes':down,'zero_changes':int((~v).sum()),'fraction_up':(up/denom if denom else None),'fraction_down':(down/denom if denom else None),'directional_concentration':score})
 obs_max=float(np.nanmax(np.asarray(scores,dtype=float)))
 perms=np.array(list(permutations(range(4))),dtype=int); rng=np.random.default_rng(contract['random_seed']); null_max=np.empty(contract['n_null_replicates'],dtype=float)
 for b in range(contract['n_null_replicates']):
  choices=rng.integers(0,len(perms),size=n); shuffled=arr[np.arange(n)[:,None],perms[choices]]; sd=np.diff(shuffled,axis=1); ss=[]
  for k in range(3):
   d=sd[:,k]; v=d!=0; denom=int(v.sum()); ss.append(max(int((d[v]>0).sum()),int((d[v]<0).sum()))/denom if denom else 0.0)
  null_max[b]=max(ss)
 p_max=(1+int((null_max>=obs_max).sum()))/(len(null_max)+1)
 metrics=pd.DataFrame(rows); metrics['observed_max_stat']=obs_max; metrics['max_stat_empirical_p_value']=p_max; metrics.to_csv(OUT/'PMR_WITHIN_DOMAIN_TRANSITION_METRICS_V1.csv',index=False)
 summary={'test_id':'OECD_PMR_WITHIN_DOMAIN_TRANSITION_V1','contract_ref':str(CONTRACT.relative_to(ROOT)),'source_ref':str(RAW.relative_to(ROOT)),'source_waves':waves,'complete_economy_indicator_series':n,'raw_rows_considered':int(len(sub)),'observed_interval_scores':scores,'observed_max_stat':obs_max,'null_method':contract['null_method'],'n_null_replicates':len(null_max),'null_max_mean':float(null_max.mean()),'null_max_sd':float(null_max.std(ddof=1)),'null_max_q95':float(np.quantile(null_max,.95)),'max_stat_empirical_p_value':p_max,'oos_available':False,'entity_holdout':False,'edge_status':'not_testable','causal_claim':False,'interpretation':'descriptive source-wave directional concentration only; four waves provide no predictive OOS design and no policy-shock date'}
 (OUT/'PMR_WITHIN_DOMAIN_NULL_SUMMARY_V1.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 te={'transition_id':'OECD_PMR_WITHIN_DOMAIN_DIRECTIONAL_CONCENTRATION_V1','source_state':'OECD_PMR_ARCHIVE2013_COMPLETE_ECONOMY_INDICATOR_SERIES','target_state':'OECD_PMR_ADJACENT_SOURCE_WAVE_DIRECTIONAL_CONCENTRATION','lag':1,'split':'descriptive_all_waves','metric':{'name':'max_directional_concentration_across_adjacent_source_wave_intervals','value':obs_max,'interval_metrics':rows},'null_method':contract['null_method'],'p_value':p_max,'entity_holdout':False,'source_refs':[str(CONTRACT.relative_to(ROOT)),str(RAW.relative_to(ROOT)),str((OUT/'PMR_WITHIN_DOMAIN_NULL_SUMMARY_V1.json').relative_to(ROOT))],'edge_status':'not_testable','causal_claim':False,'failure_cases':['only four source-defined waves','no out-of-sample split','no dated policy shock','zero changes excluded from directional denominator','not a composite or annualized series']}
 (OUT/'PMR_WITHIN_DOMAIN_TRANSITION_EVIDENCE_V1.jsonl').write_text(json.dumps(te,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf8')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
