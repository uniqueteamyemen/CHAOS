#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,os
import numpy as np
import pandas as pd

ROOT=Path('/home/ubuntu/CHAOS')
CONTRACT=ROOT/'experimental_contracts/dual_track_v02/IMF_IMTS_PARTNER_SUBSTITUTION_CONTRACT_V3.json'
SEL=ROOT/'experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_SELECTION_REGISTER_V2.csv'
OBS=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVED_RECORDS_2000_2024.csv'
SHARDS=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v2/observations_shards'
MANIFEST=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVATION_SHARDS_MANIFEST_V2.json'
OUT=ROOT/'experiments/dual_track_v02/imf_partner_substitution_v3'; OUT.mkdir(parents=True,exist_ok=True)
SEED=int(os.environ.get('CHAOS_V3_SEED','271108')); HORIZONS=[1,2,3]; SPLITS={'fit':(2005,2014),'confirmation':(2015,2024)}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def load_obs():
 cols=['country','counterpart_country','time_period','obs_value_raw']
 if OBS.exists():
  d=pd.read_csv(OBS,usecols=cols,low_memory=False)
  mode='aggregate_local'
 else:
  files=sorted(SHARDS.glob('*.csv'))
  if not files: raise FileNotFoundError('no aggregate or shards')
  d=pd.concat([pd.read_csv(x,usecols=cols) for x in files],ignore_index=True)
  mode='tracked_reporter_shards'
 d['year']=pd.to_numeric(d['time_period'],errors='coerce').astype('Int64')
 d['value']=pd.to_numeric(d['obs_value_raw'],errors='coerce')
 d=d.dropna(subset=['country','counterpart_country','year']).copy(); d['year']=d['year'].astype(int)
 d=d[(d.year>=2000)&(d.year<=2024)]
 dup=d.duplicated(['country','counterpart_country','year'],keep=False)
 if dup.any(): raise ValueError(f'duplicate reporter-partner-year rows: {int(dup.sum())}')
 return d,mode

def rate_for_events(events,h):
 usable=[e for e in events if e['year']+h<=2024]
 if not usable: return np.nan,0,0
 ok=0
 for e in usable:
  vals=[]
  valid=True
  for j in range(1,h+1):
   x=e['series'].get(e['year']+j)
   if x is None: valid=False; break
   vals.append(x)
  if valid and all(isinstance(x,dict) and x.get('top1')==e['replacement'] for x in vals): ok+=1
 return ok/len(usable),len(usable),ok

def make_series(d, candidates):
 m=d[d.counterpart_country.isin(candidates) & d.year.between(2000,2024)].copy()
 out={}
 for y,g in m.groupby('year'):
  if len(g)!=len(candidates) or g.value.isna().any() or (g.value<=0).any(): continue
  # deterministic lexical tie break after descending raw value
  g=g.sort_values(['value','counterpart_country'],ascending=[False,True])
  out[int(y)]={'top1':str(g.iloc[0].counterpart_country),'top3':tuple(g.iloc[:3].counterpart_country.astype(str))}
 return out

def build_reporter_data(obs,sel):
 result={}
 for reporter,g in sel.groupby('reporter_id',sort=True):
  g=g.sort_values('candidate_rank'); candidates=list(g.partner_id.astype(str)); baseline_top1=str(g.iloc[0].partner_id); baseline_top3=set(g[g.candidate_rank<=3].partner_id.astype(str))
  od=obs[obs.country==reporter]
  series=make_series(od,candidates)
  if len(candidates)!=10: continue
  result[reporter]={'candidates':candidates,'baseline_top1':baseline_top1,'baseline_top3':baseline_top3,'series':series}
 return result

def events_for(rep, start,end, diagnostic=False):
 ev=[]; s=rep['series']; base=rep['baseline_top1']
 for y in range(start,end+1):
  cur=s.get(y)
  if cur is None: continue
  displaced=(cur.get('top1')!=base)
  if diagnostic: displaced=(set(cur.get('top3',()))!=set(rep['baseline_top3']) and displaced)
  if displaced: ev.append({'year':y,'replacement':cur.get('top1'),'series':s})
 return ev

