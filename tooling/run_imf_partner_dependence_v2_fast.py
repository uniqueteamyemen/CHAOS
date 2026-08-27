#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,platform
from collections import Counter
import numpy as np
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); SRC=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH'; OBS=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVED_RECORDS_2000_2024.csv'; SEL=ROOT/'experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_SELECTION_REGISTER_V2.csv'; MACRO=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'; REGION_RAW=SRC/'raw/worldbank_country_metadata_v2/worldbank_country_metadata.json'; CONTRACT=ROOT/'experimental_contracts/IMF_IMTS_PARTNER_DEPENDENCE_CONTRACT_V2.json'; OUT=ROOT/'experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2'; OUT.mkdir(parents=True,exist_ok=True); H=[1,2,3]; YEARS=np.arange(2005,2022); R=10000; P=5000; rng=np.random.default_rng(20260827)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rd(x,y):
 x=np.asarray(x,dtype=bool); y=np.asarray(y,dtype=bool); nx=int(x.sum()); nn=int((~x).sum()); return float(y[x].mean()-y[~x].mean()) if nx and nn else np.nan
def agg(vals):
 vals=np.asarray(vals); anyt=(vals==1).any(axis=-1); anym=(vals<0).any(axis=-1); return np.where(anyt,1,np.where(anym,np.nan,0))
def stat_batch(x,y):
 x=np.asarray(x,dtype=bool); y=np.asarray(y,dtype=bool); sx=x.sum(axis=1); syx=(x*y).sum(axis=1); den=x.shape[1]-sx; return np.where((sx>0)&(den>0),syx/sx-(y.sum(axis=1)-syx)/den,np.nan)
def metrics(panel,lo,hi,variants):
 out=[]; ix=(panel.origin_year>=lo)&(panel.origin_year<=hi)
 for split,v in variants:
  state=panel[v].to_numpy(dtype=float)
  for h in H:
   y=panel[f'outcome_h{h}'].to_numpy(dtype=float); keep=ix&np.isfinite(state)&np.isfinite(y); x=state[keep].astype(bool); yy=y[keep].astype(bool); out.append({'split':split,'variant':v,'horizon':h,'rows':int(keep.sum()),'reporters':int(panel.loc[keep,'reporter_id'].nunique()),'regions':int(panel.loc[keep,'region_id'].nunique()),'positive_exposures':int(x.sum()),'positive_outcomes':int(yy.sum()),'exposed_outcomes':int(yy[x].sum()) if x.sum() else 0,'unexposed_outcomes':int(yy[~x].sum()) if (~x).sum() else 0,'event_rate_exposed':float(yy[x].mean()) if x.sum() else None,'event_rate_unexposed':float(yy[~x].mean()) if (~x).sum() else None,'risk_difference':rd(x,yy)})
 return out
