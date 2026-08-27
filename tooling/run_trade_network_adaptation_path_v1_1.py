#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,os
from collections import Counter,defaultdict
import numpy as np
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); CONTRACT=ROOT/'experimental_contracts/dual_track_v02/TRADE_NETWORK_ADAPTATION_PATH_CONTRACT_V1_1.json'; SEL=ROOT/'experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_SELECTION_REGISTER_V2.csv'; OBS=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVED_RECORDS_2000_2024.csv'; OUT=ROOT/'experiments/dual_track_v02/trade_network_adaptation_path_v1_1'; OUT.mkdir(parents=True,exist_ok=True); SEED=int(os.environ.get('CHAOS_TNAP_SEED','271108')); rng=np.random.default_rng(SEED)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load_inputs():
 s=pd.read_csv(SEL); s=s[s.candidate_rank<=10].copy(); pools={rid:list(g.sort_values('candidate_rank').partner_id.astype(str)) for rid,g in s.groupby('reporter_id') if len(g)==10}; o=pd.read_csv(OBS,usecols=['country','counterpart_country','time_period','obs_value_raw'],low_memory=False); o['year']=pd.to_numeric(o.time_period,errors='coerce'); o['value']=pd.to_numeric(o.obs_value_raw,errors='coerce'); o=o[o.year.between(2000,2024)&o.value.notna()]; o['year']=o.year.astype(int); o['country']=o.country.astype(str); o['counterpart_country']=o.counterpart_country.astype(str); o=o[o.country.isin(pools)].copy(); keys=pd.DataFrame([(rid,p) for rid,ps in pools.items() for p in ps],columns=['country','counterpart_country']); o=o.merge(keys,on=['country','counterpart_country'],how='inner'); dup=o.duplicated(['country','counterpart_country','year']).sum(); return pools,o,dup

def build_states(pools,obs):
 g=defaultdict(dict)
 for (rid,partner,y),z in obs.groupby(['country','counterpart_country','year'],sort=False):
  if partner in pools.get(rid,[]) and float(z.value.iloc[0])>0:g[(rid,int(y))][partner]=float(z.value.iloc[0])
 states=[]
 for rid,cand in pools.items():
  prev1=None; prev2=None
  for y in range(2000,2025):
   vals=g[(rid,y)]; valid=len(vals)>=5; order=sorted(vals,key=lambda p:(-vals[p],p)); top=order[0] if order else None; total=sum(vals.values()) if vals else None; top1=vals[top]/total if valid and total else None; top3=sum(vals[p] for p in order[:3])/total if valid and total else None; low=min([x['observed_total_raw_usd'] for x in [prev1,prev2] if x and x['valid'] and x['observed_total_raw_usd'] is not None],default=None); flow=bool(valid and low is not None and total<=.70*low); conc=bool(valid and prev1 and prev1['valid'] and top1 is not None and prev1['top1_share'] is not None and top1<=prev1['top1_share']-.10); exit=bool(valid and prev1 and prev1['valid'] and top is not None and prev1['top1_identity'] is not None and top!=prev1['top1_identity']); cur={'reporter_id':rid,'year':y,'valid':valid,'observed_count':len(vals),'observed_total_raw_usd':total,'top1_identity':top,'top1_value_raw_usd':vals.get(top),'top1_share':top1,'top3_share':top3,'top1_exit':exit,'flow_stress':flow,'concentration_stress':conc,'high_concentration':bool(top1 is not None and top1>=.70)}; states.append(cur); prev2,prev1=prev1,cur
 return pd.DataFrame(states)