def metric(rep_data,split,h,diagnostic=False):
 a,b=SPLITS[split]; rows=[]
 for reporter,rep in rep_data.items():
  ev=events_for(rep,a,b,diagnostic); rate,n,ok=rate_for_events(ev,h)
  if n: rows.append({'reporter_id':reporter,'events':n,'successes':ok,'rate':rate})
 total=sum(x['events'] for x in rows); success=sum(x['successes'] for x in rows)
 return {'split':split,'variant':'diagnostic_top1_displacement' if diagnostic else 'primary_top1_displacement','horizon':h,'reporters_with_events':len(rows),'events':total,'successes':success,'persistence_rate':(success/total if total else np.nan),'reporter_rates':rows}

def sequence_map(rep_data,split):
 a,b=SPLITS[split]; out={}
 for rid,rep in rep_data.items():
  years=list(range(a,b+1)); seq=[rep['series'].get(y,{}).get('top1') for y in years]
  seq=[x for x in seq if x is not None]
  if len(seq)>=2: out[rid]=seq
 return out

def null_rates(rep_data,split,h,replicates,kind,rng):
 seqs=sequence_map(rep_data,split); results=[]; ids=list(seqs)
 for _ in range(replicates):
  perm={rid:(list(np.roll(seq, int(rng.integers(1,len(seq))))) if kind=='time_placebo' else list(rng.permutation(seq))) for rid,seq in seqs.items()}
  total=success=0
  for rid,seq in perm.items():
   rep=rep_data[rid]; years=[y for y in range(SPLITS[split][0],SPLITS[split][1]+1) if rep['series'].get(y) is not None]
   ps={y:{'top1':x} for y,x in zip(years,seq)}; ev=[]; base=rep['baseline_top1']
   for y,x in ps.items():
    if x['top1']!=base: ev.append({'year':y,'replacement':x['top1'],'series':ps})
   rate,n,ok=rate_for_events(ev,h); total+=n; success+=ok
  results.append(success/total if total else np.nan)
 return np.asarray(results,dtype=float)

def bootstrap(rep_data,split,h,rng,replicates=5000):
 ids=list(rep_data); per={rid:metric({rid:rep_data[rid]},split,h)['reporter_rates'] for rid in ids}; vals=[]
 for _ in range(replicates):
  chosen=rng.choice(ids,size=len(ids),replace=True); e=s=0
  for rid in chosen:
   for x in per[rid]: e+=x['events']; s+=x['successes']
  vals.append(s/e if e else np.nan)
 return np.asarray(vals,dtype=float)

contract=json.loads(CONTRACT.read_text()); sel=pd.read_csv(SEL); obs,mode=load_obs(); reps=build_reporter_data(obs,sel)
rng=np.random.default_rng(SEED); metrics=[]; null_summaries=[]; event_rows=[]
for split in SPLITS:
 for h in HORIZONS:
  m=metric(reps,split,h); metrics.append({k:v for k,v in m.items() if k!='reporter_rates'})
  for rid,rep in reps.items():
   for e in events_for(rep,*SPLITS[split]): event_rows.append({'split':split,'variant':'primary_top1_displacement','reporter_id':rid,'year':e['year'],'replacement':e['replacement'],'horizon':h,'eligible_for_horizon':e['year']+h<=2024})
  nr=null_rates(reps,split,h,10000,'identity',rng); obsrate=m['persistence_rate']; valid=nr[~np.isnan(nr)]; contrast=obsrate-np.nanmean(valid) if not np.isnan(obsrate) else np.nan
  null_summaries.append({'split':split,'variant':'identity_sequence_null','horizon':h,'replicates':10000,'observed_rate':obsrate,'null_mean':float(np.nanmean(valid)),'null_sd':float(np.nanstd(valid,ddof=1)),'contrast':float(contrast),'p_value':float((np.sum(valid>=obsrate)+1)/(len(valid)+1)),'unique_statistics':int(len(np.unique(np.round(valid,12)))),'status':'pass_non_degenerate' if len(np.unique(np.round(valid,12)))>1 else 'degenerate'})
  br=bootstrap(reps,split,h,rng); null_summaries.append({'split':split,'variant':'reporter_cluster_bootstrap','horizon':h,'replicates':5000,'mean':float(np.nanmean(br)),'q025':float(np.nanquantile(br,.025)),'q975':float(np.nanquantile(br,.975))})
  tr=null_rates(reps,split,h,5000,'time_placebo',rng); tv=tr[~np.isnan(tr)]; null_summaries.append({'split':split,'variant':'time_placebo_sequence_shift_proxy','horizon':h,'replicates':5000,'observed_rate':obsrate,'null_mean':float(np.nanmean(tv)),'null_sd':float(np.nanstd(tv,ddof=1)),'contrast':float(obsrate-np.nanmean(tv)),'p_value':float((np.sum(tv>=obsrate)+1)/(len(tv)+1)),'unique_statistics':int(len(np.unique(np.round(tv,12)))),'status':'recorded_diagnostic_only'})
