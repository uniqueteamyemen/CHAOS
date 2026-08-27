#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); d=ROOT/'experiments/dual_track_v02/imf_partner_substitution_v3'; src=sorted((d/'stability_runs').glob('SUMMARY_SEED_*.json'))
rows=[]
for p in src:
 s=json.loads(p.read_text()); seed=p.stem.split('_')[-1]
 for n in s['nulls']:
  if n['variant'] in ('identity_sequence_null','time_placebo_sequence_shift_proxy'):
   rows.append({'seed':int(seed),'split':n['split'],'variant':n['variant'],'horizon':n['horizon'],'observed_rate':n.get('observed_rate'),'null_mean':n.get('null_mean'),'contrast':n.get('contrast'),'p_value':n.get('p_value'),'unique_statistics':n.get('unique_statistics')})
r=pd.DataFrame(rows); r.to_csv(d/'IMF_IMTS_PARTNER_SUBSTITUTION_STABILITY_V3.csv',index=False)
summary={'run_count':len(src),'seeds':[int(p.stem.split('_')[-1]) for p in src],'rows':len(r),'ranges':[],'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in src}}
for (split,var,h),g in r.groupby(['split','variant','horizon']):
 x={'split':split,'variant':var,'horizon':int(h),'observed_rate_min':None if g.observed_rate.isna().all() else float(g.observed_rate.min()),'observed_rate_max':None if g.observed_rate.isna().all() else float(g.observed_rate.max()),'null_mean_min':float(g.null_mean.min()),'null_mean_max':float(g.null_mean.max()),'p_value_min':None if g.p_value.isna().all() else float(g.p_value.min()),'p_value_max':None if g.p_value.isna().all() else float(g.p_value.max()),'unique_statistics_min':int(g.unique_statistics.min())}; summary['ranges'].append(x)
summary['status']='recorded_stability'; summary['contract_ref']='experimental_contracts/dual_track_v02/IMF_IMTS_PARTNER_SUBSTITUTION_CONTRACT_V3.json'; (d/'IMF_IMTS_PARTNER_SUBSTITUTION_STABILITY_SUMMARY_V3.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'run_count':summary['run_count'],'rows':summary['rows'],'output':'IMF_IMTS_PARTNER_SUBSTITUTION_STABILITY_SUMMARY_V3.json'},ensure_ascii=False,indent=2))
