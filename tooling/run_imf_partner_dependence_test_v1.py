#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, platform
from collections import Counter
import numpy as np
import pandas as pd

ROOT=Path('/home/ubuntu/CHAOS')
CONTRACT=ROOT/'experimental_contracts/IMF_IMTS_DOMINANT_PARTNER_DEPENDENCE_CONTRACT_V1.json'
TRADE=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v1/IMF_IMTS_OBSERVED_RECORDS_2000_2024.csv'
MACRO=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
CODELIST=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_CODELISTS_V1.json'
OUT=ROOT/'experiments/multi_domain_native_edges_v1/imf_partner_dependence_v1'; OUT.mkdir(parents=True,exist_ok=True)
RNG=np.random.default_rng(20260827)
HORIZONS=[1,2,3]
EXCLUDE_TERMS=['world','not specified','unspecified','special categories','countries & areas','other countries','all countries','regional aggregate','region','group','union','area not elsewhere included','oil related aggregate','services aggregate']
REPORTERS=['USA','CHN','DEU','JPN','IND','GBR','FRA','ITA','CAN','KOR','BRA','MEX','SAU','TUR','ZAF']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load_names():
 d=json.loads(CODELIST.read_text())
 for c in d['codelists']:
  if c['id']=='CL_IMTS_COUNTRY': return {x['id']:x.get('names',{}).get('en') or x.get('name') or x['id'] for x in c['codes']}
 raise RuntimeError('CL_IMTS_COUNTRY missing')
def excluded(code,name,reporter):
 s=f'{code} {name}'.lower()
 return code=='G001' or code==reporter or any(term in s for term in EXCLUDE_TERMS)
def risk_diff(x,y):
 x=np.asarray(x,dtype=bool); y=np.asarray(y,dtype=bool)
 if x.sum()==0 or (~x).sum()==0: return np.nan
 return float(y[x].mean()-y[~x].mean())
def metrics_for(df, split, lo, hi, exposure_col='interaction_state'):
 z=df[df.origin_year.between(lo,hi)].copy(); out=[]
 for h in HORIZONS:
  q=z[z[f'outcome_h{h}'].notna() & z[exposure_col].notna()].copy()
  y=q[f'outcome_h{h}'].astype(bool).to_numpy(); x=q[exposure_col].astype(bool).to_numpy()
  out.append({'split':split,'horizon':h,'rows':int(len(q)),'reporters':int(q.reporter_id.nunique()),'positive_exposures':int(x.sum()),'positive_outcomes':int(y.sum()),'exposed_outcomes':int(y[x].sum()) if x.sum() else 0,'unexposed_outcomes':int(y[~x].sum()) if (~x).sum() else 0,'event_rate_exposed':float(y[x].mean()) if x.sum() else None,'event_rate_unexposed':float(y[~x].mean()) if (~x).sum() else None,'risk_difference':risk_diff(x,y)})
 return out
