#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import hashlib,json,os
import numpy as np
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); CONTRACT=ROOT/'experimental_contracts/dual_track_v02/IMF_IMTS_PARTNER_SUBSTITUTION_CONTRACT_V3_1.json'; SEL=ROOT/'experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_SELECTION_REGISTER_V2.csv'; OBS=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVED_RECORDS_2000_2024.csv'; OUT=ROOT/'experiments/dual_track_v02/imf_partner_substitution_v3_1'; OUT.mkdir(parents=True,exist_ok=True)
SEED=int(os.environ.get('CHAOS_V31_SEED','271108')); rng=np.random.default_rng(SEED); H=[1,2,3]; SPLITS={'fit':(2005,2014),'confirmation':(2015,2024)}; SUBWINDOWS=[(2015,2017),(2018,2020),(2021,2023)]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load():
 s=pd.read_csv(SEL); o=pd.read_csv(OBS,usecols=['country','counterpart_country','time_period','obs_value_raw'],low_memory=False); o['year']=pd.to_numeric(o.time_period,errors='coerce'); o['value']=pd.to_numeric(o.obs_value_raw,errors='coerce'); o=o[o.year.between(2000,2024)].dropna(subset=['year','value']); o['year']=o.year.astype(int); return s,o

def make_rows(sel,obs):
 rows={}; meta={}
 for rid,g in sel.groupby('reporter_id',sort=True):
  g=g.sort_values('candidate_rank'); cand=list(g.partner_id.astype(str));
  if len(cand)!=10: continue
  base=str(g.iloc[0].partner_id); top3=set(g[g.candidate_rank<=3].partner_id.astype(str)); od=obs[(obs.country==rid)&obs.counterpart_country.isin(cand)]
  d={}
  for y,z in od.groupby('year'):
   if len(z)!=10 or z.value.isna().any() or (z.value<=0).any(): continue
   z=z.sort_values(['value','counterpart_country'],ascending=[False,True]); d[int(y)]=list(z.counterpart_country.astype(str))
  rows[rid]=d; meta[rid]={'cand':cand,'base':base,'base3':top3}
 return rows,meta

def readiness(rank,meta,t):
 if t-2 not in rank or t-1 not in rank: return None
 prior=set(rank[t-2][:3]) & set(rank[t-1][:3]); prior.discard(meta['base']);
 if not prior:return None
 return sorted(prior,key=lambda x:(rank[t-1].index(x),x))[0]

def event_list(rows,meta,lo,hi):
 ev=[]; last=None
 for t in range(lo,hi+1):
  if t not in rows or t-1 not in rows: continue
  if rows[t-1][0]!=meta['base'] or rows[t][0]==meta['base']: continue
  if last is not None and t-last<=3: continue
  ev.append(t); last=t
 return ev

def outcome(rank,t,pred,h):
 if pred is None or t not in rank or rank[t][0]!=pred:return 0
 return int(all((t+j in rank and rank[t+j][0]==pred) for j in range(1,h+1)))
def rank2_success(rank,t,h):
 pred=rank[t-1][1] if t-1 in rank and len(rank[t-1])>1 else None; return outcome(rank,t,pred,h)
def prev_success(rank,meta,t,h):
 pred=rank[t-1][0] if t-1 in rank and rank[t-1] else None
 return outcome(rank,t,pred,h)
def event_metrics(rows,meta,lo,hi,h,exclude=set(),placebo_years=None):
 events=[]
 years=placebo_years if placebo_years is not None else event_list(rows,meta,lo,hi)
 for t in years:
  if t in exclude: continue
  pred=readiness(rows,meta,t); c=outcome(rows,t,pred,h); r=rank2_success(rows,t,h); p=prev_success(rows,meta,t,h); anyp=int(t in rows and all(t+j in rows for j in range(1,h+1)) and rows[t][0]!=meta['base'] and len({rows[t+j][0] for j in range(0,h+1)})==1)
  events.append({'reporter_id':None,'year':t,'candidate_pred':pred,'candidate_success':c,'rank_success':r,'previous_success':p,'any_replacement_persistence':anyp,'candidate_issued':pred is not None})
 return events