for split in SPLITS:
 for h in HORIZONS:
  m=metric(reps,split,h,diagnostic=True); metrics.append({k:v for k,v in m.items() if k!='reporter_rates'})

# Clean JSON-friendly NaN values
for x in metrics+null_summaries:
 for k,v in list(x.items()):
  if isinstance(v,float) and np.isnan(v): x[k]=None
pd.DataFrame(metrics).to_csv(OUT/'IMF_IMTS_PARTNER_SUBSTITUTION_METRICS_V3.csv',index=False)
pd.DataFrame(event_rows).drop_duplicates().to_csv(OUT/'IMF_IMTS_PARTNER_SUBSTITUTION_EVENTS_V3.csv',index=False)
summary={'contract_id':contract['contract_id'],'contract_sha256':sha(CONTRACT),'observation_mode':mode,'selection_sha256':sha(SEL),'observation_sha256':sha(OBS) if OBS.exists() else json.loads(MANIFEST.read_text())['source_sha256'],'reporters':len(reps),'candidate_pool_size':10,'fit_period':list(SPLITS['fit']),'confirmation_period':list(SPLITS['confirmation']),'metrics_ref':'IMF_IMTS_PARTNER_SUBSTITUTION_METRICS_V3.csv','events_ref':'IMF_IMTS_PARTNER_SUBSTITUTION_EVENTS_V3.csv','nulls':null_summaries,'search_family':['primary_top1_displacement','diagnostic_top1_displacement'],'predictive_evidence_status':'candidate','causal_validation_status':'not_run','runtime_status':'not_eligible','causal_claim':False,'notes':['Baseline candidate pool is inherited from locked V2 selection register; no reselection after outcomes.','Missing candidate-year records are excluded, never zero-filled.','No imputation, normalization, log, differencing, smoothing, source averaging, or frequency conversion.','Time-placebo is a diagnostic sequence null and is not treated as causal evidence.']}
(OUT/'IMF_IMTS_PARTNER_SUBSTITUTION_SUMMARY_V3.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
manifest={'run_id':'IMF_IMTS_PARTNER_SUBSTITUTION_V3_DISCOVERY_RUN','contract_ref':str(CONTRACT.relative_to(ROOT)),'contract_sha256':summary['contract_sha256'],'seed':SEED,'identity_null_replicates':10000,'time_placebo_replicates':5000,'bootstrap_replicates':5000,'input_refs':[str(SEL.relative_to(ROOT)),str(OBS.relative_to(ROOT)) if OBS.exists() else str(MANIFEST.relative_to(ROOT))],'input_sha256':{'selection':summary['selection_sha256'],'observations':summary['observation_sha256']},'output_refs':[x.name for x in OUT.iterdir() if x.is_file()],'status':'completed','research_only':True}
(OUT/'IMF_IMTS_PARTNER_SUBSTITUTION_RUN_MANIFEST_V3.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'completed','reporters':len(reps),'metrics':len(metrics),'event_rows':len(event_rows),'out':str(OUT)},ensure_ascii=False,indent=2))