def state_map(df):return {(r.reporter_id,int(r.year)):r._asdict() for r in df.itertuples()}
def event_rows(df):
 m=state_map(df); events=[]
 for rid in sorted(df.reporter_id.unique()):
  last=None
  for t in range(2005,2025):
   a=m.get((rid,t)); p=m.get((rid,t-1)); pp=m.get((rid,t-2));
   if not(a and p and pp and a['valid'] and p['valid'] and pp['valid']):continue
   if not(p['high_concentration'] or a['flow_stress'] or a['concentration_stress'] or a['top1_exit']):continue
   if last is not None and t-last<=2:continue
   if a['top1_exit'] and a['top1_share'] is not None and a['top1_share']>=.40: subtype='stable_replacement'
   elif a['concentration_stress']: subtype='diversification'
   elif a['flow_stress']: subtype='failure_to_adapt'
   else: subtype='fragmentation'
   e={'reporter_id':rid,'event_year':t,'subtype':subtype,'event_top1':a['top1_identity'],'event_top1_share':a['top1_share'],'pre_top1_share':p['top1_share'],'flow_stress':a['flow_stress'],'concentration_stress':a['concentration_stress'],'top1_exit':a['top1_exit']}
   for h in [1,2,3]:
    future=[m.get((rid,t+j)) for j in range(1,h+1)]; allvalid=all(x and x['valid'] for x in future); target=None
    if allvalid:
     same=bool(a['top1_identity'] and all(x['top1_identity']==a['top1_identity'] for x in future))
     lastx=future[-1];
     if a['top1_exit'] and same: target='stable_replacement'
     elif a['top1_share'] is not None and lastx['top1_share'] is not None and p['top1_share'] is not None and lastx['top1_share']<=p['top1_share']-.10 and lastx['top1_share']>.50: target='diversification'
     elif lastx['top1_share'] is not None and lastx['top1_share']<=.50: target='fragmentation'
     else: target='failure_to_adapt'
    e[f'outcome_h{h}']=target
   events.append(e); last=t
 return pd.DataFrame(events)

def family_vec(x,fams):return np.array([1.0 if x==f else 0.0 for f in fams])
def probs(train,h,kind):
 ys=[x[f'outcome_h{h}'] for x in train if x[f'outcome_h{h}']]; fams=['stable_replacement','diversification','fragmentation','failure_to_adapt']; c=Counter(ys); n=len(ys); hist=np.array([c[f]/n for f in fams]) if n else np.ones(4)/4
 if kind=='target_history':return ('prob',hist)
 if kind=='state_persistence':
  by=defaultdict(Counter)
  for x in train:
   if x[f'outcome_h{h}']:by[(x['flow_stress'],x['concentration_stress'],x['top1_exit'])][x[f'outcome_h{h}']]+=1
  return ('conditional',by,hist)
 if kind=='previous_state':
  by=defaultdict(Counter)
  for x in train:
   if x[f'outcome_h{h}']:by[(round(float(x['pre_top1_share'] or 0),1),x['top1_exit'])][x[f'outcome_h{h}']]+=1
  return ('previous',by,hist)

def pred_prob(model,x,fams):
 if model[0]=='prob':return model[1]
 key=(x['flow_stress'],x['concentration_stress'],x['top1_exit']) if model[0]=='conditional' else (round(float(x['pre_top1_share'] or 0),1),x['top1_exit']); c=model[1].get(key); hist=model[2]
 if not c:return hist
 n=sum(c.values()); return np.array([c[f]/n for f in fams])
def eval_split(events,train_end,eval_lo,eval_hi,h):
 events=events.to_dict('records') if hasattr(events,'to_dict') else events
 fams=['stable_replacement','diversification','fragmentation','failure_to_adapt']; train=[x for x in events if x['event_year']<=train_end and x[f'outcome_h{h}']]; ev=[x for x in events if eval_lo<=x['event_year']<=eval_hi and x[f'outcome_h{h}']]; models={k:probs(train,h,k) for k in ['target_history','state_persistence','previous_state']}; out=[]
 for x in ev:
  y=family_vec(x[f'outcome_h{h}'],fams); cp=family_vec(x['subtype'],fams); # subtype uses same family labels
  row={'event_year':x['event_year'],'reporter_id':x['reporter_id'],'horizon':h,'actual_family':x[f'outcome_h{h}'],'candidate_predicted_family':x['subtype']}
  for k,model in models.items():
   p=pred_prob(model,x,fams); row[f'{k}_brier']=float(np.mean((p-y)**2)); row[f'{k}_predicted_family']=fams[int(np.argmax(p))]
  row['candidate_brier']=float(np.mean((cp-y)**2)); row['candidate_correct']=int(x['subtype']==x[f'outcome_h{h}']); out.append(row)
 def mean(k):return float(np.mean([x[k] for x in out])) if out else None
 return {'train_events':len(train),'eval_events':len(ev),'reporters':len(set(x['reporter_id'] for x in ev)),'candidate_brier':mean('candidate_brier'),'target_history_brier':mean('target_history_brier'),'state_persistence_brier':mean('state_persistence_brier'),'previous_state_brier':mean('previous_state_brier'),'candidate_accuracy':float(np.mean([x['candidate_correct'] for x in out])) if out else None,'rows':out}