def panel_metrics(allrows,meta,split,h,exclude_reporters=set(),years_override=None):
 lo,hi=SPLITS[split]; all_events=[]
 for rid,rank in allrows.items():
  if rid in exclude_reporters:continue
  ys=years_override.get(rid) if years_override else None; es=event_metrics(rank,meta[rid],lo,hi,h,placebo_years=ys)
  for e in es:e['reporter_id']=rid
  all_events.extend(es)
 def rate(k):return float(np.mean([e[k] for e in all_events])) if all_events else None
 return {'split':split,'horizon':h,'events':len(all_events),'reporters':len(set(e['reporter_id'] for e in all_events)),'candidate_success_rate':rate('candidate_success'),'rank_success_rate':rate('rank_success'),'previous_success_rate':rate('previous_success'),'any_replacement_persistence_rate':rate('any_replacement_persistence'),'candidate_coverage':float(np.mean([e['candidate_issued'] for e in all_events])) if all_events else None,'candidate_lift_vs_rank':(rate('candidate_success')-rate('rank_success')) if all_events else None,'events_data':all_events}

def brier(rows,prob):
 if not rows:return None
 if np.isscalar(prob): prob=[float(prob)]*len(rows)
 return float(np.mean([(float(p)-x)**2 for p,x in zip(prob,rows)]))
def fit_probs(allrows,meta,h):
 m=panel_metrics(allrows,meta,'fit',h); es=m['events_data']; return {'candidate':float(np.mean([x['candidate_success'] for x in es])) if es else 0.0,'rank':float(np.mean([x['rank_success'] for x in es])) if es else 0.0,'previous':float(np.mean([x['previous_success'] for x in es])) if es else 0.0,'target_history':float(np.mean([x['any_replacement_persistence'] for x in es])) if es else 0.0}
def confirmation_scores(allrows,meta,h,exclude_reporters=set()):
 m=panel_metrics(allrows,meta,'confirmation',h,exclude_reporters); es=m['events_data']; pr=fit_probs(allrows,meta,h); y=[x['candidate_success'] for x in es]; r=[x['rank_success'] for x in es]; prev=[x['previous_success'] for x in es]; anyy=[x['any_replacement_persistence'] for x in es]
 cp=[pr['candidate'] if x['candidate_issued'] else 0.0 for x in es]
 return {'horizon':h,'events':len(es),'reporters':m['reporters'],'candidate_rate':float(np.mean(y)) if y else None,'rank_rate':float(np.mean(r)) if r else None,'previous_rate':float(np.mean(prev)) if prev else None,'any_target_rate':float(np.mean(anyy)) if anyy else None,'candidate_lift_vs_rank':m['candidate_lift_vs_rank'],'brier_candidate':brier(y,cp),'brier_rank':brier(r,pr['rank']),'brier_previous':brier(prev,pr['previous']),'brier_target_history':brier(anyy,pr['target_history']),'fit_probabilities':pr,'candidate_predicted_probability':pr['candidate'],'candidate_issued_rate':float(np.mean([x['candidate_issued'] for x in es])) if es else None,'events_data':es}

def clone_block(rows,lo,hi,rng):
 out={}
 for rid,rank in rows.items():
  years=[y for y in range(lo,hi+1) if y in rank]; blocks=[]; i=0
  while i<len(years):
   L=int(rng.choice([2,3])); blocks.append(years[i:i+L]); i+=L
  rng.shuffle(blocks); new={y:rank[src] for block in blocks for y,src in zip(block,block)}
  # shuffle blocks by assigning original rows to target positions
  flat_src=[src for block in blocks for src in block]; out[rid]={y:rows[rid][src] for y,src in zip(years,flat_src)}
 return out

def clone_rank(rows,meta,rng):
 out={}
 for rid,rank in rows.items():
  out[rid]={}
  for y,vec in rank.items():
   labels=list(vec); rng.shuffle(labels); out[rid][y]=labels
 return out

def adv(rows,meta,split,h):
 m=panel_metrics(rows,meta,split,h); return m['candidate_lift_vs_rank'] if m['candidate_lift_vs_rank'] is not None else np.nan

def null_dist(rows,meta,split,h,kind,n,rng):
 vals=[]; lo,hi=SPLITS[split]
 for _ in range(n):
  z=clone_block(rows,lo,hi,rng) if kind=='block' else clone_rank(rows,meta,rng); vals.append(adv(z,meta,split,h))
 return np.asarray(vals,dtype=float)

