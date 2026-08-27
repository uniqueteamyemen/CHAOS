#!/usr/bin/env python3
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,os
import numpy as np
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS')
CONTRACT=ROOT/'experimental_contracts/dual_track_v02/TRADE_REGIME_TRANSITION_DISCOVERY_CONTRACT_V1.json'
SEL=ROOT/'experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_SELECTION_REGISTER_V2.csv'
OBS=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVED_RECORDS_2000_2024.csv'
OUT=ROOT/'experiments/dual_track_v02/trade_regime_transition_discovery_v1'; OUT.mkdir(parents=True,exist_ok=True)
SEED=int(os.environ.get('CHAOS_TRD_SEED','271108')); rng=np.random.default_rng(SEED)
FAMS=['stable_replacement','diversification','fragmentation','failure_to_adapt']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load_inputs():
 s=pd.read_csv(SEL); s=s[s.candidate_rank<=10].copy(); pools={rid:list(g.sort_values('candidate_rank').partner_id.astype(str)) for rid,g in s.groupby('reporter_id') if len(g)==10}
 o=pd.read_csv(OBS,usecols=['country','counterpart_country','time_period','obs_value_raw'],low_memory=False); o['year']=pd.to_numeric(o.time_period,errors='coerce'); o['value']=pd.to_numeric(o.obs_value_raw,errors='coerce'); o=o[o.year.between(2000,2024)&o.value.notna()]; o['year']=o.year.astype(int); o['country']=o.country.astype(str); o['counterpart_country']=o.counterpart_country.astype(str); o=o[o.country.isin(pools)].copy(); keys=pd.DataFrame([(rid,p) for rid,ps in pools.items() for p in ps],columns=['country','counterpart_country']); o=o.merge(keys,on=['country','counterpart_country'],how='inner'); return pools,o,int(o.duplicated(['country','counterpart_country','year']).sum())
def raw_map(obs):
 z=defaultdict(list)
 for r in obs.itertuples(): z[(r.country,int(r.year))].append((r.counterpart_country,float(r.value)))
 return z
def build_states(pools,raw):
 rows=[]
 for rid in pools:
  p1=p2=None
  for y in range(2000,2025):
   pairs=raw.get((rid,y),[]); vals=dict(pairs); n=len(vals); valid=n>=5; order=sorted(vals,key=lambda p:(-vals[p],p)); top=order[0] if order else None; total=sum(vals.values()) if vals else None; s1=vals[top]/total if valid and total else None; s3=sum(vals[p] for p in order[:3])/total if valid and total else None; low=min([q['total'] for q in (p1,p2) if q and q['valid'] and q['total'] is not None],default=None); flow=bool(valid and low is not None and total<=.70*low); conc=bool(valid and p1 and p1['valid'] and s1 is not None and p1['top1_share'] is not None and s1<=p1['top1_share']-.10); ex=bool(valid and p1 and p1['valid'] and top is not None and p1['top'] is not None and top!=p1['top']); turn=ex; disp=(1-s3) if s3 is not None else None; cur={'reporter_id':rid,'year':y,'valid':valid,'observed_count':n,'total':total,'top':top,'top1_share':s1,'top3_share':s3,'high_concentration':bool(s1 is not None and s1>=.70),'flow_stress':flow,'concentration_stress':conc,'top1_exit':ex,'partner_turnover':turn,'share_dispersion':disp}; rows.append(cur); p2,p1=p1,cur
 return pd.DataFrame(rows)
def sig(r):
 if r is None or not bool(r['valid']): return 'invalid'
 if r['high_concentration']: base='high'
 elif r['top1_share'] is not None and r['top1_share']<.50: base='low'
 else: base='mid'
 flags=''.join(['F' if r['flow_stress'] else '', 'C' if r['concentration_stress'] else '', 'E' if r['top1_exit'] else '']) or 'N'
 return base+'_'+flags
def fit_regimes(states,train_end):
 ss=states[states.year<=train_end]; c=Counter(sig(r) for r in ss.to_dict('records')); keep=[k for k,_ in c.most_common(7)]; mp={k:i+1 for i,k in enumerate(keep)}; mp['invalid']=0; return mp
def attach_regimes(states,mp):
 z=states.copy(); z['regime']=z.apply(lambda r:mp.get(sig(r),0),axis=1); return z
