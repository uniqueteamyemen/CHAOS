#!/usr/bin/env python3
from pathlib import Path
from itertools import permutations
import json
import numpy as np
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); RAW=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/raw/oecd_pmr_2013/OECD_DF_PMR_UNFILTERED.csv'; CONTRACT=ROOT/'experimental_contracts/OECD_PMR_WITHIN_DOMAIN_STABILITY_NULL_CONTRACT_V1_1.json'; OUT=ROOT/'experiments/multi_domain_native_edges_v1/pmr_within_domain_v1'; OUT.mkdir(parents=True,exist_ok=True)
def maxscore(a):
 s=[]
 for k in range(3):
  d=a[:,k+1]-a[:,k]; d=d[d!=0]
  s.append(max(int((d>0).sum()),int((d<0).sum()))/len(d) if len(d) else 0.0)
 return max(s),s
def main():
 c=json.loads(CONTRACT.read_text()); d=pd.read_csv(RAW,low_memory=False); d['wave']=pd.to_numeric(d.TIME_PERIOD,errors='coerce').astype('Int64'); d['value']=pd.to_numeric(d.OBS_VALUE,errors='coerce'); waves=[1998,2003,2008,2013]; w=d[d.wave.isin(waves)].pivot_table(index=['COU','Country','IND','Indicator'],columns='wave',values='value',aggfunc='first').dropna(subset=waves).reset_index(); a=w[waves].to_numpy(float); obs,obs_int=maxscore(a); perms=list(permutations(range(4))); exact=[]
 for p in perms: exact.append(maxscore(a[:,p])[0])
 exact=np.array(exact); common_p=float((exact>=obs).sum()/len(exact)); rng=np.random.default_rng(c['random_seed']); entities=w.COU.unique(); groups=[a[w.COU.to_numpy()==e] for e in entities]; boots=np.empty(c['bootstrap_replicates'])
 for b in range(len(boots)): boots[b]=maxscore(np.vstack([groups[i] for i in rng.integers(0,len(groups),len(groups))]))[0]
 summary={'test_id':'OECD_PMR_WITHIN_DOMAIN_STABILITY_NULL_V1_1','contract_ref':str(CONTRACT.relative_to(ROOT)),'complete_series':int(len(a)),'complete_entities':int(len(entities)),'complete_indicators':int(w.IND.nunique()),'observed_interval_scores':obs_int,'observed_max_stat':obs,'common_wave_permutation_count':len(exact),'common_wave_null_max_stats':exact.tolist(),'common_wave_exact_p_value':common_p,'common_wave_null_resolution':1/len(exact),'cluster_bootstrap_replicates':len(boots),'cluster_bootstrap_max_mean':float(boots.mean()),'cluster_bootstrap_max_sd':float(boots.std(ddof=1)),'cluster_bootstrap_max_q025':float(np.quantile(boots,.025)),'cluster_bootstrap_max_q975':float(np.quantile(boots,.975)),'edge_status':'not_testable','causal_claim':False,'oos_available':False,'interpretation':'dependency-aware sensitivity controls remain descriptive; exact common-wave permutation has coarse 1/24 resolution; four source waves cannot support predictive OOS promotion'}; (OUT/'PMR_STABILITY_NULL_SENSITIVITY_V1_1.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({k:v for k,v in summary.items() if k not in ['common_wave_null_max_stats']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