def main():
 contract=json.loads(CONTRACT.read_text()); names=load_names()
 tr=pd.read_csv(TRADE,low_memory=False); tr=tr[(tr.indicator=='XG_FOB_USD')&(tr.frequency=='A')].copy(); tr['year']=pd.to_numeric(tr.time_period,errors='coerce').astype('Int64'); tr['raw_value']=pd.to_numeric(tr.obs_value_raw,errors='coerce'); tr=tr.dropna(subset=['country','counterpart_country','year','raw_value']); tr=tr[tr.country.isin(REPORTERS)].copy(); tr['partner_name']=tr.counterpart_country.map(names).fillna(tr.counterpart_country); tr=tr[~tr.apply(lambda r: excluded(str(r.counterpart_country),str(r.partner_name),str(r.country)),axis=1)].copy()
 if len(tr)==0: raise RuntimeError('no eligible IMTS rows')
 # retain world denominator separately, without treating World as named partner
 world=pd.read_csv(TRADE,low_memory=False); world=world[(world.indicator=='XG_FOB_USD')&(world.frequency=='A')&(world.counterpart_country=='G001')&(world.country.isin(REPORTERS))].copy(); world['year']=pd.to_numeric(world.time_period,errors='coerce').astype('Int64'); world['raw_value']=pd.to_numeric(world.obs_value_raw,errors='coerce'); world=world.dropna(subset=['country','year','raw_value'])[['country','year','raw_value']].rename(columns={'country':'reporter_id','raw_value':'world_exports_raw'}); world=world.drop_duplicates(['reporter_id','year'])
 bilateral=tr[['country','counterpart_country','partner_name','year','raw_value']].rename(columns={'country':'reporter_id','raw_value':'bilateral_exports_raw'}).drop_duplicates(['reporter_id','counterpart_country','year'])
 sel=[]; selected_map={}; dominant_map={}
 for rep in REPORTERS:
  w=world[world.reporter_id==rep].set_index('year').world_exports_raw
  rows=[]
  for p,g in bilateral[bilateral.reporter_id==rep].groupby(['counterpart_country','partner_name']):
   code,name=p; vals=g.set_index('year').bilateral_exports_raw
   yrs=[y for y in range(2000,2005) if y in vals.index and y in w.index and vals.loc[y] is not None and w.loc[y] is not None]
   if len(yrs)!=5: continue
   shares=[float(vals.loc[y]/w.loc[y]) for y in yrs]
   rows.append({'reporter_id':rep,'partner_id':code,'partner_name':name,'baseline_years':5,'baseline_mean_share':float(np.mean(shares)),'baseline_shares':json.dumps({str(y):shares[i] for i,y in enumerate(yrs)},sort_keys=True)})
  q=pd.DataFrame(rows).sort_values(['baseline_mean_share','partner_id'],ascending=[False,True]) if rows else pd.DataFrame(columns=['reporter_id','partner_id','partner_name','baseline_years','baseline_mean_share','baseline_shares'])
  q=q.head(5).copy(); q['selected_rank']=range(1,len(q)+1); q['baseline_dominant'] = q.baseline_mean_share>=0.20; sel.append(q); selected_map[rep]=q.partner_id.tolist(); dominant_map[rep]=q.loc[q.baseline_dominant,'partner_id'].tolist()
 selection=pd.concat(sel,ignore_index=True) if sel else pd.DataFrame(); selection.to_csv(OUT/'IMF_IMTS_PARTNER_SELECTION_PROFILE_V1.csv',index=False)
 panel=[]
 for rep in REPORTERS:
  q=selection[selection.reporter_id==rep]; dom=q[q.baseline_dominant].partner_id.tolist(); chosen=q.partner_id.tolist();
  for year in range(2005,2022):
   shocked=[]; shocked_all=[]; valid_flags=[]; raw_t={}; raw_prev={}; raw_all_t={}; raw_all_prev={}; all_valid_flags=[]
   for p in chosen:
    a=bilateral[(bilateral.reporter_id==rep)&(bilateral.counterpart_country==p)&(bilateral.year==year)].bilateral_exports_raw.tolist(); b=bilateral[(bilateral.reporter_id==rep)&(bilateral.counterpart_country==p)&(bilateral.year==year-1)].bilateral_exports_raw.tolist();
    if len(a)==1 and len(b)==1 and a[0]>0 and b[0]>0:
     raw_all_t[p]=float(a[0]); raw_all_prev[p]=float(b[0]); all_valid_flags.append(True); is_shock=bool(a[0] < 0.70*b[0]);
     if is_shock: shocked_all.append(p)
     if p in dom: raw_t[p]=float(a[0]); raw_prev[p]=float(b[0]); valid_flags.append(True); shocked.append(p) if is_shock else None
    else:
     all_valid_flags.append(False)
     if p in dom: valid_flags.append(False)
   exposure = True if shocked else (False if dom and all(valid_flags) else np.nan)
   interaction = exposure if dom else np.nan
   panel.append({'reporter_id':rep,'origin_year':year,'selected_partner_ids':json.dumps(chosen),'baseline_dominant_partner_ids':json.dumps(dom),'shocked_partner_ids':json.dumps(shocked),'shocked_selected_partner_ids_all':json.dumps(shocked_all),'shocked_partner_count':len(shocked),'shocked_selected_partner_count_all':len(shocked_all),'raw_dominant_partner_values_t':json.dumps(raw_t,sort_keys=True),'raw_dominant_partner_values_t_minus_1':json.dumps(raw_prev,sort_keys=True),'raw_selected_partner_values_t':json.dumps(raw_all_t,sort_keys=True),'raw_selected_partner_values_t_minus_1':json.dumps(raw_all_prev,sort_keys=True),'dominant_partner_count':len(dom),'selected_partner_validity_complete':bool(all_valid_flags and all(all_valid_flags)),'any_baseline_dominant_partner_flow_contraction':exposure,'dependence_state':bool(dom) if dom else False,'interaction_state':interaction})
 panel=pd.DataFrame(panel); panel['year']=panel['origin_year']; m=pd.read_csv(MACRO,usecols=['entity_code','year','wdi__NY.GDP.MKTP.KD.ZG']).rename(columns={'entity_code':'reporter_id','wdi__NY.GDP.MKTP.KD.ZG':'gdp_growth'}); m['year']=pd.to_numeric(m.year,errors='coerce').astype('Int64'); m['gdp_growth']=pd.to_numeric(m.gdp_growth,errors='coerce'); panel=panel.merge(m,on=['reporter_id','year'],how='left'); panel['origin_year']=panel.origin_year.astype(int); panel=panel.sort_values(['reporter_id','origin_year']).reset_index(drop=True)
 for h in HORIZONS:
  fut=m.rename(columns={'year':'future_year','gdp_growth':f'gdp_growth_h{h}'}); panel=panel.merge(fut.assign(origin_year=fut.future_year-h).drop(columns=['future_year']),on=['reporter_id','origin_year'],how='left'); panel[f'outcome_h{h}']=np.where(panel[f'gdp_growth_h{h}'].notna()&panel.gdp_growth.notna(),(panel[f'gdp_growth_h{h}']<=panel.gdp_growth-2.0).astype(float),np.nan)
 outcols=['reporter_id','origin_year','selected_partner_ids','baseline_dominant_partner_ids','shocked_partner_ids','shocked_partner_count','raw_dominant_partner_values_t','raw_dominant_partner_values_t_minus_1','raw_selected_partner_values_t','raw_selected_partner_values_t_minus_1','shocked_selected_partner_ids_all','shocked_partner_count','shocked_selected_partner_count_all','dominant_partner_count','any_baseline_dominant_partner_flow_contraction','dependence_state','interaction_state','gdp_growth']+[f'gdp_growth_h{h}' for h in HORIZONS]+[f'outcome_h{h}' for h in HORIZONS]; panel[outcols].to_csv(OUT/'IMF_IMTS_PARTNER_DEPENDENCE_REPORTER_YEAR_PANEL_V1.csv',index=False)
 all_metrics=metrics_for(panel,'fit',2005,2013)+metrics_for(panel,'validation',2014,2018)+metrics_for(panel,'confirmation',2019,2021); pd.DataFrame(all_metrics).to_csv(OUT/'IMF_IMTS_PARTNER_DEPENDENCE_METRICS_V1.csv',index=False)
 # primary confirmation max statistic
 cm=pd.DataFrame([x for x in all_metrics if x['split']=='confirmation']); observed=float(cm.risk_difference.max()) if cm.risk_difference.notna().any() else np.nan; selected_h=int(cm.loc[cm.risk_difference.idxmax(),'horizon']) if cm.risk_difference.notna().any() else None
 # partner identity null: fixed within-reporter reassignment of dominant slots
 c=panel[panel.origin_year.between(2019,2021)].copy(); id_null=[]
 for _ in range(10000):
  xmap={}
  for rep in REPORTERS:
   q=selection[selection.reporter_id==rep]; allp=q.partner_id.tolist(); mdom=int(q.baseline_dominant.sum()); perm=RNG.permutation(allp)[:mdom] if mdom else []; xmap[rep]=set(perm)
  vals=[]
  for h in HORIZONS:
   q=c[c[f'outcome_h{h}'].notna()&c.interaction_state.notna()].copy(); x=np.array([bool(xmap[r]) and any(p in xmap[r] for p in json.loads(s)) for r,s in zip(q.reporter_id,q.shocked_selected_partner_ids_all)],dtype=bool); y=q[f'outcome_h{h}'].astype(bool).to_numpy(); vals.append(risk_diff(x,y))
  id_null.append(np.nanmax(vals) if vals else np.nan)
 id_null=np.asarray(id_null); id_p=float((1+np.sum(id_null>=observed))/(len(id_null)+1)) if np.isfinite(observed) else None
 # outcome null, fixed exposure and reporter-preserving labels
 out_null=[]
 for _ in range(10000):
  vals=[]
  for h in HORIZONS:
   q=c[c[f'outcome_h{h}'].notna()&c.interaction_state.notna()].copy(); ys=[]; xs=[]
   for rep,g in q.groupby('reporter_id'):
    a=g[f'outcome_h{h}'].astype(bool).to_numpy().copy(); RNG.shuffle(a); ys.extend(a.tolist()); xs.extend(g.interaction_state.astype(bool).tolist())
   vals.append(risk_diff(xs,ys))
  out_null.append(np.nanmax(vals) if vals else np.nan)
 out_null=np.asarray(out_null); out_p=float((1+np.sum(out_null>=observed))/(len(out_null)+1)) if np.isfinite(observed) else None
 # cluster bootstrap on confirmation max statistic
 reps=[]; base=c.reporter_id.unique().tolist()
 for _ in range(5000):
  chosen=RNG.choice(base,size=len(base),replace=True); pieces=[c[c.reporter_id==r] for r in chosen]; q=pd.concat(pieces,ignore_index=True) if pieces else c.iloc[0:0]; vals=[]
  for h in HORIZONS:
   z=q[q[f'outcome_h{h}'].notna()&q.interaction_state.notna()]; vals.append(risk_diff(z.interaction_state.astype(bool),z[f'outcome_h{h}'].astype(bool)))
  reps.append(np.nanmax(vals) if vals else np.nan)
 reps=np.asarray(reps)
 positive_exposure=panel[panel.interaction_state==True]; reporter_counts=positive_exposure.reporter_id.value_counts(); partner_counts=Counter()
 for s in positive_exposure.shocked_partner_ids: 
  for p in json.loads(s): partner_counts[p]+=1
 total_partner_events=sum(partner_counts.values()); concentration={'max_reporter_share':float(reporter_counts.max()/len(positive_exposure)) if len(positive_exposure) else None,'max_partner_event_share':float(max(partner_counts.values())/total_partner_events) if total_partner_events else None,'max_reporter':reporter_counts.idxmax() if len(reporter_counts) else None,'max_partner':max(partner_counts,key=partner_counts.get) if partner_counts else None}
 confirmation=[x for x in all_metrics if x['split']=='confirmation']; coverage_pass=all(x['positive_exposures']>=5 and x['positive_outcomes']>=5 and x['reporters']>=10 and x['rows']>=30 for x in confirmation); stability_rows=[]
 for rep,g in c.groupby('reporter_id'):
  vals=[]
  for h in HORIZONS:
   z=g[g[f'outcome_h{h}'].notna()&g.interaction_state.notna()]; vals.append(risk_diff(z.interaction_state.astype(bool),z[f'outcome_h{h}'].astype(bool)))
  v=np.nanmax(vals) if vals else np.nan; stability_rows.append({'reporter_id':rep,'confirmation_max_risk_difference':v,'defined':bool(np.isfinite(v)),'positive':bool(np.isfinite(v) and v>0)})
 stability=pd.DataFrame(stability_rows); stability.to_csv(OUT/'IMF_IMTS_PARTNER_DEPENDENCE_REPORTER_STABILITY_V1.csv',index=False); stability_pass=int(stability.defined.sum())>=10 and float(stability[stability.defined].positive.mean())>=0.60 if stability.defined.any() else False
 summ={'test_id':'IMF_IMTS_DOMINANT_PARTNER_DEPENDENCE_V1','contract_status_at_run':contract.get('status'),'contract_sha256':sha(CONTRACT),'input_sha256':{'trade_observation_artifact':sha(TRADE),'macro_target_artifact':sha(MACRO),'codelists':sha(CODELIST)},'reporters':REPORTERS,'selection_window':[2000,2004],'origin_period':[2005,2021],'splits':{'fit':[2005,2013],'validation':[2014,2018],'confirmation':[2019,2021]},'selected_partner_count':5,'eligible_selected_rows':int(len(selection)),'reporters_with_five_selected_partners':int((selection.groupby('reporter_id').size()==5).sum()),'reporters_with_dominant_partner':int(sum(bool(x) for x in dominant_map.values())),'total_panel_rows':int(len(panel)),'panel_rows_with_defined_interaction':int(panel.interaction_state.notna().sum()),'metrics':all_metrics,'observed_confirmation_max_risk_difference':observed,'selected_horizon':selected_h,'identity_null':{'replicates':10000,'seed':20260827,'p_value':id_p,'null_mean':float(np.nanmean(id_null)),'null_sd':float(np.nanstd(id_null,ddof=1)),'null_q95':float(np.nanquantile(id_null,.95))},'outcome_null':{'replicates':10000,'seed':20260827,'p_value':out_p,'null_mean':float(np.nanmean(out_null)),'null_sd':float(np.nanstd(out_null,ddof=1)),'null_q95':float(np.nanquantile(out_null,.95))},'cluster_bootstrap':{'replicates':5000,'seed':20260827,'mean':float(np.nanmean(reps)),'q025':float(np.nanquantile(reps,.025)),'q975':float(np.nanquantile(reps,.975))},'concentration':concentration,'coverage_pass':coverage_pass,'reporter_stability_pass':stability_pass,'promotion_checks':{'positive_confirmation_stat':bool(np.isfinite(observed) and observed>0),'identity_null_pass':bool(id_p is not None and id_p<0.025),'outcome_null_pass':bool(out_p is not None and out_p<0.025),'coverage_pass':coverage_pass,'stability_pass':stability_pass,'concentration_pass':bool((concentration['max_reporter_share'] is None or concentration['max_reporter_share']<=0.40) and (concentration['max_partner_event_share'] is None or concentration['max_partner_event_share']<=0.60))},'status':'supported_predictive' if np.isfinite(observed) and observed>0 and id_p is not None and id_p<0.025 and out_p is not None and out_p<0.025 and coverage_pass and stability_pass and summ['promotion_checks']['concentration_pass'] else ('not_testable' if not coverage_pass else 'rejected'),'causal_claim':False,'runtime_eligible':False,'notes':['No partner selection used GDP outcomes or confirmation data.','G001 World used only as denominator, not as named partner.','Partner-level rows are not pooled as independent GDP outcomes.','Missing bilateral observations were not converted to zero.','This is a new source-separated edge test; previous IMF total-export contraction edge was not rerun.']}; (OUT/'IMF_IMTS_PARTNER_DEPENDENCE_SUMMARY_V1.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2)+'\n'); manifest={'run_id':'IMF_IMTS_DOMINANT_PARTNER_DEPENDENCE_RUN_V1','executed_at_utc':datetime.now(timezone.utc).isoformat(),'contract_path':str(CONTRACT.relative_to(ROOT)),'contract_sha256':sha(CONTRACT),'tool':'tooling/run_imf_partner_dependence_test_v1.py','python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'rng_seed':20260827,'raw_modified':False,'status':summ['status']}; (OUT/'IMF_IMTS_PARTNER_DEPENDENCE_RUN_MANIFEST_V1.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'status':summ['status'],'observed_confirmation_max_risk_difference':observed,'selected_horizon':selected_h,'identity_null_p':id_p,'outcome_null_p':out_p,'coverage_pass':coverage_pass,'stability_pass':stability_pass,'concentration':concentration,'selected_rows':len(selection),'panel_rows':len(panel)},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