def main():
 contract=json.loads(CONTRACT.read_text()); selection=pd.read_csv(SEL); selection_counts=selection.groupby('reporter_id').size(); reporters=sorted(selection_counts[selection_counts==10].index.tolist()); nrep=len(reporters); ri={r:i for i,r in enumerate(reporters)}; selection=selection[selection.reporter_id.isin(reporters)].sort_values(['reporter_id','candidate_rank']).copy(); candidates={r:selection[selection.reporter_id==r].partner_id.tolist() for r in reporters}; active={r:selection[(selection.reporter_id==r)&selection.active_set].partner_id.tolist() for r in reporters}; shares={r:dict(zip(selection[selection.reporter_id==r].partner_id,selection[selection.reporter_id==r].baseline_mean_share)) for r in reporters}; top3={r:float(selection[selection.reporter_id==r].head(3).baseline_mean_share.sum()) for r in reporters}; top1={r:float(selection[selection.reporter_id==r].head(1).baseline_mean_share.sum()) for r in reporters}; top5={r:float(selection[selection.reporter_id==r].head(5).baseline_mean_share.sum()) for r in reporters};
 regions_raw=json.loads(REGION_RAW.read_text()); regions={x['id']:(x.get('region') or {}).get('id') for x in regions_raw[1]}; region_names={x['id']:(x.get('region') or {}).get('value') for x in regions_raw[1]}; obs=pd.read_csv(OBS,low_memory=False); obs=obs[(obs.country.isin(reporters))&(obs.indicator=='XG_FOB_USD')&(obs.frequency=='A')].copy(); obs['year']=pd.to_numeric(obs.time_period,errors='coerce'); obs['value']=pd.to_numeric(obs.obs_value_raw,errors='coerce'); obs=obs.dropna(subset=['country','counterpart_country','year','value']).drop_duplicates(['country','counterpart_country','year']); world={(x.country,int(x.year)):float(x.value) for x in obs[obs.counterpart_country=='G001'].itertuples()}; bil={(x.country,x.counterpart_country,int(x.year)):float(x.value) for x in obs[obs.counterpart_country!='G001'].itertuples() if x.country!=x.counterpart_country}; macro=pd.read_csv(MACRO,usecols=['entity_code','year','wdi__NY.GDP.MKTP.KD.ZG']); gdp={(x.entity_code,int(x.year)):float(x[2]) if pd.notna(x[2]) else np.nan for x in macro.itertuples(index=False)}
 val=np.full((nrep,len(YEARS),10),-1,dtype=np.int8); share_state=np.full_like(val,-1); rows=[]; rep_ids=[]; years=[]; dep3=[]; dep1=[]; dep5=[]
 for r in reporters:
  i=ri[r]; ps=candidates[r]; act=active[r]; d3=top3[r]>=.50; d1=top1[r]>=.20; d5=top5[r]>=.70
  for ti,y in enumerate(YEARS):
   rawt={}; rawp={}; vvals=[]; svals=[]
   for j,p in enumerate(ps):
    cur=bil.get((r,p,int(y)),np.nan); prev=bil.get((r,p,int(y-1)),np.nan); wc=world.get((r,int(y)),np.nan); wp=world.get((r,int(y-1)),np.nan); ok=np.isfinite(cur) and np.isfinite(prev) and cur>0 and prev>0; sok=ok and np.isfinite(wc) and np.isfinite(wp) and wc>0 and wp>0; vv=-1 if not ok else int(cur<.70*prev); ss=-1 if not sok else int(cur/wc<.70*(prev/wp)); val[i,ti,j]=vv; share_state[i,ti,j]=ss; vvals.append(vv); svals.append(ss); rawt[p]=None if not np.isfinite(cur) else float(cur); rawp[p]=None if not np.isfinite(prev) else float(prev)
   va=agg(val[i,ti,[ps.index(p) for p in act]]); sa=agg(share_state[i,ti,[ps.index(p) for p in act]]); rows.append({'reporter_id':r,'origin_year':int(y),'region_id':regions.get(r),'region_name':region_names.get(r),'candidate_partner_ids':json.dumps(ps),'active_partner_ids':json.dumps(act),'baseline_partner_shares':json.dumps(shares[r],sort_keys=True),'top3_baseline_share':top3[r],'top1_baseline_share':top1[r],'top5_baseline_share':top5[r],'dependence_top3_state':bool(d3),'dependence_top1_state':bool(d1),'dependence_top5_state':bool(d5),'active_value_contraction_state':float(va) if np.isfinite(va) else np.nan,'active_share_loss_state':float(sa) if np.isfinite(sa) else np.nan,'primary_interaction_state':float(va) if d3 and np.isfinite(va) else (np.nan if d3 else 0.0),'top1_value_interaction_state':float(va) if d1 and np.isfinite(va) else (np.nan if d1 else 0.0),'top5_value_interaction_state':float(va) if d5 and np.isfinite(va) else (np.nan if d5 else 0.0),'top3_share_interaction_state':float(sa) if d3 and np.isfinite(sa) else (np.nan if d3 else 0.0),'shocked_active_partner_ids_value':json.dumps([p for p in act if val[i,ti,ps.index(p)]==1]),'shocked_candidate_partner_ids_value':json.dumps([p for p in ps if val[i,ti,ps.index(p)]==1]),'shocked_active_partner_ids_share':json.dumps([p for p in act if share_state[i,ti,ps.index(p)]==1]),'raw_active_partner_values_t':json.dumps({p:rawt[p] for p in act},sort_keys=True),'raw_active_partner_values_t_minus_1':json.dumps({p:rawp[p] for p in act},sort_keys=True),'all_candidate_value_complete':bool((val[i,ti]>=0).all()),'all_candidate_share_complete':bool((share_state[i,ti]>=0).all())}); rep_ids.append(i); years.append(int(y)); dep3.append(d3); dep1.append(d1); dep5.append(d5)
 panel=pd.DataFrame(rows); panel['gdp_growth']=[gdp.get((r,int(y)),np.nan) for r,y in zip(panel.reporter_id,panel.origin_year)]
 for h in H: panel[f'outcome_h{h}']=[(float(gdp.get((r,int(y+h)),np.nan))<=float(base)-2.0) if np.isfinite(base) and np.isfinite(gdp.get((r,int(y+h)),np.nan)) else np.nan for r,y,base in zip(panel.reporter_id,panel.origin_year,panel.gdp_growth)]
 panel.to_csv(OUT/'IMF_IMTS_PARTNER_DEPENDENCE_REPORTER_YEAR_PANEL_V2.csv',index=False); panel_rep=np.asarray(rep_ids); tix=np.asarray(years)-2005; split_bounds={'fit':(2005,2013),'validation':(2014,2017),'confirmation':(2018,2021)}; variants=[]
 for s,v in [('fit','primary_interaction_state'),('validation','primary_interaction_state'),('confirmation','primary_interaction_state'),('fit','top1_value_interaction_state'),('validation','top1_value_interaction_state'),('confirmation','top1_value_interaction_state'),('fit','top5_value_interaction_state'),('validation','top5_value_interaction_state'),('confirmation','top5_value_interaction_state'),('fit','top3_share_interaction_state'),('validation','top3_share_interaction_state'),('confirmation','top3_share_interaction_state')]: variants.append((s,v))
 metrics_rows=metrics(panel,2005,2021,variants); # replace split labels from metric function by explicit bounds below
 metrics_rows=[]
 for split,(lo,hi) in split_bounds.items():
  sub=panel[panel.origin_year.between(lo,hi)].copy()
  for v in ['primary_interaction_state','top1_value_interaction_state','top5_value_interaction_state','top3_share_interaction_state']:
   for h in H:
    y=sub[f'outcome_h{h}'].to_numpy(dtype=float); x0=sub[v].to_numpy(dtype=float); keep=np.isfinite(x0)&np.isfinite(y); x=x0[keep].astype(bool); yy=y[keep].astype(bool); metrics_rows.append({'split':split,'variant':v,'horizon':h,'rows':int(keep.sum()),'reporters':int(sub.loc[keep,'reporter_id'].nunique()),'regions':int(sub.loc[keep,'region_id'].nunique()),'positive_exposures':int(x.sum()),'positive_outcomes':int(yy.sum()),'exposed_outcomes':int(yy[x].sum()) if x.sum() else 0,'unexposed_outcomes':int(yy[~x].sum()) if (~x).sum() else 0,'event_rate_exposed':float(yy[x].mean()) if x.sum() else None,'event_rate_unexposed':float(yy[~x].mean()) if (~x).sum() else None,'risk_difference':rd(x,yy)})
 pd.DataFrame(metrics_rows).to_csv(OUT/'IMF_IMTS_PARTNER_DEPENDENCE_METRICS_V2.csv',index=False); confmask=panel.origin_year.between(2018,2021).to_numpy(); base_state=panel.primary_interaction_state.to_numpy(dtype=float); observed=[]
 for h in H:
  y=panel[f'outcome_h{h}'].to_numpy(dtype=float); keep=confmask&np.isfinite(base_state)&np.isfinite(y); observed.append(rd(base_state[keep],y[keep]))
 observed=np.asarray(observed); obsmax=float(np.nanmax(observed)) if np.isfinite(observed).any() else np.nan; selected_h=int(H[int(np.nanargmax(observed))]) if np.isfinite(observed).any() else None; c_mask=confmask&np.isfinite(base_state); c_rep=panel.loc[c_mask,'reporter_id'].to_numpy(); c_ridx=np.array([ri[r] for r in c_rep]); c_tix=panel.loc[c_mask,'origin_year'].to_numpy()-2005; shock_val=val[c_ridx,c_tix,:]; dep_c=np.array([top3[r]>=.50 for r in c_rep]);
 def batch_identity():
  allnull=[]; n=len(c_ridx)
  for start in range(0,R,500):
   size=min(500,R-start); masks=np.zeros((size,nrep,10),dtype=bool)
   scores=rng.random((size,nrep,10)); masks[np.arange(size)[:,None,None],np.arange(nrep)[None,:,None],np.argsort(scores,axis=2)[:,:,:5]]=True; active=np.take_along_axis(masks[:,c_ridx,:],np.zeros((size,n,1),dtype=int),axis=2) if False else masks[:,c_ridx,:];
   vals=[]
   for j in range(10): pass
   # all ten candidate shock states are -1/0/1; use selected masks
   true=(active & (shock_val[None,:,:]==1)).any(axis=2); miss=(active & (shock_val[None,:,:]<0)).any(axis=2); x=np.where(true,1,np.where(miss,np.nan,0)); x= np.where(dep_c[None,:],x,0)
   byh=[]
   for h in H:
    y=panel.loc[c_mask,f'outcome_h{h}'].to_numpy(dtype=float); keep=np.isfinite(y); xb=x[:,keep]; yy=np.broadcast_to(y[keep],(size,keep.sum())).astype(bool); byh.append(stat_batch(xb,yy))
   allnull.append(np.nanmax(np.vstack(byh),axis=0))
  return np.concatenate(allnull)
 idnull=batch_identity(); idp=float((1+np.sum(idnull>=obsmax))/(len(idnull)+1)) if np.isfinite(obsmax) else None
 def batch_outcome():
  allnull=[]; n=len(c_ridx); outcomes={h:panel.loc[c_mask,f'outcome_h{h}'].to_numpy(dtype=float) for h in H}
  for start in range(0,R,500):
   size=min(500,R-start); byh=[]
   for h in H:
    y=outcomes[h]; yp=np.empty((size,n),dtype=bool)
    for i in range(nrep):
     ix=np.where(c_ridx==i)[0]; base=y[ix].astype(bool); yp[:,ix]=base[rng.random((size,len(ix))).argsort(axis=1)] if len(ix) else False
    x=np.broadcast_to(base_state[c_mask][None,:].astype(bool),(size,n)); yy=yp; byh.append(stat_batch(x,yy))
   allnull.append(np.nanmax(np.vstack(byh),axis=0))
  return np.concatenate(allnull)
 onull=batch_outcome(); outp=float((1+np.sum(onull>=obsmax))/(len(onull)+1)) if np.isfinite(obsmax) else None
 def batch_placebo():
  allnull=[]; active_idx=np.array([[candidates[r].index(p) for p in active[r]] for r in reporters]); n=len(c_ridx); base_all=val
  for start in range(0,P,250):
   size=min(250,P-start); shifts=rng.integers(1,17,size=(size,nrep,10)); idx=np.broadcast_to(active_idx[c_ridx][None,:,:],(size,n,5)); sh=np.take_along_axis(shifts[:,c_ridx,:],idx,axis=2); pos=(c_tix[None,:,None]-sh)%17; flat=base_all[c_ridx].reshape(n,170); codes=pos*10+idx; state=np.take_along_axis(np.broadcast_to(flat[None,:,:],(size,n,170)),codes,axis=2); xstate=agg(state); xstate=np.where(dep_c[None,:],xstate,0); byh=[]
   for h in H:
    y=panel.loc[c_mask,f'outcome_h{h}'].to_numpy(dtype=float); keep=np.isfinite(y); byh.append(stat_batch(xstate[:,keep].astype(bool),np.broadcast_to(y[keep].astype(bool),(size,keep.sum()))))
   allnull.append(np.nanmax(np.vstack(byh),axis=0))
  return np.concatenate(allnull)
 pnull=batch_placebo(); pp=float((1+np.sum(pnull>=obsmax))/(len(pnull)+1)) if np.isfinite(obsmax) else None
 # cluster bootstrap and region holdout use direct loops over <= 135 reporters.
 conf=panel[confmask].copy(); boot=[]; rep_list=conf.reporter_id.unique().tolist()
 for _ in range(P):
  chosen=rng.choice(rep_list,size=len(rep_list),replace=True); q=pd.concat([conf[conf.reporter_id==r] for r in chosen],ignore_index=True); vals=[]
  for h in H:
   y=q[f'outcome_h{h}'].to_numpy(dtype=float); x=q.primary_interaction_state.to_numpy(dtype=float); k=np.isfinite(x)&np.isfinite(y); vals.append(rd(x[k],y[k]))
  boot.append(np.nanmax(vals))
 boot=np.asarray(boot); hold=[]
 for reg in sorted(conf.region_id.dropna().unique()):
  q=conf[conf.region_id!=reg]; y=q.outcome_h2.to_numpy(dtype=float); x=q.primary_interaction_state.to_numpy(dtype=float); k=np.isfinite(x)&np.isfinite(y); held=int(conf[conf.region_id==reg].reporter_id.nunique()); hold.append({'held_out_region_id':reg,'held_out_region_reporters':held,'remaining_reporters':int(q.reporter_id.nunique()),'rows':int(k.sum()),'risk_difference_h2':rd(x[k],y[k]),'testable':bool(held>=10 and k.sum()>=30)})
 hold_df=pd.DataFrame(hold); hold_df.to_csv(OUT/'IMF_IMTS_REGION_HOLDOUT_V2.csv',index=False)
 stab=[]
 for r,q in conf.groupby('reporter_id'):
  y=q.outcome_h2.to_numpy(dtype=float); x=q.primary_interaction_state.to_numpy(dtype=float); k=np.isfinite(x)&np.isfinite(y); v=rd(x[k],y[k]); stab.append({'reporter_id':r,'region_id':q.region_id.iloc[0],'rows':int(k.sum()),'risk_difference_h2':v,'defined':bool(np.isfinite(v)),'positive':bool(np.isfinite(v) and v>0)})
 stabdf=pd.DataFrame(stab); stabdf.to_csv(OUT/'IMF_IMTS_REPORTER_STABILITY_V2.csv',index=False)
 exp=conf[conf.primary_interaction_state==1]; shocked=[]
 for s in exp.shocked_active_partner_ids_value: shocked.extend(json.loads(s))
 maxrep=float(exp.reporter_id.value_counts().max()/len(exp)) if len(exp) else None; maxpartner=float(Counter(shocked).most_common(1)[0][1]/len(shocked)) if shocked else None; coverage=bool(len(exp)>=10 and exp.reporter_id.nunique()>=5 and int(conf.outcome_h2.sum())>=10 and conf.reporter_id.nunique()>=50 and conf.region_id.nunique()>=3); stability=bool(stabdf.defined.sum()>=20 and stabdf[stabdf.defined].positive.mean()>=.60) if stabdf.defined.any() else False; holdpass=bool(hold_df.testable.sum()>=3); conpass=bool((maxrep is None or maxrep<=.40) and (maxpartner is None or maxpartner<=.50)); idunique=int(np.unique(idnull).size); idsd=float(np.std(idnull,ddof=1)); idnon=bool(idunique>=10 and idsd>0); checks={'positive_confirmation_stat':bool(np.isfinite(obsmax) and obsmax>0),'identity_null_non_degenerate':idnon,'identity_null_pass':bool(idnon and idp is not None and idp<.025),'outcome_null_pass':bool(outp is not None and outp<.025),'time_placebo_pass':bool(pp is not None and pp<.025),'coverage_pass':coverage,'stability_pass':stability,'holdout_pass':holdpass,'concentration_pass':conpass}; status='supported_predictive' if all(checks.values()) else ('not_testable' if (not coverage or not idnon) else 'rejected'); summary={'test_id':'IMF_IMTS_PARTNER_DEPENDENCE_V2','contract_id':'IMF_IMTS_PARTNER_DEPENDENCE_CONTRACT_V2','contract_sha256':sha(CONTRACT),'input_sha256':{'observations':sha(OBS),'selection':sha(SEL),'macro':sha(MACRO),'region_raw':sha(REGION_RAW)},'reporters':nrep,'selection_rows':int(len(selection)),'candidate_pool_size':10,'active_set_size':5,'panel_rows':int(len(panel)),'metrics':metrics_rows,'confirmation_exposure_rows':int(len(exp)),'confirmation_exposed_reporters':int(exp.reporter_id.nunique()),'confirmation_positive_h2_outcomes':int(conf.outcome_h2.sum()),'confirmation_regions':int(conf.region_id.nunique()),'observed_confirmation_max_risk_difference':obsmax,'selected_horizon':selected_h,'identity_null':{'replicates':R,'p_value':idp,'null_mean':float(np.mean(idnull)),'null_sd':idsd,'null_q95':float(np.quantile(idnull,.95)),'unique_statistics':idunique,'eligible_rows':int(len(c_ridx))},'outcome_null':{'replicates':R,'p_value':outp,'null_mean':float(np.mean(onull)),'null_sd':float(np.std(onull,ddof=1)),'null_q95':float(np.quantile(onull,.95)),'eligible_rows':int(len(c_ridx))},'time_placebo':{'replicates':P,'p_value':pp,'null_mean':float(np.mean(pnull)),'null_sd':float(np.std(pnull,ddof=1)),'null_q95':float(np.quantile(pnull,.95))},'cluster_bootstrap':{'replicates':P,'mean':float(np.mean(boot)),'q025':float(np.quantile(boot,.025)),'q975':float(np.quantile(boot,.975))},'coverage_pass':coverage,'reporter_stability_pass':stability,'region_holdout_pass':holdpass,'concentration':{'max_reporter_share':maxrep,'max_partner_event_share':maxpartner},'promotion_checks':checks,'status':status,'status_reason':('insufficient_coverage_or_null_degeneracy' if status=='not_testable' else None),'causal_claim':False,'runtime_eligible':False,'notes':['V2 expands to all WDI-target-ready reporters with a complete ten-partner baseline pool.','Candidate and active partner sets use only 2000-2004 raw IMTS shares.','G001 is denominator only.','Missing bilateral states remain missing; no missing-as-zero.','Partner-level rows are not pooled as independent GDP outcomes.','V1 contract and results remain preserved.']}; (OUT/'IMF_IMTS_PARTNER_DEPENDENCE_SUMMARY_V2.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); manifest={'run_id':'IMF_IMTS_PARTNER_DEPENDENCE_RUN_V2','executed_at_utc':datetime.now(timezone.utc).isoformat(),'contract_status':contract.get('status'),'contract_sha256':sha(CONTRACT),'tool':'tooling/run_imf_partner_dependence_v2_fast.py','python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'rng_seed':20260827,'status':status,'raw_modified':False,'runtime_eligible':False}; (OUT/'IMF_IMTS_PARTNER_DEPENDENCE_RUN_MANIFEST_V2.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'status':status,'reporters':nrep,'panel_rows':len(panel),'confirmation_exposure_rows':len(exp),'confirmation_exposed_reporters':int(exp.reporter_id.nunique()),'observed_confirmation_max_risk_difference':obsmax,'selected_horizon':selected_h,'identity_null_p':idp,'identity_null_sd':idsd,'identity_null_unique':idunique,'outcome_null_p':outp,'time_placebo_p':pp,'coverage_pass':coverage,'stability_pass':stability,'holdout_pass':holdpass,'concentration_pass':conpass},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
