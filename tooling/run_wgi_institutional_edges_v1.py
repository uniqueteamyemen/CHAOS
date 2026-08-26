#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,zipfile
import numpy as np,pandas as pd
from sklearn.metrics import balanced_accuracy_score,f1_score
ROOT=Path('/home/ubuntu/CHAOS'); ZIP=ROOT/'catalog_first/readiness_gate/independent_sources/worldbank_wgi_2025/raw/WGI_CSV.zip'; OUT=ROOT/'campaigns/agents/institutions_policy_v1'; OUT.mkdir(parents=True,exist_ok=True)
SEED=20260827; REPS=2000; SPLITS={'fit':(2006,2015),'validation':(2016,2019),'confirmation':(2020,2024)}; DIMS=['GOV_WGI_VA.EST','GOV_WGI_PS.EST','GOV_WGI_GE.EST','GOV_WGI_RQ.EST','GOV_WGI_RL.EST','GOV_WGI_CC.EST']
def metric(y,p):return {'balanced_accuracy':balanced_accuracy_score(y,p),'f1':f1_score(y,p,zero_division=0),'prevalence':float(np.mean(y)),'n':int(len(y))}
def main():
 with zipfile.ZipFile(ZIP) as zf:
  with zf.open('WGICSV.csv') as f: wide=pd.read_csv(f)
 wide=wide[wide['Indicator Code'].isin(DIMS)].copy(); years=[c for c in wide.columns if str(c).isdigit()]
 long=wide.melt(id_vars=['Country Name','Country Code','Indicator Code'],value_vars=years,var_name='year',value_name='value'); long['year']=long.year.astype(int); long['value']=pd.to_numeric(long.value,errors='coerce'); long=long.dropna(subset=['value']).sort_values(['Indicator Code','Country Code','year'])
 rows=[]; prepared={}
 for dim,g in long.groupby('Indicator Code'):
  g=g.copy(); g['prev']=g.groupby('Country Code').value.shift(1); g['next_year_1']=g.groupby('Country Code').year.shift(-1); g['next_value_1']=g.groupby('Country Code').value.shift(-1); g['next_year_2']=g.groupby('Country Code').year.shift(-2); g['next_value_2']=g.groupby('Country Code').value.shift(-2); g['decline_source']=g.value<=g.prev-0.5; g['continuity_source']=(g.value-g.prev).abs()<=0.25
  for edge,source_col,rule in [('institutional_decline_persistence','decline_source','decline'),('institutional_continuity_persistence','continuity_source','continuity')]:
   for lead in (1,2):
    x=g.copy(); x['target_year']=x[f'next_year_{lead}']; x['target_value']=x[f'next_value_{lead}']; x['target_decline']=x.target_value<=x.value-0.5; x['target_continuity']=(x.target_value-x.value).abs()<=0.25; target_col='target_decline' if rule=='decline' else 'target_continuity'; x=x[x.prev.notna() & x.target_value.notna() & x[target_col].notna()].copy(); x['source_pred']=x[source_col].astype(bool); x['target_label']=x[target_col].astype(bool); prepared[(dim,edge,lead)]=x
    for split,(lo,hi) in SPLITS.items():
     z=x[x.target_year.between(lo,hi)]; y=z.target_label.astype(int).to_numpy(); p=z.source_pred.astype(int).to_numpy(); rows.append({'dimension':dim,'edge_id':edge,'lead_steps':lead,'split':split,'source_rule':rule,**metric(y,p)})
 metrics=pd.DataFrame(rows); metrics.to_csv(OUT/'WGI_INSTITUTIONAL_EDGE_METRICS.csv',index=False)
 rng=np.random.default_rng(SEED); null=[]
 for rep in range(REPS):
  mx=-np.inf
  for (dim,edge,lead),x in prepared.items():
   for split,(lo,hi) in SPLITS.items():
    z=x[x.target_year.between(lo,hi)].copy().reset_index(drop=True); yp=z.target_label.astype(int).to_numpy(); perm=yp.copy()
    for _,idx in z.groupby('Country Code').groups.items():
     idx=np.asarray(list(idx)); vals=perm[idx].copy(); rng.shuffle(vals); perm[idx]=vals
    pred=z.source_pred.astype(int).to_numpy(); mx=max(mx,balanced_accuracy_score(perm,pred))
  null.append({'replicate':rep+1,'max_balanced_accuracy':mx})
 nd=pd.DataFrame(null); nd.to_csv(OUT/'WGI_INSTITUTIONAL_EDGE_MAXSTAT_NULL_REPLICATES.csv',index=False); observed=float(metrics.balanced_accuracy.max()); p=float((1+(nd.max_balanced_accuracy>=observed).sum())/(REPS+1)); summary={'contract_ref':'experimental_contracts/WGI_INSTITUTIONAL_EDGE_CONTRACT_V1.json','source_raw':str(ZIP.relative_to(ROOT)),'source_sha256':hashlib.sha256(ZIP.read_bytes()).hexdigest(),'dimensions':DIMS,'metrics_rows':len(metrics),'prepared_edge_combinations':len(prepared),'replicates':REPS,'seed':SEED,'observed_max_balanced_accuracy':observed,'maxstat_p_value':p,'raw_data_modified':False,'imputation':False,'policy_shock_inferred':False,'leader_specific_deviation_inferred':False,'native_frequency':'annual_source_defined_years','causal_claims_permitted':False,'status':'research_evidence_only'}; (OUT/'WGI_INSTITUTIONAL_EDGE_MAXSTAT_NULL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