def random_block_df(df,rng):
 out=[]
 for rid,g in df.groupby('reporter_id'):
  g=g.sort_values('year'); rec=g.to_dict('records'); blocks=[]; i=0
  while i<len(rec): L=int(rng.choice([2,3])); blocks.append(rec[i:i+L]); i+=L
  rng.shuffle(blocks); flat=[z for b in blocks for z in b]; years=[z['year'] for z in rec];
  for y,z in zip(years,flat): q=dict(z); q['year']=y; out.append(q)
 return pd.DataFrame(out)
def random_rank_df(df,rng):
 # preserve each reporter-year state record multiset while reassigning ranking-related fields
 out=df.copy(); out['top1_identity']=out.groupby('reporter_id')['top1_identity'].transform(lambda x: x.sample(frac=1,random_state=int(rng.integers(1,2**31-1))).to_numpy()); return out

def permute_blocks_obs(pools,obs,rng):
 out=[z.copy() for _,z in obs[obs.year<=2004].groupby(obs[obs.year<=2004].index)] if False else []
 for rid,g in obs.groupby('country',sort=False):
  base=g[g.year<=2004].copy(); post=g[g.year>=2005].copy(); years=sorted(post.year.unique()); blocks=[]; i=0
  while i<len(years): L=int(rng.choice([2,3])); blocks.append(years[i:i+L]); i+=L
  src=[y for b in blocks for y in b]; rng.shuffle(blocks); src=[y for b in blocks for y in b]
  targets=years; parts=[base]
  for target,source in zip(targets,src):
   z=post[post.year==source].copy(); z['year']=target; parts.append(z)
  out.append(pd.concat(parts,ignore_index=True))
 return pd.concat(out,ignore_index=True) if out else obs.copy()
def permute_rank_obs(pools,obs,rng):
 parts=[]
 for (rid,y),g in obs.groupby(['country','year'],sort=False):
  z=g.copy(); cand=pools.get(rid,[]); z=z[z.counterpart_country.isin(cand)]
  if y>=2005 and len(z)>1:
   labels=z.counterpart_country.to_numpy().copy(); rng.shuffle(labels); z['counterpart_country']=labels
  parts.append(z)
 return pd.concat(parts,ignore_index=True) if parts else obs.copy()
def forced_placebo_events(states,original,rng):
 m=state_map(states); rows=[]
 for rid,g in original.groupby('reporter_id'):
  actual=set(g.event_year); choices=[y for y in range(2007,2023) if y not in actual and m.get((rid,y)) and m.get((rid,y-1)) and m.get((rid,y-2)) and m[(rid,y)]['valid'] and m[(rid,y-1)]['valid'] and m[(rid,y-2)]['valid']]
  picks=rng.choice(choices,size=len(g),replace=len(choices)<len(g)) if choices else []
  for t in picks:
   a=m[(rid,int(t))]; p=m[(rid,int(t-1))];
   if a['top1_exit'] and a['top1_share'] is not None and a['top1_share']>=.40: subtype='stable_replacement'
   elif a['concentration_stress']: subtype='diversification'
   elif a['flow_stress']: subtype='failure_to_adapt'
   else: subtype='fragmentation'
   e={'reporter_id':rid,'event_year':int(t),'subtype':subtype,'event_top1':a['top1_identity'],'event_top1_share':a['top1_share'],'pre_top1_share':p['top1_share'],'flow_stress':a['flow_stress'],'concentration_stress':a['concentration_stress'],'top1_exit':a['top1_exit']}
   for h in [1,2,3]:
    fut=[m.get((rid,int(t+j))) for j in range(1,h+1)]; e[f'outcome_h{h}']=None if not all(x and x['valid'] for x in fut) else ('stable_replacement' if a['top1_exit'] and all(x['top1_identity']==a['top1_identity'] for x in fut) else ('diversification' if fut[-1]['top1_share'] is not None and p['top1_share'] is not None and fut[-1]['top1_share']<=p['top1_share']-.10 and fut[-1]['top1_share']>.50 else ('fragmentation' if fut[-1]['top1_share']<=.50 else 'failure_to_adapt')))
   rows.append(e)
 return pd.DataFrame(rows)
