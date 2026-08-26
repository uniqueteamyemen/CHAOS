#!/usr/bin/env python3
from pathlib import Path
import json,pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); WGI=ROOT/'campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_DOMAIN_STATES_ANNUAL_SOURCE_YEARS_V1.jsonl'; PMR=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/OECD_PMR_DOMAIN_STATES_SOURCE_WAVES_V1.jsonl'; OUT=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH'
def read(p):return pd.DataFrame([{'entity_id':x['entity_id'],'year':x['timestamp'],'indicator_id':x['source_observations']['indicator_id'],'value':x['source_observations']['value_raw']} for line in p.open() if (x:=json.loads(line))])
def main():
 w=read(WGI); p=read(PMR); rq=w[w.indicator_id.eq('GOV_WGI_RQ.EST')]; ge=w[w.indicator_id.eq('GOV_WGI_GE.EST')]; pm=p[p.indicator_id.isin(['PMR','TRD','BTI','BTE','TRF'])]; rows=[]
 for wi,wname in [(rq,'wgi_regulatory_quality'),(ge,'wgi_government_effectiveness')]:
  for pi in sorted(pm.indicator_id.unique()):
   a=wi.merge(pm[pm.indicator_id.eq(pi)],on=['entity_id','year'],suffixes=('_wgi','_pmr')).dropna()
   if len(a)>=3: rows.append({'wgi_indicator':wname,'pmr_indicator':pi,'overlap_rows':len(a),'overlap_entities':a.entity_id.nunique(),'overlap_years':sorted(a.year.unique().tolist()),'pearson':a.value_wgi.corr(a.value_pmr),'spearman':a.value_wgi.corr(a.value_pmr,method='spearman'),'interpretation':'source_concordance_only_not_edge'})
 out={'comparison_id':'WGI_PMR_SOURCE_COMPARISON_V1','wgi_rows':len(w),'pmr_rows':len(p),'comparisons':rows,'rules':{'exact_entity_year_join_only':True,'no_interpolation':True,'no_composite':True,'no_causal_claim':True},'status':'descriptive_source_comparison'}; (OUT/'WGI_PMR_SOURCE_COMPARISON_V1.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