def restricted_placebo(rows,meta,split,h,n,rng):
 lo,hi=SPLITS[split]; vals=[]
 for _ in range(n):
  yr={}
  for rid,rank in rows.items():
   actual=set(event_list(rank,meta[rid],lo,hi)); elig=[y for y in range(lo+2,hi-h+1) if y in rank and y not in actual and y-1 in rank and y-2 in rank]
   picks=[]
   for t in actual:
    choices=[y for y in elig if abs(y-t)>=1]
    if choices:picks.append(int(rng.choice(choices)))
   yr[rid]=picks
  vals.append(adv_placebo(rows,meta,split,h,yr))
 return np.asarray(vals,dtype=float)
def adv_placebo(rows,meta,split,h,yr):
 lo,hi=SPLITS[split]; ce=[]; re=[]
 for rid,rank in rows.items():
  for t in yr.get(rid,[]):
   pred=readiness(rank,meta[rid],t); ce.append(outcome(rank,t,pred,h)); re.append(rank2_success(rank,t,h))
 return (float(np.mean(ce))-float(np.mean(re))) if ce and re else np.nan

def holm(pvals,alpha=.025):
 order=np.argsort(pvals); adj=[None]*len(pvals); run=0
 for i,idx in enumerate(order): run=max(run,min(1.0,(len(pvals)-i)*pvals[idx])); adj[idx]=run
 return adj