def null_adv(pools,obs,kind,rng,h,original_events):
 if kind=='block': zobs=permute_blocks_obs(pools,obs,rng); ev=event_rows(build_states(pools,zobs))
 elif kind=='rank': zobs=permute_rank_obs(pools,obs,rng); ev=event_rows(build_states(pools,zobs))
 else: ev=forced_placebo_events(build_states(pools,obs),original_events,rng)
 if ev.empty:return np.nan
 r=eval_split(ev,2018,2019,2021,h); vals=[r['candidate_brier'],r['state_persistence_brier'],r['previous_state_brier'],r['target_history_brier']]; return float(vals[0]-min(vals[1:])) if all(v is not None for v in vals) else np.nan
def raw_map(pools,obs):
 raw=defaultdict(list)
 for r in obs.itertuples(): raw[(r.country,int(r.year))].append((r.counterpart_country,float(r.value)))
 return raw
def build_states_raw(pools,raw):
 states=[]
 for rid,cand in pools.items():
  prev1=None; prev2=None
  for y in range(2000,2025):
   pairs=raw.get((rid,y),[]); vals=dict(pairs); valid=len(vals)>=5; order=sorted(vals,key=lambda p:(-vals[p],p)); top=order[0] if order else None; total=sum(vals.values()) if vals else None; top1=vals[top]/total if valid and total else None; top3=sum(vals[p] for p in order[:3])/total if valid and total else None; low=min([x['observed_total_raw_usd'] for x in [prev1,prev2] if x and x['valid'] and x['observed_total_raw_usd'] is not None],default=None); flow=bool(valid and low is not None and total<=.70*low); conc=bool(valid and prev1 and prev1['valid'] and top1 is not None and prev1['top1_share'] is not None and top1<=prev1['top1_share']-.10); exit=bool(valid and prev1 and prev1['valid'] and top is not None and prev1['top1_identity'] is not None and top!=prev1['top1_identity']); cur={'reporter_id':rid,'year':y,'valid':valid,'observed_count':len(vals),'observed_total_raw_usd':total,'top1_identity':top,'top1_value_raw_usd':vals.get(top),'top1_share':top1,'top3_share':top3,'top1_exit':exit,'flow_stress':flow,'concentration_stress':conc,'high_concentration':bool(top1 is not None and top1>=.70)}; states.append(cur); prev2,prev1=prev1,cur
 return pd.DataFrame(states)
def permute_blocks_raw(pools,raw,rng):
 out={}
 for rid,cand in pools.items():
  years=list(range(2000,2025)); post=list(range(2005,2025)); blocks=[]; i=0
  while i<len(post): L=int(rng.choice([2,3])); blocks.append(post[i:i+L]); i+=L
  rng.shuffle(blocks); src=[y for b in blocks for y in b]
  for y in range(2000,2005):out[(rid,y)]=list(raw.get((rid,y),[]))
  for target,source in zip(post,src):out[(rid,target)]=list(raw.get((rid,source),[]))
 return out
def permute_rank_raw(pools,raw,rng):
 out={}
 for key,pairs in raw.items():
  rid,y=key; labels=[x[0] for x in pairs]; values=[x[1] for x in pairs]
  if y>=2005 and len(labels)>1:rng.shuffle(labels)
  out[key]=list(zip(labels,values))
 return out
def null_adv_fast(pools,raw,orig_states,kind,rng,h,original_events):
 if kind=='block': st=build_states_raw(pools,permute_blocks_raw(pools,raw,rng))
 elif kind=='rank': st=build_states_raw(pools,permute_rank_raw(pools,raw,rng))
 else: st=orig_states
 ev=forced_placebo_events(st,original_events,rng) if kind=='time' else event_rows(st)
 if ev.empty:return np.nan
 r=eval_split(ev,2018,2019,2021,h); vals=[r['candidate_brier'],r['state_persistence_brier'],r['previous_state_brier'],r['target_history_brier']]; return float(vals[0]-min(vals[1:])) if all(v is not None for v in vals) else np.nan
