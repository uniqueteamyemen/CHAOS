#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score
ROOT=Path('/home/ubuntu/CHAOS'); T=ROOT/'campaigns/agents/trade_v1/WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv'; M=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'; OUT=ROOT/'campaigns/agents/trade_v1'; SEED=20260827; REPS=2000; SPLITS={'fit':(2006,2015),'validation':(2016,2019),'confirmation':(2020,2024)}
def metric(y,p):return {'balanced_accuracy':balanced_accuracy_score(y,p),'f1':f1_score(y,p,zero_division=0),'prevalence':float(np.mean(y)),'n':int(len(y))}
def main():
 t=pd.read_csv(T); t=t[t['Indicator Code'].eq('NE.TRD.GNFS.ZS')][['Country Code','year','value_raw']].drop_duplicates(['Country Code','year']).sort_values(['Country Code','year']); t['prev_year']=t.groupby('Country Code').year.shift(1); t['prev_value']=t.groupby('Country Code').value_raw.shift(1); t['trade_squeeze']=(t.year==t.prev_year+1)&(t.value_raw<=t.prev_value-10)
 m=pd.read_csv(M); m=m[['entity_code','year','wdi__NY.GDP.MKTP.KD.ZG']].rename(columns={'entity_code':'Country Code','wdi__NY.GDP.MKTP.KD.ZG':'gdp_growth'}); d=t.merge(m,on=['Country Code','year'],how='inner').sort_values(['Country Code','year']); prepared={}; rows=[]
 for h in (1,2,3):
  target=m.rename(columns={'year':'target_year','gdp_growth':'target_gdp_growth'}); x=d.copy(); x['target_year']=x.year+h; x=x.merge(target,on=['Country Code','target_year'],how='left'); x['target_deterioration']=x.target_gdp_growth<=x.gdp_growth-2; x=x[x.trade_squeeze.notna() & x.target_gdp_growth.notna()].copy(); prepared[h]=x
  for split,(lo,hi) in SPLITS.items():
   z=x[x.target_year.between(lo,hi)]; y=z.target_deterioration.astype(int).to_numpy(); p=z.trade_squeeze.astype(int).to_numpy(); rows.append({'edge_id':'wdi_trade_squeeze_to_material_gdp_deterioration','horizon_years':h,'split':split,**metric(y,p)})
 metrics=pd.DataFrame(rows); metrics.to_csv(OUT/'WDI_TRADE_TO_ECONOMIC_DETERIORATION_METRICS.csv',index=False)
 rng=np.random.default_rng(SEED); null=[]
 for rep in range(REPS):
  mx=-np.inf
  for h,x in prepared.items():
   for split,(lo,hi) in SPLITS.items():
    z=x[x.target_year.between(lo,hi)].copy().reset_index(drop=True); yp=z.target_deterioration.astype(int).to_numpy(); perm=yp.copy()
    for _,idx in z.groupby('Country Code').groups.items():
     idx=np.asarray(list(idx)); vals=perm[idx].copy(); rng.shuffle(vals); perm[idx]=vals
    pred=z.trade_squeeze.astype(int).to_numpy(); mx=max(mx,balanced_accuracy_score(perm,pred))
  null.append({'replicate':rep+1,'max_balanced_accuracy':mx})
 nd=pd.DataFrame(null); nd.to_csv(OUT/'WDI_TRADE_TO_ECONOMIC_DETERIORATION_MAXSTAT_NULL_REPLICATES.csv',index=False); observed=float(metrics.balanced_accuracy.max()); p=float((1+(nd.max_balanced_accuracy>=observed).sum())/(REPS+1)); summary={'contract_ref':'experimental_contracts/WDI_TRADE_TO_ECONOMIC_DETERIORATION_CONTRACT_V1.json','trade_source':str(T.relative_to(ROOT)),'macro_source':str(M.relative_to(ROOT)),'trade_sha256':hashlib.sha256(T.read_bytes()).hexdigest(),'macro_sha256':hashlib.sha256(M.read_bytes()).hexdigest(),'rows_joined_by_horizon':{str(h):int(len(x)) for h,x in prepared.items()},'entities':int(d['Country Code'].nunique()),'observed_max_balanced_accuracy':observed,'maxstat_p_value':p,'replicates':REPS,'seed':SEED,'native_frequency':'annual','raw_modified':False,'imputation':False,'source_averaging':False,'causal_claims_permitted':False,'status':'research_evidence_only'}; (OUT/'WDI_TRADE_TO_ECONOMIC_DETERIORATION_MAXSTAT_NULL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); (OUT/'WDI_TRADE_TO_ECONOMIC_DETERIORATION_TRANSITION_EVIDENCE_V1.jsonl').write_text(json.dumps({'transition_id':'WDI_TRADE_SQUEEZE_TO_MATERIAL_GDP_DETERIORATION_V1','source_state':'wdi_trade_openness_squeeze_at_t','target_state':'material_gdp_deterioration_at_t_plus_h','lag':{'values':[1,2,3],'unit':'years','direction':'forward'},'split':'fit_validation_confirmation','metric':{'observed_max_balanced_accuracy':observed},'null_method':'within-entity target-label permutation; 2000 reps; max-stat across horizons and splits','p_value':p,'entity_holdout':False,'source_refs':['WDI_TRADE_TO_ECONOMIC_DETERIORATION_METRICS.csv','WDI_TRADE_TO_ECONOMIC_DETERIORATION_MAXSTAT_NULL_SUMMARY.json'],'edge_status':'candidate','causal_claim':False,'failure_cases':['trade openness is aggregate indicator','inner join only','no partner/commodity mechanism inferred']},ensure_ascii=False)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
