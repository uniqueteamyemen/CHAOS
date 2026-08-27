#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib, json, platform
import numpy as np
import pandas as pd

ROOT=Path('/home/ubuntu/CHAOS'); SRC=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH'; OBS=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVED_RECORDS_2000_2024.csv'; SEL=ROOT/'experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_SELECTION_REGISTER_V2.csv'; MACRO=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'; REGION_RAW=SRC/'raw/worldbank_country_metadata_v2/worldbank_country_metadata.json'; CONTRACT=ROOT/'experimental_contracts/IMF_IMTS_PARTNER_DEPENDENCE_CONTRACT_V2.json'; OUT=ROOT/'experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2'; OUT.mkdir(parents=True,exist_ok=True); H=[1,2,3]; REPORTERS=pd.read_csv(SEL).groupby('reporter_id').size(); REPORTERS=REPORTERS[REPORTERS==10].index.tolist(); rng=np.random.default_rng(20260827)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rd(x):
 try:return float(x)
 except:return np.nan
def rd_risk(x,y):
 x=np.asarray(x,dtype=bool); y=np.asarray(y,dtype=bool)
 if x.sum()==0 or (~x).sum()==0:return np.nan
 return float(y[x].mean()-y[~x].mean())
def load_regions():
 d=json.loads(REGION_RAW.read_text()); return {x['id']:((x.get('region') or {}).get('id'),(x.get('region') or {}).get('value')) for x in d[1]}
def metric_rows(panel, split_bounds, variants):
 out=[]
 for split,(lo,hi) in split_bounds.items():
  z=panel[panel.origin_year.between(lo,hi)]
  for v in variants:
   for h in H:
    q=z[z[f'outcome_h{h}'].notna()&z[f'{v}_state'].notna()]; x=q[f'{v}_state'].astype(bool).to_numpy(); y=q[f'outcome_h{h}'].astype(bool).to_numpy(); out.append({'split':split,'variant':v,'horizon':h,'rows':int(len(q)),'reporters':int(q.reporter_id.nunique()),'regions':int(q.region_id.nunique()),'positive_exposures':int(x.sum()),'positive_outcomes':int(y.sum()),'exposed_outcomes':int(y[x].sum()) if x.sum() else 0,'unexposed_outcomes':int(y[~x].sum()) if (~x).sum() else 0,'event_rate_exposed':float(y[x].mean()) if x.sum() else None,'event_rate_unexposed':float(y[~x].mean()) if (~x).sum() else None,'risk_difference':rd_risk(x,y)})
 return out
