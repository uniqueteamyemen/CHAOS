#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,zipfile
import numpy as np,pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score
ROOT=Path('/home/ubuntu/CHAOS'); AMA=ROOT/'catalog_first/readiness_gate/independent_sources/un_ama_2026/staged/UN_AMA_INDEPENDENT_GDP_GROWTH_POPULATION_PANEL.csv'; UZIP=ROOT/'catalog_first/readiness_gate/independent_sources/ucdp_organized_violence_cy_26_1/raw/UCDP_ORGANIZED_VIOLENCE_CY_26_1_RAW.zip'; OUT=ROOT/'experiments/multi_domain_native_edges_v1'; OUT.mkdir(parents=True,exist_ok=True)
SEED=20260826; REPS=2000; SPLITS={'fit':(2006,2015),'validation':(2016,2019),'confirmation':(2020,2024)}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def metric(y,p):return {'balanced_accuracy':balanced_accuracy_score(y,p),'f1':f1_score(y,p,zero_division=0),'prevalence':float(np.mean(y)),'n':int(len(y))}
def main():
 ama=pd.read_csv(AMA); ama=ama[ama.IndicatorName.eq('Gross Domestic Product (GDP)')][['CountryID','Country','year','ama_gdp_growth_pct']].drop_duplicates(['CountryID','year']).copy(); ama['country_id']=ama.CountryID.astype(int)
 with zipfile.ZipFile(UZIP) as zf:
  name=zf.namelist()[0]
  with zf.open(name) as f: u=pd.read_csv(f,usecols=['country_id','year','sb_exist'])
 u['country_id']=u.country_id.astype(int); u['future_conflict']=u.sb_exist.astype(int).eq(1); u=u[['country_id','year','future_conflict']].drop_duplicates(['country_id','year'])
 d=ama.merge(u,on=['country_id','year'],how='inner').sort_values(['country_id','year']); d['prev_growth']=d.groupby('country_id').ama_gdp_growth_pct.shift(1); d['economic_deterioration']=d.ama_gdp_growth_pct<=d.prev_growth-2.0
 rows=[]; prepared={}
 for h in (1,2,3):
  target=u.rename(columns={'year':'target_year','future_conflict':'target_conflict'}).copy(); x=d.copy(); x['target_year']=x.year+h; x=x.merge(target,on=['country_id','target_year'],how='left'); x=x[x.prev_growth.notna() & x.target_conflict.notna()].copy(); prepared[h]=x
  for split,(lo,hi) in SPLITS.items():
   z=x[x.target_year.between(lo,hi)]; y=z.target_conflict.astype(int).to_numpy(); p=z.economic_deterioration.astype(int).to_numpy(); rows.append({'edge_id':'economic_deterioration_to_conflict','horizon_years':h,'split':split,**metric(y,p)})
 metrics=pd.DataFrame(rows); metrics.to_csv(OUT/'ECONOMIC_DETERIORATION_TO_CONFLICT_METRICS.csv',index=False)
 rng=np.random.default_rng(SEED); null=[]
 for rep in range(REPS):
  mx=-np.inf
  for h,x in prepared.items():
   for split,(lo,hi) in SPLITS.items():
    z=x[x.target_year.between(lo,hi)].copy().reset_index(drop=True); yp=z.target_conflict.astype(int).to_numpy(); perm=yp.copy()
    for _,idx in z.groupby('country_id').groups.items():
     idx=np.asarray(list(idx)); vals=perm[idx].copy(); rng.shuffle(vals); perm[idx]=vals
    pred=z.economic_deterioration.astype(int).to_numpy(); mx=max(mx,balanced_accuracy_score(perm,pred))
  null.append({'replicate':rep+1,'max_balanced_accuracy':mx})
 nd=pd.DataFrame(null); nd.to_csv(OUT/'ECONOMIC_DETERIORATION_TO_CONFLICT_MAXSTAT_NULL_REPLICATES.csv',index=False); observed=float(metrics.balanced_accuracy.max()); p=float((1+(nd.max_balanced_accuracy>=observed).sum())/(REPS+1)); summary={'contract_ref':'experimental_contracts/ECONOMIC_DETERIORATION_TO_CONFLICT_CONTRACT_V1.json','ama_source':str(AMA.relative_to(ROOT)),'ucdp_source':str(UZIP.relative_to(ROOT)),'ama_sha256':sha(AMA),'ucdp_sha256':sha(UZIP),'joined_rows':int(len(d)),'joined_entities':int(d.country_id.nunique()),'joined_years':[int(d.year.min()),int(d.year.max())],'replicates':REPS,'seed':SEED,'observed_max_balanced_accuracy':observed,'maxstat_p_value':p,'native_frequency':'annual','raw_data_modified':False,'imputation':False,'deduplicated_country_year':True,'causal_claims_permitted':False,'status':'research_evidence_only'}; (OUT/'ECONOMIC_DETERIORATION_TO_CONFLICT_MAXSTAT_NULL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
