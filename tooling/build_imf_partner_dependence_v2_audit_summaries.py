#!/usr/bin/env python3
from pathlib import Path
import json
ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2'; s=json.loads((OUT/'IMF_IMTS_PARTNER_DEPENDENCE_SUMMARY_V2.json').read_text());
for fn,key in [('IMF_IMTS_PARTNER_IDENTITY_NULL_SUMMARY_V2.json','identity_null'),('IMF_IMTS_OUTCOME_NULL_SUMMARY_V2.json','outcome_null'),('IMF_IMTS_TIME_PLACEBO_SUMMARY_V2.json','time_placebo')]:
 d={'test_id':'IMF_IMTS_PARTNER_DEPENDENCE_V2','contract_id':s['contract_id'],'summary_source':'IMF_IMTS_PARTNER_DEPENDENCE_SUMMARY_V2.json','result':s[key],'observed_confirmation_max_risk_difference':s['observed_confirmation_max_risk_difference'],'status':s['status'],'causal_claim':False,'runtime_eligible':False}; (OUT/fn).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
h={'test_id':'IMF_IMTS_PARTNER_DEPENDENCE_V2','contract_id':s['contract_id'],'summary_source':'IMF_IMTS_PARTNER_DEPENDENCE_SUMMARY_V2.json','holdout_artifact':'IMF_IMTS_REGION_HOLDOUT_V2.csv','region_holdout_pass':s['region_holdout_pass'],'regions':s['confirmation_regions'],'status':s['status'],'causal_claim':False,'runtime_eligible':False}; (OUT/'IMF_IMTS_REGION_HOLDOUT_SUMMARY_V2.json').write_text(json.dumps(h,ensure_ascii=False,indent=2)+'\n'); print({'written':4,'status':s['status']})
