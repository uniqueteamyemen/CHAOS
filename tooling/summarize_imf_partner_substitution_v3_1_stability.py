#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); d=ROOT/'experiments/dual_track_v02/imf_partner_substitution_v3_1'; files=sorted((d/'stability_runs').glob('SUMMARY_SEED_*.json')); rows=[]
for p in files:
 s=json.loads(p.read_text()); seed=p.stem.split('_')[-1]
 for h,x in s['confirmation_scores'].items(): rows.append({'seed':int(seed),'horizon':int(h),'events':x['events'],'reporters':x['reporters'],'candidate_rate':x['candidate_rate'],'rank_rate':x['rank_rate'],'candidate_lift_vs_rank':x['candidate_lift_vs_rank'],'brier_candidate':x['brier_candidate'],'brier_rank':x['brier_rank'],'brier_previous':x['brier_previous'],'brier_target_history':x['brier_target_history'],'candidate_issued_rate':x['candidate_issued_rate']})
r=pd.DataFrame(rows); r.to_csv(d/'IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_STABILITY.csv',index=False); out={'run_count':len(files),'seeds':[int(p.stem.split('_')[-1]) for p in files],'rows':len(r),'ranges':[],'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
for h,g in r.groupby('horizon'):
 out['ranges'].append({'horizon':int(h),'candidate_rate_min':float(g.candidate_rate.min()),'candidate_rate_max':float(g.candidate_rate.max()),'rank_rate_min':float(g.rank_rate.min()),'rank_rate_max':float(g.rank_rate.max()),'candidate_lift_min':float(g.candidate_lift_vs_rank.min()),'candidate_lift_max':float(g.candidate_lift_vs_rank.max()),'brier_candidate_min':float(g.brier_candidate.min()),'brier_candidate_max':float(g.brier_candidate.max()),'brier_rank_min':float(g.brier_rank.min()),'brier_rank_max':float(g.brier_rank.max())})
out['decision']='stable_negative_primary_lift' if all(x['candidate_lift_min']<0 for x in out['ranges']) else 'mixed_or_positive'; out['contract_ref']='experimental_contracts/dual_track_v02/IMF_IMTS_PARTNER_SUBSTITUTION_CONTRACT_V3_1.json'; (d/'IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_STABILITY_SUMMARY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'run_count':out['run_count'],'rows':out['rows'],'decision':out['decision']},ensure_ascii=False,indent=2))
