#!/usr/bin/env python3
from pathlib import Path
import json,pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/multi_domain_native_edges_v1/imf_partner_dependence_v1'; s=json.loads((OUT/'IMF_IMTS_PARTNER_DEPENDENCE_SUMMARY_V1.json').read_text());
# The selection profile is already the frozen selection audit output.
sel=pd.read_csv(OUT/'IMF_IMTS_PARTNER_SELECTION_PROFILE_V1.csv'); sel.to_csv(OUT/'IMF_IMTS_PARTNER_SELECTION_REGISTER_V1.csv',index=False)
# Reify the two null summaries from the canonical run summary without rerunning.
for key,name in [('identity_null','IMF_IMTS_PARTNER_IDENTITY_NULL_SUMMARY_V1.json'),('outcome_null','IMF_IMTS_OUTCOME_NULL_SUMMARY_V1.json')]:
 x=dict(s[key]); x.update({'test_id':s['test_id'],'contract_sha256':s['contract_sha256'],'source':'IMF_IMTS_PARTNER_DEPENDENCE_SUMMARY_V1.json','statistic':'max_horizon_risk_difference','status':'diagnostic_complete'}); (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
# Build an auditable code-level exclusion register from the official codelist and reporter scope.
codes=json.loads((ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_CODELISTS_V1.json').read_text()); cl=next(c for c in codes['codelists'] if c['id']=='CL_IMTS_COUNTRY'); terms=['world','not specified','unspecified','special categories','countries & areas','other countries','all countries','regional aggregate','region','group','union','area not elsewhere included','oil related aggregate','services aggregate']; rows=[]
for code in cl['codes']:
 cid=code['id']; name=code.get('names',{}).get('en') or code.get('name') or cid; low=f'{cid} {name}'.lower()
 reasons=[]
 if cid=='G001': reasons.append('world_denominator_only')
 if any(t in low for t in terms): reasons.append('aggregate_or_unspecified_source_name')
 for rep in s['reporters']:
  if cid==rep: reasons.append(f'self_reporter_for_{rep}')
 if reasons: rows.append({'counterpart_code':cid,'source_name':name,'reasons':reasons,'eligible_as_named_partner':False,'contract':'IMF_IMTS_DOMINANT_PARTNER_DEPENDENCE_CONTRACT_V1'})
(OUT/'IMF_IMTS_PARTNER_EXCLUSION_REGISTER_V1.json').write_text(json.dumps({'source':'CL_IMTS_COUNTRY','source_artifact':'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_CODELISTS_V1.json','reporters':s['reporters'],'rules':'contract-defined code and source-name exclusions; no missing-as-zero','rows':rows,'count':len(rows)},ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'selection_register_rows':len(sel),'exclusion_rows':len(rows),'null_summaries':2},ensure_ascii=False,indent=2))