def state_lookup(states): return {(r.reporter_id,int(r.year)):r._asdict() for r in states.itertuples()}
def outcome_for(a,p,fut):
 if not all(x and x['valid'] for x in fut): return None
 last=fut[-1]; same=bool(a['top'] and all(x['top']==a['top'] for x in fut));
 if a['top1_exit'] and same: return 'stable_replacement'
 if a['top1_share'] is not None and p['top1_share'] is not None and last['top1_share'] is not None and last['top1_share']<=p['top1_share']-.10 and last['top1_share']>.50: return 'diversification'
 if last['top1_share'] is not None and last['top1_share']<=.50: return 'fragmentation'
 return 'failure_to_adapt'
def event_at(rid,t,m):
 a=m.get((rid,t)); p=m.get((rid,t-1)); pp=m.get((rid,t-2));
 if not(a and p and pp and a['valid'] and p['valid'] and pp['valid']): return None
 if not(p['high_concentration'] or a['flow_stress'] or a['concentration_stress'] or a['top1_exit'] or a['partner_turnover'] or (a['share_dispersion'] is not None and p['share_dispersion'] is not None and a['share_dispersion']-p['share_dispersion']>=.10)): return None
 e={'reporter_id':rid,'event_year':int(t),'subtype':('stable_replacement' if a['top1_exit'] and a['top1_share'] is not None and a['top1_share']>=.40 else ('diversification' if a['concentration_stress'] else ('flow_stress' if a['flow_stress'] else 'network_turnover'))),'regime_t2':pp.get('regime',0),'regime_t1':p.get('regime',0),'regime_t':a.get('regime',0),'pre_top1_share':p['top1_share']}
 for h in [1,2,3]: e[f'outcome_h{h}']=outcome_for(a,p,[m.get((rid,t+j)) for j in range(1,h+1)])
 return e
def make_events(states):
 m=state_lookup(states); out=[]
 for rid in sorted(states.reporter_id.unique()):
  last=None
  for t in range(2005,2025):
   e=event_at(rid,t,m)
   if e is None or (last is not None and t-last<=2): continue
   out.append(e); last=t
 return pd.DataFrame(out)
def onehot(events,regime_count=8):
 idx=[]
 if hasattr(events,'itertuples'):
  for r in events.itertuples(): idx.append(int(r.regime_t2)*64+int(r.regime_t1)*8+int(r.regime_t))
 else:
  for r in events: idx.append(int(r['regime_t2'])*64+int(r['regime_t1'])*8+int(r['regime_t']))
 X=np.zeros((len(idx),regime_count**3+1)); X[:,0]=1
 for i,j in enumerate(idx):
  if 0<=j<regime_count**3: X[i,j+1]=1
 return X
def softmax(z): z=z-z.max(axis=1,keepdims=True); e=np.exp(z); return e/e.sum(axis=1,keepdims=True)
def train_logit(X,y,alpha):
 W=np.zeros((X.shape[1],len(FAMS))); Y=np.zeros((len(y),len(FAMS)))
 for i,v in enumerate(y): Y[i,FAMS.index(v)]=1
 for _ in range(160):
  P=softmax(X@W); grad=X.T@(P-Y)/max(1,len(y)); grad[1:]+=alpha*W[1:]; W-=.35*grad
 return W
def predict(W,X): return softmax(X@W)
def counts_prob(train,condition=None):
 ys=[r[f'outcome_h{H}'] for r in train if r[f'outcome_h{H}']]
 if not ys:return np.ones(4)/4
 c=Counter(ys); return np.array([c[f]/len(ys) for f in FAMS])
def model_probs(train,ev,h):
 global H; H=h; train=[r for r in train if r[f'outcome_h{h}']];
 if len(train)<8:return np.ones((len(ev),4))/4,1.0
 split=max(4,int(len(train)*.8)); alphas=[.1,1.0,10.0]; best=1.0; bestscore=1e9
 for a in alphas:
  W=train_logit(onehot(pd.DataFrame(train[:split])),[r[f'outcome_h{h}'] for r in train[:split]],a); P=predict(W,onehot(pd.DataFrame(train[split:]))) if split<len(train) else None; score=float(np.mean((P-np.eye(4)[[FAMS.index(r[f'outcome_h{h}']) for r in train[split:]]])**2)) if P is not None else 0
  if score<bestscore:bestscore=score;best=a
 W=train_logit(onehot(pd.DataFrame(train)),[r[f'outcome_h{h}'] for r in train],best); return predict(W,onehot(ev)),best