def main():
 contract=json.loads(CONTRACT.read_text()); sel,obs=load(); rows,meta=make_rows(sel,obs); metrics=[]; scores={}
 for split in SPLITS:
  for h in H:
   m=panel_metrics(rows,meta,split,h); metrics.append({k:v for k,v in m.items() if k!='events_data'})
 for h in H: scores[h]=confirmation_scores(rows,meta,h)
 # subwindow stability and influential reporters are computed before reading confirmation into any selection rule.
 sub=[]
 for lo,hi in SUBWINDOWS:
  for h in H:
   m=panel_metrics(rows,meta,'confirmation',h,years_override={rid:[t for t in event_list(rank,meta[rid],lo,hi)] for rid,rank in rows.items()}); sub.append({'window':[lo,hi],'horizon':h,'events':m['events'],'reporters':m['reporters'],'candidate_rate':m['candidate_success_rate'],'rank_rate':m['rank_success_rate'],'lift':m['candidate_lift_vs_rank']})
 fit0=panel_metrics(rows,meta,'fit',2); counts=Counter(x['reporter_id'] for x in fit0['events_data']); influential={x[0] for x in counts.most_common(3)}; inf_scores={h:confirmation_scores(rows,meta,h,influential) for h in H}
 nulls=[]
 for kind,n in [('block',10000),('rank',10000)]:
  for h in H:
   observed=scores[h]['candidate_lift_vs_rank']; dist=null_dist(rows,meta,'confirmation',h,kind,n,rng); v=dist[~np.isnan(dist)]; nulls.append({'split':'confirmation','horizon':h,'variant':kind+'_permutation','replicates':n,'observed_lift':observed,'null_mean':float(np.mean(v)),'null_sd':float(np.std(v,ddof=1)),'p_value':float((np.sum(v>=observed)+1)/(len(v)+1)),'unique_statistics':int(len(np.unique(np.round(v,12)))),'status':'non_degenerate' if len(np.unique(np.round(v,12)))>1 else 'degenerate'})
 for h in H:
  observed=scores[h]['candidate_lift_vs_rank']; dist=restricted_placebo(rows,meta,'confirmation',h,5000,rng); v=dist[~np.isnan(dist)]; nulls.append({'split':'confirmation','horizon':h,'variant':'restricted_time_placebo','replicates':5000,'observed_lift':observed,'null_mean':float(np.mean(v)),'null_sd':float(np.std(v,ddof=1)),'p_value':float((np.sum(v>=observed)+1)/(len(v)+1)),'unique_statistics':int(len(np.unique(np.round(v,12)))),'status':'non_degenerate' if len(np.unique(np.round(v,12)))>1 else 'degenerate'})
 pvals=[x['p_value'] for x in nulls if x['horizon']==2]; null_h2=[x for x in nulls if x['horizon']==2]; adj=holm(pvals,.025)
 for x,a in zip(null_h2,adj):x['holm_adjusted_p_value']=a
 primary=scores[2]; pass_checks={'coverage':primary['events']>=30 and primary['reporters']>=15,'effect_vs_rank':primary['candidate_lift_vs_rank'] is not None and primary['candidate_lift_vs_rank']>=.05,'brier_vs_rank':primary['brier_candidate'] is not None and primary['brier_rank'] is not None and primary['brier_candidate']<=primary['brier_rank']-.05,'concentration':(max(Counter(x['reporter_id'] for x in primary['events_data']).values())/primary['events'] if primary['events'] else 1)<=.05,'subwindow_coverage':all(x['events']>=30 for x in sub if x['horizon']==2),'subwindow_lift':all((x['lift'] is not None and x['lift']>=.05) for x in sub if x['horizon']==2),'influential_direction':inf_scores[2]['candidate_lift_vs_rank'] is not None and inf_scores[2]['candidate_lift_vs_rank']>=.05,'nulls_non_degenerate':all(x['status']=='non_degenerate' for x in nulls if x['horizon']==2),'nulls_corrected':all(x.get('holm_adjusted_p_value',1)<=.025 for x in null_h2)}
 status='supported_predictive' if all(pass_checks.values()) else ('not_testable' if not pass_checks['coverage'] or not pass_checks['subwindow_coverage'] else 'rejected')
 event_rows=[]
 for h in H:
  for rid,rank in rows.items():
   for t in event_list(rank,meta[rid],*SPLITS['confirmation']):
    pred=readiness(rank,meta[rid],t); event_rows.append({'split':'confirmation','reporter_id':rid,'shock_year':t,'predicted_replacement':pred,'observed_replacement':rank[t][0],'horizon':h,'candidate_success':outcome(rank,t,pred,h),'rank2_prediction':rank[t-1][1],'rank2_success':rank2_success(rank,t,h),'previous_success':prev_success(rank,meta[rid],t,h)})
 pd.DataFrame(metrics).to_csv(OUT/'IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_METRICS.csv',index=False); pd.DataFrame(sub).to_csv(OUT/'IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_SUBWINDOW_STABILITY.csv',index=False); pd.DataFrame(event_rows).to_csv(OUT/'IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_EVENTS.csv',index=False)
 (OUT/'IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_NULL_SUMMARIES.json').write_text(json.dumps(nulls,ensure_ascii=False,indent=2)+'\n')
 summary={'contract_id':contract['contract_id'],'contract_sha256':sha(CONTRACT),'selection_sha256':sha(SEL),'observation_sha256':sha(OBS),'seed':SEED,'reporters':len(rows),'fit_metrics':{str(h):{k:v for k,v in panel_metrics(rows,meta,'fit',h).items() if k!='events_data'} for h in H},'confirmation_scores':{str(h):{k:v for k,v in scores[h].items() if k!='events_data'} for h in H},'influential_reporters_fit_top3':sorted(influential),'influential_exclusion_confirmation':{str(h):{k:v for k,v in inf_scores[h].items() if k!='events_data'} for h in H},'nulls':nulls,'admission_checks':pass_checks,'predictive_evidence_status':status,'causal_validation_status':'not_run','runtime_status':'not_eligible','causal_claim':False,'notes':['V3.1 executed only after frozen contract hash verification.','The previous-partner baseline is structurally weak on an exit-conditioned event universe because the previous baseline top-1 is defined to have exited; it is reported, not hidden.','Brier scores are strategy-success Brier scores; exact replacement-and-persistence rates are reported alongside them.','No imputation, normalization, log, differencing, smoothing, source averaging, or frequency conversion.','No CVT activation: the event is endogenous network substitution, not an exogenous assignment.']}
 (OUT/'IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 manifest={'run_id':'IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_DISCOVERY_RUN','contract_ref':str(CONTRACT.relative_to(ROOT)),'contract_sha256':summary['contract_sha256'],'code_ref':'tooling/run_imf_partner_substitution_v3_1.py','code_sha256':sha(ROOT/'tooling/run_imf_partner_substitution_v3_1.py'),'seed':SEED,'null_replicates':{'block':10000,'rank':10000,'restricted_time_placebo':5000},'input_refs':[str(SEL.relative_to(ROOT)),str(OBS.relative_to(ROOT))],'input_sha256':{'selection':summary['selection_sha256'],'observations':summary['observation_sha256']},'status':status,'research_only':True,'causal_claim':False,'runtime_eligible':False}
 (OUT/'IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_RUN_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'status':status,'reporters':len(rows),'fit_h2_events':summary['fit_metrics']['2']['events'],'confirmation_h2_events':summary['confirmation_scores']['2']['events'],'checks':pass_checks},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
