#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score
ROOT=Path('/home/ubuntu/CHAOS'); SRC=ROOT/'campaigns/agents/trade_v1/WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv'; OUT=ROOT/'campaigns/agents/trade_v1'; SEED=20260827; REPS=2000; SPLITS={'fit':(2006,2015),'validation':(2016,2019),'confirmation':(2020,2024)}
def metric(y,p):return {'balanced_accuracy':balanced_accuracy_score(y,p),'f1':f1_score(y,p,zero_division=0),'prevalence':float(np.mean(y)),'n':int(len(y))}
def main():
 d=pd.read_csv(SRC); d=d[d['Indicator Code'].eq('NE.TRD.GNFS.ZS')][['Country Code','Country Name','year','value_raw']].drop_duplicates(['Country Code','year']).sort_values(['Country Code','year']); d['prev_year']=d.groupby('Country Code').year.shift(1); d['prev_value']=d.groupby('Country Code').value_raw.shift(1); d['source_squeeze']=(d.year==d.prev_year+1)&(d.value_raw<=d.prev_value-10)
 prepared={}; rows=[]
 for h in (1,2):
  x=d.copy(); x['target_year']=x.year+h; target=d[['Country Code','year','value_raw']].rename(columns={'year':'target_year','value_raw':'target_value'}); x=x.merge(target,on=['Country Code','target_year'],how='left'); x['target_squeeze']=(x.target_year==x.year+h)&(x.target_value<=x.value_raw-10); x=x[x.source_squeeze.notna() & x.target_value.notna()].copy(); prepared[h]=x
  for split,(lo,hi) in SPLITS.items():
   z=x[x.target_year.between(lo,hi)]; y=z.target_squeeze.astype(int).to_numpy(); p=z.source_squeeze.astype(int).to_numpy(); rows.append({'edge_id':'wdi_trade_openness_squeeze_persistence','horizon_years':h,'split':split,**metric(y,p)})
 metrics=pd.DataFrame(rows); metrics.to_csv(OUT/'WDI_TRADE_EDGE_METRICS.csv',index=False)
 rng=np.random.default_rng(SEED); null=[]
 for rep in range(REPS):
  mx=-np.inf
  for h,x in prepared.items():
   for split,(lo,hi) in SPLITS.items():
    z=x[x.target_year.between(lo,hi)].copy().reset_index(drop=True); yp=z.target_squeeze.astype(int).to_numpy(); perm=yp.copy()
    for _,idx in z.groupby('Country Code').groups.items():
     idx=np.asarray(list(idx)); vals=perm[idx].copy(); rng.shuffle(vals); perm[idx]=vals
    pred=z.source_squeeze.astype(int).to_numpy(); mx=max(mx,balanced_accuracy_score(perm,pred))
  null.append({'replicate':rep+1,'max_balanced_accuracy':mx})
 nd=pd.DataFrame(null); nd.to_csv(OUT/'WDI_TRADE_EDGE_MAXSTAT_NULL_REPLICATES.csv',index=False); observed=float(metrics.balanced_accuracy.max()); p=float((1+(nd.max_balanced_accuracy>=observed).sum())/(REPS+1)); summary={'contract_ref':'experimental_contracts/WDI_TRADE_EDGE_CONTRACT_V1.json','source':str(SRC.relative_to(ROOT)),'source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'rows_joined_by_lead':{str(h):int(len(x)) for h,x in prepared.items()},'entities':int(d['Country Code'].nunique()),'observed_max_balanced_accuracy':observed,'maxstat_p_value':p,'replicates':REPS,'seed':SEED,'exact_consecutive_years_required':True,'raw_modified':False,'imputation':False,'source_averaging':False,'causal_claims_permitted':False,'status':'research_evidence_only'}; (OUT/'WDI_TRADE_EDGE_MAXSTAT_NULL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); (OUT/'WDI_TRADE_TRANSITION_EVIDENCE_V1.jsonl').write_text(json.dumps({'transition_id':'WDI_TRADE_OPENNESS_SQUEEZE_PERSISTENCE_V1','source_state':'wdi_trade_openness_squeeze_at_t','target_state':'wdi_trade_openness_squeeze_at_t_plus_h','lag':{'values':[1,2],'unit':'years','direction':'forward'},'split':'fit_validation_confirmation','metric':{'observed_max_balanced_accuracy':observed},'null_method':'within-entity label permutation; 2000 reps; max-stat across leads and splits','p_value':p,'entity_holdout':False,'source_refs':['WDI_TRADE_EDGE_METRICS.csv','WDI_TRADE_EDGE_MAXSTAT_NULL_SUMMARY.json'],'edge_status':'candidate','causal_claim':False,'failure_cases':['aggregate trade openness only','no partner/commodity network','exact consecutive years only']},ensure_ascii=False)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