def baseline_probs(train,ev,h,kind):
 ys=[r[f'outcome_h{h}'] for r in train if r[f'outcome_h{h}']]; hist=np.array([ys.count(f)/len(ys) for f in FAMS]) if ys else np.ones(4)/4
 if kind=='target_history':return np.tile(hist,(len(ev),1))
 by=defaultdict(Counter)
 for r in train:
  y=r[f'outcome_h{h}'];
  if y: by[(r['regime_t'],r['regime_t1'] if kind=='previous_state' else r['regime_t'])][y]+=1
 out=[]
 for r in ev:
  key=(r['regime_t'],r['regime_t1'] if kind=='previous_state' else r['regime_t']); c=by.get(key)
  if not c:out.append(hist)
  else:out.append(np.array([c[f]/sum(c.values()) for f in FAMS]))
 return np.array(out)
def score_probs(events,train_end,lo,hi,h):
 allr=events.to_dict('records'); train=[r for r in allr if r['event_year']<=train_end and r[f'outcome_h{h}']]; ev=[r for r in allr if lo<=r['event_year']<=hi and r[f'outcome_h{h}']];
 if not ev:return {'train_events':len(train),'eval_events':0,'candidate_brier':None,'target_history_brier':None,'state_persistence_brier':None,'previous_state_brier':None,'candidate_accuracy':None,'alpha':None}
 P,a=model_probs(train,ev,h); Ys=np.eye(4)[[FAMS.index(r[f'outcome_h{h}']) for r in ev]]; res={'train_events':len(train),'eval_events':len(ev),'reporters':len(set(r['reporter_id'] for r in ev)),'candidate_brier':float(np.mean((P-Ys)**2)),'candidate_accuracy':float(np.mean(np.argmax(P,axis=1)==np.argmax(Ys,axis=1))),'alpha':a}
 for k in ['target_history','state_persistence','previous_state']:
  Q=baseline_probs(train,ev,h,k); res[k+'_brier']=float(np.mean((Q-Ys)**2))
 return res
def block_states(states,rng):
 rows=[]
 for rid,g in states.groupby('reporter_id'):
  g=g.sort_values('year'); pre=g[g.year<=2004].to_dict('records'); post=g[g.year>=2005].to_dict('records'); years=[r['year'] for r in post]; blocks=[]; i=0
  while i<len(post): L=int(rng.choice([2,3])); blocks.append(post[i:i+L]); i+=L
  rng.shuffle(blocks); flat=[x for b in blocks for x in b]
  for y,r in zip(years,flat): q=dict(r);q['year']=y;rows.append(q)
  rows.extend(pre)
 return pd.DataFrame(rows)
def rank_states(states,rng):
 z=states.copy();
 for rid,g in z.groupby('reporter_id'):
  ids=g['top'].astype(object).to_numpy().copy(); rng.shuffle(ids); z.loc[g.index,'top']=ids
 z=z.sort_values(['reporter_id','year']); z['top1_exit']=z.groupby('reporter_id')['top'].transform(lambda x:x.ne(x.shift(1))).fillna(False); z['partner_turnover']=z['top1_exit']; return z
def placebo_events(states,original,rng):
 m=state_lookup(states); out=[]
 for rid,g in original.groupby('reporter_id'):
  choices=[y for y in range(2007,2023) if m.get((rid,y)) and m.get((rid,y-1)) and m.get((rid,y-2)) and m[(rid,y)]['valid'] and m[(rid,y-1)]['valid'] and m[(rid,y-2)]['valid']]; picks=rng.choice(choices,size=len(g),replace=len(choices)<len(g)) if choices else []
  for t in picks:
   e=event_at(rid,int(t),m)
   if e:out.append(e)
 return pd.DataFrame(out)
def null_stat(states,events,kind,rng,h=2):
 z=block_states(states,rng) if kind=='block' else (rank_states(states,rng) if kind=='rank' else states); z=attach_regimes(z,fit_regimes(z,2014)); ev=placebo_events(z,events,rng) if kind=='time' else make_events(z); r=score_probs(ev,2014,2015,2022,h); vals=[r['candidate_brier'],r['target_history_brier'],r['state_persistence_brier'],r['previous_state_brier']]; return (r['candidate_brier']-min(vals[1:])) if all(v is not None for v in vals) else np.nan