def main():
 contract=json.loads(CONTRACT.read_text()); regions=load_regions(); sel=pd.read_csv(SEL); obs=pd.read_csv(OBS,low_memory=False); obs=obs[(obs.country.isin(REPORTERS))&(obs.indicator=='XG_FOB_USD')&(obs.frequency=='A')].copy(); obs['year']=pd.to_numeric(obs.time_period,errors='coerce'); obs['value']=pd.to_numeric(obs.obs_value_raw,errors='coerce'); obs=obs.dropna(subset=['country','counterpart_country','year','value']).drop_duplicates(['country','counterpart_country','year']); world=obs[obs.counterpart_country=='G001'][['country','year','value']].rename(columns={'country':'reporter_id','value':'world_exports_raw'}).drop_duplicates(['reporter_id','year']); bil=obs[obs.counterpart_country!='G001'].copy(); bil=bil[~bil.apply(lambda r:str(r.country)==str(r.counterpart_country),axis=1)].copy(); lookup={(r.country,r.counterpart_country,int(r.year)):float(r.value) for r in bil.itertuples()}; wlookup={(r.reporter_id,int(r.year)):float(r.world_exports_raw) for r in world.itertuples()}
 # Build reporter-level selection maps and source-native partner states.
 smap={}; for_rep={}
 for rep in REPORTERS:
  q=sel[sel.reporter_id==rep].sort_values('candidate_rank'); smap[rep]={'candidates':q.partner_id.tolist(),'active':q.loc[q.active_set,'partner_id'].tolist(),'shares':dict(zip(q.partner_id,q.baseline_mean_share)),'top3':float(q.head(3).baseline_mean_share.sum()),'top1':float(q.head(1).baseline_mean_share.sum()),'top5':float(q.head(5).baseline_mean_share.sum())}; for_rep[rep]=q
 rows=[]; candidate_state={}
 for rep in REPORTERS:
  x=smap[rep]; candidate_state[rep]={}
  for year in range(2005,2022):
   value_shock={}; share_shock={}; val_missing={}; share_missing={}; raw_t={}; raw_prev={}
   for p in x['candidates']:
    cur=lookup.get((rep,p,year),np.nan); prev=lookup.get((rep,p,year-1),np.nan); wc=wlookup.get((rep,year),np.nan); wp=wlookup.get((rep,year-1),np.nan); valid=bool(np.isfinite(cur) and np.isfinite(prev) and cur>0 and prev>0); raw_t[p]=None if not np.isfinite(cur) else cur; raw_prev[p]=None if not np.isfinite(prev) else prev; value_shock[p]=(bool(cur<0.70*prev) if valid else None); val_missing[p]=not valid; share_valid=bool(valid and np.isfinite(wc) and np.isfinite(wp) and wc>0 and wp>0); share_shock[p]=(bool((cur/wc)<0.70*(prev/wp)) if share_valid else None); share_missing[p]=not share_valid
   candidate_state[rep][year]={'value':value_shock,'share':share_shock}
   def agg(d,partners):
    a=[d[p] for p in partners]; return True if any(v is True for v in a) else (False if a and all(v is False for v in a) else np.nan)
   av=agg(value_shock,x['active']); ash=agg(share_shock,x['active']); dep=bool(x['top3']>=0.50); d1=bool(x['top1']>=0.20); d5=bool(x['top5']>=0.70); rows.append({'reporter_id':rep,'origin_year':year,'region_id':regions.get(rep,(None,None))[0],'region_name':regions.get(rep,(None,None))[1],'candidate_partner_ids':json.dumps(x['candidates']),'active_partner_ids':json.dumps(x['active']),'baseline_partner_shares':json.dumps({p:float(x['shares'][p]) for p in x['candidates']},sort_keys=True),'top3_baseline_share':x['top3'],'top1_baseline_share':x['top1'],'top5_baseline_share':x['top5'],'dependence_top3_state':dep,'dependence_top1_state':d1,'dependence_top5_state':d5,'active_value_contraction_state':av,'active_share_loss_state':ash,'primary_interaction_state':(av if dep else False),'top1_value_interaction_state':(av if d1 else False),'top5_value_interaction_state':(av if d5 else False),'top3_share_interaction_state':(ash if dep else False),'shocked_active_partner_ids_value':json.dumps([p for p in x['active'] if value_shock[p] is True]),'shocked_candidate_partner_ids_value':json.dumps([p for p in x['candidates'] if value_shock[p] is True]),'shocked_active_partner_ids_share':json.dumps([p for p in x['active'] if share_shock[p] is True]),'raw_active_partner_values_t':json.dumps({p:raw_t[p] for p in x['active']},sort_keys=True),'raw_active_partner_values_t_minus_1':json.dumps({p:raw_prev[p] for p in x['active']},sort_keys=True),'all_candidate_value_complete':bool(all(v is not None for v in value_shock.values())),'all_candidate_share_complete':bool(all(v is not None for v in share_shock.values()))})
 panel=pd.DataFrame(rows); macro=pd.read_csv(MACRO,usecols=['entity_code','year','wdi__NY.GDP.MKTP.KD.ZG']).rename(columns={'entity_code':'reporter_id','year':'origin_year','wdi__NY.GDP.MKTP.KD.ZG':'gdp_growth'}); macro=macro[macro.reporter_id.isin(REPORTERS)].copy(); macro['origin_year']=pd.to_numeric(macro.origin_year,errors='coerce').astype(int); macro['gdp_growth']=pd.to_numeric(macro.gdp_growth,errors='coerce'); panel=panel.merge(macro,on=['reporter_id','origin_year'],how='left'); macro2=macro.rename(columns={'origin_year':'future_year','gdp_growth':'future_gdp'});
 for h in H:
  fut=macro2.copy(); fut['origin_year']=fut.future_year-h; panel=panel.merge(fut[['reporter_id','origin_year','future_gdp']],on=['reporter_id','origin_year'],how='left'); panel[f'outcome_h{h}']=np.where(panel.future_gdp.notna()&panel.gdp_growth.notna(),(panel.future_gdp<=panel.gdp_growth-2.0).astype(float),np.nan); panel=panel.drop(columns=['future_gdp'])
 split={'fit':(2005,2013),'validation':(2014,2017),'confirmation':(2018,2021)}; variants=['primary_interaction','top1_value_interaction','top5_value_interaction','top3_share_interaction']; metrics=metric_rows(panel,split,variants); pd.DataFrame(metrics).to_csv(OUT/'IMF_IMTS_PARTNER_DEPENDENCE_METRICS_V2.csv',index=False); panel.to_csv(OUT/'IMF_IMTS_PARTNER_DEPENDENCE_REPORTER_YEAR_PANEL_V2.csv',index=False); sel.to_csv(OUT/'IMF_IMTS_PARTNER_SELECTION_REGISTER_V2.csv',index=False)
 # Primary confirmation statistic only; max across horizons was declared in V2.
 cm=pd.DataFrame([x for x in metrics if x['split']=='confirmation' and x['variant']=='primary_interaction']); observed=float(cm.risk_difference.max()) if cm.risk_difference.notna().any() else np.nan; selected_h=int(cm.loc[cm.risk_difference.idxmax(),'horizon']) if cm.risk_difference.notna().any() else None
 # Partner identity null on complete candidate-state confirmation rows, with active labels permuted 5-of-10 per reporter.
 c=panel[(panel.origin_year.between(2018,2021))&panel.all_candidate_value_complete&panel.primary_interaction_state.notna()].copy(); null=[]
 for _ in range(10000):
  pmap={r:set(rng.choice(smap[r]['candidates'],size=5,replace=False).tolist()) for r in REPORTERS}; vals=[]
  for h in H:
   q=c[c[f'outcome_h{h}'].notna()]; x=np.array([bool(smap[r]['top3']>=0.50) and any(p in pmap[r] for p in json.loads(s)) for r,s in zip(q.reporter_id,q.shocked_candidate_partner_ids_value)],dtype=bool); y=q[f'outcome_h{h}'].astype(bool).to_numpy(); vals.append(rd_risk(x,y))
  null.append(np.nanmax(vals) if vals else np.nan)
 null=np.asarray(null); id_p=float((1+np.sum(null>=observed))/(len(null)+1)) if np.isfinite(observed) else None; id_unique=int(np.unique(null[~np.isnan(null)]).size); id_sd=float(np.nanstd(null,ddof=1)) if np.isfinite(null).sum()>1 else None
 # Outcome null, preserving reporter and horizon outcome prevalence.
 onull=[]
 for _ in range(10000):
  vals=[]
  for h in H:
   q=c[c[f'outcome_h{h}'].notna()]; yy=[]; xx=[]
   for r,g in q.groupby('reporter_id'):
    a=g[f'outcome_h{h}'].astype(bool).to_numpy().copy(); rng.shuffle(a); yy.extend(a.tolist()); xx.extend(g.primary_interaction_state.astype(bool).tolist())
   vals.append(rd_risk(xx,yy))
  onull.append(np.nanmax(vals) if vals else np.nan)
 onull=np.asarray(onull); out_p=float((1+np.sum(onull>=observed))/(len(onull)+1)) if np.isfinite(observed) else None
 # Time placebo: shift each reporter-partner value-shock sequence by a random nonzero offset; state prevalence and sequence cyclicity retained.
 placebo=[]; years=list(range(2005,2022))
 for _ in range(5000):
  shifts={(r,p):int(rng.integers(1,len(years))) for r in REPORTERS for p in smap[r]['candidates']}; vals=[]
  for h in H:
   q=panel[panel.origin_year.between(2018,2021)].copy(); xs=[]
   for r,y in zip(q.reporter_id,q.origin_year):
    active=smap[r]['active']; shocked=[]
    for p in active:
     seq=[candidate_state[r][yy]['value'][p] for yy in years]; k=shifts[(r,p)]; idx=(years.index(int(y))-k)%len(years); shocked.append(seq[idx])
    state=True if any(v is True for v in shocked) else (False if shocked and all(v is False for v in shocked) else np.nan); xs.append(state if smap[r]['top3']>=0.50 else False)
   q=q.copy(); q['placebo_state']=xs; z=q[q[f'outcome_h{h}'].notna()&q.placebo_state.notna()]; vals.append(rd_risk(z.placebo_state.astype(bool),z[f'outcome_h{h}'].astype(bool)))
  placebo.append(np.nanmax(vals) if vals else np.nan)
 placebo=np.asarray(placebo); placebo_p=float((1+np.sum(placebo>=observed))/(len(placebo)+1)) if np.isfinite(observed) else None
 # Cluster bootstrap and region leave-one-out confirmation.
 conf=panel[panel.origin_year.between(2018,2021)].copy(); boot=[]; reps=conf.reporter_id.unique().tolist()
 for _ in range(5000):
  chosen=rng.choice(reps,size=len(reps),replace=True); q=pd.concat([conf[conf.reporter_id==r] for r in chosen],ignore_index=True); vals=[]
  for h in H:
   z=q[q[f'outcome_h{h}'].notna()&q.primary_interaction_state.notna()]; vals.append(rd_risk(z.primary_interaction_state.astype(bool),z[f'outcome_h{h}'].astype(bool)))
  boot.append(np.nanmax(vals) if vals else np.nan)
 boot=np.asarray(boot); region_rows=[]
 for reg in sorted(conf.region_id.dropna().unique()):
  hold=conf[conf.region_id!=reg]; n=int(conf[conf.region_id==reg].reporter_id.nunique()); z=hold[(hold.primary_interaction_state.notna())&(hold.outcome_h2.notna())]; region_rows.append({'held_out_region_id':reg,'held_out_region_reporters':n,'remaining_reporters':int(hold.reporter_id.nunique()),'rows':int(len(z)),'risk_difference_h2':rd_risk(z.primary_interaction_state.astype(bool),z.outcome_h2.astype(bool)),'testable':bool(n>=10 and len(z)>=30)})
 region_df=pd.DataFrame(region_rows); region_df.to_csv(OUT/'IMF_IMTS_REGION_HOLDOUT_V2.csv',index=False); stab=[]
 for r,g in conf.groupby('reporter_id'):
  z=g[g.primary_interaction_state.notna()&g.outcome_h2.notna()]; v=rd_risk(z.primary_interaction_state.astype(bool),z.outcome_h2.astype(bool)); stab.append({'reporter_id':r,'region_id':g.region_id.iloc[0],'rows':int(len(z)),'risk_difference_h2':v,'defined':bool(np.isfinite(v)),'positive':bool(np.isfinite(v) and v>0)})
 stabdf=pd.DataFrame(stab); stabdf.to_csv(OUT/'IMF_IMTS_REPORTER_STABILITY_V2.csv',index=False)
 primary_conf=[x for x in metrics if x['split']=='confirmation' and x['variant']=='primary_interaction']; pconf_h2=next((x for x in primary_conf if x['horizon']==2),None); exp_count=int((conf.primary_interaction_state==True).sum()); exp_reporters=int(conf.loc[conf.primary_interaction_state==True,'reporter_id'].nunique()); pos_out=int(conf.outcome_h2.sum()) if conf.outcome_h2.notna().any() else 0; regions_n=int(conf.region_id.nunique()); coverage_pass=bool(exp_count>=10 and exp_reporters>=5 and pos_out>=10 and conf.reporter_id.nunique()>=50 and regions_n>=3); concentration_reporter=float(conf.loc[conf.primary_interaction_state==True,'reporter_id'].value_counts().max()/exp_count) if exp_count else None; shocked=[]
 for s in conf.loc[conf.primary_interaction_state==True,'shocked_active_partner_ids_value']: shocked.extend(json.loads(s))
 concentration_partner=float(Counter(shocked).most_common(1)[0][1]/len(shocked)) if shocked else None; concentration_pass=bool((concentration_reporter is None or concentration_reporter<=0.40) and (concentration_partner is None or concentration_partner<=0.50)); holdout_pass=bool(region_df.testable.sum()>=3); stability_pass=bool(stabdf.defined.sum()>=20 and stabdf[stabdf.defined].positive.mean()>=0.60) if stabdf.defined.any() else False; null_non_degenerate=bool(id_unique>=10 and id_sd is not None and id_sd>0); promotion={'positive_confirmation_stat':bool(np.isfinite(observed) and observed>0),'identity_null_non_degenerate':null_non_degenerate,'identity_null_pass':bool(null_non_degenerate and id_p is not None and id_p<0.025),'outcome_null_pass':bool(out_p is not None and out_p<0.025),'time_placebo_pass':bool(placebo_p is not None and placebo_p<0.025),'coverage_pass':coverage_pass,'stability_pass':stability_pass,'holdout_pass':holdout_pass,'concentration_pass':concentration_pass}; status='supported_predictive' if all(promotion.values()) else ('not_testable_null_degenerate' if not null_non_degenerate else ('not_testable' if not coverage_pass else 'rejected')); summary={'test_id':'IMF_IMTS_PARTNER_DEPENDENCE_V2','contract_id':'IMF_IMTS_PARTNER_DEPENDENCE_CONTRACT_V2','contract_sha256':sha(CONTRACT),'input_sha256':{'observations':sha(OBS),'selection':sha(SEL),'macro':sha(MACRO),'region_raw':sha(REGION_RAW)},'reporters_from_imts':len(REPORTERS),'reporters_with_complete_candidate_pool':int(sel.reporter_id.nunique()),'selection_rows':int(len(sel)),'candidate_pool_size':10,'active_set_size':5,'panel_rows':int(len(panel)),'panel_defined_primary_rows':int(panel.primary_interaction_state.notna().sum()),'metrics':metrics,'confirmation_exposure_rows':exp_count,'confirmation_exposed_reporters':exp_reporters,'confirmation_positive_h2_outcomes':pos_out,'confirmation_regions':regions_n,'observed_confirmation_max_risk_difference':observed,'selected_horizon':selected_h,'identity_null':{'replicates':10000,'p_value':id_p,'null_mean':float(np.nanmean(null)),'null_sd':id_sd,'null_q95':float(np.nanquantile(null,.95)),'unique_statistics':id_unique,'eligible_rows':int(len(c))},'outcome_null':{'replicates':10000,'p_value':out_p,'null_mean':float(np.nanmean(onull)),'null_sd':float(np.nanstd(onull,ddof=1)),'null_q95':float(np.nanquantile(onull,.95)),'eligible_rows':int(len(c))},'time_placebo':{'replicates':5000,'p_value':placebo_p,'null_mean':float(np.nanmean(placebo)),'null_sd':float(np.nanstd(placebo,ddof=1)),'null_q95':float(np.nanquantile(placebo,.95))},'cluster_bootstrap':{'replicates':5000,'mean':float(np.nanmean(boot)),'q025':float(np.nanquantile(boot,.025)),'q975':float(np.nanquantile(boot,.975))},'coverage_pass':coverage_pass,'reporter_stability_pass':stability_pass,'region_holdout_pass':holdout_pass,'concentration':{'max_reporter_share':concentration_reporter,'max_partner_event_share':concentration_partner},'concentration_pass':concentration_pass,'promotion_checks':promotion,'status':status,'causal_claim':False,'runtime_eligible':False,'notes':['V2 uses all reporters with WDI GDP target availability and a complete ten-partner baseline pool; reporters lacking ten candidates remain in the coverage profile but are excluded from the primary test.','Partner selection uses only raw IMTS shares in 2000-2004; GDP outcomes are not used.','G001 World is used only as same-source denominator and is not a named partner.','Partner-level rows are not pooled as independent GDP outcomes.','Missing bilateral values are not zero and produce missing partner states.','V1 baseline and V1 results are preserved and not overwritten.']}; (OUT/'IMF_IMTS_PARTNER_DEPENDENCE_SUMMARY_V2.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); manifest={'run_id':'IMF_IMTS_PARTNER_DEPENDENCE_RUN_V2','executed_at_utc':datetime.now(timezone.utc).isoformat(),'contract_status':contract.get('status'),'contract_sha256':sha(CONTRACT),'tool':'tooling/run_imf_partner_dependence_v2.py','python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'rng_seed':20260827,'status':status,'raw_modified':False,'runtime_eligible':False}; (OUT/'IMF_IMTS_PARTNER_DEPENDENCE_RUN_MANIFEST_V2.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'status':status,'reporters':len(REPORTERS),'panel_rows':len(panel),'selection_rows':len(sel),'confirmation_exposures':exp_count,'confirmation_exposed_reporters':exp_reporters,'confirmation_positive_h2_outcomes':pos_out,'observed_confirmation_max_risk_difference':observed,'selected_horizon':selected_h,'identity_null_p':id_p,'identity_null_sd':id_sd,'identity_null_unique':id_unique,'outcome_null_p':out_p,'time_placebo_p':placebo_p,'coverage_pass':coverage_pass,'stability_pass':stability_pass,'holdout_pass':holdout_pass,'concentration_pass':concentration_pass},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