def main():
 contract=json.loads(CONTRACT.read_text()); pools,obs,dup=load_inputs(); raw=raw_map(pools,obs); states=build_states_raw(pools,raw); events=event_rows(states); states.to_csv(OUT/'TRADE_NETWORK_ADAPTATION_STATE_PANEL_V1.csv',index=False); events.to_csv(OUT/'TRADE_NETWORK_ADAPTATION_EVENTS_V1.csv',index=False)
 rolling=[]
 for o in contract['evaluation']['rolling_origins']:
  for h in [1,2,3]:
   r=eval_split(events,o,o+1,min(o+2,2024-h),h); r.update({'origin':o,'horizon':h}); rolling.append({k:v for k,v in r.items() if k!='rows'})
 final={str(h):eval_split(events,2018,2019,2021,h) for h in [1,2,3]}
 nulls=[]
 observed_adv=final['2']['candidate_brier']-min(final['2']['state_persistence_brier'],final['2']['previous_state_brier'],final['2']['target_history_brier']) if final['2']['candidate_brier'] is not None and final['2']['state_persistence_brier'] is not None and final['2']['previous_state_brier'] is not None and final['2']['target_history_brier'] is not None else None
 for kind,n in [('block',2000),('rank',2000),('time',2000)]:
  for h in [2]:
   vals=np.array([null_adv_fast(pools,raw,states,kind,rng,h,events) for _ in range(n)],float); vals=vals[~np.isnan(vals)]; nulls.append({'variant':kind,'horizon':h,'replicates':n,'null_mean':float(np.mean(vals)) if len(vals) else None,'null_sd':float(np.std(vals,ddof=1)) if len(vals)>1 else None,'observed_advantage':observed_adv,'p_lower_tail':float((np.sum(vals<=observed_adv)+1)/(len(vals)+1)) if len(vals) and observed_adv is not None else None,'unique_statistics':int(len(np.unique(np.round(vals,12)))) if len(vals) else 0,'status':'non_degenerate' if len(np.unique(np.round(vals,12)))>1 else 'degenerate'})
 checks={'final_events_h2':final['2']['eval_events'],'coverage':final['2']['eval_events']>=30,'candidate_beats_rank_h2':final['2']['candidate_brier'] is not None and final['2']['candidate_brier']<=final['2']['state_persistence_brier']-.05,'final_block_available':final['2']['eval_events']>=30,'nulls_non_degenerate':all(x['status']=='non_degenerate' for x in nulls),'rolling_rows':len(rolling)}; status='supported_predictive' if all(checks.values()) else ('not_testable' if not checks['final_block_available'] else 'rejected')
 pd.DataFrame(rolling).to_csv(OUT/'TRADE_NETWORK_ADAPTATION_ROLLING_METRICS_V1.csv',index=False); (OUT/'TRADE_NETWORK_ADAPTATION_NULL_SUMMARIES_V1.json').write_text(json.dumps(nulls,ensure_ascii=False,indent=2)+'\n')
 summary={'contract_id':contract['contract_id'],'contract_sha256':sha(CONTRACT),'selection_sha256':sha(SEL),'observation_sha256':sha(OBS),'seed':SEED,'reporters':len(pools),'duplicate_input_keys':int(dup),'state_rows':len(states),'event_rows':len(events),'rolling_metrics':rolling,'final_locked_block':final,'nulls':nulls,'observed_advantage_h2':observed_adv,'admission_checks':checks,'predictive_evidence_status':status,'causal_validation_status':'not_run','runtime_status':'not_eligible','causal_claim':False,'notes':['No raw modification or missing-as-zero.','Partner rows are not treated as independent outcomes.','The current implementation records null controls and baseline comparisons; any non-conforming null implementation remains a reason not to promote.']}
 (OUT/'TRADE_NETWORK_ADAPTATION_PATH_SUMMARY_V1.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); man={'run_id':'TRADE_NETWORK_ADAPTATION_PATH_V1_1_RUN','contract_ref':str(CONTRACT.relative_to(ROOT)),'contract_sha256':summary['contract_sha256'],'code_ref':'tooling/run_trade_network_adaptation_path_v1_1.py','code_sha256':sha(ROOT/'tooling/run_trade_network_adaptation_path_v1_1.py'),'seed':SEED,'inputs':[str(SEL.relative_to(ROOT)),str(OBS.relative_to(ROOT))],'status':status,'research_only':True,'causal_claim':False,'runtime_eligible':False}; (OUT/'TRADE_NETWORK_ADAPTATION_PATH_RUN_MANIFEST_V1.json').write_text(json.dumps(man,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'status':status,'reporters':len(pools),'states':len(states),'events':len(events),'final_h2':final['2'],'checks':checks},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