def main():
 contract=json.loads(CONTRACT.read_text()); pools,obs,dup=load_inputs(); raw=raw_map(obs); states=build_states(pools,raw); states=attach_regimes(states,fit_regimes(states,2014)); events=make_events(states); states.to_csv(OUT/'TRADE_REGIME_TRANSITION_STATE_PANEL_V1.csv',index=False); events.to_csv(OUT/'TRADE_REGIME_TRANSITION_EVENTS_V1.csv',index=False)
 rolling=[]
 for o in contract['evaluation']['rolling_origins']:
  for h in [1,2,3]:
   r=score_probs(events,o,o+1,o+2,h);r.update({'origin':o,'horizon':h});rolling.append(r)
 final={str(h):score_probs(events,2014,2015,2022,h) for h in [1,2,3]}; observed=final['2']['candidate_brier']-min(final['2']['target_history_brier'],final['2']['state_persistence_brier'],final['2']['previous_state_brier']) if final['2']['candidate_brier'] is not None else None
 nulls=[]
 for kind in ['block','rank','time']:
  vals=np.array([null_stat(states,events,kind,rng,2) for _ in range(2000)],float); vals=vals[~np.isnan(vals)]; nulls.append({'variant':kind,'horizon':2,'replicates':2000,'null_mean':float(vals.mean()) if len(vals) else None,'null_sd':float(vals.std(ddof=1)) if len(vals)>1 else None,'observed_advantage':observed,'p_lower_tail':float((np.sum(vals<=observed)+1)/(len(vals)+1)) if len(vals) and observed is not None else None,'unique_statistics':int(len(np.unique(np.round(vals,12)))) if len(vals) else 0,'status':'non_degenerate' if len(np.unique(np.round(vals,12)))>1 else 'degenerate'})
 sub=[]
 for lo,hi in [(2015,2017),(2018,2020),(2021,2022)]: sub.append({'window':[lo,hi],**score_probs(events,2014,lo,hi,2)})
 checks={'event_rows':len(events),'final_h2_events':final['2']['eval_events'],'coverage':final['2']['eval_events']>=30,'candidate_gain_vs_best_h2':observed is not None and observed<=-.05,'rolling_origins':len(rolling),'rolling_effect_direction':all(r['candidate_brier'] is not None and r['candidate_brier']<=min(r['target_history_brier'],r['state_persistence_brier'],r['previous_state_brier']) for r in rolling if r['horizon']==2),'three_subwindows':sum(1 for r in sub if r['eval_events']>=30 and r['candidate_brier'] is not None and r['candidate_brier']<=min(r['target_history_brier'],r['state_persistence_brier'],r['previous_state_brier'])-.05)>=3,'nulls_non_degenerate':all(r['status']=='non_degenerate' for r in nulls),'influential_exclusion_not_implemented':False}; status='supported_predictive' if all(checks.values()) else ('not_testable' if not checks['coverage'] else 'rejected')
 summary={'contract_id':contract['contract_id'],'contract_sha256':sha(CONTRACT),'selection_sha256':sha(SEL),'observation_sha256':sha(OBS),'seed':SEED,'reporters':len(pools),'duplicate_input_keys':dup,'state_rows':len(states),'event_rows':len(events),'regime_count':int(states.regime.nunique()),'rolling_metrics':rolling,'locked_confirmation':final,'subwindows':sub,'nulls':nulls,'observed_advantage_h2':observed,'admission_checks':checks,'predictive_evidence_status':status,'causal_validation_status':'not_run','runtime_status':'not_eligible','causal_claim':False,'notes':['Model learns sequence-to-outcome probabilities from fit only.','No raw modification, imputation, normalization, source averaging, or frequency conversion.','Rank and block nulls preserve declared raw/state invariants; time placebo changes event timing only.','This is the final predictive attempt on current IMTS trade observations.']}
 (OUT/'TRADE_REGIME_TRANSITION_SUMMARY_V1.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); pd.DataFrame(rolling).to_csv(OUT/'TRADE_REGIME_TRANSITION_ROLLING_METRICS_V1.csv',index=False); pd.DataFrame(sub).to_csv(OUT/'TRADE_REGIME_TRANSITION_SUBWINDOWS_V1.csv',index=False); (OUT/'TRADE_REGIME_TRANSITION_NULL_SUMMARIES_V1.json').write_text(json.dumps(nulls,ensure_ascii=False,indent=2)+'\n'); man={'run_id':'TRADE_REGIME_TRANSITION_DISCOVERY_V1_RUN','contract_ref':str(CONTRACT.relative_to(ROOT)),'contract_sha256':summary['contract_sha256'],'code_ref':'tooling/run_trade_regime_transition_discovery_v1.py','code_sha256':sha(ROOT/'tooling/run_trade_regime_transition_discovery_v1.py'),'seed':SEED,'inputs':[str(SEL.relative_to(ROOT)),str(OBS.relative_to(ROOT))],'null_replicates':{'block':2000,'rank':2000,'time':2000},'status':status,'research_only':True,'causal_validation_status':'not_run','runtime_eligible':False,'causal_claim':False}; (OUT/'TRADE_REGIME_TRANSITION_RUN_MANIFEST_V1.json').write_text(json.dumps(man,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'status':status,'reporters':len(pools),'states':len(states),'events':len(events),'final_h2':final['2'],'checks':checks},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
